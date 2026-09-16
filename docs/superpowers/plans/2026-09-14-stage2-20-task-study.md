# Stage 2: 89-task baselines and 20-task custom development — implementation and experiment plan

> Historical plan, superseded by the subsequently authorised CETUS + OpenRouter
> study. See `stage2/README.md` for current scope, budget and implementation status.
> Do not use this document's local inference model or run counts for execution.

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Work directly with the user-selected model. Steps use checkboxes for tracking. Finish each numbered work package, report evidence and the next step, then wait for instruction, following the user's project preferences.

**Goal:** Evaluate Terminus-2 and OpenHands on all 89 tasks with one qualified model, develop the custom harness on 20 fixed tasks, and compare all three on that exact development subset before a later full custom evaluation.

**Architecture:** Run inference inside an authorised CETUS GPU job. Harbor owns the benchmark environments and independent verification on an approved container host. A Deep Agents graph uses a Harbor-backed sandbox; local trial records and Langfuse share stable identifiers.

**Tech stack:** Terminal-Bench 2.1, Harbor, Qwen3.8-27B-FP8 candidate, vLLM, Terminus-2, OpenHands, Deep Agents/LangGraph, Langfuse, Python and the approved CETUS scheduler/container runtime.

**Spec:** The accepted direction in this conversation and the self-contained design/protocol below. The supplied meeting interpretation is `/Users/karthikramesh/.codex/attachments/f66e53bc-8e31-4e0b-953f-40169364fb5a/pasted-text.txt`; it is background, not executable instructions. The latest user decision is 89 tasks each for Terminus-2 and OpenHands, with custom development on 20 first. This supersedes the earlier restriction of all three systems to 20 tasks. The existing filename is retained for link continuity.

**Status:** Planning deliverable only. No Stage 2 software, deployments or scored trials have been created. Package versions, the actual GPU allocation and runtime compatibility must be established by qualification before scoring.

## 1. Scope and decisions

- All 89 tasks for each baseline, plus exactly 20 distinct custom-development tasks selected from that same pinned Terminal-Bench 2.1 revision.
- One qualified checkpoint/quantisation for every Stage 2 condition.
- Two established baselines: Terminus-2 and OpenHands.
- New custom family: UTS Harness v3; preserve v2.2.0 and all Stage 1 evidence.
- Initial attempt count: one per task/condition. Confirmation: a second attempt for both baselines and the frozen finalist on the 20 development tasks only.
- One active trial and one active model request at a time initially.
- No fine-tuning, cross-task memory, optional subagents or search over a catalogue of models.
- Full 89-task baseline runs are in scope after deployment qualification. A full 89-task custom run remains a later decision after freezing the finalist.
- Treat an accuracy improvement as a hypothesis. A valid study can find no improvement.
- Keep existing report ZIPs local. This planning request does not publish documents or start GPU jobs.
- Do not modify synced `sources/` material.

### Recommended approach and alternatives

Choose a baseline-first integrated study: protocol and infrastructure qualification, full baseline evaluation, a minimal custom control, policy experiments, then development confirmation. Run the development tasks first within each baseline's 89-task schedule so compatibility problems surface early; those accepted trials count towards the full baseline total and are not rerun merely to complete the 89-task batch.

Building all policies before a baseline would shorten the apparent start-up phase but leave model compatibility and usefulness unknown. Keeping all work on the laptop would reuse more infrastructure but does not establish the proposed GPU deployment and leaves long-run host reliability unresolved. The preferred path uses the laptop for orchestration during integration only if necessary; the benchmark host must be settled before scored trials.

### Evidence already inspected

The repository is at `6d10c4e` with no pre-existing working-tree changes at planning start. `scripts/run_matrix.py` fixes the old task count at 21, the two Qwen2.5 models and custom version 2.2.0. `scripts/custom_harness.py` contains the edit/test gate and 120-second command limit. Reuse lessons and parser concepts, not the old matrix identity or runtime defaults.

