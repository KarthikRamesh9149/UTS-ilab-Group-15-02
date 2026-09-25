# Corrected baseline results

Both baselines completed the same 89 frozen Terminal-Bench 2.1 tasks on the
rented native x86-64 Netcup server. There was one attempt per task and harness;
failed attempts were kept, not replaced. The last trial completed on
25 September 2026 at 01:08:35 UTC. Total wall time was approximately 51.16 hours.

| Harness | Passed | Failed | Pass rate |
| --- | ---: | ---: | ---: |
| Terminus-2 | 52 / 89 | 37 | 58.43% |
| OpenHands | 44 / 89 | 45 | 49.44% |

Both passed 39 tasks; only Terminus-2 passed 13, only OpenHands passed five,
and both failed 32. The eight-task difference is an observed result of this
experiment, not proof of general superiority or a statistically established
advantage. The custom harness has not yet been evaluated under this protocol.

## Shared settings and changes from earlier experiments

Both used DeepSeek V4 Flash 0731 through OpenRouter, pinned to DeepInfra FP8
without model/provider fallback: temperature 1, top-p 1, high reasoning,
384,000 maximum output tokens, one million maximum agent turns/iterations,
and the official per-task time and resource limits. There was no project,
stage or task monetary cap, reserve, price filter or billing-receipt admission
gate. The underlying provider's actual credit limit still applied.

The shared gateway retried undelivered transient errors within each task's
deadline and preserved provider cooldown across tasks. Earlier experiments
used an 8,192-token response allowance and different error recovery; they must
not be pooled with these results. We cannot isolate the contribution of each
changed setting. See the [protocol](../../protocols/corrected_baselines_20260923.md)
and immutable [launch record](launch.json).

## Failure evidence and limitations

| Recorded condition on failed attempts | Terminus-2 | OpenHands |
| --- | ---: | ---: |
| Agent time limit reached | 20 | 29 |
| API error | 7 | 0 |
| Startup/connection error | 0 | 6 |
| Failed checks, without one of those agent errors | 10 | 10 |

These are observed conditions, not proven root causes. Three Terminus-2
attempts passed despite an API error. Three attempts per harness passed
despite an agent timeout, because their final work satisfied the verifier.
All 178 attempts have binary verifier results; there were no verifier errors.

All 49 failed timeout attempts reached their full configured task deadline,
between 15 and 60 minutes; they were not cut off by a shorter project timer.
Thirty also encountered HTTP 429 rate limits (11 Terminus-2, 19 OpenHands).
Retry waiting uses the same task allowance, so these are not necessarily pure
model-capability failures. No counterfactual number of additional passes is
established. Six OpenHands startup/connection errors occurred before any saved
model request; their underlying cause remains unconfirmed.

The gateway recorded 5,190 physical model requests, 3,749 accepted model
responses, 1,394 HTTP 429 responses, and 1,395 retry-decision records. A retry
decision is not proof that another request was sent. Recovered errors are not
additional failed task attempts.

## Costs, files and preservation

Known response-reported cost subtotal: **US$2.37838734**, comprising
US$0.91992054 for Terminus-2 and US$1.45846680 for OpenHands. Cost information
was unavailable for 1,441 requests. The full billed total therefore remains
unknown; this subtotal is neither an independently reconciled receipt total
nor an account balance. Missing costs and token counts remain blank/null,
not zero. The separate prelaunch connection check is not included.

- [All 178 rows](trials.csv): scores, timing, errors, usage and result checksums.
- [Audited summary](summary.json): totals, frozen evidence bindings and backup proof.
- [Development-only baseline rows](development-baselines.csv): exactly the fixed
  20 tasks per harness, for later fair custom development. Do not tune custom
  policies from the other 69 tasks or their final-test diagnostics.

The completion audit checked registered identities, qualification and source
bindings, unchanged dataset bytes, predecessor result hashes, trace identities
and verifier rewards, model-access revocation, cleanup and successful service
exit. Private evidence was copied off-server; source-stream and downloaded
archive checksums matched, and all 178 archived result files matched their
audited hashes. The full runtime has not been restored from that archive.
Credentials, per-trial token files, raw transcripts and private archives are
not published. Exporting and backing up made no model API calls.

Earlier complete results remain separate: original capped 18/89 and 4/89;
provider-credit-only 3/89 and 1/89. The intermediate capped repeat stopped at
151/178 attempts (8/76 and 1/75); its 27 unstarted cells are not failures.
No completed experiment was restarted or overwritten.
