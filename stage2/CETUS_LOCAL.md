# CETUS local study: implementation and execution boundary

Updated 17 September 2026. Branch: `codex/cetus-local-harbor-study`.

## Status

This is **partial implementation, not a completed benchmark**. No baseline or
custom scored trial has started for this track. No OpenRouter request was made
by this implementation. No Langfuse Cloud export has been performed.

Implemented and locally tested:

- Independent local model protocol; no imports from OpenRouter configuration.
- Canonical dataset byte revalidation against the existing provenance record.
- New deterministic category-stratified development subset and coverage table.
- Planned trial keys for the 178 baseline, 100 development, 120 confirmation
  and 89 final-custom cells. This is a schedule, not a launching runner.
- Development ranking with incomplete/invalid evidence rejection.
- Durable metadata-only trace spool with conflict detection and stable IDs.
- Explicit post-run Langfuse OTLP/HTTP JSON exporter; mock transport tested.

Not implemented or not qualified yet:

- The local model has not loaded in an observed GPU allocation. Job 89247 was
  rechecked during this implementation and remained queued in med_gpuq.
- No supported isolated 89-task runtime has been established on CETUS.
- No CETUS Harbor deployment, local inference gateway, full lifecycle adapter,
  or native-baseline local-model compatibility test has passed.
- Trace hooks are not yet attached to a live Harbor runner or LangGraph graph.
- Langfuse credentials/project and live ingestion/dashboard reconciliation
  have not been verified. Spool records deliberately contain no raw task text.
- The local custom harness has not been adapted or evaluated. The existing
  custom code remains pinned to the historical OpenRouter model.
- Leaderboard-specific protocol admission and public submission are unverified.

The existing queued probe is not modified in place and no duplicate GPU job
was submitted. Its three tests do not establish model compatibility.

Verification for this increment: 273 Stage 2 tests, 30 custom dependency tests
and 12 historical pilot tests passed (315 total). Twelve of the Stage 2 tests
are new local-study checks. Mock export acknowledgement is explicitly not a
live Langfuse verification. Canonical dataset bytes were revalidated when
generating the new manifest and again by the tests.

## Approved design

Everything that executes the benchmark stays on CETUS: model, Harbor, native
Terminus-2/OpenHands, custom agent and isolated task environments. Langfuse
Cloud is an observability-only exception. No OpenRouter or external inference
fallback. The Mac is used for development/control, not scored task execution.

Use the official Qwen3-Coder-Next Q4_K_M shards and pinned llama.cpp revision
already registered in `cetus_local_probe.py`. The registered candidate protocol
uses 32,768 context tokens, 8,192 maximum output tokens per request, 100 model
requests per trial, temperature 1.0, top-p .95 and top-k 40. All auxiliary calls
count. No inherited DeepSeek reasoning parameters. Freeze a new protocol
version if qualification or leaderboard requirements require changes; never
mutate a protocol under existing scored cells.

Task environments keep official task limits. Model/controller resources must
be reserved separately. Use bounded sequential PBS blocks and persistent
results. Never start a trial that cannot finish its setup/agent/verifier/cleanup
inside remaining walltime. Do not execute agent commands on login nodes.

## New development subset

`cetus_local_manifest.json` is separate from the historical input manifest.
It contains all 89 canonical task configurations and the 20 selected IDs,
coverage counts, exposure flags, sampling method and manifest fingerprint.
Only metadata influences selection; no reference solution, hidden verifier or
model result enters the selection rule. Other task file bytes are only hashed.

All 16 categories are covered. Four remaining seats are apportioned by largest
remainder using category capacity after the coverage seats. Within categories,
difficulty proportions determine seats, then duration/resource diversity and
fixed SHA256 ties determine tasks. This explicitly oversamples rare categories:
the 20-task dev score is not an unbiased estimate of all-89 accuracy.

Selected tasks:

1. adaptive-rejection-sampler
2. bn-fit-modify
3. caffe-cifar-10
4. chess-best-move
5. compile-compcert
6. constraints-scheduling
7. crack-7z-hash
8. feal-linear-cryptanalysis
9. git-multibranch
10. large-scale-text-editing
11. log-summary-date-ranges
12. merge-diff-arc-agi-task
13. mteb-leaderboard
14. password-recovery
15. polyglot-c-py
16. portfolio-optimization
17. pytorch-model-cli
18. sparql-university
19. torch-pipeline-parallelism
20. video-processing

