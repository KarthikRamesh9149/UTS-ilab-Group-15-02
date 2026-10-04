# Changelog

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
