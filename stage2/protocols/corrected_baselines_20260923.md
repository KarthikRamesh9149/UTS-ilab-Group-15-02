# Corrected baseline experiment

Authorised on 23 September 2026 (Sydney). This is a fresh experiment, not a
repair of saved scores. The previous provider-credit-only run already finished
178 attempts and remains immutable. The corrected run has its own source,
qualification, registration, service and result directories.

## Scope and fair limits

- All 89 frozen Terminal-Bench 2.1 tasks, once for Terminus-2 and once for
  OpenHands: 178 intended attempts, sequentially, retaining failures.
- Same DeepSeek V4 Flash 0731, fixed DeepInfra FP8 endpoint. No fallback model.
- No project, stage or task dollar allowance; no reserve; no provider price
  filter; missing receipts and uncertain charges do not gate new requests.
- Both baselines use the provider-advertised maximum output allowance of
  384,000 tokens, temperature 1, top-p 1 and high reasoning. The earlier run
  used 8,192 output tokens, so its scores are a separate experiment.
- Official task wall time, verifier, CPU and memory remain unchanged. Both
  harnesses have an effectively unreachable 1,000,000-turn guard; this replaces
  OpenHands' default 100 iterations and matches Terminus' native default.
  This is not literally infinite execution. Model context, HTTP framing and
  host security safeguards remain in force.
- Real provider credit exhaustion ends dispatch. There is no automatic top-up,
  account-limit increase or purchase. No result or harness win is guaranteed.

## What changes

The previous run recorded 171 HTTP 429 responses and stopped model interaction
in each affected task. The new shared gateway honours Retry-After and retries
undelivered transient failures within the same task's official deadline. It
does not restart the task or replay a delivered completion or tool action.
Authentication, genuine credit exhaustion and wrong model/provider identity
are not retried.

Every physical request has a distinct immutable record. Logical completions
link those records. Unknown costs remain unknown. A shared cooldown survives
gateway restarts and task boundaries; a task cannot evade a provider wait by
ending. The runner waits for an inherited cooldown before starting the next
task's clock.

Native baseline prompts, tools, context handling and decision loops are
inherited. The custom harness is not involved in this baseline run. Any later
custom comparison must use this same declared evaluation protocol.

## Launch requirements

1. Full native unit suite and gateway-image tests pass on the rented x86-64
   server. Source and parent-image hashes are bound to the evidence.
2. Actual Terminus-2 and OpenHands complete a simple file-writing fixture
   through the new gateway, recovering from a deliberately injected 429.
   No real API key or paid model is used for these tests. The fixture uses the
   same 1 CPU / 2 GiB image configuration as a previously failed startup.
3. One separately logged real-provider connection check succeeds with the
   corrected settings. It is not one of the 89 benchmark tasks.
4. Register 178 unique cells before starting the matrix. All prior deployment
   locks are held to prevent concurrent old/new matrices. Never automatically
   replay an interrupted or completed cell.

Implementation: `qualify_corrected.py`, `check_corrected_provider.py`,
`run_corrected.py`. Native root: `/opt/uts-capstone-corrected-20260923`.
Registration: `.runtime/stage2/corrected-matrix.json`.
Private requests, responses and credentials stay out of GitHub.

## Evidence status

The corrected matrix started on 22 September 2026 at 21:58:52 UTC (23 September
in Sydney). All 178 unique cells were registered before its first task. The
server service is `uts-stage2-corrected-20260923.service` and continues without
the Mac staying awake. See [launch evidence](../results/baseline-corrected-20260923/launch.json).

The native 840-test suite passed with one optional spending-PDF dependency
skip (839 executed successfully). All 62 gateway-image tests passed. Both
actual native harnesses passed their file-writing, injected-429 recovery,
verifier and cleanup fixtures. OpenHands successfully started on the previously
affected environment; the historical intermittent startup cause was not
reproduced or established, so no speculative dependency patch was applied.

The live-provider connection check succeeded on one request, reporting
US$0.00001212 in response usage, 25 prompt tokens and 59 completion tokens.
That figure is not an independently reconciled receipt or the run's total.
The first actual task received four usable responses before a later request
remained in progress. Launch is verified; benchmark completion and passing
scores are not yet established.

The read-only live page at `http://127.0.0.1:8769/` now uses
`corrected_progress.py`. Its 18 dashboard/regression tests passed. It keeps
completed attempts, passes, failures, missing scores and stale snapshots
separate. It reads result metadata over SSH, never model APIs or credentials.

The API/interface-design skill informed the explicit retry/lifecycle contract,
sanitised errors and additive gateway; completed experiment code was preserved.
The build-dashboard skill informed the compact progress layout, adapted to the
requested live feed rather than a point-in-time snapshot.

References: [OpenRouter errors](https://openrouter.ai/docs/api_reference/errors-and-debugging)
and [HTTP Retry-After](https://www.rfc-editor.org/rfc/rfc9110.html#name-retry-after).
