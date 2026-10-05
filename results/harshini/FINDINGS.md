# Findings — Deep Agents harness and same-host experiments

**Scope.** Everything in this file was built, run and analysed on this branch
(`harshini-trial-run`): the Deep Agents harness, the pinned Terminus-2 runner, every
laptop run, the repeat study and the analysis scripts. Reference numbers come from the
project's Stage 2 runs on the Netcup server, read from committed CSVs on `main`
(extracted to [`reference/stage2-reference-89.csv`](reference/stage2-reference-89.csv)
by [`compare_reference.py`](compare_reference.py)).

All runs use the same model and route: DeepSeek V4 Flash 0731 on DeepInfra FP8 via
OpenRouter, temperature 1.0, reasoning effort high, 384k max output tokens. Every
result is one run per task unless stated. Last updated 5 October 2026; the repeat
study is still running.

## Summary

1. The Deep Agents harness (0.1.3) scored **10/20** on the dev-20 tasks on the Windows
   laptop, for **US$0.40** in total.
2. **The host matters.** Terminus-2 with identical settings passed **9 of the first 16**
   dev-20 tasks on the laptop, against **12 of the same 16** on the server. Both `qemu`
   tasks fail for both harnesses on the laptop and passed for Terminus-2 on the server.
3. On the laptop the two harnesses are close so far: on those 16 tasks the Deep Agents
   harness passed **8** and Terminus-2 **9**.
4. In the Stage 2 server runs (89 tasks), the three harnesses solve **different tasks**:
   **62** tasks are solved by at least one harness, against **52** for the best single
   one, and **27** are solved by none.
5. Harness bugs found on real tasks, not in offline tests, were the main obstacle early
   on: an empty model reply ending a run, images without `python3`, and provider
   overload. Each is fixed and covered by the offline test (10/10 checks).

## 1. Deep Agents harness on dev-20 (run 1 of the repeat study)

[`deepagents/dev20-v0.1.3.csv`](deepagents/dev20-v0.1.3.csv)

| Outcome | Tasks |
|---|---:|
| Passed | 10 (9 finished by the model, 1 at the deadline) |
| Failed at the time limit | 7 |
| Failed after the model declared it was done | 3 |

- Median agent time per pass: **5.9 min**; total agent time: **5.9 h**; cost: **US$0.40**.
- **Near-miss, `build-pov-ray`:** the model downloaded, built and ran POV-Ray 2.2 and
  rendered the test scene (2 of 3 checks passed). It unpacked the archives into
  subfolders, so the expected `/app/povray-2.2/file_id.diz` was missing. A completion
  check on the required file layout is the obvious next lever.
- **Time limits dominate:** 7 of 10 failures ran out of time, the same pattern as the
  Stage 2 server runs (timeouts are the largest failure group for all three harnesses).

## 2. Same host vs. server: the host effect

[`deepagents/dev20-terminus2-r1.csv`](deepagents/dev20-terminus2-r1.csv) (in progress) ·
chart: [`dev20-tasks.png`](dev20-tasks.png)

Terminus-2 here is Harbor's own agent with only the connection pinned
([`harness/terminus_pinned.py`](../../experiments/harshini-deepagents/harness/terminus_pinned.py)).

| Tasks 1–16 of dev-20 | Passed |
|---|---:|
| Terminus-2, server (Stage 2) | 12 |
| Terminus-2, laptop | 9 |
| Deep Agents 0.1.3, laptop | 8 |

- **`qemu-alpine-ssh` and `qemu-startup`** fail for both harnesses on the laptop. Both
  boot a virtual machine inside the task container; Terminus-2 passed both on the server.
  This points to the host, not the harness. A Windows Oracle run of these two tasks would
  confirm it.
- Terminus-2 also lost `adaptive-rejection-sampler` and `overfull-hbox` on the laptop and
  gained `mailman` — swings in both directions, consistent with run-to-run variation.
- **Implication:** server scores and laptop scores should not be compared directly. The
  fair comparison for this harness is Terminus-2 on the same laptop.

