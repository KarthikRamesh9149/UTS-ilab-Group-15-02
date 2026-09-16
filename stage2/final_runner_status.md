# Full final evaluation runner

`run_final.py` consumes the verified finalist freeze and systemic review. It
uses the deterministic 267-cell schedule: all 89 tasks for Terminus-2, OpenHands
and the frozen custom condition. Task state is fresh because every final cell
has a separate, immutable identity; harness order rotates across tasks.

Before starting, the runner requires the frozen custom development evidence,
the first-20 qualification gate, all 20 OpenHands development results and all
20 registered diagnostic results. It reaudits the latter 40 results and binds
their hashes into an exclusive final-start descriptor. The descriptor also
binds the complete freeze, review and schedule. Configuration/evidence changes
reject resume. The finalist document itself is not mutated.

Between trials, the freeze and qualification are checked again. All harnesses
use the same model settings and scored trial limits. Existing valid zero
rewards remain in place; interrupted attempts require inspection, never replay.
The common matrix lock prevents concurrent runner launches.

Tests use mocked admission/execution and synthetic result files. They do not
prove live host qualification, task passes, accuracy superiority or completion.
No paid run was launched for this implementation. A compatible execution host,
actual development and final results, analysis and final artifacts remain due.
The final runner is included in the finalist implementation hash set.
