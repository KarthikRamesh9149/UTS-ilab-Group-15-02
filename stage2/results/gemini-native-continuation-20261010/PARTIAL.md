# Gemini native continuation — partial snapshot

Captured 2026-10-10T08:45:36.353246+00:00. **The batch is still running. This is not a final score.**

Six of forty native attempts are closed: three inherited attempts and three new
attempts. Across those six there are four passes, one verifier failure, and one
inherited budget stop. The other 34 attempts include any currently active task.
All three new attempts passed, costing US$2.952345750 in confirmed charges.
This amount covers completed new attempts only; active-task spending is excluded.

| Newly completed attempt | Official reward | Confirmed cost (US$) |
|---|---:|---:|
| Terminus-2 / build-pov-ray | 1 | 0.122687325 |
| Terminus-2 / mailman | 1 | 0.613809825 |
| OpenHands / mailman | 1 | 2.215848600 |

Mailman is the first task with official scores from all three harnesses: custom,
Terminus-2 and OpenHands all passed. Their observed costs were US$1.591562250,
US$0.613809825 and US$2.215848600 respectively. This single task does not establish
full-subset superiority. Two original custom attempts remain unscored; an inherited
OpenHands build-pov-ray attempt stopped for budget and is not replayed.

All 332 generation records and 684 local metadata observations for the three new
closed attempts were validated; generation costs match their billing ledger.
All three revoked model access before verification and removed task containers.
Raw exchanges, native tool logs and task artifacts remain private. Local Langfuse
is stopped during execution to fit official task memory; metadata import and
readback remain pending until the batch stops.

The same Gemini model/provider/settings, frozen development tasks, official CPU,
memory and deadlines continue under a shared US$50 total cap and fresh credit checks.
The earlier unknown charge retains its US$1.10 reservation. Docker uses shared
disk; requested disk sizes are recorded without per-container quotas.
Earlier DeepSeek results are separate. Final results and a brief will follow.
