# Completion-check development block

| Harness | Passed | Failed | Tasks |
|---|---:|---:|---:|
| Custom C0, control | 15 | 5 | 20 |
| Custom C1, planning | 14 | 6 | 20 |
| Custom C2, completion checks on C0 | 14 | 6 | 20 |
| Terminus-2, primary comparator | 14 | 6 | 20 |
| OpenHands, secondary comparator | 10 | 10 | 20 |

All 20 C2 attempts have verifier results. Four failures reached the official
deadline; two failed the task checks without a recorded agent exception.
No attempt was repeated or dropped. Adding completion checks did not improve
the observed score over C0 in this block. One comparison does not establish
that the change caused the difference.

Of 561 recorded model requests, 557 returned accepted responses and four were
interrupted at the task deadline. No HTTP 429 or other transport error was
recorded. Known response-reported cost is **US$0.62341770**; four request costs
are unknown, so a complete total is not claimed. Independent provider receipts
have not been verified. No artificial spending or model-call cap was applied.

The audit verified the exact registration, unchanged source/runtime, official
limits, tracing, model-access revocation and owned-resource cleanup. The 178
original baseline result hashes and four stopped 0.2 result hashes are unchanged.
The private off-server backup has 4,353 files, with all 20 result files and 151
bound files hash-verified. SHA-256:
`098de01a145156f41620a0f65f2050b1d96e2307406f4b4d8448188b19cce635`.
Raw model exchanges and the private archive are not published.

The complete-block selection rule keeps C0 as C3's parent. This is development
evidence, not the final 89-task score or a confirmed full-benchmark win.

Files: [task results](trials.csv), [audit and metrics](summary.json).
