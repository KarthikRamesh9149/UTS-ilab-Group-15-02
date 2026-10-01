# Saranya minimal harness (v0.2.0)

A small, single-loop Harbor agent for Terminal-Bench 2.1, by Saranya. It
succeeds my v0.1.0 (`results/saranya-custom-harness/custom_agent/my_gemini_agent.py`
on the `saranya-exploration` branch). The loop is the same: the model gives one
shell command, it runs in the task container, the output goes back to the model,
repeat until the model replies `DONE`.

The aim is a fair development comparison with Stage 2's C0 custom harness
(15/20 on the fixed dev20 tasks), so the model and its limits match C0.

## What is mine and what is adapted

- All code in this folder is mine.
- The model, provider-pinning, sampling and price values are copied from Karthik
  Ramesh's Stage 2 code. Each source file is cited in `saranya_harness/openrouter.py`.
  `tests/test_openrouter.py` imports `stage2/gateway_policy.py` and
  `stage2/retry_policy.py` read-only and checks that the request this harness sends
  matches Stage 2's.
- The list of tasks whose reference solutions fail on a Mac comes from Karthik's
  `stage2/rosetta_requalification.md`.
- The dev20 task list is `development_ids` in `stage2/input_manifest.json`.
- Nothing in `stage2/` is modified.

## Matched settings

| Setting | Value | Matches |
|---|---|---|
| Model | `deepseek/deepseek-v4-flash-0731` via OpenRouter | `stage2/gateway_policy.py` |
| Provider | only/order `deepinfra/fp8`, no fallbacks, `require_parameters`, fp8; no price filter | `gateway_policy.py`, `credit_only_gateway.py` |
| Sampling | temperature 1.0, top_p 1.0, no seed, reasoning effort high | `retry_policy.py`, `model_protocol.py` |
| Output allowance | 384,000 tokens | `retry_policy.py` |
| Model-call ceiling | none | C0 at `004943b`: `max_model_calls=None` in `corrected_custom_agent.py` |
| Time limit | the official task deadline (Harbor cancels the agent) | C0 launch record: official limits unchanged |
| Per-command timeout | 3,600 s | C0's maximum in `custom_jobs.py` at `004943b` |
| Retries | 429/502/503 and connection failures, no count cap, inside the deadline | `retry_policy.py` (`undelivered-transient-only-within-task-deadline`) |

I confirmed C0's 15/20 setting from the source at its launch commit `004943b`
(`stage2/results/custom-portable-20260926/launch.json`): no model-call ceiling,
official deadline. C0 also had harness-specific limits that this harness does not
copy, because it has no equivalent mechanism: at most two completion-repair cycles,
and a background-job quota.

## Differences from C0 that matter for interpretation

- **Design.** C0 is a Deep Agents/LangGraph graph with file and shell tools and an
  explicit completion protocol. This harness is one plain command loop.
- **Gateway.** C0's requests went through Karthik's guarded gateway on the Netcup
  server. This harness calls OpenRouter directly with the same request body.
- **Host.** C0 ran on native x86-64 Linux. Development here runs on an Apple Silicon
  Mac, where x86-64 task images run under Rosetta. Some tasks fail there for host
  reasons C0 never faced, so Mac scores are development evidence, not a matched
  comparison.
- **One run each.** Like the Stage 2 results, a single run per task is a noisy
  observation, not proof of an improvement.

## Spending safety stop

Because there is no call ceiling, every model call is checked first against:

- **a per-trial cap**, default US$1.50. This is about four times C0's highest
  per-trial known cost (US$0.3785 on video-processing). Set it with
  `--ak per_trial_cap_usd=...`.
- **an overall cap** shared by all trials writing to the same ledger. It has no
  default. If `SARANYA_HARNESS_OVERALL_CAP_USD` is unset, the agent makes **no
  model call** and records `stop_reason: no_spending_approval`.

Before each call the guard reserves the worst case: the full 384k-token output
plus an over-estimate of the prompt. Afterwards it records the provider-reported
cost, or else an uncached list-price estimate, or else the whole reservation. A
request cancelled at the deadline keeps its whole reservation. Every request and
every triggered stop goes to the JSON-lines ledger in `SARANYA_HARNESS_LEDGER`,
to the trial's `agent/saranya-trajectory.jsonl`, to the trial metadata, and to a
logged warning.

## Infrastructure classification

`python -m saranya_harness.summarize <job_dir> <out.csv>` reads each trial's
`result.json` and assigns one category per trial:

| Category | Meaning |
|---|---|
| `passed` | verifier reward above zero |
| `not_attempted` | no spending approval, so the model was never called |
| `infrastructure` | the Mac reference solution also fails (install-windows-3.11, qemu-alpine-ssh, qemu-startup: Rosetta syscall 282); or command output contained an explicit Rosetta error; or Harbor's environment/setup failed |
| `budget_stop` | the spending safety stop ended the trial |
| `infrastructure_review` | an unrecognised exception or a verifier timeout; a person must decide |
| `model_failure` | everything else with reward 0, including agent timeouts |

The rules are conservative, so failures are not blamed on the host to flatter
the harness:
- "exec format error" can be the agent's own mistake, so it is not a signature.
- build-pov-ray's Mac reference failed on an HTTP 403 from its own download URL,
  not on Rosetta, and C0 passed it, so it is not automatically infrastructure.

## Running

Use your own virtualenv with Harbor 0.22.0 and run from this folder.

Offline tests (no network, no spending):

```bash
python -B -m unittest discover -s tests
```

Zero-spend Harbor check: no cap is set, so the model is never called.

```bash
PYTHONPATH="$PWD" harbor run -d terminal-bench/terminal-bench-2-1 \
  -a saranya_harness.agent:SaranyaMinimalAgent \
  -i terminal-bench/openssl-selfsigned-cert -n 1 -k 1 -o ~/harbor-jobs --yes
```

Paid run: only with an explicitly approved ceiling. Keep the key in the
environment and the ledger outside the repository.

```bash
export OPENROUTER_API_KEY=...                      # never commit
export SARANYA_HARNESS_OVERALL_CAP_USD=3.00        # the approved ceiling
export SARANYA_HARNESS_LEDGER=~/harbor-jobs/saranya-ledger.jsonl
PYTHONPATH="$PWD" harbor run -d terminal-bench/terminal-bench-2-1 \
  -a saranya_harness.agent:SaranyaMinimalAgent -i terminal-bench/<task> \
  -n 1 -k 1 -o ~/harbor-jobs --yes
```

Run trials one at a time (`-n 1`), as Stage 2 did. Commit only the curated CSV
from `summarize`, never the job directories or the trajectory logs.

## Status

- 33 offline tests pass.
- A zero-spend Harbor trial on openssl-selfsigned-cert (Mac, Docker Desktop)
  loaded the agent, made no model call, ran the verifier (reward 0) and recorded
  the metadata. The summariser classified it as `not_attempted`.
- No paid model call has been made. There is no benchmark score yet.
