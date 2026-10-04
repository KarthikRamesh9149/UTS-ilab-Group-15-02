"""Offline smoke test: scripted model + real Docker containers, no API calls.

Scenario 1 (python image): sticky cwd, Deep Agents read_file through the backend,
the per-command kill, and the finish nudge after a failed last command.
Scenario 2 (image without python3): write_file still works, python-backed file
tools are hidden from the model, and an empty reply is nudged instead of ending.

    python experiments/harshini-deepagents/tests/smoke_offline.py
(run with the Python that has Harbor + deepagents installed)
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("OPENROUTER_API_KEY", "offline-test")

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402
from harbor.models.agent.context import AgentContext  # noqa: E402

from harness.agent import PYTHON_FILE_TOOLS, DeepAgentsHarness  # noqa: E402


class ScriptedModel(GenericFakeChatModel):
    """Replays fixed replies and records which tool names each call was offered."""

    offered: list = []

    def bind_tools(self, tools, **kwargs):
        names = sorted(getattr(t, "name", None) or t.get("name") for t in tools)
        self.offered.append(names)
        return self


def call(name: str, idx: int, **args) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"c{idx}"}])


class DockerEnv:
    def __init__(self, container: str):
        self.container = container

    async def exec(self, command: str, timeout_sec: int | None = None, **_):
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", self.container, "bash", "-c", command,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
        return SimpleNamespace(stdout=out.decode(), stderr=err.decode(), return_code=proc.returncode)


async def run_scenario(image: str, script: list[AIMessage]):
    container = subprocess.check_output(
        ["docker", "run", "-d", "--rm", "-w", "/app", image, "sleep", "600"], text=True
    ).strip()
    try:
        logs = Path(tempfile.mkdtemp()) / "agent"
        agent = DeepAgentsHarness(logs, model_name="openrouter/deepseek/deepseek-v4-flash-0731",
                                  agent_timeout_sec=300, default_command_timeout=5)
        model = ScriptedModel(messages=iter(script))
        model.offered = []
        agent._model = model
        env = DockerEnv(container)
        await agent.setup(env)
        context = AgentContext()
        await agent.run("smoke task", env, context)
        trace = json.loads((logs / "deepagents-trajectory.json").read_text(encoding="utf-8"))
        tool_out = [m["data"]["content"] for m in trace["messages"] if m["type"] == "tool"]
        final_file = subprocess.run(
            ["docker", "exec", container, "cat", "/app/out/note.txt"], capture_output=True, text=True
        ).stdout
        return tool_out, context.metadata, model.offered, final_file
    finally:
        subprocess.run(["docker", "rm", "-f", container], capture_output=True)


async def main() -> int:
    checks: dict[str, bool] = {}

    out, meta, _, _ = await run_scenario("python:3.12-slim", [
        call("execute", 1, command="mkdir -p /tmp/w && cd /tmp/w && echo hello > a.txt"),
        call("execute", 2, command="pwd && cat a.txt"),
        call("read_file", 3, file_path="/tmp/w/a.txt"),
        call("execute", 4, command="sleep 30"),
        AIMessage(content="Done."),
        call("execute", 5, command="true"),
        AIMessage(content="Done after nudge."),
    ])
    checks["sticky cwd"] = "/tmp/w" in out[1] and "hello" in out[1]
    checks["read_file via backend"] = "hello" in out[2]
    checks["command killed at cap"] = "killed after" in out[3]
    checks["finish nudge fired"] = meta["finish_nudges"] == 1
    checks["stopped by model"] = meta["stop_reason"] == "model_done"

    out, meta, offered, note = await run_scenario("debian:bookworm-slim", [
        call("write_file", 1, file_path="/app/out/note.txt", content="written without python\n"),
        AIMessage(content=""),
        call("execute", 2, command="cat /app/out/note.txt"),
        AIMessage(content="Done."),
    ])
    checks["no-python image detected"] = meta["image_has_python3"] is False
    checks["write_file without python3"] = note == "written without python\n"
    checks["python file tools hidden"] = bool(offered) and not (PYTHON_FILE_TOOLS & set(offered[-1]))
    checks["empty reply nudged"] = meta["empty_reply_nudges"] == 1 and "written without python" in out[-1]

    for name, ok in checks.items():
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
