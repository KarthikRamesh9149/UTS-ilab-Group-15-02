# Custom harness: corrected-protocol candidate

26 September 2026. **Offline candidate, not a paid launch or a final freeze.**
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

Before a paid custom attempt:

1. Add a separately registered development execution path. The old
   `run_development.py` still uses reserved billing/100 calls; the corrected
   `scored_trial.py` and `credit_only_gateway.py` currently accept passive
   billing only for `stage=final`. Do not label dev work as final to bypass
   that check. Extend the new deployment with an exact dev20 contract and
   source-bound qualification, preserving the old experiments.
2. Establish the applicable custom spending authority from the saved user
   instructions and record the exact credit policy. A baseline-only policy
   file does not itself authorize a new custom experiment. Do not introduce
   a different allowance into a supposedly fair comparison. No automatic
   payment, top-up or provider-limit increase is authorized.
3. Qualify the new deployment on native Docker using the actual custom graph,
   synthetic provider, task verifier, shared retry and cleanup. No model API
   spending is needed for this fixture. Bind sources, dependencies, images,
   official resource enforcement and test evidence before registering cells.
4. Run one registered attempt per task/variant, sequentially on the fixed 20.
   Keep all failures and unknown costs. Select C2's parent from development
   evidence only, and record one-lever changes. Update the selection/freezing
   path for passive billing without inventing complete cost data.
5. Freeze the finalist before its full 89-task evaluation. Do not tune using
   held-out diagnostics or claim a custom win before matched scores exist.

No paid custom run, server deployment, balance change or experiment outcome is
claimed by this checkpoint. The rental is still needed for unfinished work.
