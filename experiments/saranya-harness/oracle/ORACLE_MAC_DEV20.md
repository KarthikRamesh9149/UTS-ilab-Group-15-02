# Oracle check on Saranya's Mac, dev20 tasks (run r1)

**Status: incomplete. Only 3 of 20 trials gave valid evidence about this host.**
The Mac went to sleep and then lost its network during the run, so 17 trials
say nothing about Rosetta compatibility. They need a rerun.

The Oracle agent runs each task's official reference solution. It calls no
model, so the run cost nothing.

## Setup

| Item | Value |
|---|---|
| Host | Apple Silicon Mac, Docker Desktop 29.7.2 (aarch64); x86-64 task images run under Rosetta |
| Harbor | 0.22.0, `-a oracle -n 1 -k 1` (one trial at a time, as in Stage 2) |
| Tasks | the 20 `development_ids` in `stage2/input_manifest.json` |
| Task files | `harbor-framework/terminal-bench-2-1` at `7131e4375048a0e408a8fb404b5f499d726b695b`, the revision Stage 2 pinned in `stage2/dataset_provenance.json`. All 20 `task.toml` SHA-256 hashes matched the manifest. |
| Job | `oracle-dev20-mac-r1`, started 1 October 2026 00:53 UTC (10:53 AEST) |

## Results

Per-trial classifications are in [`oracle-dev20-mac-r1.csv`](oracle-dev20-mac-r1.csv),
produced by `python -m saranya_harness.summarize ... --host mac`.

| Task | Reward | What happened | Valid host evidence? |
|---|---:|---|---|
| video-processing | 1.0 | Reference solution passed | **Yes: runs on this Mac** |
| install-windows-3.11 | 0.0 | QEMU 5.2.0 compiled; the VM then crashed with `rosetta error: Unimplemented syscall number 282` | **Yes: Rosetta incompatibility** |
| qemu-alpine-ssh | 0.0 | Same `rosetta error: Unimplemented syscall number 282`; the solution could not connect to the VM | **Yes: Rosetta incompatibility** |
| openssl-selfsigned-cert | 0.0 | The solution **succeeded** ("Certificate verification successful"), but the verifier could not install curl/uv: `Could not resolve 'deb.debian.org'` | No: network outage |
| regex-chess | 0.0 | Verifier could not install its tools: `Could not resolve 'deb.debian.org'` | No: network outage |
| 15 other tasks | none | Docker could not pull the task image: `lookup registry-1.docker.io: no such host` | No: network outage |

The 15 other tasks are: adaptive-rejection-sampler, build-pov-ray,
constraints-scheduling, db-wal-recovery, distribution-search, mailman,
merge-diff-arc-agi-task, modernize-scientific-stack, nginx-request-logging,
overfull-hbox, polyglot-rust-c, prove-plus-comm, qemu-startup,
reshard-c4-data and sqlite-db-truncate.

Syscall 282 on x86-64 Linux is `signalfd`, as Karthik's
`stage2/rosetta_requalification.md` records. Two of the three Rosetta failures
he reported reproduce on this Mac. The third, qemu-startup, never started here
because of the outage.

## Why the run was compromised

The macOS power log (`pmset -g log`) shows the Mac on battery entering
`Idle Sleep` at 11:04 AEST, about ten minutes into install-windows-3.11. It
slept repeatedly after that, including `Clamshell Sleep` (lid closed) from 12:09.

- **Time limits stopped working.** install-windows-3.11's solution ran for
  2 h 37 min against a 1-hour limit, with no timeout raised. Harbor's timer
  does not advance while the Mac sleeps, so wall-clock time is not bounded.
- **The network dropped.** Trials started after about 04:10 UTC could not
  resolve DNS. Harbor retried and then gave up.

A DNS check on 2 October showed `registry-1.docker.io` and `deb.debian.org`
resolving again.

## Infrastructure list after this run

`saranya_harness/classify.py` now records where each entry's evidence comes from:

| Task | Status on Saranya's Mac | Evidence |
|---|---|---|
| install-windows-3.11 | **Confirmed** Rosetta failure | This run |
| qemu-alpine-ssh | **Confirmed** Rosetta failure | This run |
| qemu-startup | Kept, **unconfirmed** | Karthik's Mac run only; not observed here yet |
| build-pov-ray | Not on the list | Karthik's Mac failure was a reference download 403; unknown here (DNS failure) |
| video-processing | Runs | This run |
| the other 15 | Unknown | DNS failure |

The classifier also gained a **network-failure** rule:
- `no such host` in a Harbor error, or `Could not resolve '` / `Temporary
  failure resolving` in verifier output, now counts as infrastructure.
- Evidence observed in a trial is reported ahead of the known-host list.
- Network signatures are never read from the agent's own command output.

## Requirements for any valid run on this Mac

These also apply to paid harness runs, which use the same verifier:

1. **Mains power and lid open.** `caffeinate -is` stops idle and system sleep
   on mains power. Nothing stops lid-close sleep on battery.
2. **A stable network for the whole run.** The verifier downloads curl and uv
   inside the container, so a dropped network turns passes into zeros.
3. **Check the power log afterwards** (`pmset -g log`) and treat any trial that
   overlapped a sleep as invalid.

## Next step

Rerun the 17 tasks without valid evidence, as job `oracle-dev20-mac-r2`, with
the Mac on mains power, lid open, under `caffeinate -is`. Keep this r1 record
unchanged. The r2 results will replace "unknown" entries above, not overwrite
this file.
