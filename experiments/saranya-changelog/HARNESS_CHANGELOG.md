# Custom harness changelog

How the team's custom Terminal-Bench 2.1 harness evolved, from Stage 1 to the
Stage 2 finalist, reconstructed from committed code, configs, commits and
results only.

**Authorship.** All harness code and runs described here are Karthik Ramesh's
work: every commit cited below is his, under `Karthik Ramesh` or
`KarthikRamesh9149`. This document was compiled by Saranya, who only documents
it. Anything the repository does not confirm is marked **unconfirmed**.

Paths are relative to the repository root. Short hashes are commits on
`origin/main` unless stated otherwise. "Dev20" means the fixed 20 development
tasks listed in `stage2/input_manifest.json` (`development_ids`).

## Summary

| Version | Change | Parent | Score | Decision |
|---|---|---|---|---|
| Stage 1 `uts-qwen-harness` 2.2.0 | JSON-action loop with phases, evidence gate and command guards | — | 0/20 valid (3B), 0/21 (7B) on a 21-task subset | Preserved; Stage 2 started a new harness family |
| Stage 2 0.1.0 | First Deep Agents/LangGraph adapter | — | No scored result | Superseded |
| Stage 2 0.2.0 (C0) | Adapted for the corrected baseline protocol | — | Stopped after 4 attempts; no score | Stopped for compatibility repairs |
| 0.3.0 C0 | Control: file/shell tools, explicit completion | — | **15/20** dev20 | Selected (best of C0–C3) |
| 0.3.0 C1 | + planning instruction | C0 (by protocol; no declared parent) | 14/20 | Not selected as C2's parent |
| 0.3.0 C2 | + requirement-based completion checks | C0 | 14/20 | Not selected |
| 0.4.1 C3 | + remaining-time reminders; three execution cutoffs removed | C0 | 13/20 | Not selected |
| 0.5.0 C0-NC | C0 with the three cutoffs removed + capture-transport fix | C0 | 11/20 validation; **50/89** final (35/69 held out) | Ran as finalist under a recorded decision, not by beating C0 |

## Stage 1: UTS Qwen custom harness 2.2.0

**Code.**
- `scripts/custom_harness.py`, added in `259105c` (31 Aug 2026) as version 1.0.0.
- Raised directly to 2.2.0 in `ac4ee5b` (31 Aug 2026), the version string at
  `scripts/custom_harness.py:79`.
- No 2.0 or 2.1 appears in the history. What changed between 1.0.0 and 2.2.0
  beyond the diff of `ac4ee5b` is **unconfirmed**.

**Design** (`scripts/custom_harness.py`):
- **Strict JSON action contract.** Each turn the model returns
  `{"analysis", "phase", "command", "done"}` (line 39), parsed by
  `parse_action` (line 86). Requests use `response_format={"type": "json_object"}` (line 192).
- **Phase-aware prompting.** The phases are inspect, edit, test and finish
  (lines 39 and 219), under a DISCOVER / IMPLEMENT / VERIFY / FINISH system
  prompt (lines 20–).
- **Evidence gate.** Finishing is denied until there has been a successful edit
  and a successful test command (lines 245–253).
- **Command guards.**
  - Destructive commands are refused through `command_is_safe` (line 112).
  - A command is rejected on its third repeat (lines 257–270).
  - An executable-missing error triggers a forced-recovery instruction
    (lines 306–313).
- **Exact artifact check.** After an edit it confirms the requested path is a
  regular file, not a directory (lines 277–288).
- **Rolling context** with a command-status summary
  (`configs/custom_harness_local.yaml`: `context_policy`).
- **Settings** (`configs/custom_harness_local.yaml`):
  - temperature 0, 32,768-token context;
  - 25 steps, 800 output tokens per step;
  - 120-second command timeout;
  - local Ollama `qwen2.5-coder:3b` and 7b.

**Results** (`results/progress_smoke_20260831_133343/summary.md`, published in `9739fa7`):

