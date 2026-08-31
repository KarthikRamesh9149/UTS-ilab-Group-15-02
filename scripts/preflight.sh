#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"

run_dir="$(current_run_dir)"
output="$run_dir/environment.txt"
free_gib="$(df -Pk "$PROJECT_ROOT" | awk 'NR==2 {printf "%.0f", $4/1024/1024}')"
python_version="$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"

{
  printf 'Terminal-Bench 2.1 preliminary smoke environment\n'
  printf 'Captured: %s\n' "$(date -Iseconds)"
  printf 'Timezone: %s\n\n' "$(date +%Z)"
  printf 'Operating system:\n'; sw_vers
  printf '\nKernel and architecture:\n'; uname -a
  printf '\nHardware:\n'; system_profiler SPHardwareDataType | sed -E '/(Serial Number|Hardware UUID|Provisioning UDID)/d'
  printf '\nDisk:\n'; df -h "$PROJECT_ROOT"
  printf '\nApple Silicon / Metal:\n'; system_profiler SPDisplaysDataType | sed -n '1,80p'
  printf '\nNVIDIA GPU:\n'; if command -v nvidia-smi >/dev/null; then nvidia-smi; else printf 'Not present\n'; fi
  printf '\nGit:\n'; git --version
  printf '\nPython (system):\n'; python3 --version
  printf '\nuv:\n'; uv --version
  printf '\nDocker client:\n'; docker --version
  printf '\nDocker daemon:\n'; docker info --format 'Server {{.ServerVersion}}; OS {{.OperatingSystem}}; Arch {{.Architecture}}; CPUs {{.NCPU}}; Memory {{.MemTotal}}'
  printf '\nColima:\n'; colima version; colima status
  printf '\nOllama:\n'; "$OLLAMA_BIN" --version 2>&1 || true
  printf '\nHarbor:\n'; harbor --version
} | tee "$output"

if (( free_gib < 15 )); then
  printf 'ERROR: only %s GiB free; at least 15 GiB is required.\n' "$free_gib" >&2
  exit 1
fi
python3 - "$python_version" <<'PY'
import sys
parts = tuple(map(int, sys.argv[1].split('.')))
if parts < (3, 10):
    print('NOTICE: system Python is older than 3.10; the isolated Harbor Python is used instead.')
PY
docker run --rm hello-world >/dev/null
printf 'PASS: disk, Git, container runtime, isolated Python/Harbor tooling, and preflight capture are available.\n'

