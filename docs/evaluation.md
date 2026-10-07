# Evaluation

## Study design

The study compares Terminus-2, OpenHands and the final C0-NC custom harness on the same fixed 89-task Terminal-Bench 2.1 set. Twenty tasks were used during custom-harness development; the remaining 69 are reported separately. The task identities and development split are stored in `configs/tasks.json`.

All three use DeepSeek V4 Flash 0731 through OpenRouter, pinned to DeepInfra FP8 with fallback disabled. The saved settings are temperature 1.0, top-p 1.0 and high reasoning effort. Evaluation ran in isolated Harbor containers on native x86-64 Linux hosted by Netcup, with official per-task deadlines and resource limits.

## Results

| Harness | Development tasks | Remaining tasks | Total passed |
| --- | ---: | ---: | ---: |
| C0-NC | 15 / 20 | 35 / 69 | 50 / 89 |
| Terminus-2 | 14 / 20 | 38 / 69 | 52 / 89 |
| OpenHands | 10 / 20 | 34 / 69 | 44 / 89 |

C0-NC solved six more tasks than OpenHands and two fewer than Terminus-2. These are observed single-run differences. The experiments ran on separate dates, so provider variability and runtime conditions prevent a causal claim that one harness is generally superior. No additional matched baseline repeat is included in these final results.

## Custom setup recovery

The original custom run recorded 50 passes, 36 verified failures and three setup failures without verifier outcomes. Those three tasks were later evaluated in separate recovery attempts, each producing a verified failure.

The recovery-inclusive reporting view therefore has **89 distinct tasks, 92 recorded attempts, 50 passes and 39 verified failures**. Its pass rate remains 50 / 89 = 56.18%. This is not a single uninterrupted 89-attempt run. The original and recovery records remain separate and unchanged; the reporting script joins them using the original trial identity and result hash, refusing substitution of an already verified outcome.

## Evidence and analysis

The committed CSV and JSON files contain task identities, official rewards, timings, errors, request counts, available usage and result hashes. Missing costs or tokens are not treated as zero. These records are curated exports; private model exchanges and credentials are not published.

`python3 scripts/report_results.py` validates task coverage, calculates the scores and prints the final comparison. `--json` prints the same derived summary in JSON. `results/summary.json` is reproducible from these inputs and is checked by the result tests.

The harness tests use offline models and owned local test processes. They verify implementation behaviour, not new hosted-model benchmark performance.
