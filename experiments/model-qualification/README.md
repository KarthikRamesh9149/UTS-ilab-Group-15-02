# Retrospective model-qualification check: Terminus-2 with local models

**This is a retrospective check, done after Stage 2's model was chosen.** Stage 2
had already selected DeepSeek V4 Flash 0731 and run its full baselines with it. This
check asks, after the fact, how two free local 8B-class models do with the same
established harness, Terminus-2, on a few of the same tasks. It does not revisit or
validate the original selection, and it tests no custom harness.

By Saranya. Terminus-2 is Harbor's built-in agent, unmodified. The Stage 2
reference results and settings are Karthik Ramesh's work, read only from
`stage2/` (nothing there is changed).

## Results

**0 passes in 6 valid trials.** Granite 4.2 8B had 4 valid trials and Qwen3 8B had 2.
On the same four tasks, Stage 2's DeepSeek V4 Flash 0731 + Terminus-2 passed 3 of 4.
Every row from `results.csv` is shown, including the ones that are not valid.

| Task (agent limit) | DeepSeek V4 Flash, Stage 2 round C (Linux server) | Granite 4.2 8B (this Mac) | Qwen3 8B (this Mac) |
|---|---|---|---|
| video-processing (3,600 s) | 0 (1,399 s) | 0.0: 2 of 5 tests; agent timeout | **Not a result:** the verifier could not download its test tools, so the tests never ran (infrastructure) |
| constraints-scheduling (1,200 s) | **1** (136 s) | 0.0: 0 of 3 tests; agent timeout; one reply ran away for 19 min | 0.0: 0 of 3 tests; agent timeout; one reply ran away for 14 min |
| overfull-hbox (750 s) | **1** (566 s) | 0.0: **3 of 4 tests**; agent timeout | 0.0: **3 of 4 tests**; agent timeout |
| reshard-c4-data (3,600 s) | **1** (1,448 s) | 0.0: 0 of 1 tests; agent timeout | **Invalid:** the Mac slept mid-trial (agent time 20.8 h against a 1 h limit); 0.0 recorded but not counted |

Also in `results.csv`, and not counted:
- **the pilot:** Granite on video-processing with `top_p` 0.95; 0.0, 2 of 5 tests, agent timeout;
- **4 setup failures:** both models on openssl-selfsigned-cert and modernize-scientific-stack
  failed before any model call (see below).

Reward is Terminal-Bench's all-or-nothing score: 1 only if every test passes. The test
counts come from the verifier's pytest summary. The DeepSeek runtimes are agent seconds
from the committed Stage 2 records.

## Models

| Model | Ollama tag | Digest (sha256) | Size | Quantisation | Native context |
|---|---|---|---|---|---|
| IBM Granite 4.2 8B | `granite4.2:8b` | `f586c02fdecdf151b656207c339aa003997345774a41768bac1fd6d2fb85913b` | 5.35 GB (8.8B params) | Q4_K_M | 131,072 |
| Qwen3 8B | `qwen3:8b` | `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41` | 5.23 GB (8.2B params) | Q4_K_M | 40,960 |

- **Granite:** `granite4.2:8b` exists in the Ollama library, so no older Granite 4
  model was needed. The library also lists Granite 4.1 and the original Granite 4 family.
- **Qwen3:** `qwen3:8b`, as requested.
- **Serving:** both were served by Ollama 0.33.0 on the Mac with
  `OLLAMA_CONTEXT_LENGTH=16384`. Ollama reported both loaded at exactly 16,384 tokens,
  100% on the GPU.
- **Digests** are from Ollama's `/api/tags` and are also written into `results.csv`.

## How Terminus-2 calls the model

Terminus-2 runs inside the Harbor process on the host, not in the task container.
It calls the model through LiteLLM (`harbor/agents/terminus_2/terminus_2.py`,
`_init_llm`). It drives a `tmux` session inside the container only through
`environment.exec` (lines 378 and 450).

So the model is reached from the Mac at `http://127.0.0.1:11434/v1`, and Ollama
stays bound to localhost. `OLLAMA_HOST=0.0.0.0` and `host.docker.internal` were
not needed, and no container-to-Ollama connection test was needed either.

## Compatibility with thinking output

Both models are thinking-capable in Ollama. Before any trial, each was called
locally through LiteLLM's OpenAI-compatible route, the way Terminus-2 calls it.
The reply was then run through Terminus-2's own JSON parser
(`terminus_json_plain_parser.py`).

| Model | Effort | Reasoning returned separately | `<think>` in reply | Parse errors |
|---|---|---|---|---|
| granite4.2:8b | high | 1,304 characters | no | none (1 formatting warning Terminus-2 handles) |
| granite4.2:8b | low | 24 characters | no | none |
| qwen3:8b | high | 5,309 characters | no | none |
| qwen3:8b | low | 2,423 characters | no | none |

**No incompatibility was found.** Ollama returns thinking in a separate reasoning
field, so it never reaches Terminus-2's parser. The effort setting changes the
amount of thinking, so it takes effect.

## Settings: Stage 2 vs this check

