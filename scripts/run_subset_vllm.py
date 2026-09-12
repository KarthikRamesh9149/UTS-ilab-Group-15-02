#!/usr/bin/env python3
"""Run the frozen 21-task subset against a self-hosted vLLM endpoint.

The point of the brief is a same-model comparison: our custom harness against an
established one, with only the harness changing. So this script takes the harness
as an argument and holds everything else - model, endpoint, subset, k, temperature
- identical between runs.

Topology: vLLM serves the model on a CETUS GPU node (see hpc/serve_vllm.pbs) and
an SSH tunnel forwards it to this laptop:

    ssh -N -L 8000:<gpu-node>:8000 cetus

Harbor and Docker run here, because the cluster has no Docker and Harbor requires
it. Two consequences for how the endpoint is addressed:

  custom          BaseAgent, so the LLM calls happen in THIS process -> 127.0.0.1
  mini-swe-agent  installed inside the task container -> host.docker.internal,
                  which also needs --allow-agent-host

Usage:
    python scripts/run_subset_vllm.py --harness custom
    python scripts/run_subset_vllm.py --harness mini-swe-agent
    python scripts/run_subset_vllm.py --harness custom --task fix-git   # probe one
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from summarize_job import FIELDS, read_trial  # noqa: E402

# The subset is frozen at 21 tasks by the proposal (section 4.1.6). Re-selecting
# after seeing results would invalidate the comparison, so this is asserted, not
# treated as a default.
EXPECTED_TASK_COUNT = 21
SUBSET_FILE = ROOT / "configs/progress_subset.txt"
DATASET = "terminal-bench/terminal-bench-2-1"

# Lives under a hyphenated directory, so it is importable only via PYTHONPATH.
HARNESS_ROOT = ROOT / "experiments/itsha-bash-react"
CUSTOM_AGENT = "harness.v0_bash_agent:BashReActAgent"

DEFAULT_MODEL = "qwen2.5-coder-32b-awq"


def frozen_tasks() -> list[str]:
    values = [
        line.strip()
        for line in SUBSET_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if len(values) != EXPECTED_TASK_COUNT or len(set(values)) != len(values):
        raise SystemExit(
            "the frozen subset must contain %d unique task IDs, found %d (%d unique)"
            % (EXPECTED_TASK_COUNT, len(values), len(set(values)))
        )
    return values


def preflight(base_url: str, api_key: str, model: str) -> None:
    """Fail before burning 21 task containers on an endpoint that is not there."""
    request = urllib.request.Request(
        base_url.rstrip("/") + "/models",
        headers={"Authorization": "Bearer %s" % api_key},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise SystemExit(
            "endpoint returned HTTP %s. If 401, the API key is wrong - check the\n"
            "API_KEY line in ~/vllm-endpoint.txt on CETUS." % exc.code
        )
    except Exception as exc:
        raise SystemExit(
            "cannot reach %s (%s).\n"
            "Is the SSH tunnel up, and is the serve job still running?\n"
            "  ssh cetus 'cat ~/vllm-endpoint.txt'\n"
            "  ssh -N -L 8000:<node>:8000 cetus" % (base_url, exc)
        )

    served = [entry.get("id") for entry in payload.get("data", [])]
    if model not in served:
        raise SystemExit(
            "endpoint is up but serves %s, not %r. Pass --model to match."
            % (served, model)
        )
    print("preflight OK: %s serving %s" % (base_url, model))


def already_done(task_dir: Path) -> bool:
    """A finished trial means we can skip it, so an interrupted run can resume."""
    return any(task_dir.glob("*/result.json"))


def build_command(
    harness: str, task: str, run_dir: Path, model: str, args: argparse.Namespace
) -> list[str]:
    # Harbor writes to <-o>/<--job-name>/<trial>/, so -o is the run directory and
    # the job name is the task: jobs/<run>/<task>/<trial>/result.json.
    # litellm-backed harnesses need a provider prefix to route to an
    # OpenAI-compatible endpoint; the custom agent strips a known prefix so the
    # wire name stays correct either way.
    cmd = [
        "harbor", "run",
        "-d", DATASET,
        "-i", "terminal-bench/" + task,
        "-m", "openai/" + model,
        "-n", "1",
        "-k", "1",
        "-o", str(run_dir),
        "--job-name", task,
        "--yes",
    ]
    if args.timeout_multiplier != 1.0:
        cmd += ["--timeout-multiplier", str(args.timeout_multiplier)]

    if harness == "custom":
        cmd += [
            "-a", CUSTOM_AGENT,
            # Passed explicitly rather than relying on env inheritance, so the
            # trace records exactly which endpoint answered.
            "--ak", "api_base=http://127.0.0.1:%d/v1" % args.port,
            "--ak", "api_key=%s" % args.api_key,
            "--ak", "wire_model=%s" % model,
            "--ak", "temperature=0",
            "--ak", "max_steps=%d" % args.max_steps,
            "--ak", "command_timeout_sec=120",
        ]
    else:
        cmd += [
            "-a", "mini-swe-agent",
            "--allow-agent-host", "host.docker.internal",
            "--ak", "config_file=%s" % (ROOT / "configs/mini_swe_agent_config.yaml"),
            "--ak", "max_tokens=4096",
        ]
    return cmd


def aggregate(run_dir: Path, csv_path: Path) -> None:
    rows = []
    for result in sorted(run_dir.glob("*/*/result.json")):
        row = read_trial(result)
        if row:
            rows.append(row)
    rows.sort(key=lambda r: r["task"] or "")

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    passed = sum(1 for r in rows if r["passed"])
    tokens_in = sum(r["input_tokens"] or 0 for r in rows)
    tokens_out = sum(r["output_tokens"] or 0 for r in rows)
    print()
    print("=" * 60)
    print("scored %d / %d trials, passed %d" % (len(rows), EXPECTED_TASK_COUNT, passed))
    print("tokens: %d in, %d out" % (tokens_in, tokens_out))
    print("wrote %s" % csv_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--harness", choices=("custom", "mini-swe-agent"), required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL, help="name vLLM serves")
    parser.add_argument("--port", type=int, default=8000, help="local tunnel port")
    parser.add_argument("--api-key", default=os.environ.get("VLLM_API_KEY", ""))
    parser.add_argument("--task", help="run a single frozen task as a probe")
    parser.add_argument("--max-steps", type=int, default=20)
    parser.add_argument(
        "--timeout-multiplier",
        type=float,
        default=1.0,
        help="raises task, agent, verifier and environment-start timeouts together",
    )
    parser.add_argument("--run-name", help="defaults to <harness>-21-<timestamp>")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.api_key:
        raise SystemExit(
            "no API key. Pass --api-key or set VLLM_API_KEY.\n"
            "Find it with: ssh cetus 'cat ~/vllm-endpoint.txt'"
        )

    tasks = frozen_tasks()
    if args.task:
        if args.task not in tasks:
            raise SystemExit(
                "%r is not in the frozen subset - running anything else would not be "
                "comparable" % args.task
            )
        tasks = [args.task]

    run_name = args.run_name or "%s-21-%s" % (
        args.harness,
        datetime.now().strftime("%Y%m%d_%H%M%S"),
    )
    run_dir = ROOT / "jobs" / run_name

    base_url = "http://127.0.0.1:%d/v1" % args.port
    if not args.dry_run:
        run_dir.mkdir(parents=True, exist_ok=True)
        preflight(base_url, args.api_key, args.model)

    env = os.environ.copy()
    # mini-swe-agent runs inside the container, so it must cross back to the host.
    container_url = "http://host.docker.internal:%d/v1" % args.port
    agent_url = base_url if args.harness == "custom" else container_url
    env.update({
        "OPENAI_API_KEY": args.api_key,
        "OPENAI_BASE_URL": agent_url,
        "OPENAI_API_BASE": agent_url,
        "LLM_API_KEY": args.api_key,
        "LLM_BASE_URL": agent_url,
        "PYTHONPATH": os.pathsep.join(
            [str(HARNESS_ROOT), str(ROOT), env.get("PYTHONPATH", "")]
        ),
    })
    # Harbor's mini-swe adapter prefers MSWEA_API_KEY and would shadow the
    # OpenAI-compatible credentials litellm actually needs.
    env.pop("MSWEA_API_KEY", None)
    env.pop("OPENROUTER_API_KEY", None)

    print("run     : %s" % run_name)
    print("harness : %s" % args.harness)
    print("model   : %s (held constant across harnesses)" % args.model)
    print("endpoint: %s" % agent_url)
    print("tasks   : %d" % len(tasks))
    print()

    for index, task in enumerate(tasks, start=1):
        out_dir = run_dir / task
        if already_done(out_dir):
            print("[%2d/%2d] %-32s skip (already scored)" % (index, len(tasks), task))
            continue
        cmd = build_command(args.harness, task, run_dir, args.model, args)
        print("[%2d/%2d] %-32s running" % (index, len(tasks), task), flush=True)
        if args.dry_run:
            print("        " + " ".join(cmd))
            continue
        subprocess.run(cmd, cwd=ROOT, env=env, check=False)

    if not args.dry_run:
        aggregate(run_dir, ROOT / "results" / ("%s.csv" % run_name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
