# Next baseline experiment: provider credit only

The user explicitly authorised this experiment on 22 September, **after the
current repeat**. It has not started. The current running experiment must not
be modified or overlapped.

Run all 89 frozen tasks once for each of Terminus-2 and OpenHands, using the
same model/provider and nonfinancial evaluation limits. Total: 178 fresh task
attempts. Keep every prior experiment separate; do not replace an old failure
with a new pass or combine runs into a single score.

Unlike the current repeat, this experiment must have **no project-imposed
monetary limit and no credit reserve**. Old cost reservations, estimated
request costs and missing billing receipts must not prevent requests. Record
all attempts and known charges, and mark missing costs unknown. These records
are for accounting, not permission to continue. A usable, correctly routed
model response must not be rejected merely because its billing metadata is
missing. Authentication, model/provider integrity, isolation, official time
limits and resource limits remain enforced.

Actual provider credit exhaustion is different from an internal budget gate.
When the provider rejects a request for insufficient credit, stop further
dispatches and notify the user. Do not purchase a top-up automatically, retry
the same charge-ambiguous request automatically or count never-started tasks
as failures. After a user-funded top-up, only unstarted task attempts may
continue under the same frozen configuration.

The existing `run_baseline_repeat.py` does **not** implement this policy and
must not be reused by simply changing its numeric ceiling. Prepare a separate
gateway with passive accounting and test that missing receipts, old pending
calls and high request estimates cannot produce internal budget rejections.
Qualify the changed path with offline tests and an isolated synthetic runtime
test before any paid launch. Preserve the current runner until its terminal
state and confirmed cleanup; if it ends short of 178, record that partial
coverage honestly before starting the new experiment.

The machine-readable authorisation is
`next_baseline_credit_only_20260922.json`. It is a queued instruction, not
evidence that the new runtime is implemented or qualified. The existing
heartbeat owns the conditional handoff; no second concurrent runner is allowed.

Implementation checkpoint: the separate gateway and runner now exist and passed
native offline tests. They are **not yet runtime-qualified or started**.
See `credit_only_preparation_20260922.md` for the 22 September checkpoint and
the remaining handoff steps. The JSON above remains the original authorisation
record, not a live status file.
