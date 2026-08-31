# UTS iLab Group 15-02 — Terminal-Bench 2.1 smoke evaluation

This repository contains a small, honest, reproducible infrastructure smoke evaluation of the local Ollama package `qwen2.5-coder:3b` on exactly three Terminal-Bench 2.1 tasks. Harbor runs the same model endpoint through Mini-SWE-Agent and OpenHands once per task (`k=1`, concurrency 1).

This is **not** a full 89-task benchmark, a statistically meaningful accuracy estimate, or an official leaderboard submission. The repository will be updated with exact commands, frozen task IDs, raw verifier evidence, result tables, and limitations after execution.

## Quick start

```bash
make all
```

The full clean-machine prerequisites and step-by-step reproduction instructions are recorded in `docs/setup-notes.md` after the live compatibility checks resolve the current Harbor 0.22.0 agent configuration.

