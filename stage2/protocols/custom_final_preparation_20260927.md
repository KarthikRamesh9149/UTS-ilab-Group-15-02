# Custom final-run preparation

The user requested a three-day target on 27 September and explicitly said not
to compromise quality. The working target is 30 September afternoon, Sydney
time. It is not a guarantee or permission to skip required checks.

## Schedule target

- 27 September: finish the registered development comparisons while preparing
  and testing the final-run code locally, without changing the active source.
- 28 September: freeze the selected candidate before confirmation, qualify the
  new deployment, complete confirmation and the diagnostic without changing
  that candidate, then register all 89 final cells.
- 29–30 September: finish the custom 89, audit the results and preserve the
  evidence off-server. Reuse the completed corrected baseline scores.

The full custom run is provisionally estimated at 24–36 hours, using the earlier
178 baseline attempts' approximately 51 hours as a reference. Custom behaviour,
task mix and provider latency can differ. If the earlier steps are not ready,
revise the estimate instead of weakening the checks. Do not launch overlapping
matrices to meet the date or silently omit confirmation or the diagnostic.

## Offline selection work

`portable_final_selection.py` consumes complete, already audited C0/C1/C2
summaries. It validates all 20 task identities and their order, exact trial IDs,
result hashes, binary or explicitly missing rewards, counts, costs and runtimes.
It recomputes aggregates instead of trusting supplied totals. The caller still
has to verify the underlying registration, source and result-file bindings.

Selection keeps the existing ranking: passes first, then cost only when every
compared block has a known total, simpler design, observed runtime and condition
name. C2 must use the parent selected from C0/C1 before C2 ran. A later unknown
C2 cost cannot retrospectively change that parent. The planned one-lever
ablation, or unchanged repeat when no retained lever increased passes, is kept.

Missing costs and verifier outcomes remain visibly missing. There are no
financial or request-count ceilings in this module. It does not claim an
efficiency win, select a best result for each task, freeze a deployment or launch
paid calls. It explicitly reports `paid_launch_ready: false`.

## Requirements before final execution

1. Complete and audit all registered development blocks. Retain every outcome,
   including the stopped 0.2 engineering run; do not replay started attempts.
2. Freeze the selected candidate and implement and qualify the source-bound
   confirmation/diagnostic path for passive accounting. Preserve the approved
   matched comparison and ablation rules; the old capped runners cannot be
   reused unchanged.
3. Bind the finalist, model/provider settings, runtime, dependencies, execution
   source and development evidence into the new deployment's immutable
   registration. Keep the selected candidate unchanged during confirmation,
   the diagnostic and final scoring. Do not select from incomplete blocks or
   use held-out answers for tuning.
4. Pass affected local checks and actual native synthetic rehearsals for the
   final launcher, including admission, duplicate prevention, accounting,
   cancellation, model-access revocation and resource cleanup. Reuse unaffected
   evidence only while its bindings remain unchanged.
5. Check current processes and retained keys, then register exactly one attempt
   for each of the 89 tasks before dispatch. Keep the same model, official task
   resources and deadlines, and shared provider retry policy as the baselines.
6. Audit the final 89 distinct cells, retain failures and missing results,
   verify a private off-server backup, and publish only curated metadata.

No new spending cap, reserve or model-call ceiling is introduced. Actual
provider credit, authentication and identity constraints still apply. There
are no automatic top-ups, purchases or account/key-limit increases.

The current paid development deployment is untouched by this offline module.
It is not yet a native-qualified final deployment, and the final 89 have not
started. No full-benchmark improvement is established.

## Verification on 27 September

- All 23 targeted selection tests passed, using synthetic metadata only.
- The final local Stage 2 suite ran 1,069 tests: 1,068 passed and one existing
  test was skipped. These are software checks, not benchmark scores.
- A read-only check accepted the actual native C0 summary and matched all 20
  result hashes to its saved audit. Its five unknown-cost requests remained
  unknown; no finalist was selected.
- No additional paid calls, qualification jobs or benchmark runs were launched
  for this change. The existing C1 job continued independently.

## Candidate freeze and schedule implementation

