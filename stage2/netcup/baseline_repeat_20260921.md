# Separate baseline repeat: 21 September 2026

The user authorised prioritising all 89 tasks for each of Terminus-2 and
OpenHands, removing the small per-task monetary cap and leaving US$1 in reserve.
This is a new experiment, not a repair or replacement of the original scores.

## Execution

- Root: `/opt/uts-capstone-baseline-repeat-20260921` on the existing Netcup host.
- Service: `uts-stage2-baseline-repeat-20260921.service`.
- Runner: `stage2/run_baseline_repeat.py`.
- Registration: `.runtime/stage2/baseline-repeat-matrix.json` (178 unique cells).
- Progress: `.runtime/stage2/baseline-repeat.log` and individual result files.
- Trial IDs start with `repeat1-final-`; original result files remain untouched.
- Original experiment matrix lock stays held during the repeat, preventing
  overlapping old-study execution.

At 07:42 UTC the service was active, the first Terminus-2 task had started,
and two real API requests had settled. No repeat task had finished yet.
This is launch evidence, not a result or assurance that all 178 will finish.

The frozen model remains DeepSeek V4 Flash 0731, routed to DeepInfra FP8 via
OpenRouter. Harness implementations, task bytes, provider, sampling, output
token limits, official deadlines, CPU/RAM allocations and isolation are unchanged.

## Budget

The launch snapshot was US$11.540139332 available credit. Original unresolved
liability of US$7.774208 remains protected; this is not confirmed spending.
With the new US$1 reserve, the funded allowance for new calls is US$2.765931332.
There is no tighter per-task monetary allowance: one task can use the remaining
experiment allowance, subject to its unchanged time/output limits. There are
no automatic top-ups. Every dispatch checks fresh account/key credit, old
liability and new request reservations. The repeat pauses before scheduling
a task when a full request reservation no longer fits. Completion within the
available allowance is not guaranteed.

The budget profile only takes effect in a separately prepared experiment root.
Without that profile the original defaults remain unchanged. Do not deploy the
changed source over the original frozen running installation. No original
ledger policy was edited; the repeat uses fresh ledgers and carries historical
liability explicitly. Parent ledger fingerprints are checked before each task.

## Verification

- Native server suite: 800 tests; 799 passed, one optional PDF-package test
  skipped. No failed tests in the final run.
- Active repeat profile: 13 targeted budget/schedule tests passed.
- Gateway container: nine budget tests passed with networking disabled.
- Full Harbor/Docker/HTTP/verifier synthetic test passed; zero paid calls.
- Gateway parent layers and runtime configuration preserved; changed image
  source files matched the host exactly.
- Image: `sha256:5341f40edd78f982d509c6e57de565e373f323c9e3bd14814ac560c3e4f09c2b`.

The original scores (Terminus-2 18/89, OpenHands 4/89) stay separate. Do not pool
results, replace failed original tasks with repeat passes or tune custom policy
using held-out task diagnostics. A fair custom comparison against these repeat
baselines requires the same revised limits. Higher baseline scores are possible,
not guaranteed. Keep unknown billing explicitly unknown.
