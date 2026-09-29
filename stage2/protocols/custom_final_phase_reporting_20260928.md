# C0-NC final phase-reporting amendment

## Scope and dated evidence

This is a separate reporting amendment for the frozen C0-NC
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
has not been created. Trusted deployment/invocation is implemented locally in
the separate launcher described below, but has not been exercised natively.

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

The separately bound launcher is now locally implemented. One absence-aware
streamed backup, allowlisted export and real operator/native handoff integration
remain unfinished. The
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

## Offline separate reporting launcher

`no_cutoff_final_reporting.py` supplies the fixed Mac-side `deploy(commit)`,
`inspect_deployment(commit)` and `collect(commit)` operations. There is no CLI,
caller root, callback, saved-proof path, archive writer, exporter, qualification
or paid dispatch. These entries have not been invoked on the VPS. The full
amended backup/export/handoff route must still be completed before native use;
an active or unknown final remains a hard refusal.

The launcher and its tests expand the reporting bundle to nine files and the
prospective repeat union to 270. These are current reporting/repeat bindings,
not retroactive additions to the final's 211-source qualification. The original
collectors, execution sources and predecessor readers remain unchanged.

The operator rereads the five pinned metadata anchors, exact copied inputs
and all eight native qualification producers. It derives 229 native file
bindings from those real originals, including the frozen execution sources,
Python archive and historical metadata. All nine current reporting files,
unchanged trace helper and unchanged pinned SSH source must match the full
requested commit, current HEAD and fetched origin/main. Files and HEAD are
reread across the operation; a saved source map is not a shortcut. The existing
SSH destination, identity, host-key checks and options are preserved. Only the
interpreter tail is replaced with the original final `.venv` Python, `-I -B`
and the exact credential-free reporting environment. No key or private input
is included in the reporting deployment payload.

The native bootstrap is standard-library-only until it has checked successful
inactive/dead service state, no persistent stop, every original bound byte and
the separate reporting inventory. An absent reporting bytecode prefix prevents
stale local bytecode use. Protected regular single-link owned files are opened
without following links and nonblocking; file identity and bytes are checked
before/after reads. The fixed separate reporting directory is created
exclusively with private directories/files. Only the nine source/document/test
files are copied, with durable writes. An existing complete or partial root is
never overwritten, deleted, resumed or automatically retried. Inspection only
checks existing bytes; it cannot create a missing deployment. Returned
`operator_commit` identifies the bound operator source revision, not an
installed Git checkout or a new benchmark execution commit.

Collection imports only the separately bound report/archive and original
execution helpers, then calls the actual `collect()` entry. That collector
still performs real lineage authentication before its ancestor locks and all
original coverage/runtime/image/official-limit/trace/accounting/resource checks.
The launcher does not reacquire those locks or accept a saved collector flag.
It validates the explicit amended schema against actual pinned native metadata
and rereads supporting bytes, exact inventories, genuine absences, all 182
historical result hashes and all reporting sources after the last native
service observation. Loaded project-module locations are checked. Incidental
diagnostics are suppressed; only validated metadata is returned, with no raw
exception text. The Mac validates again and rereads its original bindings.
Connection uncertainty is an inspection requirement, not permission to retry
deployment or stop/replay a native study. The 300-second SSH operation timeout
and metadata parser windows are reporting transport bounds, not task limits.

All 37 new local tests passed. Tests use real temporary files, directory and
hash guards, synthetic source payloads, local FIFOs and mocked native context,
SSH, service and collector observations. They do not execute a native audit or
establish Linux/SSH compatibility. Coverage includes exclusive/partial writes,
pre-import active/stop refusal, exact source/commit/environment bindings,
links/privacy/FIFOs, incomplete or malformed replies, no automatic retry and
post-observation evidence mutation. Two test-edit placement mistakes were
corrected without weakening production checks. Review moved final evidence
rereads after the last service observation and added its regression test.

