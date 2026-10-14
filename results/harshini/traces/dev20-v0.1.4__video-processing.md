# Trace: `video-processing` (dev20-v0.1.4)

Exported from Langfuse by [`export_trace.py`](../../../experiments/harshini-deepagents/export_trace.py).

| | |
|---|---|
| Result | failed (reward 0.0) |
| Harness | uts-harshini-deepagents 0.1.4 |
| Stop reason | deadline |
| Model calls | 0 answered (42 s waiting on the model) |
| Failed model requests | 61<br>61× Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429, 'metadata': {'raw': 'deepseek/deepseek-v4-flash-0731 is temporarily rate-limited upstream. Please retry shortly, or add your own key to accumulate your rate limits: https://openrouter.ai/settings/integrations', 'provider_name': 'DeepInfra', 'is_byok': False, 'provider_error_code': 'engine_overloaded', 'limit_source': … |
| Tool calls | 0 (; 0 s) |
| Output tokens | 0 (0 of them reasoning) |
| Time split | model 100%, tools 0% |

| # | t (s) | Step | Action | Result / tokens | Took (s) |
|---:|---:|---|---|---|---:|
| 1 | 0 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.4 |
| 2 | 3 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 1.2 |
| 3 | 8 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 4 | 18 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 5 | 37 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.6 |
| 6 | 72 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.4 |
| 7 | 123 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.7 |
| 8 | 192 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 1.1 |
| 9 | 256 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 1.2 |
| 10 | 325 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.8 |
| 11 | 389 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.6 |
| 12 | 457 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.8 |
| 13 | 530 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.6 |
| 14 | 599 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.6 |
| 15 | 663 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.6 |
| 16 | 724 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.5 |
| 17 | 792 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.6 |
| 18 | 844 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.6 |
| 19 | 915 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 1.1 |
| 20 | 977 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.5 |
| 21 | 1029 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 22 | 1088 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.9 |
| 23 | 1146 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 24 | 1202 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.7 |
| 25 | 1268 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.9 |
| 26 | 1321 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 27 | 1382 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.9 |
| 28 | 1436 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.4 |
| 29 | 1491 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.7 |
| 30 | 1560 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.6 |
| 31 | 1631 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 1.1 |
| 32 | 1690 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.5 |
| 33 | 1758 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.9 |
| 34 | 1815 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.8 |
| 35 | 1878 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.8 |
| 36 | 1940 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 1.1 |
| 37 | 1993 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 38 | 2048 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.7 |
| 39 | 2107 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.7 |
| 40 | 2178 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.9 |
| 41 | 2243 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.9 |
| 42 | 2309 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.7 |
| 43 | 2373 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.6 |
| 44 | 2441 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.5 |
| 45 | 2493 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.7 |
| 46 | 2549 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.5 |
| 47 | 2614 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.5 |
| 48 | 2676 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.7 |
| 49 | 2746 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.6 |
| 50 | 2819 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.9 |
| 51 | 2868 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.7 |
| 52 | 2939 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.6 |
| 53 | 3009 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.5 |
| 54 | 3067 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.4 |
| 55 | 3120 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.7 |
| 56 | 3192 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 1.0 |
| 57 | 3263 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.5 |
| 58 | 3329 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 1.8 |
| 59 | 3403 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.5 |
| 60 | 3466 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.6 |
| 61 | 3517 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
