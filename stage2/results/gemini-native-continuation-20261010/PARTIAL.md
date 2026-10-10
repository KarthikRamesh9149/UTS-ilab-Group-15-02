# Gemini native continuation — partial snapshot

Captured 2026-10-10T10:40:28.859001+00:00. **The batch is still running. This is not a final score.**

14 of 40 native attempts are closed: 3 inherited and 11 new attempts.
Closed native outcomes: 10 passes, 3 verifier failures, 0 infrastructure failures, and 1 budget stops.
26 attempts remain, including any active task.

Confirmed spending on completed new attempts: US$8.539976175. Active-task spending is excluded.

| Newly closed attempt | Classification | Official reward | Confirmed cost (US$) |
|---|---|---:|---:|
| terminus-2 / build-pov-ray | pass | 1.0 | 0.122687325 |
| terminus-2 / mailman | pass | 1.0 | 0.613809825 |
| openhands / mailman | pass | 1.0 | 2.215848600 |
| openhands / constraints-scheduling | pass | 1.0 | 0.362850675 |
| terminus-2 / constraints-scheduling | verifier_failure | 0.0 | 0.263562525 |
| terminus-2 / overfull-hbox | pass | 1.0 | 0.300671775 |
| openhands / overfull-hbox | pass | 1.0 | 0.527323950 |
| openhands / reshard-c4-data | pass | 1.0 | 0.753597900 |
| terminus-2 / reshard-c4-data | pass | 1.0 | 0.659057775 |
| terminus-2 / install-windows-3.11 | pass | 1.0 | 1.081624125 |
| openhands / install-windows-3.11 | verifier_failure | 0.0 | 1.638941700 |

## Tasks with official scores from all three harnesses

| Task | Custom | Terminus-2 | OpenHands |
|---|---:|---:|---:|
| mailman | 1.0 | 1.0 | 1.0 |
| constraints-scheduling | 1.0 | 0.0 | 1.0 |
| overfull-hbox | 1.0 | 1.0 | 1.0 |
| reshard-c4-data | 1.0 | 1.0 | 1.0 |
| install-windows-3.11 | 0.0 | 1.0 | 0.0 |

These observed scores do not establish full-subset superiority. Classifications and budget censoring are retained in partial-comparison.json.
Two original custom attempts remain unscored; the inherited OpenHands build-pov-ray budget stop is not replayed.

1008 generation records and 2288 local metadata observations were validated against completed outcomes and billing costs.
Raw exchanges, native tool logs and task artifacts remain private. Local Langfuse is stopped for official task memory capacity; import and readback remain pending until the batch stops.

The same Gemini model/provider/settings, frozen development tasks, official CPU/memory and deadlines continue under the shared US$50 cap and fresh credit checks.
The earlier unknown charge retains its US$1.10 reservation. Requested disk sizes are recorded; Docker uses shared disk without per-container quotas.
Earlier DeepSeek results are separate. Final results and a brief will follow.
