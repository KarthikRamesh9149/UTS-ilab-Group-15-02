#!/usr/bin/env python3
"""Cross-model check: this harness and pinned Terminus-2 on dev-20 with a second model.

    python experiments/harshini-deepagents/model_study.py --model anthropic/claude-haiku-5.5 --tag haiku

The two harnesses are interleaved task by task (which one goes first alternates), so both
see the same provider conditions. One run per harness; results go to
results/harshini/deepagents/dev20-<tag>-v<version>.csv and dev20-<tag>-terminus2.csv.
Re-running resumes: tasks that already have a scored result are skipped.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run_probe import dev20  # noqa: E402

HARNESS_VERSION = "0.1.3"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    runs = {"custom": f"dev20-{args.tag}-v{HARNESS_VERSION}", "terminus": f"dev20-{args.tag}-terminus2"}

    for index, task in enumerate(dev20()):
        order = ("custom", "terminus") if index % 2 == 0 else ("terminus", "custom")
        for agent in order:
            print(f"=== {agent} {task}", flush=True)
            subprocess.run([sys.executable, str(HERE / "run_probe.py"), agent, task,
                            "--model", args.model, "--run-name", runs[agent]], check=False)

    for run_name in runs.values():
        subprocess.run([sys.executable, str(HERE / "summarize_run.py"), run_name, "--dev20", "--attempt", "first"],
                       check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
