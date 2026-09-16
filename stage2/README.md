# Stage 2 execution status

Latest host decision: user authorised a Mac + OpenRouter fallback. Read-only
qualification found insufficient current Docker resources, limited disk headroom
and six unrelated running Orchestra services. See mac_host_qualification.md.
No host transition or benchmark launch is claimed yet. CETUS records below
remain historical evidence, not the newly selected execution target.

Approved scope: CETUS task execution, OpenRouter DeepSeek V4 Flash 0731 through
the verified DeepInfra FP8 endpoint; Terminus-2, OpenHands and a new custom
Deep Agents/LangGraph harness. Preserve the Stage 1 pilot without edits.

## Gates and evidence checklist

- [x] Shared SSH authentication established; no password stored by the project.
- [x] OpenRouter key authenticated previously: non-resetting $30 limit, $0 usage.
- [ ] Compute-node network, runtime and isolation preflight.
- [ ] Account/project allocation and required Data Management Plan confirmed.
- [x] Source branch: `codex/cetus-openrouter-stage2`, based on `6d10c4e`.
  The installed Command Line Tools Git works independently of the Xcode launcher.
  No licence was accepted automatically.
- [ ] Safe task runtime validated against all 89 environment definitions.
- [ ] Crash-safe gateway and precise budget ledger implemented and tested.
- [ ] Model/provider metadata and account credit revalidated before paid probes.
- [ ] Dependencies, task manifests and experimental settings frozen.
- [ ] Real custom backend, baseline integrations and Langfuse verified.
- [ ] Bounded $1 compatibility probes and 20-task Terminus qualification.
- [ ] 120 development cells, including qualification; finalist frozen.
- [ ] 267 fresh final cells: 89 per harness, one attempt each.
- [ ] Independent evidence, metric, billing and security audit.
- [ ] Technical bundle and separate code-free report-writer ZIP.

Revised budget after authorisation to use the available account balance:
$0.055 per scored trial, equal across harnesses; setup $1; development $6.60;
final $14.685; core maximum $22.285. The observed $25.265176805 account balance
leaves a $2 untouched reserve and at most $0.980176805 contingency, with local
admission ceiling $23.265176805. This is a snapshot, not a guaranteed allocation:
recheck live account credit before spending and reduce admission if it declines.
The original plan's $0.06 cap and $30 allocation are superseded by this budget.
No paid calls until safety and spending gates pass. No model fallback,
leaderboard extension, publication, final report or presentation in this unit.

Technical completion, research success and external submission are separate.
Primary objective: higher observed accuracy against preregistered comparators,
with Terminus-2 primary. Secondary: >=20% less charged cost without fewer
nonzero successes. Efficiency-only assessment approval remains unconfirmed.

## Execution journal

2026-09-16: Began authorised implementation with read-only environment discovery.
CETUS login node is x86_64, Apptainer 1.5.3; no Docker/Podman on PATH.
Local Harbor 0.22.0 has a built-in Singularity adapter; compatibility is not
yet established. No paid requests or scored trials have been made for Stage 2.
The preflight below runs deterministic diagnostics only, with no API key.

2026-09-16: Completed PBS preflights 88368/88369; saved logs and findings.
Created deterministic 89/20/69 input inventory without reading solution/test
contents. All 15 offline tests passed. Paid and agent execution stopped at the
runtime isolation/comparability and available-account-credit gates. See
preflight_findings.md for exact evidence and required decisions. No Git commit
or push performed; no source-of-truth claim of a clean worktree is made.

2026-09-16 follow-up: User authorised adapter hardening, use of available credit,
and a new GitHub branch. Added a private Unix-socket transport prototype and
an exact-money SQLite reservation ledger. Neither is a finished Harbor adapter
or billing gateway. Pending reservations survive crashes; billing overcharges
persistently halt new reservations. Stage allocation, fresh balance retrieval,
provider reconciliation and gateway integration remain required before spending.
The runtime smoke test is intentionally network-disabled and cannot qualify
network-dependent benchmark tasks. Do not score such tasks through it.

Live transport evidence: PBS 88373 failed command execution with a read-only
container filesystem. Adding an ephemeral writable overlay allowed PBS 88375
to pass all six fixture checks: authenticated health, wrong-token rejection,
root/mount isolation, file roundtrip, no routes/TCP endpoints, private socket.
Both logs are retained. This does not establish CPU/memory limits, adversarial
containment, internet egress, Dockerfile/Compose support or all-task compatibility.
Offline checks: 17 Stage 2 tests and 12 existing tests passed (29 total).

2026-09-16 next increment: inventoried all 89 environment definitions (all have
images, no Compose, maximum declared 4 CPUs/8192 MB RAM). Added immutable stage
allocations to protect the final budget, one-outstanding-request admission,
concurrent-reservation/restart tests and strict pinned-provider request policy.
25 Stage 2 tests plus 12 existing tests passed (37 total). Request policy is
offline only: streaming, input-cost bounds, actual billing reconciliation and
live gateway integration are not qualified. Unsupported features fail closed;
do not change baseline semantics silently to make integration pass.

See runtime_blockers.md: an approved isolated network route remains unresolved.
The command-channel fixture also does not yet hide its socket/token from the
task itself. Do not run agents through it. No paid model calls were made.

2026-09-16 native-instance follow-up: PBS 88380 passed a deterministic native
Apptainer instance test with no custom control socket/token or host bind mounts.
Files persisted between separate commands; shared home/control paths were
absent; networking remained disabled; the instance was stopped afterward.
This supersedes the custom socket fixture as the preferred backend direction,
but does not qualify the all89 runtime. Apptainer reported rootless cgroups
unusable in fakeroot mode, leaving resource enforcement as an explicit gate.

Added gateway dispatch core with trial-token authentication/revocation,
reserve-before-dispatch, fresh-balance callback, and fail-closed handling of
missing/ambiguous billing. Seven synthetic gateway tests passed; total 32 Stage 2
plus 12 existing tests (44). No live transport, billable-input estimator or
provider reconciliation has been qualified. No API requests are dispatched by
default, and no paid call was made. HTTP serving/baseline wiring still pending.
