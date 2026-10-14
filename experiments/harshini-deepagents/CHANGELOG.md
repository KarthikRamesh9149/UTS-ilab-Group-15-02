# Changelog

## 0.1.5 — 2026-10-14

- **Images are no longer sent to the DeepSeek route.** With `read_file` working (0.1.4),
  the model opened a QEMU screenshot it had saved as PNG (`install-windows-3.11`); Deep
  Agents attached the image, the DeepInfra route has no image input, and OpenRouter
  answered HTTP 404 "No endpoints found that support image input", ending the trial with
  no verifier result. `MODEL_SETTINGS` now gives the DeepSeek model a text-only profile
  (`image_inputs`, `audio_inputs`, `video_inputs`, `pdf_inputs` false), so Deep Agents
  replaces the media block with a text note ("… was not attached because this model
  does not support image content") before the request is sent. Haiku keeps image input.
- Offline smoke test: 18/18 (adds: a PNG read with `read_file` reaches the model as a
  text note, with no media block). The new check fails without the profile.
- `export_trace.py` reports failed model requests and the provider's error message, and
  counts only answered requests as model calls.
- Result, DeepSeek dev-20 (`dev20-v0.1.5`, 14 October): not a usable score. 572 of 801
  model requests were rejected (DeepInfra `engine_overloaded`); 6 tasks got no answer.

## 0.1.4 — 2026-10-11

Fixes for bugs found through Langfuse traces of the Claude Haiku 5.5 run.

- **`read_file` and `edit_file` work.** The backend appended `[cwd=… exit=…]` to every
  command's output, and Deep Agents parses its read/edit script output as bare JSON, so
  every call returned "unexpected server response" (0.1.3 dev-20 DeepSeek runs: 81 of 81
  reads and 26 of 26 edits failed; models fell back to shell commands). The cwd tag is
  now added only to the model's own `execute` results.
- **Tool calls of one turn run in issue order.** The tool node starts them concurrently
  and middleware delays some, so "write file, then run it" raced (`video-processing`
  on Haiku). `OrderedTools` makes each call wait for its predecessors (5 s safety
  release).
- **Unambiguous time note:** "Time left: 59 min 55 s of the 60 min limit (5 s used)"
  instead of "3595s of 3600s remaining", which Haiku read as 5 seconds left and gave up
  on all 9 failed tasks.
- **Retries that run into the deadline end the run cleanly** (`stop_reason` deadline,
  `error_type` `retries_exhausted:…`) so the grader still checks the task, instead of
  raising with no verifier result (the 6 lost tasks in DeepSeek run 2).
- Offline smoke test: 17/17 (adds strict read, read with offset, edit, same-turn order,
  time note, and clean end on exhausted retries; the old read check passed only because
  the error message contained the file's first 200 characters).
- Result, dev-20 on Claude Haiku 5.5 (`dev20-haiku-v0.1.4`): **15/20**, up from 11/20
  with 0.1.3 (gained `adaptive-rejection-sampler`, `db-wal-recovery`, `mailman`,
  `regex-chess`; none lost), against Terminus-2's 14/20; US$1.20 vs US$5.57.
- DeepSeek dev-20 (`dev20-v0.1.4`, 12–13 October): not a usable score. DeepInfra was
  overloaded for most of the run (8 tasks ended with `retries_exhausted:OpenAIRateLimitError`,
  several more ran to the limit with 0–5 model calls), `adaptive-rejection-sampler`
  overlapped laptop standby, and `install-windows-3.11` hit the image bug fixed in 0.1.5.
  The clean end on exhausted retries worked: every overload-hit task was still graded.

## Langfuse tracing and second-model option (no change to agent behaviour)

- `harness/tracing.py`: one Langfuse trace per trial when `LANGFUSE_PUBLIC_KEY` and
  `LANGFUSE_SECRET_KEY` are set. Root observation named after the task, session = run
  name, tags = harness name and version; every model call and tool call is nested under
  it through the LangChain callback handler. Without the keys nothing is loaded.
- Tracing failures never affect a run: errors are recorded in metadata
  (`langfuse_error`), and the final upload is capped at 30 s.
- Metadata adds `langfuse_trace_id` and `langfuse_trace_url` when tracing is on.
- Offline smoke test: 12/12 checks (adds "no tracing without keys" and "unreachable
  Langfuse server does not affect the run").
- Second model for a cross-model check: `MODEL_SETTINGS` in `harness/agent.py` lists the
  allowed models with their provider route and output cap. DeepSeek V4 Flash 0731
  (default) keeps the exact reference settings; Claude Haiku 5.5 is routed to Anthropic
  only, 128k output cap, without `require_parameters` (Anthropic does not list
  `temperature`). Both harnesses and `run_probe.py --model` use it; `model_study.py`
  interleaves the two harnesses task by task. Probes on `openssl-selfsigned-cert` with
  Haiku: this harness 1/1 (US$0.006), Terminus-2 1/1 (US$0.004).

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
