# C0-NC final phase-reporting amendment

## Scope and dated evidence

This is a separate reporting amendment for the already running, frozen C0-NC
final89, not a new candidate or a change to execution. Its execution source set
remains `4f73ab4083b76f555ff3bf695d7fed87ddbf4e5982551473418b8005eaf24d05`.
The qualification and registration remain the exact bindings published in
[the final-run evidence](../results/custom-no-cutoff-final-20260928/README.md).
The original `export_no_cutoff_final.py`, all frozen execution sources and all
retained results remain unchanged. No task is repeated or replaced.

At 19:21:56 UTC on 28 September 2026, metadata inspection found three retained
`setup_failed` / `RuntimeError` outcomes at task positions 63, 64 and 65. They
had measured setup timing, zero model requests, no agent or verifier phase,
no verifier result, successful model revocation and owned-resource cleanup.
Their causes were not established. The earlier SSH timeout does not establish
causation. At 20:20:41 UTC the study was still active with 68/89 completed,
41 passes, 24 zero-score failures and these three missing verifier outcomes.
These are dated partial observations, not the final score or a completed audit.

At 20:35:19 UTC, a separate read-only metadata check confirmed that the three
actual agent-deadline paths were absent and were not symlinks. It did not read
raw diagnostics, invoke a collector or run this new reader on the native host.

The old collector requires every phase and an agent-deadline record for every
result; its backup program also requires every deadline file. The frozen
execution activates that deadline only when `agent.run` starts. It must not be
recreated for a setup-only attempt. The amendment distinguishes a phase that
provably never ran from a phase whose required evidence is missing.

## Reporting rules

- Every registered attempt stays in the full89 denominator and its fixed
  development20 or remaining69 subset. Missing verifier outcomes remain null
  and are counted separately from verified zero-score failures. No best-of
  selection, score floor, inherited score or replacement attempt is allowed.
- For a proven setup-only failure, retain measured setup seconds. Report agent
  and verifier seconds as null with `not_run_setup_failed`, not zero and not a
  fabricated deadline. Preserve their official allowances separately.
- Admission to this reporting category requires the actual setup-failure
  result, error class, failed setup event, successful cleanup event and trial
  event. There must be no agent/verifier/tool/graph/generation event, request
  evidence or agent-deadline file. A status flag alone is insufficient.
- For an executed agent or verifier phase, the actual timing, trace event and
  agent-deadline evidence remain required. Missing or contradictory evidence
  rejects the audit; it does not become a not-run phase or an invented zero.
- Keep actual request counts, interrupted calls, missing generation timings
  and unknown costs. This amendment neither estimates costs nor establishes
  independent billing receipts. It does not change retry, model or task limits.
- Duration aggregates must state their measured and not-run denominators. A
  sum over observed durations is a measured subtotal, not an all-attempt total
  when any duration is null. Do not coerce null values to zero for old schemas.

The rule applies uniformly to all registered tasks, not an exception list for
the three observed failures. Unsupported lifecycle categories still fail
closed and require their own evidence review, not a generic missing-data bypass.

## Read-only implementation boundary

`no_cutoff_final_phase_audit.py` is a phase-evidence reader, not a completed89
collector, native qualifier, archive creator, exporter or dispatch witness.
It pins the exact original qualification, registration and runtime file bytes,
their canonical identities, the execution source set and unchanged trace,
lifecycle and collector sources. It reads each actual start/result, checks
registered identity and recorded image, and reads the trace and timing files.
Raw model request/response files are hashed without parsing or returning their
contents. Only allowlisted phase metadata and file bindings are returned.

All required events must have matching identities, unique complete sequences,
non-overlapping ordered phases, finite observed durations and consistent status
and verifier outcome. Recorded monotonic phase durations must match trace
measurements without converting Python numeric types. Official agent-deadline
and timeout checks remain. Generation timings must match the observed spans;
genuinely missing per-request timings remain explicitly counted, not fabricated.

The reader rejects duplicate JSON fields, non-finite values, unsafe paths,
symlinks, non-private runtime files, hard links, changed sources and contradictory
cleanup/revocation. File inventories and proven absences are retained and
reread before return. A later under-lock recheck detects new, removed or changed
evidence, including a deadline appearing after a setup-only classification.
The amendment document and reader have separate current source hashes; neither
is retroactively inserted into the final run's 211-file native qualification.

Every returned record remains `paid_launch_ready:false` and
`completed_final_audit:false`. A saved record is not proof of native service
state, original-lineage authentication, official dataset/resource enforcement,
live image identity, owned Docker-resource absence, full accounting or backup.
Those independent checks still belong to the completed audit. This component
does not acquire ancestor locks, invoke collectors or call a provider.

## Remaining integration before final audit and repeats

Do not invoke this reader natively while final89 is active or its state is
unknown. Its real consumer must first require the inactive completed service,
perform fresh original-lineage authentication before locks, hold every ancestor
lock, read the actual files, and reread all bindings and absences before return.
All exact89 coverage, source/runtime/registration, dataset, official limits,
trace, revocation, cleanup, original178 and stopped-four preservation checks
remain mandatory. No historical collector may be patched or silently bypassed.

A separate, explicitly source-bound completed-reporting entry still needs to
integrate this reader without coercing nulls into the old schema. Its one
streamed private backup must preserve actual files and attest proven absences,
not require or create nonexistent deadlines. Verify every bound original byte
and reread that same archive before allowlisted export. Do not recreate any
completed backup. The actual operator capture, native handoff, archive streaming
verification and repeat admission must consume that explicit amended schema;
they currently remain unchanged and cannot treat this reader as predecessor
admission. No completed-final archive or full89 score is claimed here.

## Local verification checkpoint

All 40 new tests passed. They use real private temporary files, the unchanged
trace validator and local fake lifecycle execution through the unchanged shared
phase runner. They cover measured pass/zero outcomes, verifier failure and
setup-only failure; exact raw and numeric bindings; privacy, links, duplicate
fields, source drift, mutations and newly appearing evidence; and explicit
unknown-cost and missing-generation counts. Temporary qualification bindings
and deadline inputs are synthetic test data, never native qualification or
production proof. No Docker, paid provider or native collector is exercised.

The first test run exposed a missing exact runtime-file byte check: whitespace
changes preserved its canonical identity. The reader now pins the original raw
runtime hash as well. Frozen collectors and execution sources were not changed.
The reader, its tests and this amendment are in the prospective repeat source
inventory and regression set, not retroactively added to the final qualification.
