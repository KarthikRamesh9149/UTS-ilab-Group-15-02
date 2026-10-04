# Stage 2 results analysis

A small, read-only analysis of the committed Stage 2 Terminal-Bench 2.1 results,
by Saranya. It reads only CSV files under `stage2/results/` and writes nothing
there. There are no model calls and no task runs. The benchmark runs, harnesses
and result files are Karthik Ramesh's Stage 2 work; the analysis code here is mine.

**Bottom line:** nothing here establishes that C0-NC beats either baseline.
- C0-NC scored 2 tasks fewer than Terminus-2 and 6 more than OpenHands.
- Neither difference is statistically distinguishable from zero on these single runs.
- On the 69 tasks not used in custom development, C0-NC leads OpenHands by 1 task.
- The baselines and C0-NC ran days apart, and the matched comparison has not been run.

## Inputs

| Run | File under `stage2/results/` |
|---|---|
| Terminus-2, round C (89 tasks) | `baseline-corrected-20260923/trials.csv` (`harness = terminus-2`) |
| OpenHands, round C (89 tasks) | `baseline-corrected-20260923/trials.csv` (`harness = openhands`) |
| C0-NC final (89 tasks) | `custom-no-cutoff-final-20260928/c0-nc/trials.csv` |
| C0, C1, C2 (dev20) | `custom-portable-20260926/c{0,1,2}/trials.csv` |
| C3 (dev20) | `custom-deadline-20260927/c3/trials.csv` |
| Baselines on dev20 (reference rows) | `baseline-corrected-20260923/development-baselines.csv` |
| C0-NC setup recovery (sensitivity check only) | `custom-no-cutoff-recovery-20260929/trials.csv` |

The loader rejects duplicate task rows, non-binary rewards, and rows whose
status disagrees with their reward. Blank fields stay unknown, never zero.

## How to run

The code uses the Python standard library only (3.10 or newer). From this folder:

```bash
python -m saranya_analysis.report            # prints every table below as markdown
python -m pytest tests                       # needs pytest
```

The tests use small fixture CSVs. They cover parsing, the paired table, exact
McNemar values, bootstrap determinism with a seed, failure categories and usage
totals. They also check the published Stage 2 scores (52, 44, 50; 15, 14, 14, 13;
14, 10) against the committed files.

## Method

