"""Saranya's minimal Harbor agent, v0.2.0.

Successor to my v0.1.0 (results/saranya-custom-harness/custom_agent/
my_gemini_agent.py on the saranya-exploration branch). The design is the
same one-command-per-turn loop, now with:

- the Stage 2 model and sampling settings (see openrouter.py for sources);
- no model-call ceiling, matching what C0 actually ran under: the official
  task deadline, enforced by Harbor cancelling the agent, is the only limit;
- a spending safety stop instead of a call ceiling (budget.py);
- the exit code and working directory carried between commands, because each
  Harbor exec() is a fresh `bash -c` with no shell state;
- Rosetta signature detection, so Mac host failures can be classified as
  infrastructure (classify.py).

Usage stats are written to the AgentContext after every model call, so they
survive Harbor cancelling the agent at the deadline.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from decimal import Decimal
import json
import platform
import re
import shlex
import sys
from pathlib import Path
from typing import Any, Callable

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from saranya_harness.budget import BudgetGuard
from saranya_harness.classify import scan_output
from saranya_harness.openrouter import MODEL, ModelError, OpenRouterClient, estimate_cost

VERSION = '0.2.0'
# Matches C0 at 004943b: a 60 s default per command (stage2/custom_backend.py:22,
# stage2/custom_jobs.py:12) that the agent may change per command to an integer
# from 1 to 3600 s; other values are refused with C0's error message
# (stage2/custom_jobs.py:13-14). Harbor's task deadline still wins.
DEFAULT_COMMAND_TIMEOUT_SECONDS = 60
MAX_COMMAND_TIMEOUT_SECONDS = 3600
TIMEOUT_ERROR = 'Timeout must be an integer between 1 and 3600 seconds'
_TIMEOUT_DIRECTIVE = re.compile(r'#\s*timeout\s*[=:]\s*(\S+)\s*', re.IGNORECASE)
OBSERVATION_HEAD_CHARS = 4_000
OBSERVATION_TAIL_CHARS = 6_000
# Keeps the prompt well inside the 1,048,576-token context window.
MAX_HISTORY_CHARS = 2_000_000
CONTEXT_ERROR_TYPES = frozenset({'context_length_exceeded', 'token_limit_exceeded', 'string_too_long'})
PWD_MARKER = '__SARANYA_HARNESS_PWD__'

SYSTEM_PROMPT = """You are solving a task inside a Linux container by running shell commands.

Each turn, reply with exactly one bash code block containing the next command(s):

```bash
<command>
```

Rules:
- Every command runs in a fresh bash process. The working directory is carried
  over for you; environment variables, aliases and shell functions are not.
  Put needed exports in the same command, or write them to a file and source it.
- Do not use interactive programs (editors, pagers, prompts). Use non-interactive
  flags such as -y, and write files with heredocs or printf.
- A command is stopped after 60 seconds by default. For a longer command, make
  the first line of the block `# timeout=SECONDS`, with a whole number of
  seconds up to 3600. Start long-running servers in the background with nohup,
  redirecting their output to a file.
- You will see the exit code and output of each command. Long output is truncated.
- The task has a fixed time limit. Work efficiently.
- When the task is fully complete and you have checked the result, reply with
  only the word DONE and no code block."""

_BLOCK = re.compile(r'```(?:bash|sh|shell)?[ \t]*\n(.*?)```', re.DOTALL)


def parse_action(content: str) -> tuple[str, str | None]:
    """Return ('command', text), ('done', None) or ('none', None)."""
    match = _BLOCK.search(content or '')
    if match:
        command = match.group(1).strip()
        return ('command', command) if command else ('none', None)
    if re.fullmatch(r'\s*DONE\.?\s*', content or '', re.IGNORECASE):
        return 'done', None
    return 'none', None


def command_timeout(command: str) -> int | None:
    """The timeout requested on the command's first line, the default, or None if invalid."""
    first_line = command.lstrip().split('\n', 1)[0]
    match = _TIMEOUT_DIRECTIVE.fullmatch(first_line)
    if match is None:
        return DEFAULT_COMMAND_TIMEOUT_SECONDS
    value = match.group(1)
    if not value.isdigit() or not 1 <= int(value) <= MAX_COMMAND_TIMEOUT_SECONDS:
        return None
    return int(value)


def wrap_command(command: str, cwd: str | None) -> str:
    prefix = f'cd {shlex.quote(cwd)} 2>/dev/null\n' if cwd else ''
    # The newline before the trailer lets heredocs in `command` terminate.
    return (f'{prefix}{command}\n__saranya_rc=$?\n'
            f'printf "\\n{PWD_MARKER}%s\\n" "$PWD"\nexit $__saranya_rc')


