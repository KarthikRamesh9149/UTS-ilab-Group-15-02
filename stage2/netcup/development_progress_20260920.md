# First development block: partial execution checkpoint

**Superseded at 01:38 UTC:** the service stopped after a sixth retained outcome,
`reshard-c4-data` (reward zero, billing unresolved). Four billing-verified
outcomes include one pass; two outcomes now have unknown billing. Fourteen
tasks remain unstarted. No scoring process or Docker task container remains
running. See [the timeout incident](timeout_incident_20260920.md).
The following 01:23 UTC description is preserved as a historical checkpoint.
Offline runtime corrections invalidate the old source-bound admission for the
new candidate; no paid restart has occurred.

Observed 20 September 2026, 01:23 UTC on the native Netcup host. This is a
partial operational checkpoint, not a completed 20-task score, final-89
comparison or custom-harness win. The original service remained active and
owned the sequential first-20 Terminus run; no second matrix was started.

| Fixed task | Official reward | Billing status | Verified charge, USD |
|---|---:|---|---:|
| video-processing | 0 | Original historical hold, full charge unknown | Unknown |
| build-pov-ray | 0 | Verified | 0.00296814 |
| mailman | 0 | Verified | 0.00194538 |
| constraints-scheduling | 1 | Verified | 0.00182802 |
| overfull-hbox | 0 | Verified | 0.00139248 |

The first row still has its original known subtotal of $0.00037446 and
separate unresolved $0.106496 reservation. Neither represents its verified
complete cost. The four new completed trials cost $0.00813402 in total.
That figure excludes subsequent in-progress requests and cumulative setup.

`build-pov-ray`, `mailman` and `overfull-hbox` each recorded local budget-stop
markers. Repeated refused requests are not additional billed generations;
the qualification gate counts affected trials, not marker count. Three
affected trials already exceed the preregistered maximum of two, so the
current configuration cannot clear that expansion criterion, irrespective
of remaining task rewards. The authorised first-20 block continues to collect
its complete outcomes. No larger stage, replay or loosened limit is authorised
by this checkpoint.

The shared estimator reserves conservatively for the next request in addition
to actual earlier trial charges. A budget stop therefore does not establish
that $0.023 was actually charged or that account credit was exhausted. The
saved markers do not retain each refused request's full admission calculation;
an exact per-refusal numerical cause must not be claimed from them alone.

The host had approximately 14.6 GB available memory and 459 GB free disk at
01:18 UTC, and the active task relay and network guard were healthy. These
are point-in-time observations, not a promise of future availability.

## Reporting implementation verification

Commit `f3e227b` adds measured setup, agent and verifier durations to the
development exporter, with unknown-preserving summaries and 18 targeted
tests. Independent review found no actionable issue in that scoped change.
The subsequent complete local test run passed 465 Stage 2, 30 custom, two
graph callback and 12 legacy tests: **509 total**. These are implementation
tests, not benchmark passes. All 47 frozen paid-runtime source hashes remain
identical to `admission_netcupv6p.json`; reporting did not change model, agent
behaviour, tasks, limits, or the live qualification evidence.
