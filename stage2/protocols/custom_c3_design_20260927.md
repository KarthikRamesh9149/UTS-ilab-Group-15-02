# C3: deadline-aware development candidate

Status: local implementation and admission tests complete; native qualification
and paid registration pending.

On 27 September the user requested a C3 before the final 89 and supplied
walkinglabs/learn-harness-engineering as an optional reference. This extends
the current C0/C1/C2 development plan. It does not change the running C2,
replace earlier outcomes, or establish that a new design is better.

## What the evidence supports

C0 passed 15/20 and C1 passed 14/20 on the same fixed development tasks.
Four of C0's five failures reached the official deadline; the other recorded
a capture failure. This suggests testing time awareness, not assuming that
every timeout was preventable. C2 has now completed at 14/20. Its parent and
source stayed unchanged. No held-out answers or timeout-diagnostic task details informed this
design.

The initial 0.4.0 prototype added only a current time reminder before each
model request. It uses the existing gateway lifecycle clock, not a new timer.
It does not add model calls or change the model's reasoning settings.

The user subsequently authorised removing the three audited artificial
cutoffs: the 60-second command default, background handle quotas and the
two-repair stop. The revised 0.4.1 prototype combines deadline-governed
execution with that reminder. This is a broader execution-policy revision,
not a time-reminder-only ablation. Any score difference cannot be attributed
to the reminder alone. Earlier C0/C1/C2 outcomes and execution sources remain
unchanged.

The unchanged parent will be selected from all complete, audited C0/C1/C2
blocks using the existing ranking. No parent is selected from C2's partial
score. C3 retains that parent's planning and completion-check requirements,
but explicitly revises its command timeouts, job quotas and completion-repair
policy. Its identity is C3, version 0.4.1, with the complete parent lineage
recorded. Calling a valid completion or abandoning remains an agent choice;
neither forces the attempt to consume its entire allowance.

## Why this change, rather than a larger rewrite

| Candidate idea | Decision for this prototype |
| --- | --- |
| Remaining-time context | Keep the initial advisory reminder, without an extra timer or model call. |
| Artificial command, job and repair cutoffs | Remove in 0.4.1 as explicitly requested, using the same official deadline. |
| Checking the actual outputs before completion | Already the C2 experiment. Preserve its outcome and selected-parent rule. |
| Automatic compaction or loop intervention | Defer pending evidence of context exhaustion or unproductive repetition on development tasks. |
| More agents, multiple models or extra attempts | Do not add. They complicate attribution; changing the model would violate this study. |
| Structured tracing, clean termination and immutable evidence | Preserve existing mechanisms and qualify the new integration. They are not substitutes for accuracy. |

Unrelated features are not added to this revision. The three requested
execution changes are documented together, not disguised as a single prompt
change. Adding every technique at once would make a score change hard to explain.
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

Opt-in extension points in the shared runner/adapter allow the new middleware,
execution controls and accurate C3 metadata. With their defaults, the existing
C0/C1/C2 behaviour is unchanged. These local changes must not be copied into
the frozen native 0.3 deployment. Its existing qualification cannot qualify
the new code.

`custom_deadline_execution.py` reads the same authoritative deadline for both
ordinary and background commands. Without an explicit timeout, a command may
use all time still available. The agent may choose a shorter timeout, poll a
background handle or interrupt an unwanted job. The library's separate
one-hour execute ceiling is replaced by the official allowance; the backend
clips each command to time actually remaining. Clock construction and graph
construction do not restart the allowance.

Background handles have no active or lifetime count quota. All processes
still share the task's assigned CPU and memory. Incomplete completion reports
may be repaired while official time remains, without a repair-count stop.
The normal model/tool loop, observed-check requirements and no-replay rule
remain. Cancellation propagates, container-only signalling is retained, and
cleanup or transport failures are not labelled successful execution.

Timing evidence contains request numbers, remaining seconds and phase labels,
not task text or credentials. Detailed request and task observations remain
private. Reporting completion is never treated as passing the benchmark.

## Limits audit: not literally unrestricted

The user asked specifically whether restrictions could hamper progress. The
answer is not an unconditional "none". The live C2 policy has no project/task
spending cap, reserve, model-call cap or physical-request-count cap. It retains
the official overall task deadlines and resources. The C3 prototype also uses
the uncapped model-call mode; no paid C3 policy has been registered yet.

The contract distinguishes the frozen C2 from the new offline C3:

