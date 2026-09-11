# Oracle runnability check — frozen 21 tasks on a Windows host

**Date:** 11 September 2026
**Branch:** `harshini/21task-run`
**Raw data:** [`oracle-21-check.csv`](oracle-21-check.csv)

## Why this run exists

The frozen 21-task subset (seed 42, `configs/progress_subset.txt`) was Oracle-validated
on an Apple M5 MacBook Air. Scored harness trials are now being prepared on a different
host — Windows with Docker Desktop on the WSL2 backend, and **no NVIDIA GPU**. Oracle
outcomes are host-capability evidence, so they do not transfer between machines.

This run re-verifies that all 21 task environments build and verify **on the machine that
will produce the scored rows**.

It is a verification, **not** a re-selection. Protocol §4.1.6 freezes the subset, and
`run_matrix.py` enforces exactly 21 unique task IDs. No task was added, removed or
reordered on the basis of this result. Tasks that fail here stay in the denominator and
are reported as host limitations.

## Environment

| Component | Value |
|---|---|
| Host OS | Windows 10.0.26200 |
| Container runtime | Docker 29.4.0, WSL2 Linux engine, 18 CPUs / 16 GB |
| Benchmark runner | Harbor 0.22.0 |
| Dataset | `terminal-bench/terminal-bench-2-1` |
| Agent | `oracle` (official human solution — no model, no API key) |
| Settings | `-n 4` concurrent, `-k 1` attempt, default timeouts |
| GPU | none |

## Result: 19 / 21 environments valid

Nineteen tasks returned `reward = 1.0`. Two failed before any model could be involved.

| Task | Outcome | Elapsed | Interpretation |
|---|---|---:|---|
| `reshard-c4-data` | `EnvironmentStartTimeoutError` | 600 s | Environment did not finish starting inside its limit. Candidate for a documented timeout multiplier. |
| `torch-pipeline-parallelism` | `VerifierTimeoutError` | 909 s | Verifier exceeded its limit. Task is GPU-oriented and this host has no NVIDIA GPU. |

The remaining nineteen all passed: `build-pmars`, `code-from-image`,
`configure-git-webserver`, `constraints-scheduling`, `custom-memory-heap-crash`,
`feal-linear-cryptanalysis`, `financial-document-processor`, `fix-code-vulnerability`,
`fix-git`, `gcode-to-text`, `headless-terminal`, `nginx-request-logging`,
`openssl-selfsigned-cert`, `path-tracing`, `pypi-server`, `sam-cell-seg`,
`sparql-university`, `sqlite-db-truncate`, `write-compressor`.

## Consequences for the scored harness runs

1. **Nineteen tasks are known-good on this host.** A reward of 0 on any of them is
   attributable to the model or the harness, not to the environment.
2. **Two tasks cannot currently discriminate between harnesses on this host.** Every
   harness will score 0 on them for host reasons. They remain in the 21-task denominator
   and must be reported as such rather than dropped.
3. **Oracle timings set a floor.** The official solutions took 23 s to 909 s per task,
   totalling roughly 96 minutes of wall time at 4-way concurrency. An agent harness needs
   many more steps per task, so a full 21-task harness run is hours, not minutes.
4. **Next action for the two failures:** re-run only those two with an explicit
   `--timeout-multiplier` and record the multiplier as an infrastructure correction under
   §4.1.7. If `torch-pipeline-parallelism` still fails, it is a hardware limitation of the
   host and should be stated as one.

## Reproduce

```powershell
$tasks = Get-Content configs/progress_subset.txt | Where-Object { $_.Trim() -and -not $_.Trim().StartsWith('#') }
$harborArgs = @(); foreach ($t in $tasks) { $harborArgs += "-i"; $harborArgs += "terminal-bench/$($t.Trim())" }
harbor run -d terminal-bench/terminal-bench-2-1 -a oracle @harborArgs -n 4 -k 1 -o jobs --job-name oracle-21-check --yes
python scripts/summarize_job.py jobs/oracle-21-check --csv results/oracle-21-check.csv
```
