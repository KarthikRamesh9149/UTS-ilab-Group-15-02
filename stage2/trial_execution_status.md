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

## Single-trial wiring

`scored_trial.run_trial` now joins the canonical dataset, shared host lock,
private production Compose layout, resource/mount audit, host model bridge,
agent factory, shared phase executor and durable results. Its revocation callback
stops the gateway and checks Docker state before closing the host bridge. It
checks owned containers, networks and volumes after teardown. Existing attempt
directories, even interrupted ones, cannot be reused.

Six local tests exercise that wiring with mocked Docker/environment execution:
successful verification, audit failure, factory failure, leftovers, ownership
lock contention and mount rejection. They do not qualify the new wiring live.

The matrix still must supply qualified native factories and frozen model settings,
reconcile the canonical billing ledger, and halt on cleanup/ambiguous billing
failures. The module has no CLI or automatic launch. A real-container check of
this new orchestration remains required before paid scoring.

The installed OpenHands adapter supports a version and Python-version parameter;
its stock install path is in the adapter itself rather than a template file.
Production compatibility with the qualified 0.62.0 / Python 3.12 combination and
its pinned companion packages still needs verification on official task images.

## Verification

2026-09-16: the suite now has 169 local tests (127 stage-2 discovery, 12 existing,
9 backend, 2 model, 8 custom runner, 4 jobs, 5 custom Harbor adapter, 2 host
bridge). Stage-2 tests were rerun after single-trial wiring; the other 42 tests
passed on the unchanged relevant code earlier the same day. These include eight
shared-lifecycle tests. Provider and Docker mocks
in these tests are not live paid benchmark evidence.

The separate reference-solution run continues without model calls. Its current
metadata snapshot is `oracle_qualification_progress.json`; failed reference
rewards are retained, not replaced or treated as model scores.
