# Terminus development qualification gate

The client plan requires the first 20 development trials to use Terminus-2.
These are part of the 120 planned development cells, not additional spending.

`qualification_gate.evaluate` now checks exactly those 20 unique tasks, the
Terminus/development condition, common model fingerprint, binary verifier
rewards, completed cleanup, reconciled charges and complete usage evidence.
Expansion requires at least 10 verified successes, at most two trials with
budget stops, and an explicit completed systemic-failure review. Duplicate,
missing, replaced, wrong-condition or incompletely audited cells do not pass.

The gateway persists each BudgetExceeded event without storing request bodies or
inventing a charge. The read-only billing audit reports its count. Multiple
budget events in one trial count as one budget-exhausted trial for qualification.
Billing incidents or unresolved requests still halt independently.

Native factories now identify their harness and model-protocol fingerprint;
the runner records these and rejects mismatched factory/gateway settings.
This function is a tested decision gate, not a completed matrix scheduler or
evidence that qualification has passed. The systemic review must be grounded
in actual traces; callers must not blindly set its review flag to true.

Verification: 155 stage-two tests passed. Seven gate tests cover threshold
boundaries, task completeness, duplicate/wrong conditions, missing evidence,
protocol drift and required review. A real local ledger test confirms budget
refusal is recorded as zero generation calls and zero charge, not lost.
No live OpenRouter requests were made for this checkpoint.
