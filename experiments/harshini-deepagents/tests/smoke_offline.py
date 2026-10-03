"""Offline smoke test: scripted model + a real Docker container, no API calls.

Checks sticky cwd, Deep Agents file tools through the backend, the per-command
kill, and the finish nudge after a failed last command.

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

from harness.agent import DeepAgentsHarness  # noqa: E402

IMAGE = "python:3.12-slim"


class ScriptedModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
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


async def main() -> int:
    container = subprocess.check_output(
        ["docker", "run", "-d", "--rm", "-w", "/app", IMAGE, "sleep", "600"], text=True
    ).strip()
    try:
        logs = Path(tempfile.mkdtemp()) / "agent"
        agent = DeepAgentsHarness(logs, model_name="openrouter/deepseek/deepseek-v4-flash-0731",
                                  agent_timeout_sec=300, default_command_timeout=5)
        agent._model = ScriptedModel(messages=iter([
            call("execute", 1, command="mkdir -p /tmp/w && cd /tmp/w && echo hello > a.txt"),
            call("execute", 2, command="pwd && cat a.txt"),
            call("read_file", 3, file_path="/tmp/w/a.txt"),
            call("execute", 4, command="sleep 30"),
            AIMessage(content="Done."),
            call("execute", 5, command="true"),
            AIMessage(content="Done after nudge."),
        ]))
        env = DockerEnv(container)
        await agent.setup(env)
        context = AgentContext()
        await agent.run("smoke task", env, context)

        trace = json.loads((logs / "deepagents-trajectory.json").read_text(encoding="utf-8"))
        tool_out = [m["data"]["content"] for m in trace["messages"] if m["type"] == "tool"]
        meta = context.metadata
        checks = {
            "sticky cwd": "/tmp/w" in tool_out[1] and "hello" in tool_out[1],
            "read_file via backend": "hello" in tool_out[2],
            "command killed at cap": "killed after" in tool_out[3],
            "finish nudge fired": meta["finish_nudges"] == 1,
            "stopped by model": meta["stop_reason"] == "model_done",
        }
        for name, ok in checks.items():
            print(f"{'PASS' if ok else 'FAIL'}  {name}")
        print(json.dumps(meta, indent=2))
        return 0 if all(checks.values()) else 1
    finally:
        subprocess.run(["docker", "rm", "-f", container], capture_output=True)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
