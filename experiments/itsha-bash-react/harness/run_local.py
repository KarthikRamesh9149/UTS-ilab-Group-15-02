"""Run the custom harness on a TB 2.1 task using local Ollama. No paid API.

Usage:
  python harness/run_local.py openssl-selfsigned-cert
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = "terminal-bench/terminal-bench-2-1"
MODEL = "qwen2.5-coder:1.5b"


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python harness/run_local.py <task-name>")
    task = sys.argv[1]
    include = task if task.startswith("terminal-bench/") else "terminal-bench/" + task
    os.environ["OPENAI_BASE_URL"] = "http://127.0.0.1:11434/v1"
    os.environ["OPENAI_API_BASE"] = "http://127.0.0.1:11434/v1"
    os.environ["OPENAI_API_KEY"] = "ollama"
    os.environ.pop("OPENROUTER_API_KEY", None)
    os.environ["PYTHONPATH"] = str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")
    job = "v021-local-%s" % task.replace("terminal-bench/", "")
    cmd = [
        "harbor", "run", "-d", DATASET,
        "-a", "harness.v0_bash_agent:BashReActAgent",
        "-m", MODEL, "-i", include, "-n", "1", "-k", "1",
        "-o", str(ROOT / "jobs"), "--job-name", job, "--yes",
        "--ak", "max_steps=12",
    ]
    print("LOCAL RUN model=%s task=%s" % (MODEL, include), flush=True)
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
