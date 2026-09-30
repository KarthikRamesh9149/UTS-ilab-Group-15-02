# Gemini custom-harness development run â€” brief

Stopped: **twenty_attempts_complete**. 20 of 20 attempts started.

**13 passes**, 4 verifier failures, 3 infrastructure failures, 0 budget-stopped attempts; 0 tasks unstarted.

Official verifier scores: **18**; unscored attempts: **2**. Outcome categories describe the recorded failure cause; a tool infrastructure error may still have an official reward.

Known new API spending: **US$11.229633** against US$20. Unresolved charges: 1 request, with US$1.10 retained as a conservative reservation.

This is a development experiment using `google/gemini-3.7-flash` via OpenRouter and Google AI Studio, held fixed throughout. It is separate from the earlier DeepSeek experiments and the 89-task evaluation. No same-model Terminus baseline was run in this milestone. The implementation follows the [Deep Agents profiles](https://docs.langchain.com/oss/python/deepagents/profiles) and [OpenRouter provider selection](https://openrouter.ai/docs/guides/routing/provider-selection) interfaces.

## Attempt results

| # | Task | Result | Reward | Requests | Known US$ | Agent seconds |
|---:|---|---|---:|---:|---:|---:|
| 1 | video-processing | infrastructure_failure | unscored | 113 | 1.352341 | 741.73 |
| 2 | build-pov-ray | infrastructure_failure | unscored | 27 | 0.234952 | â€” |
| 3 | mailman | pass | 1.0 | 176 | 1.591562 | 756.07 |
| 4 | constraints-scheduling | pass | 1.0 | 31 | 0.256288 | 147.29 |
| 5 | overfull-hbox | pass | 1.0 | 52 | 0.379727 | 330.79 |
| 6 | reshard-c4-data | pass | 1.0 | 68 | 0.614004 | 563.23 |
| 7 | install-windows-3.11 | verifier_failure | 0.0 | 114 | 0.950388 | 3600.14 |
| 8 | openssl-selfsigned-cert | pass | 1.0 | 29 | 0.149027 | 93.3 |
| 9 | regex-chess | pass | 1.0 | 125 | 1.805197 | 3497.33 |
| 10 | polyglot-rust-c | infrastructure_failure | 0.0 | 23 | 0.100564 | 94.98 |
| 11 | adaptive-rejection-sampler | pass | 1.0 | 55 | 0.543673 | 294.59 |
| 12 | qemu-alpine-ssh | verifier_failure | 0.0 | 98 | 0.684004 | 900.05 |
| 13 | modernize-scientific-stack | pass | 1.0 | 24 | 0.105945 | 79.52 |
| 14 | distribution-search | pass | 1.0 | 16 | 0.153396 | 81.1 |
| 15 | merge-diff-arc-agi-task | pass | 1.0 | 65 | 0.472910 | 255.28 |
| 16 | sqlite-db-truncate | pass | 1.0 | 26 | 0.178754 | 98.5 |
| 17 | prove-plus-comm | pass | 1.0 | 18 | 0.125773 | 58.9 |
| 18 | db-wal-recovery | verifier_failure | 0.0 | 65 | 0.563396 | 900.12 |
| 19 | qemu-startup | verifier_failure | 0.0 | 65 | 0.804755 | 900.04 |
| 20 | nginx-request-logging | pass | 1.0 | 25 | 0.162976 | 82.58 |

## Diagnostics and qualification

The first attempt (`video-processing`) completed its agent phase but had `AddTestsDirError`: the new logging wrapper did not accept Harborâ€™s `source_dir`/`target_dir` upload keywords. The second attempt (`build-pov-ray`) was gracefully interrupted while fixing that issue. Both remain unscored infrastructure attempts, count toward the 20 attempts, and retain their costs. Neither was replayed.

`polyglot-rust-c` called `poll_command` without any prior `start_command`. The existing job registry raises `KeyError` for an unknown handle, which aborted this agent attempt. Its official verifier ran and returned reward 0; the run taxonomy classifies the attempt as an infrastructure failure due to the unhandled tool error. It is scored, unlike the first two infrastructure attempts. This behavior was retained during the frozen batch.

The repaired wrapper preserves Harborâ€™s keyword interface. Before continuing, qualification passed **80 unit checks plus a real Docker lifecycle** through the logging wrapper, using a fake model and zero paid generations. Synthetic fixture rewards are excluded from benchmark scores. The source-bound continuation records the repair and runs only previously unstarted tasks.

Task 12 (`qemu-alpine-ssh`) reached its 900-second agent deadline; the last API request timed out there without a generation ID or settled receipt. The verifier returned reward 0 and cleanup succeeded. A reviewed continuation retained the full US$1.10 unknown-charge reservation and all prior costs, verified its timing against the agent span, and started only task 13 onward. The unchanged agent and model settings remained frozen. The continuation guard passed **82 unit checks plus the real Docker fixture**, with zero paid generations. The original stop summary and source-bound amendment are retained as separate artifacts.

Agent deadlines reached: install-windows-3.11, qemu-alpine-ssh, db-wal-recovery, qemu-startup. Recorded cleanup errors: 0. Recorded trace errors: 0. Error types, verifier times and per-task resource audits are in `tasks.json`.

## Resources, budget and logs

Tasks ran sequentially on this laptop with the frozen subsetâ€™s official CPU, memory and deadlines. Two CPU workers prefetched later official task images. The RTX 2060 was not used: Gemini inference executes remotely, and the official tasks request no GPU. Dockerâ€™s shared disk does not enforce an individual task storage quota. Task configuration fields are documented in [Harbor tasks](https://www.harborframework.com/docs/tasks).

Before each physical request, the gateway checked available credit and durably reserved US$1.10. Unknown charges retain this reservation; only authoritative cost evidence releases it. No automatic model transport retries, provider fallback, or model switching occurred. A budget stop can leave some of the US$20 unused when the next maximum reservation cannot safely fit.

Provider response metadata: 57,848,867 input tokens, 371,020 output tokens, 49,701,248 cached input tokens. These are cumulative repeated-prefix totals. Observed response models: google/gemini-3.7-flash; providers: Google AI Studio.

Full requests/responses, tool activity, trajectories, verifier logs, controller diagnostics and original registrations are retained privately in `F:/Capstone/.runtime/gemini-dev20-laptop-20260930` and Docker volume `uts-gemini-dev20-20260930`. Credentials are not serialized. The complete private evidence archive is also saved outside Git; 8,841 copied log/evidence files matched their original SHA-256 hashes. The study controller was stopped, and the private volume is preserved. Only curated metadata is committed.

Langfuse status: `local_metadata_retained_credentials_unavailable`. Local metadata spans are preserved; missing credentials mean no cloud export. The exporter uses [Langfuse OpenTelemetry](https://langfuse.com/integrations/native/opentelemetry).

Public JSON files are a delivery projection: account lifetime usage, key lifetime limits and generation identifiers are omitted. Original evidence hashes are in `delivery-projection.json`; registration hashes refer to the preserved private original, not the projected public file.

Branch: `codex/gemini-dev20-laptop-20260930`. Push pending: GitHub authentication is unavailable on this laptop. The branch is committed locally.

Next decision: what would you like to do after reviewing this batch? Await the userâ€™s direction before any further paid run.
