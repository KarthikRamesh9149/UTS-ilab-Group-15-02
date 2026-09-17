# Local preparation and authenticated CETUS handoff

Prepared on 17 September 2026. **No new cluster access or scored run performed.**
The user will restore the login after returning home. Do not assume the old
GPU job status is current and do not submit a duplicate model job.

## What is prepared

| Component | Local evidence | Live check still needed |
| --- | --- | --- |
| One integration check | `cetus_harbor_check.py` and its PBS wrapper; full orchestration tested with mocked Apptainer | Run the exact code inside a PBS CPU allocation |
| Harbor environment | Actual BaseEnvironment interface and real Harbor Verifier with simulated container results | Actual image, transfer, command, verification and cleanup roundtrip |
| Model connection | Real Unix-socket HTTP roundtrips to a scripted local server; byte bounds, revocation, request budget | Qualified llama.cpp socket and chosen model |
| Native Terminus configuration | Actual Terminus LLM client through actual loopback gateway and scripted Unix service | Native agent plus real task environment and model |
| Native OpenHands configuration | Actual Harbor agent constructor, forwarded connection settings, hash-locked installer assertions | Installed OpenHands runtime and model wire compatibility |
| Detailed observations | Generation usage, command timing and actual LangGraph callbacks; metadata-only OTLP payload | Real model usage and Langfuse provider/dashboard acceptance |

These are different evidence levels. Constructors, mocked environments and
scripted model replies are not baseline trials or model performance evidence.

## One prepared integration job

From a verified copy of this branch's `stage2` directory on CETUS, the prepared
submission is `qsub -v UTS_HARBOR_PYTHON=/absolute/path/to/qualified/python3.12
cetus_harbor_check.pbs` (one shell command). The interpreter path is a placeholder,
not a claim that the environment is installed. It must be a Linux Python 3.12
environment with the pinned Harbor dependencies, not the Mac virtualenv or
CETUS system Python 3.6. Prepare and inspect that environment after login.

The job requests one CPU, 2 GB RAM and eight minutes. It pulls a harmless Python
fixture image, starts its own network-none instance, attaches the Harbor adapter,
checks the tested private paths, writes a fixed marker, uploads the fixture
verifier through the actual transfer path, downloads its reward, records traces,
stops the instance and verifies a subsequent exec is rejected. The fixture
image is fetched by tag and its resulting bytes hashed, not treated as an
official task-image identity. No LLM is used. Its `reward=1`, if obtained, is
only a synthetic transport/verifier check, never a Terminal-Bench pass.

Keep the whole relevant source directory together; the script imports the
adapter, instance/directory transfer, qualification flags, lifecycle and local
trace modules and reads `fixtures/lifecycle`. No credentials, `.env`, Mac tool
environments, historical raw logs or model weights belong in that code transfer.
The script retains private scratch and `harbor-check-<job>/result.json` evidence.
It does not delete unrelated files or export traces to a cloud service.

## Model connection and native baseline settings

`LocalModelClient` connects only to a same-user Unix socket in a private owned
directory. It uses the frozen protocol from `cetus_local_manifest.json`:
Qwen3-Coder-Next Q4_K_M, 32,768 context, at most 8,192 generated tokens per request,
temperature 1.0, top-p 0.95, top-k 40 and at most 100 attempted requests per trial.
Failures count towards the request budget. There are no automatic retries,
external-provider fallback, API-key lookup or OpenRouter imports. Missing token
usage remains unknown, not zero. Context token counting is still performed by
the qualified model/runtime; the byte limit is not a tokenizer or context proof.
The client enforces request parameters but does not attest model weights or GPU
allocation; those remain the model qualification job's responsibility.

`local_model_gateway.serve(client)` adds a token-authenticated loopback endpoint
for native OpenAI-compatible clients. A fresh random trial token is returned
in memory, not written into checked-in configurations. Closing the gateway
revokes access. The tested chain is:

