# Stage 2 execution status

## Current checkpoint, 27 September 2026

The user has requested a C3 before final scoring. The
[C3 design and limits audit](protocols/custom_c3_design_20260927.md) adds an
offline deadline-context prototype with a distinct 0.4 identity. It has not
been deployed, qualified natively, registered or run on paid tasks. It also
documents the inherited command and completion limits; no claim of a wholly
unrestricted harness is made. C2 continues unchanged. Do not use the existing
three-block freeze to bypass the new C3 decision and required admission work.

The corrected baselines are complete: Terminus-2 52/89 and OpenHands 44/89.
The separate [custom 0.3 C0 block](results/custom-portable-20260926/c0/README.md)
completed all 20 development tasks with 15 passes. Its matched baseline scores
are 14/20 and 10/20. This is a development result, not a confirmed full-run win.

The [C1 planning comparison](results/custom-portable-20260926/c1/README.md)
completed at 04:51 UTC on 27 September: 14 passes, six failures and no missing
verifier results. Its audit and private off-server backup are complete.
C2 started at 08:35 UTC, adding completion checks to the registered C0 parent
on the same 20 tasks. See its [launch snapshot](results/custom-portable-20260926/launch-c2.json).
The source and qualification are unchanged. These are timestamped records,
not live counters. The custom final 89 has not started.

The [final-run preparation note](protocols/custom_final_preparation_20260927.md)
records the 30 September afternoon Sydney target and the checks it cannot
override. `portable_final_selection.py` adds offline selection over complete
C0/C1/C2 summaries without the old spending or call-count gates. It is not yet
connected to a qualified final-run launcher and cannot authorise paid calls.
Confirmation, the planned ablation/repeat, source freeze, final registration and
native final-run qualification remain required.

The offline candidate-freeze and schedule modules now bind all 60 development
results and generate separate confirmation (60), diagnostic (20) and final
custom (89) cells. They reject altered evidence and do not authorise paid
execution. No real candidate has been frozen yet; C2 must finish first.

## Previous checkpoint, 26 September 2026

The corrected full baselines and separate timeout diagnostic are complete.
See [baseline results](results/baseline-corrected-20260923/README.md) and
[diagnostic results](results/timeout-diagnostic-20260925/README.md).
Do not restart those experiments or apply current source edits to their
immutable server deployments.

Custom development is [stopped for compatibility repairs](results/custom-development-20260926/README.md).
The first C0 deployment retains four started attempts: two verifier zeros,
one setup failure and one operator interruption. It has no completed /20 score.
The separately versioned [0.3 candidate](results/custom-compatibility-20260926/README.md)
adds text-only file transport, a private Python fallback, safer process capture,
cooperative boundary stopping and cancellation evidence. Its offline checks do
not constitute a paid launch or a benchmark quality result.
The fixed dev20 comparison is Terminus-2 14/20
and OpenHands 10/20. `corrected_custom_scope.py` verifies that matched export.
The separate development runner now records the user's 26 September authority:
no project/task financial cap, reserve or artificial call-count ceiling. It
retains actual provider limits and official task limits, with no automatic
top-up. The original 0.2 setup qualification passed 120 server tests and four
real-Docker rehearsals, but the paid run exposed gaps in that fixture coverage.
It cannot qualify changed 0.3 source. A successor needs fresh native qualification
and a new registration retaining the partial experiment. See the protocol note for the
remaining development and final-freeze work. Approved new work is pushed to
`main`; historical experiment commits remain unchanged.

Everything below is historical; earlier caps, running states and admissions
must not be mistaken for current execution authority or current results.

## Historical track, 20 September 2026

The active authorised track is now [Netcup native Linux + OpenRouter](NETCUP.md),
on branch `codex/netcup-openrouter-study`. This restores the one-model paid
study on a dedicated x86-64 Docker server. The user capped further spending at
the observed US$12.031657772 remaining balance; no top-ups are authorised.
The amended caps are in `budget_policy.json` and `study_budget.py`.
All 20 development environments and three live harness/model fixtures passed
earlier qualification. Six Terminus development tasks have now been attempted:
four have verified billing, one passed, and two retain unknown charges. The
[approved completion amendment](COMPLETION_AMENDMENT_20260920.md) permits
collecting low-score results while retaining those two exact historical holds.
Fresh synthetic runtime qualification passed, but the subsequent real-model
setup request returned HTTP429 and has no available billing receipt. This new
setup reservation blocks paid execution; it is not covered by the two-hold
exception. No full89 run, completed comparison or custom win is established.
Langfuse service readback is verified for the setup traces, not final results.
See [the current checkpoint](NETCUP.md) and
[billing recovery evidence](netcup/BILLING_RECOVERY.md). The older running
statuses and budget amounts below are historical, not the current policy.

