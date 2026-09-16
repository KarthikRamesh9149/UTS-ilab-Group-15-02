# Resumable first-20 runner

## Current checkpoint: frozen-image qualification

The full custom synthetic runner passed in `scored_runtime_probe_pinnedv2.json`.
It verified cleanup and preservation of the exact gateway/guard image IDs.
The earlier `pinnedv1` failure is retained: the host used the baseline Python
environment instead of the custom environment and lacked `langchain_core`.
No paid request was made in either synthetic attempt.

All three real-model rechecks passed in `native_live_*_pinnedv2.json` with the
same immutable images and model protocol. Their validated admission is
`scoring_admission_pinnedv2.json`. Historical v1 proofs used differing rebuilt
image IDs and cannot be combined into a current admission. Aggregate original
setup-ledger charges are USD 0.00463008 after these checks, not benchmark spend.

`build_admission.py` constructs and validates an admission from four explicit
proof paths. It does not spend, launch trials, replace an existing admission,
or waive missing/stale evidence. Reference qualification still has 15 passes,
four zero rewards and one timeout; those are not model scores and must not be
represented as a fully qualified environment. The paid runner has not started.
Infrastructure-only pattern inspection found HTTP 403 indicators in the
build-pov-ray reference log, and timeout indicators in both qemu reference logs.
These are diagnostic leads, not completed root-cause findings. No hidden
solution text or verifier assertions were exported into harness policy.

## Earlier implementation checkpoint

`run_qualification.py --admission PATH` now connects validated compatibility
evidence, native Terminus construction, real single-trial execution, receipt
reaudit on resume, and the paid-expansion decision gate. It runs only the frozen
20 development tasks, sequentially, and stops pending systemic trace review.
It does not automatically start OpenHands, custom development or final scoring.

The admission document must bind passed full-runner and three live native-agent
proofs to exact evidence hashes, current runtime sources, immutable Docker image
IDs and the same model settings. Required check names are validated; a generic
`passed` flag alone is not enough. Old fixture results without this provenance
are insufficient. No complete real admission document exists yet.

Completed zero-score trials are reused, not rerun. Interrupted attempt directories
require inspection. Existing results must match their task/condition/protocol,
and their billing artifacts are reaudited before reuse. A separate matrix lock
prevents duplicate schedulers; each trial also retains the existing host lock.

The pending Docker probe now records source hashes and rejects source changes
between module loading, lock acquisition and completion. Its waiting process was
refreshed without touching the active oracle run. The native OpenHands fixture
remains a subsequent step, not a concurrent job.

Verification: 164 stage-two tests passed. New tests cover qualified-admission
shape, stale/missing evidence, source/model/image drift, two-pass zero-result
resume without extra executions, interrupted-attempt refusal, and no execution
without admission. Synthetic test records are never used as actual qualification
evidence. The paid runner has not been launched.
