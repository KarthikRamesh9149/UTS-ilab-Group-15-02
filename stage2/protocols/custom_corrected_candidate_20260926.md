# Custom harness: corrected-protocol candidate

**Current status:** The 0.2 C0 block stopped with four retained attempts after
live compatibility failures. Do not resume or patch that deployment. The
[separate 0.3 repairs](../results/custom-compatibility-20260926/README.md) are
offline candidates and need new native qualification/registration. The
description below preserves the original 0.2 protocol and setup history.

26 September 2026. **Setup candidate, not a paid launch or a final freeze.**
The completed 178 baseline results and 30 timeout-diagnostic results stay
unchanged. Their server deployments must not receive these source edits.

## Implemented

`corrected_custom_agent.py` adds a separately versioned Harbor agent,
`stage2-candidate-0.2.0`. It uses the existing Deep Agents/LangGraph controller
and container-only backend, with these execution changes:

- Exact corrected-baseline settings: `deepseek/deepseek-v4-flash-0731`,
  `deepinfra/fp8`, no fallback, temperature 1, top-p 1, high reasoning,
  maximum output 384,000 tokens. There are no per-agent settings overrides.
- No 100-call ceiling. Calls are still counted. The official task deadline
  remains enforced. LangGraph uses `sys.maxsize` as its required integer
  recursion guard, not as an experiment allowance.
- The same host-controlled deadline wrapper as the native baselines. The
  client has no SDK retries; the shared gateway handles undelivered transient
  requests, Retry-After, provider identity, authentication and credit errors.
- Private, one-attempt markers and trajectories; no claim of task success
  before the official verifier. Background task services remain available
  until verification, then the existing orchestrator must revoke and clean up.
- Setup checks `python3`, which the container backend actually invokes.

The legacy adapter still requires its explicit positive call limit. Its
recorded source/deployment is not overwritten. `custom_execution_limits.json`
remains historical and is not used by this new adapter.

This compatibility work does not change the registered design levers. C0 is
the minimal control; C1 adds planning instructions; C2 adds completion checks
to an explicitly chosen C0/C1 parent. All retain the existing two incomplete-
completion corrections. That is a completion-policy choice, not a model-call
budget. Tools, output bounds, lack of delegation and context handling otherwise
remain unchanged. No held-out answers or diagnostic failure details informed
these changes.

## Matched development comparison

`corrected_custom_scope.py` reads only the saved dev20 baseline CSV and its
protocol/input bindings. It checks the original deterministic task order,
exactly 20 unique rows per baseline, binary scores, original result hashes,
cleanup and model revocation. An edited comparator CSV is rejected.

| Baseline on the same fixed 20 tasks | Passed | Failed |
|---|---:|---:|
| Terminus-2, primary comparator | 14 | 6 |
| OpenHands, secondary comparator | 10 | 10 |

These are existing corrected-baseline results, not new runs. There is no need
to repeat them. Neither comparator is selected after looking for a weaker
score. Custom `/20` must be compared with these `/20` rows, not full `/89`
scores or recovered diagnostic passes.

Input manifest SHA256:
`a33de38d1794617b2acc7c50b1f997da49c34b7df5032b481f023184e4aacbc7`.
Matched CSV SHA256:
`8d7a7ba671d3987c7fe92246f2580e737f66c59a68e1513e85ac3b73c9959783`.
The scope inspector is read-only and always reports `paid_launch_ready=false`.

## Verification and remaining implementation

The initial local-only checkpoint below is historical. The subsequent runtime
at `da9b4a8` passed 120 native tests and all four real-Docker synthetic
rehearsals with zero paid calls. See the [setup evidence](../results/custom-setup-20260926/README.md).
No paid custom score or finalist freeze exists yet.

The local tests exercise the real Deep Agents graph and OpenAI-compatible
client against synthetic task/provider responses. They include 104 model
calls, an official-deadline timeout, cancellation, no task replay, every custom
variant, deferred cleanup, and a simulated 429 through the actual shared
retry code and host bridge. Unknown request cost stays unknown. Docker RPC
and task execution in this local test are synthetic; it is not the required
native Docker qualification and is not evidence of benchmark accuracy.

Validation on this candidate: 31 new tests passed. Stage 2 discovery ran 926
tests: 925 passed and one pre-existing check was skipped. The
separate 34-test legacy custom suite also passed. Commands:

