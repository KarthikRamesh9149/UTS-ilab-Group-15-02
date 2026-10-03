"""Harbor agent: Deep Agents (LangGraph) controller for Terminal-Bench 2.1.

Same pinned model and provider route as the group study (DeepSeek V4 Flash 0731 on
DeepInfra FP8 via OpenRouter). Design levers, relative to the group's C0-NC agent:

- One blocking `execute` tool with a sticky working directory and a default
  per-command cap; slow work is pushed to background jobs that the model polls.
- Remaining wall-clock time is shown to the model on every turn, without editing
  the system prompt (keeps the provider's prefix cache valid).
- If the model stops while its last command failed, it is sent back to fix or
  verify, at most `max_finish_nudges` times.
- `write_todos` planning stays enabled; sub-agents and summarisation are off.

Run with:
    harbor run ... -a harness.agent:DeepAgentsHarness \
        -m openrouter/deepseek/deepseek-v4-flash-0731
with `experiments/harshini-deepagents` on PYTHONPATH and OPENROUTER_API_KEY set.
"""
from __future__ import annotations

import asyncio
import json
import os
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deepagents import (
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    create_deep_agent,
    register_harness_profile,
)
from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, HumanMessage, messages_to_dict
from langchain_openai import ChatOpenAI
from langsmith.run_helpers import tracing_context

from harness.backend import Deadline, HarborShellBackend

PINNED_MODEL = "deepseek/deepseek-v4-flash-0731"
PROVIDER_ROUTE = {
    "only": ["deepinfra/fp8"],
    "order": ["deepinfra/fp8"],
    "allow_fallbacks": False,
    "require_parameters": True,
    "quantizations": ["fp8"],
}
FALLBACK_TIMEOUT_SEC = 900.0

SYSTEM_PROMPT = """You are an autonomous terminal agent solving a task inside a Linux container. Nobody will answer questions; keep working until the task is complete.

How to work:
- Run shell commands with the `execute` tool. The working directory persists between calls (`cd` is remembered). File tools (read_file, write_file, edit_file, ls, grep, glob) need absolute paths.
- Commands are killed after {default_timeout}s unless you pass a larger `timeout`. For builds, installs, servers, training or anything slow, start it in the background (`nohup CMD > /tmp/NAME.log 2>&1 &`) and poll the log instead of blocking.
- Never start interactive programs (vim, nano, less, top, a bare python REPL). Use non-interactive flags such as `apt-get install -y`.
- Anything you deliver (scripts, configs, programs) must work with the tools and packages that were already on the image. The grader may run it in a fresh environment where packages you installed are missing, so prefer the standard library and existing command-line tools.
- For multi-step tasks, plan with write_todos and keep it updated.
- After an error, read it and change approach. Do not repeat a failing command unchanged.
- Do not search for or read the benchmark's tests or reference solutions.
- Before finishing, check every requirement in the task against the real result: exact paths, file names, formats, permissions, and any service that must still be running.
- Each turn reports the time remaining. When time is short, stop exploring and secure the required outputs.
- When the task is done, reply with a short summary and no tool call."""


class DeadlineNote(AgentMiddleware):
    """Append the remaining time as a trailing message on each model call (not stored in state)."""

    def __init__(self, deadline: Deadline):
        super().__init__()
        self.deadline = deadline

    def _note(self) -> HumanMessage:
        left = self.deadline.remaining()
        frac = left / self.deadline.budget if self.deadline.budget else 0.0
        if frac <= 0.05:
            phase = "Almost out of time: finish the required outputs now; do not start anything new."
        elif frac <= 0.20:
            phase = "Low on time: wrap up and verify the required outputs."
        else:
            phase = "Continue."
        return HumanMessage(
            content=f"[harness] {int(left)}s of {int(self.deadline.budget)}s remaining. {phase}"
        )

    async def awrap_model_call(self, request, handler):
        return await handler(request.override(messages=[*request.messages, self._note()]))

    def wrap_model_call(self, request, handler):
        return handler(request.override(messages=[*request.messages, self._note()]))


