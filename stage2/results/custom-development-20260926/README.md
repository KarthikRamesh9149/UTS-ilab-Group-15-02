# Custom development

## C0 started, 26 September 2026

The first fixed-20 custom block started at 05:45:37 UTC. At 05:46:37 UTC, the service was running with the first task underway and real model requests recorded. No completed custom score was available at that snapshot.

[launch.json](launch.json) records the exact 20-cell registration, source bindings and qualification. [Setup checks](../custom-setup-20260926/README.md) passed before the first paid request.

The runner is sequential and keeps one attempt per task and variant, including failures. It has no project/task spending cap, reserve or artificial model-call ceiling. Official task deadlines and resources, actual provider limits, authentication, identity checks and cleanup remain unchanged. It does not buy credit automatically.

## Design comparison

- C0: the existing minimal custom controller with typed container tools and task-local state.
- C1: add planning instructions, leaving other settings unchanged.
- C2: add completion checks to the parent selected from complete C0/C1 development results.

C1 and C2 have not started. Compare each block with the saved baseline results on these same 20 tasks: Terminus-2 14/20, OpenHands 10/20. Keep Terminus-2 as the pre-selected primary comparator. No custom win or final freeze is claimed.

The source for this registered deployment is frozen. Do not edit it during the run or replay a started attempt. The server job continues independently of the local Mac.