def split_marker(output: str) -> tuple[str, str | None]:
    index = output.rfind(PWD_MARKER)
    if index < 0:
        return output, None
    cwd = output[index + len(PWD_MARKER):].strip().splitlines()
    return output[:index].rstrip('\n'), (cwd[0] if cwd else None)


def truncate(text: str) -> str:
    limit = OBSERVATION_HEAD_CHARS + OBSERVATION_TAIL_CHARS
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return (text[:OBSERVATION_HEAD_CHARS] + f'\n[... {omitted} characters omitted ...]\n'
            + text[-OBSERVATION_TAIL_CHARS:])


def trim_history(messages: list[dict[str, str]], max_chars: int = MAX_HISTORY_CHARS) -> int:
    """Drop the oldest assistant/observation pairs, keeping system and task. Returns pairs dropped."""
    dropped = 0
    while sum(len(m['content']) for m in messages) > max_chars and len(messages) > 4:
        del messages[2:4]
        dropped += 1
    return dropped


def detect_host() -> str:
    if sys.platform == 'darwin' and platform.machine() == 'arm64':
        return 'mac'
    return f'{sys.platform}-{platform.machine()}'


@dataclass
class _Totals:
    model_calls: int = 0
    retries: int = 0
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    charged_usd: Decimal = Decimal(0)
    reported_cost_usd: Decimal = Decimal(0)
    cost_sources: dict[str, int] = field(default_factory=dict)
    unknown_usage_calls: int = 0
    unexpected_provider_calls: int = 0


