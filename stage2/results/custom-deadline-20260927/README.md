# C3 development run

C3 completed all 20 registered development tasks at 18:22:57 UTC on
27 September 2026: **13 passes, seven failures and no missing verifier results**.
The audit, curated export and verified private off-server backup are complete.
The service exited successfully and all 160 execution source files are unchanged.

C3 keeps C0 as its preselected parent. The completed development scores are
C0 15/20, C1 14/20, C2 14/20 and C3 13/20. The matched baselines remain Terminus-2 14/20
(primary) and OpenHands 10/20 (secondary). Every version keeps its own results.

The registered whole-candidate ranking selects C0. All 80 original development
results and their original runtime identities are bound in a private, freshly
verified evidence freeze. This is not permission to run C0 unchanged: it still
has the old execution cutoffs. The authorised C0-NC revision needs its own
native qualification, fixed20 validation and final freeze. C3 did not improve
the observed score; this single comparison does not establish a causal reason.

## What changed

C3 adds remaining-time reminders, lets commands use the remaining official
task time by default, and removes background-job count and completion-repair
count cutoffs. This is a combined execution-policy change, not a claim that
one technique caused any later score difference.

There is no project/task spending cap, reserve or artificial model-call-count
ceiling. The unchanged model/provider, official task deadlines and resources,
actual provider constraints, finite output windows, isolation and cleanup
remain. One registered attempt is retained for each of the same 20 tasks.

## Checks before paid execution

- Local: 1,210 tests run, 1,209 passed and one pre-existing skip; 34 separate
  legacy tests also passed.
- Native: all 205 targeted tests and three real end-to-end synthetic cases
  passed, including long commands, 73 jobs, repeated repairs, cancellation,
  shared retry behaviour, tracing, revocation and cleanup. Zero paid calls.
- The first rehearsal failed because its test service expired before the
  verifier. That evidence is retained in [rehearsal-r1.json](rehearsal-r1.json).
  Only the synthetic fixture changed; benchmark limits and agent behaviour did not.
- Qualification, parent evidence, policy and registration have verified
  private off-server copies. Execution source `19051bd` binds 160 files.

## Evidence

- [Native qualification](qualification.json)
- [Whole-parent selection and original result hashes](parent.json)
- [Registered 20 tasks](registration-c3.json)
- [Uncapped accounting policy](credit-policy.json)
- [Verified launch snapshot](launch-c3.json)
- [Completed results and audit](c3/summary.json)
- [Per-attempt metadata](c3/trials.csv)
- [Original four-variant selection](original-selection.json)
- [Capture-failure metadata and synthetic diagnosis](c3/capture-observation.json)

The audit checked exact coverage, source/runtime bindings, official limits,
traces, model revocation, owned-resource cleanup and original result hashes.
The private backup contains 4,339 files; all 20 results and 185 bound files were
read and hash-verified. A full runtime restore was not exercised. The archive
is not published.

There were 554 recorded physical requests, including 548 accepted responses,
four interrupted requests and two errors. Two HTTP 429 responses were recorded.
Known response-reported cost is USD 1.00869792; six requests lack a known cost,
so the total is unknown and not independently receipt-verified. Of seven
failures, five had an agent timeout, one a capture-helper error and one no
recorded agent exception. Every outcome remains in the comparison.

The earlier confirmation60 and diagnostic20 are deferred under the direct-final
decision, not completed. The final 89 has not started. The revised finalist's
registration, native qualification, validation and final admission remain pending.
