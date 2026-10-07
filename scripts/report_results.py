"""Validate and summarise the committed study records without model calls."""
import argparse
import csv
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_rows(path):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or any(not row.get("task_id") or not row.get("trial_id") for row in rows):
        raise ValueError("Nonempty task and trial identities are required")
    if len({row["trial_id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate trial identity")
    return rows


def reward(row):
    value = row.get("reward", "")
    if value == "":
        return None
    try:
        number = Decimal(value)
        if not number.is_finite() or number not in (0, 1):
            raise ValueError("Only binary official verifier rewards are supported")
        return int(number)
    except InvalidOperation as error:
        raise ValueError("Invalid verifier reward") from error


def summarise(name, rows, development_ids, *, attempts=None):
    if len({row["task_id"] for row in rows}) != len(rows):
        raise ValueError("Each reporting view must contain one outcome per task")
    outcomes = [reward(row) for row in rows]
    passed = outcomes.count(1)
    return {
        "harness": name,
        "tasks": len(rows),
        "attempts": len(rows) if attempts is None else attempts,
        "passed": passed,
        "verified_failures": outcomes.count(0),
        "missing_outcomes": outcomes.count(None),
        "pass_rate_percent": round(100 * passed / len(rows), 2),
        "development_passed": sum(reward(row) == 1 for row in rows if row["task_id"] in development_ids),
        "remaining_passed": sum(reward(row) == 1 for row in rows if row["task_id"] not in development_ids),
    }


def join_recovery(original, recovery):
    """Replace only setup-missing outcomes in a derived view; preserve inputs."""
    tasks = {row["task_id"]: row for row in original}
    if len(tasks) != len(original):
        raise ValueError("Duplicate original task identity")
    seen = set()
    for row in recovery:
        task = row["task_id"]
        if task in seen or task not in tasks:
            raise ValueError("Duplicate or unknown recovery task")
        seen.add(task)
        prior = tasks[task]
        if (reward(prior) is not None or prior.get("status") != "setup_failed"
                or prior.get("verifier_observation") != "not_run_setup_failed"):
            raise ValueError("Recovery can only resolve an original setup-missing outcome")
        if (row.get("original_trial_id") != prior["trial_id"]
                or row.get("original_result_sha256") != prior.get("result_sha256")):
            raise ValueError("Recovery evidence does not match the original attempt")
        if reward(row) is None or row.get("status") != "verified":
            raise ValueError("Recovery requires an official verifier outcome")
        tasks[task] = dict(row)
    return [tasks[row["task_id"]] for row in original]


def build_summary(root=ROOT):
    root = Path(root)
    manifest = json.loads((root / "configs/tasks.json").read_text())
    expected = set(manifest["task_ids"])
    development = set(manifest["development_ids"])
    if len(expected) != 89 or len(development) != 20 or not development <= expected:
        raise ValueError("The study requires 89 tasks and its fixed 20-task development set")
    baseline = read_rows(root / "results/baselines/trials.csv")
    originals = read_rows(root / "results/custom/trials.csv")
    recovery = read_rows(root / "results/custom/recovery/trials.csv")
    if set(row["harness"] for row in baseline) != {"terminus-2", "openhands"}:
        raise ValueError("Unexpected baseline harness")
    if any(row["harness"] != "C0-NC" for row in originals + recovery):
        raise ValueError("Unexpected custom harness")
    views = []
    for harness in ("terminus-2", "openhands"):
        rows = [row for row in baseline if row["harness"] == harness]
        if set(row["task_id"] for row in rows) != expected:
            raise ValueError("Baseline task set differs from the frozen study")
        views.append(summarise(harness, rows, development))
    if set(row["task_id"] for row in originals) != expected:
        raise ValueError("Custom task set differs from the frozen study")
    combined = join_recovery(originals, recovery)
    return {
        "benchmark": "Terminal-Bench 2.1",
        "reporting": "Derived from original records; recovery is not a single 89-attempt run",
        "baselines": views,
        "custom_original": summarise("C0-NC", originals, development),
        "custom_recovery": summarise("C0-NC recovery", recovery, development),
        "custom_recovery_inclusive": summarise("C0-NC", combined, development,
                                               attempts=len(originals) + len(recovery)),
    }


def markdown(summary):
    rows = [summary["baselines"][0], summary["custom_recovery_inclusive"], summary["baselines"][1]]
    output = ["| Harness | Tasks | Attempts | Passed | Verified failures | Missing | Pass rate |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in rows:
        output.append(f'| {row["harness"]} | {row["tasks"]} | {row["attempts"]} | {row["passed"]} | '
                      f'{row["verified_failures"]} | {row["missing_outcomes"]} | {row["pass_rate_percent"]:.2f}% |')
    output.extend(["", "Custom: 89 original attempts plus three separate setup-recovery attempts.",
                   "Original custom outcomes: 50 passed, 36 verified failures, three missing."])
    return "\n".join(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print the derived summary as JSON")
    args = parser.parse_args()
    result = build_summary()
    print(json.dumps(result, indent=2) if args.json else markdown(result))
