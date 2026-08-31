#!/usr/bin/env python3
"""Resume the frozen 21-task, two-model, three-harness evaluation matrix."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / ".cache/datasets/terminal-bench-2-1"
MODELS = (
    "openai/qwen2.5-coder:3b",
    "openai/qwen2.5-coder:7b",
)
HARNESSES = ("mini-swe-agent", "openhands", "custom")
EXPECTED_TASK_COUNT = 21
CUSTOM_VERSION = "2.2.0"


def selected_tasks():
    values = [
        line.strip()
        for line in (ROOT / "configs/progress_subset.txt").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if len(values) != EXPECTED_TASK_COUNT or len(set(values)) != len(values):
        raise RuntimeError("the frozen subset must contain 21 unique task IDs")
    return values


def trial_key(data):
    task_name = data.get("task_name")
    agent = data.get("agent_info") or {}
    model = (agent.get("model_info") or {}).get("name")
    harness = agent.get("name")
    if not task_name or not model:
        return None
    if harness == "uts-qwen-harness":
        if agent.get("version") != CUSTOM_VERSION:
            return None
        harness = "custom"
    if harness not in HARNESSES:
        return None
    return task_name.rsplit("/", 1)[-1], harness, "openai/" + model


def completed_trials(run_dir):
    completed = {}
    for path in (run_dir / "raw").rglob("result.json"):
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        key = trial_key(data)
        if key is None:
            continue
        stamp = data.get("finished_at") or data.get("started_at") or ""
        if key not in completed or stamp > completed[key][0]:
            completed[key] = (stamp, path)
    return completed


def run_one(task, harness, model):
    command = [
        sys.executable,
        str(ROOT / "scripts/run_baselines.py"),
        "--harness",
        harness,
        "--model",
        model,
        "--task",
        task,
    ]
    print("MATRIX START task=%s harness=%s model=%s" % (task, harness, model), flush=True)
    result = subprocess.run(command, cwd=ROOT, env=os.environ.copy(), check=False)
    print(
        "MATRIX END task=%s harness=%s model=%s exit=%d"
        % (task, harness, model, result.returncode),
        flush=True,
    )
    return result.returncode


def benchmark_images(task):
    result = subprocess.run(
        ["docker", "image", "ls", "--format", "{{.Repository}}:{{.Tag}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    prefix = "alexgshaw/%s:" % task
    return sorted({line for line in result.stdout.splitlines() if line.startswith(prefix)})


def cleanup_task_images(task):
    for image in benchmark_images(task):
        print("MATRIX CLEANUP image=%s" % image, flush=True)
        subprocess.run(["docker", "image", "rm", image], check=False)


def main():
    run_dir = Path(os.environ.get("RUN_DIR") or (ROOT / ".current_run").read_text().strip())
    failures = []
    for task in selected_tasks():
        completed = completed_trials(run_dir)
        for model in MODELS:
            for harness in HARNESSES:
                key = (task, harness, model)
                if key in completed:
                    print("MATRIX SKIP complete task=%s harness=%s model=%s" % key, flush=True)
                    continue
                code = run_one(task, harness, model)
                refreshed = completed_trials(run_dir)
                if key not in refreshed:
                    failures.append({"task": task, "harness": harness, "model": model, "exit": code})
                completed = refreshed
        cleanup_task_images(task)
    status_path = run_dir / "matrix_status.json"
    status_path.write_text(json.dumps({"missing_after_run": failures}, indent=2) + "\n")
    print("MATRIX COMPLETE missing=%d status=%s" % (len(failures), status_path), flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
