# Bash-ReAct Harbor agent

Custom [Harbor](https://github.com/harbor-framework/harbor) agent for **Terminal-Bench 2.1**. The agent asks the model for one bash command, runs it in the task container, and repeats until `DONE` or the step limit.

This is a harness comparison, not a model comparison. The same model is used for the custom agent and the baseline.

## Requirements

- Docker Desktop
- Harbor (`uv tool install harbor`)
- For local runs: [Ollama](https://ollama.com) with `qwen2.5-coder:1.5b`
- For hosted runs: OpenRouter key in `.env` (do not commit)

## Usage

From this folder (or with `PYTHONPATH` set to the folder that contains `harness/`):

```powershell
# official solution, no model
harbor run -d terminal-bench/terminal-bench-2-1 -a oracle -i terminal-bench/openssl-selfsigned-cert -n 1 -k 1 -o jobs --job-name oracle-openssl --yes

# custom agent, local Ollama
python harness/run_local.py openssl-selfsigned-cert

# custom agent, hosted model
harbor run -d terminal-bench/terminal-bench-2-1 `
  -a harness.v0_bash_agent:BashReActAgent `
  -m openai/gpt-4o-mini `
  -i terminal-bench/openssl-selfsigned-cert `
  -n 1 -k 1 -o jobs --job-name v02-openssl --yes --env-file .env

# baseline
harbor run -d terminal-bench/terminal-bench-2-1 `
  -a terminus-2 `
  -m openrouter/openai/gpt-4o-mini `
  -i terminal-bench/openssl-selfsigned-cert `
  -n 1 -k 1 -o jobs --job-name term2-openssl --yes --env-file .env
```

`harness/run_probe.py` calls the paid API. Leave it unused unless credit is available.

## Agent design

Implementation: [`harness/v0_bash_agent.py`](harness/v0_bash_agent.py)

The model must reply with a single fenced command:

```bash
one command
```

Harbor `exec` starts a new shell each time, so the agent wraps the command in `cd $cwd` and records `pwd` after it. Several bash fences in one reply are rejected. `DONE` only stops the loop when there is no command in the same message.

| Version | Behaviour |
|---|---|
| 0.1.0 | First bash fence only. `cd` not persisted. |
| 0.2.0 | One fence per turn; sticky cwd; DONE ignored if a command is present. |
| 0.3.0 | First DONE denied (extra review turn). Reverted. |
| 0.2.1 | Same loop as 0.2.0; OpenRouter or local Ollama. **Current.** |

Changelog: [`harness/CHANGELOG.md`](harness/CHANGELOG.md)

## Results

Official Terminal-Bench reward is 1 only if every hidden test passes. Agent runs below scored 0 on that metric. Tables use hidden tests passed.

### `openssl-selfsigned-cert` (6 tests)

| Agent | Model | Tests | Failed checks |
|---|---|---:|---|
| bash-react 0.2.0 | gpt-4o-mini | 4 / 6 | `verification.txt` dates; `import OpenSSL` |
| terminus-2 | gpt-4o-mini | 4 / 6 | same two |
| bash-react 0.3.0 | gpt-4o-mini | 4 / 6 | same two; ~4× tokens vs 0.2.0 |
| bash-react 0.2.1 | qwen2.5-coder:1.5b (local) | 1 / 6 | directory only |

### Other

| Agent | Task | Tests | Notes |
|---|---|---|---|
| oracle | 5 TB 2.1 tasks | 4 / 5 | `torch-tensor-parallelism` verifier timed out (no GPU) |
| bash-react 0.1.0 | pypi-server | — | only first fence ran; not a valid comparison |
| bash-react 0.3.0 | fix-git | 1 / 2 | layout passed |
| terminus-2 | fix-git | — | OpenRouter 402; discarded |

Token counts and per-test detail: [`results/scores.md`](results/scores.md).  
Run commands and traces: [`results/WALKTHROUGH.md`](results/WALKTHROUGH.md).  
Iteration notes: [`results/WHAT_WE_LEARNED.md`](results/WHAT_WE_LEARNED.md).

## Layout

```
harness/v0_bash_agent.py   agent class
harness/run_local.py       Ollama helper
harness/run_probe.py       OpenRouter helper (paid)
harness/CHANGELOG.md
results/scores.md
results/WALKTHROUGH.md
results/WHAT_WE_LEARNED.md
```

Raw Harbor output is written to `jobs/` (gitignored).

## Scope

This is a development subset (one main task, a few probes), not a full 89-task leaderboard run. The originally listed 14B AWQ checkpoint was not used: that format needs a GPU, which this host does not have.