| Rule in frozen C2 | C3 0.4.1 behaviour |
| --- | --- |
| Execute and start default to 60 seconds, with explicit timeouts up to 3,600 seconds | Default is remaining official task time; an agent-chosen shorter timeout is optional. No independent one-hour ceiling. |
| Four active background handles, 64 total handles | No handle-count quota; actual task CPU and memory still apply. |
| Two completion-repair opportunities, then termination on the third incomplete report | No repair-count stop; corrections continue until valid completion, abandonment, an actual error or the official deadline. |
| Bounded tool output and file-transfer helpers | Retained: captured output 64,000 bytes before decoding, structured-read envelope 4 MiB, upload/download helpers 1 MiB per file. These do not cap files generated inside the container. Large content can be processed in the container or retrieved in parts. |
| Request and model-context bounds | Retained: bounded gateway body and the exact baseline setting of 384,000 maximum output tokens. Actual provider limits still apply. |

Finite convenience-tool read/search windows and helper timeouts also remain;
they are not overall trial limits. The execution tool can perform longer
searches or process larger files inside the task. This is not a claim of
literally unlimited resources or that retained bounds cannot affect behaviour.
No specific prior failure is attributed to a removed rule without evidence.
Container isolation, authentication, shared retry correctness, cleanup and
memory-safe output handling remain necessary. No setup or billing gate may
silently reintroduce the removed attempt limits during C3 admission.

## Requirements before any C3 paid attempt

1. Complete and audit C2. Bind the parent selected from all three full blocks,
   their source/qualification hashes and all 60 retained result hashes.
2. Bind and test the amended 0.4.1 contract above. Register the exact combined
   change and its comparison before C3 outcomes are observed. Do not select
   easier tasks or claim a reminder-only causal comparison.
3. Implement a separate C3 policy, admission/registration and exporter with
   fresh attempt IDs, all ancestor locks, no overlap, no replay, passive cost
   accounting and the original fixed 20-task order. Do not relabel C3 as C0 or
   development as final to enter an old gateway.
4. Qualify the final source on native Harbor/Docker with a fake, isolated model:
   tool/media transport, Python-less setup, long reads, background processes,
   commands exceeding 60 seconds, more than 64 handles, more than two
   completion repairs, clock reminders, shared 429 recovery, cancellation, cooperative stop,
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

## Initial 0.4.0 verification, 27 September

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

## Amended 0.4.1 verification, 27 September

- All 87 affected tests passed after fixing two test fixtures that reused the
  same synthetic message identity. The complete local suite ran 1,158 tests:
  1,157 passed and one pre-existing skip. The separate 34 legacy custom tests
  passed. No paid API calls were made by these checks.
- The 26 new tests include a real, predetermined local command lasting more
  than 60 seconds, 80 simultaneous synthetic background handles and an 81st
  retained handle, eight invalid completions followed by a valid ninth, and
  150 control-level repair events without a count-based stop. The real graph
  accepts an explicit command timeout over one hour using a synthetic clock.
- An indefinitely incomplete synthetic model ends at the actual one-second
  fixture deadline, not after two repairs. Tests also cover already-expired
  clocks, cancellation, container-only interruption, error propagation,
  optional shorter command timeouts, no replay and unchanged legacy controls.
- These are local process and synthetic graph/adapter checks, not native C3
  Harbor/gateway/verifier qualification. No C3 deployment, paid registration,
  benchmark execution or accuracy gain is established by them.

## Admission implementation, 27 September

C2's complete block was audited and backed up off-server. The unchanged
complete-block ranking selects C0 (15/20) over C1 and C2 (14/20 each) before
any C3 results. The new `deadline_custom_parent.py` rechecks all 60 predecessor
results, their qualification, source, registrations, revocation and cleanup
using the predecessor's own frozen interpreter and code. It copies metadata,
not task answers. Parent evidence is immutable once bound.

The separate C3 runner uses fresh `customdev3-` identities, the exact fixed20,
all ancestor no-overlap locks, passive accounting and the unchanged model
protocol. It refuses started-attempt replay, changed sources or lineage,
unqualified images and unresolved actual provider/cleanup failures. Ordinary
unknown billing is retained without becoming a spending stop.

The native qualifier is implemented for the actual selected-parent graph,
gateway, Docker environment and verifier, using a fake key and network-isolated
model service. It must pass tools, setup cancellation and cooperative-stop
cases, including a command over 60 seconds, 73 new background jobs and seven
completion repairs. Merely implementing these fixtures does not count as a
native pass. The existing 20-image helper evidence is reused only for unchanged
components and exact source/runtime hashes.

Four-variant selection validates every row and chooses a whole candidate;
it never combines each task's best attempt. Pure freeze/schedule documents
bind all 80 outcomes and cannot grant paid admission. Authentic final-freeze
capture and the source-bound confirmation/final runner still require separate
implementation and qualification after development.

Local admission/reporting/selection checks: 135 passed. Full local discovery:
1,209 tests run, 1,208 passed and one pre-existing skip. These tests used no
paid provider or scored benchmark execution. No C3 native qualification or
benchmark score is established at this checkpoint.
