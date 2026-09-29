# Stage 2 execution status

## Latest: recovery-only locked prerequisite session implemented locally

The new [locked session](protocols/custom_setup_recovery_session_20260929.md)
consumes the actual recovery handoff before taking the complete 34-lock chain:
33 existing ancestor locks and the new recovery matrix lock, in the original
order. It then calls the real current C0-NC host/library reader under those
locks. Source/private raw bytes, identities and loaded origins are checked on
entry, during rechecks and at normal exit. Both live handles are invalidated
before unlocking on success, failure, cancellation or partial acquisition.
Nonblocking contention, replacement or loss of a held lock refuses; lock files
are never created, written, replaced or chmodded by this component.

This is LOCAL implementation, not an actual native session or qualification.
It accepts no saved witness, root override, factory or authentication callback,
and exposes no registration, qualification-verification or paid-dispatch entry.
Actual pinned SSH/service wiring and genuine native image/producer verification
remain required. Recovery remains 0/3 started; both baseline repeats remain
unstarted. The source union is 283 files, adding only the session, its tests and
protocol. Only the policy source inventory/test list changes; all earlier
recovery components, archived 35-file reporter and original evidence are intact.

All 215 affected checks passed, including 36 new tests with real temporary
files, pipes, competing locks and async cancellation. Native audits/services/host/library observations
are mocked. The isolated import child refuses credential reads, writes,
processes and networking. Initial fixture errors concerned the local tokenizer
cache path and an OS-level symlink refusal; both were corrected without
relaxing production checks. Review ensured partial lock acquisition also
invalidates the witness before any descriptor is released.

A wider development run correctly refused a changed shared temporary-parent
identity while another local suite created files there. The fixture now uses
an owned stable parent, and wider suites use separate temporary directories.
The other two local draft gates were interrupted before that fixture correction;
they are not passed checks. No native process was signalled or guard relaxed.
An initial `/tmp` isolation directory inherited group 0 instead of the local
process's group 20, causing the ownership checks to refuse. The final harness
uses separate owned directories under the user's normal temporary location;
all 36 new tests passed there before restarting the wider gates. No source or
ownership check was weakened to accommodate that harness error.

Final local gates passed all 607 recovery regressions (283 bindings, 187 final
loaded project modules) and all 1,675 combined broader regressions (326 source
bindings, 245 final loaded modules), with zero skips/errors/failures. Both
checked source bytes before discovery, after discovery and after execution.
Full discovery ran 2,842 tests: 2,841 passed and one pre-existing skip, with
unchanged hashes over 424 Python files at all three checkpoints. These are
local/synthetic checks, not native qualification or paid evidence; mocked
lifecycle completion output does not add study outcomes.

The only native operation was the existing read-only progress inspector at
**19:39:50 UTC on 29 September**: **89/89 complete, 50 passed, 36 verified
failures, 3 missing verifier outcomes**, no active/partial task and all 211
source bytes matching. No collector, real archive read, installation, native
session, image build, qualification, registration, recovery attempt or provider
request occurred. Actual new-root absence, trusted service/scored integration,
durable setup observations, six genuine native cases, one-shot dispatcher and
separate completed reporting/ONE backup/export remain unfinished. Keep the VPS.

## Earlier checkpoint: recovery-specific current host and library reader

The separate [host/library component](protocols/custom_setup_recovery_runtime_20260929.md)
now requires a live original-evidence witness and actual C0-NC host, dependency,
Python archive, dataset, all 89 official configurations and three task-image
bindings. Its two isolated constructor-only children compare current original
and recovery site-packages bytes, versions and C0-NC controls. Actual libraries,
inputs and sources are reread after the final native observations. A failure
invalidates the witness. No saved description is admission, and the future
session must still hold the full ancestor locks after real authentication.

This is LOCAL implementation, not a native inspection or qualification. The
original backup excluded its virtual environment: current parity would not
prove historical installed bytes. The prospective recovery union is now 280
files, adding only the new runtime, stdlib library producer, tests and protocol.
The policy AST changes only its source inventory/test list. The original 211
retain only the prior local scored-runner hooks; archived 35 reporter files, diagnosis,
observer, handoff, original preparation/lifecycle and published evidence remain
unchanged. All 179 affected local checks passed, including 47 new tests.

Final local gates passed all 571 recovery regressions (280 bindings, 185 final
loaded project modules) and all 1,639 combined broader regressions (323 source
bindings, 243 final loaded modules), with zero skips/errors/failures. Both
checked source bytes before discovery, after discovery and after execution.
Full discovery ran 2,806 tests: 2,805 passed and one pre-existing skip, with
unchanged hashes over 422 Python files at all three checkpoints. All 12
repository tests passed. These are local/synthetic checks, not native or paid
evidence; mocked lifecycle completion output does not add study outcomes.

The only native operation was the existing read-only inspector at **18:36:19 UTC
on 29 September**: **89/89 complete, 50 passed, 36 verified failures, 3 missing verifier
outcomes**, no active/partial task, all 211 sources matching, all 89 revoked and no
stop. Recovery remains **0/3 started**; both baseline repeats are unstarted.
No archive read/recreation, collector, new native root/service/build/rehearsal,
qualification, registration, provider request or recovery attempt occurred.
Actual new-root absence, trusted service/live locked session, new image/native
qualification, durable observer/scored integration, dispatcher and separate
completed report/ONE backup/export are still required. The VPS remains needed.

## Earlier checkpoint: recovery-specific original-evidence handoff

The separate [capture and handoff component](protocols/custom_setup_recovery_handoff_20260929.md)
now provides the recovery-only route for a fresh original audit and strict
authentication of the SAME retained archive. It checks committed operator and
actual native source/input/public bytes, exact raw snapshot/backup metadata,
all 89 original outcomes, genuine absences and all 182 historical result hashes.
The native reader audits before the future session's ancestor locks; its
process/thread/async-task-bound witness permits only nonrecursive rereads under
those locks. A failed recheck or ownership violation invalidates it permanently.
The actual pinned SSH/service and locked host scope are still required: this
local component has not performed a real handoff or granted paid admission.

The current recovery source union is 276 files. The new consumers and unchanged
archived-reporting dependencies are bound for current verification only, never
added retroactively to the original 211 or archived 35. The policy change only
extends that prospective inventory and its test list; the three-task plan,
gateway behaviour, setup observer and original preparation/lifecycle remain
unchanged. No original reporter or historical handoff source was edited.

The only native operation was the permitted read-only inspector at **17:36:33 UTC
on 29 September**: original final89 **89/89 complete, 50 passed, 36 verified
failures, 3 missing verifier outcomes**, no active/partial task, all 211 sources
matching, all 89 revoked and no stop. Recovery remains **0/3 started** and both
baseline repeats remain unstarted. No archive was read/recreated or new native
operation attempted by this implementation. Actual C0-NC host/runtime/library
identity, trusted service/locked session, native qualification, scored observer
durability, dispatcher and separate completed reporting/backup/export remain
unfinished. The VPS and hourly reports remain needed.

All 38 new handoff tests and 94 related checks passed locally. Final gates
passed all 524 recovery regressions (276 bindings, 182 final loaded modules)
and all 1,253 broader guarded regressions (323 bindings, 205 final loaded
modules), with zero skips/errors/failures. Full discovery ran 2,759 tests:
2,758 passed and one pre-existing skip; before/discovery/after hashes covered
419 Python files. All 12 repository tests passed. These use synthetic archives,
local pipes and mocked native observations, not native qualification or study
outcomes. Review added final manifest rereads and strict private-file group/mode
checks. The original 35 reporter files, seven diagnosis controls, three observer
controls and five published metadata files remain byte-identical.

## Earlier checkpoint: recovery policy and gateway implemented locally

The separate [policy and gateway component](protocols/custom_setup_recovery_gateway_20260929.md)
now checks the fixed three-task plan, exact original qualification/manifest
copies, all 89 original result hashes and retained audit/archive/export bindings.
Seven recovery-only private inputs are reread with raw-byte and file-identity
checks. Any gateway input refusal is latched; restoring metadata cannot revive
that gateway. Shared retry, unknown-cost accounting, model identity, official
deadline, revocation and exclusive attempt directories remain unchanged.

The qualification contract requires the original C0-NC controls, actual image
producers and six real native preparation/lifecycle cases. It does not run
them or authenticate saved metadata as a live witness. The prospective source
inventory is 236 files, preserving all 211 original files except the already
permitted local scored-runner hooks. Previously unlisted regression/helper
bytes are bound for current verification only. No new inherited-source edit
was made. All 38 new tests and 147 affected checks passed with fake providers
and synthetic private inputs. The 486-test recovery regression set passed with
zero skips/errors/failures and 236 source bindings/163 final loaded modules.
All 1,215 broader guarded regressions passed with 319 bindings/202 final loaded
modules. Full discovery ran 2,721 tests: 2,720 passed, one pre-existing skip,
with unchanged hashes over 416 Python files before/discovery/after execution.
All 12 repository tests passed. These are local checks, not native qualification.

The only native operation was the existing read-only inspector at **16:44:12 UTC
on 29 September**: original final89 **89/89 complete, 50 passed, 36 verified
failures, 3 missing verifier outcomes**, no active/partial task, all 211 sources
matching, all 89 revoked, no stop. Recovery remains **0/3 started**; both
baseline repeats remain unstarted. The real original-audit/same-archive live
handoff, host/runtime/service, actual qualification, scoped scored hook,
sequential dispatcher and completed recovery audit/backup/export remain
unfinished. No recovery root, service, registration, provider request or paid
attempt was created. Original evidence and archived reporting bytes are intact.

## Earlier checkpoint: recovery-only setup observer implemented locally

The separate [setup observation component](protocols/custom_setup_recovery_instrumentation_20260929.md)
now wraps the exact original preparation function without changing its command,
180-second command window, root context, exception/cancellation behaviour or
the shared lifecycle. It records only stage, allowlisted error class, actually
returned integer code, elapsed time and returned-text byte counts/hashes.
Nonzero commands and execution exceptions are distinguished without inventing
a package, network or SSH cause. Unknowns remain null; incomplete diagnostics
cannot become a complete observation after a source refusal is restored.

All 43 targeted tests and 134 affected checks passed locally. These include
the actual unchanged shared lifecycle with synthetic environments and an
isolated no-write/no-process/no-network import/execution check. Final discovery
passed 2,682 of 2,683 tests with one pre-existing skip and unchanged hashes over
413 Python files before/discovery/after execution. All 1,177 guarded regressions
passed with zero skips/errors/failures, 311 stage2 bindings and 199 loaded
project modules at the final reread. The 12 repository tests passed. These are not
native qualification or provider measurements. The real recovery policy,
gateway, authenticated host/runtime/service, qualification, scoped dispatcher
and separate reporting route remain unfinished; this observer is not yet wired
into the scored runner and supplies no admission or durable replay protection.

The latest read-only native observation at **15:36:40 UTC on 29 September**
still found original Custom C0-NC final89 complete: **89/89, 50 passes, 36 verified
failures, 3 setup-only missing verifier outcomes**, no active/partial task,
all 211 source bytes matching, all 89 revoked and no stop. Recovery is **0/3
started** and both baseline repeats remain unstarted. The original archive,
35-file reporter, published diagnosis/schedule and every original outcome are
unchanged. No native recovery installation, qualification or command was run.

## Earlier checkpoint: separate three-task recovery diagnosis and fixed plan

The original final89 remains audited, privately backed up and publicly exported:
50 passes, 36 verified failures and three setup-only missing outcomes. A fresh
read-only observation at 14:41:09 UTC on 29 September found 89/89 complete, no
active/partial task, all 211 sources matching, all 89 revoked and no stop.

Inspection of the SAME retained archive narrows original tasks 63-65 to failure
inside environment preparation before its return, hence before agent setup.
The pinned original code stores `environment_preparation` before `agent.setup`;
that field is absent in all three exact original results. Their command output,
exit code and exception stack were not retained. A package/mirror/network/SSH
cause is not established, and no speculative infrastructure change is applied.

