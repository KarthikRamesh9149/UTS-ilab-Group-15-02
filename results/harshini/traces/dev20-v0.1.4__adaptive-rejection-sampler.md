# Trace: `adaptive-rejection-sampler` (dev20-v0.1.4)

Exported from Langfuse by [`export_trace.py`](../../../experiments/harshini-deepagents/export_trace.py).

| | |
|---|---|
| Result | failed (reward 0.0) |
| Harness | uts-harshini-deepagents 0.1.4 |
| Stop reason | error |
| Model calls | 0 answered (2 s waiting on the model) |
| Failed model requests | 5<br>5× Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429, 'metadata': {'raw': 'deepseek/deepseek-v4-flash-0731 is temporarily rate-limited upstream. Please retry shortly, or add your own key to accumulate your rate limits: https://openrouter.ai/settings/integrations', 'provider_name': 'DeepInfra', 'is_byok': False, 'provider_error_code': 'engine_overloaded', 'limit_source': … |
| Tool calls | 0 (; 0 s) |
| Output tokens | 0 (0 of them reasoning) |
| Time split | model 100%, tools 0% |

| # | t (s) | Step | Action | Result / tokens | Took (s) |
|---:|---:|---|---|---|---:|
| 1 | 0 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.4 |
| 2 | 3 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.5 |
| 3 | 7 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 4 | 14 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.3 |
| 5 | 27 | model | | failed: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429,… | 0.7 |
