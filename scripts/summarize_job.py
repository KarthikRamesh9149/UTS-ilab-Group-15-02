#!/usr/bin/env python3
"""Summarise a Harbor job directory into a readable table and a CSV row per trial.

Usage:
    python scripts/summarize_job.py jobs/oracle-21-check
    python scripts/summarize_job.py jobs/oracle-21-check --csv results/harshini/oracle-21-check.csv

Works on any Harbor 0.22 job directory, so the same reader serves the Oracle
runnability check, the baseline harnesses and the custom harness.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

FIELDS = [
    "task",
    "harness",
    "harness_version",
    "model",
    "reward",
    "passed",
    "duration_sec",
    "input_tokens",
    "output_tokens",
    "cost_usd",
    "exception",
    "trial_dir",
]


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def read_trial(result_path: Path) -> dict | None:
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    agent = data.get("agent_info") or {}
    model_info = agent.get("model_info") or {}
    agent_result = data.get("agent_result") or {}
    verifier = data.get("verifier_result") or {}
    rewards = verifier.get("rewards") or {}
    reward = rewards.get("reward")

    started = _parse_time(data.get("started_at"))
    finished = _parse_time(data.get("finished_at"))
    duration = round((finished - started).total_seconds(), 1) if started and finished else None

    exception_info = data.get("exception_info") or {}
    exception = exception_info.get("exception_type") if isinstance(exception_info, dict) else None

    task = (data.get("task_name") or "").rsplit("/", 1)[-1]

    return {
        "task": task,
        "harness": agent.get("name"),
        "harness_version": agent.get("version"),
        "model": model_info.get("name"),
        "reward": reward,
        # A trial only counts as passed on an exact 1.0 - Terminal-Bench has no partial credit.
        "passed": reward == 1.0,
        "duration_sec": duration,
        "input_tokens": agent_result.get("n_input_tokens"),
        "output_tokens": agent_result.get("n_output_tokens"),
        "cost_usd": agent_result.get("cost_usd"),
        "exception": exception,
        "trial_dir": result_path.parent.name,
    }


def collect(job_dirs: list[Path]) -> tuple[list[dict], list[str]]:
    """Read one or more job directories, later ones overriding earlier per task.

    The override is what records an infrastructure correction (proposal 4.1.7): a
    task re-run with a raised timeout supersedes its earlier timed-out trial,
    without editing the original job directory that documents the failure.
    """
    by_task: dict[str, dict] = {}
    pending = []
    for job_dir in job_dirs:
        for trial_dir in sorted(p for p in job_dir.iterdir() if p.is_dir()):
            result_path = trial_dir / "result.json"
            if not result_path.exists():
                pending.append(trial_dir.name)
                continue
            row = read_trial(result_path)
            if row is None:
                pending.append(trial_dir.name)
            else:
                by_task[row["task"]] = row
    return list(by_task.values()), pending


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "job_dir",
        type=Path,
        nargs="+",
        help="one or more job dirs; later ones supersede earlier per task",
    )
    parser.add_argument("--csv", type=Path, help="also write a CSV here")
    args = parser.parse_args()

    for job_dir in args.job_dir:
        if not job_dir.is_dir():
            raise SystemExit("not a directory: %s" % job_dir)

    rows, pending = collect(args.job_dir)
    rows.sort(key=lambda r: r["task"])

    width = max([len(r["task"]) for r in rows] + [len(p) for p in pending] + [12])
    print("%-*s  %6s  %9s  %s" % (width, "TASK", "REWARD", "TIME(s)", "NOTE"))
    print("-" * (width + 32))
    for row in rows:
        note = row["exception"] or ""
        reward = "-" if row["reward"] is None else "%.1f" % row["reward"]
        duration = "-" if row["duration_sec"] is None else "%.0f" % row["duration_sec"]
        print("%-*s  %6s  %9s  %s" % (width, row["task"], reward, duration, note))
    for name in pending:
        print("%-*s  %6s  %9s  %s" % (width, name, "", "", "still running"))

    passed = sum(1 for r in rows if r["passed"])
    scored = len(rows)
    print("-" * (width + 32))
    print("passed %d / %d scored  (%d of 21 trials present)" % (passed, scored, scored))
    if pending:
        print("%d trial(s) not finished yet" % len(pending))

    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        print("wrote %s" % args.csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
