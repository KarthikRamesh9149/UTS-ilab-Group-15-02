# Native request timeout and duplicate dispatch: retained incident

## Verified stopped state

On 20 September 2026 at 01:32 UTC, systemd reported
`uts-stage2-qualification-netcupv6p.service` failed (exit status 1), with exit time
01:29:51 UTC. No Docker containers were running. The service stopped during the
sixth fixed development cell, `dev-terminus-2-05-reshard-c4-data`, after retaining
reward zero and reporting `billing_unresolved`. Model revocation and removal of
the trial containers, networks and volumes were all recorded as successful.

There are six retained trial outcomes: four with verified billing, including one
official pass, and two with unresolved billing. Fourteen tasks in this baseline
block have not run. This is not a completed 20-task score. Three of the four
billing-verified trials are budget-stopped, already exceeding the unchanged
qualification maximum of two; fixing connectivity cannot retroactively qualify
this block. No larger stage, replacement attempt or second unknown-hold exception
has been started.

## Concrete implementation defect

The installed Harbor 0.22.0 `Terminus2._query_llm` has an outer three-attempt
exception retry. Our `NoRetryTerminus` had disabled the inner LLM retry but missed
this outer wrapper. The Unix relay also used a 90-second response wait, while
other client layers used 120 seconds. These waits can expire before the official
agent deadline. Closing the client connection does not cancel a synchronous
upstream request already being processed by the gateway.

The saved task-6 evidence shows:

| Request sequence | Dispatch UTC | End UTC | Duration | Recorded outcome |
|---|---|---|---:|---|
| 5 | 01:23:50.276501 | 01:27:15.961285 | 205.684783 s | Complete response, matched receipt |
| 6 | 01:27:16.722945 | 01:28:23.914082 | 67.191138 s | Error, no saved response or generation ID |

Both request JSON files have the exact same SHA-256:
`db8ee6c57c7c1265956ed41e4409abeb8b008d17b7a1b4029016f026f86eae81`.
The upstream native source used here has SHA-256
`c6b72b8c6289809b2ff3a3009b8f118fa1edb1da205f48d0b56c6938a49cb12f`.
Thus duplicate dispatch and the still-active retry wrapper are verified facts,
not a claim that every historical API failure had this cause.

The agent trace ended approximately 96 ms before request 6's error record, and
the verifier began immediately afterwards. Client timeouts followed by queued
native retries and gateway teardown explain the observed sequence. The exact
signal received by the gateway was not separately logged, so the final
interruption mechanism is a reconstruction, not a directly observed SIGTERM.
The transport's 45-second socket timeout is not a whole-call duration limit;
the 205-second completion is not evidence that the configured socket wait was
ignored.

## Accounting and evidence preservation

New unresolved local request:
`5464bb2d-0767-42ff-86d7-66b11ab737ad`.
It has no generation ID, `charged = NULL`, and a retained USD 0.106496
reservation. This is separate from the original historical unknown request
`03d8ac6c-f2c8-4e3a-9781-be9c8ddadf9f` and its equal reservation.

The five task-6 known response charges total USD 0.00287676. Their generation
receipts were fetched read-only and independently matched without a generation
replay or changing the scored ledger/result bytes. The last known generation is
`gen-1789867430-CnN2r9EJ5IN1pky315wV`, charged USD 0.00168114. The following
unknown request needs provider evidence for approximately
**20 September 2026 01:27:16–01:28:24 UTC**; no aggregate balance difference is
being substituted for that record.

Preserved task-6 result SHA-256:
`45abaf15c1a88ea01dcbbfb019596cb7cf322a208bd2f734e657216b7af01c05`.
Stopped-checkpoint scored-ledger SHA-256:
`9eb1a8b631c55b48c2018317c0835683175484e41a42fa3686dd12b39e988484`.
Private off-host archive SHA-256:
`cef1c63ff28ef1f9df4e62966385c6b99bc92b4ecf54607ac00cf6d82ba4aa8e`.

The 81-request stopped accounting checkpoint retains the known charges and
both unknown reservations, separately labelled. The user's later instruction
stops further spending-PDF/report work until explicitly requested again.
No earlier failed result or missing charge has been erased, reclassified as
zero cost, or retried to obtain a better outcome.

## Offline correction boundary

The candidate removes the outer retry by binding the upstream undecorated
`_query_llm` body, preserving the native prompt, tools and context-recovery
behaviour. Regression tests exercise the actual bound method: one chat dispatch
on timeout or disconnect, with unchanged success behaviour. Restoring the old
wrapper in a private in-memory check reproduces three calls.

The accompanying timeout/early-response-identity correction is implemented
offline. One trusted wait, official agent timeout plus 60 seconds, reaches the
model clients, host bridge, Docker RPC, Unix relay and provider transport.
The official agent/verifier deadlines remain unchanged. Bridge shutdown has a
five-second bound and reports cleanup failure if its worker is still running.
OpenHands' actual pinned parser requires an integer timeout; integral values
are formatted accordingly and fractional values are rejected before launch.
All 89 canonical task configurations were hash-verified to produce integral
waits, without inspecting held-out instructions or solutions for tuning.

The gateway saves allowlisted response identifiers and their committed
reservation association before reading a response body. Matching repeated
identity evidence is idempotent; conflicts cannot overwrite or settle a charge.
Longer transport waits are not extra model-solving time; header-only evidence
is not a verified charge. Missing provider evidence still preserves unknown
liability and stops new spending. The shared wait helper is included in the
48-file runtime fingerprint; existing admission files were not rewritten.

These are changed runtime sources. `admission_netcupv6p.json` remains evidence
for the historical candidate only and cannot admit this new candidate. No new
runtime has been deployed, requalified through paid calls or started against
the remaining tasks. Billing recovery and the failed expansion criteria remain
separate from this engineering correction.

## Executed verification

The corrected implementation passed **563 offline tests on each host**:
515 Stage 2 tests, 34 custom-agent tests, two graph callback tests and 12 legacy
tests. The new spending-report test module was excluded after the user stopped
that work. A separate live-progress panel has its own tests and is not part of
this runtime count. Focused independent reviews covered gateway evidence,
retry behaviour, timeout propagation, bounded shutdown and packaging.

Native tests ran in the private isolated candidate directory
`/opt/uts-capstone/.runtime/offline-candidate-20260920.C0Db5U`, not in production.
A temporary network namespace exposed only loopback for synthetic HTTP fixtures;
no model/provider calls or Docker jobs were launched. All 203 candidate-file
hashes, 48 runtime-source hashes and 1,037 opaque canonical dataset hashes were
verified before and after testing. Production source, protocol, admission,
ledger and historical-hold hashes were unchanged. The candidate uses exactly
the same protocol and official-deadline implementation as production.

This is native-host **offline verification**, not live provider qualification,
deployment or permission to resume the benchmark. Unknown billing and the
failed qualification criteria remain unresolved.
