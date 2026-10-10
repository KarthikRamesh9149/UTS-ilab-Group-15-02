# Same-model baseline comparison proposal

**Awaiting the user's scope decision. This is not a paid-run registration.**

The complete project comparison needs actual Gemini Terminus-2 and OpenHands
scores alongside the completed custom batch. Synthetic fixture success cannot
substitute for those results. The requested first 20 custom attempts are already
complete; another paid run waits for the user's direction.

## Proposed scope

Use the same frozen 20 tasks for each requested native baseline, sequentially,
with the existing fixed Gemini/OpenRouter route and model settings. If both
baselines are selected, there are up to **40 new attempts**. Preserve task order
and alternate which baseline runs first on each task. This prevents either
baseline from always receiving first access to the remaining allowance.

The original custom results are the reference, not reruns. Preserve official
images, CPU, memory and phase deadlines. Revoke inference before uploading
verifier tests, retain full private evidence and export sanitized metadata to
local Langfuse with observation-ID readback.

## Verified preparation

A read-only audit of the original Docker volume verified the frozen archive
and **all 1,037 task files**. The subset and task configurations match the
original registration. **All 20 official images are locally cached and their
image IDs match the original custom run**. Nineteen use `/app`; `prove-plus-comm`
uses `/workspace`. None uses `/`, which caused the earlier synthetic OpenHands
startup delay. No official image or task file was modified by this audit.

Docker reports 12 logical CPUs and 8,239,165,440 bytes of memory. The selected
tasks request up to 4,096 MiB and no GPU. Gemini inference remains remote.
Runtime admission must also account for local Langfuse, controller processes
and other memory usage; these metadata checks do not prove peak runtime fit.

The native integration passed 49 offline checks and both scripted Docker
lifecycles. These are preparation evidence, not paid provider qualification
or benchmark scores. See [the qualification brief](BRIEF.md).

## Budget and reporting

| Original allowance | US$ |
|---|---:|
| Total cap | 20.000000000 |
| Known spending | 11.229632850 |
| Unresolved reservation retained | 1.100000000 |
| Conservative remaining exposure | 7.670367150 |

No new model calls were made during this audit. Available credit and the
frozen endpoint must be checked again before any approved paid run. Reserve
the full US$1.10 before each physical request and stop if it cannot fit.
Additional account credit does not increase the original experiment cap.

The remaining allowance may not fund all proposed attempts. Report every
started task, verifier failure, infrastructure failure, budget stop and
unstarted task. The custom allowance and remaining baseline allowance differ;
report budget censoring explicitly. Compare outcomes only where actual
verifier evidence exists for the relevant harnesses, disclose missingness,
and do not claim full-subset superiority from a partial run.

The read-only audit has a separate local Langfuse trace with both observation
identities verified. [preflight-langfuse.json](preflight-langfuse.json) records
the proposal's SHA-256 and the readback. Raw task files and the original ledger
were read from a read-only mount and remain outside this public proposal.

## Full-goal completion audit

| Requirement | Current evidence | State |
|---|---|---|
| Custom Deep Agents/LangGraph harness | `gemini_laptop_agent.py` selects the custom runner; `custom_runner.py` builds `create_deep_agent`; saved paid trial evidence | Implemented and exercised |
| First frozen 20 attempts on this laptop | Custom `summary.json`: 20 started, 18 scored, 13 passes, `twenty_attempts_complete`; saved resource audits | Complete milestone |
| Fixed Gemini route and bounded API spending | Original registration, response metadata and inherited ledger audit | Exercised; one unresolved charge retained |
| Langfuse logging | Original 6,219 observation identities verified; separate synthetic/preflight readbacks | Implemented and verified |
| Gemini Terminus-2 comparison | Scripted Docker fixture and adapter qualification; zero paid baseline attempts | Incomplete |
| Gemini OpenHands comparison | Scripted Docker fixture and adapter qualification; zero paid baseline attempts | Incomplete |
| Full comparative conclusions | No actual Gemini baseline scores yet | Not established |
| Separate branch with sanitized results | `codex/gemini-dev20-results-20261005`; completed results and preparation commits | Delivered so far |

The full goal is not complete. Its remaining paid benchmark stage depends on
the requested post-milestone scope decision; a synthetic fixture or proposal
cannot satisfy that stage.

## Before execution

The selected scope needs a fresh source-bound registration and launcher
qualification, current model and credit admission, and runtime capacity
checks. Never restart the completed custom study or replay its attempts.
Transport, routing or cleanup failures stop the new study; unresolved charges
remain reserved until authoritative cost evidence settles them.

The [machine-readable proposal](comparison-proposal.json) contains all task
resources, image identities, the inherited ledger hash, fixed model settings,
the proposed 40-cell order and remaining execution gates. It is deliberately
labeled `proposal_awaiting_user_scope_not_registered_or_admitted`.
