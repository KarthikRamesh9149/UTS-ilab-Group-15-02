# Shared HTTP 429 handling: offline candidate

Status: implemented and unit-tested offline on 22 September 2026. Not deployed,
not connected to the provider, and not a new scored experiment. The completed
baselines and their gateway remain unchanged.

## Contract

`rate_limit_candidate.plan_retry` is a pure function. It accepts an observed
HTTP status, the separate `Retry-After` header values, trusted clocks and trial
deadline, a consecutive-rejection count, lifecycle flags and a jitter sample.
It returns a typed retry/stop decision plus sanitised timing metadata. It does
not read credentials, make requests, sleep, start trials or inspect billing.
Results are immutable dataclasses with typed reasons; malformed trusted clocks,
lifecycle flags, rejection counts or jitter samples raise a sanitised
`ValueError`. Provider header errors return typed states, not raw error text.

- Only an actual HTTP 429 rejection is eligible. A body error inside HTTP 200,
  an ambiguous disconnect, 401, 402, 403 or another status is not retried by
  this candidate. A response already delivered to the agent is never replayed.
- Parse both integer delay-seconds and HTTP-date forms of `Retry-After`.
  Header text is untrusted and never copied into exported metadata. Conflicting
  duplicate values stop the decision rather than risk retrying too early.
  Header values longer than 256 characters or more than 16 duplicates also
  stop. The adapter must not turn these stop states into permission to dispatch
  another task immediately. Missing/malformed ordinary headers use the fallback.
- If the header is absent or malformed, use exponential backoff with jitter:
  a 5-second initial base, doubling to a 60-second base, and a sample between
  half and all of that base. A valid provider delay is never shortened by
  that cap. These are candidate settings, not a claim about the provider limit.
  A valid provider delay overrides the fallback; zero/past dates have a
  one-second minimum to avoid a hot loop. Dates round up to whole seconds.
- Retry waits count against the unchanged official task deadline. There is no
  separate monetary or retry-count allowance. Do not start a request if its
  wait consumes all remaining time. Recheck the deadline and revocation state
  after waiting and immediately before dispatch.
- The returned not-before time must also constrain the next task's first call.
  The integration must therefore own one shared cooldown for the fixed
  provider/model across both harnesses. A trial ending must not reset it.
  Persisted state must handle process restarts and host reboots: a monotonic
  timestamp by itself is not a portable expiry time.
- Each physical request needs its own immutable evidence record, linked to
  one logical completion. Never overwrite the first rejected call's record.
  Unknown costs remain unknown; a retry is not evidence that a charge was zero.
- Use identical shared transport handling for both baselines and any custom
  harness in a future comparison. Retrying a rejected API request inside one
  task attempt is distinct from restarting the benchmark task.

## Offline verification

80 tests passed, including 31 new policy tests plus existing transport,
credit-only gateway, experiment and completion-wait tests:

```sh
PYTHONPATH=stage2 .tools/stage2-custom/bin/python -m unittest \
  test_rate_limit_candidate test_openrouter_transport test_credit_only_gateway \
  test_credit_only_experiment test_completion_wait
```

The new tests exercise seconds/dates, duplicates, invalid input, long waits,
backoff and jitter, deadline boundaries, lifecycle checks, safe metadata and
absence of file/network/sleep side effects. Existing gateway tests use injected
clients and local loopback fixtures. No paid requests or benchmark tasks were
dispatched. Passing these checks does **not** qualify a live retrying gateway.

## Still required before live use

Wire the parser at the HTTP boundary, persist and enforce the shared cooldown,
make waits interruptible, and test the full gateway with a fake provider.
Verify immutable per-request accounting and unchanged model/provider/payload.
Then separately register and qualify any authorised new execution protocol.
Do not silently change or replay the completed 178-cell experiment.

References: [OpenRouter error handling](https://openrouter.ai/docs/api_reference/errors-and-debugging)
and [RFC 9110, Retry-After](https://www.rfc-editor.org/rfc/rfc9110.html#name-retry-after).