The [separate recovery amendment](protocols/custom_setup_recovery_20260929.md)
and deterministic three-task plan retain the original C0-NC agent, model,
official limits and preparation command, with fresh recovery IDs and separate
outcomes. The new read-only diagnosis reader actually verifies the existing
archive and committed public bytes, but grants no native scope or admission.
Current diagnosis sources are not added retrospectively to the archived reporter.
Real setup diagnostics, recovery scope/service/gateway/qualification/dispatch
and separate reporting still need implementation before any recovery launch.
No recovery or baseline repeat has begun; fixed baseline schedules are unchanged.

The committed reader `7656915c3d50b97df1964f2802b9ddf67cca16ea` actually
completed the local archive diagnosis at 15:22:15 UTC. Its allowlisted
[diagnosis and fixed schedule](results/custom-no-cutoff-recovery-20260929/README.md)
are published separately. Final local gates passed: 2,639 of 2,640 discovery
tests, one pre-existing skip, and all 1,134 guarded regressions with no skips.
These checks are not native qualification or recovery results; 0/3 have started.

## Latest: original final89 audit, private backup and public export complete

The version-4 reporter at `a74e0dd053fed70a1ede3eef23e0ccdb6db6fb09`
was installed exclusively at 14:12:58 UTC on 29 September. Its read-only actual
inventory preflight passed at 14:14:05 UTC. The one new backup ran from 14:14:51
to 14:21:35 UTC and passed fresh native audit, lineage/ancestor-lock checks,
streaming, final evidence rereads and actual Mac archive verification.

The ONE retained private archive has SHA256
`7e53dd3eb45bec457f81d59b694fd171a949fbf123f02baa14f4158d9634a400`,
105,731,876 compressed bytes and 27,159 files. All 89 results, 26,640 bound files
and 3 true absences were verified. A full runtime restore was not exercised.
No source permission, original outcome or earlier failed state was changed;
no archive is recreated. The old reporters and first successful v3 audit remain.

The allowlisted export completed at 14:26:29 UTC after another actual fresh
native audit and rereading that same archive. The [summary](results/custom-no-cutoff-final-20260928/c0-nc/summary.json),
[89 rows](results/custom-no-cutoff-final-20260928/c0-nc/trials.json) and
[CSV](results/custom-no-cutoff-final-20260928/c0-nc/trials.csv) preserve **50 passes,
36 verified zero-score failures and 3 setup-only missing verifier outcomes**.
Development20 is 15/20; remaining69 is 35 passes/31 failures/3 missing. Unknown
cost and unexecuted phase durations remain null, not zero. No recovery is merged.

The reporting/backup/export unit is complete, not the whole capstone or repeat
admission. The approved separate recovery for tasks 63-65 still needs diagnosis,
amendment and qualification. Native baseline repeat prerequisites also remain
unfinished. No recovery or
baseline attempt has started. Continue routine authorised work without repeated
approval prompts, retain fixed schedules/order and all evidence, and keep the
VPS and explicit hourly notifications active. Older sections are historical.

## Latest: full audit passed; protected-log backup correction in progress

The source-bound version-3 native audit at `7bfb84d` completed successfully at
13:18:45.897886 UTC on 29 September. All final launcher/schema/evidence rereads
passed and the exact private snapshot was retained. The original 89 attempts
are now audited: **50 passes, 36 verified zero-score failures and three setup-only
missing verifier outcomes**. Development20 is 15 passes/5 failures; remaining69
is 35 passes/31 failures/3 missing outcomes. These are separately measured final
attempts, not inherited validation scores or merged recovery attempts.

The one backup ran from 13:20:22 to 13:24:52 UTC and returned ValueError. Its
exact historical failure stage was not retained. Only private intent/failure
exist; no archive, snapshot or verified backup record was created. Read-only
checks found no remaining study/reporting process or held/waiting ancestor lock,
all 237 native and 21/28/32 installed reporter bindings intact, and no native
backup state. A source-bound read-only inventory check reproduced a current
permission refusal on extra agent/verifier log directories, not required audit
evidence. Metadata showed root:root0777 log roots behind exact0700 boundaries;
required trial files remain0600. No native permission or evidence was changed.

The explicit [extra-log archive amendment](protocols/custom_final_archive_logs_20260929.md)
is implemented locally for only those registered extra payloads, retaining
owner/group, canonical private ancestors, ACL/link checks, exact narrow modes,
before/after identities and hashes, and unchanged strict required-evidence rules.
The prospective r4 reporting root and new protected-logs backup destination
preserve the old installations, successful audit and failed backup. The current
successor connection uses the same new destination without a legacy fallback;
the old predecessor reader remains unchanged. Final discovery ran 2,597 tests:
2,596 passed and one pre-existing skip. All 1,091 guarded regressions passed with
zero skips/errors/failures, before/discovery/after checks over 303 stage2 bindings
(299 prospective sources plus four metadata files), and 193 loaded project
modules at completion. All 27 new permission tests, an earlier 335 affected
checks, the corrected 39 connection tests and all 12 repository tests passed.
The initial wider runs exposed the stale successor destination and were retained
as failed; correcting that actual consumer did not relax any evidence check.
These are local/synthetic checks, not another native audit or backup. No new
installation or backup invocation has occurred for this correction.

No final public export, recovery or baseline repeat exists. The three separately
approved recovery attempts still require a verified original backup and their
own diagnosis/amendment/qualification. Fixed baseline schedules/order remain.
Routine in-scope authority is valid without repeated approval prompts; it does
not permit evidence replacement, replay, payment/topup or VPS cancellation.
Keep the VPS and hourly notifications. Older checkpoints below are historical.

## Latest: version-2 installed; environment correction locally verified

The approved version-2 installation at 2fbdc938 succeeded at 12:34:30 UTC on
29 September. Its single audit failed at 12:35:39 UTC at the exact environment
check, after reader preload and before lineage authentication or the result
audit. It was not a timeout. No completed snapshot, backup or export exists.
The 28-file version-2 and original 21-file installations, and both failed-audit
states, remain unchanged. Read-only checks verified the audit process absent
and all 234 native, 28 version-2 and 21 original reporter bytes intact.

The [environment amendment](protocols/custom_final_reporting_environment_20260929.md)
addresses observed import-time dotenv loading and tokenizer-cache assignment.
Version 3 disables dotenv before imports, sets the fixed existing cache path,
retains exact environment equality and latches credential-read/environment
violations across the launcher and producer. Three current library-control
sources are separately hashed, archived and reread. This is not a full library
inventory or historical installed-byte proof, and the original 211-file
qualification is unchanged. No frozen source, permission, library or result is
edited. The proposed new root ends in `20260929-r3`; it is not installed yet.

The user has authorised needed routine in-scope corrections without further
approval prompts. One new protected installation/audit can follow final local
gates, source binding and push. Existing/partial roots and audit states remain
terminal; there is no automatic retry loop. Final discovery ran 2,566 tests:
2,565 passed and one pre-existing skip. All 1,060 guarded regressions passed
without skips/errors/failures, with 300 stage2 bindings (296 prospective sources
plus four metadata files) and 191 loaded project modules at the final check.
The stable focused 127-test run and all 12 repository tests passed too. Tests
remain local/synthetic, not native audit or benchmark evidence.

Last normal progress observation: 11:51:02 UTC, 89/89 complete, 50 passes,
36 verified zero-score failures, three setup-only missing verifier outcomes,
no active or partial task. These remain preliminary, not audited final scores.
Recovery63-65 and both baseline repeats have not started. Keep the VPS and
explicit hourly notifications active. Earlier checkpoints are historical.

## Latest: version-2 reporting correction prepared locally, 29 September 2026

The explicit [source-inventory amendment](protocols/custom_final_reporting_inventory_20260929.md)
binds the five missing helpers for CURRENT reporting only, without changing the
original 211-file qualification. The audit, strict archive, one-time backup,
public projection and live handoff require the same separate dependency contract.
Static transitive-import checks run before native imports/writes; actual loaded
origins and bytes are still checked before the long audit and at final rereads.
No guard is removed and no historical installed-byte attestation is invented.

Final local discovery ran 2,535 tests: 2,534 passed and one pre-existing skip.
All 1,029 guarded regressions passed without skips/errors/failures, including
before/discovery/after checks over 296 stage2 bindings (292 prospective sources
plus four retained metadata files) and 188 loaded project modules. All 12
repository tests passed. These use local files/pipes and synthetic native
observations; they are not native audit, qualification or benchmark evidence.

The candidate targets a NEW exclusive 28-file reporting root,
`/opt/uts-capstone-custom-no-cutoff-final-reporting-20260929-r2`, with 234 native
bindings (the original 229 plus five current-only helpers). The existing 21-file
ea543e4 installation, frozen execution and prior failures remain untouched.
Reporting audit connections use the metadata-only 1,800-second transport;
backup and handoff windows are explicitly 2,700 and 4,500 seconds. These are
reporting bounds, not task deadlines. Backup/export now check the real private
Netcup boundary and owned non-writable parents, with identity rereads and no chmod.

The new one-shot Mac audit destination is
`.runtime/netcup/custom-no-cutoff-final89-inventory-audit-20260929`.
It cannot reuse the earlier failed audit directory or accept a saved internal
result. Late local validation failures retain actual transport diagnostics and
their local failure stage. Existing or partial state still forbids repetition.

This is local implementation, not installation or native audit success. The
next native unit needs explicit authority for ONE new separate installation and
ONE fresh audit; consumed earlier attempts are not an automatic retry loop.
There is no completed audit, final backup/export, recovery or baseline repeat.
Last observed preliminary progress is 08:04:31 UTC: 89/89 complete, 50 passes,
36 verified zeros, three setup-only missing verifier outcomes and no active task.
The approved separate recovery63-65 and fixed baseline order remain unchanged.
The VPS and requested hourly notifications remain active. Earlier sections below
are historical checkpoints, superseded by this local-preparation status.

## Earlier audit outcome: loaded-source inventory gap, 29 September 2026

The one approved further audit at f41e47d was invoked and retained. It returned
SSH exit 1 / native ValueError at the final loaded-module guard, after internal
collector/schema return but before the launcher's final evidence rereads.
It did not time out: native failure was at 176.140959 seconds and operator
elapsed time was 182.660407 seconds. No successful completed audit, snapshot,
backup or export was obtained. Exact metadata and scope are recorded in the
[final-run status](results/custom-no-cutoff-final-20260928/README.md).

Read-only post-failure metadata at 07:54:22 UTC verified the audit PID absent,
no study processes or held/waiting ancestor locks, all 229 native and 21
installed reporting byte bindings and the trusted completion/protection guard.
Static transitive import analysis found five omitted helper bindings:
setup_probe.py, extended_token_calibration.py, calibrate_tokenizer.py,
final_schedule.py and freeze_inputs.py. At 07:58:34 UTC a stdlib-only native
read confirmed their current bytes match original deployment commit fb2d5cc and
current f41e47d. No project imports, collector or native writes occurred in
that diagnosis. This is current evidence, not retrospective qualification;
the first rejected module was not named by the retained exception metadata.

The exclusive private operator intent/failure remain; no snapshot/result exists.
Do not automatically repeat the consumed audit or weaken its import guard.
A source-inventory amendment across reporting/backup/export/handoff is needed,
without changing frozen execution or overwriting the installed reporting root.
Existing downstream connection bounds and private-parent assumptions remain
unchanged. Fresh 07:59:43 UTC preliminary progress is 89/89 complete, 50 passes,
36 verified zeros, three setup-only missing verifier outcomes and no active
task. The approved three separately reported retries remain conditional on
actual completed audit and verified backup. Keep the VPS and hourly reporting.

## Audit transport preparation validated, 29 September 2026

The user approved the reporting connection correction and one further audit.
The new Mac-only `no_cutoff_final_audit_transport.collect(full_commit)` retains
the exact installed bootstrap/main checks, pinned SSH route, original isolated
interpreter and credential-free environment. It allows 1,800 seconds for this
reporting connection and samples bound stack locations every 30 seconds instead
of profiling every call. No benchmark deadline, installed reporting file,
frozen source, permission, service or result changes. The one-shot private Mac
state retains safe diagnostics and only a validated exact-byte snapshot; existing
or partial state forbids repetition. No saved audit grants backup or admission.

