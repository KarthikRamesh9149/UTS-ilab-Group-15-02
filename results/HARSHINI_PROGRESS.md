# Harshini progress log — branch `harshini/21task-run`

**Owner:** Harshini Prasad (u26025369)  
**Purpose:** Single place to show progress for teammates / client update.  
**Rule:** Frozen 21-task subset (`configs/progress_subset.txt`). No re-selection after scores.

---

## Branch

| | |
|---|---|
| Working branch | **`harshini/21task-run`** |
| Based on | `main` |
| Push target | `origin/harshini/21task-run` (feature branch — not merging to `main` yet) |

---

## Timeline of results (old → new)

### 1) Early probe (OpenRouter gpt-4o-mini) — harness design signal

Source: `experiments/itsha-bash-react/results/scores.md`

| Comparison | Result |
|---|---|
| Custom v0.2 vs Terminus-2 on `openssl-selfsigned-cert` | **Matched 4/6 tests** (same passes/fails) |
| Custom v0.3 (deny early DONE) | Still 4/6, **~4× tokens** → reverted |
| Local Qwen 1.5B | 1/6 only |

**Takeaway:** harness can match an established agent on a capable model; small local models do not.

### 2) Team progress matrix (Ollama 3B/7B) — no harness signal

Source: `results/progress_smoke_20260831_133343/summary.md`

| Models × harnesses | Passed |
|---|---|
| 3B/7B × mini-SWE / OpenHands / uts-qwen | **0 / 126** (125 valid) |

**Takeaway:** model below the floor where harness differences show up.

### 3) Oracle on Windows host (this machine) — environment proven

Sources: `results/oracle-21-final.csv`, `results/oracle-21-windows-check.md`

| Check | Result |
|---|---|
| First pass | 19/21 (2 timeouts) |
| After `--timeout-multiplier 3.0` (§4.1.7) | **21 / 21** |

**Takeaway:** later zeros are model/harness, not “tasks won’t run here.”

### 4) Custom harness × Qwen2.5-Coder-14B-AWQ (CETUS vLLM) — current main number

Sources: `results/custom-21-final.csv`

| Metric | Value |
|---|---|
| Official TB pass (reward = 1.0) | **0 / 21** |
| Fair attempts | Yes (tunnel failures retried) |
| Tokens (approx.) | ~699k in / ~34k out |
| Model | `qwen2.5-coder-14b-awq` via CETUS |
| Harness | `BashReActAgent` v0.2.2 |

Per-task detail is in the CSV. Two `RuntimeError`, one `BadRequestError`; rest reward 0.0.

### 5) mini-SWE-agent same model — not a fair baseline yet

Sources: `results/mini-swe-agent-21-final.csv`

| Attempt | Outcome |
|---|---|
| First resume | Skipped (empty stubs) — fixed in runner |
| Full 21 rerun | **0/21** but **invalid**: vLLM rejected `tool_choice=auto` |
| Fix prepared | `--enable-auto-tool-choice` + `--tool-call-parser hermes` |
| Status at doc time | Serve job queued on CETUS; waiting on GPU |

**Takeaway for meeting:** same-model baseline is **pending infra**, not “mini-SWE scored zero fairly.”

---

## What to say at the client meeting

1. **Environment:** Oracle **21/21** on the scored host.  
2. **Custom harness:** full frozen subset on a **capable open 14B** → **0/21** official passes (honest capability floor).  
3. **Earlier signal:** on gpt-4o-mini, custom **matched Terminus-2** 4/6 on openssl (design works).  
4. **Team 3B/7B matrix:** 0/126 — why we moved to a larger open model via HPC.  
5. **Next:** fair mini-SWE baseline once CETUS tool-enabled server starts (script already updated).

---

## Repo layout (Harshini’s work)

| Path | What |
|---|---|
| `experiments/itsha-bash-react/` | Custom Bash-ReAct harness + early scores |
| `hpc/` | CETUS survey, stage, serve scripts |
| `scripts/run_subset_vllm.py` | Same-model 21-task runner |
| `scripts/watch_and_run.ps1` | Unattended tunnel + run |
| `scripts/summarize_job.py` | Harbor job → CSV |
| `results/oracle-*` | Host validation |
| `results/custom-21-final.csv` | Current custom scores |
| `results/mini-swe-agent-21-final.csv` | Invalid mini attempt (documented) |

---

## Not pushed (by design)

- `jobs/` (large Harbor raw trials)  
- `*.log` (watcher logs; may contain endpoint metadata)  
- Local pid stamps (`.watcher.pid`, etc.)