Stage 1 remains 126 intended cells, 125 valid verifier outcomes and zero passes. Stage 2 changes several factors; any Stage 1 versus Stage 2 improvement cannot be attributed solely to the new harness.

## 2. Study protocol

### Task selection and exposure

Select before any Stage 2 model scoring. Enumerate task IDs from the pinned dataset; compute SHA-256 of UTF-8 `uts-stage2-dev20-v1:42:` followed by each task ID; order by digest and then task ID; take the first 20. Record the algorithm, dataset revision, complete candidate list and selected-list hash.

This is a reproducible sampling rule, not a claim of statistical representativeness. Record categories and overlap with all Stage 1 tasks. Do not remove a task because it is hard, slow or failed previously. Treat the entire set as development data, including any task with earlier exposure.

Run official Oracle validation separately on these 20. A failure stops qualification for diagnosis; do not repeatedly replace tasks until an easy/compatible subset appears. Any necessary dataset or selection revision must precede scoring and be documented as a protocol change. Synthetic backend tests are software tests, not newly authored benchmark tasks and never enter scoring.

Also freeze the full 89-task manifest and its 69-task complement. Preflight environment availability and official resources for all 89 before dispatching baseline jobs; additional Oracle diagnostics outside the 20 are separately accounted for and never shown to the custom agent. Keep baseline scores and trajectories for the other 69 outside custom-development views until the finalist is frozen. Operational health checks may inspect infrastructure errors, but must not feed task solutions or performance patterns into policy decisions. Some of those 69 may overlap Stage 1: record exposure per task and describe them as outside current development, not universally unseen.

### Model and resource freeze

