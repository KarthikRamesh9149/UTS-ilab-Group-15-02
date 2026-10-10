# Gemini native continuation — US$50 total cap

Stopped: unresolved_charge. Outcomes include three inherited attempts; 15 new attempts completed.

| Harness | Started | Pass | Verifier failure | Infrastructure failure | Budget stop | Unstarted |
|---|---:|---:|---:|---:|---:|---:|
| terminus-2 | 9 | 7 | 2 | 0 | 0 | 11 |
| openhands | 9 | 6 | 1 | 1 | 1 | 11 |

Total confirmed spending: US$31.490725275; unresolved reserve: US$2.20.
New continuation spending: US$13.682050575.

There are 22 unstarted native attempts (11 per harness). The remaining conservative allowance under the US$50 total cap is US$16.309274725, subject to live available credit. No paid task is running.

The new unresolved charge occurred during OpenHands `regex-chess`: a response arrived but its billing cost could not be confirmed. A subsequent read-only billing metadata lookup returned HTTP 404. The US$1.10 request reserve remains held, alongside the earlier US$1.10 custom-run reserve. An unknown charge is not treated as free; no generation was repeated to obtain a receipt. See [billing diagnostic](billing-diagnostic.json).

Same Gemini model/provider/settings, frozen tasks, official resources and deadlines. No paid replays or automatic request retries.
Official CPU/memory limits and deadlines are enforced. Requested disk sizes are recorded; Docker uses shared disk without per-container quotas.
All raw exchanges, tool outputs and task artifacts retained privately. Local Langfuse metadata readback verified.
Earlier custom Gemini and DeepSeek results remain separate. Partial data does not establish full-subset superiority.
Native paired tasks: 9; tasks with official scores from all three harnesses: 7.
Await user direction before another experiment.

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

1393 new physical requests; 1 unresolved new charge. All 1,617 predecessor request records are preserved.
3380 new metadata observations, including synthetic qualification rounds, were read back by ID. Synthetic checks are separate from benchmark scores.
1393 paid generation observations; known costs match the ledger: True.
Full exchanges and task artifacts remain in the private Docker volume and Windows backup; the file inventories match by path and hash.
The continuation backup contains 10,327 files (855,412,717 bytes). The controller exited with code 0, without an out-of-memory event, and native task containers were removed. Local Langfuse is running at http://127.0.0.1:3300.
Provider-reported cache usage: 80768641 cached input tokens across 1392 requests with that field. Missing usage is retained; no dollar-saving estimate is inferred.

## Implementation references

[Deep Agents profiles](https://docs.langchain.com/oss/python/deepagents/profiles), [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence), and [Langfuse OpenTelemetry](https://langfuse.com/integrations/native/opentelemetry).
For this frozen experiment, stopped scored attempts are not resumed or replayed.