| Model | Valid / intended | Passed |
|---|---|---|
| qwen2.5-coder:3b | 20 / 21 | 0 |
| qwen2.5-coder:7b | 21 / 21 | 0 |

One 3B trial hit the 120-second command limit before verification. It is kept
as an invalid, non-infrastructure outcome. Mini-SWE-Agent and OpenHands also
scored 0 under both models, so the run could not separate harnesses (`README.md`,
Stage 1 section).

**Why Stage 2 rebuilt it.** The Stage 2 plan
(`docs/superpowers/plans/2026-09-14-stage2-20-task-study.md`) records the decisions:
- line 24: "New custom family: UTS Harness v3; preserve v2.2.0";
- line 41: "Reuse lessons and parser concepts, not the old matrix identity or
  runtime defaults";
- line 107: "Deep Agents supplies the graph foundation".

It also records that Stage 1 had zero passes, and that Stage 2 changes several
factors at once, so no Stage 1 → Stage 2 gain can be attributed to the harness
alone (line 43). **Unconfirmed:** the repository does not state why Deep
Agents/LangGraph was chosen over extending 2.2.0.

## Stage 2 before C0's score: 0.1.0 and 0.2.0

- **0.1.0.** `stage2/custom_harbor_agent.py:28` (added in `8f48ca7`, 16 Sep), with
  - the Deep Agents container backend `stage2/custom_backend.py` (`4514781`);
  - the bounded controller `stage2/custom_runner.py` and
    `stage2/custom_control.py` (`444ec59`).

  No scored dev20 result exists for 0.1.0. Its role was integration and
  qualification work. Which probe files exercised it is **unconfirmed**: the
  `stage2/native_live_custom_*.json` probe records carry no version field.
- **0.2.0.** `stage2/corrected_custom_agent.py:32` (added in `7582828`, 26 Sep),
  adapted to the corrected baseline protocol. Its C0 run stopped after four
  attempts for compatibility repairs, with no 20-task score
  (`stage2/results/custom-development-20260926/README.md`). The recorded problems:
  - a file tool sent image content to the text-only gateway;
  - one task image had no Python;
  - a command-execution `RuntimeError`;
  - an interrupted setup.

  The four attempts are retained and were not replayed.
- **0.2.0 → 0.3.0.** The changes were
  - a pinned Python fallback for images without Python;
  - text-only handling of file attachments;
  - more reliable output capture;
  - better cancellation metadata.

  Sources: `stage2/protocols/custom_portable_development_20260926.md`, "What
  changes"; code in `e1d6675` and `004943b`.

## Stage 2 C0 (control), version 0.3.0

**What it is.** A Deep Agents/LangGraph graph with file and shell tools that
execute inside the Harbor task container, and an explicit `complete_task`
completion call. The agent is `stage2/portable_custom_agent.py` (`e1d6675`) and
the backend `stage2/custom_portable_backend.py`. The protocol describes C0 as
"Minimal common controller, file/shell tools and explicit completion"
(`stage2/EXPERIMENT_PROTOCOL.md:54`). Its prompt is `BASE_PROMPT` in
`stage2/custom_control.py:4–9`.

**Settings** (`stage2/protocols/custom_portable_development_20260926.md`, "What stays fixed"):
- **Model:** `deepseek/deepseek-v4-flash-0731`, routed only to `deepinfra/fp8`;
  temperature 1, top-p 1, high reasoning, 384,000 output tokens.
- **Calls and spending:** no model-call ceiling (`max_model_calls=None` in
  `stage2/corrected_custom_agent.py` at `004943b`) and no spending cap.
- **Limits:** official task deadlines and resources.

C0's three execution cutoffs, as committed at `004943b`:
- **Commands:** 60-second default timeout, adjustable from 1 to 3,600 s
  (`stage2/custom_jobs.py:12–14`, `stage2/custom_backend.py:22`).
