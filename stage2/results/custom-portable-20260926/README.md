# Custom 0.3: qualified development run

The revised harness passed native setup qualification. C0 started on
26 September at 12:19 UTC on the same fixed 20 tasks. At the
[launch check](launch.json), the first task was running with nine accepted
provider responses and no completed result yet. This is not a benchmark score.

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
tasks. The full baseline scores stay 52/89 and 44/89. No custom accuracy win,
finalist freeze or whole-project completion is claimed.

See the [protocol](../../protocols/custom_portable_development_20260926.md),
[qualification metadata](qualification.json) and [C0 registration](registration-c0.json).
