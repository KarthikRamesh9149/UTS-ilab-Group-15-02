# Post-trial billing gate

`scored_accounting.audit_trial` opens the existing scored ledger read-only after
gateway teardown. It cannot create a ledger, release reservations, retry a model
request, or increase any allowance.

It checks the canonical aggregate/stage/estimated-trial policy, unresolved
requests, billing incidents, charges versus caps, trial stage, unique generation
identities, and one-to-one request/response/receipt evidence. Response and provider
receipt costs must agree exactly with the integer-nanodollar ledger entry.
Missing token metrics remain null, not guessed or replaced with zero.

`scored_trial.run_trial` now records this audit in its durable result. An otherwise
verified trial with failed billing checks is marked `billing_unresolved`; its
verifier reward is retained. The matrix must not advance from that state.

Eight local tests cover successful reconciliation, genuine no-request attempts,
missing ledgers/receipts, unresolved requests, matching-but-forged artifact costs,
stage mismatch, routing drift and extra evidence. The unresolved-request test
also verifies that the audit does not alter the ledger or release its reservation.

The queued synthetic Docker probe was refreshed before it started any container
so it loads this audit. Its eventual success requires both verifier success and
verified synthetic billing. No new credit allocation or live generation was
made for this implementation.
