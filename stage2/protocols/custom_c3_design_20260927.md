# C3: deadline-aware development candidate

Status: offline prototype, not a qualified or registered paid run.

On 27 September the user requested a C3 before the final 89 and supplied
walkinglabs/learn-harness-engineering as an optional reference. This extends
the current C0/C1/C2 development plan. It does not change the running C2,
replace earlier outcomes, or establish that a new design is better.

## What the evidence supports

C0 passed 15/20 and C1 passed 14/20 on the same fixed development tasks.
Four of C0's five failures reached the official deadline; the other recorded
a capture failure. This suggests testing time awareness, not assuming that
every timeout was preventable. C2 is still running. Its parent and source stay
unchanged. No held-out answers or timeout-diagnostic task details informed this
design.

The present agent has a hard outer deadline but no explicit remaining-time
message. C3's proposed single lever is a short, current time reminder before
each model request. It uses the existing gateway lifecycle clock, not a new
timer. It does not add model calls or change the model's reasoning settings.

The unchanged parent will be selected from all complete, audited C0/C1/C2
blocks using the existing ranking. No parent is selected from C2's partial
score. C3 retains that parent's prompt, tools and completion behaviour; its
identity is C3, version 0.4, with the complete parent lineage recorded.

## Why this change, rather than a larger rewrite

| Candidate idea | Decision for this prototype |
| --- | --- |
| Remaining-time context | Implement as one testable change. The loop currently lacks it. |
| Checking the actual outputs before completion | Already the C2 experiment. Preserve its outcome and selected-parent rule. |
| Automatic compaction or loop intervention | Defer pending evidence of context exhaustion or unproductive repetition on development tasks. |
| More agents, multiple models or extra attempts | Do not add. They complicate attribution; changing the model would violate this study. |
| Structured tracing, clean termination and immutable evidence | Preserve existing mechanisms and qualify the new integration. They are not substitutes for accuracy. |

Adding every technique at once would make a score change hard to explain.
There is no evidence supporting a "best on earth" or guaranteed improvement
claim. Published gains with other models and benchmarks do not predict ours.

## Implemented behaviour

`custom_deadline_guidance.py` adds one transient system note. The original
system content, conversation, tool-call IDs and model settings are preserved.
The note is not appended to persistent conversation history. Remaining seconds
are rounded down and explicitly described as a snapshot before a request;
waiting for the model and running tools both consume the official allowance.

The initial policy has three advisory phases: normal work above 20% remaining,
focus on completion and checks at 20%, and avoid a broad new approach at 5%.
These are not early cutoffs or time reservations. Expiry is still enforced by
the original orchestrator and gateway. A reminder invokes its handler once,
does not retry, and propagates cancellation and transport failures.

`deadline_custom_agent.py` reads the authoritative lifecycle after setup and
retains the prepared portable environment, text-only transport, pinned Python,
shared provider retry policy and exact baseline model configuration. The new
factory identifies itself as C3 and is rejected by the old 0.3 registration.

Two small extension points in the shared runner/adapter allow the new
middleware and accurate C3 metadata. With their defaults, the existing C0/C1/C2
behaviour is unchanged. These local changes must not be copied into the frozen
native 0.3 deployment. Its existing qualification cannot qualify the new code.

Timing evidence contains request numbers, remaining seconds and phase labels,
not task text or credentials. Detailed request and task observations remain
private. Reporting completion is never treated as passing the benchmark.

## Limits audit: not literally unrestricted

The user asked specifically whether restrictions could hamper progress. The
answer is not an unconditional "none". The live C2 policy has no project/task
spending cap, reserve, model-call cap or physical-request-count cap. It retains
the official overall task deadlines and resources. The C3 prototype also uses
the uncapped model-call mode; no paid C3 policy has been registered yet.

The inherited implementation still has these non-benchmark rules:

| Rule | Actual effect |
| --- | --- |
| Ordinary execute defaults to 60 seconds | A foreground command can be terminated before the overall task deadline. The separate start/poll tool accepts up to 3,600 seconds. |
| Four active background handles, 64 total handles | Bounds the start/poll tool, not all commands or processes in the task container. |
| Two repair opportunities after an incomplete completion attempt | A third incomplete completion ends the agent attempt even if time remains. This is not a general model-call limit. |
| Bounded tool output and file-transfer helpers | Normal captured output is 64,000 bytes before decoding; a separate structured-read envelope allows 4 MiB. Upload/download helpers allow 1 MiB per file. These are not limits on files generated inside the container. |
| Request and model-context bounds | The gateway request body is bounded and the exact baseline generation setting remains 384,000 maximum output tokens. Actual provider limits still apply. |

