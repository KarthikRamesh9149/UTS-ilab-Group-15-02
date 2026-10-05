#!/usr/bin/env bash
# Step 5: each model once on each selected task, one trial at a time, with the
# same settings (run_trial.sh). Free: local Ollama models only.
#
# Usage: run_check.sh <jobs-dir>
# Needs HARBOR and TB21_TASKS (see run_trial.sh). Run under `caffeinate -is`.
#
# Replacement rule: a trial that fails before any model call (an exception, no
# tokens, an empty agent folder) is rerun once under a "-r2" job name. Both
# attempts are kept. The batch stops on any of:
#   - a second pre-model failure on the same trial;
#   - a macOS sleep or wake event since the batch started;
#   - DNS failure;
#   - battery below 25% and discharging (checked before each trial).
set -uo pipefail

jobs="$1"
here="$(cd "$(dirname "$0")" && pwd)"
tasks=(constraints-scheduling overfull-hbox reshard-c4-data)
models=(granite4.2:8b qwen3:8b)
batch_start=$(date '+%Y-%m-%d %H:%M:%S')

stop() { echo "=== STOP: $1"; exit 2; }

guard_power() {
  local pct
  pct=$(pmset -g batt | grep -o '[0-9]*%' | head -1 | tr -d '%')
  if pmset -g batt | grep -q "discharging" && [ "${pct:-100}" -lt 25 ]; then
    stop "battery at ${pct}% and discharging; not starting another trial"
  fi
}

guard_sleep_and_network() {
  local events
  # Column 4 is the event type; "Wake Requests" lines are scheduling notes, not wakes.
  events=$(pmset -g log | awk -v start="$batch_start" \
    '($1" "$2) >= start && ($4=="Sleep" || $4=="DarkWake" || ($4=="Wake" && $5!="Requests"))' \
    | head -3 | tr '\n\t' '  ')  # one line, so the caller's "tail -1" still sees STOP
  [ -n "$events" ] && stop "macOS sleep/wake since batch start: $events"
  host -W 5 deb.debian.org >/dev/null 2>&1 || stop "DNS lookup failed (network loss)"
}

# Prints "pre-model" if the trial failed before any model call, else "ok".
classify() {
  local job_dir="$1"
  python3 - "$job_dir" <<'EOF'
import json, sys
from pathlib import Path
trials = [p for p in Path(sys.argv[1]).glob('*/result.json')]
if not trials:
    print('pre-model'); sys.exit()
result = json.loads(trials[0].read_text())
agent = result.get('agent_result') or {}
agent_dir = trials[0].parent / 'agent'
empty = not agent_dir.exists() or not any(agent_dir.iterdir())
failed = result.get('exception_info') is not None
no_tokens = not agent.get('n_input_tokens')
print('pre-model' if failed and no_tokens and empty else 'ok')
EOF
}

run_one() {
  local model="$1" task="$2" suffix="$3"
  local safe
  safe=$(echo "$model" | tr ':/.' '---')
  guard_power
  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) start $model $task$suffix"
  "$here/run_trial.sh" "$model" "$task" "$jobs" "$suffix" || echo "=== harbor exited non-zero for $model $task$suffix"
  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) end $model $task$suffix"
  guard_sleep_and_network
  classify "$jobs/terminus2-$safe-$task$suffix"
}

for task in "${tasks[@]}"; do
  for model in "${models[@]}"; do
    outcome=$(run_one "$model" "$task" "" | tee /dev/stderr | tail -1)
    case "$outcome" in *STOP*) exit 2;; esac
    if [ "$outcome" = "pre-model" ]; then
      echo "=== pre-model failure: replacing $model $task once"
      outcome=$(run_one "$model" "$task" "-r2" | tee /dev/stderr | tail -1)
      case "$outcome" in *STOP*) exit 2;; esac
      [ "$outcome" = "pre-model" ] && stop "repeated pre-model failure for $model $task"
    fi
  done
done
echo "=== ALL TRIALS DONE"
