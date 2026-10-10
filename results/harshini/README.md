# Harshini results

Overview and current status: [branch README](../../README.md).

| Folder / file | Stage | What it is |
|---|---|---|
| [`FINDINGS.md`](FINDINGS.md) | 3 | All findings |
| [`deepagents/`](deepagents/) | 3 | One CSV per laptop run (Deep Agents and pinned Terminus-2) |
| [`progress.png`](progress.png) | 3 | Repeat-study scores next to the Stage 2 server scores ([`plot_progress.py`](plot_progress.py)) |
| [`dev20-tasks.png`](dev20-tasks.png) | 3 | Per-task grid: laptop runs vs. Stage 2 server runs ([`compare_reference.py`](compare_reference.py)) |
| [`traces/`](traces/) | 3 | Step-by-step task timelines exported from Langfuse ([`export_trace.py`](../../experiments/harshini-deepagents/export_trace.py)) |
| [`reference/`](reference/) | 3 | Stage 2 server results reduced to one row per task, extracted from `main` |
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
