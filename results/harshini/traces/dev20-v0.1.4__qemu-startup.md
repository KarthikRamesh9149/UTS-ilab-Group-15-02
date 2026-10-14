# Trace: `qemu-startup` (dev20-v0.1.4)

Exported from Langfuse by [`export_trace.py`](../../../experiments/harshini-deepagents/export_trace.py).

| | |
|---|---|
| Result | failed (reward 0.0) |
| Harness | uts-harshini-deepagents 0.1.4 |
| Stop reason | deadline |
| Model calls | 0 answered (10 s waiting on the model) |
| Failed model requests | 19<br>19× Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429, 'metadata': {'raw': 'deepseek/deepseek-v4-flash-0731 is temporarily rate-limited upstream. Please retry shortly, or add your own key to accumulate your rate limits: https://openrouter.ai/settings/integrations', 'provider_name': 'DeepInfra', 'is_byok': False, 'provider_error_code': 'engine_overloaded', 'limit_source': … |
| Tool calls | 0 (; 0 s) |
| Output tokens | 0 (0 of them reasoning) |
| Time split | model 100%, tools 0% |

| # | t (s) | Step | Action | Result / tokens | Took (s) |
|---:|---:|---|---|---|---:|
| 1 | 0 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.4 |
| 2 | 3 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.7 |
| 3 | 8 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 4 | 17 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 5 | 31 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.9 |
| 6 | 58 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 7 | 119 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.6 |
| 8 | 182 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.6 |
| 9 | 241 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 10 | 301 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 11 | 367 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.5 |
| 12 | 421 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.6 |
| 13 | 476 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 14 | 527 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 15 | 599 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.5 |
| 16 | 669 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.5 |
| 17 | 740 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.5 |
| 18 | 810 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.6 |
| 19 | 877 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.9 |