The first local post-push preflight at 2706832 refused the readable, owned
mode-0755 `.runtime` parent before any SSH call or state creation. Read-only
inspection confirmed the actual private boundary is `.runtime/netcup` mode 0700.
The correction requires canonical owner-controlled, non-writable-by-others
parents, that exact private boundary and the private leaf, with parent/leaf
identity rereads. No permissions were changed, and the native audit authority
was not consumed by this local refusal.

All 49 new local tests passed after this correction. Full discovery ran
2,497 tests: 2,496 passed and one pre-existing skip. All 991 guarded regressions
passed without skips/errors/failures, with 289 stage2 bindings (285 prospective
sources plus four retained metadata files) and 182 loaded project modules checked.
All 12 repository tests passed. Native/SSH observations are mocked in these
tests; they are not native audit success. All 21 installed reporting-source
bytes remain identical to ea543e4; only the prior permitted local scored-trial
hooks differ among the 211 final-anchor files.

The whole reporting route was inspected. The old exporter/Mac predecessor and
native handoff still use 300-second audit callers; the old backup has a 900-second
audit-plus-transfer window. Its existing private-parent assumption also remains
unchanged and needs explicit downstream review. None is monkeypatched or claimed migrated. This is
a standalone audit route, not downstream completion. See the explicit
[transport amendment](protocols/custom_final_audit_transport_20260929.md).
The one further native audit is pending commit/push and fresh preflight at this
checkpoint. Previous failures and the approved separate recovery remain retained.

## Latest: approved diagnostic audit timed out, 29 September 2026

The user approved ONE read-only diagnostic audit. That invocation ran from
06:42:32 to 06:47:32 UTC at operator commit
94e4e99e91ab3981a1ed3732e32c2fc56e1b187a. The unchanged 300-second SSH/operator
wait expired (`TimeoutExpired`, 300.07346 seconds) before any completed audit
JSON returned. Metadata-only stage observations reached per-task phase evidence
and row/accounting processing. Repeated stage events were deduplicated, so they
do not establish a row count, the final active check, or a successful full audit.
Six unrecognised stderr records were suppressed; their contents and any remote
failure are unestablished. The earlier 06:16 failure remains independently
unexplained. This diagnostic timeout does not retrospectively establish its cause.

The temporary stdin observer retained the exact original bootstrap/main bodies,
all evidence checks and existing operation/subprocess bounds. Eight local
synthetic observer tests passed, including privacy, unchanged-code comparison,
numeric types and a harmless timeout fixture. No installed reporting file,
frozen source, permission, service or result was edited. This is diagnostic
evidence, not successful audit, benchmark or qualification evidence.

At 06:49:28 UTC, read-only metadata found an execution-root process still present
(PID 1127965, parent PID 1); the completion guard correctly refused then. No
holder/waiter existed for the 33 inspected ancestor locks. At 06:57:28 UTC,
a further read-only check found no process with cwd/exe in the 12 inspected
study/reporting roots, no held/waiting locks, and all 229 native and 21 reporting
bindings matched. The trusted completion guard passed again. No signal, stop,
restart or second collector was used. All three reporting backup-state paths
remained absent. These point-in-time checks do not establish successful audit.
A 07:00:36 UTC metadata check repeated those passes and explicitly confirmed
that `/proc/1127965` no longer existed.

The single diagnostic authority is consumed. No completed snapshot, backup,
export, recovery or baseline repeat was obtained or started. A reporting-only
connection/diagnostics correction and one further audit require a new decision;
do not extend waits, retry, replace the reporting root or modify frozen evidence
automatically. Review the whole audit/backup/export/handoff route before a change.
The existing recovery approval remains valid after actual audit and verified
backup; do not ask for it again. Keep the VPS and hourly notifications active.

Latest benchmark metadata is the 06:33:33 UTC observation: 89/89 complete,
50 passes, 36 verified zeros and three setup-only missing verifier outcomes,
with no active task. These remain preliminary, not an audited final score.

## Earlier audit blocker; separate recovery approved, 29 September 2026

The first actual completed audit through `no_cutoff_final_reporting.collect`
at operator commit f4e2ddd56584469aadb2023e36d858583b4fb8e8 returned a
`ValueError` at 06:16:00 UTC. No successful completed audit was obtained, and
no backup or export invocation began. The operator wrapper retained only the
exception type, so the failure stage and cause are not established: neither
a transport timeout nor an evidence-validation failure may be inferred.
The failed attempt is retained; there has been no automatic collector retry.

Read-only diagnosis at 06:17:26 UTC passed the actual completion guard and
all 229 native source/input/producer/anchor and 21 reporting-file bindings.
The reporting backup intent/result/failure paths were all absent and not
symlinks. A further metadata-only check at 06:24:52 UTC found no process with
its working directory or executable in any of the 12 inspected study/reporting
roots and no holder or waiter for the 33 existing ancestor lock files. All
229/21 bindings and the trusted completion guard still passed. These checks
invoked no collector and do not establish a completed audit or its failure cause.
One read-only diagnostic audit has been requested and is not yet approved.
Do not retry collect or replace the existing reporting installation automatically.

The user explicitly approved "one separately reported retry each" for tasks
63-65, only after the original run is audited and backed up. This supersedes
older pending-recovery statements. Diagnosis and an explicit pre-launch recovery
amendment/qualification are still required; none has run. Each recovery must use
one fresh attempt, preserve the original failures and new outcomes separately,
and never promise a pass or substitute a retry into the original 89 results.
The fixed baseline repeats remain separate. No recovery or baseline has started.

Last progress metadata is still the 06:05:15 UTC observation below: 89/89
complete, 50 passes, 36 verified zeros and three setup-only missing verifier
outcomes, with no active task. It is not an audited final score. Keep the VPS
and the explicitly requested hourly notifications active.

## Reporting installation verified, 29 September 2026

The single newly approved reporting deployment succeeded at 06:04:02 UTC from
commit ea543e46784025f3db7a5ac54c4e8e4624893278. A separate read-only inspection
at 06:04:26 verified all 21 installed reporting files and the completion guard.
The preceding read-only preflight at 06:03:29 verified all 229 native bindings,
the protected mode-0700 root, original manager completion and absence of live
execution processes, and confirmed that no reporting directory existed.
The separate reporting root now exists; do not redeploy, overwrite or retry it.
The previous pre-write refusal at 7bfe217 remains historical evidence.

No frozen execution file, permission, service or result was changed. This was
installation and inspection only: no completed native audit, final snapshot,
archive, transfer, public result export, recovery or baseline repeat ran.
The installed reporting bundle is unchanged by this documentation checkpoint.

Fresh read-only metadata at 06:05:15 UTC still shows 89/89 complete: 50 passes,
36 verified zero-score failures and three setup-only missing verifier outcomes.
There is no active or started-without-result task. All 211 frozen sources match,
all 89 results record revocation and no provider/operator stop is present.
These remain preliminary metadata, not an audited final score.

Next required work is the actual completed audit, ONE verified private backup,
allowlisted export and push before any Terminus repeat. Recovery sequencing
remains separately pending. Keep the VPS and hourly notifications active.
The following preparation and refusal checkpoints are dated history.

## Approved reporting compatibility work, 29 September 2026

The user approved the reporting-only correction and ONE new installation
attempt after validation. The guard now requires the original trusted systemd
manager start/success records and boot/invocation, inactive/dead state, absent
service cgroup and no other execution-tree process. Actual LoadState is retained;
not-found/default exit zero is never used alone as successful-execution proof.
The narrow file rule retains existing public mode-0664 bytes only behind the
exact root-owned mode-0700 execution root, with protected path/ACL/identity and
byte rereads. No frozen permission, source or result is changed.

The complete reporting/phase/archive/amended-handoff route and actual current
repeat ancestor/connection consumers use the new standard-library guard.
There are 21 reporting files and 282 prospective repeat sources (286 stage2
test bindings include four retained metadata files). The previous refused
deployment at `7bfe217` is preserved. Final local discovery ran 2,448 tests:
2,447 passed and one pre-existing skip. All 942 guarded regressions passed
without skips, failures or errors; before/discovery/after checks covered up to
180 loaded project modules with no unbound imports. All 12 repository tests
passed. A focused 132-test rerun also passed. The 51 new checks include 44
guard tests using real temporary files and synthetic procfs/manager records.
Native services, Docker and transport observations remain mocked in these
tests; this is not native audit, deployment, qualification or paid evidence.

Initial fixture corrections modelled Linux ACL observations on macOS and
included the new bound module in the synthetic bootstrap. An intermediate
source-binding refusal was retained; the stable rerun and final suites passed
without relaxing production checks. Actual local anchors match 302 old and
304 merged operator bindings, 229 reporter-native bindings, 40 reporter-local
bindings (44 with export prerequisites), and five exact metadata anchors.
Among 211 final-anchor files only the previous permitted local scored-trial
hooks differ. The newly approved installation is still pending at this source
checkpoint; no audit, backup, export, recovery or baseline repeat is claimed.
Recovery sequencing remains pending.

## Final-run direction, 28 September 2026

The user requested the best whole candidate from C0/C1/C2/C3 to run all 89
tasks after C3. The [direct-final decision](protocols/custom_direct_final_20260928.md)
defers the earlier 60-task confirmation and 20-task diagnostic; it does not
skip final runtime qualification or alter the C3 study. C3 completed at
18:22:57 UTC on 27 September with 13/20 passes. Its audit and private backup
are complete. The separately qualified [C0-NC final89](results/custom-no-cutoff-final-20260928/README.md)
service launched at 03:37:46 UTC on 28 September. At 03:21:46 UTC on 29 September,
read-only metadata showed all 89 attempts retained: 50 passes, 36 verified zeros
and three setup-only missing verifier outcomes. The service was inactive/dead,
PID 0, exit 0; all 211 sources matched, all 89 results recorded revocation and
no stop was present. No active task remains. A completed native audit, one
verified private archive and public final result export are still pending.
No baseline repeat or recovery has started.

The first separate reporting deployment attempt, after the source-bound
handoff commit and local gates, was refused before project imports or writes.
Read-only diagnosis at 04:03 UTC found no reporting directory, all 229 native
byte bindings unchanged and no stop. The transient final unit now reports
LoadState=not-found, while the systemd manager journal records successful
deactivation at 03:15:06 UTC for the same invocation that started at 03:37:46
on 28 September. The launcher currently requires LoadState=loaded.
An additional compatibility mismatch is 213 root-owned source/metadata files
with mode 0664 inside the unchanged root-owned 0700 deployment; 16 private
inputs/producers are mode 0600. No permissions or guard were changed.
A reporting-only compatibility amendment and explicit approval for a new
deployment attempt are now required. No collector, backup, export or repeat
was invoked, and no deployment retry was made.

The explicit amended operator capture and native handoff now select the
absence-aware archive verifier and actual separate fresh audit. The actual
repeat session/inspection connection is wired to it; old readers and frozen
execution remain unchanged. The reporting bundle is 19 files and prospective
repeat inventory is 280. This remains local preparation, not native deployment,
audit, transfer, qualification or dispatch. Trusted repeat service operations,
native compatibility, repeat exporter and the OpenHands successor reader remain
unfinished. The separately labelled recovery proposal still awaits the user's
sequencing/reporting decision.

Final local verification of this amended handoff ran 2,397 tests: 2,396 passed
and one pre-existing skip. All 891 guarded repeat regressions passed without
skips/errors/failures, with 178 loaded project modules bound before discovery,
after discovery and after execution. The guard covered 284 stage2 bindings:
280 prospective sources plus four retained metadata files. All 12 repository
tests passed. The 42 new capture/handoff tests and an additional connection
regression use real temporary private files, archive bytes, pipes and locks,
with native observations mocked. These are not native audit or paid evidence.

Historical launch observation:
At 03:39:51 UTC its first task was underway, with ten requests and nine accepted
responses. All 211 sources matched and no stop marker was present. This is a
dated observation, not a claim about subsequent progress.

