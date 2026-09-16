# Paired final analysis

The pure `final_analysis.analyze` function requires exactly the scheduled 267
unique final cells, one frozen model protocol, complete receipt-derived usage,
binary verifier outcomes, finite runtime and verified teardown. It does not
read or certify receipts itself; a durable-evidence collector must reaudit them
before calling it. Missing results are rejected, never imputed as passes or
silently excluded.

It reports condition totals and task-paired custom/baseline gains and regressions
on all 89 tasks and separately on the 69 outside the registered development set.
Costs include unsuccessful final trials. Setup, development and correction
costs require a separate project-wide accounting export, not this final-only sum.

An observed accuracy lead is explicitly distinguished from project completion.
Exact two-sided McNemar/binomial-tail p values are exploratory, unadjusted for
the two baseline comparisons, and based on one attempt per condition/task.
They do not establish repeatability or substitute for confidence intervals.
Tied observed accuracy is not statistical equivalence; no efficiency win is
automatically accepted without the mentor's required decision.

Tests use synthetic data, including all-zero results, development-only gains,
known discordant-tail probabilities, missing/duplicate cells, protocol drift and
unknown usage. No actual final results have been produced or claimed. The
analysis implementation is included in the finalist freeze hash set.
