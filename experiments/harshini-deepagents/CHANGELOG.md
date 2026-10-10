# Changelog

## Unreleased — Langfuse tracing (no change to agent behaviour)

- `harness/tracing.py`: one Langfuse trace per trial when `LANGFUSE_PUBLIC_KEY` and
  `LANGFUSE_SECRET_KEY` are set. Root observation named after the task, session = run
  name, tags = harness name and version; every model call and tool call is nested under
  it through the LangChain callback handler. Without the keys nothing is loaded.
- Tracing failures never affect a run: errors are recorded in metadata
  (`langfuse_error`), and the final upload is capped at 30 s.
- Metadata adds `langfuse_trace_id` and `langfuse_trace_url` when tracing is on.
- Offline smoke test: 12/12 checks (adds "no tracing without keys" and "unreachable
  Langfuse server does not affect the run").

## 0.1.3 — 2026-10-05

- Provider errors are retried inside the task deadline: HTTP 429, 5xx and connection
  failures get exponential backoff (2 s doubling to 60 s, ±20% jitter) with no count
  cap, matching the C0 reference retry rule. The OpenAI client's own retries are off,
  so every retry is counted.
- Metadata adds `model_retries` and `model_retries_by_type`.
- Offline smoke test adds a scripted 429 (10/10 checks pass).
- Added `harness/terminus_pinned.py` (Harbor's Terminus-2 with the reference model
  settings and the same retry rule) and `repeat_study.py`. Terminus-2 probe on
  `openssl-selfsigned-cert`: 1/1 on the Windows laptop.

### dev-20 on 0.1.2 — stopped after 3 tasks

All three tasks ended with `OpenAIRateLimitError` (DeepInfra `engine_overloaded`,
shared upstream pool) after the client's built-in retries, with no verifier result.
The run was stopped; no score.

## 0.1.2 — 2026-10-03

- Empty-reply nudge: a model turn with no text and no tool call no longer ends the
  run; the harness asks the model to continue (up to 3 times while >30 s remain).
- Images without `python3`: `write_file` creates parent directories with a shell
  preflight instead of Deep Agents' Python one, and the Python-backed file tools
  (`read_file`, `edit_file`, `ls`, `grep`, `glob`) are hidden from the model, with a
  note telling it to use shell tools.
- Metadata adds `empty_reply_nudges` and `image_has_python3`.
- Offline smoke test adds a `debian:bookworm-slim` scenario (9/9 checks pass).

### Partial dev-20 run on 0.1.1 (stopped at task 6 when the host went down)

| Task | Reward | Stop | Cause |
|---|---:|---|---|
| constraints-scheduling | 1.0 | model_done | |
| distribution-search | 1.0 | model_done | |
| adaptive-rejection-sampler | 0.0 | deadline | `write_file` failed: no `python3` on the R image |
| build-pov-ray | 0.0 | model_done | empty model reply ended the run at 14 of 200 min |
| db-wal-recovery | 0.0 | deadline | no working approach found |

Not a valid score: two of the three failures came from the harness bugs fixed above.

## 0.1.1 — 2026-10-03

- Prompt: deliverables must run with the tools and packages already on the image,
  because the grader may run them in a fresh environment.

### Probes — `openssl-selfsigned-cert`, k=1, Windows laptop host

| Version | Reward | Tests | Cost | Agent time |
|---|---:|---:|---:|---:|
| 0.1.0 | 0.0 | 5/6 | $0.0037 | ~2 min |
| 0.1.1 | 1.0 | 6/6 | $0.0076 | ~3 min |

0.1.0 failed only `test_python_verification_script`: the agent pip-installed
`cryptography` for its check script, and the verifier's Python did not have it.

## 0.1.0 — 2026-10-03

- Deep Agents (LangGraph) controller as a Harbor `BaseAgent`, pinned to
  `deepseek/deepseek-v4-flash-0731` on `deepinfra/fp8` (temperature 1.0, reasoning high,
  384k max output tokens).
- Container backend: sticky cwd, per-command cap (default 300 s, bounded by the task
  deadline), head/tail output clipping at 12k chars, background-job hint on timeout.
- Middleware adds remaining time as a trailing message on each model call.
- Finish gate: up to two nudges when the model stops after a failed command.
- `write_todos` kept; general-purpose sub-agent and summarisation disabled.
- Offline smoke test passes (sticky cwd, read_file, command kill, finish nudge).
- No scored runs yet.
