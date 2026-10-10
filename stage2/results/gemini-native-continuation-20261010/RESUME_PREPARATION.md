# Remaining native comparison: preparation only

No paid calls were made during this preparation. The closed controller remains stopped. The [exact remaining manifest](resume-preparation.json) selects cells 19–40, with eleven Terminus-2 and eleven OpenHands attempts, and binds the private closed ledger and outcomes by SHA-256. It excludes all eighteen completed attempts.

## Spending and billing

The existing US$50 total allowance remains unchanged. Confirmed spending is US$31.490725275, unresolved reserves are US$2.20, and the conservative remaining allowance is US$16.309274725. Live available credit must be rechecked before any future paid request. This preparation grants no additional allowance.

A single read-only generation metadata lookup at 2026-10-10T12:09:37.574577+00:00 still returned HTTP 404 for request 3009. Its US$1.10 reserve remains held; the earlier custom request retains its separate US$1.10 reserve. The closed ledger was unchanged. No generation or task was replayed.

## Current admission limitation

`gemini_baseline_run.py:continuation_inputs` requires exactly three closed predecessor attempts. `gemini_baseline_budget.py:ExtendedBaselineLedger` requires a predecessor cap of US$20 before applying the US$30 amendment. The current predecessor has eighteen closed attempts and a US$50 cap. The existing launcher therefore cannot admit this suffix as written; reusing its old authorization would not be a valid continuation.

Before any continuation, admission must preserve all 3,010 predecessor request records, both unknown reserves, the existing authorization and the eighteen immutable outcomes. It must retain US$50 as the total cap, select only this suffix, use a fresh evidence directory, and reject duplicate attempts. Changed admission code requires new source-bound fake-model and Docker qualification. Agent loops, prompts, model/provider/settings, official resources, deadlines and failure stops remain frozen.

The decision to continue after the unresolved-charge stop is pending. This manifest is preparation, not a qualified paid entrypoint.

## Goal evidence and outstanding work

| Requirement | Evidence | State |
|---|---|---|
| Custom Deep Agents/LangGraph harness, frozen development subset | [Original custom brief](../gemini-dev20-laptop-20260930/BRIEF.md), original registration and qualifications | Twenty attempts complete; two unscored infrastructure attempts retained |
| Fixed Gemini model/provider/settings | Original custom registration; [native registration](registration.json); generation metadata | Recorded throughout; no fallback or model switching |
| Native Terminus-2 and OpenHands comparison | [Terminal batch brief](BRIEF.md), [outcomes](tasks.json), [comparison](comparison.json) | Eighteen of forty attempts closed; twenty-two unstarted |
| Spending limit and unresolved-charge accounting | [Summary](summary.json), [billing diagnostic](billing-diagnostic.json), preserved private ledger | US$50 total cap; both unknown reserves held |
| Local CPU/memory limits, deadlines and cleanup | Per-task environment and phase evidence in `tasks.json`; source-bound qualification | Enforced; shared Docker disk has no per-task quota. Official tasks request no GPU; Gemini inference is remote |
| Private complete logs and Langfuse metadata | [Evidence audit](evidence-audit.json), [Langfuse ID audit](langfuse.json), [generation cost audit](langfuse-generation-audit.json); original custom and earlier native import reports | Verified; raw exchanges and solutions remain private |
| Separate branch, sanitized results and brief | Commit `88989bffe5feb061d300921a29f8baf5c91d1244` on `codex/gemini-dev20-results-20261005`; matching remote SHA verified | Delivered; credentials, PDFs and raw evidence excluded |
| Complete remaining native scope or record authorized early termination | Exact suffix manifest and pending direction | Incomplete; goal remains active |

This preparation does not replace the requested comparison with the seven tasks currently having scores from all three harnesses. Unstarted attempts are not assigned scores, and the partial comparison does not establish full-subset superiority.
