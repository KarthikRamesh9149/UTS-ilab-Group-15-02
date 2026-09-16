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

2026-09-16 OpenRouter transport increment: added fixed-origin HTTPS transport
with redirects refused, no retries, exact decimal response parsing, sanitised
HTTP errors and a private credential-file check. Generation remains disabled
by default. All 37 Stage 2 tests and 12 existing tests passed (49 total).
A real read-only account/endpoint check returned available account credit
$25.265176805, key usage $0, key remaining allowance $30, and the requested
DeepInfra FP8 endpoint at $0.06/M input and $0.18/M output tokens. This is not
generation, tool-use, billing reconciliation or harness compatibility evidence.
The safe request-cost bound and live gateway serving remain pending.

2026-09-16 gateway integration increment: a loopback-only HTTP endpoint now
accepts OpenAI-style chat requests and forwards them to the guarded core.
Real localhost HTTP tests use scripted responses, not paid model calls.
Generation identifiers are durably attached before reconciliation; the core
requires matching model/provider/cost from OpenRouter's generation endpoint
before settling a reservation. Pending records remain queryable after restart.
All 42 Stage 2 tests and 12 existing tests passed (54 total).

The live upstream transport is implemented, but no live gateway instance was
launched. Harness compatibility and a qualified conservative input-cost bound
remain gates. The official tokenizer source was located at
`deepseek-ai/DeepSeek-V4-Flash-0731`, revision
`7872f01b1d1fe23eabc4c98b48bffcef5a386062`; it has not been installed or qualified
against the provider's actual prompt encoding. No heuristic estimate is treated
as a proven bound, and no paid generation occurred in this increment.

API references inspected:
- https://openrouter.ai/docs/api/api-reference/generations/get-generation
- https://openrouter.ai/docs/cookbook/administration/usage-accounting
- https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash-0731

2026-09-16 first live setup fixture: one plain completion through the gateway
core returned exactly `UTS_OK` (14 prompt tokens, 4 completion tokens). Before
dispatch, the ledger reserved $0.10487040: the entire 1,048,576-token input
context at the $0.10/M routing ceiling plus 64 output tokens at $0.20/M. This
does not rely on a heuristic tokenizer. It is only suitable for the setup
allocation, not the $0.055 scored-trial ceiling.

The generation receipt was initially unavailable, so the gateway retained its
reservation and stopped. A later read-only lookup returned the canonical dated
model identifier. Registered the exact alias mapping and reconciled the same
generation without replay. Final cost: $0.00000156. Key usage, completion cost,
generation cost and account-balance decrement agree; credit $25.265175245.
See setup_probe_result.json (initial stop) and setup_probe_reconciled.json
(recovery). The setup ledger is `.runtime/stage2/setup_budget.sqlite`, with a
strict aggregate $1 ceiling. Every future setup request must use this ledger;
do not create another setup allocation in another ledger. Development/final
allocations remain separate and must not double-count this setup allowance.

All 46 Stage 2 tests and 12 existing tests passed (58 total). No scored task
ran. Tool calling, HTTP-to-live-provider wiring, real baseline execution,
input-cost bounds for scored trials, Docker network isolation and full runtime
qualification remain outstanding. The one-shot marker prevents probe replay.

2026-09-16 tool/client milestone: the single real tool-call fixture returned
`record_fixture` with exactly `{"marker":"UTS_OK","count":7}`; no commands or
tool side effects were executed. Cost $0.00003084 (319 input, 65 output tokens).
Its receipt was delayed beyond bounded read-only polling, so the gateway stopped
and retained the reservation. Reconciled the same generation later, no replay.
Total setup spend $0.00003240, no pending requests. Refreshed key usage and
account credit agree: remaining $25.265144405. Keep the earlier result/receipt
snapshots: they accurately record the transient accounting delay.

The installed Harbor LiteLLM client successfully used the real localhost HTTP
gateway and guarded core with a scripted upstream response, exactly once.
Harbor's outer automatic retry decorator was explicitly bypassed only in this
fixture and SDK retries disabled. A production connection adapter must preserve
that no-hidden-retries property; no baseline agent was executed by this test.
No vendor package was edited. All 48 Stage 2 tests plus 12 existing tests pass
(60 total). Scored-trial input-cost bounds, native agent/task wiring and Docker
network isolation still require qualification before the study can launch.

2026-09-16 runtime/tokenizer milestone: the actual Harbor DockerEnvironment
started an isolated fixture using the cached native ARM Node image. All seven
checks passed: 4-CPU and 8-GiB configured limits, no Mac home, no Docker socket,
no upstream API key, loopback-only networking, and a file preserved between
commands. The fixture was removed through Harbor afterwards. This is an
offline fixture, not an agent run, adversarial isolation audit, AMD64 task
qualification, or evidence that all 89 tasks fit the host. See
`harbor_runtime_probe_result.json` and the explicitly network-disabled Compose
override. Do not use that override for tasks that require internet access.

Reviewed the pinned official DeepSeek encoder and tokenizer. Offline replay of
the two existing request shapes exactly matches the provider's input counts:
14 plain and 319 tool-schema tokens. `calibrate_tokenizer.py` verifies both asset
hashes before importing the reviewed encoder and makes no API calls. The assets
remain in ignored `.cache/stage2-tokenizer/`; the output records source revision
and hashes. This small calibration is NOT a qualified upper bound for scored
requests. Multi-turn/tool-result/reasoning/schema cases and provider template
drift remain unresolved; the production reservation policy is unchanged.

Adapter inspection confirms OpenHands runs inside its environment, whereas the
gateway currently listens only on host loopback. Restricted container-to-gateway
connectivity and public-internet/private-network isolation need implementation
and runtime verification before a live baseline can run. Harbor 0.22.0 has an
egress-control sidecar worth evaluating, but its availability alone proves no
isolation guarantee. No paid requests or scored tasks were added this increment.
All 48 Stage 2 tests and 12 existing tests passed again (60 total). Mac checks
showed no thermal/performance warnings, 37% memory free and 48 GiB disk free.
