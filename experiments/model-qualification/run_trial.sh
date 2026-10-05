#!/usr/bin/env bash
# Run stock Harbor Terminus-2 once on one Terminal-Bench 2.1 task with a local
# Ollama model. Free: the model runs on this machine; no hosted API is called.
#
# Usage: run_trial.sh <ollama-model-tag> <task-id> <jobs-dir> [job-suffix]
# job-suffix (for example "-r2") names a replacement attempt so both are kept.
# Needs: HARBOR (harbor executable), TB21_TASKS (terminal-bench-2-1 tasks
# directory at the Stage 2 pinned revision), Ollama serving on 127.0.0.1:11434.
#
# Settings follow Stage 2's Terminus-2 factory (stage2/native_agents.py:79-89)
# where a local model allows it; README.md lists every difference.
set -euo pipefail

model="$1"; task="$2"; jobs="$3"; suffix="${4:-}"
: "${HARBOR:?set HARBOR to the harbor executable}"
: "${TB21_TASKS:?set TB21_TASKS to the pinned terminal-bench-2-1 tasks directory}"

timeout=$(python3 -c "import tomllib,sys; print(int(tomllib.load(open(sys.argv[1],'rb'))['agent']['timeout_sec']))" \
    "$TB21_TASKS/$task/task.toml")
wait_seconds=$((timeout + 60))  # Stage 2: completion wait = agent timeout + 60 s (stage2/completion_wait.py)
safe_model=$(echo "$model" | tr ':/.' '---')

# No hosted-provider keys reach this process, so nothing can be billed.
exec env -u OPENROUTER_API_KEY -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u GEMINI_API_KEY \
  "$HARBOR" run --debug -p "$TB21_TASKS" -i "$task" -n 1 -k 1 \
  -a terminus-2 -m "openai/$model" \
  --ak api_base=http://127.0.0.1:11434/v1 \
  --ak temperature=1.0 \
  --ak reasoning_effort=high \
  --ak "llm_kwargs={\"api_key\": \"ollama\", \"timeout\": $wait_seconds}" \
  --ak 'llm_call_kwargs={"top_p": 1.0, "extra_body": {"reasoning_effort": "high"}}' \
  --ak 'model_info={"max_input_tokens": 16384, "max_output_tokens": 16384, "max_tokens": 16384, "input_cost_per_token": 0, "output_cost_per_token": 0, "litellm_provider": "openai", "mode": "chat", "supports_reasoning": true}' \
  -o "$jobs" --job-name "terminus2-$safe_model-$task$suffix" --yes
