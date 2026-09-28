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

A separate completed-reporting entry is now implemented locally as described
below, without coercing nulls into the old schema. Its trusted invocation and
one streamed private backup must still preserve actual files and attest proven absences,
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

## Offline completed-audit reader

`no_cutoff_final_report.collect()` now integrates the leaf reader into a separate
completed89 audit. It has no CLI, caller-selected root, callback, saved-proof,
backup or paid-dispatch entry. It is local preparation and has not been invoked
on the native host. The future trusted launcher must independently bind its
reporting bundle before imports, outside the frozen execution tree,
at `/opt/uts-capstone-custom-no-cutoff-final-reporting-20260928`. That directory
has not been created. Trusted deployment/invocation is not yet implemented.

The reader requires the original final interpreter with `-I -B`, a fixed
credential-free environment, an absent bytecode-cache prefix and the original
trace validator. It checks an inactive/dead successful final service and no
stop before fresh original-lineage authentication. Authentication occurs before
the unchanged ancestor-lock chain, never recursively under those locks.

Under the locks it calls the actual unchanged qualification/runtime, image,
producer, dataset and registered-coverage readers. Each of the 89 rows uses the
real phase reader, actual official task configuration and unchanged passive
accounting. Fresh accounting must equal the retained result, with unknown costs
and missing generation timing retained. Raw request/response bytes are only
hashed. No native factory, setup, model, registration or dispatcher is called.
Owned containers, networks and volumes are inspected, never removed. Original
178 and stopped-four actual result hashes are reread against separately pinned
historical metadata; those metadata bytes also match the frozen execution
commit. This does not add them retrospectively to a historical qualification.

Source/input/producer, result, trace, accounting, exact inventory and proven
absence bindings are retained and reread after the final native observations.
The actual native qualification/runtime is verified again. The reporting
bundle is hashed separately, not inserted into the final's 211-file source set.
Service, stop, coverage, current source and preserved historical outcomes are
rechecked; a changed or incomplete observation fails closed without a retry.

The new audit schema explicitly distinguishes `completed_final_audit` from
off-server backup or paid admission. It returns `paid_launch_ready:false`,
`off_server_backup_verified:false` and
`archive_export_and_handoff_integrated:false`. The full89, development20 and
remaining69 aggregates retain missing outcomes and measured/not-run timing
denominators. A measured duration subtotal is not labelled an all-attempt total.
Saved records or these flags alone cannot grant predecessor admission.

All 42 new local tests passed using real synthetic private files for 89 trials,
actual phase/trace/accounting readers and a competing local lock. Native
service, Docker, task configuration, lineage and qualification observations are
mocked. Tests exercise setup-only/null, zero and pass results, 105 physical
requests with unknown costs, historical/result/source/producer mutations,
privacy, duplicate fields, strict native invocation context, audit-before-lock
ordering and final-observation mutation checks. These are not native audit,
qualification or paid benchmark evidence.

The separately bound launcher, one absence-aware streamed backup, allowlisted
export and real operator/native handoff integration remain unfinished. The
strict metadata/archive verifier below is separate from those operations.
Existing completed collectors, backups,
repeat predecessor readers and admission are unchanged and still fail closed
for this amended route. No native completed collector may run while final89 is
active or its state is unknown.

## Offline amended snapshot and archive verification

`no_cutoff_final_archive.py` adds strict validation of the explicit amended
schema and read-only verification of existing archive bytes. It has no writer,
CLI, network operation, collector, extraction, deployment or admission entry.
Its two new source/test files expand the prospective repeat union to 268 and
the separate reporting bundle to seven files. None is added retrospectively
to the final run's 211-file qualification. No reporting root has been deployed.

The schema validator requires the exact original qualification, registration,
runtime, baseline CSV and stopped metadata bytes, checked against their pinned
hashes, not a caller-supplied success flag. It checks the original source/input/
eight-producer maps, all 178 original and four stopped result hashes, fixed89
order, official resource/deadline numeric types, status/reward compatibility,
accounting and generation counts, null phases and measured/not-run aggregates.
Only the exact supporting-file inventory, corroborated deadline/accounting
absences and current separate reporting-source map are permitted. The five
metadata inputs have a 64 MiB parser window, not a benchmark execution limit.

The archive contract retains frozen-root paths and adds the seven reporting
files under `reporting/stage2/`, outside the execution-source namespace.
Every supporting file is hash-verified, including starts, results, traces,
accounting and actual deadline files. Each recorded evidence directory must
be present, including empty directories; its exact children must match. A
proven absent path must have neither an archive entry nor any descendant.
Additional private logs are allowed only below registered trial directories,
outside those exact inventories. They are streamed and hashed, never returned,
parsed as model exchanges, extracted or published. No exclusion may remove a
required binding. This is not proof of a full runtime restore.

The distinct receipt binds the amended snapshot, reporting map and absence set
alongside the compressed checksum and source counts. Path verification requires
an owned, private, regular single-link file, checks its identity before/after
reading and rejects replacement. A substituted FIFO is opened nonblocking and
rejected without waiting for a writer. The same verifier can consume exactly one
declared stream frame; it leaves transport framing and the final authenticated
operator commitment to the future caller. A pipe, saved receipt or regular
stream is not proof of network identity or an off-server location.

Verification rejects unsafe or duplicate paths, credentials, links, special
files, global/sparse extensions, changed or missing bindings, hidden data after
the tar end marker, incomplete end blocks and damaged gzip trailers. Standard
PAX path/timestamp and GNU long-name metadata are supported; extension headers
are bounded before their bodies are read. Ordinary file payloads have no new
size ceiling and use bounded-buffer reads. Exact source counts are checked.

Both validation results explicitly retain `completed_final_audit:false` and
`paid_launch_ready:false`; archive verification additionally records
`off_server_location_verified:false` and `full_runtime_restore_exercised:false`.
Archive bytes corroborate the report's bindings, not a fresh native service,
phase, lineage, image or cleanup observation. The actual operator/native
handoff still must perform the separately bound fresh audit and compare it to
the saved snapshot, read the existing off-server archive, verify its final
commitment and recheck native evidence under every ancestor lock. The unchanged
predecessor readers do not yet consume this schema and must not be bypassed.

All 47 new local tests passed with actual temporary tar/gzip bytes and synthetic
89-attempt files produced through the real phase/accounting readers. Native
observations are mocked. Coverage includes byte/absence/inventory drift,
private file replacement, malformed archives, chunked stream parity, standard
PAX metadata, parser windows and 105 synthetic physical requests with 104
unknown costs and missing timing retained. No provider was called. An initial
test fixture used a collection timestamp before its synthetic future trace
epoch; the fixture was corrected without relaxing production time checks.
Review added the nonblocking regular-file check and an actual FIFO regression.

Trusted invocation, the exclusive one-time native archive writer/transfer,
allowlisted public export and actual predecessor-handoff integration are still
required. They must be completed and source-bound before the reporting bundle
is frozen or any completed-final route is invoked. No actual native completed
audit, archive, export or repeat authority is claimed by this checkpoint.
