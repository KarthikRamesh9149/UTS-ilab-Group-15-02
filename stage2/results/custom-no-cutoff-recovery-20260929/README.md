# Separate C0-NC setup recovery

Status: diagnosis and fixed plan published; separate setup observer implemented
locally. **0/3 recovery attempts started.** No native recovery qualification,
registration or paid admission has occurred.

## Current implementation checkpoint

The [instrumentation companion](../../protocols/custom_setup_recovery_instrumentation_20260929.md)
describes the new single-use observer and exact metadata contract. It executes
only the unchanged original preparation callback/command with its existing
180-second window. Returned nonzero codes, execution exceptions, context errors
and cancellation have distinct observations; arbitrary output/error text is
never retained. Missing code/output/timing stays unknown. A source failure or
capture gap is latched as incomplete, without replacing an executed outcome.

All 43 targeted observer tests and 134 affected checks passed. The tests use
synthetic environments, the actual shared phase engine and a guarded isolated
Python child, not Docker/native qualification or paid provider calls. The
observer does not create files, run a service, register tasks, hold admission
authority or implement durable no-replay protection across processes.

Final full discovery ran 2,683 tests: 2,682 passed and one pre-existing skip,
with unchanged hashes over 413 Python files before discovery, after discovery
and after execution. All 1,177 guarded regressions passed with zero skips,
errors or failures; final rereads covered 311 stage2 bindings and 199 loaded
project modules. The 12 repository tests passed. The three new component files
are current bindings, not retrospective additions to the original qualification
or archived 35-file reporter. The original seven diagnosis controls and all
five published original-result/recovery-metadata files remain byte-identical.

Review reinforced the immediate pre-command source/command check, preservation
of original context suppression and exception replacement, static field reads
without diagnostic property execution, and permanent source-refusal latching.
No speculative package fix or production evidence-check relaxation was applied.

It is not yet wired into `scored_trial.py`. The separate recovery policy/gateway,
actual original-audit/archive handoff, host/runtime/service, real native
qualification, scoped sequential admission and completed reporting/backup/export
remain required before launch. The actual future host must durably retain its
observations with new outcomes, including failure/cancellation, without replay.
The original runner, preparation/lifecycle, 35-file reporter and archive are
unchanged. Original counts were refreshed read-only at 15:36:40 UTC on
29 September: 89/89 complete, 50 passed, 36 verified failures, 3 missing verifier,
no active task. No new native recovery operation occurred.

## Retained diagnosis and fixed plan

The actual fixed reader at source commit
`7656915c3d50b97df1964f2802b9ddf67cca16ea` completed its read-only diagnosis at
15:22:15 UTC on 29 September. It strictly verified the same retained archive,
original result/source hashes, committed public outputs, private inventories
and final source/byte rereads. The [diagnosis](diagnosis.json) contains only
allowlisted metadata. This was a local archive inspection, not a fresh native
audit, qualification, deployment or provider call; nothing was extracted and
no archive was created or changed.

The [fixed schedule](schedule.json) has canonical SHA256
`dd46fb43239d1b84ffcf0e387c234f6f8df693852f18bdaeeb7a034bdc3cdd38`.
It is a plan, not a registration or admission witness. Both files preserve the
original null rewards and keep all three recovery outcomes unstarted.

The user authorised one fresh, separately reported attempt for original tasks
63-65 after the original89 audit and verified backup. Those prerequisites and
the original allowlisted export are complete. The original89 remain 50 passes,
36 verified zero-score failures and three setup-only missing outcomes; see the
[original results](../custom-no-cutoff-final-20260928/README.md).

Read-only retained archive inspection places each failure before environment
preparation returned, before agent setup and any model call. It does not reveal
the missing command exit/output/traceback or prove a package, network or SSH
cause. The [pre-launch amendment](../../protocols/custom_setup_recovery_20260929.md)
fixes three fresh identities, unchanged agent/model/official limits and the
existing preparation command. Native integration/qualification of the observer
and the actual source-bound service/dispatch/reporting route remain required.

Future recovery outcomes will be reported separately beside the original
failures, with denominator three. No guaranteed success, replaced rows, best-of
selection or merged retry /89 score is permitted. The baseline repeat schedule
remains unchanged. The original archive and archived reporting bundle are not
recreated, overwritten or extended.

## Diagnosis publication local validation (earlier checkpoint)

The final candidate ran 2,640 discovery tests: 2,639 passed and one pre-existing
skip, with before/discovery/after checks over 411 Python source files. All 1,134
guarded regressions passed with zero skips/errors/failures; the final check
matched 308 stage2 bindings and 197 loaded project modules. This includes all
43 new recovery tests. The 12 repository tests also passed. These checks use
synthetic private files, archives and mocked native observations, not native
qualification or recovery results.

Initial tests exposed an incorrect attempt to verify new diagnosis files at
the old archived reporter revision. The new current bindings were separated
from the unchanged historical bindings. Review also added explicit scheduling/
model helper and loaded-origin checks. Two draft wider runs passed their test
cases but correctly refused final source verification after concurrent review
edits; the stable final runs above passed every source check. No evidence check
or archived reporter source was weakened or changed.
