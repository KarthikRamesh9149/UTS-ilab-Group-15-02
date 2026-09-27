# Planning-only custom development block

| Harness | Passed | Failed | Tasks |
|---|---:|---:|---:|
| Custom C0, control | 15 | 5 | 20 |
| Custom C1, planning instructions added | 14 | 6 | 20 |
| Terminus-2, primary comparator | 14 | 6 | 20 |
| OpenHands, secondary comparator | 10 | 10 | 20 |

C1 ran from 00:56 to 04:51 UTC on 27 September. It used the same fixed 20
tasks, model, provider and official limits. Adding planning instructions did
not improve the observed score in this block. This single comparison does not
prove that planning caused the difference. The registered rule selects C0 as
the parent for C2, which tests completion checks as its only added design lever.

All 20 attempts have verifier results. Of the six failures, two reached the
official agent deadline, two failed the task checks without a recorded agent
exception, and two ended after the command-output helper exited with code 143.
That code alone does not establish why the helper was terminated. One other
task passed its checks despite reaching the deadline; its pass is retained.
No failed or interrupted task was repeated or dropped.

All 607 recorded model requests returned accepted responses. No HTTP 429 or
other transport error was recorded. Response-reported cost totals
**US$0.40601118**, with no unknown request costs in this block. This has not
been independently reconciled against provider receipts. C0 still has five
unknown request costs, so its total is not treated as a complete bill or used
for a cost tie-break. No artificial spending or model-call cap was applied.

The audit passed for exact registration, source and runtime bindings, official
limits, trace identities, model-access revocation and owned-resource cleanup.
All 178 original baseline result hashes and all four stopped 0.2 result hashes
remain unchanged. The private off-server backup contains 4,680 files, with all
20 result files and 151 bound files hash-verified. Its SHA-256 is
`f6b34a611b0bfb39250305f025ee3075a255e22974e0f2c315d445104dc0d529`.
The archive and raw model exchanges are not published.

All 26 reporting tests passed. No execution source changed, so the existing
source-bound native qualification was checked and reused, not rerun.

These remain development results. Confirmation and the frozen custom 89-task
evaluation are unfinished; no full-benchmark win is established.

Files: [task results](trials.csv), [audit and metrics](summary.json).
