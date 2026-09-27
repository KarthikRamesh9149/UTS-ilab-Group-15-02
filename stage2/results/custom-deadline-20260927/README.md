# C3 development run

C3 started its fixed20 run at 13:47 UTC on 27 September 2026. At 13:50 UTC,
the first task was running with 12 accepted model responses and no completed
result. This is a launch snapshot, not a C3 score or a full-benchmark win.

C3 keeps C0 as its preselected parent. The completed development scores were
C0 15/20, C1 14/20 and C2 14/20. The matched baselines remain Terminus-2 14/20
(primary) and OpenHands 10/20 (secondary). Every version keeps its own results.

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

After the block finishes, retain and audit all results, including failures
and missing verifier outcomes. Compare whole variants before freezing the
finalist. Confirmation and final-89 admission still need separate implementation
and qualification. No final-89 run has started.
