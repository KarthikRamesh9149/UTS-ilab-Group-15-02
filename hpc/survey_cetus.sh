#!/bin/bash
# Read-only survey of CETUS: what exists, what we can use, what is blocked.
# Run with:  (Get-Content hpc/survey_cetus.sh -Raw) -replace "`r`n","`n" | ssh cetus "bash -s"

section() { echo; echo "=============== $1 ==============="; }

section "IDENTITY"
whoami; hostname
cat /etc/os-release 2>/dev/null | grep -E '^(NAME|VERSION)=' || true

section "STORAGE"
echo "--- home ---"
echo "HOME=$HOME"
df -h "$HOME" 2>/dev/null | tail -2
echo "--- quota (if enabled) ---"
quota -s 2>/dev/null | head -10 || echo "(no quota command)"
echo "--- scratch candidates ---"
for d in /scratch "/scratch/$USER" /shared/scratch /shared/eresearch; do
  [ -d "$d" ] && echo "EXISTS: $d" && df -h "$d" 2>/dev/null | tail -1
done

section "PBS QUEUES"
which qsub qstat 2>/dev/null
qstat -Q 2>/dev/null | head -25 || echo "(qstat -Q unavailable)"

section "GPU NODES (from PBS)"
pbsnodes -aSj 2>/dev/null | head -30 || echo "(pbsnodes unavailable)"
echo "--- nodes advertising ngpus ---"
pbsnodes -a 2>/dev/null | grep -B12 -i 'ngpus' | grep -E '^[a-zA-Z0-9_-]+$|ngpus|gpu_|resources_available.mem|available.ncpus' | head -40 || true

section "MODULES"
if command -v module >/dev/null 2>&1; then
  echo "--- searching for things we care about ---"
  module avail 2>&1 | tr ' ' '\n' | grep -iE 'apptainer|singularity|podman|docker|cuda|python|conda|miniforge|anaconda|gcc|vllm|pytorch' | sort -u | head -60
else
  echo "(no 'module' command in this shell)"
fi

section "CONTAINER RUNTIMES"
for c in apptainer singularity podman docker udocker; do
  p=$(command -v $c 2>/dev/null)
  if [ -n "$p" ]; then echo "FOUND $c -> $p"; $c --version 2>&1 | head -1; else echo "absent: $c"; fi
done

section "PYTHON / UV"
for c in python3 python uv pip3; do
  p=$(command -v $c 2>/dev/null)
  [ -n "$p" ] && echo "$c -> $p ($($c --version 2>&1 | head -1))" || echo "absent: $c"
done

section "NETWORK EGRESS (can we download model weights?)"
for url in https://pypi.org/simple/ https://huggingface.co https://github.com; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$url" 2>/dev/null)
  echo "$url -> HTTP ${code:-FAILED}"
done
echo "--- proxy env ---"
env | grep -i proxy || echo "(no proxy variables set)"

section "DONE"
