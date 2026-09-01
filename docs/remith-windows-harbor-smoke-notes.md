# Remith Windows Harbor Smoke Notes

Date: 2026-09-01
Branch: `remith/qwen-ollama-workflow`
Contributor: Remith

## Purpose

This note records Remith's local Windows setup checks for the Terminal-Bench 2.1 harness evaluation project. The goal of these checks was to confirm that the local machine can run Harbor jobs through Docker Desktop and connect benchmark containers to the local Ollama model server.

These are smoke tests only. They are not the full 21-task fixed subset and are not final benchmark results.

## Local Environment

- Operating system path used for the repository: `C:\Users\remit\OneDrive\Desktop\UTS-ilab-Group-15-02`
- Docker Desktop: installed and running with the WSL2-backed Linux engine
- Docker client/server version observed: `29.7.2`
- Docker context observed: `desktop-linux`
- Docker smoke command: `docker run --rm hello-world`
- Harbor version: `0.22.0`
- Ollama version: `0.33.2`
- Local model installed: `qwen2.5-coder:7b`
- Docker-to-Ollama check: `docker run --rm curlimages/curl:8.16.0 -fsS http://host.docker.internal:11434/api/version`
- Docker-to-Ollama result: `{"version":"0.33.2"}`

## Dataset And Task

- Harbor dataset: `terminal-bench/terminal-bench-2-1`
- Smoke-test task: `terminal-bench/build-pmars`
- Model held constant for baseline harness smoke tests: `openai/qwen2.5-coder:7b`

The initial task filter `headless-terminal` did not match the registered Terminal-Bench 2.1 dataset. Harbor reported that `terminal-bench/build-pmars` was an available task, so that task was used for the smoke checks.

## Smoke Results

| Run | Harness | Model | Reward | Exceptions | Runtime | Interpretation |
| --- | --- | --- | ---: | ---: | --- | --- |
| `remith-oracle-smoke-build-pmars` | `oracle` | N/A | 1.0 | 0 | 57s | Harbor, Docker, dataset resolution, task environment, and verifier worked. |
| `remith-mini-swe-qwen7b-smoke-build-pmars` | `mini-swe-agent` | `openai/qwen2.5-coder:7b` | 0.0 | 0 | 1m 27s | Infrastructure worked, but the task was not solved. |
| `remith-mini-swe-qwen7b-smoke-build-pmars-config` | `mini-swe-agent` | `openai/qwen2.5-coder:7b` | 0.0 | 0 | 1m 17s | Infrastructure worked with the repo config file, but the task was not solved. |
| `remith-openhands-qwen7b-smoke-build-pmars` | `openhands` | `openai/qwen2.5-coder:7b` | 0.0 | 0 | 2m 50s | Infrastructure worked, but the task was not solved within the configured iteration limit. |
| `remith-custom-qwen7b-smoke-build-pmars` | `uts-qwen-harness` | `openai/qwen2.5-coder:7b` | 0.0 | 0 | 5m 56s | Infrastructure worked, but the custom harness did not solve the task within its step limit. |

## Observations

- The Oracle run passed with reward `1.0`, which confirms the benchmark task itself is runnable locally.
- The Mini-SWE-Agent runs completed without Harbor exceptions, but the agent transcript ended with `RepeatedFormatError`. Qwen did not emit the required Mini-SWE-Agent bash tool-call format.
- The OpenHands run completed without Harbor exceptions, but OpenHands reached the configured `max_iterations=25` limit. Harbor also reported `No final_metrics found in trajectory`.
- The custom harness run completed without Harbor exceptions and used the expected `uts-qwen-harness` version `2.2.0`. It made 25 model calls, used 43,590 input tokens and 2,318 output tokens, then terminated at `step_limit`.
- In the custom harness run, Qwen attempted package/source commands but did not produce a valid no-X11 source build. The verifier still reported that `/usr/local/bin/pmars` was missing or unusable and that the expected source layout was not present.
- The verifier failures for the model harness runs were expected consequences of the task not being solved. For `build-pmars`, the verifier reported that `/usr/local/bin/pmars` was not installed and that no `/app/pmars-*` source directory existed.
- The model remained constant for the Mini-SWE-Agent and OpenHands smoke tests. The harness was the changed variable.

## Next Steps

1. Keep the Oracle smoke result as environment validation, not as a model score.
2. Treat the Mini-SWE-Agent and OpenHands smoke runs as baseline harness compatibility evidence.
3. Avoid committing the full `jobs/` directory because Harbor job outputs can be large and the repository already ignores it.
4. Add curated summaries or selected evidence under a Remith-specific results directory only if the team agrees on the evidence format.
5. Next technical work should focus on the custom harness, because the project objective is to compare against established harnesses while holding the model constant.
