"""A small, auditable Harbor-native terminal agent for local Qwen evaluation."""
import json
import re
import shlex
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


SYSTEM_PROMPT = """You are UTS-Qwen-Terminal, an autonomous terminal coding agent.
Solve the user's task inside the disposable benchmark environment. The task text is authoritative.

Operating protocol:
1. DISCOVER: inspect relevant paths and existing files. If the task names an absolute output path,
   inspect its parent and create the requested artifact at that exact path. A path ending in a file
   extension must be a regular file, never a directory or a similarly named nested substitute.
2. IMPLEMENT: make a complete, minimal solution. Do not stop after merely creating a directory,
   describing code, or printing code; the required files must actually exist in the environment.
3. VERIFY: run a focused noninteractive syntax/build/test command. Read failures and repair them.
4. FINISH only after an implementation command and a successful verification command.

Never inspect hidden benchmark solutions, reference answers, or verifier implementation files.
Never claim success unless command observations support it. Avoid interactive tools and broad or
destructive system commands. Do not install interpreters, compilers, or large dependencies merely
to validate a file; when a runtime is absent, use available POSIX tools to check that the requested
artifact is nonempty and inspect its required structure. You have at most 25 model turns, so prefer
direct progress over prose. Every non-finish turn must contain a useful command, not an acknowledgement.

Return exactly one JSON object per turn and no markdown:
{"analysis":"brief evidence-based reasoning","phase":"inspect|edit|test|finish","command":"one shell command or empty","done":false}
Set phase="finish", command="", done=true only after the completion conditions above. When a command
fails, diagnose its observation and change approach. Pipelines and short command chains are allowed.
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
        return "2.2.0"

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
            "phase": str(data.get("phase", "inspect")).strip().lower(),
            "command": command.strip(),
            "done": bool(data.get("done", False)),
        }

    @staticmethod
    def command_is_safe(command: str) -> tuple[bool, str]:
        """Reject only clearly unsafe or interactive actions; benchmark containers are disposable."""
        normalized = " ".join(command.lower().split())
        blocked = (
            ("rm -rf /", "broad filesystem deletion"),
            ("mkfs", "filesystem formatting"),
            ("shutdown", "system shutdown"),
            ("reboot", "system reboot"),
            (":(){", "fork bomb"),
            ("vim ", "interactive editor"),
            ("nano ", "interactive editor"),
        )
        for needle, reason in blocked:
            if needle in normalized:
                return False, reason
        return True, ""

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

    @staticmethod
    def requested_artifacts(instruction: str) -> list[str]:
        """Extract explicit absolute file paths for recovery hints, without reading them."""
        paths = re.findall(r"(?<![\w.])(/[A-Za-z0-9_./-]+\.[A-Za-z0-9_+-]+)", instruction)
        return list(dict.fromkeys(path.rstrip(".,:;)") for path in paths))[:8]

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        initial = await environment.exec(
            "pwd; ls -la | sed -n '1,120p'; "
            "find . -maxdepth 2 -type f -not -path '*/.git/*' | sort | sed -n '1,160p'",
            cwd=self._cwd, timeout_sec=20,
        )
        state = self._clip((initial.stdout or "") + (initial.stderr or ""), 4000)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Task:\n%s\n\nInitial directory state:\n%s" % (instruction, state)},
        ]
        steps = [Step(step_id=1, timestamp=self._stamp(), source="user", message=messages[1]["content"])]
        command_history: list[str] = []
        prompt_tokens = completion_tokens = model_calls = invalid_actions = 0
        edit_successes = test_successes = denied_finishes = stalled_actions = empty_actions = 0
        seen_commands: dict[str, int] = {}
        termination_reason = "step_limit"
        artifacts = self.requested_artifacts(instruction)
        artifact_hint = artifacts[0] if artifacts else "the requested output file"

        for turn in range(1, self._max_steps + 1):
            if len(messages) > 12:
                summary = (
                    "Durable execution state (do not repeat completed work):\n"
                    + "\n".join(command_history[-14:])
                    + "\nCompletion gates: successful edits=%d, successful tests=%d."
                    % (edit_successes, test_successes)
                )
                messages = messages[:2] + [{"role": "system", "content": summary}] + messages[-6:]
            remaining = self._max_steps - turn + 1
            if remaining in (8, 4, 2):
                messages.append({
                    "role": "system",
                    "content": (
                        "%d turns remain. Prioritize completing the artifact and validation. "
                        "If a language runtime is unavailable, use: test -s %s && sed -n '1,240p' %s"
                        % (remaining, artifact_hint, artifact_hint)
                    ),
                })
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
            phase = action["phase"] if action["phase"] in {"inspect", "edit", "test", "finish"} else "inspect"
            normalized_command = command.strip().lower()
            if command and phase != "finish" and (
                normalized_command.startswith(("test ", "grep ", "pytest ", "python -m py_compile", "python3 -m py_compile"))
                or " && test " in normalized_command
            ):
                phase = "test"
            if not command and not action["done"]:
                empty_actions += 1
                invalid_actions += 1
                messages.append({
                    "role": "user",
                    "content": (
                        "No command was provided, so no progress occurred. Do not acknowledge the last observation. "
                        "Return the next concrete inspect, edit, or test command now. Target artifact: %s." % artifact_hint
                    ),
                })
            if action["done"] and command:
                action["done"] = False
                messages.append({"role": "user", "content": "A finish action must have command empty. Execute the command first."})
            if action["done"] and not command:
                if edit_successes < 1 or test_successes < 1:
                    denied_finishes += 1
                    action["done"] = False
                    missing = []
                    if edit_successes < 1:
                        missing.append("a successful phase=edit command that creates or changes the requested artifact")
                    if test_successes < 1:
                        missing.append("a successful phase=test validation command")
                    messages.append({
                        "role": "user",
                        "content": "Finish denied by the evidence gate. Missing: %s. Continue working; do not merely restate the plan." % "; ".join(missing),
                    })
                else:
                    termination_reason = "evidence_gated_finish"
            if command:
                call_id = "command-%02d" % turn
                safe, unsafe_reason = self.command_is_safe(command)
                repeats = seen_commands.get(command, 0)
                seen_commands[command] = repeats + 1
                if not safe:
                    class RejectedResult:
                        return_code = 126
                        stdout = ""
                        stderr = "Rejected by harness safety policy: %s" % unsafe_reason
                    result = RejectedResult()
                elif repeats >= 2:
                    stalled_actions += 1
                    class StalledResult:
                        return_code = 125
                        stdout = ""
                        stderr = "Rejected repeated command: use the prior observations and change approach."
                    result = StalledResult()
                else:
                    result = await environment.exec(command, cwd=self._cwd, timeout_sec=self._command_timeout)
                observed = self._clip("exit_code=%d\nphase=%s\nstdout:\n%s\nstderr:\n%s" % (
                    result.return_code, phase, result.stdout or "", result.stderr or ""
                ), 8000)
                artifact_contract_ok = True
                if result.return_code == 0 and phase == "edit" and artifacts:
                    quoted = shlex.quote(artifacts[0])
                    contract = await environment.exec(
                        "if [ -f %s ]; then echo 'artifact_contract=regular_file'; "
                        "elif [ -d %s ]; then echo 'artifact_contract=ERROR_expected_file_found_directory'; exit 41; "
                        "else echo 'artifact_contract=ERROR_exact_file_missing'; exit 42; fi" % (quoted, quoted),
                        cwd=self._cwd, timeout_sec=15,
                    )
                    artifact_contract_ok = contract.return_code == 0
                    observed += "\nartifact check:\n" + self._clip(
                        (contract.stdout or "") + (contract.stderr or ""), 1200
                    )
                command_history.append("%02d phase=%s rc=%d %s" % (turn, phase, result.return_code, command[:240]))
                if result.return_code == 0 and phase == "edit" and artifact_contract_ok:
                    edit_successes += 1
                if result.return_code == 0 and phase == "test":
                    test_successes += 1
                messages.append({"role": "user", "content": "Command observation:\n" + observed})
                if result.return_code == 0 and phase == "edit" and not artifact_contract_ok:
                    messages.append({
                        "role": "system",
                        "content": (
                            "MANDATORY ARTIFACT REPAIR: the exact required file %s is missing or is a directory. "
                            "Remove only that mistaken path if needed, create its parent directory, and write the "
                            "complete implementation directly to the exact file path."
                            % artifact_hint
                        ),
                    })
                if result.return_code == 127:
                    messages.append({
                        "role": "system",
                        "content": (
                            "MANDATORY RECOVERY: the executable was unavailable. Do not install it and do not repeat "
                            "that command. Use existing shell tools. A valid fallback check is: "
                            "test -s %s && grep -n . %s | sed -n '1,240p'. Mark that command phase=test."
                            % (artifact_hint, artifact_hint)
                        ),
                    })
                elif result.return_code == 125:
                    messages.append({
                        "role": "system",
                        "content": (
                            "MANDATORY RECOVERY: this exact command is stalled and will never be executed again. "
                            "Choose a different command now. Inspect or validate %s with POSIX shell tools."
                            % artifact_hint
                        ),
                    })
                tool_calls = [ToolCall(tool_call_id=call_id, function_name="shell", arguments={"command": command})]
                observation = Observation(results=[ObservationResult(content=observed, source_call_id=call_id)])

            steps.append(Step(
                step_id=len(steps) + 1, timestamp=self._stamp(), source="agent",
                model_name=self._wire_model, message=action["analysis"] or content,
                tool_calls=tool_calls, observation=observation,
                metrics=Metrics(prompt_tokens=in_tokens, completion_tokens=out_tokens),
                llm_call_count=1, extra={"done": action["done"], "turn": turn, "phase": phase},
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
            "successful_edit_actions": edit_successes, "successful_test_actions": test_successes,
            "denied_finish_attempts": denied_finishes, "stalled_actions": stalled_actions,
            "empty_actions": empty_actions, "requested_artifacts": artifacts,
            "termination_reason": termination_reason,
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
                extra={
                    "max_steps": self._max_steps, "temperature": self._temperature,
                    "command_timeout_sec": self._command_timeout,
                    "completion_gate": "successful_edit_and_test",
                },
            ),
            steps=steps,
            final_metrics=FinalMetrics(
                total_prompt_tokens=prompt_tokens, total_completion_tokens=completion_tokens,
                total_cost_usd=0.0, total_steps=len(steps), extra={"model_calls": model_calls},
            ),
            notes="Evidence-gated phase loop; repeat/safety guards; deterministic rolling context; no paid API.",
        )
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        (self.logs_dir / "trajectory.json").write_text(json.dumps(trajectory.to_json_dict(), indent=2) + "\n")
        (self.logs_dir / "custom-harness-summary.json").write_text(json.dumps(context.metadata, indent=2) + "\n")
