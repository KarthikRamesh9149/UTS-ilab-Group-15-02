#!/usr/bin/env python3
"""Run one Harbor trial per frozen task for the requested integrated harness."""
import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / ".cache/datasets/terminal-bench-2-1"
DEFAULT_MODEL = "openai/qwen2.5-coder:3b"
EXPECTED_TASK_COUNT = 21
SUPPORTED_MODELS = {
    "openai/qwen2.5-coder:3b": "3b",
    "openai/qwen2.5-coder:7b": "7b",
}
BASE_URL = "http://host.docker.internal:11434/v1"
OLLAMA_API = "http://127.0.0.1:11434/api/generate"


def selected_tasks():
    values = []
    for line in (ROOT / "configs/progress_subset.txt").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            values.append(line)
    if len(values) != EXPECTED_TASK_COUNT:
        raise RuntimeError(
            "frozen subset must contain exactly %d task IDs, found %d"
            % (EXPECTED_TASK_COUNT, len(values))
        )
    return values


def command(harness, task, jobs_dir, model, model_tag):
    cmd = [
        "harbor", "run", "-p", str(DATASET / task), "-a", harness,
        "-m", model, "-n", "1", "-k", "1", "-o", str(jobs_dir),
        "--job-name", "%s-%s-%s" % (harness, model_tag, task), "--yes",
        "--allow-agent-host", "host.docker.internal",
    ]
    if harness == "mini-swe-agent":
        cmd += [
            "--ak", "config_file=%s" % (ROOT / "configs/mini_swe_agent_config.yaml"),
            "--ak", "max_tokens=4096",
        ]
    elif harness == "openhands":
        for value in (
            "disable_tool_calls=true", "reasoning_effort=none", "temperature=0",
            "max_iterations=25", "drop_params=true", "disable_vision=true",
            "num_retries=2", "version=0.61.0", "python_version=3.12",
        ):
            cmd += ["--ak", value]
        cmd += [
            "--ae", "LLM_MAX_INPUT_TOKENS=32768",
            "--ae", "LLM_MAX_OUTPUT_TOKENS=4096",
        ]
    return cmd


def unload_inactive_models(selected_model):
    """Keep only the selected Qwen size resident on a 16 GB local machine."""
    selected_name = selected_model.removeprefix("openai/")
    for candidate in SUPPORTED_MODELS:
        candidate_name = candidate.removeprefix("openai/")
        if candidate_name == selected_name:
            continue
        payload = json.dumps({"model": candidate_name, "keep_alive": 0}).encode()
        request = urllib.request.Request(
            OLLAMA_API,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                response.read()
            print("Unloaded inactive local model %s" % candidate_name, flush=True)
        except Exception as exc:
            print("Warning: could not unload inactive model %s: %s" % (candidate_name, exc), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--harness", choices=("oracle", "mini-swe-agent", "openhands", "custom"), required=True)
    parser.add_argument("--task", help="Run only one frozen task as a compatibility probe")
    parser.add_argument("--model", choices=tuple(SUPPORTED_MODELS), default=DEFAULT_MODEL)
    args = parser.parse_args()
    if args.harness == "oracle":
        return subprocess.call([sys.executable, str(ROOT / "scripts/validate_oracle.py"), "--execute"], cwd=ROOT)
    unload_inactive_models(args.model)
    tasks = selected_tasks()
    if args.task:
        if args.task not in tasks:
            raise SystemExit("probe task is not in frozen subset")
        tasks = [args.task]
    run_dir = Path(os.environ.get("RUN_DIR") or (ROOT / ".current_run").read_text().strip())
    model_tag = SUPPORTED_MODELS[args.model]
    jobs_dir = run_dir / ("raw/%s-%s-jobs" % (args.harness, model_tag))
    jobs_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({
        "OPENAI_API_KEY": "ollama", "LLM_API_KEY": "ollama",
        "OPENAI_BASE_URL": BASE_URL, "OPENAI_API_BASE": BASE_URL, "LLM_BASE_URL": BASE_URL,
        "PYTHONPATH": str(ROOT) + os.pathsep + env.get("PYTHONPATH", ""),
    })
    # Harbor's Mini-SWE adapter checks MSWEA_API_KEY first, but LiteLLM's
    # OpenAI-compatible path needs the canonical OPENAI_API_KEY. Do not set the
    # former so Harbor resolves and passes through the latter.
    env.pop("MSWEA_API_KEY", None)
    for task in tasks:
        print("Running %s on %s" % (args.harness, task), flush=True)
        if args.harness == "custom":
            custom_cmd = [
                "harbor", "run", "-p", str(DATASET / task),
                "-a", "scripts.custom_harness:QwenCustomHarness", "-m", args.model,
                "-n", "1", "-k", "1", "-o", str(jobs_dir),
                "--job-name", "uts-qwen-harness-v22-%s-%s" % (model_tag, task), "--yes",
                "--ak", "api_base=http://127.0.0.1:11434/v1", "--ak", "api_key=ollama",
                "--ak", "temperature=0", "--ak", "max_steps=25",
                "--ak", "max_output_tokens=1200", "--ak", "command_timeout_sec=120",
            ]
            subprocess.run(custom_cmd, cwd=ROOT, env=env, check=False)
        else:
            subprocess.run(command(args.harness, task, jobs_dir, args.model, model_tag), cwd=ROOT, env=env, check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