No reporting directory, completed-final audit, archive, export, handoff or
repeat attempt has been produced. The one-time absence-aware archive writer,
public exporter and actual operator/native amended predecessor integration
remain required. The old readers still fail closed; this launcher or a receipt
flag cannot grant successor admission. Trusted repeat service operations,
native compatibility, repeat exporter and completed-Terminus successor reader
also remain unfinished.

## Offline one-time archive producer and Mac receiver

`no_cutoff_final_backup.py` and `no_cutoff_final_backup_operator.py` now implement
the separate one-shot producer and fixed Mac receiver. They have not been
invoked on the VPS. Their two test modules join the reporting bundle, bringing
it to 13 files and the prospective repeat union to 274. These are current
reporting/repeat bindings, not changes to the frozen execution qualification.
The public exporter and actual amended predecessor/handoff integration must
still be completed and frozen before any native reporting operation.

The only operator entry is `backup(full_commit)`, with no caller root, callback,
saved report, supplied archive or CLI. It uses the original byte-pinned SSH
route and the separate launcher's exact committed-source checks and isolated
credential-free interpreter. A read-only deployment inspection must first
confirm the successful inactive final service. The fixed private Mac
destination is `.runtime/netcup/custom-no-cutoff-final89-c0-nc-20260928`.
Any existing or partial destination refuses repetition before SSH dispatch.
The buffered JSON launcher explicitly refuses the binary backup operation.

The native `stream()` entry requires its actual separately deployed module and
reporting context. It invokes the real amended completed audit, validates its
schema against the five original byte anchors and performs fresh original
lineage authentication before acquiring the unchanged full ancestor locks.
Under those locks it repeats qualification, registration, coverage, loaded
source, owned-resource, service and stop checks. Supporting bytes, exact
inventories, genuine absences and all 182 historical result hashes are reread
after the last native observation. No audit is invoked recursively under
those locks and no saved audit flag substitutes for these operations.

Only the separate reporting root receives the exclusive private durable
`.backup-intent.json`, `.backup-result.json` or `.backup-failure.json` records.
Any retained record forbids another producer attempt. The reporting bootstrap
permits these exact private state names for later inspection; they are not
sources, off-server proof or dispatch authority. Existing source trees and
results are never overwritten. No archive is created on the server.

The producer streams one tar/gzip archive through bounded binary frames.
It hashes actual source bytes before and while archiving, checks file identity,
preserves exact empty directories and excludes credential paths. Additional
private logs are copied only under registered trial directories; their payloads
are never parsed or returned. Required evidence cannot be excluded. Proven
absences remain absent, including descendants, rather than synthetic deadline
files. All source/evidence/inventory checks run again after streaming. Only
then can the native terminal receipt and final marker be emitted. A transport
failure or mutation leaves private evidence and an exception-type-only failure
record, without a retry, deletion or study restart.

The Mac exclusively writes `intent.json`, exact raw `snapshot.json` bytes and
one `evidence.tar.gz`. It requires the exact receipt, final marker, clean EOF
and successful SSH exit. It then rereads that same archive with the strict
member/hash/inventory/absence verifier, rechecks current operator inputs and
retained file hashes, and only then writes `backup.json`. Python numeric types
and nulls are preserved. A failed or uncertain transfer retains partial files
and `failure.json`; it cannot automatically create another backup. The
900-second whole-transfer bound is a reporting transport window, not a task
deadline or model-request limit. Cleanup may terminate only the owned SSH
client, never a native service or benchmark process.

The new backup record deliberately differs from the old receipt schema. Its
successful future Mac execution can assert `off_server_backup_verified:true`,
but `paid_launch_ready:false`, `archive_export_and_handoff_integrated:false`
and `full_runtime_restore_exercised:false` remain explicit. The native stream
record does not claim an off-server copy. Neither record is a live successor
witness, and unchanged predecessor readers still refuse the amended route.