```sh
PYTHONPATH=stage2 .tools/stage2-custom/bin/python -m unittest discover -s stage2 -p 'test_*.py' -q
PYTHONPATH=stage2 .tools/stage2-custom/bin/python -m unittest discover -s stage2 -p 'custom_*_tests.py' -q
```

A read-only server inspection at 01:02:37 UTC found no active study service,
owned trial container or matching matrix process, and no custom deployment
directory. Its existing environment has Harbor 0.22.0, Deep Agents 0.7.14,
langchain-openai 1.6.2 and LangGraph 1.2.11. These are inventory observations,
not qualification of the new source.

## Uncapped development execution

The user explicitly authorised no custom spending cap, no reserve and no
artificial API-call cap on 26 September. `corrected_custom_policy.py` records
that scope separately from baseline authority. It does not authorise buying
credit, changing account/key limits or bypassing actual provider limits.

`run_corrected_custom.py` now supports real `stage=development` passive
accounting. It registers the exact fixed 20 cells before each C0/C1/C2 block,
binds current source, dependencies, gateway images and native qualification,
and skips completed cells without replaying failures. A started attempt without
a result requires inspection; it is never silently run again. Genuine provider
credit/authentication/identity failures remain explicit. Unknown costs do not
block the next request and are not presented as zero spending.

`corrected_custom_gateway.py` uses the same shared Retry-After/deadline recovery
as the baselines. The existing baseline gateway remains final-only. The new
custom gateway requires its own policy and registered cell, checked again
before each physical request. No old reservation, receipt gate or financial
allowance enters this dispatch path.

The native qualifier uses an isolated synthetic model with no real API key and
no network interface. It exercises the actual custom graph, container command,
verifier, 429 recovery, tracing, revocation and cleanup for C0, C1, C2-on-C0 and
C2-on-C1. The repository's synthetic fixture is not a new benchmark task.
Setup retains the baselines' 900-second allowance; task execution and verifier
limits are still read unchanged from the official benchmark configuration.

C2's parent is chosen only after both C0 and C1 finish all 20 tasks. Selection
keeps the original ordering: passes first; complete recorded cost, if available
for both; simpler design; observed runtime. If either cost is incomplete, the
cost tie-break is omitted. Missing verifier output remains separately labelled,
earns no pass in the all-intended denominator, and is not called a verified
failure. Retain the source/result hashes used for the decision.

Before a paid custom attempt:

1. Finish the local regression and native setup checks on the final candidate.
   The old `run_development.py` remains historical; do not use it for this run.
2. Qualify the new deployment on native Docker using the actual custom graph,
   synthetic provider, task verifier, shared retry and cleanup. No model API
   spending is needed for this fixture. Bind sources, dependencies, images,
   official resource enforcement and test evidence before registering cells.
3. Run one registered attempt per task/variant, sequentially on the fixed 20.
   Keep all failures and unknown costs. Select C2's parent from development
   evidence only, and record one-lever changes. Update the selection/freezing
   path for passive billing without inventing complete cost data.
4. Freeze the finalist before its full 89-task evaluation. Do not tune using
   held-out diagnostics or claim a custom win before matched scores exist.

No paid custom result or quality win is claimed by this setup checkpoint.
Native qualification status must be supported by its separate evidence, not
inferred from this document or a test count. The rental remains needed.

## Engineering practices and evidence

The design uses Harbor's external `BaseAgent`/environment interface rather
than modifying its verifier. Deep Agents supplies typed filesystem/command
tools and the LangGraph loop. Private per-attempt state and write-before-send
request records support inspection without replaying side effects. Benchmark
success comes only from the official verifier, not an agent's completion tool.

Planning (C1) and requirement checks (C2) are separate experimental levers.
Automatic summarisation, extra subagents, persistent cross-task memory and new
tools are **not** quietly enabled together. They are possible later dev-only
experiments, not proven improvements. Current context handling uses bounded
tool observations and task-local files; there is no learned or held-out memory.

Official guidance checked on 26 September:

- [Harbor agents](https://www.harborframework.com/docs/agents): custom agent/environment integration.
- [Deep Agents overview](https://docs.langchain.com/oss/python/deepagents/overview): tools, sandbox backends, context and optional planning.
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence): durable state. This one-attempt study deliberately does not resume a crashed scored agent and replay its tools.

These references guide engineering, not claims of superior accuracy. Installed
dependency versions are pinned and included in the qualification fingerprint;
new documentation is not a reason to upgrade them during an experiment.
