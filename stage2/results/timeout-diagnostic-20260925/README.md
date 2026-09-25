# What happened when we repeated the rate-limited timeout failures?

**10 of 30 fresh attempts passed; 20 failed.** The diagnostic finished on
25 September 2026 at 17:41 UTC. Each selected task-and-harness pair ran once.

We selected every original failed attempt that both timed out and recorded an
HTTP 429 rate-limit error: 11 Terminus-2 attempts and 19 OpenHands attempts,
covering 25 different tasks. This is a selected-failure check, not another
full benchmark score.

| Harness | Repeated attempts | Passed | Failed | Passes with every model response accepted |
| --- | ---: | ---: | ---: | ---: |
| Terminus-2 | 11 | 3 | 8 | 3 |
| OpenHands | 19 | 7 | 12 | 5 |
| Total | 30 | 10 | 20 | 8 |

## What the API records show

No repeat recorded an HTTP 429. The detailed breakdown is:

| API observation | Passed | Failed |
| --- | ---: | ---: |
| Every response accepted; no recorded API errors or retries | 8 | 6 |
| Last request interrupted at the task deadline | 2 | 13 |
| Other recorded transport error | 0 | 1 |

The 15 interrupted final requests ended within five seconds of the official
deadline. They are not proof of a separate provider failure. The one transport
error was also recorded at the deadline, about 0.08 seconds after it; its
effect on the outcome is not established.

Of the 20 failures, 18 reached the official time limit and two failed the task
checks without a recorded agent exception. Three **passes** also had an agent
timeout: the files already produced still passed the verifier. We kept those
verifier results rather than treating every timeout as a failure.

## What we can conclude

Eight previously failing attempts passed with complete, accepted API responses.
Two more passed despite a final interrupted request. However, **we cannot say
exactly how many original failures were caused by API delays**: a fresh model
attempt can take different actions, and successful API calls still take time.
Accepted calls averaged 21.9 seconds; the longest took about 9 minutes 40 seconds.
This was not a zero-delay experiment.

The original results remain **Terminus-2 52/89** and **OpenHands 44/89**. None of
these repeat passes has been added to those scores. This diagnostic must not be
used to tune the custom harness on held-out tasks.

## Conditions and evidence

Same DeepSeek V4 Flash 0731 model, DeepInfra FP8 endpoint without fallback,
native harnesses, official task deadlines and CPU/memory limits. Sequential
execution; no project dollar cap or reserve. All 30 results were checked,
model access revoked, and owned containers, networks and volumes removed.
The original 178 result hashes and frozen execution sources are unchanged.

There were 1,296 model requests and 1,280 accepted responses. Recorded response
costs total **US$1.27234008**, with costs unknown for 16 requests. This is a known
subtotal, not a fully reconciled charge or current account balance.

- [All 30 attempts, including time limits and API observations](trials.csv)
- [Audited summary, source hashes and private-backup verification](summary.json)
- [Original frozen cohort](cohort.csv) and [launch evidence](launch.json)
- [Diagnostic protocol](../../protocols/timeout_diagnostic_20260925.md)
- [Unchanged full baseline results](../baseline-corrected-20260923/README.md)

Raw evidence was backed up privately off-server; no raw transcripts, credentials,
task solutions or private archive are published here. Backup verification checks
every diagnostic result and bound source file; a full runtime restore was not
performed. The reporting change passed 21 targeted tests and the 895-test local
suite (894 passed, one skipped). No new paid calls were made to export this report.

Custom-harness development on the fixed 20 tasks and its frozen 89-task final
evaluation are still unfinished. This diagnostic is not whole-project completion.
