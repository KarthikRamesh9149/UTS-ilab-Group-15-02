# Harshini — frozen 21-task runs (vLLM / Windows host)

Curated Harbor exports for the **`harshini-trial-run`** branch. Team-wide Ollama matrix lives in [`../progress_smoke_20260831_133343/`](../progress_smoke_20260831_133343/); teammate folders are under `results/saranya-*`.

**Subset:** `configs/progress_subset.txt` (21 tasks, seed 42).  
**Regenerate CSV:** `python scripts/summarize_job.py jobs/<job-dir> --csv results/harshini/<name>.csv`

## Artifacts

| File | Description |
|------|-------------|
| [`oracle-21-windows-check.md`](oracle-21-windows-check.md) | Oracle runnability on the Windows scoring host |
| [`oracle-21-check.csv`](oracle-21-check.csv) | First Oracle pass (19/21; two timeouts) |
| [`oracle-21-final.csv`](oracle-21-final.csv) | After `--timeout-multiplier 3.0` (21/21) |
| [`custom-21-final.csv`](custom-21-final.csv) | Custom harness, Qwen2.5-Coder-14B-AWQ via CETUS vLLM |
| [`mini-swe-agent-21-final.csv`](mini-swe-agent-21-final.csv) | mini-SWE-agent same model (invalid until tool-enabled vLLM) |
| `custom-21-20260912_201547.csv` | Raw export for job stamp (same trials as final where noted) |
| `mini-swe-agent-21-20260914_100136.csv` | Raw export for invalid tool-choice run |

**Not in git:** `jobs/` (Harbor trials), watcher logs, CETUS endpoint files.

## Infra on this track

- `hpc/` — stage weights + serve vLLM on CETUS  
- `scripts/run_subset_vllm.py` — custom + mini-SWE on one OpenAI-compatible endpoint  
- `scripts/watch_and_run.ps1` — tunnel + run when the PBS job starts  