The [separate phase-reporting amendment](protocols/custom_final_phase_reporting_20260928.md)
now has a local read-only evidence reader and 40 passing tests. At 20:20:41 UTC,
metadata showed 68/89 completed: 41 passes, 24 zero-score failures and three
missing verifier outcomes, with task 69 running. Tasks 63–65 retained setup-only
failures; a 20:35:19 UTC metadata check confirmed their agent-deadline files
were absent. Their missing agent/verifier durations and rewards must remain
null, not invented zeros. These are dated observations, not a final score.
The frozen collector and backup expect those files and remain unchanged.
The separate completed-audit reader is now implemented locally with 42 new
passing tests. It requires actual inactive-service, lineage, ancestor-lock,
runtime, source, official-limit, accounting and cleanup checks, retaining
measured/not-run timing denominators for full89/development20/remaining69.
Its trusted invocation, one absence-aware backup, public export and actual
repeat-handoff integration remain pending. Separate amended snapshot/archive
validation is now implemented locally, as described below.
No completed audit or repeat operation has run. At 21:37:10 UTC, the read-only
inspector still showed task 71 active and 70/89 complete: 41 passes, 26 zero-score
failures and three missing verifier outcomes. All 211 frozen sources matched.
At 21:48:48 UTC, task 71 had completed with a verified zero and task 72 was
running: 71/89 complete, 41 passes, 27 zero-score failures and the same three
missing verifier outcomes. No stop or source change was observed.
The final local checks ran 2,182 tests: 2,181 passed and one pre-existing skip.
All 676 guarded repeat-regression checks and 12 repository tests passed.
These are local tests with mocked native observations, not a completed audit
or additional benchmark attempts.

The separate `no_cutoff_final_archive.py` verifier now has 47 passing local
tests. It validates exact original byte anchors and amended metadata, then
reads actual archive files or stream frames to check all supporting hashes,
directory inventories and genuine absences. Missing phases remain null and
their measured/not-run denominators are checked. No archive is created or
extracted, and no native audit, off-server location or paid authority is
inferred from JSON or a receipt. The separate reporting bundle is seven files;
the prospective repeat inventory is 268 files. Old collectors and native
execution remain unchanged. The reporting launcher, one-time archive writer,
public export and actual predecessor-handoff integration are still pending.

Final local discovery ran 2,229 tests: 2,228 passed and one pre-existing skip.
All 723 guarded repeat-regression checks passed with zero skips and all 166
loaded project modules bound. The 12 repository tests also passed. These
synthetic/local checks are not native audit, backup or paid-run evidence.

At 22:21:45 UTC the read-only inspector found 73/89 complete: 42 passes,
28 zero-score failures and the same three setup-only missing verifier outcomes.
Task 74 was running with 33 physical requests and 18 accepted responses. All
211 frozen sources matched, all 73 completed results recorded revocation and
no operator/provider stop was present. These are partial, dated metadata.

At 22:59:18 UTC the service was active on task 76, with 75/89 complete:
43 passes, 29 zero-score failures and three setup-only missing verifier
outcomes. Task 75 passed. Task 76 had 21 physical requests and 20 accepted
responses. All 211 frozen sources matched, all 75 completed results recorded
revocation and no operator/provider stop was present. No repeat was launched.

The separate reporting launcher is now locally implemented with 37 passing
tests. It requires committed source bytes, the original pinned SSH route,
successful inactive final service and pre-import source/private-file checks.
Deployment is exclusive into a separate nine-file reporting bundle; existing
or partial directories are never overwritten or automatically retried.
Collection calls the actual amended audit and rereads retained evidence after
its last native service observation. No native operation has been attempted.
The prospective repeat inventory is 270 files. The one-time archive writer,
allowlisted export and actual predecessor-handoff integration remain pending.
The final local suite ran 2,266 tests: 2,265 passed and one pre-existing skip.
All 760 guarded repeat regressions and all 12 repository tests passed.

At 23:44:57 UTC, task 76 was still active: 75/89 complete, 43 passes,
29 zero-score failures and the same three setup-only missing verifier outcomes.
It had 265 physical requests and 174 accepted responses. All 211 frozen sources
matched, all 75 completed results recorded revocation and no stop was present.

At 01:21:45 UTC on 29 September, read-only metadata showed 81/89 complete:
46 passes, 32 zero-score failures and the same three setup-only missing verifier
outcomes. Task 82 was running. All 211 frozen source files matched, all 81
completed results recorded revocation and no stop was present. This is a dated
partial observation, not a final score. No baseline repeat has started.

The separate one-shot absence-aware archive producer and fixed Mac receiver
are now implemented locally, with actual-file/stream tests and mocked native
observations. They require a fresh real audit and under-lock rereads, preserve
missing evidence as absent and refuse any existing or partial backup. The
current reporting bundle is 13 files; the prospective repeat union is 274.
No native reporting deployment, audit or archive has been attempted. The full
route still requires allowlisted public export and actual amended predecessor
handoff integration before native use; old readers remain unchanged and fail
closed. Trusted repeat service operations and native verification also remain
unfinished. The user's requested three-task recovery block awaits an explicit
sequencing/reporting decision; originals are retained and no recovery is run.

At 02:21:51 UTC on 29 September, read-only metadata showed 86/89 complete:
50 passes, 33 verified zero-score failures and the same three setup-only missing
verifier outcomes. Task 87 was active. All 211 frozen source files matched, all
86 completed results recorded revocation and no stop was present. These are
dated partial metadata, not a completed score or audit.

At 02:42:39 UTC the service was active on task 88, with 87/89 complete:
50 passes, 34 verified zero-score failures and the same three missing outcomes.
Task 87 finished with a verified zero. All 211 frozen sources matched, all 87
completed results recorded revocation and no stop was present. No repeat or
recovery was launched.

The separate allowlisted public exporter and its read-only verifier are now
implemented locally. Both require a fresh actual completed native audit and
reread the existing private archive; saved flags cannot substitute. The three
public files retain null/not-run phases, missing outcomes and unknown costs,
with measured/not-run denominators for full89/development20/remaining69. The
reporting bundle is now 15 files and the prospective repeat union is 276.
No actual public result export, reporting deployment, native audit or archive
has occurred. Actual amended operator capture/native handoff integration remains
required before native use. Old collectors/readers and frozen execution remain
unchanged; neither repeats nor recovery attempts have started.

The final local suite ran 2,354 tests: 2,353 passed and one pre-existing skip.
All 848 guarded repeat regressions passed with zero skips/errors/failures,
binding all 174 loaded project modules before/discovery/after execution. All
40 new exporter tests and all 12 repository tests passed. An earlier 363-check
reporting run also passed. These use temporary synthetic evidence and mocked
native observations, not completed native audit, export or benchmark evidence.

The finalist must have no artificial spending, model-call, command-time,
job-count or completion-repair cutoff. C0/C1/C2 still contain their original
execution cutoffs: removing those from an older winner requires a labelled,
qualified and development-validated revision, not silently changing the
measured winner. Actual provider limits, finite tool windows and isolation
still apply. A best-in-world or full-benchmark accuracy win is not established.

The [older-parent no-cutoff revision](protocols/custom_no_cutoff_revision_20260928.md)
has completed its separately registered fixed20 validation. It omits C3's
dynamic time advice, retains the whole parent's planning/check choices and
uses a distinct `-NC` identity.
The complete four-block audit selected C0 (15/20, versus 14/20, 14/20 and 13/20).
Its original evidence freeze preserves all 80 outcomes and the actual 0.3 runtime;
it does not transfer that score to C0-NC or grant paid admission.
Its separate native qualification and fixed20 registration are complete. The
[C0-NC validation](results/custom-no-cutoff-20260928/README.md) started at
21:16:50 UTC on 27 September and completed at 02:43:35 UTC on 28 September:
11/20 passes, nine failures, no missing verifier outcomes. The 03:19:50 UTC
native audit verified all 190 frozen sources, official limits, original/result
bindings, revocation and cleanup. Its one private off-server backup is verified.
This is below original C0's 15/20 and is not evidence of an accuracy improvement.
Older native deployments remain unchanged. The disclosed encoded
capture correction passed its separate native fixture without replaying the
original failed command.

C0-NC has a separate policy, gateway, host-identity reader, study
registration and locked dispatcher. The new scored-runner hook requires the
authenticated dispatch scope and exact qualified image; its own fixed20 IDs
cannot reuse C0/C3 results. The source bindings explicitly record admission and
trace-label changes without modifying the measured agent implementations.
The native qualifier, isolated rehearsal, pinned gateway build and exporter
are now implemented and locally tested. The rehearsal uses synthetic-only
IDs, a fake-key-only session and a networkless gateway, without manufacturing
a completed production qualification. Host admission re-reads the bound
regression reports and actual lifecycle results. The current local suite ran
1,419 tests: 1,418 passed and one pre-existing skip; 36 separate legacy tests
passed. The separately deployed source then passed 238 native tests and all
three actual Harbor/graph/gateway/Docker/verifier rehearsals with an isolated
fake model and zero paid calls. The qualification and exact registration have
verified private off-server copies. Paid validation is complete on that
frozen source; it is not the final89 run or an inherited 15/20 score.

The earlier C3-only direct-final gateway contract is implemented and tested locally. It
accepts only the exact 89 fresh final IDs, the authenticated-freeze schema and
a separate native-final qualification record. It retains the existing shared
retry and unknown-cost accounting, without financial or request-count gates.
Its lightweight freeze reader recomputes the original whole-candidate ranking
without importing the host's agent or SSH stack into the gateway image.

The host-side original-evidence authenticator is also implemented with local
synthetic tests. It runs the unchanged original collector in its original
native interpreter, compares the fresh audit with the operator freeze, and
returns file bindings for rechecking under the final runner's ancestor locks.
It neither writes a registration nor grants paid admission.

The final-host identity reader now checks current source and dependency
versions, the Python archive, dataset file hashes, all 89 task configurations
and local image identities against all 178 original baseline results. It
reads metadata without starting containers or making model calls. Its recorded
identity must match again before execution; it does not grant paid admission.

These earlier C3-only components do not admit the selected original C0 and
have not been bypassed or relabelled. The explicit measured C0-NC final route
is described below. The original-selection freeze is saved and freshly
verified. The actual revised-finalist freeze is also saved and freshly verified,
binding all 100 outcomes and C0-NC's measured 0.5.0 runtime. The separate native-final
proof and exact89 registration are now complete, and its service has launched.
The C3 deployment was not changed. See the implementation
checkpoints in the [direct-final decision](protocols/custom_direct_final_20260928.md).

The revised-finalist evidence reader is now implemented separately in
`no_cutoff_final_candidate.py` and `no_cutoff_evidence_freeze.py`. It requires
all 80 original and 20 revised outcomes, binds the actual measured C0-NC
runtime, and cannot inherit the original 15/20 score or grant paid admission.
The operator capture refuses an active validation before acquiring native locks
and checks the original native source/input hashes before executing the unchanged
qualified collector. It has now saved and freshly verified the completed validation,
with canonical SHA256 `29bcc290a269944441f40d6b8c904aed584d16d2a7c658465e5be16e906a5ecd`.
It is not final execution admission for this lineage.
All 31 new local tests and 172 affected checks passed. Full local discovery
ran 1,450 tests: 1,449 passed and one pre-existing skip; 36 separate legacy
tests passed. A read-only local anchor check matched the actual saved original
selection, 190 revision sources, 20 registered cells and eight native producer
file bindings. Those initial tests did not perform a completed-revision audit;
the separate actual audit and freeze described above are now complete.

The C0-NC final-host authentication, lightweight gateway contract and all89
host-identity reader are now implemented separately. The authenticator checks
all 100 original/revised result bindings and the native sources before running
the unchanged completed-revision collector, then rechecks their files. Its
under-lock recheck does not recursively acquire the collector's locks. The
new final contract uses fresh `customfinal2-c0-nc-` IDs, keeps the measured
0.5.0 behaviour unchanged and binds separate final-native producer evidence.
The identity reader checks all 89 official configurations and their baseline
image/deadline bindings, without starting containers or making provider calls.

