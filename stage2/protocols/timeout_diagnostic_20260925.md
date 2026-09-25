# Timeout and rate-limit diagnostic

Authorised on 25 September 2026 when the user asked us to establish how many
timed-out attempts would pass without API delays.

## What this can establish

Repeat all 30 original failed attempts which both timed out and recorded an
HTTP 429: 11 Terminus-2 attempts and 19 OpenHands attempts, across 25 tasks.
Give each exactly one fresh attempt. Count passes, failures, attempts with no
recorded API errors, and attempts still affected by API errors separately.

The original attempt cannot be rerun identically with time removed. The model
is stochastic, so a pass on a fresh attempt does not prove the first failure
was caused by rate limiting. This is a recovery diagnostic, not a causal
estimate or an improved 89-task score. Do not add repeat passes to the original
scores, replace failures, or keep retrying until a task passes.

## Conditions

- Same frozen tasks, native server, harness versions and qualified runtime.
- Same DeepSeek V4 Flash 0731 / DeepInfra FP8 endpoint, temperature 1, top-p 1,
  high reasoning and 384,000-token output allowance; no model/provider fallback.
- Same official task time, CPU, memory and verification limits.
- Sequential execution. Existing shared cooldown and transient retry behaviour
  are unchanged. A known cooldown is waited out before the next task begins;
  API waiting during a task still uses its official time allowance.
- No project/task dollar cap or reserve. Respect the provider's existing key
  credit limit. No top-up, new subscription or limit increase.
- Fresh IDs and a separate deployment. The engine calls its broad task-access
  phase `final`; the registration and all reporting label this as diagnostic,
  never final benchmark scoring.

We cannot force the provider to be rate-limit-free. A repeated attempt with
another API failure is not clean evidence of performance without API delays.
Successful requests can also be slow, even with no recorded error.

## Evidence and launch

The cohort is selected from all 178 original result/error metadata records,
not task instructions, solutions, hidden tests or output content. Preserve the
hash of every original result. Do not use this diagnostic to tune the custom
harness on the held-out tasks.

Before spending: check no runner or task container is active, validate the
unchanged source/image/host qualification, run the diagnostic regression tests,
and test both real harnesses against an isolated synthetic provider. Register
the exact cohort and all source bindings before the first real task starts.
Locks prevent overlap with old experiments. Started/interrupted attempts are
retained; only never-started cells may be resumed automatically.

Native deployment: `/opt/uts-capstone-timeout-diagnostic-20260925`.
Runner: `stage2/run_timeout_diagnostic.py qualify|run|report`.
The original corrected baseline remains untouched.

Reference: [OpenRouter rate-limit handling](https://openrouter.ai/docs/api_reference/limits).

## Verified launch

The first diagnostic attempt started on 25 September 2026 at 04:45:28 UTC.
The server service was active when checked at 04:46:09 UTC. Exactly 30 cells
were registered before dispatch; no diagnostic result was complete at that
checkpoint. This is a launch observation, not a final outcome.

The final candidate passed 68 targeted tests on the server and both native
harness fixtures, including injected rate-limit recovery, task checks and
cleanup. Those fixtures made zero paid calls. The full local suite ran 874
tests: 873 passed and one was skipped. All 178 original result hashes were
checked unchanged. See the [launch evidence](../results/timeout-diagnostic-20260925/launch.json)
and [registered cohort](../results/timeout-diagnostic-20260925/cohort.csv).

The server service is `uts-stage2-timeout-diagnostic-20260925.service`.
It runs independently of the Mac. The existing capstone follow-up now monitors
this diagnostic; it must not restart completed baseline experiments.
