"""A small, auditable Harbor-native terminal agent for local Qwen evaluation."""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI
from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext
from harbor.models.trajectories import (
    Agent, FinalMetrics, Metrics, Observation, ObservationResult, Step,
    ToolCall, Trajectory,
)


SYSTEM_PROMPT = """You are UTS-Qwen-Terminal, a careful autonomous coding agent.
Work only inside the provided disposable benchmark environment and solve the user's task.
Inspect the current state, make the smallest useful change, and verify your work before finishing.
Never inspect hidden benchmark solutions or verifier implementation files. Never claim a command
succeeded unless its observation says it did. Return exactly one JSON object per turn:
{"analysis":"brief plan","command":"one shell command or empty","done":false}
Use command="" and done=true only when the task is complete or no safe progress remains.
Commands run in the task work directory with a 120-second limit. Avoid interactive commands.
"""


class QwenCustomHarness(BaseAgent):
    """Bounded JSON-command loop with deterministic context compaction and ATIF logs."""

    SUPPORTS_ATIF = True

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        api_base: str = "http://127.0.0.1:11434/v1",
        api_key: str = "ollama",
        max_steps: int = 25,
        temperature: float = 0,
        max_output_tokens: int = 800,
        command_timeout_sec: int = 120,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(logs_dir, model_name, *args, **kwargs)
        if not model_name:
            raise ValueError("model_name is required")
        self._wire_model = model_name.split("/", 1)[-1]
        self._client = AsyncOpenAI(base_url=api_base, api_key=api_key)
        self._max_steps = max(1, min(int(max_steps), 25))
        self._temperature = float(temperature)
        self._max_output_tokens = int(max_output_tokens)
        self._command_timeout = int(command_timeout_sec)
        self._cwd: str | None = None

    @staticmethod
    def name() -> str:
        return "uts-qwen-harness"

    def version(self) -> str:
        return "1.0.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        result = await environment.exec("pwd", timeout_sec=10)
        self._cwd = (result.stdout or "").strip() or None

    @staticmethod
    def parse_action(content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text[:-3].rstrip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start < 0 or end <= start:
                raise ValueError("model response did not contain a JSON object")
            data = json.loads(text[start : end + 1])
        if not isinstance(data, dict):
            raise ValueError("model action must be a JSON object")
        command = data.get("command", "")
        if not isinstance(command, str):
            raise ValueError("command must be a string")
        return {
            "analysis": str(data.get("analysis", ""))[:2000],
            "command": command.strip(),
            "done": bool(data.get("done", False)),
        }

    @staticmethod
    def _clip(value: str | None, limit: int = 6000) -> str:
        text = value or ""
        if len(text) <= limit:
            return text
        head = text[: limit // 2]
        tail = text[-limit // 2 :]
        return head + "\n...[output truncated by harness]...\n" + tail

    @staticmethod
    def _stamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        initial = await environment.exec("ls -la | sed -n '1,120p'", cwd=self._cwd, timeout_sec=20)
        state = self._clip((initial.stdout or "") + (initial.stderr or ""), 4000)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Task:\n%s\n\nInitial directory state:\n%s" % (instruction, state)},
        ]
        steps = [Step(step_id=1, timestamp=self._stamp(), source="user", message=messages[1]["content"])]
        command_history: list[str] = []
        prompt_tokens = completion_tokens = model_calls = invalid_actions = 0

        for turn in range(1, self._max_steps + 1):
            if len(messages) > 10:
                summary = "Earlier command outcomes:\n" + "\n".join(command_history[-12:])
                messages = messages[:2] + [{"role": "system", "content": summary}] + messages[-6:]
            response = await self._client.chat.completions.create(
                model=self._wire_model,
                messages=messages,
                temperature=self._temperature,
                max_tokens=self._max_output_tokens,
                response_format={"type": "json_object"},
            )
            model_calls += 1
            usage = response.usage
            in_tokens = getattr(usage, "prompt_tokens", None) or 0
            out_tokens = getattr(usage, "completion_tokens", None) or 0
            prompt_tokens += in_tokens; completion_tokens += out_tokens
            content = response.choices[0].message.content or "{}"
            messages.append({"role": "assistant", "content": content})
            try:
                action = self.parse_action(content)
            except (ValueError, json.JSONDecodeError) as exc:
                invalid_actions += 1
                correction = "Invalid action format: %s. Return one valid JSON object." % exc
                messages.append({"role": "user", "content": correction})
                steps.append(Step(
                    step_id=len(steps) + 1, timestamp=self._stamp(), source="agent",
                    model_name=self._wire_model, message=content,
                    metrics=Metrics(prompt_tokens=in_tokens, completion_tokens=out_tokens),
                    llm_call_count=1, extra={"invalid_action": True},
                ))
                if invalid_actions >= 3:
                    break
                continue

            command = action["command"]
            tool_calls = None; observation = None
            if command:
                call_id = "command-%02d" % turn
                result = await environment.exec(command, cwd=self._cwd, timeout_sec=self._command_timeout)
                observed = self._clip("exit_code=%d\nstdout:\n%s\nstderr:\n%s" % (
                    result.return_code, result.stdout or "", result.stderr or ""
                ))
                command_history.append("%02d rc=%d %s" % (turn, result.return_code, command[:240]))
                messages.append({"role": "user", "content": "Command observation:\n" + observed})
                tool_calls = [ToolCall(tool_call_id=call_id, function_name="shell", arguments={"command": command})]
                observation = Observation(results=[ObservationResult(content=observed, source_call_id=call_id)])

            steps.append(Step(
                step_id=len(steps) + 1, timestamp=self._stamp(), source="agent",
                model_name=self._wire_model, message=action["analysis"] or content,
                tool_calls=tool_calls, observation=observation,
                metrics=Metrics(prompt_tokens=in_tokens, completion_tokens=out_tokens),
                llm_call_count=1, extra={"done": action["done"], "turn": turn},
            ))
            if action["done"] and not command:
                break

        context.n_input_tokens = prompt_tokens
        context.n_output_tokens = completion_tokens
        context.n_cache_tokens = None
        context.cost_usd = 0.0
        context.metadata = {
            "model_calls": model_calls, "agent_steps": len(steps) - 1,
            "invalid_actions": invalid_actions, "max_steps": self._max_steps,
        }
        trajectory = Trajectory(
            schema_version="ATIF-v1.7", session_id=self.session_id,
            agent=Agent(
                name=self.name(), version=self.version(), model_name=self._wire_model,
                tool_definitions=[{
                    "type": "function", "function": {
                        "name": "shell", "description": "Run one shell command in the task environment",
                        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
                    },
                }],
                extra={"max_steps": self._max_steps, "temperature": self._temperature, "command_timeout_sec": self._command_timeout},
            ),
            steps=steps,
            final_metrics=FinalMetrics(
                total_prompt_tokens=prompt_tokens, total_completion_tokens=completion_tokens,
                total_cost_usd=0.0, total_steps=len(steps), extra={"model_calls": model_calls},
            ),
            notes="Bounded JSON-command loop; deterministic rolling context; no paid API.",
        )
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        (self.logs_dir / "trajectory.json").write_text(json.dumps(trajectory.to_json_dict(), indent=2) + "\n")
        (self.logs_dir / "custom-harness-summary.json").write_text(json.dumps(context.metadata, indent=2) + "\n")