Stage 2's Terminus-2 settings are in `stage2/native_agents.py:79–89` and
`stage2/retry_policy.py`. This check's are in `run_trial.sh`.

| Setting | Stage 2 Terminus-2 | This check | Same? |
|---|---|---|---|
| Harness | Terminus-2 via `NoRetryTerminus` (stock Terminus-2 with Harbor's agent-layer and adapter retries disabled) | stock `terminus-2` 2.0.0, Harbor 0.22.0 | **Differs**: Harbor's retries are on (local, so no cost) |
| Model | DeepSeek V4 Flash 0731 via OpenRouter → DeepInfra FP8 | Granite 4.2 8B / Qwen3 8B, Q4_K_M, Ollama | **Differs**: the point of the check |
| API route | `openai/…` through the Stage 2 gateway | `openai/<tag>` through Ollama's OpenAI-compatible API | Same type of route |
| Temperature | 1.0 | 1.0 | Same |
| top_p | 1.0 (enforced by the gateway) | 1.0 (sent per request); the **pilot used 0.95** (see below) | Same, except the pilot |
| top_k | not sent (provider default) | not sent: Qwen3 uses its Ollama default of 20; Granite uses Ollama's built-in 40 (confirmed in the Ollama log) | Not sent in either |
| Reasoning effort | `high`, sent as OpenRouter's `extra_body.reasoning.effort` | `high`, sent as Ollama's `extra_body.reasoning_effort` | Same level, provider's own field |
| Max output tokens | 384,000 | not sent; limited by the 16,384-token context | **Differs** |
| Context window | 1,048,576 (`model_info`) | 16,384 (`model_info` and Ollama) | **Differs**: Terminus-2 summarises far more often |
| Request timeout | agent timeout + 60 s | agent timeout + 60 s | Same |
| Turn limit | Terminus default (1,000,000) | Terminus default | Same |
| Parser, summarisation | defaults (JSON; proactive summarisation at 8,000) | defaults | Same |
| Task limits | official (agent, verifier, CPUs, memory) | official | Same |
| Task files | `terminal-bench-2-1` at `7131e43` | same revision; all 20 dev `task.toml` hashes match `stage2/input_manifest.json` | Same |
| Host | native x86-64 Linux server (Netcup) | Apple Silicon Mac, Docker Desktop, x86-64 images under Rosetta | **Differs** |

Without `model_info`, Terminus-2 assumes a 1,000,000-token context
(`harbor/llms/lite_llm.py:150–180`) and would never summarise before Ollama's
16,384-token window overflowed. Passing `model_info`, as Stage 2 did for DeepSeek,
makes it summarise in time. The pilot logs show summarisation happening.

## Pilot

Granite 4.2 8B on video-processing, run with the same settings except `top_p`. The
pilot ran before `top_p = 1.0` was added, so it used Ollama's default of 0.95. It is
reported separately and not counted in the comparison. Granite's video-processing
trial was rerun with the corrected setting.

## Task selection

- **video-processing** is kept from the pilot stage. Both models ran it with the final
  settings.
- **The other tasks follow a fixed rule:**
  - take the dev20 tasks (`development_ids` in `stage2/input_manifest.json`, in their
    existing hash order) where **Terminus-2 + DeepSeek passed** in Stage 2 round C
    (`stage2/results/baseline-corrected-20260923/trials.csv`);
  - exclude the tasks whose reference solutions fail on a Mac under Rosetta
    (install-windows-3.11, qemu-alpine-ssh, qemu-startup);
  - exclude tasks with an official agent time limit over 1 hour (3,600 s);
  - take the first three.

  This gives **constraints-scheduling (1,200 s), overfull-hbox (750 s) and
  reshard-c4-data (3,600 s)**.
- **The time-limit exclusion was added on 4 October, before any small-model results on
  these tasks, for practical runtime reasons.** Among DeepSeek's passes it excludes only
  **build-pov-ray**, whose 12,000-second limit would allow up to about 6 h 40 min for
  two trials. Without it, the rule would have selected build-pov-ray, constraints-scheduling
  and overfull-hbox.
- **Each selected task must pass Harbor's Oracle agent on this Mac first.** If one fails
  for infrastructure reasons, the next eligible task in hash order is taken, and the
  reason is recorded here.
- **This rule favours DeepSeek by design.** It picks only tasks DeepSeek solved, so the
  local models can at best match it on those tasks. The rule exists to ask whether the
  local models can do what the chosen model did, not to compare them fairly.
- **An earlier selection was abandoned:** openssl-selfsigned-cert and
  modernize-scientific-stack. Their four trials failed in setup (below); they are
  reported as infrastructure failures, not results.

## Observed model behaviour

- **Runaway replies.** On constraints-scheduling, both models produced one reply that
  never finished:
  - **Granite:** its second model request ran **19 min 8 s** and generated 10,897 tokens
    without ending, nearly filling the 16,384-token context;
  - **Qwen3:** its fourth request ran **14 min 6 s**.

  In both cases the task's time limit cut the request off (Ollama logged HTTP 500 when the
  client disconnected). On overfull-hbox, Granite's fourth request took 10 minutes but did
  finish. Neither this check nor Stage 2 caps reply length (Stage 2's cap was 384,000
  tokens). So with a slow local model, a single runaway reply can use up a task's whole
  time limit.
