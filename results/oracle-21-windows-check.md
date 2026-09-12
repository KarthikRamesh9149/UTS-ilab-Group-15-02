# Oracle runnability check — frozen 21 tasks on a Windows host

**Date:** 11 September 2026, corrected 12 September 2026
**Branch:** `harshini/21task-run`
**Raw data:** [`oracle-21-check.csv`](oracle-21-check.csv) (first pass, 19/21) ·
[`oracle-21-final.csv`](oracle-21-final.csv) (after the timeout correction, 21/21)

> **Outcome: 21 / 21 environments valid on this host.** The first pass returned 19/21;
> the two failures were both timeouts and both passed on re-run with
> `--timeout-multiplier 3.0`. See [the correction](#infrastructure-correction-12-september)
> below. Neither failure was a task defect or a hardware limit.

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

## First pass: 19 / 21 environments valid

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

## Infrastructure correction, 12 September

Both failures were re-run with `--timeout-multiplier 3.0`, changing nothing else. This is
an infrastructure correction under §4.1.7: the timeout is a property of the host, not of
the task or the harness, and the subset is untouched.

| Task | First pass | Re-run | Elapsed |
|---|---|---|---:|
| `reshard-c4-data` | `EnvironmentStartTimeoutError` at 600 s | **`reward = 1.0`** | 322 s |
| `torch-pipeline-parallelism` | `VerifierTimeoutError` at 909 s | **`reward = 1.0`** | 923 s |

Two things are worth noting about *why* they failed, because they change the
interpretation:

- `torch-pipeline-parallelism` needed **923 s against a 909 s limit** — it was over by
  about fourteen seconds. The first pass was a marginal miss, not a capability gap. The
  earlier reading that this task needs an NVIDIA GPU was wrong: it passes on this host
  with no GPU at all.
- `reshard-c4-data` finished in **322 s on the re-run, roughly half its 600 s limit**.
  A task cannot become twice as fast from a timeout multiplier alone, so the limit was
  never the real constraint. The plausible cause is first-run cost that the retry did not
  pay again — pulling and unpacking the task image. That makes it a cold-start artefact,
  and it argues for warming images before a scored run rather than for raising timeouts.

The original job directory is kept as-is, so `summarize_job.py jobs/oracle-21-check` still
reports 19/21 on its own. The corrected total comes from reading both directories, where a
later trial supersedes an earlier one for the same task.

## Consequences for the scored harness runs

1. **All 21 tasks are known-good on this host.** A reward of 0 on any of them is now
   attributable to the model or the harness, not to the environment. This is the claim the
   earlier matrix could not make, because it was Oracle-validated on a different machine.
2. **No task has to be reported as a host limitation.** The full 21 stay in the
   denominator and all 21 can discriminate between harnesses.
3. **Oracle timings set a floor.** The official solutions took 23 s to 923 s per task;
   the 21-task first pass took 28m37s of wall time at 4-way concurrency. An agent harness
   needs many more steps per task, so a scored 21-task run is hours, not minutes.
4. **Warm the images before a scored run.** Given the `reshard-c4-data` cold-start
   evidence, pulling task images in advance avoids charging first-run download time
   against an agent's environment-start budget.

## Reproduce

```powershell
$tasks = Get-Content configs/progress_subset.txt | Where-Object { $_.Trim() -and -not $_.Trim().StartsWith('#') }
$harborArgs = @(); foreach ($t in $tasks) { $harborArgs += "-i"; $harborArgs += "terminal-bench/$($t.Trim())" }
harbor run -d terminal-bench/terminal-bench-2-1 -a oracle @harborArgs -n 4 -k 1 -o jobs --job-name oracle-21-check --yes
python scripts/summarize_job.py jobs/oracle-21-check --csv results/oracle-21-check.csv
```

Then the correction for the two timeouts:

```powershell
harbor run -d terminal-bench/terminal-bench-2-1 -a oracle `
  -i terminal-bench/reshard-c4-data -i terminal-bench/torch-pipeline-parallelism `
  -n 1 -k 1 -o jobs --job-name oracle-2-retry --timeout-multiplier 3.0 --yes
python scripts/summarize_job.py jobs/oracle-21-check jobs/oracle-2-retry --csv results/oracle-21-final.csv
```
