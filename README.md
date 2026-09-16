# UTS iLab Group 15-02 — Terminal-Bench 2.1 harness comparison

This repository is a small, honest comparison of three coding-agent harnesses on a fixed 21-task Terminal-Bench 2.1 development subset:

- Mini-SWE-Agent (baseline 1)
- OpenHands (baseline 2)
- UTS Qwen custom harness 2.2.0

Each harness runs the same tasks once (`k=1`, concurrency 1, temperature 0) with both locally hosted Q4_K_M models:

- Qwen2.5-Coder-3B-Instruct (`qwen2.5-coder:3b`)
- Qwen2.5-Coder-7B-Instruct (`qwen2.5-coder:7b`)

The intended matrix is therefore 21 tasks × 3 harnesses × 2 models = **126 trials**. This is deliberately **not** a full 89-task run, an official leaderboard submission, or a statistically representative accuracy estimate.

## Harshini track (`harshini-trial-run`)

Larger open model on CETUS (Qwen2.5-Coder-14B-AWQ via vLLM) + Harbor on the Windows host. Details and CSVs: [`results/harshini/`](results/harshini/README.md).

| Check | Result |
|---|---|
| Oracle on scoring host | **21 / 21** valid |
| Custom harness × 14B (full 21) | **0 / 21** passes |
| mini-SWE × 14B | **Partial** (4/21 trials; 0 passes; interrupted — not a finished baseline) |

## Current phase: a model capable enough to separate harnesses

The 126-trial matrix scored **0 passes in every condition**, so accuracy could not
distinguish one harness from another. Terminal-Bench 2.1 is hard by construction —
frontier models score 65–85% and small models around 15% — and a 3B/7B checkpoint at
4-bit sits below the level where the benchmark produces signal at all.

The current phase keeps the frozen 21-task subset and the fairness controls below, and
changes only the model, to a size where a harness difference has somewhere to show up.

| Piece | Where | Status |
|---|---|---|
| Custom harness (one bash command per turn) | [`experiments/itsha-bash-react/`](experiments/itsha-bash-react/README.md) | v0.2.2 |
| Host Oracle check (frozen 21) | [`results/harshini/oracle-21-final.csv`](results/harshini/oracle-21-final.csv) | 21/21 |
| Custom × 14B scores | [`results/harshini/custom-21-final.csv`](results/harshini/custom-21-final.csv) | 0/21 |
| CETUS vLLM PBS scripts | [`hpc/`](hpc/) | in repo |
| Same-model subset runner | `scripts/run_subset_vllm.py` | working |

Oracle validation is host-specific, so it was re-run on the machine that will produce
the scored rows. That is verification only: the subset stays frozen at 21 task IDs and
the two host-limited tasks remain in the denominator.

## Evaluation safeguards

- The task list is frozen in `configs/progress_subset.txt`.
- Selection uses seed 42 and accepts only tasks whose official Oracle trial produced a valid passing verifier result.
- Oracle outcomes are selection evidence only and never enter model pass rates.
- A reward-zero model trial is retained; only unambiguous infrastructure failures may be corrected.
- Custom harness version 2.2.0 is frozen for every scored custom row.
- Missing trials remain visible in the 126-row CSV instead of disappearing from the denominator.
- Raw Harbor jobs and local model weights are ignored because of their size; curated CSV, summaries, manifests, and terminal evidence are committed.

## Reproduce or resume

The project uses local, ignored tool/model directories. See `docs/setup-notes.md` for exact versions and endpoint details.

```bash
make preflight
make model-start
make model-test
make matrix
make collect
make report
make evidence
make test
```

`scripts/run_matrix.py` is resumable: it discovers valid existing trials by task, harness, model, and frozen custom version, then runs only missing cells sequentially.

## Results

The completed run artifacts live under `results/progress_smoke_20260831_133343/`. Read `summary.md` for the six-condition comparison, `results.csv` for all intended trial rows, `limitations.md` before interpreting the numbers, and `terminal_evidence/` for per-condition output captures.

Model | Harness | Valid / Intended | Passed | Pass rate | Mean runtime
--- | --- | ---: | ---: | ---: | ---:
Qwen 3B | Mini-SWE-Agent | 21 / 21 | 0 | 0.0% | 353.5 s
Qwen 3B | OpenHands | 21 / 21 | 0 | 0.0% | 442.9 s
Qwen 3B | UTS custom 2.2.0 | 20 / 21 | 0 | 0.0% | 233.2 s
Qwen 7B | Mini-SWE-Agent | 21 / 21 | 0 | 0.0% | 289.7 s
Qwen 7B | OpenHands | 21 / 21 | 0 | 0.0% | 515.0 s
Qwen 7B | UTS custom 2.2.0 | 21 / 21 | 0 | 0.0% | 400.4 s

All six conditions scored zero passes, so this run provides no evidence that any harness or model size is more accurate on the subset. The custom harness had the lowest mean runtime with 3B, but one of its 3B trials exceeded the frozen 120-second command limit before verification; that row remains an invalid, non-infrastructure outcome. Runtime alone is not a quality win.

The custom harness is intentionally benchmark-specific rather than a general agent framework. It uses a strict JSON action contract, phase-aware prompting, rolling context, bounded execution, repeat/destructive-command guards, exact artifact checks, and an edit-plus-test completion gate. Its behavior is covered by the repository test suite and frozen at version 2.2.0 for all scored custom rows.
