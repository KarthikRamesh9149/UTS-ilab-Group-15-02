#!/usr/bin/env python3
"""Discover Harbor trial results and create the frozen 126-row comparison CSV."""
import csv
import json
import os
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = [
    "run_id", "timestamp", "task_id", "benchmark", "benchmark_version", "harness",
    "harness_version", "model_name", "model_digest", "model_runtime",
    "model_base_url_redacted", "context_length", "temperature", "pass", "reward",
    "valid_trial", "duration_seconds", "prompt_tokens", "completion_tokens", "total_tokens",
    "model_calls", "agent_steps", "timeout", "infrastructure_error", "error_type",
    "error_message", "trajectory_path", "harbor_job_path", "git_commit", "notes",
]
INFRA_MARKERS = (
    "docker compose", "docker daemon", "connection refused", "failed to connect",
    "image pull", "no such host", "environment setup", "container startup",
    "network connection", "could not resolve", "unknown flag: --project-name",
)
MODELS = (
    ("qwen2.5-coder:3b", "f72c60cabf62"),
    ("qwen2.5-coder:7b", "dae161e27b0e"),
)
HARNESSES = ("mini-swe-agent", "openhands", "uts-qwen-harness")
CUSTOM_VERSION = "2.2.0"


def load_json(path):
    return json.loads(Path(path).read_text())


def reward_value(data):
    rewards = (data.get("verifier_result") or {}).get("rewards") or {}
    value = rewards.get("reward")
    if value is None:
        numeric = [v for v in rewards.values() if isinstance(v, (int, float))]
        value = numeric[0] if numeric else None
    return value


def seconds_between(start, finish):
    if not start or not finish:
        return None
    def parse(value):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    try:
        return round((parse(finish) - parse(start)).total_seconds(), 3)
    except ValueError:
        return None


def is_infrastructure_error(data):
    exc = data.get("exception_info") or {}
    message = (exc.get("exception_message") or "").lower()
    if not exc:
        return False
    if "timeout" in (exc.get("exception_type") or "").lower() and data.get("agent_execution"):
        return False
    return any(marker in message for marker in INFRA_MARKERS) or (
        data.get("agent_execution") is None and data.get("verifier_result") is None
    )


def rel(path):
    if not path:
        return ""
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return "[external path redacted]"


def trajectory_metrics(path):
    if not path.exists():
        return None, None
    try:
        data = load_json(path)
    except (OSError, json.JSONDecodeError):
        return None, None
    steps = data.get("steps") or []
    calls = sum((s.get("llm_call_count") or 0) for s in steps if isinstance(s, dict))
    return calls or None, len(steps) or None


def parse_trial(path, model_digest="", git_commit=""):
    path = Path(path)
    data = load_json(path)
    harness = data.get("agent_info", {}).get("name", "")
    model_info = data.get("agent_info", {}).get("model_info") or {}
    exc = data.get("exception_info") or {}
    infra = is_infrastructure_error(data)
    reward = reward_value(data)
    trial_dir = path.parent
    trajectory = trial_dir / "agent/trajectory.json"
    model_calls, agent_steps = trajectory_metrics(trajectory)
    agent_result = data.get("agent_result") or {}
    prompt = agent_result.get("n_input_tokens")
    completion = agent_result.get("n_output_tokens")
    total = prompt + completion if prompt is not None and completion is not None else None
    exception_text = ((exc.get("exception_type") or "") + " " + (exc.get("exception_message") or "")).lower()
    timeout = "timeout" in exception_text or "timed out" in exception_text
    task = data.get("task_name", "").rsplit("/", 1)[-1]
    valid = bool(data.get("verifier_result")) and not infra
    return {
        "run_id": data.get("id", ""), "timestamp": data.get("started_at", ""),
        "task_id": task, "benchmark": "Terminal-Bench", "benchmark_version": "2.1",
        "harness": harness, "harness_version": data.get("agent_info", {}).get("version", ""),
        "model_name": model_info.get("name") or "",
        "model_digest": model_digest, "model_runtime": "Ollama 0.33.2",
        "model_base_url_redacted": "http://host.docker.internal:11434/v1",
        "context_length": 32768, "temperature": 0,
        "pass": (float(reward) > 0) if reward is not None and valid else "",
        "reward": reward if reward is not None else "", "valid_trial": valid,
        "duration_seconds": seconds_between(data.get("started_at"), data.get("finished_at")),
        "prompt_tokens": prompt if prompt is not None else "",
        "completion_tokens": completion if completion is not None else "",
        "total_tokens": total if total is not None else "", "model_calls": model_calls or "",
        "agent_steps": agent_steps or "", "timeout": timeout,
        "infrastructure_error": infra, "error_type": exc.get("exception_type", ""),
        "error_message": (exc.get("exception_message") or "")[:500].replace(str(ROOT), "[project]"),
        "trajectory_path": rel(trajectory) if trajectory.exists() else "",
        "harbor_job_path": rel(trial_dir.parent), "git_commit": git_commit,
        "notes": "Verifier result preserved" if valid else "Trial did not produce a valid verifier result",
    }


def discover_latest(run_dir):
    latest = {}
    for path in (run_dir / "raw").rglob("result.json"):
        if "infrastructure-failures" in path.parts:
            continue
        try:
            data = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        harness = data.get("agent_info", {}).get("name")
        if harness not in HARNESSES or "task_name" not in data:
            continue
        if harness == "uts-qwen-harness" and (data.get("agent_info") or {}).get("version") != CUSTOM_VERSION:
            continue
        model = ((data.get("agent_info") or {}).get("model_info") or {}).get("name")
        if model not in {name for name, _ in MODELS}:
            continue
        task = data["task_name"].rsplit("/", 1)[-1]
        stamp = data.get("finished_at") or data.get("started_at") or ""
        key = (model, harness, task)
        if key not in latest or stamp > latest[key][0]:
            latest[key] = (stamp, path)
    return {key: value[1] for key, value in latest.items()}


def collect(run_dir):
    subset = [x.strip() for x in (ROOT / "configs/progress_subset.txt").read_text().splitlines() if x.strip() and not x.startswith("#")]
    latest = discover_latest(run_dir)
    try:
        commit = os.popen("git -C %s rev-parse HEAD" % ROOT).read().strip()
    except OSError:
        commit = ""
    rows = []
    for model, digest in MODELS:
        for harness in HARNESSES:
            for task in subset:
                path = latest.get((model, harness, task))
                if path:
                    rows.append(parse_trial(path, model_digest=digest, git_commit=commit))
                else:
                    row = {key: "" for key in COLUMNS}
                    row.update({
                        "task_id": task, "benchmark": "Terminal-Bench", "benchmark_version": "2.1",
                        "harness": harness, "model_name": model, "model_digest": digest,
                        "model_runtime": "Ollama 0.33.2", "model_base_url_redacted": "[local OpenAI-compatible endpoint]",
                        "context_length": 32768, "temperature": 0, "valid_trial": False,
                        "timeout": False, "infrastructure_error": True, "error_type": "MissingTrial",
                        "error_message": "No Harbor trial result was discovered", "git_commit": commit,
                        "notes": "Intended trial row retained",
                    })
                    rows.append(row)
    return rows


def main():
    run_dir = Path(os.environ.get("RUN_DIR") or (ROOT / ".current_run").read_text().strip())
    rows = collect(run_dir)
    with (run_dir / "results.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader(); writer.writerows(rows)
    print("Wrote %d intended trial rows to %s" % (len(rows), run_dir / "results.csv"))


if __name__ == "__main__":
    main()