- **Background jobs:** at most 4 active and 64 per trial (`stage2/custom_jobs.py:15–16`).
- **Repairs:** at most two completion-repair cycles (stated at `stage2/custom_control.py:8–9`,
  enforced at lines 52–54).

**Score.** 15/20 on dev20 (`stage2/results/custom-portable-20260926/c0/trials.csv`,
published in `cf30cbd`). It failed adaptive-rejection-sampler,
install-windows-3.11, polyglot-rust-c, qemu-alpine-ssh and video-processing.

## C1, C2, C3

**Retention rule.** Variants are ranked by passes first. Then come charged cost
(only if every variant's cost is complete), then simplicity, then agent runtime.
Sources: `stage2/portable_final_selection.py:109–118` (`ddbe589`) and
`stage2/EXPERIMENT_PROTOCOL.md:58–59`. Every variant had some unknown costs, so
the cost tie-break was never used:
- `cost_tiebreak_used: false` in `stage2/results/custom-portable-20260926/registration-c2.json`;
- the same in `stage2/results/custom-deadline-20260927/original-selection.json`.

The C1 and C2 changes are the prompt additions in `stage2/custom_control.py`. All
three variants were defined in one commit, `444ec59` (16 Sep), so there is no
separate per-variant code commit. The per-variant config difference is the
registration's `condition` and `parent` fields.

Gains and losses below compare each variant's dev20 results with C0's, task by task.

### C1: planning instruction

- **Change.** `PLAN_PROMPT` is added to C0's prompt (`stage2/custom_control.py:10–12`,
  applied at lines 34–35): state an interpretation and a short task-specific
  plan, with no separate planning call.
- **Config.** `registration-c1.json`: `condition: C1`, `parent: null`, version
  0.3.0. The protocol defines it as "C0 plus a concise task-specific planning
  instruction" (`stage2/EXPERIMENT_PROTOCOL.md:55`).
- **Run.** Started in `6591f7a`, results in `8ae400f`.
- **Score.** 14/20 (`custom-portable-20260926/c1/trials.csv`).
- **Against C0.** Gained adaptive-rejection-sampler and qemu-alpine-ssh. Lost
  db-wal-recovery, overfull-hbox and qemu-startup.
- **Decision.** Not kept. Ranked below C0 (14 < 15) when C2's parent was chosen
  (`registration-c2.json`, `parent_selection.parent: C0`).

### C2: requirement-based completion checks

- **Change.** `CHECK_PROMPT` is added (`stage2/custom_control.py:13–17`, applied at
  lines 36–37). `complete_task` must also supply at least one observed,
  satisfied check, or completion is refused as incomplete (lines 69–75).
- **Config.** `registration-c2.json`: `condition: C2`, `parent: C0`, version 0.3.0.
- **Run.** Results committed in `1926e91`.
- **Score.** 14/20 (`custom-portable-20260926/c2/trials.csv`).
- **Against C0.** Gained adaptive-rejection-sampler and qemu-alpine-ssh. Lost
  db-wal-recovery, qemu-startup and regex-chess.
- **Decision.** Not kept (14 < 15; `original-selection.json`, `selected_original: C0`).

### C3: deadline-aware execution, version 0.4.1

- **Change** (`stage2/protocols/custom_c3_design_20260927.md`; code in `8154c96`,
  `edc92d4` and `1926e91`). Two things changed at once:
  - it adds a remaining-time reminder before each model request;
  - it removes all three C0 cutoffs (`execution_contract` in `registration-c3.json`):
    - `default_command_timeout: remaining-official-task-time`;
    - `background_active_count_cap` and `background_lifetime_count_cap: null`;
    - `completion_repair_count_cap: null`.

  The design note states this is "a broader execution-policy revision, not a
  time-reminder-only ablation".
- **Config.** `condition: C3`, `parent: C0`, version 0.4.1.
- **Run.** Launched in `8a7df73`, results in `6fc848a`.
- **Score.** 13/20 (`custom-deadline-20260927/c3/trials.csv`).
- **Against C0.** Gained adaptive-rejection-sampler and qemu-alpine-ssh. Lost
  db-wal-recovery, mailman, overfull-hbox and regex-chess.
