## Fixed-subset implementation and evaluation

Harbor 0.22.0 and Terminal-Bench 2.1 were configured on an Apple M5 MacBook Air. Qwen2.5-Coder-3B-Instruct and Qwen2.5-Coder-7B-Instruct were hosted locally through Ollama 0.33.2 as Q4_K_M packages (digests `f72c60cabf62` and `dae161e27b0e`) with a 32,768-token context. Host and container checks confirmed access to the same OpenAI-compatible local model service.

Mini-SWE-Agent, OpenHands, and custom UTS Qwen harness 2.2.0 were each assigned the same frozen 21-task subset for both model sizes, temperature zero, `k=1`, and concurrency one. Across 126 intended trial rows, 125 produced valid verifier results and 0 passed. Recorded agent exception types were: AgentTimeoutError, NonZeroAgentExitCodeError, RuntimeError. One custom-harness 3B command timeout produced no verifier result and is retained as an invalid, non-infrastructure outcome. Missing token fields remain unavailable rather than being reported as zero; no paid model endpoint was used.

This is a controlled local fixed-subset comparison, not a full Terminal-Bench 2.1 accuracy estimate. The full 89-task run was intentionally excluded from scope.
