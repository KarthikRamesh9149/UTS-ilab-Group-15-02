# Setup notes

The live run uses Harbor 0.22.0, Ollama 0.33.2, Docker CLI 29.7.2, Docker Engine 29.5.2 through Colima 0.10.3, and checksum-verified Docker Compose 5.4.0. All downloaded tools and model weights remain in ignored `.tools/` and `.cache/` directories.

The model server contains the Q4_K_M Ollama packages `qwen2.5-coder:3b` (digest `f72c60cabf62`) and `qwen2.5-coder:7b` (digest `dae161e27b0e`). It is configured with a 32,768-token context, keep-alive enabled, one parallel request, and a host bind required for `host.docker.internal` access from Colima. It is not exposed through a public tunnel.

Harbor 0.22.0's installed integration source was used to resolve current argument names. Mini-SWE-Agent receives a 25-step configuration file and `max_tokens=4096`; missing local price information is ignored. OpenHands 0.61.0 on Python 3.12 receives `disable_tool_calls=true`, `reasoning_effort=none`, `temperature=0`, `max_iterations=25`, and explicit 32K/4K token limits. Both baselines receive the same dummy local key and endpoint.

The custom harness uses a strict JSON action contract, phase-aware prompting, a 25-step budget, rolling context, bounded command execution, repeated-command and destructive-command guards, explicit artifact checks, and an edit-plus-test completion gate. Its scored version is frozen at 2.2.0.

The fixed subset contains 21 unique tasks. It was deterministically sampled using seed 42 and filtered through successful official Oracle verification. The full 89-task suite is not run.