Final scored-runner admission, the locked dispatcher, isolated native qualifier,
pinned gateway build and metadata/private-backup exporter are now implemented
locally, then qualified separately on the native host. All 392 native tests
and all three actual Harbor/graph/gateway/Docker/verifier rehearsals passed
at 03:34:32 UTC, with an isolated fake model and zero paid qualification calls.
Fourteen native proof/input/producer files and exact89 registration bytes have
verified private off-server copies. The 211-file frozen final source is
`fb2d5cc569745e3087a9b3c7b65e695aebc5c0a3`; only the explicitly recorded
`scored_trial.py` orchestration differs from the measured revision.
The completed C0-NC deployment and the earlier C3-only final path were not changed.
See the [implementation checkpoint](protocols/custom_direct_final_20260928.md#final-runner-and-native-producer-checkpoint-28-september-2026).
All 61 new tests and 392 affected checks passed. Full local discovery ran
1,573 tests, with 1,572 passes and one pre-existing skip; 36 legacy tests passed.
Those local checks are distinct from the subsequently completed native rehearsal.

The user subsequently approved one separately registered 89-task repeat for
each baseline after custom final89. The [matched-repeat protocol](protocols/baseline_matched_repeat_20260928.md)
records this decision before the custom final score: custom89, then Terminus-2
repeat89, then OpenHands repeat89, with no overlapping matrices and all original
results preserved. These 178 new attempts are authorised but not yet qualified,
registered or launched. No parallel-dispatch or extra-server authority was given.
The offline `matched_repeat_schedule.py` now fixes the 178 fresh identities
and matches custom89's task order without reading outcomes. Its 15 new tests
and 55 affected checks passed; the full local suite passed 1,587 tests with
one pre-existing skip. This is not paid admission. The protocol also discloses
the original baselines' inherited one-million-turn guards, separately from
the absence of additional study request caps; custom C0-NC is unchanged.

The matched-repeat lightweight policy and gateway contracts are now implemented
locally. They bind the fixed sequence and all predecessor result/audit/archive
identities, preserve the original baseline factories and shared retry behaviour,
and add no study financial or request-count cap. Their 27 new tests and 172
affected checks passed. Full local discovery ran 1,615 tests, with 1,614 passes
and one pre-existing skip; the separate 36-test legacy suite passed.
A local check matched the original 84-source and final
211-source anchors and the prospective 220-file repeat inventory. These are
not native authentication or execution evidence. The host authenticator,
runtime checks, scored admission/dispatcher, qualifier, pinned image and
exporter are still unfinished; no repeat is registered or launched. The
active custom final source was not changed. See the
[gateway contract checkpoint](protocols/baseline_matched_repeat_20260928.md#offline-gateway-contract-checkpoint).

The [off-server predecessor reader](protocols/baseline_matched_repeat_20260928.md#offline-off-server-predecessor-reader)
is now implemented for the first Terminus-2 successor, with local synthetic
tests. After custom final89 completes, it will freshly run the unchanged native
collector and read/hash the existing off-server archive, matching the saved
audit, actual member bytes, receipt and curated rows. It refuses active/stopped
native evidence before collector locks and never creates or replaces a backup.
Its exclusive private save and fresh verification remain non-admitting.
No real capture/save/verify has run while custom final89 is active. The
OpenHands predecessor reader and remaining native repeat host/runner/qualifier
integration are still unfinished. The prospective repeat inventory has 222
sources; the active final's 211 frozen sources remain unchanged.
All 36 new tests and 89 focused checks passed; the final local suite ran
1,651 tests, with 1,650 passes and one pre-existing skip. The separate 36-test
legacy suite passed. Real local anchor bytes were checked without invoking a
completed native collector or creating any repeat execution evidence.

The [matched-repeat host identity reader](protocols/baseline_matched_repeat_20260928.md#offline-current-host-identity-reader)
is now implemented locally. It checks the separate deployment's source,
interpreter, dependency versions, Python archive and full native host identity,
all 89 official configurations and task images against the 178 original
baseline result bindings. Its under-lock recheck reads the eight real producer
files and actual synthetic result metadata, without invoking a collector or
granting dispatch. The future scored integration must produce the explicit
repeat result identity; it is not implemented by this reader.
Installed-library/original-control authentication, native predecessor admission,
the locked dispatcher, actual isolated qualifier, pinned build and exporter
remain unfinished. Neither planned repeat root has been deployed.
All 31 new tests and 154 focused checks passed; full local discovery ran 1,682
tests, with 1,681 passes and one pre-existing skip, plus 36 passing legacy tests.
These new host tests use mocked native responses and real temporary file checks,
not native qualification. A local anchor check matched all 211 unchanged final
sources and the 224-file prospective repeat union. No completed collector,
repeat registration or model request occurred.

The [installed-library and constructor reader](protocols/baseline_matched_repeat_20260928.md#offline-installed-library-and-constructor-reader)
is now implemented locally. It will compare current original/repeat installed
library bytes and actual factory settings in separate credential-free
interpreters, refusing active ancestors and any source or library drift.
It performs no agent setup/run, task tool or provider call and grants no
admission. It explicitly does not prove historical installed bytes: the old
qualification has source/lock bindings but no installed-library byte manifest,
and its backup excludes `.venv`. Native execution, predecessor integration,
scoped dispatch and actual repeat qualification remain unfinished.
All 28 new tests and 204 focused checks passed; final full local discovery ran
1,710 tests, with 1,709 passes and one pre-existing skip. The 12 repository
tests under `tests/` passed. The prospective repeat union has 227 files;
all 211 active custom-final sources remain unchanged. No native reader,
completed collector, deployment or repeat launch was invoked.

The [original-outcome authenticator](protocols/baseline_matched_repeat_20260928.md#offline-original-outcome-authenticator)
is now implemented locally. It pins the original 178-row snapshot/CSV and the
unchanged completed-baseline collector, audits in the original interpreter
under all ancestor locks, and provides a separate actual-file recheck without
recursive audits. Active/stopped ancestors, source/anchor drift and changed
supporting evidence fail closed. No native invocation has occurred while
custom final89 runs. This does not establish off-server predecessor verification,
historical installed bytes, repeat runtime qualification or scoped paid admission;
those remaining integrations must still precede any repeat launch.
All 30 new tests and 213 focused checks passed. Full local discovery ran 1,740
tests, with 1,739 passes and one pre-existing skip; 12 repository tests passed.
The 230-file prospective union includes the unchanged original exporter.
All 211 active final sources remain unchanged. A local check matched all 178
original rows and the actual saved anchors without invoking a native collector,
writing an archive or launching a study.

The [live predecessor handoff](protocols/baseline_matched_repeat_20260928.md#offline-live-predecessor-handoff)
now has a locally tested operator sender and native consumer. The sender
performs fresh Mac-side capture and streams the existing private archive; the
consumer checks the actual compressed/member bytes, then freshly audits final89
in its original interpreter before caller locks. Under-lock rechecks require
a process-local witness and reread files, without another collector. Saved
JSON or a receipt flag is not a live witness. This does not supply paid
admission, authenticate a network peer by itself, or create an SSH/service
launcher. That connection, combined original/library/runtime authentication,
scoped dispatch, native qualifier, pinned build, repeat exporter and OpenHands
successor remain unfinished. No native handoff or completed collector was
invoked while custom final89 runs.
All 46 new tests and 213 focused checks passed. Full local discovery ran 1,786
tests: 1,785 passed and one pre-existing skip; 12 repository tests passed.
The tests use real temporary archives and local pipes with mocked native
services and audits. The prospective source union is 234 files; all 211
qualified final sources remain unchanged. No new study has launched.

The [locked prerequisite session](protocols/baseline_matched_repeat_20260928.md#offline-locked-prerequisite-session)
now connects the live handoff, original-result audit, current library comparison
and host reader locally. Real audits precede outer locks; actual file rechecks
run under the complete ancestor chain. Its process/thread/task-bound handle
cannot be saved or reused after exit or a failed check. The qualification
recheck binds actual producer bytes to fresh library, host and predecessor
observations, without registering or admitting a paid trial.
All 32 new tests and 245 focused checks passed with mocked native readers and
real temporary files/locks. No native session, collector or qualification was
invoked while custom final89 runs. The prospective union is 236 sources; all
211 final sources remain unchanged. Pinned SSH/service integration, scored
dispatch, actual isolated qualification, pinned build, repeat export and the
OpenHands successor reader remain unfinished. No repeat has launched.
Full local discovery ran 1,818 tests, with 1,817 passes and one pre-existing
skip; all 12 repository tests passed. The final 32-test session recheck passed.

The [pinned inspection connection](protocols/baseline_matched_repeat_20260928.md#offline-pinned-inspection-connection)
is now implemented locally. It preserves the existing SSH pinning and sends a
freshly audited archive stream to a detached service that opens its own locked
session in the same process/task. Exact sources and inactive ancestors are
checked before imports; local peer PID, MainPID and directory checks bind the
relay to that service. Private intents and receipts survive disconnects and
uncertain failures. Its only operation is prerequisite inspection: no paid
run, registration or qualifier command exists, and no receipt grants admission.
All 36 new tests and 281 focused checks passed using actual local archives,
pipes and sockets with mocked native services/audits. No target-host connection
was executed. The prospective union is 239 sources, with all 211 final sources
unchanged. Native service verification, scoped scored admission/dispatcher,
real isolated qualification, pinned build, repeat export and the OpenHands
successor reader remain unfinished. No repeat deployment or attempt exists.
Full local discovery ran 1,854 tests: 1,853 passed and one pre-existing skip.
All 12 repository tests and the final 36-test connection recheck passed.

The [scoped repeat admission](protocols/baseline_matched_repeat_20260928.md#offline-scoped-scored-admission)
now connects a live same-task session to immutable registration and the explicit
local scored-runner hook. It issues the original baseline factory, admits only
the next fresh registered key, rechecks qualification/source/producer bytes,
preserves zero/missing/unknown outcomes and verifies the started task image.
The 31 new local tests use synthetic qualification and mocked native execution;
the combined study/scored recheck passed 39 tests. This is not a native
qualification, real registration or paid launch. The inspection connection
still cannot dispatch. Native qualification, pinned images, the paid service/
dispatcher, exporter and OpenHands successor reader remain unfinished.
The prospective union has 241 files. Only the permitted local `scored_trial.py`
orchestration hook differs from the 211-file final anchor; the running native
final source, baseline factories, tools, model, retries and old collectors
were not changed.
All 371 final focused checks passed. Full local discovery ran 1,885 tests:
1,884 passed and one pre-existing skip; all 12 repository tests passed.

The [sequential repeat dispatcher](protocols/baseline_matched_repeat_20260928.md#offline-sequential-dispatcher)
is now implemented locally. It consumes a live session in the same process and
async task, registers through the existing qualification checks and dispatches
the exact 89 fresh keys using the issued original baseline factory. It retains
zero/missing outcomes, verifies real result bytes at each boundary, honours
shared cooldown and cooperative stops, and refuses automatic restart after a
private launch intent or any prior attempt. Its count summary is not a completed
evidence audit or verified backup. There is no CLI or saved-receipt launch mode.
The connection remains inspection-only; native qualification, pinned images,
paid service integration, repeat export and the OpenHands successor reader are
still required. No native repeat operation or provider call occurred. The
prospective union is 243 files, with no additional final-anchor source change.
All 31 new tests and 165 focused checks passed, using real local scopes/files
and mocked native execution. Full local discovery ran 1,916 tests: 1,915 passed
and one pre-existing skip; all 12 repository tests passed separately.

The [session-bound image builder](protocols/baseline_matched_repeat_20260928.md#offline-session-bound-image-builder)
is now implemented locally. It uses the original qualified gateway base,
overlays seven allowlisted lightweight source files, and checks all 31 gateway
import-source bytes. The guard image is reused unchanged. A live same-task
session, held ancestor locks, exclusive private intent and actual Docker
observations are required; saved receipts cannot build or qualify a repeat.
Existing image evidence or attempts prohibit automatic rebuild. A separate
verification function rereads existing evidence and images without rebuilding.
The prospective source union is now 249 files, including three inherited import
helpers newly bound for current parity, not retroactive historical attestation.
No native build has run, and legacy-builder compatibility remains unverified.
The real isolated qualifier, trusted service integration, exporter and OpenHands
successor reader remain unfinished. The connection still only inspects
prerequisites and must not be invoked while custom final89 is active.
All 35 new tests and 223 focused checks passed. Final local discovery ran 1,951
tests: 1,950 passed and one pre-existing skip; all 12 repository tests passed.
These checks did not invoke a native repeat operation or paid provider.

The [image-evidence admission integration](protocols/baseline_matched_repeat_20260928.md#offline-image-evidence-admission)
now requires the actual retained image-build intent/result in addition to the
eight native regression/lifecycle producers. Qualification rechecks and each
next-cell admission reverify installed gateway bytes and pinned images inside
the same live locked session; saved image reports alone cannot grant admission.
Both raw build-file hashes remain bound through the final admission reread.
All 27 new tests and 250 focused checks passed with mocked native readers and
Docker, real local files/locks and test-only synthetic qualification. The
prospective union is 250 files, with no additional final-anchor source delta.
Actual isolated qualification, trusted service wiring, native image build,
repeat export and the OpenHands successor reader are still required. No native
repeat operation or model call occurred, and the active final is unchanged.
Full local discovery ran 1,978 tests: 1,977 passed and one pre-existing skip.
All 12 repository tests and the final 27-test image-admission recheck passed.

The [isolated rehearsal gateway](protocols/baseline_matched_repeat_20260928.md#offline-isolated-rehearsal-gateway)
is now implemented locally. It accepts only fixed synthetic identities and
credentials, checks network isolation, and scripts the original Terminus and
OpenHands wire/tool formats through unchanged retry and passive accounting.
Terminus keeps its native completion-confirmation turn. No production proof,
registration, host lifecycle or paid admission is created. The prospective
inventory is 252 files; the future image overlays eight sources and verifies
32 installed import files, with its production entrypoint unchanged.
All 40 new tests and 262 focused checks passed, plus a final 67-test affected
recheck. Native host/scored fixture integration, the actual qualifier, trusted
service wiring, pinned native build, repeat export and the OpenHands successor
reader remain unfinished. No repeat operation or paid request was run; the
active custom final deployment and all old evidence remain unchanged.
Full local discovery ran 2,018 tests: 2,017 passed and one pre-existing skip;
all 12 repository tests passed separately. These are local checks, not native
qualification or additional benchmark results.

The [session-owned host rehearsal route](protocols/baseline_matched_repeat_20260928.md#offline-session-owned-host-rehearsal-route)
is now implemented locally. It awaits the shared scored lifecycle in the same
live prerequisite session, uses the original baseline factory and a separate
synthetic-only admission scope, and checks actual service isolation, retained
results, traces, revocation, cleanup and image evidence. Setup cancellation and
cooperative boundary stopping have dedicated one-shot fixtures; no production
qualification is fabricated and no paid admission is patched. The prospective
inventory is 254 files, with only `scored_trial.py` changed from the final anchor.
The native qualifier, trusted service operations, real image build, repeat
exporter and OpenHands successor reader are still unfinished. No native
rehearsal or repeat dispatch has occurred, and the active custom final remains
unchanged.
All 42 new tests and 318 focused checks passed. Full local discovery ran 2,060
tests: 2,059 passed and one pre-existing skip; all 12 repository tests passed.
Native Docker, setup/run, verifier and prerequisite readers are mocked. These
checks do not establish native qualification or additional benchmark results.

The [one-shot native qualifier](protocols/baseline_matched_repeat_20260928.md#offline-one-shot-native-qualifier)
is now implemented locally. It keeps the actual handoff session on its owning
async task while building/reverifying images, running an isolated regression
child and awaiting all three host rehearsals. Actual producer and supporting
trace/accounting bytes, not return flags, are required. Durable intent,
completion and failure records prevent automatic replay and prevent a proof
left by a failed operation from admitting paid work. Session/scored admission
rereads those additional bindings, alongside all ten core producer files.
The prospective inventory is 261 files; the active final's frozen sources and
all original evidence are untouched. Trusted service operations, actual native
build/qualification, repeat export and the OpenHands successor reader remain
unfinished. This checkpoint did not perform a native repeat operation or make
a provider request.

All 40 new tests and all 594 local repeat regression checks passed. The actual
regression import closure now requires source bindings, adding five unchanged
helpers for current verification only, not retrospective attestation. Final
local discovery ran 2,100 tests: 2,099 passed and one pre-existing skip; all
12 repository tests passed. Native readers, Docker and actual baseline
setup/run remain mocked; these local checks are not native proof or benchmark
results.

## Current checkpoint, 27 September 2026

The user has requested a C3 before final scoring. The
[C3 design and limits audit](protocols/custom_c3_design_20260927.md) records an
separately qualified 0.4.1 candidate. At the user's request, it removes the 60-second
command default, background handle quotas and completion-repair count stop.
Commands use the remaining official task time unless the agent chooses a
shorter timeout. The time reminders remain advisory. This combined revision
is not a reminder-only ablation or a claim of unlimited resources.
The [C3 fixed20 run](results/custom-deadline-20260927/README.md) started at
13:47 UTC on 27 September, after 205 native tests and all three real
Harbor/gateway/Docker/verifier synthetic rehearsals passed without paid calls.
At 13:50 UTC its first task was active with 12 accepted provider responses.
This is a historical launch snapshot. C3 is now complete and audited at 13/20;
C0/C1/C2 remain 15/20, 14/20 and 14/20. C3 uses its own policy, qualification and
registration path; it cannot enter the older registry as C0. Whole-variant
selection now includes C3, but its freeze/schedule documents are metadata,
not permission to launch confirmation or the final benchmark.

The corrected baselines are complete: Terminus-2 52/89 and OpenHands 44/89.
The separate [custom 0.3 C0 block](results/custom-portable-20260926/c0/README.md)
completed all 20 development tasks with 15 passes. Its matched baseline scores
are 14/20 and 10/20. This is a development result, not a confirmed full-run win.

The [C1 planning comparison](results/custom-portable-20260926/c1/README.md)
completed at 04:51 UTC on 27 September: 14 passes, six failures and no missing
verifier results. Its audit and private off-server backup are complete.
C2 added completion checks to the registered C0 parent on the same 20 tasks.
It completed with [14 passes and six failures](results/custom-portable-20260926/c2/README.md),
with no missing verifier results. Its audit and private off-server backup are
complete. C0 remains the strongest complete development variant and is the
preselected parent for C3. The custom final 89 has not started.

The [final-run preparation note](protocols/custom_final_preparation_20260927.md)
records the 30 September afternoon Sydney target and the checks it cannot
override. `portable_final_selection.py` adds offline selection over complete
C0/C1/C2 summaries without the old spending or call-count gates. It is not yet
connected to a qualified final-run launcher and cannot authorise paid calls.
The confirmation and ablation/repeat in that earlier note are now deferred by
the 28 September decision above. Source freeze, final registration and native
final-run qualification remain required.

The offline candidate-freeze and schedule modules now bind all 60 development
results and generate separate confirmation (60), diagnostic (20) and final
custom (89) cells. They reject altered evidence and do not authorise paid
execution. The new four-variant modules extend those schedules to include C3,
bind all 80 development outcomes after completion, and label a C3-parent
comparison as a combined revision rather than a single-lever ablation.
The original four-variant evidence has been frozen, but the revised no-cutoff
finalist has not. Final admission remains unfinished. Native jobs run
independently of the Mac.

`deadline_evidence_freeze.py` now connects the four-variant candidate document
to a fresh, read-only audit of original result files and their source bindings.
It preserves the selected version's actual runtime rather than automatically
using C3's code. After C3 completed, a real capture/save/fresh-verification
selected C0 and bound all 80 original outcomes. This does not admit paid
confirmation or final trials or exempt the C0-NC revision from qualification.

## Previous checkpoint, 26 September 2026

The corrected full baselines and separate timeout diagnostic are complete.
See [baseline results](results/baseline-corrected-20260923/README.md) and
[diagnostic results](results/timeout-diagnostic-20260925/README.md).
Do not restart those experiments or apply current source edits to their
immutable server deployments.

Custom development is [stopped for compatibility repairs](results/custom-development-20260926/README.md).
The first C0 deployment retains four started attempts: two verifier zeros,
one setup failure and one operator interruption. It has no completed /20 score.
The separately versioned [0.3 candidate](results/custom-compatibility-20260926/README.md)
adds text-only file transport, a private Python fallback, safer process capture,
cooperative boundary stopping and cancellation evidence. Its offline checks do
not constitute a paid launch or a benchmark quality result.
The fixed dev20 comparison is Terminus-2 14/20
and OpenHands 10/20. `corrected_custom_scope.py` verifies that matched export.
The separate development runner now records the user's 26 September authority:
no project/task financial cap, reserve or artificial call-count ceiling. It
retains actual provider limits and official task limits, with no automatic
top-up. The original 0.2 setup qualification passed 120 server tests and four
real-Docker rehearsals, but the paid run exposed gaps in that fixture coverage.
It cannot qualify changed 0.3 source. A successor needs fresh native qualification
and a new registration retaining the partial experiment. See the protocol note for the
remaining development and final-freeze work. Approved new work is pushed to
`main`; historical experiment commits remain unchanged.

Everything below is historical; earlier caps, running states and admissions
must not be mistaken for current execution authority or current results.

## Historical track, 20 September 2026

The active authorised track is now [Netcup native Linux + OpenRouter](NETCUP.md),
on branch `codex/netcup-openrouter-study`. This restores the one-model paid
study on a dedicated x86-64 Docker server. The user capped further spending at
the observed US$12.031657772 remaining balance; no top-ups are authorised.
The amended caps are in `budget_policy.json` and `study_budget.py`.
All 20 development environments and three live harness/model fixtures passed
earlier qualification. Six Terminus development tasks have now been attempted:
four have verified billing, one passed, and two retain unknown charges. The
[approved completion amendment](COMPLETION_AMENDMENT_20260920.md) permits
collecting low-score results while retaining those two exact historical holds.
Fresh synthetic runtime qualification passed, but the subsequent real-model
setup request returned HTTP429 and has no available billing receipt. This new
setup reservation blocks paid execution; it is not covered by the two-hold
exception. No full89 run, completed comparison or custom win is established.
Langfuse service readback is verified for the setup traces, not final results.
See [the current checkpoint](NETCUP.md) and
[billing recovery evidence](netcup/BILLING_RECOVERY.md). The older running
statuses and budget amounts below are historical, not the current policy.

Offline finalisation now binds finalist selection to the canonical registered
custom-development blocks and their independently valid reviews. A local-only
[code-free evidence packager](final_export_status.md) is implemented but refuses
to create the real ZIP until the complete 267-cell final matrix is reaudited.
No new spending PDF, assignment report, real final archive or submission has
been generated by these changes.

## Previous track, 17 September 2026

The then-active authorised study was [CETUS-only local inference](CETUS_LOCAL.md),
on branch `codex/cetus-local-harbor-study`. The OpenRouter configuration and
records below are preserved historical work, not the active execution policy.
Do not invoke the old paid runners to execute the local study.

## Historical Mac/OpenRouter track (superseded)

Current host: the authorised Mac + OpenRouter fallback. Docker was resized to
4 CPUs / 10 GiB and the authorised Orchestra services stopped. Local runtime,
gateway and agent fixtures now run. CETUS records and earlier host inspections
below are historical; no further CETUS execution is planned in this fallback.
The scored study has not launched and is not complete.

Approved scope, with the authorised host amendment: Mac Docker task execution,
OpenRouter DeepSeek V4 Flash 0731 through
the verified DeepInfra FP8 endpoint; Terminus-2, OpenHands and a new custom
Deep Agents/LangGraph harness. Preserve the Stage 1 pilot without edits.

## Gates and evidence checklist

- [x] OpenRouter authenticated; spending is recorded in the setup ledger.
- [x] Mac Docker offline fixture and narrow public-egress fixture passed.
- CETUS account/DMP/compute-node gates are historical and inapplicable to the
  selected local host; no claim of UTS approval is made.
- [x] Source branch: `codex/cetus-openrouter-stage2`, based on `6d10c4e`.
  The installed Command Line Tools Git works independently of the Xcode launcher.
  No licence was accepted automatically.
- [ ] Safe task runtime validated against all 89 environment definitions.
- [ ] Crash-safe gateway and precise budget ledger implemented and tested.
- [x] Model/provider metadata and account credit revalidated before paid probes.
- [x] Canonical dataset bytes matched official revision; development IDs unchanged.
- [ ] Dependencies, task manifests and experimental settings frozen.
- [ ] Real custom backend, baseline integrations and Langfuse verified.
- [ ] Bounded $1 compatibility probes and 20-task Terminus qualification.
- [ ] 120 development cells, including qualification; finalist frozen.
- [ ] 267 fresh final cells: 89 per harness, one attempt each.
- [ ] Independent evidence, metric, billing and security audit.
- [ ] Technical bundle and separate code-free report-writer ZIP.

Stage 2 dataset source: see `dataset_provenance.json` for the authoritative
`dataset_path`, official Git revision and per-file hashes. Do not use the old
pilot cache or pilot selection/oracle runner for this stage.

Revised budget after authorisation to use the available account balance:
$0.055 per scored trial, equal across harnesses; setup $1; development $6.60;
final $14.685; core maximum $22.285. The observed $25.265176805 account balance
leaves a $2 untouched reserve and at most $0.980176805 contingency, with local
admission ceiling $23.265176805. This is a snapshot, not a guaranteed allocation:
recheck live account credit before spending and reduce admission if it declines.
The original plan's $0.06 cap and $30 allocation are superseded by this budget.
No paid calls until safety and spending gates pass. No model fallback,
leaderboard extension, publication, final report or presentation in this unit.

Technical completion, research success and external submission are separate.
Primary objective: higher observed accuracy against preregistered comparators,
with Terminus-2 primary. Secondary: >=20% less charged cost without fewer
nonzero successes. Efficiency-only assessment approval remains unconfirmed.

## Execution journal

2026-09-16: Began authorised implementation with read-only environment discovery.
CETUS login node is x86_64, Apptainer 1.5.3; no Docker/Podman on PATH.
Local Harbor 0.22.0 has a built-in Singularity adapter; compatibility is not
yet established. No paid requests or scored trials have been made for Stage 2.
The preflight below runs deterministic diagnostics only, with no API key.

2026-09-16: Completed PBS preflights 88368/88369; saved logs and findings.
Created deterministic 89/20/69 input inventory without reading solution/test
contents. All 15 offline tests passed. Paid and agent execution stopped at the
runtime isolation/comparability and available-account-credit gates. See
preflight_findings.md for exact evidence and required decisions. No Git commit
or push performed; no source-of-truth claim of a clean worktree is made.

2026-09-16 follow-up: User authorised adapter hardening, use of available credit,
and a new GitHub branch. Added a private Unix-socket transport prototype and
an exact-money SQLite reservation ledger. Neither is a finished Harbor adapter
or billing gateway. Pending reservations survive crashes; billing overcharges
persistently halt new reservations. Stage allocation, fresh balance retrieval,
provider reconciliation and gateway integration remain required before spending.
The runtime smoke test is intentionally network-disabled and cannot qualify
network-dependent benchmark tasks. Do not score such tasks through it.

Live transport evidence: PBS 88373 failed command execution with a read-only
container filesystem. Adding an ephemeral writable overlay allowed PBS 88375
to pass all six fixture checks: authenticated health, wrong-token rejection,
root/mount isolation, file roundtrip, no routes/TCP endpoints, private socket.
Both logs are retained. This does not establish CPU/memory limits, adversarial
containment, internet egress, Dockerfile/Compose support or all-task compatibility.
Offline checks: 17 Stage 2 tests and 12 existing tests passed (29 total).

2026-09-16 next increment: inventoried all 89 environment definitions (all have
images, no Compose, maximum declared 4 CPUs/8192 MB RAM). Added immutable stage
allocations to protect the final budget, one-outstanding-request admission,
concurrent-reservation/restart tests and strict pinned-provider request policy.
25 Stage 2 tests plus 12 existing tests passed (37 total). Request policy is
offline only: streaming, input-cost bounds, actual billing reconciliation and
live gateway integration are not qualified. Unsupported features fail closed;
do not change baseline semantics silently to make integration pass.

See runtime_blockers.md: an approved isolated network route remains unresolved.
The command-channel fixture also does not yet hide its socket/token from the
task itself. Do not run agents through it. No paid model calls were made.

2026-09-16 native-instance follow-up: PBS 88380 passed a deterministic native
Apptainer instance test with no custom control socket/token or host bind mounts.
Files persisted between separate commands; shared home/control paths were
absent; networking remained disabled; the instance was stopped afterward.
This supersedes the custom socket fixture as the preferred backend direction,
but does not qualify the all89 runtime. Apptainer reported rootless cgroups
unusable in fakeroot mode, leaving resource enforcement as an explicit gate.

Added gateway dispatch core with trial-token authentication/revocation,
reserve-before-dispatch, fresh-balance callback, and fail-closed handling of
missing/ambiguous billing. Seven synthetic gateway tests passed; total 32 Stage 2
plus 12 existing tests (44). No live transport, billable-input estimator or
provider reconciliation has been qualified. No API requests are dispatched by
default, and no paid call was made. HTTP serving/baseline wiring still pending.

2026-09-16 OpenRouter transport increment: added fixed-origin HTTPS transport
with redirects refused, no retries, exact decimal response parsing, sanitised
HTTP errors and a private credential-file check. Generation remains disabled
by default. All 37 Stage 2 tests and 12 existing tests passed (49 total).
A real read-only account/endpoint check returned available account credit
$25.265176805, key usage $0, key remaining allowance $30, and the requested
DeepInfra FP8 endpoint at $0.06/M input and $0.18/M output tokens. This is not
generation, tool-use, billing reconciliation or harness compatibility evidence.
The safe request-cost bound and live gateway serving remain pending.

2026-09-16 gateway integration increment: a loopback-only HTTP endpoint now
accepts OpenAI-style chat requests and forwards them to the guarded core.
Real localhost HTTP tests use scripted responses, not paid model calls.
Generation identifiers are durably attached before reconciliation; the core
requires matching model/provider/cost from OpenRouter's generation endpoint
before settling a reservation. Pending records remain queryable after restart.
All 42 Stage 2 tests and 12 existing tests passed (54 total).

The live upstream transport is implemented, but no live gateway instance was
launched. Harness compatibility and a qualified conservative input-cost bound
remain gates. The official tokenizer source was located at
`deepseek-ai/DeepSeek-V4-Flash-0731`, revision
`7872f01b1d1fe23eabc4c98b48bffcef5a386062`; it has not been installed or qualified
against the provider's actual prompt encoding. No heuristic estimate is treated
as a proven bound, and no paid generation occurred in this increment.

API references inspected:
- https://openrouter.ai/docs/api/api-reference/generations/get-generation
- https://openrouter.ai/docs/cookbook/administration/usage-accounting
- https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash-0731

2026-09-16 first live setup fixture: one plain completion through the gateway
core returned exactly `UTS_OK` (14 prompt tokens, 4 completion tokens). Before
dispatch, the ledger reserved $0.10487040: the entire 1,048,576-token input
context at the $0.10/M routing ceiling plus 64 output tokens at $0.20/M. This
does not rely on a heuristic tokenizer. It is only suitable for the setup
allocation, not the $0.055 scored-trial ceiling.

The generation receipt was initially unavailable, so the gateway retained its
reservation and stopped. A later read-only lookup returned the canonical dated
model identifier. Registered the exact alias mapping and reconciled the same
generation without replay. Final cost: $0.00000156. Key usage, completion cost,
generation cost and account-balance decrement agree; credit $25.265175245.
See setup_probe_result.json (initial stop) and setup_probe_reconciled.json
(recovery). The setup ledger is `.runtime/stage2/setup_budget.sqlite`, with a
strict aggregate $1 ceiling. Every future setup request must use this ledger;
do not create another setup allocation in another ledger. Development/final
allocations remain separate and must not double-count this setup allowance.

All 46 Stage 2 tests and 12 existing tests passed (58 total). No scored task
ran. Tool calling, HTTP-to-live-provider wiring, real baseline execution,
input-cost bounds for scored trials, Docker network isolation and full runtime
qualification remain outstanding. The one-shot marker prevents probe replay.

2026-09-16 tool/client milestone: the single real tool-call fixture returned
`record_fixture` with exactly `{"marker":"UTS_OK","count":7}`; no commands or
tool side effects were executed. Cost $0.00003084 (319 input, 65 output tokens).
Its receipt was delayed beyond bounded read-only polling, so the gateway stopped
and retained the reservation. Reconciled the same generation later, no replay.
Total setup spend $0.00003240, no pending requests. Refreshed key usage and
account credit agree: remaining $25.265144405. Keep the earlier result/receipt
snapshots: they accurately record the transient accounting delay.

The installed Harbor LiteLLM client successfully used the real localhost HTTP
gateway and guarded core with a scripted upstream response, exactly once.
Harbor's outer automatic retry decorator was explicitly bypassed only in this
fixture and SDK retries disabled. A production connection adapter must preserve
that no-hidden-retries property; no baseline agent was executed by this test.
No vendor package was edited. All 48 Stage 2 tests plus 12 existing tests pass
(60 total). Scored-trial input-cost bounds, native agent/task wiring and Docker
network isolation still require qualification before the study can launch.

2026-09-16 runtime/tokenizer milestone: the actual Harbor DockerEnvironment
started an isolated fixture using the cached native ARM Node image. All seven
checks passed: 4-CPU and 8-GiB configured limits, no Mac home, no Docker socket,
no upstream API key, loopback-only networking, and a file preserved between
commands. The fixture was removed through Harbor afterwards. This is an
offline fixture, not an agent run, adversarial isolation audit, AMD64 task
qualification, or evidence that all 89 tasks fit the host. See
`harbor_runtime_probe_result.json` and the explicitly network-disabled Compose
override. Do not use that override for tasks that require internet access.

Reviewed the pinned official DeepSeek encoder and tokenizer. Offline replay of
the two existing request shapes exactly matches the provider's input counts:
14 plain and 319 tool-schema tokens. `calibrate_tokenizer.py` verifies both asset
hashes before importing the reviewed encoder and makes no API calls. The assets
remain in ignored `.cache/stage2-tokenizer/`; the output records source revision
and hashes. This small calibration is NOT a qualified upper bound for scored
requests. Multi-turn/tool-result/reasoning/schema cases and provider template
drift remain unresolved; the production reservation policy is unchanged.

Adapter inspection confirms OpenHands runs inside its environment, whereas the
gateway currently listens only on host loopback. Restricted container-to-gateway
connectivity and public-internet/private-network isolation need implementation
and runtime verification before a live baseline can run. Harbor 0.22.0 has an
egress-control sidecar worth evaluating, but its availability alone proves no
isolation guarantee. No paid requests or scored tasks were added this increment.
All 48 Stage 2 tests and 12 existing tests passed again (60 total). Mac checks
showed no thermal/performance warnings, 37% memory free and 48 GiB disk free.

2026-09-16 container gateway transport: added a private Unix-socket HTTP server
and task-local loopback relay. This permits an installed agent's ordinary
OpenAI client to contact a dedicated model gateway container through a read-only
socket volume, without a host HTTP listener. The relay forwards only the fixed
completion route, preserves the caller's trial bearer token, bounds request and
response sizes, strips unrelated headers and never retries requests. It has no
upstream key and no command-execution interface. The existing host-loopback
gateway behaviour is unchanged.

`docker_gateway_probe_result.json` records a real two-container run using the
pinned cached ARM64 Python image. All 12 checks passed, including roundtrip,
wrong-token/account-route rejection, no task network other than loopback,
read-only socket mount, no exposed host ports, and exactly one settled request
in the **synthetic fixture ledger**. The provider response and balance were
scripted; no real account, credential or paid request was used. Both containers
and their dedicated socket volume were removed. No existing volumes or services
were changed. Five new regression tests pass; 53 Stage 2 plus 12 existing tests
pass (65 total). Mac health checks remained normal with 48 GiB free space.

This qualifies the narrow socket/HTTP transport fixture, NOT the OpenHands
agent itself or the complete execution architecture. Production integration
must supply an authoritative persistent budget ledger and upstream credential
to the trusted gateway only, run its upstream HTTPS connection separately from
the task, revoke each trial token, and explicitly support each task's user/UID.
The fixture used root in both containers. The task must not receive a Docker
socket, gateway ledger or credential mount. Public task internet access remains
unqualified and disabled in this fixture. Scored-request cost bounds and native
baseline execution remain launch gates. No scored trial has run in Stage 2.

2026-09-16 live HTTP milestone: `live_harbor_probe.py` exercised the installed
Harbor LiteLLM client, localhost HTTP gateway, guarded admission ledger and
actual pinned OpenRouter endpoint together. It returned exactly `UTS_OK` with
one upstream dispatch, 14 input tokens and 4 output tokens. Cost $0.00000156;
the generation receipt reconciled within this execution and no pending requests
remain. Total aggregate setup spending is $0.00003396. A subsequent read-only
account check reported credit $25.265142845 and matching key usage $0.00003396.
The $0.10487040 full-context reservation was made before dispatch, using the
existing $1 setup ledger, not a new allowance. No scored-trial bound is inferred.

`receipt_polling.py` now provides bounded read-only receipt lookup: at most
eight attempts with a 20-second admission deadline for new lookups by default.
An already-running HTTP lookup retains the transport's 45-second timeout, so
this is not a strict 20-second end-to-end wall limit. No generation call is
retried. Unknown outcomes retain the reservation. The one-shot setup runner
persists its marker and response privately and has an explicit read-only
reconciliation mode for a delayed receipt. Its client disables SDK retries and
bypasses Harbor's outer retry decorator only for this documented fixture;
native baseline retry configuration still needs integration and verification.

All 57 Stage 2 tests and 12 existing tests pass (69 total), including four new
receipt delay/deadline/error tests. This was a real **client** run, not a Terminus
agent, OpenHands agent or benchmark task. No task scores were produced. The
remaining execution gates include scored-request cost limits, public task
network isolation, native agent integration, dataset provenance and the
previously documented study protocol gates. Mac checks remained normal with
48 GiB disk free. Raw credentials and runtime journals remain untracked.

2026-09-16 agent/provenance/network milestone:

- Verified all 89 tasks and 1,037 files (including dataset metadata) against
  official Git revision `7131e4375048a0e408a8fb404b5f499d726b695b` from
  https://github.com/harbor-framework/terminal-bench-2-1 . The fresh extraction
  is separate from the pilot. All frozen task-config hashes and 20 development
  IDs match. The historical cache lacks 89 `.gitignore` files and two metadata
  files, and `sanitize-git-repo/tests/test_outputs.py` differs. No old files or
  pilot results were changed. This audit compared bytes/hashes without showing
  hidden verifier or solution contents to policy development.
- The actual Terminus-2 prompt, parser, terminal session and completion loop
  passed a three-turn scripted-model fixture, then a three-call real-model
  fixture. The real agent created the expected file and emitted a trajectory.
  Charges reconciled at $0.000162; total setup spend $0.00019596, no pending
  requests. This is a synthetic setup task, not a benchmark score. The fixture
  used a four-turn / 2,048-output-token cap and disabled reasoning; these are
  fixture settings, not a frozen final baseline configuration. Retry decorator
  bypass remains an explicitly documented connection adjustment.
- Subsequent source hardening generates a random token for future live fixture
  use and journals each request before dispatch. The completed fixture predates
  those two changes: it used a local fixture token and saved responses/receipts,
  not exact outgoing request bodies. Do not claim multi-turn tokenizer
  calibration from those responses alone. The one-shot marker prevents replay.
- A disposable namespace-firewall fixture passed 10 checks: public HTTPS,
  known-live private-peer denial, local task service access, inability to alter
  firewall rules/create raw sockets, and no host home/control socket/key. Only
  the guard container had NET_ADMIN; no host/CETUS firewall rules were changed.
  All fixture containers and its network were removed. IPv6 and raw sockets
  remain unavailable in this candidate; all-task semantic compatibility and
  an adversarial isolation audit remain outstanding. This is not yet the
  production Harbor network adapter.

References for this local fixture design:
https://docs.docker.com/engine/network/ (container network namespaces) and
https://wiki.nftables.org/wiki-nftables/index.php/Configuring_chains (chain hooks).
Neither documentation nor a fixture pass establishes full-study completion.

2026-09-16 OpenHands integration milestone:

- Harbor 0.22.0's selected adapter invokes `openhands.core.main`. The latest
  OpenHands 1.11.0 package lacks that entry point, so its installation fixture
  failed before agent execution. The compatible legacy baseline is now pinned
  to OpenHands 0.62.0. Its three exact, declared prerelease dependencies are
  explicitly pinned in `fixtures/Dockerfile.openhands`; no package was patched.
- The first native-agent attempt (`openhands_agent_probe_v1.json`) was rejected
  because its client sends `max_completion_tokens`. The gateway now normalises
  this documented equivalent to `max_tokens` without changing its value, and
  rejects requests containing both aliases. Two regression tests cover this.
  Reference: https://openrouter.ai/docs/api_reference/parameters .
- The second attempt (`openhands_agent_probe_v2.json`) passed: actual native
  OpenHands used its shell tool to create the expected file, then finished,
  through the private socket relay in two scripted-model requests. The task
  had no external network, host home, upstream key or Docker socket. Containers
  and the dedicated volume were removed. No API credit was spent.
- `openhands_fixture_audit.json` inventories the exact image's installed
  packages and verifies post-run conversion into a six-step native trajectory.
  Its token counts are scripted fixture values, not provider measurements;
  native cost is absent. The inventory is not a hashed dependency rebuild lock.
- All 62 Stage 2 and 12 existing tests pass (74 total). No scored trial ran.
  Live-provider OpenHands qualification, scored-request cost bounds, production
  task isolation, custom harness and the remaining study gates are still open.

2026-09-16 custom backend milestone:

- Installed a separate custom-harness environment, leaving the qualified
  baseline environment unchanged: Deep Agents 0.7.14, LangGraph 1.2.11,
  LangChain 1.4.0, Harbor 0.22.0. `custom_dependency_inventory.json` records
  all 121 installed versions. Input requirements and a hash-locked resolution
  are separate from that observed inventory.
- `custom_backend.py` implements Deep Agents' sandbox filesystem/execute
  interface using only the supplied Harbor environment. Model paths are never
  opened on the Mac. Container-side foreground timeout, explicit output
  truncation, bounded file transfers, and async/thread bridging are covered.
- The first actual graph fixture failed file readback because Docker copy
  preserved host ownership. `custom_agent_probe_result.json` retains that
  failure. The backend now creates files through bounded, quoted commands as
  the container user. `custom_agent_probe_v2.json` passes all seven runtime
  checks: native file/execute tools, no delegation/planning tool, exactly three
  scripted replies, timeout, and quoted-path roundtrip. Disposable containers
  were removed. This is a real Deep Agents graph, not a paid model run.
- `custom_model.py` requires an explicit loopback gateway, explicit bounded
  output, one model, no SDK retry, and no Responses API/streaming. Two tests
  include the actual LangChain/OpenAI client through the real gateway and a
  synthetic ledger/provider. Nine backend tests also pass.
- This is NOT frozen C0: background job polling/interruption, equal bounded
  recovery, completion controls, fixed context policy and full run lifecycle
  still need implementation. No C1/C2 or scored custom results are claimed.
  All fixtures used scripted replies and spent no API credit.

Custom checks use `.tools/stage2-custom/bin/python stage2/custom_backend_tests.py`
and `stage2/custom_model_tests.py`, separately from the original test suites.
Reference: https://docs.langchain.com/oss/python/deepagents/backends .

Final checks for this increment: 62 Stage 2 + 12 existing + 9 custom backend
+ 2 custom client tests passed (85 total). Read-only OpenRouter verification
still reports $25.264980845 credit and $0.00019596 aggregate key usage. No new
paid requests were made. macOS reported no thermal/performance warning, 31%
memory free and 38 GiB disk available. No benchmark fixture container remains.

2026-09-16 custom controller milestone:

- `custom_control.py` implements C0/C1/C2 candidate prompt composition. C1
  adds only planning instructions; C2 requires an explicit C0/C1 parent and
  adds completion-check instructions/validation. Every condition has the same
  two-repair allowance and tool schema. No finalist has been selected or frozen.
- `custom_runner.py` runs the actual Deep Agents graph with explicit completion
  and abandonment, per-trial state, total timeout and no replay. Completion is
  labelled `agent_reported_complete`, never a verifier pass. C2 accepts no-edit
  tasks and records model-supplied observations; it cannot establish that those
  observations are true or exhaustive. The benchmark verifier remains decisive.
- The fixed candidate context policy retains graph conversation state between
  repair invocations, disables LLM summarisation and optional delegation, and
  uses identical filesystem middleware across conditions. Request/body/context
  exhaustion must fail closed rather than silently trim the baseline or input.
- A regression exposed that the library's graph-output call counter did not
  survive our repair reinvocation. A per-runner model-attempt limiter now spans
  every repair; provider/transport exceptions are not automatically retried.
- `custom_jobs.py` adds per-trial start/poll/interrupt handles, maximum four live
  commands and 64 total handles. Signals are executed only inside the container.
  Cleanup stops remaining jobs; the caller must always destroy the container,
  including on cleanup failure. Polling returns output once the command finishes.
- `custom_controller_probe_v1.json` passed nine actual-container checks. After
  output-capture hardening, `custom_controller_probe_v2.json` passed ten: a
  two-million-character command is drained inside the container with only a
  64,000-byte prefix retained, before Harbor/host capture. The previous backend
  truncated only after capture; the new implementation prevents that unbounded
  host-memory path. Command output remains an untrusted task observation.
- Seven pure control tests, six real-graph/controller tests and four job-guard
  tests supplement existing suites. These fixtures used scripted replies and
  made no paid API requests. `budget_qualification.md` explains why the scored
  spending gate remains closed. Full production runtime qualification, live
  integrations, experiment freeze, Langfuse delivery and scored runs remain.

Final candidate checks: 69 Stage 2, 12 existing, 9 custom backend, 2 custom
client, 6 custom runner and 4 custom job tests passed (102 total). The latest
container fixture passed all ten checks and left no running fixture container.
Read-only account verification still reports $25.264980845 credit and
$0.00019596 aggregate usage. No scored trial or new paid request ran.

2026-09-16 spending-bound investigation: three additional paid setup probes
now match the pinned tokenizer on Unicode history and native OpenHands tool
history with reasoning disabled/default. All three used the full-context
reservation and the original $1 setup ledger. Actual additional spending was
$0.00083352; aggregate setup spending is $0.00102948, with no pending requests.
No scored task ran. See `extended_token_calibration_result.json` for all eight
precomputed encoding candidates per request, matches, token usage and costs.

Calibration cannot establish a provider-guaranteed bound for arbitrary future
requests. `budget_qualification.md` now states the material decision explicitly:
an estimated per-trial cap would need risk acceptance and separate full-context
aggregate/stage reservations. No cap was raised and no estimate was enabled.

Final checks for the calibration increment: all 105 automated tests passed
(72 Stage 2, 12 existing, 9 backend, 2 client, 6 runner, 4 job guards).
Read-only account verification reports $25.264147325 available and matching
$0.00102948 aggregate key usage. The study remains paused before scored work.

2026-09-16 approved budget amendment implemented:

The user accepted conservative estimated per-trial admission while retaining
worst-case aggregate protection. Gateway/ledger now persist separate hard and
estimated amounts atomically. Project, stage and account checks still use the
full-context bound; trial checks use previous actual charges plus the estimate.
Any actual charge exceeding the estimate persists a halt across restarts.
Strict setup/pilot ledger behaviour remains the default. Estimation mode must
be explicitly enabled on a fresh scored ledger and cannot be changed on reopen.

`trial_estimator.py` provides the single shared `utf8-envelope-v1` estimator.
The offline receipt audit covers all three additional calibration cases, with
no new API call. See `budget_qualification.md` for the approved residual risk,
formula and integration contract. Scored-run wiring, full runtime qualification
and the remaining experiment gates still precede any benchmark launch.

Verification: all 115 tests pass (82 Stage 2 + 12 existing + 21 custom suites).
The estimate audit reused prior receipts and made no paid call. No new scored
ledger was funded and no benchmark started during this amendment.
