# Gemini command-handle recovery — 10 October 2026

**New API spending: US$0. No paid tasks were run.**

## Change

The opt-in `RecoveryGeminiAgent` uses adapter version
`stage2-c0-nc-gemini-0.2.0`. Polling or interrupting an unknown command handle
returns structured feedback explaining that the handle must come from
`start_command` in the same trial. An `execute` call does not create a handle.

This addresses the error that aborted the earlier `polyglot-rust-c` attempt.
Registered commands retain their existing behavior. Actual command transport
failures, cleanup failures and official deadlines still stop execution.

The original `GeminiAgent` still selects the original registry. Model, provider,
sampling settings, prompt, tools and official resource/deadline policy are not
changed by selecting the recovery adapter. The original 20-attempt results
remain unchanged; they have not been replayed or rescored.

## Validation

- **61 offline and regression checks passed** in the pinned controller image.
  The container had no network, provider key or Docker socket.
- A fake graph polled and interrupted an unknown handle, received feedback and
  continued to completion. No command was executed by those invalid handles.
- A separate **real Harbor/Docker synthetic lifecycle passed**, using the
  recovery adapter, fake inference and a 512 MiB fixture container.
- The fixture revoked model access, ran its synthetic verifier, removed its
  task container and recorded no cleanup errors. Its controller was stopped.
- These are qualification results, not new benchmark scores. The fixture's
  synthetic reward is not exported as an official Langfuse reward.

Qualification details and source hashes are in [`qualification.json`](qualification.json).

## Langfuse and evidence

The qualification has separate `recovery-docker-fixture` and
`recovery-offline-checks` traces in the local Langfuse project at
http://127.0.0.1:3300. They are labeled `synthetic_no_benchmark_score` and
`paid_generations=0`. Observation-ID readback is recorded in the qualification
report. The earlier paid batch's 6,219 observations remain separate.

Private logs and the fixture evidence are preserved outside Git:

```text
F:/Capstone/.runtime/langfuse-local-20261010/recovery-offline.log
F:/Capstone/.runtime/langfuse-local-20261010/recovery-docker.log
F:/Capstone/.runtime/gemini-recovery-offline-20261010/
Docker volume: uts-gemini-recovery-20261010
```

## Budget and next diagnostic

A read-only OpenRouter metadata check reported US$36.537936525 available on
10 October. This does not increase the original US$20 experiment spending cap.
Known prior spending remains US$11.229632850 and the unresolved request retains
US$1.10. The original cap has **US$7.670367150 conservative headroom**, subject
to another credit check before any new paid call.

The lowest-cost paid diagnostic to prepare next is **one new
`polyglot-rust-c` attempt** with the recovery adapter, fixed Gemini routing and
official task limits. A proposed additional exposure cap of **US$2** would
include unresolved new charges, retain the existing reservation and stop if
the next full US$1.10 request reservation cannot fit. Actual cost may be much
lower; no cost or pass outcome is promised.

That diagnostic needs a fresh source-bound registration and shared spending
accounting. It must be reported separately from the original dev20 batch and
cannot establish a full harness comparison. The recovery adapter is currently
an opt-in module; the old dev20 paid launcher has not been switched to it.
