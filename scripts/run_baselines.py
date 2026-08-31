#!/usr/bin/env python3
"""Run one Harbor trial per frozen task for the requested integrated harness."""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / ".cache/datasets/terminal-bench-2-1"
MODEL = "openai/qwen2.5-coder:3b"
BASE_URL = "http://host.docker.internal:11434/v1"


def selected_tasks():
    values = []
    for line in (ROOT / "configs/progress_subset.txt").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            values.append(line)
    if len(values) != 3:
        raise RuntimeError("frozen subset must contain exactly three task IDs")
    return values


def command(harness, task, jobs_dir):
    cmd = [
        "harbor", "run", "-p", str(DATASET / task), "-a", harness,
        "-m", MODEL, "-n", "1", "-k", "1", "-o", str(jobs_dir),
        "--job-name", "%s-%s" % (harness, task), "--yes",
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
            "num_retries=2",
        ):
            cmd += ["--ak", value]
        cmd += [
            "--ae", "LLM_MAX_INPUT_TOKENS=32768",
            "--ae", "LLM_MAX_OUTPUT_TOKENS=4096",
        ]
    return cmd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--harness", choices=("oracle", "mini-swe-agent", "openhands", "custom"), required=True)
    parser.add_argument("--task", help="Run only one frozen task as a compatibility probe")
    args = parser.parse_args()
    if args.harness == "oracle":
        return subprocess.call([sys.executable, str(ROOT / "scripts/validate_oracle.py"), "--execute"], cwd=ROOT)
    tasks = selected_tasks()
    if args.task:
        if args.task not in tasks:
            raise SystemExit("probe task is not in frozen subset")
        tasks = [args.task]
    run_dir = Path(os.environ.get("RUN_DIR") or (ROOT / ".current_run").read_text().strip())
    jobs_dir = run_dir / ("raw/%s-jobs" % args.harness)
    jobs_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({
        "OPENAI_API_KEY": "ollama", "LLM_API_KEY": "ollama",
        "OPENAI_BASE_URL": BASE_URL, "OPENAI_API_BASE": BASE_URL, "LLM_BASE_URL": BASE_URL,
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
                "-a", "scripts.custom_harness:QwenCustomHarness", "-m", MODEL,
                "-n", "1", "-k", "1", "-o", str(jobs_dir),
                "--job-name", "uts-qwen-harness-%s" % task, "--yes",
                "--ak", "api_base=http://127.0.0.1:11434/v1", "--ak", "api_key=ollama",
                "--ak", "temperature=0", "--ak", "max_steps=25",
                "--ak", "max_output_tokens=800", "--ak", "command_timeout_sec=120",
            ]
            subprocess.run(custom_cmd, cwd=ROOT, env=env, check=False)
        else:
            subprocess.run(command(args.harness, task, jobs_dir), cwd=ROOT, env=env, check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
