#!/usr/bin/env python3
"""Write one CSV row per task for a run under jobs/harshini-deepagents/<run-name>/.

    python experiments/harshini-deepagents/summarize_run.py dev20-v0.1.2 --dev20

Output: results/harshini/deepagents/<run-name>.csv. With --dev20, tasks that never
ran are kept as "not run" rows so the denominator stays 20.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIELDS = ["task", "status", "reward", "stop_reason", "agent_min", "budget_min",
          "cost_usd", "model_calls", "harness", "harness_version"]


def minutes(span: dict | None) -> str:
    if not span or not span.get("started_at") or not span.get("finished_at"):
        return ""
    start, end = (datetime.fromisoformat(span[k].replace("Z", "+00:00")) for k in ("started_at", "finished_at"))
    return f"{(end - start).total_seconds() / 60:.1f}"


def row_for(task: str, task_dir: Path, attempt: str = "latest") -> dict:
    results = sorted(task_dir.glob("*/result.json"), key=lambda p: p.stat().st_mtime)
    if not results:
        return {"task": task, "status": "not run"}
    data = json.loads(results[0 if attempt == "first" else -1].read_text(encoding="utf-8"))
    agent = data.get("agent_result") or {}
    meta = agent.get("metadata") or {}
    rewards = (data.get("verifier_result") or {}).get("rewards")
    if rewards is not None:
        reward = rewards.get("reward")
        status = "pass" if reward == 1.0 else "fail"
    else:
        reward = ""
        status = "error" if data.get("exception_info") else "unscored"
    budget = meta.get("agent_budget_sec")
    cost = agent.get("cost_usd")
    return {
        "task": task,
        "status": status,
        "reward": reward,
        "stop_reason": meta.get("stop_reason", ""),
        "agent_min": minutes(data.get("agent_execution")),
        "budget_min": f"{budget / 60:.0f}" if budget else "",
        "cost_usd": f"{cost:.4f}" if cost is not None else "",
        "model_calls": meta.get("model_calls", ""),
        "harness": meta.get("harness", ""),
        "harness_version": meta.get("harness_version", ""),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_name")
    parser.add_argument("--dev20", action="store_true", help="include unrun dev-20 tasks")
    parser.add_argument("--attempt", choices=("latest", "first"), default="latest",
                        help="which completed trial to report when a task was run more than once")
    parser.add_argument("--suffix", default="", help="appended to the output CSV name")
    args = parser.parse_args()

    run_dir = ROOT / "jobs" / "harshini-deepagents" / args.run_name
    tasks = sorted(p.name for p in run_dir.iterdir() if p.is_dir()) if run_dir.exists() else []
    if args.dev20:
        listed = [t.strip() for t in (HERE / "dev20_tasks.txt").read_text(encoding="utf-8").splitlines()
                  if t.strip() and not t.startswith("#")]
        tasks = listed + [t for t in tasks if t not in listed]
    rows = [row_for(task, run_dir / task, args.attempt) for task in tasks]

    out = ROOT / "results" / "harshini" / "deepagents" / f"{args.run_name}{args.suffix}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    passed = sum(r["status"] == "pass" for r in rows)
    scored = sum(r["status"] in ("pass", "fail") for r in rows)
    cost = sum(float(r["cost_usd"]) for r in rows if r.get("cost_usd"))
    print(f"{args.run_name}: {passed} passed / {scored} scored / {len(rows)} tasks, ${cost:.4f} -> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
