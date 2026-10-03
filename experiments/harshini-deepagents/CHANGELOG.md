# Changelog

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
