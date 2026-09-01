# Small-model baseline check — Shruthi

**What this is:** a quick, individual check for tonight's weekly team report, run on
my own machine. It is **not** part of the team's formal 21-task / 3-harness / 2-model
comparison matrix described in the main [README](../README.md) — that matrix uses
locally-hosted Qwen models and the team's custom harness. This is a separate, one-off
run using Harbor's own built-in agent, against a small slice of the full benchmark,
so we'd have *some* small-model number to bring to tonight's report.

## What was run

| Setting | Value |
|---|---|
| Harness / agent | Harbor's `terminus-2` agent |
| Model | `claude-3-haiku` (Anthropic), accessed via OpenRouter |
| Benchmark dataset | `terminal-bench/terminal-bench-2-1` (the Terminal-Bench 2.1 benchmark, 89 tasks total) |
| Tasks run | 5 tasks (a small sample, not the full 89 — chosen for a quick same-night check, not a statistically meaningful score) |
| Date/time | 1 September 2026, run started 14:06 AEST |
| Run tool | Harbor CLI v0.22.0, via Docker |

## Results

**1 out of 5 tasks passed → 20% pass rate**

| Task | Result |
|---|---|
| `kv-store-grpc` | ✅ Passed |
| `schemelike-metacircular-eval` | ❌ Failed |
| `write-compressor` | ❌ Failed |
| `pypi-server` | ❌ Failed |
| `torch-tensor-parallelism` | ❌ Failed |

No tasks errored out or timed out — all 5 ran to completion, the agent just didn't
solve most of them correctly.

## Resource usage

| Metric | Value |
|---|---|
| Input tokens | 31,638 |
| Output tokens | 8,679 |
| Total tokens | 40,317 |
| Estimated cost | **$0.0188 USD** (under 2 cents) |
| Total run time | ~12 minutes 15 seconds |

## Plain-English takeaway

Claude 3 Haiku is a small, cheap, fast model. On this quick 5-task sample it solved
1 in 5 terminal-based coding tasks — a modest result, which is expected for a
lightweight model on a benchmark designed to be genuinely hard (Terminal-Bench 2.1).
The main value of this run for tonight's report is confirming the harness pipeline
works end-to-end (OpenRouter → Harbor → Docker → verified pass/fail) and giving a
concrete, very-low-cost data point: **roughly $0.02 for 5 tasks**, so a full 89-task
run on this same small model would cost well under $1 in model spend (excluding time).

**Caveat:** 5 tasks is far too small a sample to draw firm conclusions about Haiku's
real capability on this benchmark — this is a smoke-test-scale number, not a
statistically reliable accuracy estimate. Treat the 20% figure as illustrative only.

## Where the raw data lives

Full trial logs, per-task transcripts, and verifier output are saved locally at
`~/harbor-jobs/shruthi-small-model-baseline/` on my machine (not committed to this
repo — they're large and mostly raw trajectory data). This markdown file plus
[`docs/shruthi-eval-process-flowchart.md`](../docs/shruthi-eval-process-flowchart.md)
are the committed, shareable record.
