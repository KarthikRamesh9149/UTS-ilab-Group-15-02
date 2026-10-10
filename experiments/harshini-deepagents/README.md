# Deep Agents custom harness (Harshini)

Custom Terminal-Bench 2.1 harness built on **Deep Agents / LangGraph**, for the
Stage 2 comparison set by the client: **DeepSeek V4 Flash 0731** (DeepInfra FP8 via OpenRouter),
baselines **Terminus-2** and **OpenHands**.

| Piece | File |
|---|---|
| Harbor agent + Deep Agents graph | [`harness/agent.py`](harness/agent.py) |
| Container backend (execute, file tools) | [`harness/backend.py`](harness/backend.py) |
| Optional Langfuse tracing | [`harness/tracing.py`](harness/tracing.py) |
| Trace → Markdown timeline | [`export_trace.py`](export_trace.py) |
| Offline smoke test (fake model + Docker) | [`tests/smoke_offline.py`](tests/smoke_offline.py) |
| Terminus-2 with the reference model settings | [`harness/terminus_pinned.py`](harness/terminus_pinned.py) |
| Task runner | [`run_probe.py`](run_probe.py) |
| Repeat study runner | [`repeat_study.py`](repeat_study.py) |
| Cross-model study runner | [`model_study.py`](model_study.py) |
| Dev subset (20 tasks) | [`dev20_tasks.txt`](dev20_tasks.txt) |

## Design

Model settings match the reference runs: temperature 1.0, reasoning effort high,
384k max output tokens, provider pinned to `deepinfra/fp8` with no fallbacks.

Harness levers (differences from the C0-NC reference agent):

- **Blocking `execute` with a per-command cap** (default 300 s, model can request more,
  never past the task deadline). Timed-out commands return a hint to background the
  job and poll its log. Working directory persists across calls.
- **Remaining time on every model call**, added as a trailing message by middleware
  so the system prompt (and provider prefix cache) stays fixed.
- **Finish gate:** if the model stops right after a failed command, it is sent back
  to fix or verify (at most twice).
- **Planning on** (`write_todos`); sub-agents and summarisation off.
- Official agent timeout read from the task's `task.toml` in Harbor's cache.

## Setup

```powershell
uv pip install --python "$(uv tool dir)\harbor\Scripts\python.exe" -r experiments/harshini-deepagents/requirements.txt
# OPENROUTER_API_KEY (and optional Langfuse keys): user environment variables, or a
# git-ignored .env at the repo root (template: experiments/harshini-deepagents/.env.example)
```

## Run

```powershell
$py = "$(uv tool dir)\harbor\Scripts\python.exe"
& $py experiments/harshini-deepagents/tests/smoke_offline.py        # free
python experiments/harshini-deepagents/run_probe.py oracle --dev20    # free, checks the host
python experiments/harshini-deepagents/run_probe.py custom openssl-selfsigned-cert   # paid
```

Raw Harbor output goes to `jobs/harshini-deepagents/<run-name>/` (not committed).
Per-trial trace: `<trial>/agent/deepagents-trajectory.json`.

### Langfuse tracing (optional)

Set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` as user environment variables
(and `LANGFUSE_HOST` for a non-EU region). Each trial then appears in Langfuse as one
trace named after the task, grouped into a session per run name, with every model call
(tokens, cost, latency) and tool call nested under it. The trace link is stored in the
trial's metadata as `langfuse_trace_url`. Without the keys, tracing is off and nothing
is loaded.

## Repeat study (same host)

All published scores for this model are single runs at temperature 1.0, so a
one- or two-task gap on dev-20 may be run-to-run noise. The repeat study measures
that directly on the Windows laptop: three dev-20 runs of this harness (frozen at
0.1.3) and three of Terminus-2, alternating between the two.

Terminus-2 here is Harbor's own agent ([`harness/terminus_pinned.py`](harness/terminus_pinned.py)):
its prompt, tools and loop are unchanged; only the connection is pinned to the
reference settings (model, DeepInfra FP8 route, temperature 1.0, reasoning high,
384k output tokens) with the same deadline-bounded retry on 429/5xx/connection errors.

```powershell
python experiments/harshini-deepagents/repeat_study.py
```

Outputs: `results/harshini/deepagents/dev20-v0.1.3{,-r2,-r3}.csv` and
`dev20-terminus2-r{1,2,3}.csv`. Official scores use each task's first attempt
(`summarize_run.py <run> --dev20 --attempt first`).

Result (5–10 October 2026): this harness 10, 8, 11 of 20 (mean 9.7); Terminus-2 11, 12,
11 (mean 11.3). Details in [`results/harshini/FINDINGS.md`](../../results/harshini/FINDINGS.md).

## Cross-model check

Every result above uses one model. To test whether the harness comparison depends on it,
[`model_study.py`](model_study.py) runs this harness and Terminus-2 on dev-20 with a
second model (Claude Haiku 5.5, Anthropic route), interleaved task by task, one run each:

```powershell
python experiments/harshini-deepagents/model_study.py --model anthropic/claude-haiku-5.5 --tag haiku
```

Outputs: `results/harshini/deepagents/dev20-haiku-v0.1.3.csv` and `dev20-haiku-terminus2.csv`.

## Reference scores (Netcup server, same model)

| Harness | Dev 20 | Full 89 |
|---|---:|---:|
| Terminus-2 | 14 | 52 |
| OpenHands | 10 | 44 |
| Stage 2 custom harness (C0 / C0-NC) | 15 | 50 |

Results for this harness: [`results/harshini/deepagents/`](../../results/harshini/deepagents/),
summarised in the [branch README](../../README.md). Runs on the Windows laptop host
should be compared against Terminus-2 run on the same host.

Summarise a finished run into a CSV:

```powershell
python experiments/harshini-deepagents/summarize_run.py dev20-v0.1.2 --dev20
```