Offline finalisation now binds finalist selection to the canonical registered
custom-development blocks and their independently valid reviews. A local-only
[code-free evidence packager](final_export_status.md) is implemented but refuses
to create the real ZIP until the complete 267-cell final matrix is reaudited.
No new spending PDF, assignment report, real final archive or submission has
been generated by these changes.

## Previous track, 17 September 2026

The then-active authorised study was [CETUS-only local inference](CETUS_LOCAL.md),
on branch `codex/cetus-local-harbor-study`. The OpenRouter configuration and
records below are preserved historical work, not the active execution policy.
Do not invoke the old paid runners to execute the local study.

## Historical Mac/OpenRouter track (superseded)

Current host: the authorised Mac + OpenRouter fallback. Docker was resized to
4 CPUs / 10 GiB and the authorised Orchestra services stopped. Local runtime,
gateway and agent fixtures now run. CETUS records and earlier host inspections
below are historical; no further CETUS execution is planned in this fallback.
The scored study has not launched and is not complete.

Approved scope, with the authorised host amendment: Mac Docker task execution,
OpenRouter DeepSeek V4 Flash 0731 through
the verified DeepInfra FP8 endpoint; Terminus-2, OpenHands and a new custom
Deep Agents/LangGraph harness. Preserve the Stage 1 pilot without edits.

## Gates and evidence checklist

- [x] OpenRouter authenticated; spending is recorded in the setup ledger.
- [x] Mac Docker offline fixture and narrow public-egress fixture passed.
- CETUS account/DMP/compute-node gates are historical and inapplicable to the
  selected local host; no claim of UTS approval is made.
- [x] Source branch: `codex/cetus-openrouter-stage2`, based on `6d10c4e`.
  The installed Command Line Tools Git works independently of the Xcode launcher.
  No licence was accepted automatically.
- [ ] Safe task runtime validated against all 89 environment definitions.
- [ ] Crash-safe gateway and precise budget ledger implemented and tested.
- [x] Model/provider metadata and account credit revalidated before paid probes.
- [x] Canonical dataset bytes matched official revision; development IDs unchanged.
- [ ] Dependencies, task manifests and experimental settings frozen.
- [ ] Real custom backend, baseline integrations and Langfuse verified.
- [ ] Bounded $1 compatibility probes and 20-task Terminus qualification.
- [ ] 120 development cells, including qualification; finalist frozen.
- [ ] 267 fresh final cells: 89 per harness, one attempt each.
- [ ] Independent evidence, metric, billing and security audit.
- [ ] Technical bundle and separate code-free report-writer ZIP.

Stage 2 dataset source: see `dataset_provenance.json` for the authoritative
`dataset_path`, official Git revision and per-file hashes. Do not use the old
pilot cache or pilot selection/oracle runner for this stage.

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

2026-09-16 container gateway transport: added a private Unix-socket HTTP server
and task-local loopback relay. This permits an installed agent's ordinary
OpenAI client to contact a dedicated model gateway container through a read-only
socket volume, without a host HTTP listener. The relay forwards only the fixed
completion route, preserves the caller's trial bearer token, bounds request and
response sizes, strips unrelated headers and never retries requests. It has no
upstream key and no command-execution interface. The existing host-loopback
gateway behaviour is unchanged.

`docker_gateway_probe_result.json` records a real two-container run using the
pinned cached ARM64 Python image. All 12 checks passed, including roundtrip,
wrong-token/account-route rejection, no task network other than loopback,
read-only socket mount, no exposed host ports, and exactly one settled request
in the **synthetic fixture ledger**. The provider response and balance were
scripted; no real account, credential or paid request was used. Both containers
and their dedicated socket volume were removed. No existing volumes or services
were changed. Five new regression tests pass; 53 Stage 2 plus 12 existing tests
pass (65 total). Mac health checks remained normal with 48 GiB free space.

