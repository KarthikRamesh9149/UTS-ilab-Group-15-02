"""v0.2 custom harness: one bash command per turn, sticky cwd, DONE only if idle.

Still markdown (not the group JSON contract). Fixes the three failures from the
pypi-server 0.1.0 probe.
"""
from __future__ import annotations

import json
import os
import re
import shlex
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI
from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

SYSTEM_PROMPT = """You are a terminal agent. Complete the task by running shell commands.

Rules:
- Think briefly, then emit exactly ONE bash command in a single fenced block.
- Never put more than one ```bash block in a reply. Never chain a full plan of
  separate commands; you will get the observation before the next turn.
- Each command already starts in the working directory shown in the observation.
  Prefer relative paths. `cd` is remembered by the harness.
- Do not use interactive programs (vim, nano, less). Use apt-get with -y if needed.
- Do not read hidden benchmark solutions or verifier files under /tests unless asked.
- After a failure, change approach. Do not repeat the same command.
- When the task is fully done, reply with DONE and no bash block.

Format:
<one or two sentences>
```bash
single command
```
"""

BASH_RE = re.compile(r"```(?:bash|sh)?\n(.*?)```", re.DOTALL | re.IGNORECASE)
DONE_RE = re.compile(r"^\s*DONE\s*$", re.MULTILINE | re.IGNORECASE)
CWD_MARK = "__CWD__"


