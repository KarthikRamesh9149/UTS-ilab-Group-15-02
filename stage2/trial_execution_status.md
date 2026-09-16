# Shared scored-trial lifecycle checkpoint

The shared `execute_phases` implementation is tested but is not yet wired into
an end-to-end paid matrix. No benchmark win is established by these tests.

## Implemented

- Explicit setup limit and official task agent/verifier limits.
- Agent timeout or exception retains the attempt and still invokes verification.
- Model access must be revoked successfully before verifier preparation or upload.
- Verifier preparation is included in its phase timeout.
- Custom background jobs remain available until verification completes.
- Cleanup attempts model revocation, post-verifier agent cleanup and environment
  destruction, including cancellation during the agent phase.
- Error types are retained without copying potentially sensitive exception text.

## Caller responsibilities still to integrate

Validate phase limits before allocating resources. Acquire the host trial lock,
start and audit the guarded task and gateway, provide the correct native agent,
and make revocation actually terminate gateway access. Persist results and
cancellation evidence, reconcile the canonical billing ledger, and independently
inspect Docker to confirm teardown. Cleanup exceptions must halt the matrix.
The module alone does not prove container destruction or reconcile receipts.

The installed OpenHands adapter supports a version and Python-version parameter;
its stock install path is in the adapter itself rather than a template file.
Production compatibility with the qualified 0.62.0 / Python 3.12 combination and
its pinned companion packages still needs verification on official task images.

## Verification

2026-09-16: all 163 local tests passed (121 stage-2 discovery, 12 existing,
9 backend, 2 model, 8 custom runner, 4 jobs, 5 custom Harbor adapter, 2 host
bridge). These include eight shared-lifecycle tests. Provider and Docker mocks
in these tests are not live paid benchmark evidence.

The separate reference-solution run continues without model calls. Its current
metadata snapshot is `oracle_qualification_progress.json`; failed reference
rewards are retained, not replaced or treated as model scores.