class SaranyaMinimalAgent(BaseAgent):
    def __init__(self, logs_dir: Path, model_name: str | None = None, *,
                 per_trial_cap_usd: str | None = None, overall_cap_usd: str | None = None,
                 ledger_path: str | None = None,
                 client_factory: Callable[[], Any] | None = None, **kwargs):
        if model_name is not None and model_name.removeprefix('openrouter/') != MODEL:
            raise ValueError(f'This harness is pinned to {MODEL}; got {model_name}')
        super().__init__(logs_dir=logs_dir, model_name=model_name, **kwargs)
        self._per_trial_cap = per_trial_cap_usd
        self._overall_cap = overall_cap_usd
        self._ledger_path = ledger_path
        self._client_factory = client_factory or OpenRouterClient

    @staticmethod
    def name() -> str:
        return 'saranya-minimal'

    def version(self) -> str | None:
        return VERSION

    async def setup(self, environment: BaseEnvironment) -> None:
        return None

    def _trajectory(self, record: dict) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        with open(self.logs_dir / 'saranya-trajectory.jsonl', 'a') as log:
            log.write(json.dumps(record, default=str) + '\n')

    def _publish(self, context: AgentContext, totals: _Totals, metadata: dict) -> None:
        context.n_input_tokens = totals.input_tokens
        context.n_cache_tokens = totals.cached_tokens
        context.n_output_tokens = totals.output_tokens
        # Upper-bound cost: reported where available, estimated or reserved otherwise.
        context.cost_usd = float(totals.charged_usd)
        metadata.update(model_calls=totals.model_calls, retries=totals.retries,
                        charged_usd=str(totals.charged_usd),
                        reported_cost_usd=str(totals.reported_cost_usd),
                        cost_sources=dict(totals.cost_sources),
                        unknown_usage_calls=totals.unknown_usage_calls,
                        unexpected_provider_calls=totals.unexpected_provider_calls)
        context.metadata = dict(metadata)

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        trial_id = self.logs_dir.parent.name or 'unknown-trial'
        totals = _Totals()
        metadata: dict[str, Any] = {
            'harness': self.name(), 'version': VERSION, 'model': MODEL, 'host': detect_host(),
            'model_call_ceiling': None,
            'command_timeout_seconds': {'default': DEFAULT_COMMAND_TIMEOUT_SECONDS,
                                        'max': MAX_COMMAND_TIMEOUT_SECONDS},
            'stop_reason': None, 'budget_stop': None, 'infrastructure_signals': [],
            'history_pairs_dropped': 0,
        }
        try:
            guard = BudgetGuard.from_environment(trial_id, per_trial_cap_usd=self._per_trial_cap,
                                                 overall_cap_usd=self._overall_cap,
                                                 ledger_path=self._ledger_path)
        except ValueError as exc:
            metadata['stop_reason'] = 'no_spending_approval'
            metadata['stop_detail'] = str(exc)
            self.logger.error('Not calling the model: %s', exc)
            self._publish(context, totals, metadata)
            return
        metadata.update(per_trial_cap_usd=str(guard.per_trial_cap), overall_cap_usd=str(guard.overall_cap))

        client = self._client_factory()
        messages = [{'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': f'Task:\n{instruction}'}]
        cwd: str | None = None
        context_retry_used = False
        try:
            while True:
                metadata['history_pairs_dropped'] += trim_history(messages)
                prompt_chars = sum(len(m['content']) for m in messages)
                reservation, stop = guard.check(prompt_chars)
                if stop is not None:
                    metadata['stop_reason'] = f'budget_{stop.scope}'
                    metadata['budget_stop'] = {'scope': stop.scope, 'cap_usd': str(stop.cap_usd),
                                               'spent_usd': str(stop.spent_usd),
                                               'reservation_usd': str(stop.reservation_usd)}
                    self._trajectory({'event': 'budget_stop', **metadata['budget_stop']})
                    break
                try:
                    completion = await client.complete(messages)
                except asyncio.CancelledError:
                    # The request may have been delivered and billed: keep the reservation.
                    guard.record(charged_usd=reservation, cost_source='interrupted_reserved')
                    totals.charged_usd += reservation
                    totals.cost_sources['interrupted_reserved'] = totals.cost_sources.get('interrupted_reserved', 0) + 1
                    self._publish(context, totals, metadata)
                    raise
                except ModelError as exc:
                    guard.record(charged_usd=Decimal(0), cost_source='error_no_usage')
                    self._trajectory({'event': 'model_error', 'status': exc.status, 'error_type': exc.error_type})
                    if exc.error_type in CONTEXT_ERROR_TYPES and not context_retry_used:
                        context_retry_used = True
                        metadata['history_pairs_dropped'] += trim_history(messages, max_chars=prompt_chars // 2)
                        continue
                    metadata['stop_reason'] = 'model_error'
                    metadata['stop_detail'] = {'status': exc.status, 'error_type': exc.error_type}
                    break

                totals.model_calls += 1
                totals.retries += completion.retries
                if completion.provider != 'DeepInfra' or completion.model is None:
                    totals.unexpected_provider_calls += 1
                estimate = estimate_cost(completion.prompt_tokens, completion.completion_tokens)
                if completion.reported_cost_usd is not None:
                    charged, source = completion.reported_cost_usd, 'reported'
                    totals.reported_cost_usd += charged
                elif estimate is not None:
                    charged, source = estimate, 'estimated_list_price'
                else:
                    charged, source = reservation, 'unknown_reserved'
                    totals.unknown_usage_calls += 1
                guard.record(charged_usd=charged, cost_source=source, prompt_tokens=completion.prompt_tokens,
                             completion_tokens=completion.completion_tokens,
                             generation_id=completion.generation_id)
                totals.charged_usd += charged
                totals.cost_sources[source] = totals.cost_sources.get(source, 0) + 1
                totals.input_tokens += completion.prompt_tokens or 0
                totals.cached_tokens += completion.cached_tokens or 0
                totals.output_tokens += completion.completion_tokens or 0
                self._publish(context, totals, metadata)

                kind, command = parse_action(completion.content)
                self._trajectory({'event': 'model', 'call': totals.model_calls, 'action': kind,
                                  'command': command, 'charged_usd': str(charged), 'cost_source': source})
                messages.append({'role': 'assistant', 'content': completion.content})
                if kind == 'done':
                    metadata['stop_reason'] = 'done'
                    break
                if kind == 'none':
                    messages.append({'role': 'user', 'content':
                                     'No command found. Reply with exactly one ```bash code block, '
                                     'or only the word DONE if the task is complete.'})
                    continue

                observation = await self._execute(environment, command, cwd, metadata, totals.model_calls)
                cwd = observation.pop('cwd') or cwd
                messages.append({'role': 'user', 'content': observation['text']})
        finally:
            self._publish(context, totals, metadata)
            await client.aclose()

    async def _execute(self, environment: BaseEnvironment, command: str, cwd: str | None,
                       metadata: dict, call: int) -> dict:
        timeout = command_timeout(command)
        if timeout is None:
            self._trajectory({'event': 'exec_refused', 'call': call, 'reason': TIMEOUT_ERROR})
            return {'text': f'The command was not run: {TIMEOUT_ERROR}.', 'cwd': None}
        try:
            result = await environment.exec(wrap_command(command, cwd), timeout_sec=timeout)
        except RuntimeError as exc:
            text = f'The command did not finish: {exc}'
            self._trajectory({'event': 'exec_error', 'call': call, 'error': str(exc)})
            return {'text': text, 'cwd': None}
        # Docker merges stderr into stdout; stderr is kept in case another backend separates it.
        raw = (result.stdout or '') + (f'\n[stderr]\n{result.stderr}' if result.stderr else '')
        output, new_cwd = split_marker(raw)
        signals = scan_output(output)
        if signals:
            metadata['infrastructure_signals'].append({'call': call, 'signatures': signals})
        self._trajectory({'event': 'exec', 'call': call, 'return_code': result.return_code,
                          'output_chars': len(output), 'infrastructure_signals': signals})
        return {'text': f'Exit code: {result.return_code}\nOutput:\n{truncate(output)}', 'cwd': new_cwd}
