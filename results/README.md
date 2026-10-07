# Final study results

This directory contains the completed Terminus-2 and OpenHands baselines, the original final C0-NC run and its three separate setup-recovery attempts.

| File | Records |
| --- | --- |
| `baselines/trials.csv` | 89 Terminus-2 attempts and 89 OpenHands attempts |
| `custom/trials.csv`, `custom/trials.json` | The original 89 C0-NC attempts |
| `custom/recovery/trials.csv`, `custom/recovery/trials.json` | Three recovery attempts linked to original setup failures |
| `summary.json` | Derived comparison, original scores and separate recovery accounting |

The CSV and JSON attempt records retain their original bytes. Their filenames have been relocated for a concise repository layout; they have not been relabelled as new runs. The summary is a derived reporting view, not a raw run receipt.

Run `python3 scripts/report_results.py` from the repository root to reproduce the final comparison. All 89 tasks remain in the score denominator. The recovery-inclusive custom result covers 92 attempts across 89 distinct tasks, not 92 benchmark tasks.