Coverage is 14 medium / 6 hard / 0 easy. Duration is 6 short / 6 medium / 7 long /
1 unknown. Missing duration metadata is not invented. No task may be replaced
because of poor performance. Historical exposure is disclosed; the other 69
are development-excluded, not an untouched holdout.

## Execution sequence and selection

1. Check job 89247 and finish model qualification, including genuine near-limit
   context and native client tests. Current probe covers only a bounded prompt.
2. Establish a UTS-supported isolated Docker-compatible runtime, or a permitted
   Harbor environment adapter with equivalent semantics. Verify confinement,
   resource enforcement, downloads, services, user/root behaviour, transfer,
   verification and descendant cleanup. Reference-qualify all 89 separately.
3. Verify TB2.1 leaderboard requirements, account/project authority, dependency
   locks and runtime fingerprints before admitting any scored execution.
4. Run Terminus-2 on 89, then OpenHands on 89. Seal non-dev outcomes from custom
   development, including dashboards. OpenHands is the primary comparator.
5. Adapt the existing minimal Deep Agents/LangGraph custom control only after
   baselines qualify. Keep file/terminal operations behind the Harbor backend.
   No subagents, cross-trial memory, external skills or hidden-test feedback.
6. Evaluate C0 then at most four one-lever candidates: planning, completion
   checks, context management, recovery. Each builds on the retained parent.
   All calls use identical limits. Rank by passes, generated tokens, retained
   feature count, runtime, variant ID. Record failures and regressions too.
7. Confirm selected custom and both baselines with two fresh repetitions on 20
   tasks (120 trials). Confirmation does not authorise additional tuning.
8. Freeze finalist and evaluate on all 89, even if development did not win.
   A missing win must be reported, not corrected by score-dependent retries.
9. Audit/export paired scores, uncertainty, token/runtime/resource metrics,
   failure categories, provenance, charts and actual terminal captures.

Maximum planned scored trials: 487, excluding qualification and any separately
registered leaderboard repetition requirements. Preserve reward-zero trials.
Infrastructure-only retries require correction, retain all attempts, and have
a maximum of two retries. Native agent timeouts are not infrastructure retries.

## Observability

`local_trace.py` provides the future runner's metadata hook; `local_langfuse.py`
exports completed spans using the documented OTLP endpoint, not the deprecated
general ingestion endpoint. Exact timestamps and stable trace/span IDs survive
replay. Private local records remain authoritative. Transport acknowledgement
is not dashboard acceptance. No live acceptance is claimed here.

Future wiring must record setup, agent, generation, tools, graph, verifier and
cleanup for each trial. Add LangGraph callbacks using local recording rather
than vendor-default live export. Export after the timed trial. No cloud failure
may change task outcome. External inference spend is zero, but compute cost is
unknown until UTS provides a rate; measure GPU/CPU allocation time separately.

The exporter accepts only the official EU/US/Japan Langfuse Cloud origins and
explicit `LANGFUSE_BASE_URL`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` in the
trusted controller environment. It does not follow redirects or inherit HTTP
proxies. Do not place those keys in this repository or task environments.
Do not create a project or send data under an assumed account identity.

## Run offline checks

From the repository root:

```sh
.tools/uv-tools/harbor/bin/python -m unittest discover -s stage2 -p 'test_*.py'
.tools/stage2-custom/bin/python -m unittest discover -s stage2 -p '*_tests.py'
.tools/uv-tools/harbor/bin/python -m unittest discover -s tests
```

Rebuild a candidate manifest using `local_study.py --output <new-path>`; it
refuses to overwrite the frozen file. Tests revalidate canonical dataset bytes.
No test result in this document is a benchmark score.

## Unresolved external dependency

Network-none fixtures succeeded, but the earlier CETUS compute-node check
explicitly denied bridge networking. It did not demonstrate hard task cgroup
limits. Read-only reinspection found Apptainer but no Docker or Podman on PATH;
that does not prove an administrator-supported service is unavailable.

UTS needs to identify/provide an approved isolated task runtime and resource
enforcement, or supply evidence of an existing supported configuration. Until
then the scored execution gate remains closed. Do not install networking or
privilege workarounds. Model loading alone does not remove this blocker.

Official integration references:
- https://huggingface.co/Qwen/Qwen3-Coder-Next
- https://docs.harborframework.com/core-concepts/agents/custom-agents
- https://docs.harborframework.com/core-concepts/sandboxes/custom-sandboxes
- https://docs.langchain.com/oss/python/deepagents/overview
- https://langfuse.com/integrations/native/opentelemetry
- https://www.tbench.ai/benchmarks
