# Harshini results — branch `harshini-trial-run`

Frozen 21-task subset (`configs/progress_subset.txt`, seed 42).  
Team Ollama matrix (3B/7B): [`../progress_smoke_20260831_133343/`](../progress_smoke_20260831_133343/).

## Summary

| Run | Model | Result | Status |
|-----|--------|--------|--------|
| Oracle (Windows host) | n/a (official solutions) | **21 / 21** environments valid | Done — see [`oracle-21-final.csv`](oracle-21-final.csv) |
| Custom harness (`BashReActAgent`) | Qwen2.5-Coder-14B-AWQ on CETUS | **0 / 21** official passes | Done — [`custom-21-final.csv`](custom-21-final.csv) |
| mini-SWE-agent (same model) | Qwen2.5-Coder-14B-AWQ on CETUS | **0 passes**; **4/21** trials present (3 reward 0.0, 1 timeout); rest not run | Partial — GPU walltime / Docker / VPN cut the run short — [`mini-swe-agent-21-partial-20260915.csv`](mini-swe-agent-21-partial-20260915.csv) |

**Takeaway:** the scoring host can run all 21 tasks. On the open 14B model, the custom harness completed a full fair run at **0/21**. A same-model mini-SWE baseline was started with tool-enabled vLLM but **did not finish**; treat the partial CSV as incomplete, not a full comparison.

Earlier mini-SWE exports under this folder (`mini-swe-agent-21-final.csv`, `*-20260914_*.csv`) are **invalid** (empty stubs or vLLM rejecting tool calls) and should not be used as the baseline score.

## Files

| File | What it is |
|------|------------|
| [`oracle-21-windows-check.md`](oracle-21-windows-check.md) | Write-up of the Oracle host check |
| [`oracle-21-check.csv`](oracle-21-check.csv) | First Oracle pass (19/21; two timeouts) |
| [`oracle-21-final.csv`](oracle-21-final.csv) | Oracle after timeout multiplier (**21/21**) |
| [`custom-21-final.csv`](custom-21-final.csv) | Full custom × 14B run (**0/21**) |
| [`mini-swe-agent-21-partial-20260915.csv`](mini-swe-agent-21-partial-20260915.csv) | Incomplete mini-SWE × 14B attempt |
| `custom-21-20260912_201547.csv` | Stamp export for the custom job |
| `mini-swe-agent-21-*.csv` (other) | Invalid / superseded mini-SWE attempts |

Raw Harbor `jobs/` directories and watcher logs are not committed (large / local-only).

## How these runs were produced

- Model served on UTS CETUS (`hpc/stage_assets.pbs`, `hpc/serve_vllm.pbs`)
- Tasks run on the laptop via Harbor + SSH tunnel (`scripts/run_subset_vllm.py`, `scripts/watch_and_run.ps1`)
