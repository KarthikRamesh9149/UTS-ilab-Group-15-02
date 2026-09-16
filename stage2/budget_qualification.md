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
