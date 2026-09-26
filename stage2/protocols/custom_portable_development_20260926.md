# Custom 0.3 development protocol

This is a new engineering version, not a replacement score for the stopped
0.2 run. All four old attempts, their source and their private backup remain
unchanged. They must be disclosed alongside the new run. No best-of result is
chosen between versions.

## What changes

The 0.3 adapter adds a hash-pinned Python fallback for images without Python,
text-only handling of file attachments, reliable command output capture and
complete cancellation metadata. A cooperative stop finishes the active attempt
and prevents the next one from starting. It persists across process restarts.

The runtime archive, source files, installed package versions, model settings,
task split and native qualification are bound into registration. The old 0.2
policy, qualification and trial IDs cannot admit a 0.3 attempt.

The new deployment is `/opt/uts-capstone-custom-portable-20260926`.
Its trial IDs start with `customdev2-`. Development blocks contain exactly the
same 20 tasks in the same order. The stopped deployment is never resumed.

## What stays fixed

- Model: `deepseek/deepseek-v4-flash-0731`, routed only to `deepinfra/fp8`.
  No fallback; temperature 1, top-p 1, high reasoning, output maximum 384,000.
- No project/task spending cap, reserve, price filter or model-call ceiling.
  Existing credit, authentication and model-identity requirements still apply.
  There are no automatic top-ups, purchases or changes to account/key limits.
- Official task and verifier deadlines and resources; sequential execution;
  the same shared Retry-After handling as the corrected baselines.
- One retained attempt per task and version. A failed, interrupted or started
  attempt is never silently repeated. Unknown costs stay unknown.
- C0 is the control. C1 adds planning instructions only. C2 adds completion
  checks to the parent selected from complete C0/C1 development results.

Terminus-2 remains the primary comparator (14/20). OpenHands remains the
secondary comparator (10/20). These are the existing matched development
results, not new runs or the full 89-task scores.

## Checks before paid execution

The unchanged container helpers reuse the completed 20-image capability
checks, with exact source hashes and archive binding. The new qualification
also requires six actual native Harbor rehearsals: all four agent variants,
cancellation during setup, and a stop signal during an active attempt.

The scripted model runs in a container with no network and a fake credential.
It tests image-file tool messages, a 16,000-line file read, editing, a timed-out
command, a background service, transient API recovery, tracing, revocation and
cleanup. The verifier checks the fixture's files and live background process.
These are infrastructure tests, not Terminal-Bench scores or evidence that the
custom harness is more accurate.

Only a passing qualification for the current source can create a paid block.
The runner also holds the older studies' locks, checks for active task
containers and rejects partial or duplicate attempts.

## Selection and final scoring

Keep every development result and record each design change. Compare on the
same 20 tasks. For C2's parent, rank by passes, then fully observed cost when
both blocks have it, then simpler design and observed runtime. Missing
verifier output earns no pass but remains separate from a verified failure.

Development confirmation, finalist selection and the passive-accounting
freeze path still need completion before custom final scoring. Do not use the
older capped final runner. Freeze the selected harness before the full 89-task
run; do not tune it from held-out or timeout-diagnostic answers. A setup test
count is not an accuracy win, and no win is guaranteed.
