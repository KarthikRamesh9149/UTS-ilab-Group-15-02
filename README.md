# UTS iLab Group 15-02 — Terminal-Bench 2.1 harness comparison

## Active study: Netcup + OpenRouter

The [one-model Harbor study on native x86-64 Linux](stage2/NETCUP.md)
uses DeepSeek V4 Flash 0731 through the pinned DeepInfra FP8 endpoint.
Terminus-2, OpenHands and the custom Deep Agents/LangGraph harness use the same
benchmark. The saved study results include three 89-task baseline rounds, a
20-task C0–C3 custom-candidate comparison, and one completed 89-task C0-NC
custom run. Their different denominators and stages are reported separately
below.

The scores are one-run observations; they do not establish a causal
improvement or full-benchmark win. Recovery and matched-repeat results are
outside the summary below. The [CETUS local-model work](stage2/CETUS_LOCAL.md)
and the Stage 1 pilot below are preserved as separate historical experiments.

## Latest Netcup results (30 September 2026)

### Three full baseline rounds

Each round ran the same 89 tasks once with each harness (178 outcomes per round). Values below are passed / not-passed task counts.

| Round | Terminus-2 | OpenHands |
| --- | ---: | ---: |
| A — Original capped | 18 / 89 passed; 71 not passed | 4 / 89 passed; 85 not passed |
| B — API-troubled | 3 / 89 passed; 86 not passed | 1 / 89 passed; 88 not passed |
| C — Latest corrected | 52 / 89 passed; 37 not passed | 44 / 89 passed; 45 not passed |

The rounds had different operational settings. A used spending/billing-safety caps; B removed those caps but suffered model-service errors; C added temporary API retry handling and increased response/step allowances while retaining official task limits. Multiple settings changed, so the score differences do not identify a single cause. See the [earlier baseline records](stage2/results/baseline-credit-only-20260922/README.md) and [latest corrected baseline record](stage2/results/baseline-corrected-20260923/README.md).

### C0–C3 custom candidate comparison

These variants were compared on the fixed 20-task development subset:

| Variant | Passed | Not passed | Decision |
| --- | ---: | ---: | --- |
| C0 | 15 / 20 | 5 | Selected highest observed score |
| C1 | 14 / 20 | 6 | Not selected |
| C2 | 14 / 20 | 6 | Not selected |
| C3 | 13 / 20 | 7 | Not selected |

The cost tie-break was not used. The [selection record](stage2/results/custom-deadline-20260927/README.md) preserves the decision and qualification history.

### Final custom harness: C0-NC, all 89 tasks

| Scope | Passed | Verified zero-score failures | Setup-only; no verifier outcome |
| --- | ---: | ---: | ---: |
| Development subset (20) | 15 | 5 | 0 |
| Remaining tasks (69) | 35 | 31 | 3 |
| **Full C0-NC run (89)** | **50** | **36** | **3** |

The three setup-only attempts are missing verifier outcomes, not passes or zero scores. The run was audited, one off-server backup was verified, and its allowlisted result export was published. Reported known cost was **$1.71399138**, but **799 requests had unknown cost**; total cost remains unknown and independent billing receipts were not verified. See the [final C0-NC report](stage2/results/custom-no-cutoff-final-20260928/README.md).

C0's 15/20 development score is not an 89-task result. C0-NC is a later revised harness and must be treated as a separate run. No recovery attempt or matched-repeat baseline is included in these results.

## Historical Stage 1 pilot (preserved)

This repository is a small, honest comparison of three coding-agent harnesses on a fixed 21-task Terminal-Bench 2.1 development subset:

- Mini-SWE-Agent (baseline 1)
- OpenHands (baseline 2)
- UTS Qwen custom harness 2.2.0

Each harness runs the same tasks once (`k=1`, concurrency 1, temperature 0) with both locally hosted Q4_K_M models:

- Qwen2.5-Coder-3B-Instruct (`qwen2.5-coder:3b`)
- Qwen2.5-Coder-7B-Instruct (`qwen2.5-coder:7b`)

The intended matrix is therefore 21 tasks × 3 harnesses × 2 models = **126 trials**. This is deliberately **not** a full 89-task run, an official leaderboard submission, or a statistically representative accuracy estimate.

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