- **Partial progress on overfull-hbox.** Both models passed 3 of the task's 4 tests but
  scored 0, because the reward needs all tests to pass.
- **Almost every valid trial hit the official time limit.** That fits the local generation
  speed (below) as much as the models' ability.

## Infrastructure failures on 4 October, about 05:24–05:28 AEDT (not model results)

- **What failed.** Granite and Qwen3 each failed to start on openssl-selfsigned-cert and
  modernize-scientific-stack, each in about 49 seconds, with
  `RuntimeError: Failed to start tmux session. Error: None`. No model call was made; the
  trials' agent log folders are empty.
- **Why the message is empty.** Terminus-2 reports the command's `stderr`
  (`harbor/agents/terminus_2/tmux_session.py:498–505`), but Harbor's Docker backend
  merges stderr into stdout, so the real message was not kept.
- **None of the task images include tmux.** Terminus-2 installs it at setup with
  `apt-get update && apt-get install -y tmux asciinema` (`tmux_session.py:122–175`,
  120-second limit). That worked in both video-processing trials.
- **The failure does not reproduce.** In a fresh container from the openssl image, run as
  root with the task's CPU and memory limits, the same install finished in 13 seconds
  (exit 0) and the same `tmux new-session` command started (exit 0).
- **Ruled out:**
  - the task network policy: all three tasks have identical environment settings,
    including `allow_internet = true`;
  - the image user: root in all three;
  - the Debian release: Debian 12 in all three;
  - Mac sleep: none in the power log.
- **A verifier failure in the same minutes.** Qwen3's video-processing verifier ran at
  about the same time and could not download `uv` from GitHub ("failed to download …
  uv-x86_64-unknown-linux-gnu.tar.gz"), so its tests never ran. Network access from the
  containers was probably interrupted briefly then, which would also explain the four
  tmux installs failing.
- **The cause is unconfirmed.** A DNS check on the host afterwards succeeded, and the
  install worked when reproduced.

## Host and validity

- **Mac, not the Stage 2 server.**
  - x86-64 task images run under Rosetta here. Some tasks cannot run on this Mac at
    all (the Rosetta syscall-282 crash on install-windows-3.11 and qemu-alpine-ssh;
    see `experiments/saranya-harness/oracle/ORACLE_MAC_DEV20.md` on branch
    `saranya-minimal-harness`).
  - Every task used here was first confirmed runnable on this Mac with Harbor's
    Oracle agent (official solutions, no model). All scored 1.0:
    - video-processing in Oracle run r1;
    - openssl-selfsigned-cert, modernize-scientific-stack and constraints-scheduling in
      `oracle-candidates-r2`;
    - overfull-hbox and reshard-c4-data in `oracle-candidates-r3`.
- **Battery and sleep during this run.**
  - All trials ran under `caffeinate -is`, but the Mac moved between mains power and
    battery during the run. On battery, `-s` does not prevent system sleep.
  - At 17:05 AEDT on 4 October the lid was closed (`Clamshell Sleep`, on battery),
    47 minutes into Qwen3's reshard-c4-data trial. Sleep pauses Harbor's timer, so that
    trial ran 20.8 hours and is invalid.
  - `collect_results.py` checks every trial against the macOS power log (`pmset -g log`).
    No other counted trial overlaps a sleep or wake event.
  - The batch script checks the power log after each trial and stops on sleep. That check
    first missed its own stop message because the message spanned several lines; this is
    fixed in `run_check.sh`. The trial was the last one, so no further trial ran.
- **Speed.** Generation ran at about 15 output tokens per second for Granite, slowing to
  about 9.6 late in long replies (Ollama log). Part of the run was on battery, which may
  throttle the GPU; the two effects cannot be separated. Either way this is far slower
  than a hosted model, so trials hit the official time limit much more often.
- **Small sample.**
  - Four tasks, one run per model per task: 4 valid trials for Granite and 2 for Qwen3.
  - These are observations, not estimates of either model's general ability, and not a
    comparison that could have changed Stage 2's choice.
  - The task rule favours DeepSeek by design (see Task selection).

## Files

- `run_trial.sh`: one Terminus-2 trial with a local model and the settings above.
- `run_check.sh`: step 5, each model once per task, one trial at a time. A trial that
  fails before any model call is replaced once, and both attempts are kept. The batch
  stops on a repeated pre-model failure, on sleep, on DNS failure, or on low battery.
- `collect_results.py`: builds `results.csv` from Harbor's trial records. It adds model
  digests from Ollama and labels each trial's validity (pilot; invalid because the Mac
  slept; infrastructure because setup failed or the verifier's tests did not run; or
  valid). It also appends Stage 2's committed DeepSeek + Terminus-2 rows for the tasks
  with a valid trial.
- `results.csv`: one row per trial (13 local and 4 reference). Harbor job directories
  and logs are not committed; the raw job logs are archived locally.