Tests exercise real temporary private files, synthetic 89-row phase/accounting
evidence, tar/gzip bytes, competing local locks and harmless local subprocess
pipes. Native service, context, Docker, SSH and lineage observations are mocked.
Coverage includes true missing phases, exclusivity, partial transfers, unknown
costs, source/result/inventory mutation, malformed framing, private-file drift,
raw numeric-byte preservation and final commitment refusal. These tests do not
establish native compatibility, a completed audit, a real backup or permission
to start a repeat. Allowlisted public export, actual operator/native amended
handoff integration and trusted repeat service operations remain unfinished.

## Separate allowlisted public exporter checkpoint, 29 September

`no_cutoff_final_export.py` now implements the fixed Mac `export(full_commit)`
and read-only `verify_export(full_commit)` entries. This is local preparation,
not an actual native audit, backup, public result export or repeat handoff.
The exporter and its tests join the reporting bundle, now 15 files, and the
prospective repeat union, now 276 files. Old collectors and predecessor readers
remain unchanged. The actual amended operator capture/native handoff integration
is still required before the reporting/backup/export route may be invoked.

Both entries require current committed source bytes matching HEAD and fetched
origin/main, the exact private completed backup inventory and the four existing
public qualification/registration/lineage/policy files. Their hashes are pinned
for this reporting route, not retrospectively added to native qualification.
The retained backup intent and receipt must match exact raw snapshot bytes and
the current reporting bundle. Actual Git bytes from the retained operator commit
are checked; later result/documentation commits may advance HEAD only while the
archived reporting source bytes remain unchanged.

The actual separate reporting launcher performs a fresh native completed audit.
Its inactive-service, lineage-before-lock, under-lock source/runtime/resource,
supporting-file/inventory/absence and 182 historical-result checks remain required.
Only collection time may differ from the retained snapshot, and the fresh audit
cannot predate it. The exporter then rereads the ONE existing private archive
with the strict member/hash/inventory/absence verifier. Saved audit, backup or
export flags never replace these operations. Actual local metadata, source,
prerequisite and archive bytes are reread after the native audit and again before
the export commitment. No archive is created, extracted or replaced.

The only public outputs are `summary.json`, `trials.json` and `trials.csv` under
the fixed `results/custom-no-cutoff-final-20260928/c0-nc` directory. They use
explicit metadata allowlists. No raw result, exception text, exchange, solution
or private inventory is projected. JSON retains nulls and Python numeric types;
CSV uses empty cells for nulls with explicit phase-observation labels. Actual
official allowances remain separate from measured durations. Full89,
development20 and remaining69 retain measured/not-run timing denominators and
measured subtotals. Unknown costs remain unknown; missing outcomes stay distinct
from verified zero rewards. Original 52/89 and 44/89 baselines remain labelled,
and no recovery outcome is included in this original one-attempt final89.

Private export intent/result/failure records use the separate fixed Mac directory
`.runtime/netcup/custom-no-cutoff-final89-export-20260928`, leaving the four-file
backup inventory untouched. Writes are exclusive and durable. Any existing or
partial export/state refuses automatic repetition; failures retain partial files
and exception type only. Read-only verification repeats the actual native audit
and archive read and regenerates expected public bytes for exact comparison.
Neither its return value nor a public file grants paid admission. Whole-route
integration and full-runtime-restore claims remain false.

Tests use synthetic89 evidence, real temporary private files and tar/gzip bytes,
with mocked native audit, SSH and Git observations. They cover null versus zero,
official allowances, 105 physical requests/104 unknown costs, exact row and
column allowlists, stale audits, changed bytes, privacy/symlinks/FIFOs, duplicate
JSON fields, partial writes, no replay and fresh read-only verification. They do
not establish native compatibility, a real completed audit, off-server archive
or benchmark results. No production entry has been invoked.

## Explicit amended predecessor handoff, 29 September