This qualifies the narrow socket/HTTP transport fixture, NOT the OpenHands
agent itself or the complete execution architecture. Production integration
must supply an authoritative persistent budget ledger and upstream credential
to the trusted gateway only, run its upstream HTTPS connection separately from
the task, revoke each trial token, and explicitly support each task's user/UID.
The fixture used root in both containers. The task must not receive a Docker
socket, gateway ledger or credential mount. Public task internet access remains
unqualified and disabled in this fixture. Scored-request cost bounds and native
baseline execution remain launch gates. No scored trial has run in Stage 2.

2026-09-16 live HTTP milestone: `live_harbor_probe.py` exercised the installed
Harbor LiteLLM client, localhost HTTP gateway, guarded admission ledger and
actual pinned OpenRouter endpoint together. It returned exactly `UTS_OK` with
one upstream dispatch, 14 input tokens and 4 output tokens. Cost $0.00000156;
the generation receipt reconciled within this execution and no pending requests
remain. Total aggregate setup spending is $0.00003396. A subsequent read-only
account check reported credit $25.265142845 and matching key usage $0.00003396.
The $0.10487040 full-context reservation was made before dispatch, using the
existing $1 setup ledger, not a new allowance. No scored-trial bound is inferred.

`receipt_polling.py` now provides bounded read-only receipt lookup: at most
eight attempts with a 20-second admission deadline for new lookups by default.
An already-running HTTP lookup retains the transport's 45-second timeout, so
this is not a strict 20-second end-to-end wall limit. No generation call is
retried. Unknown outcomes retain the reservation. The one-shot setup runner
persists its marker and response privately and has an explicit read-only
reconciliation mode for a delayed receipt. Its client disables SDK retries and
bypasses Harbor's outer retry decorator only for this documented fixture;
native baseline retry configuration still needs integration and verification.

All 57 Stage 2 tests and 12 existing tests pass (69 total), including four new
receipt delay/deadline/error tests. This was a real **client** run, not a Terminus
agent, OpenHands agent or benchmark task. No task scores were produced. The
remaining execution gates include scored-request cost limits, public task
network isolation, native agent integration, dataset provenance and the
previously documented study protocol gates. Mac checks remained normal with
48 GiB disk free. Raw credentials and runtime journals remain untracked.

2026-09-16 agent/provenance/network milestone:

- Verified all 89 tasks and 1,037 files (including dataset metadata) against
  official Git revision `7131e4375048a0e408a8fb404b5f499d726b695b` from
  https://github.com/harbor-framework/terminal-bench-2-1 . The fresh extraction
  is separate from the pilot. All frozen task-config hashes and 20 development
  IDs match. The historical cache lacks 89 `.gitignore` files and two metadata
  files, and `sanitize-git-repo/tests/test_outputs.py` differs. No old files or
  pilot results were changed. This audit compared bytes/hashes without showing
  hidden verifier or solution contents to policy development.
- The actual Terminus-2 prompt, parser, terminal session and completion loop
  passed a three-turn scripted-model fixture, then a three-call real-model
  fixture. The real agent created the expected file and emitted a trajectory.
  Charges reconciled at $0.000162; total setup spend $0.00019596, no pending
  requests. This is a synthetic setup task, not a benchmark score. The fixture
  used a four-turn / 2,048-output-token cap and disabled reasoning; these are
  fixture settings, not a frozen final baseline configuration. Retry decorator
  bypass remains an explicitly documented connection adjustment.
- Subsequent source hardening generates a random token for future live fixture
  use and journals each request before dispatch. The completed fixture predates
  those two changes: it used a local fixture token and saved responses/receipts,
  not exact outgoing request bodies. Do not claim multi-turn tokenizer
  calibration from those responses alone. The one-shot marker prevents replay.
- A disposable namespace-firewall fixture passed 10 checks: public HTTPS,
  known-live private-peer denial, local task service access, inability to alter
  firewall rules/create raw sockets, and no host home/control socket/key. Only
  the guard container had NET_ADMIN; no host/CETUS firewall rules were changed.
  All fixture containers and its network were removed. IPv6 and raw sockets
  remain unavailable in this candidate; all-task semantic compatibility and
  an adversarial isolation audit remain outstanding. This is not yet the
  production Harbor network adapter.

