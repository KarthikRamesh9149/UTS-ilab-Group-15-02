# Custom 0.3 development

C0 is complete: **15/20 passed**, with five failures and no missing verifier
results. On these same tasks, Terminus-2 passed 14/20 and OpenHands passed
10/20. This is an encouraging development result, not a confirmed improvement
on the full 89-task benchmark. C1 started on 27 September at 00:56 UTC to test
planning instructions only, without changing the model, task set or official
limits. The [C1 launch check](launch-c1.json) found one task in progress, six
accepted model responses and no completed C1 result yet. This is a launch
snapshot, not a live counter or a C1 score.

See the [C0 comparison](c0/README.md), [per-task CSV](c0/trials.csv) and
[audited summary](c0/summary.json). The initial [launch snapshot](launch.json)
is retained unchanged.

| Check | Result |
|---|---|
| Local test suite | 1,019 passed; one pre-existing skip |
| Separate legacy custom tests | 34 passed |
| Native targeted tests | 151 passed; no skips |
| Actual Harbor lifecycle rehearsals | All six passed |
| Paid model calls during qualification | 0 |
| Existing baseline results | All 178 hashes unchanged |
| Stopped custom 0.2 | All four results and original source unchanged |

The native rehearsals used the real custom graph, gateway, Docker environment
and verifier with a fake, network-isolated model. They covered all four
variants, a Python-less image, image-file messages, 16,000-line reads, editing,
command timeouts, background services, rate-limit recovery, cancellation and a
cooperative stop. The intentional cancellation correctly has no verifier score.

The earlier 20-image checks are reused only for unchanged container helpers.
Their source hashes and the Python runtime archive are bound into the new
qualification. No baseline or diagnostic task was rerun for this work.

Two preliminary synthetic rehearsals stopped at a fixture assertion. It was
counting the fixture's own image-creation command as returned attachment data.
The assertion and its regression tests were corrected; the final six rehearsals
passed on the bound source. Those failed fixture records remain private and
retained. They made no paid calls.

This is a new 0.3 experiment, not a replacement or best-of score for the
[stopped 0.2 run](../custom-development-20260926/README.md). It keeps the same
model, provider, task order and official limits. There is no custom spending
cap, reserve or artificial model-call ceiling. Actual provider credit,
authentication and identity safeguards remain.

Compare C0/C1/C2 with Terminus-2's 14/20 and OpenHands' 10/20 on these exact
tasks. The full baseline scores stay 52/89 and 44/89. No full-benchmark win,
finalist freeze or whole-project completion is claimed.

See the [protocol](../../protocols/custom_portable_development_20260926.md),
[qualification metadata](qualification.json), [C0 registration](registration-c0.json)
and [C1 registration](registration-c1.json).
