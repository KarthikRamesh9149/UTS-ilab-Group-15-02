# Setup notes

The live run uses Harbor 0.22.0, Ollama 0.33.2, Docker CLI 29.7.2, Docker Engine 29.5.2 through Colima 0.10.3, and checksum-verified Docker Compose 5.4.0. All downloaded tools and model weights remain in ignored `.tools/` and `.cache/` directories.

The model server is configured with a 32,768-token context, keep-alive enabled, one parallel request, and a host bind required for `host.docker.internal` access from Colima. It is not exposed through a public tunnel.

Harbor 0.22.0's installed integration source was used to resolve current argument names. Mini-SWE-Agent receives a 25-step configuration file and `max_tokens=4096`; missing local price information is ignored. OpenHands receives `disable_tool_calls=true`, `reasoning_effort=none`, `temperature=0`, `max_iterations=25`, and explicit 32K/4K token limits. Both receive the same dummy local key and endpoint.

