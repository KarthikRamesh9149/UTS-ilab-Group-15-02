# Gemini C0-NC development experiment, 30 September 2026

This is a new development experiment, separate from every earlier DeepSeek run.
The user authorised twenty custom-harness attempts and at most US$20 of new API
spending. Finish only this frozen twenty-task batch (at most twenty attempts),
or stop earlier for the budget, available credit, provider or cleanup failure. Deliver the results,
logs and end-of-run brief, then ask the user what to do next and await direction.
There is no baseline replay, final89 evaluation, fine tuning, or model switching.

## Frozen configuration

- Branch: `codex/gemini-dev20-laptop-20260930`.
- Model: `google/gemini-3.7-flash` through OpenRouter; expected dated snapshot
  `google/gemini-3.7-flash-20260813` and Google AI Studio provider.
- Provider restricted in every physical request; no model/provider fallback.
- Temperature/top-p 1, reasoning high, text-only transport, maximum output 65,536
  tokens. This is Gemini's output limit, not the earlier DeepSeek limit.
- Existing C0-NC prompt, completion control, filesystem and encoded execution
  backend; Deep Agents 0.7.14 on LangGraph; no delegation, persistent memory,
  automatic summarisation, or model-call quota. Official agent deadline remains.
- Existing `input_manifest.json` development_ids in their recorded order.
- Dataset revision `7131e4375048a0e408a8fb404b5f499d726b695b`, verified against all
  1,037 file hashes in `dataset_provenance.json`. No task answers enter the agent.
- Sequential execution on Docker Desktop Linux, original task CPU/memory,
  build/agent/verifier deadlines, and task networking. Docker does not enforce
  an individual storage quota: official requested storage and this limitation
  are recorded. Setup allowance is 180 seconds, outside the agent deadline.
- A fresh portable CPython 3.12.13 bundle is prepared and hash-qualified for this
  experiment. It is not claimed to match the inaccessible historic private
  runtime archive. Existing task Python takes precedence over the fallback.

## Budget

The controller rechecks key allowance and account credit before study start and
each physical request. The study ceiling is the lower of US$20 and available
credit at start. It never modifies the account, key limit, or purchases credit.

Each request durably reserves US$1.10 before transmission. This exceeds a full
1,048,576-token input plus 65,536-token output at the frozen maximum prices,
including a margin. Native billable tools and explicit caching are disabled.
Only settled response costs or generation receipts release a reservation.
Unknown, interrupted, and failed charges retain their entire reservation.
No automatic transport retries occur. A provider/routing/credit-check failure
stops further dispatch and is reported; unfinished trials are not replayed.

The local ceiling cannot control simultaneous spending by other clients sharing
this key. Account usage delta is reported separately from this study's charges.
Budget stops include the current attempt and list every unstarted task.

## Isolation and observability

The Linux controller uses a native Docker volume mounted at its daemon path so
Harbor's child bind mounts resolve correctly. Only the controller has the Docker
socket and read-only key file. Task containers have their log mounts, no provider
key or controller socket, and no privileged execution. Model authorisation is
revoked before the official verifier is uploaded; teardown follows verification.

Retain full model requests/responses/receipts, graph trajectory, tool input/output,
container command output, verifier logs, and controller output inside the private
Docker volume under `.runtime/gemini-dev20-laptop-20260930`. Authorisation headers
and keys are never serialized. Private logs may contain task solutions and are
excluded from Git.

Metadata-only phase, graph, tool, and generation spans are saved separately.
`local_langfuse.py --track gemini-laptop` exports these through the existing
OpenTelemetry transport when project credentials are available. Missing Langfuse
credentials do not block evaluation. An ingestion acknowledgement does not prove
dashboard visibility. Never send raw exchanges or task solutions to Langfuse.

## Qualification and delivery

Before any paid generation, run budget/routing fixtures, affected historic unit
checks, and a real Harbor Docker lifecycle with a scripted Gemini-labelled model.
Bind qualification to source hashes. Synthetic reward is never a benchmark score.

The orchestrator creates immutable fresh attempt directories; a lock prevents
parallel study processes. Progress summaries are atomically updated. Sanitized
results distinguish passes, verifier failures, infrastructure failures, budget
stops and unstarted tasks, with known spending and unresolved reservations.
Commit and push only implementation, registration, qualification, metrics and an
end-of-run brief. Do not publish credentials, PDFs, private archives, raw exchanges
or task solutions. Do not merge this branch into main.

## Laptop commands

From PowerShell in the repository, preparation and qualification only:

```powershell
./stage2/Run-GeminiLaptop.ps1
```

For a fresh authorised study, add `-RunPaid`. Running the paid entrypoint again
after registration is rejected; recovery needs a separate reviewed protocol.
Private evidence stays in Docker volume `uts-gemini-dev20-20260930` even after
the controller is stopped. Do not remove that volume when cleaning task containers.

## Logging repair amendment during development

The first paid attempt finished its agent phase but encountered `AddTestsDirError`:
the new logging wrapper did not preserve Harbor's keyword names for `upload_dir`.
It received no verifier score. The controller was gracefully interrupted during
the second attempt to prevent further affected attempts; both task containers were
removed and their spending retained. Neither attempt may be replayed or relabelled
as a scored failure/pass.

The wrapper now preserves `source_dir`/`target_dir` and `source_path`/`target_path`.
Qualification must exercise the actual logging wrapper in the real Docker fixture.
A single explicit `--continue-unstarted` entrypoint may retain these two attempts
and the original ledger, source-bind this repair, and run only the remaining
eighteen IDs. Model settings, core C0-NC mechanics, deadlines, and the total US$20
ceiling remain fixed. The amendment and new qualification are separate immutable
artifacts; the original registration and results remain evidence of the failure.

Documentation checked: [Deep Agents profiles](https://docs.langchain.com/oss/python/deepagents/profiles),
[Harbor agents](https://www.harborframework.com/docs/agents),
[Harbor tasks](https://www.harborframework.com/docs/tasks),
[OpenRouter provider selection](https://openrouter.ai/docs/guides/routing/provider-selection),
[Langfuse OpenTelemetry](https://langfuse.com/integrations/native/opentelemetry).

## Reviewed deadline stop continuation

Task 12 reached its official 900-second agent deadline. Its last physical API
request began about 1.85 seconds before that deadline and timed out there without
a generation ID or settled cost. The verifier returned reward 0 and the task
container was removed. The gateway stopped the study for a transport failure.

An explicit `--continue-after-deadline-stop` permits only the unstarted task IDs
after this reviewed stop. It requires a verified last trial, clean teardown,
matching protocol, a last unresolved request with `TimeoutError`, and an agent
timeout span showing that the request began and ended within five seconds of the
official deadline. Arbitrary transport errors, routing failures, changed settings
and replayed task IDs are rejected. This is an administrative continuation; the
agent loop, tools, model, settings, official resources and deadlines are unchanged.

Preserve the original stop summary and a numbered, source-bound amendment and
qualification. The original ledger and all completed attempts remain; the
unknown charge retains its full US$1.10 reservation across continuation. Recheck
credit and requalify the changed source with fake-model and Docker fixtures before
paid work. There is no automatic request retry or background study restart.
