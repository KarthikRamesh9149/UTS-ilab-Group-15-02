# Gemini native comparison on the laptop

The user selected option 2 on 10 October 2026: up to twenty Terminus-2 attempts
and twenty OpenHands attempts, sequentially, on the original frozen development
subset. Both use Gemini 3.7 Flash through the same pinned OpenRouter transport.

`gemini_baseline_run.py` is a fresh launcher. It does not restart or replay the
earlier custom batch. Task order is frozen; the first harness alternates between
tasks. No automatic task replay or physical model-request retry is permitted.

## Spending

The original US$20 experiment limit includes US$11.229632850 known spending and
an unresolved US$1.10 reservation. The new comparison therefore starts with
US$7.670367150 conservative headroom. More account credit does not increase this
allowance. The shared ledger preserves the original requests unchanged. Every
new POST requires a durable US$1.10 reservation and a fresh available-credit
check. Stop when another reservation cannot fit. An unknown charge, transport
error, routing error, evidence error, or cleanup failure stops the batch.

## Admission and execution

- Check every frozen task file and all twenty cached image identities.
- Run affected offline tests with no external network or provider key.
- Run `--qualify` in a key-free controller on internal Docker networks. It
  exercises the same launcher, native clients, fake upstream, shared ledger,
  task networking, verifier phase and cleanup as the paid path. Synthetic
  marker rewards are not benchmark results.
- Paid execution requires that qualification's exact Python source hashes and
  OpenHands bundle hash. The model endpoint and credit are checked again.
- The paid controller has a 1.5 GiB limit. Stop other Docker workloads, including
  local Langfuse services, to accommodate official task memory limits. Admission
  requires official maximum task memory, controller memory, and a 1 GiB daemon
  margin to fit the Docker VM. Official agent/verifier deadlines and task CPU
  and memory limits are retained; setup has a separate 180-second limit.
- Task containers receive only agent/verifier log mounts. Provider credentials
  and the Docker socket stay in the controller. OpenHands receives a fresh
  trial token and a gateway listener bound to its task network interface.
- Revoke inference, close the task listener, and detach the controller before
  uploading verifier tests. Retain actual rewards even when a budget stop occurs.
- Requested task disk sizes are recorded. Docker uses shared disk without a
  per-container disk quota; this limitation is explicit in environment evidence.

## Evidence and delivery

Raw exchanges, native logs, command outputs and task artifacts remain in the
private Linux evidence volume, with a Windows backup. Metadata spans are
durably spooled throughout. Restart local Langfuse after the batch; import with
the separate experiment name and verify every observation ID through readback.
The shared API key is never sent to Langfuse. Only source, sanitized registration,
qualification, aggregate/per-task results, and the brief belong in Git.

Report attempted/unstarted cells, actual verifier scores, passes, verifier and
infrastructure failures, budget stops, known spending and unknown reservations
separately for each native harness. The remaining allowance may censor the
comparison. Do not infer a full twenty-task superiority claim from partial data.
