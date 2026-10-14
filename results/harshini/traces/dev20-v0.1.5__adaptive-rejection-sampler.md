# Trace: `adaptive-rejection-sampler` (dev20-v0.1.5)

Exported from Langfuse by [`export_trace.py`](../../../experiments/harshini-deepagents/export_trace.py).

| | |
|---|---|
| Result | failed (reward 0.0) |
| Harness | uts-harshini-deepagents 0.1.5 |
| Stop reason | deadline |
| Model calls | 0 answered (12 s waiting on the model) |
| Failed model requests | 19<br>19× Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429, 'metadata': {'raw': 'deepseek/deepseek-v4-flash-0731 is temporarily rate-limited upstream. Please retry shortly, or add your own key to accumulate your rate limits: https://openrouter.ai/settings/integrations', 'provider_name': 'DeepInfra', 'is_byok': False, 'provider_error_code': 'engine_overloaded', 'limit_source': … |
| Tool calls | 0 (; 0 s) |
| Output tokens | 0 (0 of them reasoning) |
| Time split | model 100%, tools 0% |

| # | t (s) | Step | Action | Result / tokens | Took (s) |
|---:|---:|---|---|---|---:|
| 1 | 0 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 1.0 |
| 2 | 3 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 3 | 7 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 4 | 16 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.4 |
| 5 | 34 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 6 | 62 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.4 |
| 7 | 131 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.5 |
| 8 | 188 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.8 |
| 9 | 251 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.6 |
| 10 | 301 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 11 | 362 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 1.3 |
| 12 | 425 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.6 |
| 13 | 491 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.5 |
| 14 | 553 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.6 |
| 15 | 605 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 16 | 658 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 17 | 714 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.4 |
| 18 | 768 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.8 |
| 19 | 838 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 1.7 |
