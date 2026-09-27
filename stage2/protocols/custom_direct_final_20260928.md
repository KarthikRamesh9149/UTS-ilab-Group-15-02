# Route to the custom final 89

## User decision, 28 September Sydney time

The user asked for the best of C0, C1, C2 and C3 to run all 89 tasks after C3
finishes, with one attempt per task and no artificial execution or spending
cutoffs. The repeated C3 in the message is interpreted as C2 and C3, not an
additional candidate or a duplicate run.

The next main scored phase is the custom final 89. The previously planned
60-task confirmation and 20-task diagnostic are deferred, not completed and
not prerequisites for this route. Keep their unused schedules and the earlier
plan as history. Report that the separate confirmation and ablation evidence
was not collected; do not claim repeatability or isolate a causal design gain
from the single development comparison. This decision does not skip runtime
qualification or permit changing a running experiment.

## Selection and final execution

1. Finish the existing C3 block without changing its source, repeating a
   started task or overlapping another matrix. Audit and preserve all 20
   outcomes, including failures and missing results.
2. Apply the already registered whole-candidate ranking to all four audited
   development blocks: passes first, then the existing tie-break rules.
   Missing costs stay unknown. Never assemble each task's best attempt or
   promote C3 solely because it is newer.
3. Check the winner's actual execution contract against the user's no-cutoff
   requirement. Preserve the selected source and its lineage. C3 removes the
   old default command timeout, job-count quotas and completion-repair stop;
   the original C0/C1/C2 deployments do not. An older winner cannot silently
   acquire C3's runtime and still be presented as the same measured candidate.
4. If an older candidate wins, prepare a separately versioned, clearly labelled
   no-cutoff revision. Removing its execution rules changes the candidate:
   qualify the revision and validate it on the fixed development set under a
   separate registration before claiming its score or freezing it for final
   evaluation. Retain the original winner and every revised result. This is
   not permission for unlimited new variants or best-of retries. A development
   check needed for an altered finalist is distinct from the deferred 60/20
   confirmation and diagnostic matrices.
5. Freeze the actual finalist, implement the remaining source-bound final
   admission, and qualify that separately versioned deployment using the
   native synthetic model/Harbor/gateway/container/verifier path. Reuse only
   unaffected, still-bound evidence. No paid probe is needed merely to repeat
   already established provider access.
6. Inspect current processes and retained keys, then register exactly 89 fresh
   final cells with one attempt each. Use the fixed model/provider settings,
   official task deadlines/resources, sequential execution and shared retry
   policy. No replay of a started or interrupted cell. No tuning from final
   outcomes or held-out task content.
7. Audit all 89 intended outcomes, retain failures and missing verifier
   results, make one verified private off-server backup, and publish only
   curated metadata. Reuse the corrected baseline scores unchanged.

## Execution limits

No project or per-task spending cap, reserve, model-call ceiling,
physical-request-count ceiling, fixed 60-second command default, independent
one-hour command ceiling, background-handle quota or completion-repair-count
stop may be introduced in the finalist. An agent may deliberately choose a
shorter command timeout or decide to finish; the harness does not require it
to consume the entire task allowance.

This is not literally unlimited operation. Official task time, CPU and memory
remain fixed. Actual provider credit, authentication, rate and context limits
remain, as do finite tool-output and transfer windows, container isolation,
revocation and cleanup. Large files may be processed inside the container or
read in parts. Do not describe those remaining engineering bounds as benchmark
rules or claim they cannot affect behaviour. No automatic top-up, purchase,
account/key-limit increase or payment is authorised.

## Timing evidence, not a promise

At 14:41 UTC on 27 September (00:41 Sydney on 28 September), C3 was active on
its first task with zero completed results, 80 requests and 79 accepted
responses. All 160 frozen source files matched. That task's official agent
allowance is 3,600 seconds and had not expired at the observation.

The completed C0/C1/C2 blocks took approximately 5 hours 17 minutes,
3 hours 55 minutes and 4 hours 11 minutes respectively. With only one C3 task
underway, its estimate is weak: provisionally another 3–6 hours. The fixed 20
tasks have 12 hours 2 minutes 30 seconds of summed official agent allowances,
before setup and verification, so several long tasks could exceed that estimate.

