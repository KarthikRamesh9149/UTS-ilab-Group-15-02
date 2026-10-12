# Gemini native continuation â€” US$50 total cap

Stopped: unresolved_charge. Outcomes include eighteen inherited attempts; 1 new attempt completed.

| Harness | Started | Pass | Verifier failure | Infrastructure failure | Budget stop | Unstarted |
|---|---:|---:|---:|---:|---:|---:|
| terminus-2 | 9 | 7 | 2 | 0 | 0 | 11 |
| openhands | 10 | 6 | 1 | 2 | 1 | 10 |

Total confirmed spending: US$31.571603775; unresolved reserve: US$3.30.
New continuation spending: US$0.08087850.

Logical model remains `google/gemini-3.7-flash`; new physical requests use the dated `google/gemini-3.7-flash-20260813` ID with Google AI Studio. Model and provider are checked in response and billing metadata. Frozen tasks, sampling settings, official resources and deadlines are unchanged. Provider-reported identity is the available evidence; model weights cannot be independently verified. No paid replays or automatic request retries.
Official CPU/memory limits and deadlines are enforced. Requested disk sizes are recorded; Docker uses shared disk without per-container quotas.
All raw exchanges, tool outputs and task artifacts retained privately. Local Langfuse metadata readback verified.
Earlier custom Gemini and DeepSeek results remain separate. Partial data does not establish full-subset superiority.
Native paired tasks: 9; tasks with official scores from all three harnesses: 7.
New unresolved charge stopped further dispatch. No scored attempt was replayed.

## Original custom milestone

Twenty attempts: 13 passes, 4 verifier failures, 3 infrastructure failures. Two attempts have no official score.
Original allowance: US$20. The native allowance was increased after three attempts; this budget difference and censored outcomes limit comparison.
The original results remain in [custom brief](../gemini-dev20-laptop-20260930/BRIEF.md). Its subsequent verified trace import is documented in [Langfuse import](../gemini-dev20-laptop-20260930/LANGFUSE_20261010.md).

## Recorded scores from all three harnesses

| Task | Custom | Terminus-2 | OpenHands | All completed without infrastructure or budget stop |
|---|---:|---:|---:|---|
| mailman | 1.0 | 1.0 | 1.0 | True |
| constraints-scheduling | 1.0 | 0.0 | 1.0 | True |
| overfull-hbox | 1.0 | 1.0 | 1.0 | True |
| reshard-c4-data | 1.0 | 1.0 | 1.0 | True |
| install-windows-3.11 | 0.0 | 1.0 | 0.0 | True |
| openssl-selfsigned-cert | 1.0 | 1.0 | 1.0 | True |
| regex-chess | 1.0 | 1.0 | 0.0 | False |

The comparison JSON retains classifications and per-task costs. Missing scores and unstarted cells are not assigned rewards.

## Trace and billing audit

11 new physical requests; 1 unresolved new charge. All 3,010 predecessor request records are preserved.
117 new metadata observations, including synthetic qualification rounds, were read back by ID. Synthetic checks are separate from benchmark scores.
11 paid generation observations; known costs match the ledger: True.
Full exchanges and task artifacts remain in the private Docker volume and Windows backup; the file inventories match by path and hash.
Provider-reported cache usage: 0 cached input tokens across 10 requests with that field. Missing usage is retained; no dollar-saving estimate is inferred.

## Implementation references

[Deep Agents profiles](https://docs.langchain.com/oss/python/deepagents/profiles), [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence), and [Langfuse OpenTelemetry](https://langfuse.com/integrations/native/opentelemetry).
For this frozen experiment, stopped scored attempts are not resumed or replayed.

## 12 October continuation

The only new benchmark attempt was cell 19, OpenHands on `polyglot-rust-c`: official reward 0, classified as infrastructure failure after `unresolved_charge`. Eleven physical requests incurred US$0.08087850 confirmed spending; the eleventh has no confirmed cost. The task container was removed and model access revoked; controller exit code was 0, with no controller OOM.

The task's cgroup recorded a 2 GiB peak and no OOM kills. Numeric library workers were capped to the task's official CPU allocation before qualification; CPU/RAM limits and deadlines were retained. Remote Gemini inference cannot be accelerated with the laptop GPU.

The final source passed 72 selected offline checks and both native fake-provider launcher fixtures. The first new fixture round failed because the fake provider expected the generic model ID; that failed round is retained and traced separately. The corrected second and final third rounds passed. These are synthetic qualification outcomes, not benchmark passes. Final source commit: `e73a1be95745aef78eae94162e461857332fd381`.

The original 3,010 request objects and all 18 prior attempt records were preserved exactly. Twenty-one native cells remain unstarted. Further dispatch stopped on the new unresolved charge. Metadata-only receipt checks found no generation ID for request 910 and HTTP 404 for requests 3009 and 3020; none was counted as free or replayed. All three US$1.10 reserves remain held under the US$50 cumulative cap.

Local Langfuse is available at <http://127.0.0.1:3300/>. New traces contain 24 paid metadata observations and 93 synthetic observations, all verified by ID. Full model text, command output and task solutions remain private. This result does not establish that Gemini outperforms the repository's DeepSeek V4 experiment.
