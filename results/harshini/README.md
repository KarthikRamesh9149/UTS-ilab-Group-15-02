# Harshini results

Overview and current status: [branch README](../../README.md).

| Folder / file | Stage | What it is |
|---|---|---|
| [`deepagents/`](deepagents/) | 3 | One CSV per Deep Agents run (DeepSeek V4 Flash) |
| [`progress.png`](progress.png) | 3 | Chart from the latest dev-20 CSV ([`plot_progress.py`](plot_progress.py)) |
| [`oracle-21-final.csv`](oracle-21-final.csv) | 2 | Oracle on the laptop after the timeout multiplier (**21/21**) |
| [`oracle-21-check.csv`](oracle-21-check.csv) | 2 | First Oracle pass (19/21; two timeouts) |
| [`oracle-21-windows-check.md`](oracle-21-windows-check.md) | 2 | Write-up of the Oracle host check |
| [`custom-21-final.csv`](custom-21-final.csv) | 2 | Custom bash harness × Qwen 14B, full 21 tasks (**0/21**) |
| [`mini-swe-agent-21-partial-20260915.csv`](mini-swe-agent-21-partial-20260915.csv) | 2 | mini-SWE-agent × Qwen 14B, unfinished (4/21 trials, 0 passes) |
| [`archive/`](archive/) | 2 | Superseded exports and invalid mini-SWE attempts; not used for any score |

## Deep Agents run CSVs

Columns: `task`, `status` (pass / fail / error / not run), `reward`, `stop_reason`
(`model_done` or `deadline`), `agent_min`, `budget_min` (task time limit), `cost_usd`,
`model_calls`, `harness_version`. Dev-20 CSVs keep all 20 tasks, so unfinished runs show
`not run` rows rather than a smaller denominator.

## Stage 2 notes

- Model served on UTS CETUS (`hpc/stage_assets.pbs`, `hpc/serve_vllm.pbs`); tasks run on the
  laptop via Harbor and an SSH tunnel (`scripts/run_subset_vllm.py`).
- The mini-SWE baseline was cut short by GPU walltime, Docker and VPN interruptions; the
  partial CSV is not a finished comparison.
- Files in `archive/` are empty stubs or runs where vLLM rejected tool calls.