First candidate: `Qwen/Qwen3.8-27B-FP8`. The model card reports a parent-model Terminal Bench 2.1 (Terminus) score of 73.0. This is external reference evidence, not a local result or promised score. [Official model card](https://huggingface.co/Qwen/Qwen3.8-27B-FP8).

Request/confirm an L40 48 GB allocation through the authorised CETUS process. Actual GPU memory, scheduler, driver, container support and tunnel policy must be captured from the authorised environment. Weight-size arithmetic is not a memory-fit test. Never place model inference on a login node.

Qualification starting configuration:

- 32,768-token total context; up to 8,192 generated tokens per model call, reduced to available context room by the common serving layer.
- Thinking enabled; temperature 1.0, top_p 0.95, top_k 20, min_p 0, presence_penalty 0 and repetition_penalty 1, following the candidate's current documented thinking configuration. Record resolved chat template, reasoning parser and tool parser. Check every outgoing request, not only configuration files. [Model guidance](https://huggingface.co/Qwen/Qwen3.8-27B-FP8).
- Preserve each baseline's native context handling and tools. Freeze the custom control's resolved middleware/context policy across its variants. Any auxiliary model call must use the same checkpoint and count towards usage.
- Keep official task resource and time limits unchanged. Use a common additional study ceiling of 262,144 generated tokens per trial, including reasoning and auxiliary calls; label this explicitly as a local study restriction. Clamp requests to the remaining allowance through a common metering layer. If reliable total output accounting cannot be established, do not claim this cap is enforced; revise the protocol before scoring.
- Do not force equal framework iteration counts. Count all calls, actual input/output usage and elapsed time; include them in analysis.
- Prefix caching starts disabled for the main study. This removes an unverified serving dependency from accuracy qualification. The separate cache study below measures whether enabling it is useful.

These are proposed qualification settings. Test capacity and wire compatibility before locking them. If they must change, record the reason and resolve all baseline/custom clients before any score is accepted. Once the first scored qualification begins, changes create a new protocol ID; results under different protocols cannot be pooled. If the 8,192 output limit truncates actions during compatibility tests, settle a larger feasible limit and corresponding context before scoring.

### Outcomes and comparison rules

Publish two separate tables: full-baseline results use official passes / 89 intended tasks; the three-way development comparison uses passes / the exact same 20 tasks for every harness, extracting baseline rows by task identity. Never compare custom passes / 20 directly with baseline passes / 89 as an accuracy ranking. Report valid-verifier coverage and pass / valid as a secondary measure when coverage is incomplete. Keep reward-zero outcomes, agent timeouts and malformed actions in the intended denominator. A later full custom comparison requires a frozen finalist on all 89 under a compatible protocol.

Distinguish: verified pass; verified non-pass; agent termination without verification; pre-execution infrastructure failure; interrupted execution; verifier infrastructure failure. Preserve exception fields even when a verifier returns reward zero.

A clearly documented pre-agent setup failure may receive one infrastructure replacement. Retain both attempts and explicit supersession links. An ambiguous interruption or post-execution failure requires an auditable classification before retry; no automatic best-result selection. Never retry an agent failure as if it were setup failure. If coverage is incomplete after allowed correction, report the stage incomplete instead of presenting a complete comparison.

Resume identity is `(protocol_hash, dataset_revision, task_id, condition_hash, repetition_index)`. An attempt also has a unique ID. Do not select the latest or highest reward when several records exist. The run ledger explicitly identifies the accepted attempt under the correction policy.

## 3. Conditions and run budget

| ID | Condition | Only planned difference | Trials |
|---|---|---|---:|
| B1 | Terminus-2 | Native established baseline; full dataset | 89 |
| B2 | OpenHands | Native established baseline; full dataset | 89 |
| C0 | Custom control | Qualified Deep Agents/Harbor integration; built-in capabilities disclosed | 20 |
| C1 | Planning | Concise task-specific planning instruction over C0 | 20 |
| C2 | Completion | Task-aware completion policy over retained parent | 20 |
| C3 | Recovery | Up to two explicit repair cycles after failed self-checks over retained parent | 20 |
| Confirmation | B1, B2, frozen finalist | Second attempt on dev20 only, no edits between runs | 60 |
| Ablation | Finalist minus strongest retained policy | Remove one policy, otherwise identical | 20 |

Maximum planned scored workload: 338 trials: 178 full-baseline trials + 80 custom discovery trials (C0–C3) + 60 development confirmation trials + 20 ablation trials. Full baselines plus C0 total 198 trials; the matched three-way development table contains 60 of those rows. B1's first 20 are included in its 89, not an additional batch. Oracle runs, deployment probes and cache replays are separately accounted for. If no policy is retained, omit the ablation and unnecessary variants. A later full custom evaluation is outside this count: budget 89 fresh finalist trials so results from earlier evolving variants are never assembled into a supposed full finalist run. That would bring the maximum including that future run to 427.

Use the fixed development-task order first, then the 69-task complement in the same hash ordering. After initial baseline qualification, rotate baseline condition order across remaining tasks and record actual order and timestamps. Custom development necessarily runs later; disclose this and use the paired dev20 confirmation block for a less order-confounded comparison. Use recorded repetition seed 42 for discovery and 43 for confirmation where supported. Seeds do not guarantee identical stochastic model behaviour across harnesses or GPU runs.

Retention rule, applied to each complete 20-task candidate versus its declared parent: retain for the accuracy finalist only if it gains at least one net verified pass, has no new invalid trials, and meets the common resource policy. Report per-task gains and losses. This rule identifies a development candidate; one extra pass is not statistical proof. An equal-pass version may be recorded as an efficiency alternative but is not automatically the parent for the accuracy sequence. If C2 is rejected, C3 does not silently retain it: bounded recovery can use the parent's existing self-check observations, and the exact parent/policy diff must be recorded before running.

B1's first 20 tasks provide a capability checkpoint: at least 10/20 passes meets the proposed development target. A lower score alone does not cancel the requested full baseline evaluation; continue a healthy, correctly configured 89-task run while recording the capability concern before policy development. Actual deployment faults stop dispatch for correction. Any correction to frozen model/settings creates a new protocol and requires both complete baseline conditions to be comparable under it; do not splice old and new settings. If the qualified model remains weak, present the measured resource/model decision before custom policy experiments, without task-shopping.

## 4. Custom design

Deep Agents supplies the graph foundation. There is no second independent agent loop. A small adapter binds it to Harbor's task lifecycle; the backend routes terminal and filesystem operations into that trial's container. The backend must never default to the host filesystem or graph-only state for final task artifacts. [Deep Agents backend documentation](https://docs.langchain.com/oss/python/deepagents/backends).

Tools: execute, poll, read, edit, list and search inside the supplied environment. Long commands return a process/session handle; polling reports running versus completed with exit code. Agent cancellation and the official deadline stop trial-owned processes. No blanket 120-second kill rule. An individual poll yields after at most ten seconds; command lifetime is bounded by the remaining official agent deadline.

C0 preserves and documents built-in planning and repair behaviour. C1 tests a different instruction policy, not the invention of planning. C2 asks for evidence appropriate to the task: artifact checks, service checks, tests or another observed condition. It never requires editing for every task or treats exit zero alone as completion. C3 adds at most two explicit repair cycles after a failing agent-visible self-check; existing ordinary error handling stays disclosed.

Agent tools cannot read hidden verifier code, Oracle solutions, historical task answers, experiment results or Langfuse scores. Verifier results attach after agent termination. New trial IDs get fresh graph state, scratch storage and process registry. Resolve the complete tool list and middleware: optional delegation and default external-model fallback must be absent, rather than assuming a configuration flag removes them.

## 5. File and responsibility map

All paths below are relative to the repository. They are planned files, not files that already exist. Stage 1 source and evidence remain usable unchanged.

| Files | Responsibility |
|---|---|
| `stage2/pyproject.toml`, `stage2/uv.lock` | Isolated, pinned Stage 2 dependency environment |
| `stage2/config/protocol.json`, `all89.txt`, `dev20.txt`, `outside_dev69.txt`, `exposure.csv` | Frozen full/development manifests and exposure identities |
| `stage2/config/baselines/{terminus2,openhands}.json`, `variants.json` | Resolved baseline and custom condition configurations |
| `stage2/deploy/serve.pbs`, `model-server.sh`, `README.md` | Qualified scheduler job, model startup and connection procedure |
| `stage2/uts_stage2/protocol.py`, `select_tasks.py` | Schema checks, canonical hashes and selection |
| `stage2/uts_stage2/qualification.py`, `metering.py` | Deployment/wire probes, shared usage accounting and limits |
| `stage2/uts_stage2/harbor_adapter.py`, `sandbox_backend.py` | Harbor lifecycle and actual task-environment tools |
| `stage2/uts_stage2/agent.py`, `policies.py` | Frozen graph construction and isolated policy variants |
| `stage2/uts_stage2/run.py`, `ledger.py` | Single-run lock, schedule, resumability and append-only attempt records |
| `stage2/uts_stage2/tracing.py`, `export_atif.py` | Local events, baseline trajectory export and Langfuse join |
| `stage2/uts_stage2/analyze.py`, `cache_replay.py` | Audited tables, paired analysis and separate cache study |
| `stage2/tests/test_*.py` | Focused protocol, backend, lifecycle, accounting and analysis tests |
| `stage2/evidence/<protocol-id>/` | Manifests, attempts, coverage audits and report artifacts |

Use public Python APIs from the versions actually locked in Work Package 2. Record the exact Harbor agent and Deep Agents backend method signatures in the integration report before writing the adapter. Do not copy hosted-Harbor APIs into a local Harbor integration or assume current online examples match Harbor 0.22.0.

## 6. Numbered implementation work packages

Each package ends with a reviewable deliverable. During execution, use targeted failing tests for new behaviour, implement the smallest passing change, then run affected checks. Commit only completed implementation units under the execution authorisation; no automatic push. The commands below describe the proposed Stage 2 CLI and test contract, not currently runnable commands.

### Work Package 1 — Freeze the protocol and task identities

Files: `stage2/config/`, `protocol.py`, `select_tasks.py`, `tests/test_protocol.py`.

- [ ] Implement task selection using the exact hash ordering above; compare input order reversal to prove identical output.
- [ ] Validate 89 unique full-dataset IDs, 20 unique development IDs and a disjoint 69-task complement whose union is all89. Reject changed dataset hashes and any condition selecting the wrong task set.
- [ ] Make baseline discovery select all89 by default and custom discovery/confirmation/ablation select dev20. Require an explicit later full-finalist phase for custom all89 dispatch.
- [ ] Record overlap with `configs/progress_subset.txt`; no claim that a previously exposed task is unseen.
- [ ] Produce protocol hash from canonical configuration; ensure changing model revision, condition or repetition changes identity as applicable.
- [ ] Make missing deployment-lock fields block scoring with an explicit qualification error.

Validation: `uv run --project stage2 pytest stage2/tests/test_protocol.py -q` after the environment exists. Fixtures must show reversed task enumeration produces identical selection and changing one frozen setting invalidates a run manifest.

Exit evidence: draft protocol, all89/dev20/outside_dev69 manifests and exposure table. The protocol becomes scoring-ready only after deployment qualification locks the concrete runtime fields.

### Work Package 2 — Qualify infrastructure and serving

Files: `stage2/pyproject.toml`, lockfile, `deploy/`, `qualification.py`, `metering.py`, `tests/test_metering.py`.

- [ ] Verify authorised CETUS access, allocation, scheduler and container-host location; record `nvidia-smi`, driver, runtime and actual GPU capacity.
- [ ] Resolve and pin checkpoint revision, tokenizer/template, vLLM, Harbor, baseline packages and Deep Agents/LangGraph versions in the isolated environment.
- [ ] Test FP8 load and a near-limit context request; record peak GPU memory and latency. Test from the actual benchmark container over the approved connection.
- [ ] Run five complete action/output/action smoke cycles for each baseline interface and the proposed custom model client. Check reasoning/tool separation, escaped arguments, a failing command and a subsequent corrective action.
- [ ] Verify the shared metering path captures auxiliary calls and clips each response allowance to the remaining trial budget. Test that an exhausted trial makes no new model request.
- [ ] Exercise server disconnect and job-expiry handling. Stop dispatching before insufficient allocation time remains for the official trial allowance plus measured setup/verification allowance and five minutes of scheduling margin.
- [ ] Run the separate 20-task Oracle checks and archive their evidence outside model score tables.
- [ ] Preflight task environment availability and resource requirements for all 89 without revealing the other 69 task outcomes to custom development.
- [ ] Freeze all concrete runtime fields. Save a compatibility report including actual method signatures for the two adapters to be implemented.

Exit evidence: pinned deployment manifest, passing interaction probes for all interfaces, Oracle coverage, runtime/memory measurements and a protocol that validates as scoring-ready. A chatbot response alone cannot satisfy this gate.

### Work Package 3 — Build the ledger and evaluate both full baselines

Files: `run.py`, `ledger.py`, `tracing.py`, baseline config files, `tests/test_ledger.py`.

- [ ] Implement explicit trial identity and atomic append-only state transitions: queued, started, agent_finished, verifier_finished, accepted or classified interruption.
- [ ] Test that a second matrix process cannot acquire the same run lock; stale lock recovery must verify owner termination.
- [ ] Test that reward-zero and agent-timeout entries are terminal, missing cells resume, and setup replacement requires an explicit classification/supersession record.
- [ ] Persist local model/tool/trajectory identifiers before adding remote tracing. Exercise interruption between writing result and updating the ledger without duplicate execution.
- [ ] Run the first 20 B1 trials once, preserving native Terminus behaviour except documented model connectivity, common limits and logging. Record the capability checkpoint.
- [ ] Complete B1's remaining 69 and B2's full 89 under the same frozen protocol. Do not rerun the accepted first 20 B1 cells.
- [ ] Publish a baseline-only all89 summary and a separate dev20 extract. Restrict outside_dev69 scores/trajectories from custom-development views until the finalist is frozen.
- [ ] Produce the dev20 capability/failure report before substantial policy work; healthy baseline runs continue regardless of the 10/20 target.

Validation: `uv run --project stage2 pytest stage2/tests/test_ledger.py -q`; proposed dry-run contract `uv run --project stage2 python -m uts_stage2.run --protocol stage2/config/protocol.json --condition B1 --repetition 0 --dry-run` must list exactly 89 unique intended cells and start none. A fixture with the first 20 accepted must schedule only the other 69; B2 must independently list 89.

Exit evidence: 178 baseline cells (89 per harness), matched dev20 extracts, raw evidence joins, restricted outside-dev artifacts and a go/revise decision for custom development based on actual dev20 results.

### Work Package 4 — Integrate the minimal custom control

Files: `harbor_adapter.py`, `sandbox_backend.py`, `agent.py`, `tests/test_backend.py`, `tests/test_agent_contract.py`.

- [ ] Write a backend test that creates a file through the agent backend and reads identical bytes through Harbor's environment interface.
- [ ] Cover quoted paths, missing files, binary-file rejection by text tools, search output limits, concurrent process handles and cancellation.
- [ ] Test a command running longer than one polling interval, then completing normally. Deadline cancellation must clean up only this trial's processes.
- [ ] Test two trial environments with the same path; writing in one cannot affect the other or the host.
- [ ] Instantiate C0, inspect its resolved tools/model clients, and prove optional delegation/external-provider fallback are absent.
- [ ] Run fixture integration checks; then execute C0 on dev20 under the frozen protocol. Reuse B1/B2's accepted dev20 rows from their full baseline runs.
- [ ] Audit 198 accepted cells: 178 baselines plus 20 C0. Build the matched 60-row dev20 table by task identity. Report baseline agent versions and model-client adaptations.

Validation: `uv run --project stage2 pytest stage2/tests/test_backend.py stage2/tests/test_agent_contract.py -q`, followed by real Harbor-container artifact round-trip and lifecycle checks. Mock tests alone do not establish backend correctness.

Exit evidence: a matched 60-row development comparison drawn from 198 accepted trials, verified real-container artifact handling, isolated state and baseline/custom trajectory coverage.

### Work Package 5 — Link comparable observability

Files: `tracing.py`, `export_atif.py`, `tests/test_tracing.py`.

- [ ] Use a stable trial root for model calls, tools and self-check/recovery events. Attach Harbor verifier outcome only after execution finishes.
- [ ] Export baseline trajectories using the locked Harbor/agent format; preserve raw evidence when an event has no comparable field.
- [ ] Capture available usage and latency at the common model boundary for all conditions. Use null for unavailable metrics, including reasoning or cache fields.
- [ ] Test retries do not double-count a generation; repeated upload is idempotent; offline Langfuse logging preserves local events for later export.
- [ ] Redact secrets, flush the async event queue on normal exit, and verify at least one real trace per condition joins its result and raw trajectory.

Exit evidence: three trace/result/trajectory joins, metric-coverage table and logging overhead measurement. Basic local evidence is required from B1; remote dashboards may be backfilled to avoid blocking baseline qualification. [Langfuse integration](https://langfuse.com/integrations/frameworks/langchain-deepagents).

### Work Package 6 — Run controlled policy experiments

Files: `policies.py`, `config/variants.json`, `tests/test_policies.py`.

- [ ] Encode C0 and each candidate's parent hash, exact prompt/policy diff and unchanged dependency/settings hashes.
- [ ] Test C1 changes planning instructions only; no extra tools or extra model budget appear.
- [ ] Test C2 can finish a read-only/service task with suitable evidence and rejects unsupported completion without consulting hidden verifier data.
- [ ] Test C3 receives actual failed self-check observations, performs at most two explicit repair cycles and stops at the shared deadline/token ceiling.
- [ ] Run at most 20 trials per candidate, apply the declared retention rule and log all outcomes before choosing the next parent.
- [ ] Publish net task gains/losses and failure categories: parsing, context/output truncation, planning, incorrect action, premature completion, recovery exhaustion, resource exhaustion and infrastructure.

Validation: `uv run --project stage2 pytest stage2/tests/test_policies.py -q` plus candidate-versus-parent configuration-diff audit. Failure categories are evidence-backed annotations; uncertain causes remain uncertain.

Exit evidence: up to 258 discovery trials (178 baseline + 80 custom), an explicit candidate lineage and one frozen finalist. All custom policy selection uses dev20 only. Framework sophistication is not a selection metric.

### Work Package 7 — Confirm, ablate and measure caching

Files: `cache_replay.py`, frozen finalist configuration, confirmation schedule.

- [ ] Freeze the finalist and run a second repetition for B1, B2 and that finalist on dev20 only: 60 new trials, no policy edits. No second full-baseline repetition is included.
- [ ] If at least one policy was retained, remove the strongest one and run one 20-task ablation with the same repetition seed as the corresponding finalist attempt.
- [ ] Keep all confirmation outcomes even if the apparent improvement disappears. Further tuning begins a new development round, outside this bounded plan.
- [ ] For caching only, select a predeclared saved development request sequence, replay identical requests with caching off/on in five alternating pairs, with a verified cold cache at each sequence start and reuse only within the sequence.
- [ ] Record server cache-hit evidence, TTFT when supported, elapsed time, input/output sizes and GPU memory. Keep output-generation differences visible; do not attribute total latency changes to prefill alone.
- [ ] Report cache replay as serving-efficiency evidence, never as extra benchmark passes. If the locked architecture/server cannot verify cache behaviour, report unsupported and preserve the main experiment. [vLLM caching](https://docs.vllm.ai/en/latest/features/automatic_prefix_caching/).

Exit evidence: paired confirmation table, one focused ablation when applicable and a separately labelled caching report.

### Work Package 8 — Audit and deliver the stage report

Files: `analyze.py`, `tests/test_analysis.py`, `stage2/evidence/<protocol-id>/`.

- [ ] Check exactly 89 identities for each baseline discovery condition; exactly 20 for every custom discovery, development confirmation and ablation condition. Validate that each dev20 baseline extract matches its full-run rows exactly, with unique accepted cells and explicit replacement links.
- [ ] Test an analysis fixture with pass, verifier fail, invalid agent outcome, missing trial and superseded setup attempt; totals must keep intended cells visible and exclude superseded attempts from accepted scores.
- [ ] Publish baseline all89 results separately from matched three-way dev20 results. For development confirmation, publish second-attempt results and per-task mean outcomes across two dev20 attempts for B1/B2/finalist; never pool custom variants or mix 89-task and 20-task denominators. Do not mix baseline extra dev20 repetitions into the single-attempt all89 score.
- [ ] Calculate paired task gains/losses and exploratory task-cluster bootstrap intervals with 10,000 resamples and seed 42. With repeated outcomes, resample whole tasks, retaining both observations per task. Explicitly note development selection bias and the small sample.
- [ ] Report median and p90 runtime, all-attempt compute including corrections, model usage coverage, actual allocation hours and external API charges separately. Do not call allocated HPC compute free.
- [ ] Deliver protocol/model locks, CSV, summary, policy lineage, failure analysis, raw evidence index, representative successful/failed traces where they exist, authentic trace screenshots and decision log.
- [ ] Label generated tables/renderings as such; do not present a CSV-rendered image as a live terminal screenshot. If no successful trace exists, state that.
- [ ] Prepare a local report-only package if requested; source code remains in the implementation repository and report ZIP publication remains disallowed without a new request.

Validation: `uv run --project stage2 pytest stage2/tests -q` and `uv run --project stage2 python -m uts_stage2.analyze --protocol stage2/config/protocol.json --audit`. Success requires coverage/hashes/joins to pass; incomplete results cannot be labelled final.

Exit evidence: reproducible full-baseline results and a matched 20-task custom-development study, with a recommendation to proceed, revise or stop. Only the custom full-89 evaluation requires a later decision; baseline full-89 execution is already part of this plan.

## 7. Allocation, team ownership and stop conditions

| Workstream | Suggested owner | Accountable output |
|---|---|---|
| Protocol and coordination | Member 1 | Frozen decisions, exposure and run budget |
| CETUS and serving | Member 2 | Qualified model job and connection |
| Baselines and ledger | Member 3 | Correct B1/B2 trials and resumability |
| Custom backend/control | Member 4 | Real environment tools and C0 |
| Policies | Member 5 | One-change variants and lineage |
| Observability/analysis | Member 6 | Trace joins, audits and report |

These are responsibilities, not automatic Codex subagent delegation. Work packages are reviewed at their boundaries; hardware-dependent work sets the critical path.

Measure actual average trial time after B1's development checkpoint, then update using all89 baseline measurements. Planning estimate for N remaining trials: N × observed end-to-end mean, plus measured setup and verification not already included, plus 30% operational contingency. Report queue delay separately. At 10 minutes per trial, 178 baseline trials are 29.7 hours; 258 discovery trials are 43 hours; the full 338-trial stage allowance is 56.3 hours before Oracle/probes/queue/contingency. A future 89-trial custom run adds 14.8 hours at that illustrative rate. These are not runtime promises.

Stop new dispatch if the model server loses health, allocation time cannot fit a task, disk is below 20 GB, or the host reports critical memory/thermal pressure. Preserve evidence and classify any in-flight interruption. Resume only under the same locked protocol or explicitly start a new one. If the Mac is used temporarily, allow display sleep while holding system wake for the job; do not silently expand to overnight laptop-heavy inference.

Before implementation, the first factual dependencies to resolve are authorised CETUS access/allocation, an approved container host, and an approved Langfuse destination. The local protocol, tests and adapter design can progress independently of credentials; actual GPU qualification cannot be reported until it runs.

## 8. Definition of done and decision

The stage is complete when the protocol is pinned, B1 and B2 each have one complete 89-task run, B1/B2/finalist each have two recorded dev20 repetitions, the planned policy outcomes are accounted for, evidence audits pass, and the report explains results and resource use. Reduced execution requires an explicit decision entry and honest incomplete/reduced-scope reporting.

A recommendation for the custom finalist's all89 run requires a stable deployment, a frozen finalist, a completed matched dev20 comparison and a measured allocation estimate. Reuse the full baseline results only if dataset, model revision, serving settings, baseline versions and resource policy remain compatible; record environment drift and qualify it rather than assuming old results remain comparable. Run the frozen custom finalist on all89 after the later decision; disclose exposure and report outside-dev performance separately. A custom accuracy gain is desirable but not mandatory for a useful larger study.

## 9. Planning self-review

- Scope: 89 tasks per baseline; 20 fixed tasks for custom development; only the full custom run is gated for later.
- Preservation: Stage 1 code/results and local-only report packages retained.
- Fairness: pinned model, common time/token limits, original baseline behaviour disclosed, all auxiliary calls counted.
- Causality: C0 and exact parent diffs; confirmation is still development evidence.
- Integrity: explicit accepted-attempt ledger, no reward-based replacement, no verifier feedback in the action loop.
- Observability: real trace joins, nullable metrics and original artifacts survive dashboard failure.
- Dependencies: hardware/API qualification is an explicit deliverable, not an assumed success.
- Workload: 178 baseline + 80 custom discovery + 60 dev20 confirmation + up to 20 ablation = at most 338 scored trials, plus separately recorded Oracle/probes/cache replay. A later full custom run adds 89 fresh trials.
- Exposure: outside_dev69 baseline outcomes are excluded from custom tuning; prior Stage 1 overlap is recorded and prevents claims that all 69 are unseen.

This document is a complete stage plan. Package-specific implementation details are resolved against the pinned APIs in Work Package 2; no untested runtime API signatures are asserted here.
