# First custom 0.3 development block

| Harness | Passed | Failed | Tasks |
|---|---:|---:|---:|
| Custom C0 | 15 | 5 | 20 |
| Terminus-2, primary comparator | 14 | 6 | 20 |
| OpenHands, secondary comparator | 10 | 10 | 20 |

These are the same fixed 20 tasks and the same model/provider settings. C0 is
one task ahead of the primary comparator in this development block. That is
not yet evidence of a reliable or full-benchmark improvement. The planned C1
and C2 comparisons, confirmation, freeze and final 89-task run remain.

All 20 attempts have verifier results and remain in the score. Four failures
reached the official agent deadline. One failed after the command-output helper
exited with code 137; that code alone does not establish why the process was
killed. Another task passed its checks despite reaching the agent deadline,
and its pass is retained. No failed task was repeated or dropped.

The audit checked registered cells, exact source and Python runtime bindings,
official deadlines and resources, trace identities, model-access revocation
and container/network/volume cleanup. All 178 original baseline result hashes
and all four stopped custom 0.2 result hashes are unchanged.

There were 682 physical model requests: 677 accepted responses, three
interrupted requests and two error outcomes. One HTTP 429 was recorded. The
responses report **US$0.68143482** in known cost; five request costs are unknown,
so this is not a complete or independently reconciled bill. There was no
project/task spending cap, reserve or artificial model-call ceiling.

The private off-server backup contains 5,201 files. All 20 result files and
151 bound files, including the execution source and Python archive, were
hash-verified. Its SHA-256 is
`364d9a19d93aa52e96a9faf1111940393bfa29fb5458e1e094d10067f74dd03c`.
The archive and raw messages are not published. An earlier interrupted transfer
was retained privately; it was not counted as a verified backup.

This is a separate 0.3 engineering version. The [stopped 0.2 run](../../custom-development-20260926/README.md)
and its four attempts remain disclosed, not replaced with the better 0.3
outcomes. There is no best-of score across versions.

Reporting checks: 26 targeted tests passed. The full local suite ran 1,046
tests: 1,045 passed and one pre-existing test was skipped. No execution source
was changed, so the existing native qualification was not rerun.

Files: [task results](trials.csv), [audit and metrics](summary.json).