References for this local fixture design:
https://docs.docker.com/engine/network/ (container network namespaces) and
https://wiki.nftables.org/wiki-nftables/index.php/Configuring_chains (chain hooks).
Neither documentation nor a fixture pass establishes full-study completion.

2026-09-16 OpenHands integration milestone:

- Harbor 0.22.0's selected adapter invokes `openhands.core.main`. The latest
  OpenHands 1.11.0 package lacks that entry point, so its installation fixture
  failed before agent execution. The compatible legacy baseline is now pinned
  to OpenHands 0.62.0. Its three exact, declared prerelease dependencies are
  explicitly pinned in `fixtures/Dockerfile.openhands`; no package was patched.
- The first native-agent attempt (`openhands_agent_probe_v1.json`) was rejected
  because its client sends `max_completion_tokens`. The gateway now normalises
  this documented equivalent to `max_tokens` without changing its value, and
  rejects requests containing both aliases. Two regression tests cover this.
  Reference: https://openrouter.ai/docs/api_reference/parameters .
- The second attempt (`openhands_agent_probe_v2.json`) passed: actual native
  OpenHands used its shell tool to create the expected file, then finished,
  through the private socket relay in two scripted-model requests. The task
  had no external network, host home, upstream key or Docker socket. Containers
  and the dedicated volume were removed. No API credit was spent.
- `openhands_fixture_audit.json` inventories the exact image's installed
  packages and verifies post-run conversion into a six-step native trajectory.
  Its token counts are scripted fixture values, not provider measurements;
  native cost is absent. The inventory is not a hashed dependency rebuild lock.
- All 62 Stage 2 and 12 existing tests pass (74 total). No scored trial ran.
  Live-provider OpenHands qualification, scored-request cost bounds, production
  task isolation, custom harness and the remaining study gates are still open.

2026-09-16 custom backend milestone:

- Installed a separate custom-harness environment, leaving the qualified
  baseline environment unchanged: Deep Agents 0.7.14, LangGraph 1.2.11,
  LangChain 1.4.0, Harbor 0.22.0. `custom_dependency_inventory.json` records
  all 121 installed versions. Input requirements and a hash-locked resolution
  are separate from that observed inventory.
- `custom_backend.py` implements Deep Agents' sandbox filesystem/execute
  interface using only the supplied Harbor environment. Model paths are never
  opened on the Mac. Container-side foreground timeout, explicit output
  truncation, bounded file transfers, and async/thread bridging are covered.
- The first actual graph fixture failed file readback because Docker copy
  preserved host ownership. `custom_agent_probe_result.json` retains that
  failure. The backend now creates files through bounded, quoted commands as
  the container user. `custom_agent_probe_v2.json` passes all seven runtime
  checks: native file/execute tools, no delegation/planning tool, exactly three
  scripted replies, timeout, and quoted-path roundtrip. Disposable containers
  were removed. This is a real Deep Agents graph, not a paid model run.
- `custom_model.py` requires an explicit loopback gateway, explicit bounded
  output, one model, no SDK retry, and no Responses API/streaming. Two tests
  include the actual LangChain/OpenAI client through the real gateway and a
  synthetic ledger/provider. Nine backend tests also pass.
- This is NOT frozen C0: background job polling/interruption, equal bounded
  recovery, completion controls, fixed context policy and full run lifecycle
  still need implementation. No C1/C2 or scored custom results are claimed.
  All fixtures used scripted replies and spent no API credit.

Custom checks use `.tools/stage2-custom/bin/python stage2/custom_backend_tests.py`
and `stage2/custom_model_tests.py`, separately from the original test suites.
Reference: https://docs.langchain.com/oss/python/deepagents/backends .

Final checks for this increment: 62 Stage 2 + 12 existing + 9 custom backend
+ 2 custom client tests passed (85 total). Read-only OpenRouter verification
still reports $25.264980845 credit and $0.00019596 aggregate key usage. No new
paid requests were made. macOS reported no thermal/performance warning, 31%
memory free and 38 GiB disk available. No benchmark fixture container remains.

2026-09-16 custom controller milestone:

