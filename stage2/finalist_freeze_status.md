# Finalist freeze implementation, not an executed finalist selection

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
