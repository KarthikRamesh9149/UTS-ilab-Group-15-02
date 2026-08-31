# Parallel custom harness experiment

This folder is **one teammate’s experiment**. It is not the group’s main 21-task Ollama matrix.

If you are new: start here. You do not need to know Harbor, OpenRouter, or the other repo layout first.

## What the project is

We are not comparing models. We are comparing **wrappers around the same model**.

| Word | Meaning |
|---|---|
| **Model** | The LLM (the “brain”). Example: gpt-4o-mini. |
| **Harness / agent** | The loop around the model: system prompt, how it runs shell commands, how history is trimmed, when it is allowed to stop. Example: Claude Code is a harness; Claude Opus is a model. |
| **Terminal-Bench 2.1** | 89 Docker tasks. Hidden tests give a score of 1 (pass) or 0 (fail). |
| **Harbor** | The official runner. It starts a container, lets the harness work, then runs tests. |
| **Oracle** | A built-in “cheat” agent that runs the official solution. Used only to check that Harbor/Docker work. Oracle scores do **not** count as model accuracy. |
| **Terminus-2** | Harbor’s established Terminal-Bench harness. We used it as the published-style baseline. |

**Goal:** hold the model fixed, change only the harness, and see if a small custom harness can match or beat an established one.

Karthik’s work in the repo root uses **local Qwen 3B/7B + Mini-SWE-Agent + OpenHands + a JSON custom harness**. This experiment is **parallel**: a markdown bash loop, gpt-4o-mini (hosted, already run), and later local Ollama if installed.

## Results (read this)

The official Terminal-Bench score is 1 or 0 for the whole task. Our agent runs all “failed” that bar because two checks were still wrong. **That is not the finding.**

**Read [results/WALKTHROUGH.md](results/WALKTHROUGH.md)** if you want the actual commands, the Python, and the logs.

**Read [results/WHAT_WE_LEARNED.md](results/WHAT_WE_LEARNED.md)** for keep vs drop.

Short version:

| What we did | What happened |
|---|---|
| v0.1: run the first bash block only | Broken. A 6-step plan only ran `mkdir`. |
| **v0.2: one command per turn + remember `cd`** | openssl **4/6 tests**. Terminus-2 on the same model: **also 4/6**, same two fails. **Keep this.** |
| v0.3: refuse the first DONE | Still **4/6**, about 4× the tokens. **Drop this.** |
| Same v0.2 loop, local Qwen 1.5B | openssl **1/6**. Weaker model, not a harness win. |
| Oracle (no AI) | **4/5** tasks — Harbor works on this PC. |

Compact numbers: [results/scores.md](results/scores.md).

## How the custom harness works

Code: [`harness/v0_bash_agent.py`](harness/v0_bash_agent.py)

Each turn the model must reply with **exactly one** shell command:

```bash
one command here
```

The harness runs that command in the task container, sends the output back, and repeats. It remembers the working directory. If the model writes `DONE` with no command, it stops.

This is **deliberately different** from Karthik’s harness (JSON object + inspect/edit/test phases + “you may not finish until an edit and a test succeeded”). The point of running in parallel is to compare those design choices later.

### What we changed, and what moved the score

History: [`harness/CHANGELOG.md`](harness/CHANGELOG.md)

| Version | Change | Did the score move? |
|---|---|---|
| 0.1.0 | Markdown bash loop, take the first code fence | No. A 6-command plan only ran `mkdir`. `cd` was forgotten next turn. |
| **0.2.0** | One fence only; remember `cd`; ignore `DONE` if a command is also present | **Yes.** openssl went from “broken loop” to **4/6**, matching Terminus-2. **Keep this.** |
| 0.3.0 | Reject the first `DONE` and force a review | **No.** Still 4/6, 4× tokens. Model looped on `sed` instead of fixing the Python script. **Do not keep.** |
| 0.2.1 | Same as 0.2.0, plus optional **local Ollama** (no paid API) | openssl + 1.5B: **1/6**. Confirms the 4/6 was the hosted model, not a lucky container. |

## Folder map

```
README.md                 ← you are here
harness/
  v0_bash_agent.py        custom agent (the harness)
  run_probe.py            paid OpenRouter helper — do not use until we have credits
  run_local.py            free local Ollama helper
  CHANGELOG.md            one row per design change
results/WHAT_WE_LEARNED.md  ← tweaks, tests passed, keep vs drop
results/scores.md         compact test counts
jobs/                     raw Harbor outputs (large, not for git)
.env                      API keys — never commit, never paste in chat
```

`jobs/` is only for debugging a trial. Teammates should read `results/WHAT_WE_LEARNED.md`, not the raw folders.

## How to reproduce (free)

Needs: Docker Desktop running, Harbor (`uv tool install harbor`), this folder.

Oracle (no model):

```powershell
harbor run -d terminal-bench/terminal-bench-2-1 -a oracle -i terminal-bench/openssl-selfsigned-cert -n 1 -k 1 -o jobs --job-name oracle-openssl --yes
```

Local Ollama (after Ollama is installed and `ollama pull qwen2.5-coder:1.5b`):

```powershell
python harness/run_local.py openssl-selfsigned-cert
```

Do **not** run `harness/run_probe.py` unless someone has explicitly added OpenRouter credit. The last Terminus-2 retry burned leftover budget.

## What this is not

- Not the full 89-task leaderboard run.
- Not Karthik’s 21 × 3 × 2 matrix.
- Not a claim that we beat Terminus-2 on official reward. We **tied on subtests** on one task.
- Not pushed to GitHub until the group agrees. This lives as a local branch.

## Suggested next step

Keep **v0.2**. Next useful tweak (when you have compute, still $0 locally) is a **specific** hint: “write verification.txt with the org name as two words; in Python use `openssl` CLI or stdlib, never `import OpenSSL`.” Vague extra retries already failed.