The full 89 remains provisionally 24–36 hours after the finalist is qualified
and registered, using the corrected baselines as a rough reference. Allow
roughly 2–3 days overall for remaining development, final-run engineering,
native qualification, execution and audit. A revised older winner, provider
failures or new qualification defects can move the date. No deadline justifies
shortening benchmark limits or claiming unfinished checks passed.

No final selection, actual finalist freeze, final deployment or paid final
launch occurred when this decision was recorded. C3 continues independently
of the Mac. The final admission path still needs implementation.

## Local implementation checkpoint

`direct_final_candidate.py`, `direct_final_policy.py` and
`direct_final_gateway.py` implement the final gateway side, not a runnable
final study. They recompute whole-candidate selection, bind all 80 development
results, enforce the original full manifest and register 89 distinct final
identities. An older winner is rejected from the C3 execution path rather
than silently receiving different code. The final proof must bind the original
agent and selection sources plus the new admission sources. Only an explicit,
recorded change to trusted `scored_trial.py` orchestration is anticipated;
agent, prompt, tool, model and retry changes are not exempted.

The private freeze schema has a lightweight gateway reader with parity tests
against the original operator-side validator. This avoids requiring Harbor,
Deep Agents or the operator's SSH/audit code inside the gateway. The full
host-side evidence audit is still required; a self-consistent JSON record is
not proof that it happened.

The 27 new local tests include 105 accepted calls with unknown costs, 106
physical requests during shared 429 recovery, cooldown across tasks, provider
credit/authentication/identity stops, deadline/revocation, owner locks, no
restart, registration drift, changed source/protocol rejection and import
checks without the host-only dependency stack. All 95 affected tests passed.
The final full local suite ran 1,259 tests: 1,258 passed and one pre-existing
test was skipped. These tests use a fake provider and make no paid calls.

Still required: current-file and runtime authentication on the final host,
the explicit scored-runner integration, ancestor locks and dispatch, the
separate native synthetic qualification, pinned gateway image, exact private
registration and final exporter. The gateway contract does not bypass any of
these steps. No final deployment, native final qualification, real finalist
freeze or paid final launch was performed at this checkpoint.

## Original-native authentication checkpoint

`direct_final_evidence.py` now checks an operator freeze against a fresh audit
of the original C0/C1/C2 and C3 deployments. It checks the expected source,
qualification, registration, runtime archive and all 80 result hashes before
executing the unchanged original collector in its original native interpreter.
The collector retains its ancestor locks and validates the original task
limits, traces, service state, baseline hashes and cleanup. The returned
allowlisted metadata must reproduce the freeze, apart from its observation
timestamp. Files and stop markers are checked again before returning.

The authentication record is read-only and explicitly not paid admission.
It is intended to be created before the final runner takes the ancestor
locks; `recheck()` then verifies its file bindings under those locks without
trying to acquire the collector's locks recursively. Rechecking a self-created
record is not a replacement for performing the native audit. The eventual
final qualification must bind the authentication record, source and tests.

Twenty new local tests cover fresh-audit comparison, original source and
result bindings, changed files before/during an audit, altered scores and
metadata, older-winner identity, symlinks, persistent stops and sanitised
subprocess failures. All 115 affected tests passed. The full local suite ran
1,279 tests: 1,278 passed and one pre-existing test was skipped. Native reads
are mocked in those tests; file checks also use real temporary files.
No live native authentication, final freeze, qualification or paid launch was
performed. Current final-runtime authentication, runner integration, native
synthetic rehearsal and final export remain unfinished.

## Final-host identity checkpoint

`direct_final_runtime.py` checks the current deployment's source files,
loaded helper locations, interpreter, installed dependency versions, pinned
Python archive and native Linux host identity. It hashes the canonical dataset
and parses only task configuration, not instructions or solutions. All 89
official configurations and phase deadlines are retained, including allowances
longer than an hour. Declared storage is recorded, not claimed to have a new
storage-quota enforcement mechanism.

