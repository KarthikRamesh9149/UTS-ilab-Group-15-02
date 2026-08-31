#!/usr/bin/env python3
"""Select seed-42 candidates and retain the first three successful Oracles.

This script only lists task directories and reads Harbor result JSON. It never
opens solution or verifier implementation files.
"""
import argparse
import json
import os
import random
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / ".cache/datasets/terminal-bench-2-1"


def candidate_order(dataset=DATASET, seed=42):
    names = sorted(p.name for p in dataset.iterdir() if p.is_dir())
    if len(names) != 89:
        raise RuntimeError("expected 89 Terminal-Bench 2.1 tasks, found %d" % len(names))
    return random.Random(seed).sample(names, len(names))


def trial_results(jobs_dir):
    found = []
    for path in Path(jobs_dir).rglob("result.json"):
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if "task_name" not in data or data.get("agent_info", {}).get("name") != "oracle":
            continue
        data["_path"] = str(path)
        found.append(data)
    return found


def task_id(result):
    raw = result.get("task_name", "")
    return raw.rsplit("/", 1)[-1]


def reward_value(result):
    rewards = (result.get("verifier_result") or {}).get("rewards") or {}
    value = rewards.get("reward")
    if value is None:
        numeric = [v for v in rewards.values() if isinstance(v, (int, float))]
        value = numeric[0] if numeric else None
    return value


def successful(result):
    value = reward_value(result)
    return result.get("exception_info") is None and value is not None and float(value) > 0


def latest_by_task(results):
    latest = {}
    for item in results:
        key = task_id(item)
        stamp = item.get("finished_at") or item.get("started_at") or ""
        if key not in latest or stamp > (latest[key].get("finished_at") or latest[key].get("started_at") or ""):
            latest[key] = item
    return latest


def execute_candidate(name, jobs_dir):
    cmd = [
        "harbor", "run", "-p", str(DATASET / name), "-a", "oracle",
        "-n", "1", "-k", "1", "-o", str(jobs_dir),
        "--job-name", "oracle-%s" % name, "--yes",
    ]
    print("Executing Oracle candidate:", name, flush=True)
    return subprocess.run(cmd, cwd=ROOT, check=False).returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--max-candidates", type=int, default=15)
    args = parser.parse_args()
    run_dir = Path(os.environ.get("RUN_DIR") or (ROOT / ".current_run").read_text().strip())
    jobs_dir = run_dir / "raw/oracle-jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    order = candidate_order()

    if args.execute:
        for name in order[: args.max_candidates]:
            latest = latest_by_task(trial_results(jobs_dir))
            if name not in latest:
                execute_candidate(name, jobs_dir)
            latest = latest_by_task(trial_results(jobs_dir))
            successes = [n for n in order if n in latest and successful(latest[n])]
            if len(successes) >= 3:
                break

    latest = latest_by_task(trial_results(jobs_dir))
    selected = [name for name in order if name in latest and successful(latest[name])][:3]
    attempts = []
    for rank, name in enumerate(order, 1):
        if name not in latest:
            continue
        result = latest[name]
        attempts.append({
            "candidate_rank": rank,
            "task_id": name,
            "oracle_success": successful(result),
            "reward": reward_value(result),
            "exception_type": (result.get("exception_info") or {}).get("exception_type"),
            "result_path": str(Path(result["_path"]).relative_to(ROOT)),
        })

    manifest = {
        "label": "Preliminary three-task engineering smoke subset",
        "benchmark": "Terminal-Bench 2.1",
        "dataset": "terminal-bench/terminal-bench-2-1@latest",
        "dataset_task_count": 89,
        "selection_seed": 42,
        "selection_algorithm": "sort IDs; random.Random(42).sample all IDs; retain first three successful Oracle candidates",
        "selection_safety": "Task names and resource metadata only; solution and verifier implementation contents were not inspected.",
        "candidate_order": order,
        "oracle_attempts": attempts,
        "selected_task_ids": selected,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "k": 1,
        "n_concurrent": 1,
        "official_leaderboard_claim": False,
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if len(selected) == 3:
        (ROOT / "configs/progress_subset.txt").write_text("\n".join(selected) + "\n")
        print("Selected:", ", ".join(selected))
    else:
        print("Oracle selection incomplete: %d/3 successful candidates" % len(selected))
        if args.execute:
            raise SystemExit(1)


if __name__ == "__main__":
    main()

