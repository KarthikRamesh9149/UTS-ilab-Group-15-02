#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"

if [[ ! -f "$RUNTIME_DIR/ollama.pid" ]]; then
  printf 'Ollama PID file is absent; nothing to stop.\n'
  exit 0
fi
pid="$(<"$RUNTIME_DIR/ollama.pid")"
if kill -0 "$pid" 2>/dev/null; then
  kill "$pid"
  for _ in {1..20}; do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.25
  done
fi
rm -f "$RUNTIME_DIR/ollama.pid"
printf 'Ollama stopped.\n'