The image check uses the already audited baseline CSV and verifies all 178
original result hashes before reading their observed image IDs. Both baseline
harnesses must agree on each task's image and official agent allowance. Local
Docker image metadata must match those identities; this does not pull images,
start containers or repeat benchmark tasks. Missing original image evidence is
an error, not permission to substitute a current tag silently.

The final proof and registration now bind the runtime-identity hash. A later
locked runner must recheck it, authenticate the original selection separately
and require the actual native synthetic qualifier. Passing these readers, or
creating a self-consistent metadata record, is not paid-launch authorisation.
The final gateway remains C3-only and refuses an older winner until its
separate no-cutoff revision is validated. This checkpoint does not select C3.

All 27 new local tests and 134 affected tests passed. The full local suite ran
1,306 tests: 1,305 passed and one pre-existing test was skipped. The separate
legacy discovery ran 36 passing tests. A read-only local check also hashed all
1,037 canonical dataset files and parsed the 89 real task configurations.
These checks made no paid calls. A separate server metadata read confirmed
that all 178 original baseline result hashes still match and all 89 task image
identities are recorded consistently by both harnesses. No current-final-host
capture, actual finalist freeze, final deployment, native final rehearsal or
new paid launch occurred. Runner integration and final export remain pending;
the active C3 source is unchanged.

## Older-winner revision preparation

The separate [no-cutoff adapter](custom_no_cutoff_revision_20260928.md) implements
only the permitted runtime revision, without selecting an unfinished study's
winner. It retains the chosen whole parent's planning/completion-check choices
and omits C3's dynamic time advice. It reuses the unchanged deadline-governed
tools, jobs and completion controller under a distinct version and `-NC` label.
The original C0/C1/C2/C3 sources, results and registry admissions are unchanged.
Its native qualification, exact fixed20 study registration and measured
validation still need implementation. An adapter alone is not a paid-ready
experiment or a final selection.

## Completed C3 and original selection

C3 finished at 18:22:57 UTC on 27 September with 13 passes, seven failures and
no missing verifier results. Its exact20 audit, curated export and verified
private backup are complete. All original sources/results, official limits,
model revocation and owned-resource cleanup passed the audit. No C3 attempt
was replayed. The archive is private; its 20 results and 185 bound files were
hash-verified, not a full runtime restore.

The live original-evidence capture, exclusive private save and fresh verification
selected C0 over all four complete blocks: 15/20, 14/20, 14/20 and 13/20. The
freeze binds all 80 original results and preserves C0's actual 0.3 source and
runtime. It does not authorise paid final execution. The selected older parent
requires the labelled C0-NC revision described above; the C3-only direct-final
gateway correctly refuses to relabel that winner.

The C0-NC assembly also now includes a separately tested capture-transport
correction after the C3 metadata audit identified an early helper SIGTERM and
full-command process matching. The generic mechanism was reproduced without
the original task command, using only a harmless owned parent PID. Exact
original causation is not claimed. Native qualification of the changed
transport, separate fixed20 admission/validation and final89 admission remain
unfinished. The original failure remains part of C3's 13/20 score.

## C0-NC validation launch

The permitted C0-NC revision has now passed its separate native qualification:
238 tests and all three actual Harbor/graph/gateway/Docker/verifier rehearsals,
with zero paid qualification calls. Its one fixed20 validation started at
21:16:50 UTC on 27 September, under execution source
`06d94f75459f039d3b64c9139b28c732dd62231f` and a fresh `customdev4-c0-nc-`
registration. At 21:18:03 UTC the first task was active, with no completed
result. See the [launch evidence](../results/custom-no-cutoff-20260928/README.md).

This is the labelled development validation required by step 4, not another
original variant, an inherited C0 score, or the deferred confirmation/diagnostic
matrices. It has no artificial financial/request/command/job/repair-count
cutoff, but retains the official allowance and disclosed provider/transport
bounds. Freeze the actual measured revision after its audit. The final path
must explicitly authenticate this lineage and qualify its own orchestration;
the existing C3-only contract must not be bypassed. Final89 has not started.