The 03:21:46 UTC metadata observation found all 89 results retained, with 50
passes, 36 verified zeros and the same three setup-only missing verifier
outcomes. The service was inactive/dead, PID 0, exit 0; all 211 execution
sources matched, all 89 results recorded model revocation and no stop was
present. This is completed-run metadata, not the completed audit or backup.

`matched_repeat_amended_predecessor.py` and
`matched_repeat_amended_handoff.py` implement the distinct amended route.
Their two test modules expand the reporting bundle to 19 files and prospective
repeat union to 280. The actual session and inspection connection now select
this route. Old predecessor, handoff, stream and completed collectors remain
unchanged and fail closed for the amended schema. Frozen execution is unchanged.

Fixed Mac capture requires the full current revision, fetched origin/main and
actual committed bytes for every current repeat/reporting consumer. It calls
the export verifier's internal actual capture, never accepts its public return
as authority, and thus performs a fresh completed native audit, a strict reread
of the ONE retained archive and exact deterministic public/export-state checks.
All three public result files must already be committed on main. Missing or
partial backup/export inventories refuse a connection before starting a service.
The retained backup revision binds its reporting bundle; later current repeat
code is separately bound, not retroactively added to the historical archive.

The source-bound Mac sender streams exact retained UTF-8 snapshot/backup bytes
and that existing private archive. It uses protected single-link file reads,
then rereads current source, private inputs, public export, private state and
archive bytes before its final commitment. No archive is recreated, extracted
or copied to a second local pathname. The distinct envelope cannot select the
old schema. The old framing helper is unchanged; the amended strict archive
verifier checks the stream, all directory inventories and actual absences,
gzip/tar termination, hashes and the final operator commitment plus EOF.

Native authentication checks actual copied qualification bytes, current repeat
sources, deterministic public projections and all five exact native anchors.
It requires the real separate reporting tree, its exact source inventory and
both successful native backup producer records, including the same receipt.
A failure marker, partial deployment or changed state refuses authentication.
Those records alone still do not prove an off-server copy. The pinned SSH
connection and exact native Unix peer/PID/cwd checks remain necessary; a regular
file, pipe descriptor or saved JSON is not peer identity or admission.

After the complete committed stream, the native consumer invokes the actual
separate reporter through its source-bound bootstrap in the original final
isolated interpreter, with the exact credential-free environment. Actual
lineage authentication and audit locks run BEFORE the session's outer locks.
Only collection time may differ, and the fresh audit cannot predate the retained
snapshot. Final source/input/supporting/result/inventory/absence and all 182
historical-result reads follow the last native service observation.

The native witness cannot be constructed from saved metadata, serialised or
moved across processes, threads or async tasks. The real session consumes it in
that same task before taking all ancestor locks. Under-lock recheck reads actual
bytes, separate reporting state, exact inventories and true absences without a
collector, archive transfer or recursive lock acquisition. Failed rechecks
permanently invalidate the witness/session. Session ordering leaves the amended
evidence reread after other native observations. Independent original178,
current library/constructor/host checks and real native qualification remain
mandatory. No score, request count or unknown-cost gate is added.

Local tests use actual synthetic89 evidence, private files, tar/gzip bytes,
pipes, Unix sockets and competing locks. The actual sender, amended archive
reader and real same-task session are exercised together. Native host/audit,
Docker, SSH and Git observations are mocked; these tests are not native
compatibility, completed audit, off-server backup or benchmark evidence.
No native reporting deployment, collector, archive, public export, handoff,
repeat build/qualification/dispatch or recovery attempt has occurred here.

Native reporting must use the exact committed source freeze after final local
gates. Trusted qualify/paid service operations, actual native
compatibility, repeat exporter and the completed-Terminus OpenHands successor
reader remain separate work. Recovery sequencing/reporting approval is pending;
original setup failures cannot be replaced or silently merged with new attempts.
