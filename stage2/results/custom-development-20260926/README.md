# Custom development

## C0 stopped for compatibility repairs, 26 September 2026

Four attempts started. All are retained; none will be overwritten or silently
retried. There is no completed 20-task custom score.

| Task | Retained outcome | Recorded issue |
|---|---|---|
| video-processing | Verifier reward 0 | A file tool attached image content to the text-only gateway after 13 accepted requests. |
| build-pov-ray | Setup failed; no verifier result | The task image has no Python. No API call was made. |
| mailman | Verifier reward 0 | RuntimeError during command execution after 24 accepted requests. The exact original cause was not recorded. |
| constraints-scheduling | Interrupted during setup; no verifier result | The external stop watcher signalled after this fourth attempt had already started. No API call was made. |

The watcher did not achieve a clean boundary stop. The fourth result also
lacks a `model_revoked` field. Its containers, networks and volumes were
removed, and a subsequent live check found no owned trial container. That
does not retroactively fill in missing revocation evidence. Original result
bytes remain unchanged.

The 37 accepted requests recorded US$0.01410066 in response-reported costs,
with no unknown costs among these records. This is not independently verified
receipt accounting. No further paid calls were made for the compatibility work.

Both the C0 service and the stop watcher are inactive. **Do not resume this
partial deployment or run C1/C2 from it.** The separately versioned 0.3 candidate
needs fresh source-bound native qualification and transparent registration.
See [compatibility repairs](../custom-compatibility-20260926/README.md).

## Historical launch snapshot

The first fixed-20 custom block started at 05:45:37 UTC. At 05:46:37 UTC, the service was running with the first task underway and real model requests recorded. No completed custom score was available at that snapshot.

[launch.json](launch.json) records the exact 20-cell registration, source bindings and qualification. [Setup checks](../custom-setup-20260926/README.md) passed before the first paid request.

The runner is sequential and keeps one attempt per task and variant, including failures. It has no project/task spending cap, reserve or artificial model-call ceiling. Official task deadlines and resources, actual provider limits, authentication, identity checks and cleanup remain unchanged. It does not buy credit automatically.

## Design comparison

- C0: the existing minimal custom controller with typed container tools and task-local state.
- C1: add planning instructions, leaving other settings unchanged.
- C2: add completion checks to the parent selected from complete C0/C1 development results.

C1 and C2 have not started. Compare each block with the saved baseline results on these same 20 tasks: Terminus-2 14/20, OpenHands 10/20. Keep Terminus-2 as the pre-selected primary comparator. No custom win or final freeze is claimed.

The source for this registered deployment remains frozen. Do not edit it or
replay a started attempt. The historical launch snapshot is not current
evidence of an active job.