- **Decision.** Not kept (`original-selection.json`: C0 15, C1 14, C2 14, C3 13;
  C0 selected).

## C0-NC ("no cutoffs"), version 0.5.0

**Why it exists.** A recorded "User decision" asked for the best of C0–C3 to run
all 89 tasks "with no artificial execution or spending cutoffs"
(`stage2/protocols/custom_direct_final_20260928.md:69–76`). The file does not
name the person who made that decision. C0 won the four-way selection but still
had C0's cutoffs, so a labelled revision was built
(`stage2/protocols/custom_no_cutoff_revision_20260928.md`; code in `6fc848a`,
`01e5261` and `09171e6`).

**What changed from C0** (`registration-c0-nc.json`, `execution_contract`
`parent-no-cutoff-without-time-advice-v1`):
- **The three cutoffs are removed,** as in C3: commands default to the remaining
  official task time, there are no background-job quotas, and there is no
  completion-repair stop.
- **No time reminders:** C3's dynamic time advice is not included
  (`remaining_time_guidance: false`).
- **Capture-transport fix:** the output-capture helper's source is encoded in its
  arguments. This fixes a process-matching collision found in C3's audit
  (`custom_no_cutoff_revision_20260928.md`, "Capture transport correction").
- **Prompt amendment:** limited to describing the changed command and completion
  contract (`prompt_amendment: command-and-completion-contract-only`).

**Validation on dev20.** 11/20 (`stage2/results/custom-no-cutoff-20260928/c0-nc/trials.csv`,
published in `fb2d5cc`). This is below C0's 15/20. Against C0 it gained
adaptive-rejection-sampler and lost build-pov-ray, db-wal-recovery, overfull-hbox,
qemu-startup and regex-chess. The validation had "no score floor"
(`custom_direct_final_20260928.md:63`). C0-NC was frozen as the finalist anyway,
with "it does not establish an accuracy improvement" noted in
`stage2/results/custom-no-cutoff-20260928/README.md:31–32`.

**Final 89-task run.** 50 passed, 36 verified zero-score failures and 3 setup
failures with no verifier result
(`stage2/results/custom-no-cutoff-final-20260928/c0-nc/trials.csv`, published in
`a0baf65`). The separate recovery runs of the 3 setup failures scored 0/3 and
are not part of the score (`stage2/results/custom-no-cutoff-recovery-20260929/README.md`).

**Held-out result.** 35/69 on the 69 tasks outside dev20, with 66 valid
(`experiments/saranya-analysis/README.md:89` on branch
`saranya-results-analysis`, commit `6383f4f`). On the same 69 tasks, Terminus-2
scored 38/69 and OpenHands 34/69 (lines 87–88).

### Validation (11/20) vs the final run's dev20 tasks (15/20): not identical conditions

The same 20 tasks scored 11 in validation and 15 inside the final run. The
recorded conditions were **not identical**, so the gap is **not** reported here
as single-run variance.

**The same in both** (`credit-policy.json` in both result folders: 32 identical
fields, including `model`, `execution_contract`, `candidate_version` 0.5.0,
`design`, `physical_request_retry` and `python_runtime_sha256`):
- model, endpoint and sampling;
- execution contract and candidate version;
- retry policy, with no caps;
- each task's official agent and verifier timeouts, CPUs and memory (identical in
  both `trials.csv` files);
- task order;
- the agent's prompt, graph and tool code (none of those files changed between
  the two source commits).

**What differed:**
1. **Source commit.** `06d94f7` for validation, `fb2d5cc` for the final
   (`launch.json`, `source_commit`). Six commits lie between them. Among existing
   files, only `stage2/scored_trial.py` changed: it adds final-study admission
   plumbing. The final also added new admission, policy, gateway and evidence
   modules (`stage2/no_cutoff_final_*.py`).
