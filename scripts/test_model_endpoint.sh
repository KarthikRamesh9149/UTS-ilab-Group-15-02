#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"

model="${MODEL_NAME:-qwen2.5-coder:3b}"
host_url="${HOST_MODEL_BASE_URL:-http://127.0.0.1:11434/v1}"
container_url="${CONTAINER_MODEL_BASE_URL:-http://host.docker.internal:11434/v1}"
run_dir="$(current_run_dir)"
raw="$run_dir/raw/model_endpoint"
mkdir -p "$raw"

request='{"model":"'"$model"'","messages":[{"role":"user","content":"Write a Python function that returns the first 300 Fibonacci numbers, then explain its complexity in enough detail to demonstrate a long response."}],"temperature":0,"max_tokens":1100,"stream":false}'
curl -fsS "$host_url/models" -H 'Authorization: Bearer ollama' | tee "$raw/host_models.json" >/dev/null
curl -fsS "$host_url/chat/completions" -H 'Authorization: Bearer ollama' -H 'Content-Type: application/json' -d "$request" | tee "$raw/host_chat.json" >/dev/null
curl -fsS "$host_url/chat/completions" -H 'Authorization: Bearer ollama' -H 'Content-Type: application/json' -d '{"model":"'"$model"'","messages":[{"role":"user","content":"Reply with exactly: SECOND_REQUEST_OK"}],"temperature":0,"max_tokens":32,"stream":false}' | tee "$raw/host_second_request.json" >/dev/null

docker run --rm curlimages/curl:8.16.0 -fsS "$container_url/models" -H 'Authorization: Bearer ollama' | tee "$raw/container_models.json" >/dev/null
docker run --rm curlimages/curl:8.16.0 -fsS "$container_url/chat/completions" -H 'Authorization: Bearer ollama' -H 'Content-Type: application/json' -d '{"model":"'"$model"'","messages":[{"role":"user","content":"Reply with exactly: CONTAINER_OK"}],"temperature":0,"max_tokens":32,"stream":false}' | tee "$raw/container_chat.json" >/dev/null

python3 - "$raw" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
for name in ('host_models.json', 'host_chat.json', 'host_second_request.json', 'container_models.json', 'container_chat.json'):
    data = json.loads((root / name).read_text())
    if 'error' in data:
        raise SystemExit(f'{name}: {data["error"]}')
if 'SECOND_REQUEST_OK' not in json.loads((root/'host_second_request.json').read_text())['choices'][0]['message']['content']:
    raise SystemExit('second host request did not return expected marker')
if 'CONTAINER_OK' not in json.loads((root/'container_chat.json').read_text())['choices'][0]['message']['content']:
    raise SystemExit('container request did not return expected marker')
usage = json.loads((root/'host_chat.json').read_text()).get('usage', {})
print(f'PASS: host and container endpoint checks completed; long-response usage={usage or "unavailable"}')
PY

