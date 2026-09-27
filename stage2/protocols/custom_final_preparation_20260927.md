# Custom final-run preparation

The user requested a three-day target on 27 September and explicitly said not
to compromise quality. The working target is 30 September afternoon, Sydney
time. It is not a guarantee or permission to skip required checks.

## Schedule target

- 27 September: finish the registered development comparisons while preparing
  and testing the final-run code locally, without changing the active source.
- 28 September: complete the planned confirmation and diagnostic, freeze the
  selected harness, qualify the final deployment and register all 89 cells.
- 29–30 September: finish the custom 89, audit the results and preserve the
  evidence off-server. Reuse the completed corrected baseline scores.

The full custom run is provisionally estimated at 24–36 hours, using the earlier
178 baseline attempts' approximately 51 hours as a reference. Custom behaviour,
task mix and provider latency can differ. If the earlier steps are not ready,
revise the estimate instead of weakening the checks. Do not launch overlapping
matrices to meet the date or silently omit confirmation or the diagnostic.

## Offline selection work

`portable_final_selection.py` consumes complete, already audited C0/C1/C2
summaries. It validates all 20 task identities and their order, exact trial IDs,
result hashes, binary or explicitly missing rewards, counts, costs and runtimes.
It recomputes aggregates instead of trusting supplied totals. The caller still
has to verify the underlying registration, source and result-file bindings.

Selection keeps the existing ranking: passes first, then cost only when every
compared block has a known total, simpler design, observed runtime and condition
name. C2 must use the parent selected from C0/C1 before C2 ran. A later unknown
C2 cost cannot retrospectively change that parent. The planned one-lever
ablation, or unchanged repeat when no retained lever increased passes, is kept.

Missing costs and verifier outcomes remain visibly missing. There are no
financial or request-count ceilings in this module. It does not claim an
efficiency win, select a best result for each task, freeze a deployment or launch
paid calls. It explicitly reports `paid_launch_ready: false`.

## Requirements before final execution

1. Complete and audit all registered development blocks. Retain every outcome,
   including the stopped 0.2 engineering run; do not replay started attempts.
2. Implement and qualify the source-bound confirmation/diagnostic path for
   passive accounting. Preserve the approved matched comparison and ablation
   rules; the old capped runners cannot be reused unchanged.
3. Bind the finalist, model/provider settings, runtime, dependencies, source and
   development evidence into an immutable freeze. Do not select a finalist from
   incomplete blocks or use held-out answers for tuning.
4. Pass affected local checks and actual native synthetic rehearsals for the
   final launcher, including admission, duplicate prevention, accounting,
   cancellation, model-access revocation and resource cleanup. Reuse unaffected
   evidence only while its bindings remain unchanged.
5. Check current processes and retained keys, then register exactly one attempt
   for each of the 89 tasks before dispatch. Keep the same model, official task
   resources and deadlines, and shared provider retry policy as the baselines.
6. Audit the final 89 distinct cells, retain failures and missing results,
   verify a private off-server backup, and publish only curated metadata.

No new spending cap, reserve or model-call ceiling is introduced. Actual
provider credit, authentication and identity constraints still apply. There
are no automatic top-ups, purchases or account/key-limit increases.

The current paid development deployment is untouched by this offline module.
It is not yet a native-qualified final deployment, and the final 89 have not
started. No full-benchmark improvement is established.

## Verification on 27 September

- All 23 targeted selection tests passed, using synthetic metadata only.
- The final local Stage 2 suite ran 1,069 tests: 1,068 passed and one existing
  test was skipped. These are software checks, not benchmark scores.
- A read-only check accepted the actual native C0 summary and matched all 20
  result hashes to its saved audit. Its five unknown-cost requests remained
  unknown; no finalist was selected.
- No additional paid calls, qualification jobs or benchmark runs were launched
  for this change. The existing C1 job continued independently.
