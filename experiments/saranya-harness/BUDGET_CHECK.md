# Budget check, 1 October 2026

Prepared without any API call, from committed Stage 2 results only. The figures
are estimates for planning, not billing records. Stage 2 never reconciled its
costs against independent provider receipts.

## Sources

- Per-trial data: `stage2/results/baseline-corrected-20260923/trials.csv`
  (round C, both baselines), `stage2/results/custom-portable-20260926/c0/trials.csv`
  (C0 dev20), and `stage2/results/custom-no-cutoff-final-20260928/c0-nc/trials.csv`
  (C0-NC final89).
- Price: `stage2/model_protocol.py`, `model_info` for DeepSeek V4 Flash on the
  pinned DeepInfra FP8 endpoint: **US$0.06 per million input tokens, US$0.18 per
  million output tokens**, US$0.015 per million cache-read tokens.
- The CSVs record no cached-token counts, only total input and output tokens.

## 1. What each run recorded

| Run | Requests | Known cost (US$) | Requests with unknown cost | Known input tokens | Known output tokens |
|---|---:|---:|---|---:|---:|
| Terminus-2 round C (89 tasks) | 2,007 | 0.9199 | 668 (645 are HTTP 429) | 24,166,772 | 2,200,743 |
| OpenHands round C (89 tasks) | 3,183 | 1.4585 | 773 (749 are HTTP 429) | 52,136,188 | 2,363,608 |
| C0 dev20 (20 tasks) | 682 | 0.6814 | 5 (1 is HTTP 429) | 29,171,391 | 774,976 |
| C0-NC final89 (89 tasks) | 3,657 | 1.7140 | 799 (774 are HTTP 429) | 68,277,661 | 2,300,682 |

Token totals cover only requests with recorded usage. Requests with unknown
cost have no token counts.

Two patterns drive the estimates:

1. **Almost all unknown-cost requests are rate-limit rejections.** Only 23, 24,
   4 and 25 respectively are anything else: transport errors or requests
   interrupted at the deadline.
2. **Known costs are well below uncached list price.** Pricing the recorded
   tokens at list price gives US$1.85, US$3.55, US$1.89 and US$4.51, so the
   known costs are 50%, 41%, 36% and 38% of list. The difference is most likely
   prompt-cache discounts, which a fresh run may or may not get to the same degree.

## 2. Estimated full cost of each run

Three estimates per run:

- **Low:** known cost only. Assumes no unknown-cost request was billed.
- **Middle:** known cost, plus each unknown-cost request that was *not* a 429 at
  the run's average known cost per request. 429 rejections are treated as
  unbilled because they produce no generation. This is an assumption, not
  verified against receipts.
- **High:** all recorded tokens at uncached list price, plus each non-429
  unknown-cost request at the run's average list-price cost per request.

| Run | Low | Middle | High |
|---|---:|---:|---:|
| Terminus-2 round C | 0.92 | 0.94 | 1.88 |
| OpenHands round C | 1.46 | 1.47 | 3.59 |
| C0 dev20 | 0.68 | 0.69 | 1.90 |
| C0-NC final89 | 1.71 | 1.73 | 4.55 |

### Why the high figure is roughly double the known cost

Run-to-run usage varies a lot at temperature 1. Committed data gives two
direct comparisons of the same tasks run twice:

- **Timeout diagnostic** (`stage2/results/timeout-diagnostic-20260925/`): the
  30 rate-limited failures were rerun with fewer rate limits. The reruns cost
  **2.05×** the originals for Terminus-2 (11 tasks) and **2.18×** for OpenHands
  (19 tasks), because the agents kept working instead of stalling.
- **C0-NC on the 20 dev tasks** cost **0.63×** C0's run on the same tasks.

The high estimate is 2.0–2.8× each run's known cost. That covers both losing
the cache discount and the roughly 2× usage growth seen in the reruns. It does
not cover both happening at once.

## 3. Planned matched comparison (89 tasks × 3 harnesses, fresh trials)

Proxies: Terminus-2 and OpenHands round C, and C0-NC final89 for the custom
finalist.

| Estimate | US$ |
|---|---:|
| Low | 4.09 |
| Middle | 4.14 |
| High | 10.02 |

The low and middle figures are close because nearly all unknown-cost requests
are 429s, assumed unbilled. Fewer rate limits would raise usage instead: see
the 2× rerun result above. Karthik's recovery of the 3 setup-only C0-NC tasks
is not included.

## 4. My minimal harness, 20 dev tasks

Proxy: C0's dev20 usage. My harness's own usage is untested and could differ
either way.

| Estimate | US$ | Reasoning |
|---|---:|---|
| Low | 0.68 | C0's known cost |
| Middle | 0.69 | plus C0's 4 non-429 unknown-cost requests at its average known cost per request |
| High | 1.90 | C0's tokens at uncached list price: 29,171,391 × $0.06/M = $1.750, plus 774,976 × $0.18/M = $0.139, plus 4 requests × about $0.0028 |

This is the reasoning behind the earlier summary "C0 cost about $0.68 known, and
I estimate about $1.90 worst case". The high figure assumes C0's token volume
with no cache discount.

The harness's spending stop always allows for the worst case:
- the full 384k-token output allowance (about US$0.069) is reserved before every call;
- interrupted requests keep that whole reservation.

So its ledger will over-state spending compared with real billing. Cap the run
to the approved amount through `SARANYA_HARNESS_OVERALL_CAP_USD`.

## 5. Does it fit in US$13?

The remaining credit of US$13 is the figure you gave me. I have not checked the
account balance, because that would need an API call.

| Item | US$ |
|---|---:|
| Remaining credit | 13.00 |
| Matched comparison, high, plus 30% contingency (10.02 × 1.3) | −13.02 |
| My 20-task run, high | −1.90 |
| **Remaining** | **−1.92** |

**It does not fit. The plan is US$1.92 short.** The matched comparison's high
figure plus 30% contingency (US$13.02) alone already uses the whole US$13.

Other ways of counting:

- With my run at its middle figure (US$0.69) instead: still **US$0.71 short**.
- Without the contingency, the matched comparison's high figure plus my run's
  high figure is US$11.92, leaving US$1.08.
- At the matched comparison's middle figure plus my run's high figure, the plan
  needs US$6.04 (no contingency) or US$7.28 (contingency on the matched part),
  leaving US$6.96 or US$5.72.

The tight case is a fresh matched run that loses the cache discount or uses
about twice the tokens, which the reruns show is plausible.

### Options to discuss with Karthik (decisions, not recommendations of fact)

- Run my 20 tasks only after the matched comparison finishes, using whatever
  credit is actually left, with the ceiling set below that amount.
- Run my harness on a subset first (say 5 tasks, about US$0.10–0.50) to measure
  its real usage before committing to 20.
- Add credit. That is a spending decision, not mine to make.
