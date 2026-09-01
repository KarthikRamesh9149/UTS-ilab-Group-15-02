# Harshini trial run — custom Terminal-Bench harness

This is a first trial of a custom Harbor harness on **Terminal-Bench 2.1**.

The goal is the project brief: **hold one model fixed**, change only the wrapper (the harness), and see if a small custom loop can match or beat an established harness.

## What is being done

A coding agent is a **model** plus a **harness**.

| Piece | Meaning here |
|---|---|
| **Model** | The LLM. It only writes text. |
| **Harness** | The Python loop that prompts the model, runs its shell command in Docker, and sends the output back. |
| **Benchmark** | Terminal-Bench 2.1. Harbor starts a container, the harness works, then hidden pytest tests score the files. |
| **Official score** | 1 only if every hidden test passes. Otherwise 0. |
| **What I report** | Hidden **tests passed / total**, because official 0 vs 0 hides real progress. |

This trial:

1. Installed Harbor and checked that Docker works (oracle run, no AI).
2. Wrote a custom harness in `harness/v0_bash_agent.py` (one bash command per turn).
3. Compared it to **Terminus-2** (Harbor’s established Terminal-Bench harness) on the same task and same model.
4. Changed one harness rule at a time (v0.1 → v0.2 → v0.3) and recorded whether more tests passed.

Planned original setup was Qwen 14B AWQ + mini-SWE-agent + OpenHands. That 14B AWQ model needs a GPU. This PC has none, so the trial used **gpt-4o-mini** (hosted) and a free local **Qwen 1.5B**, with **Terminus-2** as the baseline that actually runs here.

## Results

Main task: `openssl-selfsigned-cert` (6 hidden tests).

| Run | Tests | What that means |
|---|---|---|
| Custom **v0.2** + gpt-4o-mini | **4 / 6** | Folder, key, cert, and pem were correct. Failed: `verification.txt` date format, and `check_cert.py` used `import OpenSSL` (not installed). |
| **Terminus-2** + gpt-4o-mini | **4 / 6** | Same four passed, same two failed. **Tied.** |
| Custom v0.3 + gpt-4o-mini | **4 / 6** | Forced an extra review before DONE. Same fails, about 4× the tokens. Dropped. |
| Custom v0.2 + local Qwen 1.5B | **1 / 6** | Same harness, weaker model. Directory only. |
| Oracle (official solution, no model) | **4 / 5** tasks | Harbor/Docker work on this PC. One GPU task timed out. |

Official Terminal-Bench reward is still **0** on the agent runs, because two openssl checks failed. The useful finding is the **4/6 tie** with Terminus-2 after the v0.2 loop fix.

More numbers: [results/scores.md](results/scores.md).  
Commands, code, and logs: [results/WALKTHROUGH.md](results/WALKTHROUGH.md).  
Keep vs drop: [results/WHAT_WE_LEARNED.md](results/WHAT_WE_LEARNED.md).

## How the custom harness works

Each turn the model must send **exactly one** command:

```bash
one command here
```

The harness runs it inside the task container, returns the output, and repeats. It remembers `cd`. If the model writes `DONE` with no command, it stops.

| Version | Change | Score move? |
|---|---|---|
| v0.1 | Run the first bash block only | No. A 6-step plan only ran `mkdir`. |
| **v0.2** | One command per turn + remember `cd` | **Yes.** openssl **4/6**, matching Terminus-2. **Keep this.** |
| v0.3 | Ignore the first DONE and force a review | **No.** Still 4/6, more tokens. **Drop this.** |
| v0.2.1 | Same as v0.2, plus local Ollama | 1.5B scored **1/6**. The 4/6 was the stronger model. |

## How to rerun (free)

Needs Docker Desktop and Harbor (`uv tool install harbor`).

```powershell
python harness/run_local.py openssl-selfsigned-cert
```

Do not run `harness/run_probe.py` unless there is OpenRouter credit. Paid retries are stopped.

## What this trial is not

- Not the full 89-task leaderboard.
- Not a claim of an official Terminal-Bench win. It is a **subtest tie** on one task.
- Next useful harness change: a **specific** prompt hint (verification.txt date format; Python via `openssl` CLI / stdlib, never `import OpenSSL`). Vague extra retries already failed.
