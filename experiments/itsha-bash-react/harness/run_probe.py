"""Optional OpenRouter helper. Do not use unless the group has API credit.

Usage: python harness/run_probe.py <v0|terminus-2> <task> <job-name>
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = "terminal-bench/terminal-bench-2-1"
MODEL = "openai/gpt-4o-mini"


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        raise SystemExit("missing .env — this script is the paid-API path")
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())
    os.environ.setdefault("OPENAI_API_KEY", os.environ.get("OPENROUTER_API_KEY", ""))
    os.environ.setdefault("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
    os.environ.setdefault("OPENAI_API_BASE", "https://openrouter.ai/api/v1")
    os.environ["PYTHONPATH"] = str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit("usage: run_probe.py <v0|terminus-2> <task> <job-name>")
    agent, task, job_name = sys.argv[1], sys.argv[2], sys.argv[3]
    load_env()
    include = task if task.startswith("terminal-bench/") else "terminal-bench/" + task
    cmd = [
        "harbor", "run", "-d", DATASET, "-m", MODEL,
        "-i", include, "-n", "1", "-k", "1",
        "-o", str(ROOT / "jobs"), "--job-name", job_name,
        "--yes", "--env-file", str(ROOT / ".env"),
    ]
    if agent == "v0":
        cmd += ["-a", "harness.v0_bash_agent:BashReActAgent", "--ak", "max_steps=20"]
    elif agent == "terminus-2":
        cmd[cmd.index("-m") + 1] = "openrouter/openai/gpt-4o-mini"
        cmd += ["-a", "terminus-2"]
    else:
        raise SystemExit("agent must be v0 or terminus-2")
    print("RUN", " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
