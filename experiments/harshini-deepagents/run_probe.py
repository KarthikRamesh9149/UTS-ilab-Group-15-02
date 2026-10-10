#!/usr/bin/env python3
"""Run Terminal-Bench 2.1 tasks one at a time with this harness, pinned Terminus-2 or Oracle.

    python experiments/harshini-deepagents/run_probe.py oracle --dev20
    python experiments/harshini-deepagents/run_probe.py custom openssl-selfsigned-cert
    python experiments/harshini-deepagents/run_probe.py terminus --dev20 --run-name dev20-terminus2-r1
    python experiments/harshini-deepagents/run_probe.py custom --dev20 --run-name dev20-v0.1.0

Each task is its own Harbor job under jobs/<run-name>/<task>/. Tasks that already
have a scored result.json are skipped, so an interrupted run can be resumed.
For paid runs, the OpenRouter key's spend is printed before and after.
Keys can come from the environment or a git-ignored `.env` at the repo root.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATASET = "terminal-bench/terminal-bench-2-1"
MODEL = "openrouter/deepseek/deepseek-v4-flash-0731"
AGENTS = {
    "custom": "harness.agent:DeepAgentsHarness",
    "terminus": "harness.terminus_pinned:PinnedTerminus2",
}


def dev20() -> list[str]:
    lines = (HERE / "dev20_tasks.txt").read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def load_dotenv(path: Path) -> None:
    """Read KEY=value lines from the git-ignored repo-root .env; variables already set win."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and not os.environ.get(key, "").strip():
            os.environ[key] = value


def key_usage() -> float | None:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        return None
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/key", headers={"Authorization": f"Bearer {key}"}
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return float(json.loads(response.read())["data"]["usage"])
    except Exception:
        return None


def scored(task_dir: Path) -> bool:
    for result in task_dir.glob("*/result.json"):
        try:
            data = json.loads(result.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (data.get("verifier_result") or {}).get("rewards") is not None:
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("agent", choices=("custom", "terminus", "oracle"))
    parser.add_argument("tasks", nargs="*")
    parser.add_argument("--dev20", action="store_true", help="run the 20-task dev subset")
    parser.add_argument("--run-name")
    parser.add_argument("--model", default=MODEL.removeprefix("openrouter/"),
                        help="OpenRouter model id (must be listed in harness.agent.MODEL_SETTINGS)")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")

    tasks = dev20() if args.dev20 else args.tasks
    if not tasks:
        parser.error("give task IDs or --dev20")
    run_name = args.run_name or f"{args.agent}-{datetime.now():%Y%m%d_%H%M%S}"
    run_dir = ROOT / "jobs" / "harshini-deepagents" / run_name

    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(HERE), env.get("PYTHONPATH", "")])
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    paid = args.agent != "oracle"
    if paid and not env.get("OPENROUTER_API_KEY", "").strip():
        raise SystemExit("OPENROUTER_API_KEY is not set")
    before = key_usage() if paid else None
    if before is not None:
        print(f"OpenRouter key usage before: ${before:.4f}")
    if args.agent == "custom":
        tracing = env.get("LANGFUSE_PUBLIC_KEY") and env.get("LANGFUSE_SECRET_KEY")
        print(f"Langfuse tracing: {'on' if tracing else 'off'}")

    for index, task in enumerate(tasks, start=1):
        if scored(run_dir / task):
            print(f"[{index:2d}/{len(tasks)}] {task:32s} skip (already scored)")
            continue
        print(f"[{index:2d}/{len(tasks)}] {task:32s} running", flush=True)
        cmd = [
            "harbor", "run", "-d", DATASET, "-i", f"terminal-bench/{task}",
            "-n", "1", "-k", "1", "-o", str(run_dir), "--job-name", task, "--yes",
        ]
        cmd += ["-a", "oracle"] if args.agent == "oracle" else ["-a", AGENTS[args.agent], "-m", f"openrouter/{args.model}"]
        subprocess.run(cmd, cwd=ROOT, env=env, check=False)

    if before is not None:
        after = key_usage()
        if after is not None:
            print(f"OpenRouter key usage after: ${after:.4f} (this run: ${after - before:.4f})")
    print(f"results: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
