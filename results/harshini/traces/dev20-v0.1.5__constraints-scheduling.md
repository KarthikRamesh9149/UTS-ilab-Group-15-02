# Trace: `constraints-scheduling` (dev20-v0.1.5)

Exported from Langfuse by [`export_trace.py`](../../../experiments/harshini-deepagents/export_trace.py).

| | |
|---|---|
| Result | failed (reward 0.0) |
| Harness | uts-harshini-deepagents 0.1.5 |
| Stop reason | deadline |
| Model calls | 0 answered (13 s waiting on the model) |
| Failed model requests | 23<br>23× Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429, 'metadata': {'raw': 'deepseek/deepseek-v4-flash-0731 is temporarily rate-limited upstream. Please retry shortly, or add your own key to accumulate your rate limits: https://openrouter.ai/settings/integrations', 'provider_name': 'DeepInfra', 'is_byok': False, 'provider_error_code': 'engine_overloaded', 'limit_source': … |
| Tool calls | 0 (; 0 s) |
| Output tokens | 0 (0 of them reasoning) |
| Time split | model 100%, tools 0% |

| # | t (s) | Step | Action | Result / tokens | Took (s) |
|---:|---:|---|---|---|---:|
| 1 | 0 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.5 |
| 2 | 3 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 3 | 7 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 4 | 15 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.7 |
| 5 | 30 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.6 |
| 6 | 63 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.8 |
| 7 | 115 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.4 |
| 8 | 187 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.5 |
| 9 | 259 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.9 |
| 10 | 311 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 11 | 378 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.7 |
| 12 | 442 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.5 |
| 13 | 499 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.4 |
| 14 | 549 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 15 | 603 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.4 |
| 16 | 675 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.6 |
| 17 | 742 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.6 |
| 18 | 808 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.5 |
| 19 | 875 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.9 |
| 20 | 931 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 21 | 984 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.8 |
| 22 | 1050 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.8 |
| 23 | 1116 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.6 |
