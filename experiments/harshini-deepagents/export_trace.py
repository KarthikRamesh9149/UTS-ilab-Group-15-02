#!/usr/bin/env python3
"""Export the Langfuse trace of each trial in a run as a step-by-step Markdown timeline.

    python experiments/harshini-deepagents/export_trace.py trace-openssl-v0.1.3

Reads the trace id from each trial's result.json (written when tracing is on), fetches
the trace's observations from the Langfuse v2 observations API and writes
results/harshini/traces/<run>__<task>.md. Needs LANGFUSE_PUBLIC_KEY/SECRET_KEY
(environment or repo-root .env).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from run_probe import ROOT, load_dotenv

JOBS = ROOT / "jobs" / "harshini-deepagents"
OUT = ROOT / "results" / "harshini" / "traces"


def parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def fetch_observations(trace_id: str, started: datetime, finished: datetime) -> list[dict]:
    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com").rstrip("/")
    token = base64.b64encode(
        f"{os.environ['LANGFUSE_PUBLIC_KEY']}:{os.environ['LANGFUSE_SECRET_KEY']}".encode()
    ).decode()
    params = {
        "traceId": trace_id,
        "fromStartTime": (started - timedelta(minutes=5)).isoformat(),
        "toStartTime": (finished + timedelta(minutes=5)).isoformat(),
        "fields": "core,basic,io,usage,model",
        "limit": 1000,
    }
    observations, cursor = [], None
    while True:
        query = dict(params, **({"cursor": cursor} if cursor else {}))
        request = urllib.request.Request(
            f"{host}/api/public/v2/observations?{urllib.parse.urlencode(query)}",
            headers={"Authorization": f"Basic {token}"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read())
        observations += body.get("data", [])
        cursor = (body.get("meta") or {}).get("cursor")
        if not cursor:
            return observations


def as_dict(value) -> dict:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value) if isinstance(value, str) else {}
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def one_line(text, limit: int = 110) -> str:
    text = " ".join(str(text or "").split()).replace("|", "\\|")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def tool_detail(obs: dict) -> tuple[str, str]:
    args = as_dict(obs.get("input"))
    action = args.get("command") or args.get("file_path") or args.get("path") or args.get("pattern") or ""
    if obs["name"] == "write_todos":
        action = f"{len(args.get('todos') or [])} todo items"
    result = as_dict(obs.get("output")).get("content", obs.get("output"))
    return one_line(action), one_line(result, 80)


def render(task: str, run: str, meta: dict, reward, observations: list[dict]) -> str:
    steps = sorted((o for o in observations if o["type"] in ("GENERATION", "TOOL")), key=lambda o: o["startTime"])
    t0 = parse_time(steps[0]["startTime"]) if steps else None
    model_s = sum(o.get("latency") or 0 for o in steps if o["type"] == "GENERATION")
    tool_s = sum(o.get("latency") or 0 for o in steps if o["type"] == "TOOL")
    gens = [o for o in steps if o["type"] == "GENERATION"]
    reasoning = sum((o.get("usageDetails") or {}).get("output_reasoning", 0) or 0 for o in gens)
    output = sum(o.get("outputUsage") or 0 for o in gens)
    tools: dict[str, int] = {}
    for o in steps:
        if o["type"] == "TOOL":
            tools[o["name"]] = tools.get(o["name"], 0) + 1

    lines = [
        f"# Trace: `{task}` ({run})",
        "",
        "Exported from Langfuse by "
        "[`export_trace.py`](../../../experiments/harshini-deepagents/export_trace.py).",
        "",
        "| | |",
        "|---|---|",
        f"| Result | {'passed' if reward == 1 else 'failed' if reward is not None else 'no verifier result'} (reward {reward}) |",
        f"| Harness | {meta.get('harness')} {meta.get('harness_version')} |",
        f"| Stop reason | {meta.get('stop_reason')} |",
        f"| Model calls | {len(gens)} ({sum(o.get('latency') or 0 for o in gens):.0f} s waiting on the model) |",
        f"| Tool calls | {sum(tools.values())} ({', '.join(f'{k} {v}' for k, v in sorted(tools.items()))}; {tool_s:.0f} s) |",
        f"| Output tokens | {output:,} ({reasoning:,} of them reasoning) |",
        f"| Time split | model {model_s / max(model_s + tool_s, 1e-9):.0%}, tools {tool_s / max(model_s + tool_s, 1e-9):.0%} |",
        "",
        "| # | t (s) | Step | Action | Result / tokens | Took (s) |",
        "|---:|---:|---|---|---|---:|",
    ]
    for index, obs in enumerate(steps, start=1):
        offset = (parse_time(obs["startTime"]) - t0).total_seconds()
        took = f"{obs.get('latency') or 0:.1f}"
        if obs["type"] == "GENERATION":
            usage = obs.get("usageDetails") or {}
            tokens = f"in {obs.get('inputUsage') or 0:,} · out {obs.get('outputUsage') or 0:,}"
            if usage.get("output_reasoning"):
                tokens += f" (reasoning {usage['output_reasoning']:,})"
            lines.append(f"| {index} | {offset:.0f} | model | | {tokens} | {took} |")
        else:
            action, result = tool_detail(obs)
            lines.append(f"| {index} | {offset:.0f} | `{obs['name']}` | `{action}` | {result} | {took} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    OUT.mkdir(parents=True, exist_ok=True)
    for result_path in sorted((JOBS / args.run).glob("*/*/result.json")):
        result = json.loads(result_path.read_text(encoding="utf-8"))
        meta = (result.get("agent_result") or {}).get("metadata") or {}
        trace_id = meta.get("langfuse_trace_id")
        task = result_path.parents[1].name
        if not trace_id:
            print(f"{task}: no trace id (tracing was off)")
            continue
        started = parse_time(result["started_at"])
        finished = parse_time(result.get("finished_at") or result["started_at"])
        reward = ((result.get("verifier_result") or {}).get("rewards") or {}).get("reward")
        observations = fetch_observations(trace_id, started, finished)
        path = OUT / f"{args.run}__{task}.md"
        path.write_text(render(task, args.run, meta, reward, observations), encoding="utf-8")
        print(f"{task}: {len(observations)} observations -> {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