![dev-20 per task](dev20-tasks.png)

## 3. Repeat study (in progress)

[`repeat_study.py`](../../experiments/harshini-deepagents/repeat_study.py) runs three
dev-20 runs of each harness on the laptop, alternating between them, with the harness
frozen at 0.1.3. Every published score for this model is a single run at temperature
1.0, so the size of the run-to-run spread is unknown; this study measures it. Results
will be added here as runs finish (`dev20-v0.1.3-r2/-r3`, `dev20-terminus2-r2/-r3`).

## 4. Stage 2 server results: where the harnesses differ

From [`reference/stage2-reference-89.csv`](reference/stage2-reference-89.csv), 89 tasks,
one run each.

| | Terminus-2 | OpenHands | Stage 2 custom (C0-NC) |
|---|---:|---:|---:|
| Passed (of 89) | 52 | 44 | 50 |
| Tasks only this harness solved | 4 | 2 | 5 |
| Median agent minutes per pass | 8.5 | 6.6 | 5.6 |
| Median output tokens per pass | 17,260 | 12,792 | 10,414 |
| Known input tokens (all tasks) | 24.2M | 52.1M | 68.3M |
| Known cost (all tasks) | US$0.92 | US$1.46 | US$1.71 |

- **Different harnesses win different tasks.** Picking the right harness per task would
  solve 62/89 (70%) against 52/89 for the best single harness. Tasks solved only by
  C0-NC: `hf-model-inference`, `mailman`, `mteb-leaderboard`, `polyglot-rust-c`,
  `regex-chess`. Only by Terminus-2: `circuit-fibsqrt`, `pytorch-model-recovery`,
  `qemu-alpine-ssh`, `schemelike-metacircular-eval`.
- **27 tasks are solved by no harness** — a ceiling that harness changes alone have not
  moved.
- **Trade-off, not a win:** C0-NC finishes its passes faster with fewer output tokens,
  but sends about 3× Terminus-2's input tokens and has the highest known cost. Agent
  time includes waits on rate-limited requests, so it is not a clean speed measure, and
  costs are incomplete (hundreds of requests per run have no recorded cost).
- The score differences (52 vs 50 vs 44) are within single-run noise; the paired
  statistical tests are in the Stage 2 analysis on `main`
  (`experiments/saranya-analysis/`).

## 5. Harness engineering findings

Found on real tasks and fixed (see the
[harness changelog](../../experiments/harshini-deepagents/CHANGELOG.md)):

| Finding | Effect before the fix | Fix |
|---|---|---|
| Graders run in a fresh environment | A check script used a pip-installed package the grader lacked (`openssl-selfsigned-cert` 5/6) | Prompt rule: deliverables use only preinstalled tools (0.1.1) |
| Some task images have no `python3` | Deep Agents' file tools failed on the R image | Shell-based write preflight; Python-backed tools hidden (0.1.2) |
| The model can return an empty reply | `build-pov-ray` ended at 14 of 200 minutes | Nudge to continue, up to 3 times (0.1.2) |
| Provider overload (HTTP 429, `engine_overloaded`) | Three tasks ended with no verifier result | Deadline-bounded retry with backoff, no count cap (0.1.3) |

## 6. Infrastructure findings

- **Terminus-2 runs on Windows with Harbor 0.22** when the OpenRouter key and provider
  route are passed in the agent's LLM settings (`terminus_pinned.py`); the one-task probe
  passed with no authentication errors.
- **Laptop sleep stops runs.** The run launchers now hold a Windows "system required"
  request for their lifetime.
- **CETUS (UTS HPC) cannot run Harbor** (no Docker; Stage 2 work, see the
  [results README](README.md)), so the laptop is the run host for this branch.

## Open questions

1. How large is the run-to-run spread on dev-20 (repeat study)?
2. How much of the laptop–server gap is the host? (Windows Oracle on the `qemu` tasks.)
3. Does a single change — a file-layout completion check — recover near-misses like
   `build-pov-ray` without losing other tasks?
