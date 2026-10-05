# Deep Agents custom harness (Harshini)

Custom Terminal-Bench 2.1 harness built on **Deep Agents / LangGraph**, for the
Stage 2 comparison set by the client: **DeepSeek V4 Flash 0731** (DeepInfra FP8 via OpenRouter),
baselines **Terminus-2** and **OpenHands**.

| Piece | File |
|---|---|
| Harbor agent + Deep Agents graph | [`harness/agent.py`](harness/agent.py) |
| Container backend (execute, file tools) | [`harness/backend.py`](harness/backend.py) |
| Offline smoke test (fake model + Docker) | [`tests/smoke_offline.py`](tests/smoke_offline.py) |
| Task runner | [`run_probe.py`](run_probe.py) |
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
# OPENROUTER_API_KEY must be set as a user environment variable
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

## Reference scores (Netcup server, same model)

| Harness | Dev 20 | Full 89 |
|---|---:|---:|
| Terminus-2 | 14 | 52 |
| OpenHands | 10 | 44 |
| Karthik's custom harness (C0 / C0-NC) | 15 | 50 |

Results for this harness: [`results/harshini/deepagents/`](../../results/harshini/deepagents/),
summarised in the [branch README](../../README.md). Runs on the Windows laptop host
should be compared against Terminus-2 run on the same host.

Summarise a finished run into a CSV:

```powershell
python experiments/harshini-deepagents/summarize_run.py dev20-v0.1.2 --dev20
```
