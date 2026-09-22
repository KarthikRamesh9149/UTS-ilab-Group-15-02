# Uncapped baseline results: 22 September 2026

Both baselines finished all 89 frozen Terminal-Bench 2.1 tasks on Netcup.
The model remained DeepSeek V4 Flash 0731 through the fixed DeepInfra FP8
endpoint. Harbor, native harnesses, task files and official time/resource limits
were held constant. There was one attempt per task and harness, with no project
monetary caps or reserve. The run took approximately seven hours.

| Harness | Passed | Failed | Pass rate |
| --- | ---: | ---: | ---: |
| Terminus-2 | 3 | 86 | 3.37% |
| OpenHands | 1 | 88 | 1.12% |

These are complete recorded outcomes, but **not a clean measure of model or
harness capability**. Of 403 model requests, 171 received HTTP 429 responses.
OpenRouter documents 429 as rate limiting, distinct from insufficient credit.
[Official error reference](https://openrouter.ai/docs/api_reference/errors-and-debugging).

The frozen gateway stopped further model calls within an attempt after its
first transport failure; it did not retry those requests. This affected 87
Terminus-2 attempts and 84 OpenHands attempts, including some that still passed
the verifier. Another five OpenHands attempts recorded `NetworkConnectionError`
and made no saved model request. The exception class alone does not establish
their underlying cause. No provider-credit stop was recorded.

Removing monetary caps did not improve these recorded scores. The evidence
does not show that low model ability caused every failure, or that budget caps
help accuracy. Rate limiting and the no-retry policy are major limitations.
The saved diagnostics do not establish the precise rate-limit scope or the
required waiting interval.

## Earlier runs, kept separate

| Experiment | Terminus-2 passes / attempted | OpenHands passes / attempted |
| --- | ---: | ---: |
| Original capped run, complete | 18 / 89 | 4 / 89 |
| Capped repeat, stopped early | 8 / 76 | 1 / 75 |
| Provider-credit-only run, complete | 3 / 89 | 1 / 89 |

The capped repeat left 27 intended cells unstarted. No results were replaced,
pooled, or selected as the best of multiple attempts.

## Costs and evidence

Response-reported known cost subtotal for **this run only**: **US$0.07185378**.
Cost data was missing for 171 requests, so the complete billed total remains
unknown. Missing amounts were not changed to zero. This is not an account-wide
spending reconciliation or an independently receipt-verified total.

- [178 trial rows](trials.csv): scores, call counts, rate-limit counts, token counts, costs and result hashes.
- [Machine-readable summary](summary.json): per-harness totals and separate historical scores.
- Audit: 178 unique cells, exactly 89 per harness, binary verifier results for
  every cell, complete cleanup, matching qualification evidence and unchanged
  predecessor result hashes. No active benchmark containers remained.
- Private evidence and historical results were copied off-server and their
  archive checksums verified. The API-key file and per-trial token files were
  excluded; raw prompts, responses, logs and private backups are not published.
- Exporter regression checks: eight tests passed. Exporting made no API calls.

The next technical step is to qualify consistent rate-limit handling for both
baselines before any further scored experiment. This audit did not change the
frozen runtime or rerun tasks. Custom 20-task development and frozen custom
89-task scoring remain unfinished; a custom-harness win has not been shown.
