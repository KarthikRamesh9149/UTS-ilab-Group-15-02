#!/usr/bin/env python3
"""Repeat study: three dev-20 runs each of this harness and pinned Terminus-2 on one host.

    python experiments/harshini-deepagents/repeat_study.py

Runs alternate between the two agents so both see similar provider load over the
study. Each run is resumable (scored tasks are skipped) and is summarised into
results/harshini/deepagents/<run-name>.csv when it ends. The harness version is
frozen for the whole study.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
HARNESS_RUN = "dev20-v0.1.3"
RUNS = [
    ("custom", HARNESS_RUN),
    ("terminus", "dev20-terminus2-r1"),
    ("custom", f"{HARNESS_RUN}-r2"),
    ("terminus", "dev20-terminus2-r2"),
    ("custom", f"{HARNESS_RUN}-r3"),
    ("terminus", "dev20-terminus2-r3"),
]


def main() -> int:
    # The second pass only re-runs tasks left without a verifier result (e.g. trials set aside after host sleep).
    for agent, run_name in RUNS + RUNS:
        print(f"=== {agent} {run_name}", flush=True)
        subprocess.run([sys.executable, str(HERE / "run_probe.py"), agent, "--dev20", "--run-name", run_name],
                       cwd=ROOT, check=False)
        subprocess.run([sys.executable, str(HERE / "summarize_run.py"), run_name, "--dev20"], cwd=ROOT, check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
