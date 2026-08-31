#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS_BIN="$PROJECT_ROOT/.tools/bin"
PYTHON_BIN_DIR="$PROJECT_ROOT/.tools/python/cpython-3.12.13-macos-aarch64-none/bin"
OLLAMA_BIN="$PROJECT_ROOT/.tools/ollama/Ollama.app/Contents/Resources/ollama"
RUNTIME_DIR="$PROJECT_ROOT/.runtime"
MODEL_STORE="$PROJECT_ROOT/.cache/ollama/models"
PROJECT_DOCKER_CONFIG="$RUNTIME_DIR/docker-config"
DOCKER_PLUGIN_DIR="$PROJECT_ROOT/.tools/docker-cli-plugins"

export PATH="$TOOLS_BIN:$PYTHON_BIN_DIR:$PATH"
if [[ -z "${DOCKER_HOST:-}" ]]; then
  detected_docker_host="$(docker context inspect colima --format '{{.Endpoints.docker.Host}}' 2>/dev/null || true)"
  if [[ -n "$detected_docker_host" ]]; then
    export DOCKER_HOST="$detected_docker_host"
  fi
fi
export DOCKER_CONFIG="$PROJECT_DOCKER_CONFIG"
mkdir -p "$PROJECT_DOCKER_CONFIG"
printf '{"cliPluginsExtraDirs":["%s"]}\n' "$DOCKER_PLUGIN_DIR" > "$PROJECT_DOCKER_CONFIG/config.json"

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
