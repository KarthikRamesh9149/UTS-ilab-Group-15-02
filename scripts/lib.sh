#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS_BIN="$PROJECT_ROOT/.tools/bin"
OLLAMA_BIN="$PROJECT_ROOT/.tools/ollama/Ollama.app/Contents/Resources/ollama"
RUNTIME_DIR="$PROJECT_ROOT/.runtime"
MODEL_STORE="$PROJECT_ROOT/.cache/ollama/models"

export PATH="$TOOLS_BIN:$PATH"

current_run_dir() {
  if [[ -n "${RUN_DIR:-}" ]]; then
    mkdir -p "$RUN_DIR"
    cd "$RUN_DIR" && pwd
    return
  fi
  if [[ -f "$PROJECT_ROOT/.current_run" ]]; then
    local recorded
    recorded="$(<"$PROJECT_ROOT/.current_run")"
    if [[ -d "$recorded" ]]; then
      printf '%s\n' "$recorded"
      return
    fi
  fi
  local created="$PROJECT_ROOT/results/progress_smoke_$(date +%Y%m%d_%H%M%S)"
  mkdir -p "$created/raw" "$created/trials"
  printf '%s\n' "$created" > "$PROJECT_ROOT/.current_run"
  printf '%s\n' "$created"
}

log_command() {
  local run_dir
  run_dir="$(current_run_dir)"
  printf '%s\t%s\n' "$(date -Iseconds)" "$*" >> "$run_dir/commands.log"
}

