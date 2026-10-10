# Twenty-task milestone — current brief, 10 October 2026

The requested **20 custom-harness attempts are complete**. Further paid runs
await the user's direction. The wider project goal remains active.

## Results

| Outcome | Attempts |
|---|---:|
| Pass | 13 |
| Verifier failure | 4 |
| Infrastructure failure | 3 |
| Budget stop | 0 |
| Unstarted | 0 |

There are **18 official verifier scores** and **two unscored attempts**.
One infrastructure failure has an official reward of zero; the other two
have no score. The detailed task table and diagnostics are in [BRIEF.md](BRIEF.md).

All paid attempts used `google/gemini-3.7-flash` through OpenRouter with the
fixed provider route. This experiment is separate from earlier DeepSeek runs
and the 89-task evaluation. No same-model Terminus or OpenHands comparison
has run, so these results do not establish an improvement over either baseline.

## Spending

- Known new API spending: **US$11.229632850**.
- Unresolved request: **one**, retaining **US$1.10**.
- Known spending plus reservation: **US$12.329632850**.
- Conservative headroom under the original US$20 cap: **US$7.670367150**.
- Additional model spending for local logging and offline recovery work: **US$0**.

The unresolved request is not assumed free. Remaining headroom is not an
authorization to start another batch. Available credit must also be checked
before any subsequently authorized paid request.

## Logs and delivery

Local Langfuse runs at [http://127.0.0.1:3300](http://127.0.0.1:3300).
The completed import contains **20 trial traces and 6,219 observations**,
including all 1,215 model requests. Its verified import, usage audit and
deployment details are in [LANGFUSE_20261010.md](LANGFUSE_20261010.md).
An additional readback on 10 October verified all 6,219 observation identities
across all 20 trials, with zero model API calls.

Langfuse stores timing, status, model, tokens, cost and outcome metadata.
Full requests/responses, tool output, trajectories and verifier logs remain
private under `F:/Capstone/.runtime/gemini-dev20-laptop-20260930` and in the
preserved Docker volume. Credentials and raw task exchanges are excluded
from Git. The original paid controller remains stopped.

The opt-in command-handle recovery fix passed **61 offline checks and a
synthetic Docker lifecycle**. Those checks are separately logged and do not
change the original benchmark scores or count as additional paid runs.
See [the recovery brief](../gemini-recovery-offline-20261010/BRIEF.md).

Delivery branch: `codex/gemini-dev20-results-20261005`.
Future baseline preparation is retained privately as unqualified work; it has
not been registered or run against paid inference.

## Next decision

Review this milestone, then choose the next scope: finish the report using
these results, authorize a targeted recovery attempt, or authorize a matched
Terminus comparison. No additional paid task starts before that direction.
