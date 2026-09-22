# Next baseline run: implementation checkpoint

Checked 22 September 2026, 11:10 UTC. **Not started.**

The current capped repeat was active at 139/178, with task140 in progress.
All 139 completed trials had binary verifier results and complete cleanup.
Its registered source files were unchanged. We have not changed its limits or
combined its results with another run.

## What is ready

The next experiment has a separate deployment:
`/opt/uts-capstone-credit-only-20260922`.

- `run_credit_only.py`: 89 frozen tasks × two baselines, one attempt per cell.
  It cannot overlap either predecessor, and cannot replay an existing attempt.
- `credit_only_gateway.py`: no project budget caps, reserve, cost estimates,
  reservation checks, receipt checks or balance checks before model requests.
  The provider's price filter is also removed; its purpose is documented in
  [OpenRouter's routing reference](https://openrouter.ai/docs/guides/routing/provider-selection#max-price).
- Accounting is observational. Known costs are saved; missing costs stay
  unknown. A missing cost does not discard a usable model response.
- Real provider credit rejection stops new task dispatches. After a
  user-confirmed manual top-up, only unstarted tasks can resume. There is no
  automatic purchase or retry of the already-started task.
- The same model, endpoint, native harness code, output settings, official
  task limits, task bytes and container safeguards are preserved.

The pinned OpenHands 0.62.0 package defaults `max_budget_per_task` to `None`;
the baseline factory supplies no override. This was checked in the published
wheel whose SHA-256 is
`ede573ee052781e7b4b9ce9b882d350464f486178241991b7485dfa03e506c4a`,
which matches the project's dependency lock. No extra native OpenHands
monetary cap was found in that configuration.

The API/interface-design checks kept error handling and accounting separate
from the agent's task execution. The old reserved-budget path remains the
default for old experiments.

## Verification completed

| Check | Evidence |
| --- | --- |
| Targeted local tests | 37 passed, including the actual Terminus client without a cost field |
| Full native offline suite | 790 tests: 789 passed, one optional PDF test skipped; zero failures/errors |
| Tests inside the new gateway image | 17 passed, none skipped |
| Active predecessor source check | All registered hashes unchanged |
| New paid model requests | None |

Native offline tests ran in a network namespace with only loopback enabled.
The gateway-image tests also used `--network=none`. The skipped test requires
optional PDF packages; it is unrelated to benchmark execution. No PDF was made.

Candidate image:
`sha256:d49c6f6a40ec9bbc5a9932e201e4e93fe151ae8f55cba054507bd464a6f10f8a`.
It retains the qualified parent's layers and runtime configuration, except
for its explicit new gateway entry point. Installed new gateway sources match
the host candidate.

Private machine-readable evidence is in the new deployment's
`.runtime/stage2/credit-only-offline-tests.json` and
`.runtime/stage2/credit-only-image-tests.json`.
Both were rerun after the final summary edge-case correction, and their source
bindings match the current candidate. Earlier offline evidence is retained in
the private `qualification-attempt-1` directory, not overwritten.

## Remaining before launch

1. Let the predecessor finish or reach a terminal stop. Check exact coverage,
   no active model access and completed cleanup. Report partial coverage if it
   stopped short of178; do not call it complete.
2. Run `.venv/bin/python stage2/qualify_credit_only.py runtime` from the new
   deployment. It holds the original, predecessor and new execution locks.
   Its isolated full Harbor/container fixture uses a fake key and fake model,
   checks three usable responses with unknown costs, then verifies cleanup.
3. Only after that succeeds, launch `stage2/run_credit_only.py` as a persistent
   server service with working directory set to the new deployment and
   `UMask=0077`. Do not launch or qualify a second concurrent matrix.
4. Monitor its separate `credit-only-matrix.json`, `creditonly1-final-*`
   result keys and log. Do not use old budget-ledger admission or old report
   exporters that require every receipt to be verified.

Any runtime source change invalidates the recorded offline checks. Preserve
old evidence and rerun affected qualification before paid launch. A future
manual top-up can be acknowledged with `--confirm-manual-top-up STOPPED_TRIAL_ID`
only after the user confirms it; this never repeats the stopped task.

No claim is made here that either baseline score improved, that the custom
harness won, or that the whole project is complete.