```text
Native Terminus LLM client -> loopback trial gateway -> Unix socket -> scripted model
```

This test sends actual serialized native requests, including top-k and output
limits. Replacing the final fixture with the qualified llama.cpp process still
needs live verification. Nonstreaming only is implemented. Streaming/native
OpenHands behaviour must be checked before declaring compatibility.

`baseline_config` and `create_baseline` prepare Terminus-2 and OpenHands with
the same model/sampling settings and no equal-iteration override. A 24,576-token
input allowance reserves the 8,192-token output budget within the 32,768 context.
OpenHands version 0.62.0 uses the existing hash-locked dependency set; the installer
and its dependency downloads were not run in this increment. Default reasoning
options are not forwarded to the local model. Terminus's extra retry wrapper is
disabled, and both configurations set native retry counts to zero.

**No container-to-controller route is installed by this work.** An isolated
container's loopback is not the host's loopback. OpenHands runs in its task
environment, so reaching the local model gateway from that environment remains
an integration task. Do not substitute host networking or silently mount the
private model socket based on these local tests. No networking permission was
changed, tested or requested during this local-only increment.

## Observability

- PhaseRecorder still records setup, agent, verifier, cleanup and trial-root
  spans. It now serializes concurrent observations safely.
- LocalModelClient records generation timing, attempted requests and token
  usage returned by the model service. No prompt, response or key is recorded
  in the metadata spool. Native agent trajectory files have their own retention
  policy and are not automatically part of the cloud export.
- The adapter records each environment exec as a tool event. This includes
  setup and verifier commands, **not just agent tool calls**; phase timestamps
  are needed to separate them in analysis. File transfers are not counted as
  tool calls. Output callbacks are buffered, not live streaming.
- `LocalGraphCallbacks` records graph/chain durations and statuses without
  inputs, outputs, exception text or arbitrary tags. It is tested with an actual
  StateGraph; it has not yet been attached to an evaluated custom agent.
- Observation-write failures are recorded separately and do not change model
  responses or verifier rewards. Any final scored-evidence audit must reject
  missing required metrics or trace errors rather than silently reporting them.
- Existing Langfuse export is post-run and explicit. Local OTLP payload checks
  are not proof of cloud receipt or dashboard visibility. No cloud request was
  made. Generation usage uses the supported OTEL token attribute names.

External inference cost is zero on this route. Native client API cost fields
are zero to avoid invented hosted-provider charges; they do not mean GPU time
is free. Actual GPU/CPU allocation time and its monetary value remain separate,
with monetary value unknown until an applicable rate is available.

## After authentication, in order

1. Inspect current scheduler job/history and existing model results before any
   new submission. Do not modify or duplicate the prior GPU job blindly.
2. Prepare the pinned Linux Harbor controller environment and run the one trusted
   integration job above. Inspect its result and cleanup, not only PBS exit zero.
3. Inspect model qualification output; complete real generation/tool/context
   checks on allocated compute resources. Do not infer success from downloads.
4. Finish native installed-agent endpoint reachability and task setup. Resolve
   actual failures through supported implementations; do not label untested
   alternatives as forbidden or promise that every task works already.
5. Reference-qualify task environments, then run baseline trials under the
   frozen protocol. No production scored launcher or full 89-task admission is
   delivered by these preparation modules alone.
6. Develop the custom harness after the baselines work. Attach the tested graph
   callbacks then; they do not themselves constitute a custom harness.

No score, benchmark improvement, live model success, fresh cluster status or
leaderboard submission is claimed by this handoff.

## Final local verification

All 368 tests passed on the final code candidate: 324 Stage 2 tests, 32 custom
dependency tests and 12 historical pilot tests. The PBS wrapper passed shell
syntax checking, and the new controller/client modules passed compilation.
The local server tests use Unix sockets and loopback only with scripted replies;
the actual LangGraph tests execute synthetic nodes without model calls.
