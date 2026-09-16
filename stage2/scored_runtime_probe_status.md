# Full-runner infrastructure qualification

`scored_runtime_probe.py` drives the actual single-trial runner through Docker,
the host HTTP bridge, private relay, gateway, receipt recording, model revocation,
Harbor verifier and teardown. Only the model provider and tiny input fixture are
synthetic. The probe agent writes a marker after a successful gateway roundtrip;
this is not a real harness performance trial.

The fixture under `fixtures/lifecycle` is an infrastructure test, not a new
benchmark task. It is never added to Terminal-Bench's frozen dataset or scores.
Its credential and billing ledger are synthetic and isolated from project funds.

Current evidence (2026-09-16): Python syntax and Harbor fixture validation pass.
An attempted launch correctly returned lock contention while the oracle process
was live. A single `--label v1 --wait --rebuild-gateway` process is now queued
behind the shared host lock. It creates no task container while waiting and
checks host health after acquiring ownership. It has not yet passed its live
container checks. Do not launch another queued copy.

On execution, inspect `scored_runtime_probe_v1.json`, not this status note, for
the result. A failed attempt is retained and cannot be overwritten by the same
label. This check is necessary but not sufficient for paid scoring: native
OpenHands wire settings, protocol enforcement, matrix admission and billing
reconciliation remain separate gates.
