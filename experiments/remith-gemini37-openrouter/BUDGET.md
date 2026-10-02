# Remith Gemini OpenRouter Budget Ledger

## Scope

- Planned subset: 20 Terminal-Bench 2.1 tasks
- Planned harnesses: Terminus-2, OpenHands, and the custom harness
- Planned trials: one trial per task for each harness unless the team later
  agrees on a different `k` value
- Model: `google/gemini-3.7-flash` through OpenRouter

## Recorded Usage

| Category | Tokens | Cost | Status |
| --- | ---: | ---: | --- |
| Oracle smoke | Not applicable | Not applicable | Oracle does not call an LLM |
| Terminus-2 attempts | Unavailable | No successful model call confirmed | Authentication failed before task work |
| OpenHands attempts | Unavailable | No successful model call confirmed | Setup/authentication failure |
| Custom harness attempts | Unavailable | No successful model call confirmed | Authentication failed before task work |

## Accounting Rules

- Do not infer cost from Harbor reward or exception count.
- A `0.0` reward with an authentication exception is not a benchmark result.
- Record prompt tokens, completion tokens, request cost, and model ID only from
  a completed valid trial or an OpenRouter billing record.
- API keys, raw job folders, and private provider metadata are excluded from
  Git history.

## Current Budget Status

No valid Gemini benchmark cost or token total is available yet. The account
owner should confirm any provider-side usage in OpenRouter before the 20-task
run. The experiment is not ready for the full subset.
