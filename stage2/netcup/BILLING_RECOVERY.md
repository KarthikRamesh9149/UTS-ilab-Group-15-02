# Unresolved OpenRouter requests

## Additional stopped request, 20 September 2026

The continuation stopped on a second unknown request at approximately
**20 September 2026 01:27:16–01:28:24 UTC**, on the same model/provider/settings.
Trial: `dev-terminus-2-05-reshard-c4-data`.
Local request: `5464bb2d-0767-42ff-86d7-66b11ab737ad` (not a provider ID).
The preceding complete generation was
`gen-1789867430-CnN2r9EJ5IN1pky315wV`, charged USD 0.00168114. Its known receipt
has been recovered. The following request has no saved response or generation
ID, so its USD 0.106496 reservation remains unresolved. Do not infer its charge
from the aggregate key-usage difference or replay it. The one-historical-hold
amendment does not cover this request.

[Incident evidence and implementation correction](timeout_incident_20260920.md)
separate the verified duplicate dispatch from the inferred teardown mechanism.
Provider Activity evidence or an exact billing confirmation is still needed;
no password, API key or new credit is requested. The existing result remains
reward zero and cannot be replaced by a new attempt.

## Original historical request

This is a technical recovery handoff, not a benchmark result or a request to
buy credit. Do not send an API key, password or verification code in chat.

## Exact request to locate in the project's OpenRouter account

- Time: **19 September 2026, approximately 14:39:46–14:39:47 UTC**.
- Model: `deepseek/deepseek-v4-flash-0731`.
- Provider route: `deepinfra/fp8`, fallback disabled.
- Requested output ceiling: 8192; temperature 1; reasoning high; top-p 1.
- Local trial: `dev-terminus-2-00-video-processing`.
- Local accounting request: `03d8ac6c-f2c8-4e3a-9781-be9c8ddadf9f`.
  This is our identifier, **not** an OpenRouter request/generation ID.
- The previous two successful generations were
  `gen-1789828749-tkNrgh9lhqdj66lg1HqG` ($0.00014982) and
  `gen-1789828759-u4JNkd8GOr1sjV7kuN6w` ($0.00022464).
- The third request had no stored response/generation ID. Its exception
  reached the gateway as an unknown upstream outcome. Detailed upstream HTTP
  metadata was not retained by that version of the transport.

The account owner or OpenRouter support needs to identify that third request
and supply its request/generation ID and final billing outcome, or specific
confirmation that it was not charged. A private account activity export or
provider confirmation is sufficient information to investigate; credentials
are not needed in the conversation. No support message has been sent.

## What is already verified

The two successful generation receipts independently match their response
charges. At 14:53:07 UTC, the key's total usage was $0.00773598, exactly the
sum of known setup and scored charges, and available account credit was
$12.028551872. This suggests no additional charge was then visible, but does
not establish the individual missing request's settled outcome. No new
generation was sent to investigate it. The $0.106496 reservation remains in
the original ledger and is not reported as actual cost.

The original trial result has SHA-256
`f534d15c22f53a7de2df316372271f18a259a6387a13e0f7892eb2e3003ef541`.
It retains reward zero, agent `APIError`, verified cleanup and unresolved
billing. Nothing in recovery can change that reward or grant a new attempt.

## Recovery requirements

1. Match authoritative provider evidence to this exact failed request.
   Aggregate account balance alone, guessing an ID or replaying generation is
   not enough. The supplied project inference key is not a management key;
   the existing browser session belonged to a different personal account.
2. Record an immutable recovery sidecar and reconcile only the supported charge
   in the original ledger under the existing ownership locks. Preserve the
   original request, result and zero; never fabricate a missing response,
   receipt, token count or complete trace. The existing `reconcile_pending.py`
   intentionally cannot handle this ID-less, response-less case by itself.
   A narrowly tested evidence-specific recovery path is still required once
   the actual provider record is available.
3. Validate accounting and any audited resume sidecar independently. Do not
   rewrite `result.json` or let the matrix replay the failed cell. The present
   resumable runner correctly refuses its unresolved status.
4. Stop the dedicated observability services before timed work. Requalify the
   patched runtime and refresh its source-bound admission only after recovery.
   Then continue only missing permitted cells, within unchanged caps and gates.

The budget is not exhausted. Research success, the first-20 expansion gate and
the final matched comparison remain unproved.
