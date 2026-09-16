# Resumable first-20 runner

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