class DeepAgentsHarness(BaseAgent):
    @staticmethod
    def name() -> str:
        return "uts-harshini-deepagents"

    def version(self) -> str:
        return "0.1.1"

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        *args: Any,
        temperature: float = 1.0,
        reasoning_effort: str = "high",
        max_output_tokens: int = 384000,
        default_command_timeout: int = 300,
        agent_timeout_sec: float | None = None,
        max_finish_nudges: int = 2,
        **kwargs: Any,
    ) -> None:
        super().__init__(logs_dir, model_name, *args, **kwargs)
        wire = model_name or PINNED_MODEL
        for prefix in ("openrouter/", "openai/"):
            if wire.startswith(prefix):
                wire = wire[len(prefix):]
        if wire != PINNED_MODEL:
            raise ValueError(f"model must be {PINNED_MODEL}, got {wire}")
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not set")
        self._model = ChatOpenAI(
            model=wire,
            base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key=api_key,
            temperature=float(temperature),
            max_tokens=int(max_output_tokens),
            max_retries=3,
            timeout=900,
            streaming=False,
            use_responses_api=False,
            extra_body={
                "provider": PROVIDER_ROUTE,
                "reasoning": {"effort": str(reasoning_effort)},
                "usage": {"include": True},
            },
        )
        self._default_command_timeout = int(default_command_timeout)
        self._timeout_override = float(agent_timeout_sec) if agent_timeout_sec else None
        self._max_finish_nudges = int(max_finish_nudges)
        self._start_cwd = "/app"
        register_harness_profile(
            "openai:" + PINNED_MODEL,
            HarnessProfile(
                general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
                excluded_middleware=frozenset({"SummarizationMiddleware"}),
            ),
        )

    def _task_timeout(self) -> tuple[float, str]:
        """Official agent timeout from the task's cached task.toml (Harbor only passes it to Oracle)."""
        if self._timeout_override:
            return self._timeout_override, "agent_kwarg"
        try:
            trial = json.loads((self.logs_dir.parent / "config.json").read_text(encoding="utf-8"))
            name = trial["task"]["name"]
            digest = trial["task"]["ref"].split(":")[-1]
            toml_path = Path.home() / ".cache/harbor/tasks/packages" / name / digest / "task.toml"
            config = tomllib.loads(toml_path.read_text(encoding="utf-8"))
            return float(config["agent"]["timeout_sec"]), "task_toml"
        except Exception:
            return FALLBACK_TIMEOUT_SEC, "fallback"

    async def setup(self, environment: BaseEnvironment) -> None:
        result = await environment.exec("pwd", timeout_sec=15)
        lines = (result.stdout or "").strip().splitlines()
        if result.return_code == 0 and lines and lines[-1].startswith("/"):
            self._start_cwd = lines[-1].strip()
        check = await environment.exec("command -v bash && command -v timeout && command -v base64", timeout_sec=15)
        if check.return_code != 0:
            raise RuntimeError("task image lacks bash, timeout or base64")

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        budget, budget_source = self._task_timeout()
        deadline = Deadline(budget)
        backend = HarborShellBackend(
            environment,
            deadline,
            identifier=self.session_id or "trial",
            start_cwd=self._start_cwd,
            default_timeout=self._default_command_timeout,
        )
        graph = create_deep_agent(
            model=self._model,
            tools=[],
            system_prompt=SYSTEM_PROMPT.format(default_timeout=self._default_command_timeout),
            backend=backend,
            middleware=[DeadlineNote(deadline)],
            subagents=[],
        )
        state: dict[str, Any] = {
            "messages": [
                HumanMessage(
                    content=(
                        f"Task:\n{instruction}\n\n"
                        f"Starting directory: {self._start_cwd}\n"
                        f"Time budget: {int(budget)} seconds."
                    )
                )
            ]
        }
        stop_reason = "model_done"
        nudges = 0
        error_type = None
        try:
            with tracing_context(enabled=False):
                async with asyncio.timeout(max(30.0, budget - 15)):
                    while True:
                        async for snapshot in graph.astream(
                            state, config={"recursion_limit": 10000}, stream_mode="values"
                        ):
                            state = snapshot
                        failed = backend.last_exit_code not in (None, 0)
                        if failed and nudges < self._max_finish_nudges and deadline.remaining() > 60:
                            nudges += 1
                            state = {
                                **state,
                                "messages": [
                                    *state["messages"],
                                    HumanMessage(
                                        content=(
                                            f"[harness] Your last command failed (exit {backend.last_exit_code}). "
                                            "Fix it, or confirm the task requirements are already met, "
                                            "before finishing."
                                        )
                                    ),
                                ],
                            }
                            continue
                        break
        except TimeoutError:
            stop_reason = "deadline"
        except BaseException as exc:
            stop_reason = "error"
            error_type = type(exc).__name__
            raise
        finally:
            self._record(context, state, backend, budget, budget_source, stop_reason, nudges, error_type)

    def _record(self, context, state, backend, budget, budget_source, stop_reason, nudges, error_type) -> None:
        messages = state.get("messages", [])
        tokens_in = tokens_out = cache = 0
        cost = 0.0
        model_calls = 0
        for message in messages:
            if not isinstance(message, AIMessage):
                continue
            model_calls += 1
            usage = message.usage_metadata or {}
            tokens_in += usage.get("input_tokens", 0) or 0
            tokens_out += usage.get("output_tokens", 0) or 0
            cache += (usage.get("input_token_details") or {}).get("cache_read", 0) or 0
            token_usage = (message.response_metadata or {}).get("token_usage") or {}
            cost += float(token_usage.get("cost") or 0.0)
        context.n_input_tokens = tokens_in
        context.n_output_tokens = tokens_out
        context.n_cache_tokens = cache
        context.cost_usd = cost or None
        context.metadata = {
            "harness": self.name(),
            "harness_version": self.version(),
            "pinned_model": PINNED_MODEL,
            "stop_reason": stop_reason,
            "error_type": error_type,
            "agent_budget_sec": budget,
            "agent_budget_source": budget_source,
            "model_calls": model_calls,
            "finish_nudges": nudges,
            **backend.stats(),
        }
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        (self.logs_dir / "deepagents-trajectory.json").write_text(
            json.dumps(
                {
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": context.metadata,
                    "messages": messages_to_dict(messages),
                },
                indent=2,
                default=str,
            )
            + "\n",
            encoding="utf-8",
        )