- `custom_control.py` implements C0/C1/C2 candidate prompt composition. C1
  adds only planning instructions; C2 requires an explicit C0/C1 parent and
  adds completion-check instructions/validation. Every condition has the same
  two-repair allowance and tool schema. No finalist has been selected or frozen.
- `custom_runner.py` runs the actual Deep Agents graph with explicit completion
  and abandonment, per-trial state, total timeout and no replay. Completion is
  labelled `agent_reported_complete`, never a verifier pass. C2 accepts no-edit
  tasks and records model-supplied observations; it cannot establish that those
  observations are true or exhaustive. The benchmark verifier remains decisive.
- The fixed candidate context policy retains graph conversation state between
  repair invocations, disables LLM summarisation and optional delegation, and
  uses identical filesystem middleware across conditions. Request/body/context
  exhaustion must fail closed rather than silently trim the baseline or input.
- A regression exposed that the library's graph-output call counter did not
  survive our repair reinvocation. A per-runner model-attempt limiter now spans
  every repair; provider/transport exceptions are not automatically retried.
- `custom_jobs.py` adds per-trial start/poll/interrupt handles, maximum four live
  commands and 64 total handles. Signals are executed only inside the container.
  Cleanup stops remaining jobs; the caller must always destroy the container,
  including on cleanup failure. Polling returns output once the command finishes.
- `custom_controller_probe_v1.json` passed nine actual-container checks. After
  output-capture hardening, `custom_controller_probe_v2.json` passed ten: a
  two-million-character command is drained inside the container with only a
  64,000-byte prefix retained, before Harbor/host capture. The previous backend
  truncated only after capture; the new implementation prevents that unbounded
  host-memory path. Command output remains an untrusted task observation.
- Seven pure control tests, six real-graph/controller tests and four job-guard
  tests supplement existing suites. These fixtures used scripted replies and
  made no paid API requests. `budget_qualification.md` explains why the scored
  spending gate remains closed. Full production runtime qualification, live
  integrations, experiment freeze, Langfuse delivery and scored runs remain.

Final candidate checks: 69 Stage 2, 12 existing, 9 custom backend, 2 custom
client, 6 custom runner and 4 custom job tests passed (102 total). The latest
container fixture passed all ten checks and left no running fixture container.
Read-only account verification still reports $25.264980845 credit and
$0.00019596 aggregate usage. No scored trial or new paid request ran.

2026-09-16 spending-bound investigation: three additional paid setup probes
now match the pinned tokenizer on Unicode history and native OpenHands tool
history with reasoning disabled/default. All three used the full-context
reservation and the original $1 setup ledger. Actual additional spending was
$0.00083352; aggregate setup spending is $0.00102948, with no pending requests.
No scored task ran. See `extended_token_calibration_result.json` for all eight
precomputed encoding candidates per request, matches, token usage and costs.

Calibration cannot establish a provider-guaranteed bound for arbitrary future
requests. `budget_qualification.md` now states the material decision explicitly:
an estimated per-trial cap would need risk acceptance and separate full-context
aggregate/stage reservations. No cap was raised and no estimate was enabled.

Final checks for the calibration increment: all 105 automated tests passed
(72 Stage 2, 12 existing, 9 backend, 2 client, 6 runner, 4 job guards).
Read-only account verification reports $25.264147325 available and matching
$0.00102948 aggregate key usage. The study remains paused before scored work.

2026-09-16 approved budget amendment implemented:

The user accepted conservative estimated per-trial admission while retaining
worst-case aggregate protection. Gateway/ledger now persist separate hard and
estimated amounts atomically. Project, stage and account checks still use the
full-context bound; trial checks use previous actual charges plus the estimate.
Any actual charge exceeding the estimate persists a halt across restarts.
Strict setup/pilot ledger behaviour remains the default. Estimation mode must
be explicitly enabled on a fresh scored ledger and cannot be changed on reopen.

`trial_estimator.py` provides the single shared `utf8-envelope-v1` estimator.
The offline receipt audit covers all three additional calibration cases, with
no new API call. See `budget_qualification.md` for the approved residual risk,
formula and integration contract. Scored-run wiring, full runtime qualification
and the remaining experiment gates still precede any benchmark launch.

Verification: all 115 tests pass (82 Stage 2 + 12 existing + 21 custom suites).
The estimate audit reused prior receipts and made no paid call. No new scored
ledger was funded and no benchmark started during this amendment.
