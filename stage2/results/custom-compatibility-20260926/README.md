# Custom runtime compatibility repairs

26 September 2026. Candidate `stage2-candidate-0.3.0`. **Offline engineering
evidence, not a completed benchmark run or a quality win.**

## Changes

- The real Deep Agents file-tool flow now declares a text-only model profile
  and serializes tool messages as text. Unsupported attachments are explicitly
  described as not transmitted; no image understanding is invented.
- A hash-pinned CPython fallback is copied into a private container directory.
  Existing task interpreters stay first on PATH. No package downloads, system
  Python replacement, host mount or new model is required.
- Command capture stops waiting when a finished shell leaves a background
  child holding stdout open. Foreground timeouts remain ordinary exit-124 tool
  observations. Genuine capture/transport errors remain errors, not successes.
- Structured file-read envelopes have a separate bounded capture allowance so
  long valid reads do not become truncated, invalid JSON. Ordinary shell
  observations remain bounded separately.
- SIGUSR1 or an operator stop marker prevents the next trial after the active
  trial finishes. Cancellation still propagates, but phase cleanup/revocation
  observations are retained. These fixes do not rewrite the old fourth result.
- New failure metadata records stack locations and known capture error codes,
  not private exception messages, commands, request bodies or model responses.

The model/provider, temperature, reasoning level, output-token setting and
official task resources/deadlines are unchanged. There is still no project or
task financial cap, reserve or artificial model-call count limit. Actual
provider constraints, tool/process safety bounds and isolation remain.

## Evidence and limits

The first native capability check passed on all 20 fixed development images.
Five lacked Python. The fallback, command execution, file read/write/edit,
foreground timeout and background-process checks passed; all probe containers
were removed. A second source-bound check also passed all 20 images, including
16,000-line file reads. [Native image evidence](native-images.json) records the
image identities, source hashes, runtime archive hash and per-image checks.
Each probe is isolated without network access and makes zero paid API calls.
These checks use a small Docker test adapter, not the complete scored Harbor
orchestration path. They do not claim task passes.

A generic background-output fixture reproduces the old helper's RuntimeError
on the mailman image and succeeds with the new helper. It does not prove the
exact original failure cause, because that attempt did not retain a traceback.
No original model command was replayed.

Local discovery: 983 tests run, 982 passed and one pre-existing skip. The
separate 34-test legacy custom suite passed. Regression coverage includes the
actual Deep Agents graph and OpenAI-compatible serialization with synthetic
responses, the existing shared gateway policy, cancellation and stop-at-boundary.
The same native dependency environment passed 50 targeted regression tests.
One local discovery run caught two return-value regressions in the cancellation
change; both were corrected before the passing full-suite run.

## Next admission step

The 0.3 adapter is deliberately not admitted by the frozen 0.2 study registry.
Before paid execution, build a separate deployment, bind the runtime archive
and changed source, rehearse the actual Harbor/gateway/verifier lifecycle,
then register the successor's fixed-20 cells. Retain the partial C0 evidence
and all genuine failures. Do not patch or resume the original deployment.
Do not tune using held-out task answers or claim superior accuracy until a
complete, matched development comparison exists.