`portable_candidate_freeze.py` now captures the complete C0/C1/C2 development
evidence under the existing no-overlap locks. It rejects unfinished attempts,
an operator stop, remaining task containers, missing revocation/cleanup, changed
registrations, changed source files and disagreements between a summary and its
original result. Selection is recomputed from all 60 retained attempts. Only
allowlisted metadata is copied; no task observations or model exchanges enter
the document. Saving is exclusive and idempotent, never an overwrite.

The document binds the original qualification, dependencies, Python archive,
model, fixed task split, matched baseline export, all 60 result hashes and the
selection implementation and tests. It freezes the development candidate, not
the admission code of a future deployment. That deployment must separately
prove the candidate is unchanged and qualify its actual execution source.

`portable_evaluation_schedule.py` generates three separate, deterministic
schedules from that candidate document and the exact pinned input inventory:

- Confirmation: 20 tasks each for Terminus-2, OpenHands and the chosen custom
  variant, rotating harness order within each task. These are explicitly
  labelled new development repetitions, not replacements for the completed
  89-task baseline results.
- Diagnostic: the planned 20-task ablation or unchanged repeat. It cannot
  change the selected candidate or enter the final score.
- Final: 89 fresh custom attempts, starting with the fixed development tasks
  and then the 69-task complement in the original hash order. No baseline
  full-matrix rerun is scheduled.

The three schedules use distinct attempt IDs and keep sequential concurrency,
one attempt per cell and the official task limits. They do not grant paid
admission. The source-bound post-development runner and its native qualification
still need implementation; no real candidate freeze or final registration has
been created while development remains incomplete.

### Verification of the freeze and schedules

- All 58 targeted selection, freeze and schedule tests passed. The new tests
  use synthetic temporary evidence and explicitly mock native qualification,
  locking and Docker checks; they are not native execution evidence.
- The final local Stage 2 suite ran 1,104 tests: 1,103 passed and one existing
  test was skipped.
- At 03:36:52 UTC on 27 September, the existing C1 service was still running.
  A read-only check verified that all 127 bound execution-source files were
  unchanged. No additional scored job or native qualifier was launched for
  this implementation.

## Original-evidence binding after C3

`deadline_evidence_freeze.py` adds operator-side capture, verification and an
exclusive private save for the four-variant candidate. It does not modify a
study deployment. The reader reuses C3's exact qualified metadata collector,
which takes all ancestor locks and audits the original 20 C3 results, 60
predecessor results, registrations, source hashes, official limits, traces,
revocation and cleanup. Active or incomplete execution cannot supply a freeze.
Persistent operator stops are checked before and after the audit.

The reader checks the public qualification projection against the complete,
hash-bound private qualification copy. This prevents an edited dependency or
source field in a summary from being treated as original runtime evidence.
It also binds the policy's original file bytes, all original result hashes and
the operator's selection code and tests. It copies only allowlisted metadata;
no task observations or model exchanges enter the candidate document.

The selected execution record explicitly retains the winning generation:
C0/C1/C2 use their original 0.3 source and dependencies; C3 uses its original
0.4.1 source and dependencies. Selecting an older winner cannot silently swap
in C3's execution policy. Unknown costs stay unknown, missing verifier rewards
stay in the denominator, and a document cannot grant itself paid admission.

`capture()` audits without saving. `save()` writes once to the operator's
private `.runtime/finalisation/four-variant-candidate-freeze.json` and is
idempotent only when the original evidence and selection code still agree.
`verify()` performs a fresh original-file audit; structural JSON validation
alone is not sufficient. The audit timestamp may advance without changing
the frozen evidence. An existing freeze is never replaced after a change.

This implementation was tested with synthetic completed evidence and mocked
SSH responses. All 82 affected tests passed, including 22 new tests. The full
local suite ran 1,232 tests: 1,231 passed and one pre-existing skip remained.
A local check also matched the
real saved qualification's source and dependency projection, without contacting
the server or creating a freeze. The active C3 study and its 160 execution
source files were not edited. Actual capture must wait for all 20 C3 outcomes.
Paid confirmation, diagnostic and final-run admission and native rehearsal
remain separate, unfinished work.

The original collector requires recorded phase durations. A result missing a
phase duration stops this freeze path; it is not assigned a fabricated zero or
discarded. Such an outcome would need a separate reporting amendment, not a
task replay or an edit to the frozen study.
