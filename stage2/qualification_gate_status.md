# Terminus development qualification gate

## Evidence-bound review implementation

`qualification_review.assess` now reaudits exactly the frozen first-20 cells
through the durable resume validator and binds the review to their exact result
hashes and model protocol. It requires attributed, explicit parser, routing and
environment findings with notes. Missing/stale review evidence is rejected;
any uncleared systemic finding blocks expansion. A clear review cannot override
the existing pass-count, budget-stop, billing or coverage thresholds.

This evaluator makes no model calls and does not create a favourable review.
No real first-20 model results or cleared review exist yet. The Mac's known
reference translation failures remain unresolved; paid execution is paused.
Integration into the later development-block driver remains pending.

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