class BashReActAgent(BaseAgent):
    """Harbor-native loop: prompt -> one bash command -> observe -> repeat."""

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        max_steps: int = 20,
        temperature: float = 0,
        max_output_tokens: int = 700,
        command_timeout_sec: int = 120,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(logs_dir, model_name, *args, **kwargs)
        if not model_name:
            raise ValueError("model_name is required")
        api_key = (
            os.environ.get("OPENROUTER_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or "ollama"
        )
        self._wire_model = model_name
        if self._wire_model.startswith("openrouter/"):
            self._wire_model = self._wire_model.split("/", 1)[1]
        elif self._wire_model.startswith("ollama/"):
            self._wire_model = self._wire_model.split("/", 1)[1]
        elif self._wire_model.startswith("openai/") and ":" in self._wire_model:
            # Harbor-style local tags like openai/qwen2.5-coder:1.5b
            self._wire_model = self._wire_model.split("/", 1)[1]
        base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE")
        if not base_url:
            base_url = "https://openrouter.ai/api/v1" if os.environ.get("OPENROUTER_API_KEY") else "http://127.0.0.1:11434/v1"
        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://github.com/UTS-ilab-Group-15-02",
                "X-Title": "UTS TB2.1 custom harness",
            },
        )
        self._max_steps = int(max_steps)
        self._temperature = float(temperature)
        self._max_output_tokens = int(max_output_tokens)
        self._command_timeout = int(command_timeout_sec)
        self._cwd = "/app"

    @staticmethod
    def name() -> str:
        return "bash-react-v0"

    def version(self) -> str:
        return "0.2.1"

    async def setup(self, environment: BaseEnvironment) -> None:
        result = await environment.exec("pwd", timeout_sec=10)
        pwd = (result.stdout or "").strip().splitlines()
        if result.return_code == 0 and pwd:
            self._cwd = pwd[-1].strip() or self._cwd

    @staticmethod
    def parse_action(text: str) -> tuple[str | None, bool, str | None]:
        fences = [block.strip() for block in BASH_RE.findall(text or "") if block.strip()]
        done = bool(DONE_RE.search(text or ""))
        if len(fences) > 1:
            return None, False, "multiple_fences"
        if len(fences) == 1:
            command = fences[0]
            if command.upper() == "DONE":
                return None, True, None
            return command, False, "done_ignored" if done else None
        if done:
            return None, True, None
        return None, False, "no_command"

    @staticmethod
    def _clip(text: str, limit: int = 4000) -> str:
        if len(text) <= limit:
            return text
        half = limit // 2
        return text[:half] + "\n...[truncated by harness]...\n" + text[-half:]

    def _wrapped(self, command: str) -> str:
        return (
            f"cd {shlex.quote(self._cwd)} || exit 1\n"
            f"{command}\n"
            "status=$?\n"
            f"printf '\\n{CWD_MARK}%s\\n' \"$(pwd)\"\n"
            "exit $status\n"
        )

    def _split_observation(self, stdout: str, stderr: str, return_code: int) -> str:
        combined = (stdout or "") + ("\n" + stderr if stderr else "")
        cwd = self._cwd
        visible = combined
        if CWD_MARK in combined:
            before, after = combined.rsplit(CWD_MARK, 1)
            visible = before
            cwd_line = after.strip().splitlines()
            if cwd_line:
                cwd = cwd_line[0].strip() or cwd
        self._cwd = cwd
        return self._clip(
            "cwd=%s\nexit_code=%s\noutput:\n%s" % (self._cwd, return_code, visible)
        )

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "Task:\n%s\n\nWorking directory starts at: %s"
                % (instruction, self._cwd),
            },
        ]
        prompt_tokens = completion_tokens = 0
        parse_failures = 0
        commands_run = 0
        turns: list[dict[str, Any]] = []
        stop_reason = "step_limit"

        for turn in range(1, self._max_steps + 1):
            response = await self._client.chat.completions.create(
                model=self._wire_model,
                messages=messages,
                temperature=self._temperature,
                max_tokens=self._max_output_tokens,
            )
            usage = response.usage
            in_tok = getattr(usage, "prompt_tokens", None) or 0
            out_tok = getattr(usage, "completion_tokens", None) or 0
            prompt_tokens += in_tok
            completion_tokens += out_tok
            content = (response.choices[0].message.content or "").strip()
            messages.append({"role": "assistant", "content": content})
            command, done, parse_error = self.parse_action(content)
            record: dict[str, Any] = {
                "turn": turn,
                "model_text": content[:2000],
                "command": command,
                "parse_error": parse_error,
                "cwd_before": self._cwd,
                "prompt_tokens": in_tok,
                "completion_tokens": out_tok,
            }
            if done:
                stop_reason = "model_done"
                turns.append(record)
                break
            if parse_error == "multiple_fences":
                parse_failures += 1
                messages.append({
                    "role": "user",
                    "content": (
                        "Rejected: more than one bash block. Send exactly one command "
                        "this turn. cwd=%s" % self._cwd
                    ),
                })
                turns.append(record)
                if parse_failures >= 4:
                    stop_reason = "parse_failures"
                    break
                continue
            if not command:
                parse_failures += 1
                messages.append({
                    "role": "user",
                    "content": (
                        "No bash command found. Send one ```bash block, or DONE if "
                        "finished. cwd=%s" % self._cwd
                    ),
                })
                record["parse_failure"] = True
                turns.append(record)
                if parse_failures >= 4:
                    stop_reason = "parse_failures"
                    break
                continue
            result = await environment.exec(
                self._wrapped(command), timeout_sec=self._command_timeout
            )
            commands_run += 1
            observed = self._split_observation(
                result.stdout or "", result.stderr or "", result.return_code
            )
            record["exit_code"] = result.return_code
            record["cwd_after"] = self._cwd
            record["observation"] = observed[:1500]
            turns.append(record)
            remaining = self._max_steps - turn
            messages.append({
                "role": "user",
                "content": "Observation:\n%s\n%d turns remain." % (observed, remaining),
            })

        context.n_input_tokens = prompt_tokens
        context.n_output_tokens = completion_tokens
        context.n_cache_tokens = None
        context.cost_usd = None
        context.metadata = {
            "stop_reason": stop_reason,
            "turns": len(turns),
            "commands_run": commands_run,
            "parse_failures": parse_failures,
            "max_steps": self._max_steps,
            "final_cwd": self._cwd,
            "harness_version": self.version(),
        }
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "agent": self.name(),
            "version": self.version(),
            "model": self._wire_model,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "metadata": context.metadata,
            "turns": turns,
        }
        (self.logs_dir / "v0-trace.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