These rules must not be hidden behind a claim that only benchmark constraints
exist. They can affect behaviour; no claim is made that they caused a specific
failure without evidence. Removing arbitrary early-stop or command-lifecycle
limits is a different design change from merely showing the clock. Before C3
paid registration, review this audit and settle an explicit, tested contract.
If its tools or stop policy change, revise and version the experiment rather
than describe several changes as a time-reminder-only ablation. Do not alter C2
mid-run. Keep container isolation, provider authentication, retry correctness,
cleanup and memory-safe output handling.

## Requirements before any C3 paid attempt

1. Complete and audit C2. Bind the parent selected from all three full blocks,
   their source/qualification hashes and all 60 retained result hashes.
2. Resolve and test the limits contract above. Register the exact change and
   its comparison before C3 outcomes are observed. Do not select easier tasks.
3. Implement a separate C3 policy, admission/registration and exporter with
   fresh attempt IDs, all ancestor locks, no overlap, no replay, passive cost
   accounting and the original fixed 20-task order. Do not relabel C3 as C0 or
   development as final to enter an old gateway.
4. Qualify the final source on native Harbor/Docker with a fake, isolated model:
   tool/media transport, Python-less setup, long reads, background processes,
   clock reminders, shared 429 recovery, cancellation, cooperative stop,
   tracing, revocation and cleanup. Reuse only unaffected, still-bound image
   evidence. Local graph tests do not constitute this qualification.
5. Extend candidate selection, confirmation, ablation and freeze explicitly to
   admit C3. The existing three-block offline selection and freeze modules do
   not do this. Select a whole variant, never each task's best attempt. Retain
   the preselected Terminus primary comparator and OpenHands secondary.
6. Only then run one C3 attempt on each fixed development task, retaining every
   failure or missing result. Compare with the parent and both baselines.
   Freeze the chosen candidate before confirmation and the final 89. Do not
   silently promote C3 merely because it is newer.

No new financial or API-call ceiling, automatic top-up, purchase, or account
limit increase is authorised by this design. Unknown costs remain unknown.
The 30 September target may need revision for C3's extra engineering and 20
development attempts; quality checks and fair task limits do not get shortened
to preserve that date. No additional paid calls were launched for this work.

## References reviewed

- [Walkinglabs verification lesson](https://github.com/walkinglabs/learn-harness-engineering/blob/main/docs/en/lectures/lecture-09-why-agents-declare-victory-too-early/index.md)
  and [observability lesson](https://github.com/walkinglabs/learn-harness-engineering/blob/main/docs/en/lectures/lecture-11-why-observability-belongs-inside-the-harness/index.md):
  useful checklists for distinguishing runtime evidence from an agent's own
  claim. No course scripts were run or quantitative improvement claims adopted.
- [LangChain harness engineering](https://www.langchain.com/blog/improving-deep-agents-with-harness-engineering):
  trace-guided changes and time-awareness middleware informed this hypothesis.
- [OpenAI's agent loop](https://openai.com/index/unrolling-the-codex-agent-loop/)
  and [Anthropic's context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents):
  support keeping the model/tool loop observable and its context selective.
  They do not demonstrate an improvement for this model or this candidate.

Review scope: selected relevant material, not every page of each repository or
every possible harness technique. The benchmark's hidden verifier stays
separate from the agent's own checks.

## Offline verification, 27 September

- 28 new tests cover the middleware and adapter, including every possible
  parent, changing clocks, preserved messages/settings, 104 model calls,
  completion repair, cancellation, cleanup lifecycle and replay rejection.
- All 58 affected tests passed. The complete local Stage 2 suite ran 1,132
  tests: 1,131 passed and one pre-existing skip. The separate 34 legacy custom
  tests also passed. Two initial fixture issues (a missing test event loop and
  an incorrect JSON-format assertion) were corrected before the final checks.
- These are local synthetic tests, including the real graph. Python runtime
  preparation and task execution in the new adapter tests are mocked. They
  are not a native C3 qualification, paid-provider test or benchmark score.
- A read-only native check at 11:46:17 UTC found C2 running with 12 completed
  attempts and eight passes. All 127 bound execution files were unchanged.
  Its private policy and retained result metadata confirmed no spending,
  reserve, logical-call or physical-call ceiling. This is a timestamped
  snapshot, not a live counter or a completed C2 score.
