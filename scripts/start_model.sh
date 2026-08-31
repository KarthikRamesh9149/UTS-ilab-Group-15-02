#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"

mkdir -p "$RUNTIME_DIR" "$MODEL_STORE"
if [[ ! -x "$OLLAMA_BIN" ]]; then
  printf 'ERROR: Ollama binary missing at %s\n' "$OLLAMA_BIN" >&2
  exit 1
fi
if [[ -f "$RUNTIME_DIR/ollama.pid" ]] && kill -0 "$(<"$RUNTIME_DIR/ollama.pid")" 2>/dev/null; then
  printf 'Ollama is already running (PID %s).\n' "$(<"$RUNTIME_DIR/ollama.pid")"
  exit 0
fi

log_command 'OLLAMA_CONTEXT_LENGTH=32768 OLLAMA_KEEP_ALIVE=-1 OLLAMA_NUM_PARALLEL=1 OLLAMA_HOST=0.0.0.0:11434 ollama serve'
OLLAMA_MODELS="$MODEL_STORE" \
OLLAMA_CONTEXT_LENGTH=32768 \
OLLAMA_KEEP_ALIVE=-1 \
OLLAMA_NUM_PARALLEL=1 \
OLLAMA_HOST=0.0.0.0:11434 \
nohup "$OLLAMA_BIN" serve >"$RUNTIME_DIR/ollama.log" 2>&1 &
pid=$!
printf '%s\n' "$pid" > "$RUNTIME_DIR/ollama.pid"

for _ in {1..30}; do
  if curl -fsS http://127.0.0.1:11434/api/version >/dev/null; then
    printf 'Ollama started on the local network interface required by Colima containers (PID %s).\n' "$pid"
    exit 0
  fi
  sleep 1
done
printf 'ERROR: Ollama did not become ready. See %s\n' "$RUNTIME_DIR/ollama.log" >&2
exit 1

