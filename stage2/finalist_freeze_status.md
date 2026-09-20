# Finalist freeze implementation, not an executed finalist selection

## Current implementation, 20 September 2026

The freeze now requires the exact canonical 20 development cells for each of
C0, C1 and C2. Their original pre-dispatch block registrations must match the
current source-qualified admission, registered limits, runner hash and C2
parent. Each original systemic review is independently revalidated; legitimate
differences in reviewer attribution or notes do not disqualify a valid block.
All three registration byte hashes are bound into the frozen document.

This closes a gap where caller-supplied diagnostic, repeat or older trial IDs
could substitute for selection evidence. Tests cover those substitutions,
source/admission/limit/parent/review changes, missing or symlinked registrations,
changed registration bytes after freeze, and both valid C2 parent choices.
The registered real limits are 100 model calls and two repair cycles, uniformly
applied across custom variants; common budgets and official deadlines remain
unchanged. No new scoring threshold or paid-runtime limit was introduced.

The gated development, diagnostic and final drivers are implemented, but their
real scored execution is incomplete. No real finalist freeze exists. The
following older checkpoints describe implementation history, not current gaps.

## Earlier implementation checkpoint

`finalist_freeze.build` reads all 60 unique C0/C1/C2 development result files,
freshly reaudits their canonical billing ledger, reruns registered selection,
and binds the choice to source, prompt/control, dependency-lock, budget, dataset
provenance and task-manifest hashes. It retains both preselected established
baselines: Terminus-2 and OpenHands. Its embedded runtime admission must pass
current host/image/model/source compatibility checks.

The explicit custom call ceiling must match `custom_execution_limits.json`,
with the common two-repair allowance. That real configuration has not been
created here: the development driver must register it before C0 starts, use it
unchanged for all custom variants, and include it in trial provenance. Synthetic
tests use a fixture ceiling only; they do not choose the study's limit.

Verification rechecks input hashes and result hashes, freshly reaudits receipts,
and recomputes the selection rather than trusting an editable winner field.
Exclusive durable saving refuses to overwrite an earlier freeze. The six tests
cover complete evidence, overwrite refusal, changed code/results/winner/limits,
and incomplete development blocks.

No real freeze document exists, no development results are invented, and this
does not authorize final expansion or establish superiority. Integrating the
registered development limits and freeze into the gated matrix driver, binding
the selected diagnostic block, and final execution remain pending.

## Final ordering implemented

`final_schedule.schedule` generates exactly 267 fresh final cells, one per
task/role, using sorted task IDs and rotating the order of Terminus-2, OpenHands
and custom for successive tasks. It rejects missing/duplicate/unsafe task IDs
and invalid custom parents. Final IDs cannot collide with development IDs.
The schedule code is included in the finalist freeze's file hashes.

Four synthetic tests and a read-only check against the actual 89-task manifest
passed for every supported custom configuration. The complete stage-two suite
passed 209 tests. This creates no trial directories and makes no API requests;
the final execution driver and its prerequisite gates remain pending.
