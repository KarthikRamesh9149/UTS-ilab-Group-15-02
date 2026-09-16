# Scored-request admission remains closed

Checked 2026-09-16. This records a remaining gate, not a new budget or permission
request. No scored request was sent to test an insufficient spending bound.

The current setup-only bound reserves the full 1,048,576-token context at the
gateway's maximum prompt rate of $0.10/million plus explicit maximum output at
$0.20/million. With 64 output tokens this is $0.10487040; with 4,096 it is
$0.10567680. Both exceed the approved $0.055 scored-trial cap before any work.

OpenRouter's `provider.max_price` filters provider unit rates. Its `request`
field addresses per-request pricing, not a universal total-inference dollar
cap. It is not a substitute for the local reservation ledger. Reasoning tokens
are billed as output and must be included in the output allowance.

Official references inspected:

- https://openrouter.ai/docs/guides/routing/provider-selection
- https://openrouter.ai/docs/guides/best-practices/reasoning-tokens

The existing local tokenizer matches two first-turn paid fixtures. That does
not qualify arbitrary multi-turn tool history, reasoning, response schemas,
or provider-template changes. Native OpenHands/custom scripted fixtures show
client shapes but their scripted token counts provide no billing calibration.

Next qualification work must establish and test a conservative supported-input
bound for the actual serialized request shapes, fail closed on unsupported
shapes, compare against real receipts within the original setup allocation,
and persistently halt on any underestimate. Do not silently reduce the
reservation, enlarge the trial cap, create another setup allowance, or start
the 20-task paid qualification while this remains unresolved.

## Extended live calibration, 2026-09-16

`extended_token_calibration_result.json` records three additional one-shot
requests charged only to the existing aggregate $1 setup ledger. Every request
reserved $0.10487040 before dispatch and reconciled its generation receipt.
Returned tool calls were not executed. No benchmark task was used.

| Synthetic fixture | Provider prompt tokens | Matching local encoding | Actual USD |
|---|---:|---|---:|
| Unicode multi-turn history | 50 | chat/low and thinking/low candidates | 0.00000336 |
| Native OpenHands tool history, reasoning disabled | 6703 | prepend-system chat/low (also merge-system thinking/low) | 0.00041172 |
| Native OpenHands tool history, default reasoning | 6782 | thinking/high candidates | 0.00041844 |

All candidate counts were computed before requests were sent; all candidates,
including nonmatches, are retained. Several layouts have identical counts, so
matching counts do not uniquely identify the provider's serialization layout.
Reasoning output was capped at 64 tokens for these accounting probes only.

Additional setup spend: $0.00083352. Aggregate setup spend: $0.00102948.
No pending request remained. This is calibration evidence, not a proven upper
bound for every future provider transformation or serialization change.

DeepInfra documents a token-count endpoint for its Anthropic-compatible API,
but it requires a DeepInfra credential, not the supplied OpenRouter key:
https://docs.deepinfra.com/integrations/anthropic . The OpenRouter key was not
sent to DeepInfra. OpenRouter's documented usage records are post-generation:
https://openrouter.ai/docs/cookbook/administration/usage-accounting . No usable
preflight count endpoint for this OpenRouter route was established.

## Decision needed before weakening the per-trial guarantee

Current policy stays unchanged. A possible amendment is to retain full-context
reservations for the aggregate/stage budget, while using a conservative local
estimate plus safety margin for the $0.055 per-trial admission check. It would
halt on any underestimate, retain actual charges, and prohibit automatic
replay. This does NOT guarantee the individual trial cap against unexpected
provider tokenization changes. It also requires separate global and trial
reservation accounting, which is not implemented or enabled here.

User acceptance of this per-trial estimation risk is required before that
amendment is implemented for paid scoring. It must apply equally to all three
harnesses. Without that amendment or a provider-verifiable input bound, scored
admission stays closed; more matching samples alone do not remove this issue.