- **Score:** passes over all 89 intended tasks. A missing verifier outcome
  (C0-NC's 3 setup failures) counts as not passed and stays in the denominator.
  The pass rate among valid trials is shown separately.
- **Paired table:** per task, over tasks where both harnesses have a verifier
  outcome. Excluded tasks are listed.
- **McNemar test:** exact two-sided binomial test on the discordant pairs at p = 0.5.
- **Bootstrap:** 10,000 resamples of whole tasks with replacement, seed 42. The
  same tasks are drawn for both harnesses, so the pairing is kept. The interval
  is the 2.5th–97.5th percentile of the pass-rate difference over 89 tasks.
- **Failure categories:** taken from the recorded `agent_error_type`,
  `verifier_error_type`, `status`, `reward` and `http_429_requests` fields:

| Category | Rule |
|---|---|
| Timeout | agent timeout, no HTTP 429 recorded |
| Rate limit | agent timeout or API error with at least one HTTP 429 recorded |
| Setup error | `status = setup_failed`, no verifier outcome |
| Verifier fail | no agent exception; the official checks failed |
| Other | never assigned automatically |
| Needs review | anything the fields cannot settle: API errors without a 429, startup/connection errors, permission-denied errors, capture-helper errors, unknown statuses |

  Categories describe what was recorded, not proven causes. "Rate limit" does
  not mean rate limiting alone caused the failure.

## Results: all 89 tasks (one run each)

### Scores

| Harness | Passes / intended | Valid verifier outcomes | Pass rate (intended) | Pass rate (valid only) |
|---|---|---|---|---|
| Terminus-2 | 52 / 89 | 89 / 89 (100.0%) | 58.4% | 58.4% |
| OpenHands | 44 / 89 | 89 / 89 (100.0%) | 49.4% | 49.4% |
| C0-NC | 50 / 89 | 86 / 89 (96.6%) | 56.2% | 58.1% |

### Development tasks vs held-out tasks (same runs, split)

C0 was selected on the dev20 tasks, so only the other 69 tasks are held out
from custom-harness selection. Stage 2's protocol asks for them to be reported
separately.

| Harness | dev20 tasks | Other 69 tasks | Valid on other 69 | Pass rate on other 69 (intended) |
|---|---|---|---|---|
| Terminus-2 | 14 / 20 | 38 / 69 | 69 / 69 | 55.1% |
| OpenHands | 10 / 20 | 34 / 69 | 69 / 69 | 49.3% |
| C0-NC | 15 / 20 | 35 / 69 | 66 / 69 | 50.7% |

### Paired per-task comparison

| Comparison | Both pass | Only C0-NC | Only baseline | Neither | Excluded (no outcome) | McNemar p |
|---|---|---|---|---|---|---|
| C0-NC vs Terminus-2 | 42 | 8 | 8 | 28 | 3 | 1.000 |
| C0-NC vs OpenHands | 36 | 14 | 7 | 29 | 3 | 0.189 |

Excluded tasks (C0-NC setup failures): pytorch-model-recovery, query-optimize,
schemelike-metacircular-eval.

#### Sensitivity checks

| Comparison | Treatment of the 3 missing | Only C0-NC | Only baseline | McNemar p |
|---|---|---|---|---|
| C0-NC vs Terminus-2 | missing counted as C0-NC failures | 8 | 10 | 0.815 |
| C0-NC vs Terminus-2 | recovery outcomes substituted (not official) | 8 | 10 | 0.815 |
| C0-NC vs OpenHands | missing counted as C0-NC failures | 14 | 8 | 0.286 |
| C0-NC vs OpenHands | recovery outcomes substituted (not official) | 14 | 8 | 0.286 |

The separate recovery attempts were 0 passed of 3, so substituting them gives the
same numbers as counting the missing tasks as failures. Stage 2 states the
recovery outcomes are not replacements for, or additions to, the original 89.
For example, the recovery attempt on schemelike-metacircular-eval made 56 model
requests, all of them HTTP 429, and never received a model response.

### Pass-rate differences with paired bootstrap intervals

| Difference | Observed | 95% bootstrap interval |
|---|---|---|
| C0-NC − Terminus-2 | -2.2 pts | [-11.2, +6.7] pts |
| C0-NC − OpenHands | +6.7 pts | [-3.4, +16.9] pts |
| Terminus-2 − OpenHands (reference) | +9.0 pts | [+0.0, +18.0] pts |

Both C0-NC intervals include zero. The baseline-vs-baseline interval just
touches zero.

### Failure categories

| Harness | Passed | Timeout | Rate limit | Setup error | Verifier fail | Other | Needs review | Passes with an agent error recorded |
|---|---|---|---|---|---|---|---|---|
| Terminus-2 | 52 | 9 | 17 | 0 | 10 | 0 | 1 | 6 |
| OpenHands | 44 | 10 | 19 | 0 | 10 | 0 | 6 | 3 |
| C0-NC | 50 | 9 | 16 | 3 | 9 | 0 | 2 | 5 |

The baseline counts reconcile with Stage 2's own breakdown in
`baseline-corrected-20260923/README.md`.

Needs-review cases:
- **Terminus-2:** raman-fitting, an API error with no 429.
- **OpenHands:** six startup/connection errors (filter-js-from-html,
  gpt2-codegolf, headless-terminal, mailman, openssl-selfsigned-cert,
  pytorch-model-recovery). Stage 2 records their cause as unconfirmed.
- **C0-NC:** build-cython-ext and train-fasttext. Both were model-access-denied
  errors within about 40 seconds of the deadline, after 23 and 100 HTTP 429s.

### Cost and tokens

| Harness | Model requests | Accepted responses | HTTP 429 | Unknown-cost requests | Known cost (US$) | Total cost | Known input tokens | Known output tokens | Trials with complete token counts |
|---|---|---|---|---|---|---|---|---|---|
| Terminus-2 | 2,007 | 1,339 | 645 | 668 | 0.9199 | unknown | 24,166,772 | 2,200,743 | 28 / 89 |
| OpenHands | 3,183 | 2,410 | 749 | 773 | 1.4585 | unknown | 52,136,188 | 2,363,608 | 33 / 89 |
| C0-NC | 3,657 | 2,858 | 774 | 799 | 1.7140 | unknown | 68,277,661 | 2,300,682 | 38 / 89 |

"Known cost" is the sum of response-reported costs. Total cost is unknown for
every run, because some requests have no cost.

### Agent runtime

| Harness | Trials with measured agent time | Total agent hours | Median agent seconds |
|---|---|---|---|
| Terminus-2 | 89 / 89 | 22.0 | 758 |
| OpenHands | 89 / 89 | 23.8 | 794 |
| C0-NC | 86 / 89 | 21.3 | 642 |

## Results: fixed dev20 tasks (separate; never pooled with the 89-task numbers)

C0 to C3 are four custom-harness variants, each run once on the same 20
development tasks. The baseline rows are round C's attempts on those 20 tasks,
included for reference.

### Scores

| Harness | Passes / intended | Valid verifier outcomes | Pass rate (intended) | Pass rate (valid only) |
|---|---|---|---|---|
| C0 | 15 / 20 | 20 / 20 (100.0%) | 75.0% | 75.0% |
| C1 | 14 / 20 | 20 / 20 (100.0%) | 70.0% | 70.0% |
| C2 | 14 / 20 | 20 / 20 (100.0%) | 70.0% | 70.0% |
| C3 | 13 / 20 | 20 / 20 (100.0%) | 65.0% | 65.0% |
| Terminus-2 (round C, dev20) | 14 / 20 | 20 / 20 (100.0%) | 70.0% | 70.0% |
| OpenHands (round C, dev20) | 10 / 20 | 20 / 20 (100.0%) | 50.0% | 50.0% |

### Failure categories

| Harness | Passed | Timeout | Rate limit | Setup error | Verifier fail | Other | Needs review | Passes with an agent error recorded |
|---|---|---|---|---|---|---|---|---|
| C0 | 15 | 3 | 1 | 0 | 0 | 0 | 1 | 1 |
| C1 | 14 | 2 | 0 | 0 | 2 | 0 | 2 | 1 |
| C2 | 14 | 4 | 0 | 0 | 2 | 0 | 0 | 0 |
| C3 | 13 | 4 | 1 | 0 | 1 | 0 | 1 | 0 |
| Terminus-2 (round C, dev20) | 14 | 2 | 3 | 0 | 1 | 0 | 0 | 1 |
| OpenHands (round C, dev20) | 10 | 3 | 2 | 0 | 3 | 0 | 2 | 0 |

### Cost and tokens

| Harness | Model requests | Accepted responses | HTTP 429 | Unknown-cost requests | Known cost (US$) | Total cost | Known input tokens | Known output tokens | Trials with complete token counts |
|---|---|---|---|---|---|---|---|---|---|
| C0 | 682 | 677 | 1 | 5 | 0.6814 | unknown | 29,171,391 | 774,976 | 16 / 20 |
| C1 | 607 | 607 | 0 | 0 | 0.4060 | known | 15,563,189 | 650,224 | 20 / 20 |
| C2 | 561 | 557 | 0 | 4 | 0.6234 | unknown | 29,283,440 | 763,021 | 16 / 20 |
| C3 | 554 | 548 | 2 | 6 | 1.0087 | unknown | 16,198,432 | 580,144 | 16 / 20 |
| Terminus-2 (round C, dev20) | 461 | 277 | 181 | 184 | 0.2282 | unknown | 6,216,959 | 530,669 | 8 / 20 |
| OpenHands (round C, dev20) | 582 | 390 | 188 | 192 | 0.2207 | unknown | 6,829,365 | 432,916 | 10 / 20 |

### Agent runtime

| Harness | Trials with measured agent time | Total agent hours | Median agent seconds |
|---|---|---|---|
| C0 | 20 / 20 | 4.8 | 332 |
| C1 | 20 / 20 | 3.5 | 372 |
| C2 | 20 / 20 | 3.8 | 299 |
| C3 | 20 / 20 | 4.3 | 345 |
| Terminus-2 (round C, dev20) | 20 / 20 | 5.4 | 721 |
| OpenHands (round C, dev20) | 20 / 20 | 4.9 | 460 |

### C0-NC's separate dev20 validation run (not in the tables above)

Before its final 89-task run, C0-NC ran once on the same 20 dev tasks as a
validation. It scored **11/20**
(`stage2/results/custom-no-cutoff-20260928/c0-nc/trials.csv`). The same 20 tasks
scored **15/20** inside the final run. This package does not load the
validation file.

The two runs' recorded conditions were **not identical**, so the 4-task gap is
not reported as single-run variance.

**The same in both** (32 identical fields in the two `credit-policy.json` files,
plus both `trials.csv` files):
- model, endpoint and sampling;
- harness version 0.5.0 and its execution contract;
- retry policy, with no caps;
- each task's official limits;
- task order;
- the agent's prompt, graph and tool code.

**What differed:**
1. **Source commit:** `06d94f7` for validation vs `fb2d5cc` for the final
   (`launch.json`, `source_commit`). Among existing files, only
   `stage2/scored_trial.py` changed (admission plumbing). The final added new
   admission, policy and gateway modules (`stage2/no_cutoff_final_*.py`).
2. **Gateway container image:** different digests (`qualification.json`,
   `gateway_image`). The final image added a new gateway session wrapper around
   the same retry logic.
3. **Frozen candidate file:** different lineage hashes (`lineage.json`,
   `candidate_file_sha256`). They hash two different private files that are not
   committed, so whether the difference affects behaviour is unconfirmed.
4. **Time:** validation ran 27 Sep 21:17 – 28 Sep 02:43 UTC; the final's dev20
   tasks ran 28 Sep 03:38 – 08:01 UTC. Rate limiting was light in both
   (3 vs 1 HTTP 429s).

None of these touches the model, the limits or the agent logic, but their effect
on behaviour is unconfirmed. The 11/20 is a caution against reading any single
dev20 score precisely.

## Caveats

1. **Single runs.** Every harness ran each task once, at temperature 1. The
   McNemar tests and bootstrap intervals treat the tasks as the only source of
   variation. They ignore run-to-run randomness, so they understate the true
   uncertainty.
2. **Different times, different conditions.**
   - The baselines ran from 22 to 25 September 2026 (UTC).
   - C0-NC ran from 28 to 29 September, days later, as a separate experiment.
   - Provider load and rate limiting differed between the runs: thousands of
     HTTP 429s in each, which use task time. Rate-limit waits are also included
     in the runtime figures, so those are not a speed comparison.
3. **The matched comparison has not been done.** Stage 2's protocol requires 267
   fresh, matched trials before claiming success: 89 tasks each for the frozen
   finalist and both baselines. These results are not that comparison. Nothing
   here formally establishes a win.
4. **Not all 89 tasks are held out.**
   - C0, the parent of C0-NC, was chosen as the best of C0–C3 on the dev20 tasks,
     and those 20 tasks are part of the 89. The 69-task split above is the
     cleaner view.
   - C0-NC is a later revision of C0 (execution cutoffs removed). Its dev20
     score is not C0's.
5. **dev20 is tiny.** Differences of one or two tasks among C0–C3 are within
   noise. Stage 2 itself states that its variant comparison does not establish
   a causal effect.
6. **Two comparisons.** Two McNemar tests are reported without a
   multiple-comparison correction. Neither is significant at 0.05 either way.
7. **Costs are incomplete.** Known costs are response-reported, not receipts.
   Hundreds of requests per run have unknown cost; most are HTTP 429
   rejections. No total cost is known.
8. **Failure categories are records, not causes.** In particular, "rate limit"
   marks a recorded 429, not proof that rate limiting caused the failure.
