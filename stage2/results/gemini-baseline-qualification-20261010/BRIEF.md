# Gemini native baseline preparation — 10 October 2026

**No additional paid tasks or provider calls were run. New API spending: US$0.**

The original custom batch remains 20 attempts, 13 passes, 18 official scores
and two unscored attempts. This work prepares the wider project comparison;
it is not a benchmark result or authorization for another paid batch.

## Implemented and checked

- Gemini adapters for Harbor's native Terminus-2 and OpenHands 0.62.0 loops.
  Native prompts, tools and context management remain inherited. The adapters
  set the fixed model parameters, disable transport retries and cache the
  OpenHands installation. A one-million-iteration guard is explicit; synthetic
  and future official agent deadlines remain the primary runtime limit.
- A shared baseline ledger inherits the complete original ledger under a
  checked SHA-256, preserves all original requests and retains unresolved
  charges. It cannot increase the original US$20 cap, silently settle an
  inherited unknown charge or allocate credit to an unregistered trial.
  No automatic budget split between baselines is imposed.
- The gateway now accepts the exact native `reasoning_effort=high` alias,
  plain structured text blocks and an empty assistant content list paired with
  local function calls. The existing OpenRouter model, provider, reasoning,
  sampling and output-limit settings remain fixed. Images, extra text-block
  fields, provider fallback and billable plugins remain rejected.
- **49 offline checks passed** without network, an upstream key or a Docker
  socket. The checks include the original Gemini, Langfuse and native adapter
  regression suites.
- **Two real Harbor/Docker synthetic lifecycles passed** against the final
  source snapshot: Terminus made three scripted requests and OpenHands two.
  Both produced the marker, passed the synthetic verifier, revoked model
  access and removed their task containers with no cleanup or trace errors.

The fixture responder has no upstream client or API credential. Its controller
and tasks used internal Docker networks without an internet route. Each task
had only its log mounts, no controller socket or upstream key, and no privileged
mode. Synthetic limits were one CPU and 1 GiB for Terminus, one CPU and 2 GiB for
OpenHands, with a 180-second agent deadline. These are fixture limits, not claims
that official benchmark resource settings were evaluated in this work.

## Diagnostics and logging

Earlier synthetic rounds exposed Docker's inability to add a controller in
`none` network mode to another network, the reasoning alias, structured text
and empty assistant tool-call content. These failures remain in the private
evidence and are separately logged. The synthetic task image now has a dedicated
`/workspace`; the earlier root working directory caused OpenHands to recursively
initialize `/`. Official task images and working directories were not changed.

Local [Langfuse](http://127.0.0.1:3300) contains **10 separately labeled synthetic
traces and 146 observations**, including the failed preparation rounds and the
offline checks. Every observation identity was read back and matched. Synthetic
verifier rewards are omitted and all traces are marked
`synthetic_no_benchmark_score` and `paid_generations=0`.

Full scripted exchanges, tool output, trajectories, setup diagnostics and source
snapshots remain private in:

```text
F:/Capstone/.runtime/gemini-comparison-20261010/
Docker volume: uts-gemini-baseline-qualification-20261010
```

Both qualification controllers are stopped. Their evidence volume and cached
images are preserved. The public [qualification.json](qualification.json) records
source hashes, image identities, the OpenHands bundle hash, earlier failures,
resource audits and complete Langfuse observation-ID readback counts.

## Remaining work and budget

Same-model paid Terminus and OpenHands benchmark results are **still missing**.
These fixtures prove the tested synthetic integration, not provider behavior or
success across the frozen development subset. A paid comparison needs its own
fresh registration and launcher admission, a current provider/credit check,
official per-task resources/deadlines and separate outcome reporting. Do not
reuse or restart the completed custom study launcher.

Known prior spending is **US$11.229632850**, with **US$1.10** unresolved. Conservative
headroom under the original US$20 cap is **US$7.670367150**. A paid comparison
could stop before completing the requested task set; only authoritative new
cost evidence can release its reservations. Additional account credit does not
increase this experiment cap.

The user requested a stop after the first 20 attempts and a decision before
continuing. That milestone is complete. Further paid benchmark attempts await
that decision; the wider comparison goal remains active.