2. **Gateway container image.** The digests differ (`qualification.json`,
   `gateway_image`: `21f6f029…` vs `780a545c…`). The final image was built from
   `stage2/fixtures/Dockerfile.no-cutoff-final` with a new gateway session wrapper
   (`stage2/no_cutoff_final_gateway.py`). That wrapper reuses the same
   `RetrySession` but binds a different registration policy.
3. **Frozen candidate file.** The lineage hashes differ (`f493c72f…` vs
   `d6d2125a…`). They hash two different private runtime files that are not
   committed. Whether the contents differ in any behaviour-relevant way is
   **unconfirmed**.
4. **Time.** Validation ran 27 Sep 21:17 – 28 Sep 02:43 UTC; the final's dev20
   tasks ran 28 Sep 03:38 – 08:01 UTC (`started_utc`/`completed_utc` in both
   `trials.csv` files). Rate limiting was light in both: 3 HTTP 429s in
   validation and 1 in the final's dev20 tasks.

None of these differences touches the model settings, the task limits or the
agent's prompt or tools. But they are real code and infrastructure differences,
and their effect on behaviour is unconfirmed.

## What this tells us

- **No change beat C0 on dev20.**
  - Adding a planning instruction (C1) or completion checks (C2) each gave 14/20,
    against C0's 15/20.
  - Removing the cutoffs, with time reminders (C3), gave 13/20.
  - Removing the cutoffs without time reminders (C0-NC) gave 11/20 in validation.
- **On dev20 one task is 5 percentage points,** so a 1–2-task difference is within
  what single runs can produce. Most differences here are within noise.
- **The per-task pattern points the same way.** C1, C2 and C3 each gained the
  same two tasks over C0 (adaptive-rejection-sampler, qemu-alpine-ssh). All four
  later runs, C0-NC's validation included, lost db-wal-recovery. Changes that
  different producing the same task swings suggests run-to-run variation rather
  than an effect of any one change.
- **C0-NC's two runs on the same 20 tasks scored 11 and 15.** Their conditions
  were not identical (see above), but no recorded difference touches the model,
  limits or agent logic. That gap is a caution against reading any one dev20
  score precisely. Stage 2's separate confirmation and diagnostic runs, designed
  to measure this, were deferred and never run
  (`custom_direct_final_20260928.md:76–82`).
- **Changes were bundled.** C3 and C0-NC each changed several things at once
  (`custom_c3_design_20260927.md`), so no single cutoff's effect can be isolated.

**The brief's four levers.** The brief named four design levers: system prompt,
tools, context management and retries. Only the system prompt was ever tested
as a variant:

| Lever | Tested as a variant? |
|---|---|
| System prompt | **Yes.** C1 (planning) and C2 (checks) are prompt additions; C2 also adds a completion contract. |
| Tools | **No.** C0–C3 and C0-NC share the same file/shell tool set. C0-NC's capture fix was a bug fix, not a tested variant. |
| Context management | **No.** Output and context windows stayed "finite-unchanged" (`execution_contract`); no compaction or memory variant exists. |
| Retries | **No.** Model-request retries used one shared policy throughout (`physical_request_retry: undelivered-transient-only-within-task-deadline`). The completion-repair cap was removed only inside the bundled C3 and C0-NC changes, never on its own. |

## Related harnesses

- **Harshini's Bash-ReAct harness.** Harshini Prasad's separate
  one-command-per-turn Harbor agent, with its own version history:
  [`experiments/itsha-bash-react/harness/CHANGELOG.md`](https://github.com/KarthikRamesh9149/UTS-ilab-Group-15-02/blob/harshini-trial-run/experiments/itsha-bash-react/harness/CHANGELOG.md)
  on branch `harshini-trial-run`.
- **Saranya's minimal harness v0.2.** Saranya's one-command-per-turn agent
  pinned to the Stage 2 model settings, with a spending safety stop. It is
  untested on paid runs:
  `saranya-minimal-harness`, `experiments/saranya-harness/`.
