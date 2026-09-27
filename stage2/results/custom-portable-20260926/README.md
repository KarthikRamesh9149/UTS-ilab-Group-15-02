# Custom 0.3 development

C0 and C1 are complete and audited. C2 started on 27 September at 08:35 UTC.
It adds completion checks to C0, the parent selected from the complete C0/C1
results under the registered rule. No development attempt is replaced.

| Variant | Change | Result on the fixed 20 tasks |
|---|---|---|
| C0 | Control | 15 passed, 5 failed |
| C1 | Planning instructions added to C0 | 14 passed, 6 failed |
| C2 | Completion checks added to the selected C0 parent | Running |

The matched baseline scores remain Terminus-2 14/20 and OpenHands 10/20.
The observed C1 score is one pass lower than C0; one stochastic block does not
establish that planning caused the difference. C0's incomplete cost total is
not used for a cost tie-break. No full-benchmark improvement is established.

See the [C0 comparison](c0/README.md), [C1 comparison](c1/README.md),
[C1 per-task CSV](c1/trials.csv) and [C1 audited summary](c1/summary.json).
The [C2 launch snapshot](launch-c2.json) is a dated observation, not a live
counter. Earlier [C0](launch.json) and [C1](launch-c1.json) launch records are
retained unchanged. Both completed blocks have verified private off-server
backups; all 178 baseline and four stopped 0.2 result hashes remain unchanged.

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
[qualification metadata](qualification.json), [C0 registration](registration-c0.json),
[C1 registration](registration-c1.json) and [C2 registration](registration-c2.json).
