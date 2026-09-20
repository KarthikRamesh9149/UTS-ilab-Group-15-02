# Active experiment protocol: Netcup + OpenRouter

Registered before the first scored model trial on this host. This document
describes execution and evidence requirements; it is not a report or a result.
Historical Mac pilot and CETUS trials are separate and cannot fill these cells.

Post-incident amendment, recorded 20 September 2026:
[one historical unresolved-charge hold](ACCOUNTING_AMENDMENT_20260920.md).
It prospectively changes the billing-completeness prerequisite for continuation,
not the model, tasks, scoring thresholds or financial limits. The original rule
below is preserved; any amended clearance is reported separately, never as
passing the original billing-completeness gate. Runtime qualification is still
required before the amended implementation can execute paid trials.

## Constant inputs and common limits

- Terminal-Bench 2.1: official revision and exact file hashes in
  `dataset_provenance.json`; 89 task IDs and deterministic fixed development
  subset of 20 in `input_manifest.json`. No task substitution after outcomes.
- Harbor 0.22.0 on native x86-64 Linux Docker. Each trial receives the task's
  declared CPU, RAM, agent deadline and verifier deadline. Sequential execution.
- One model: `deepseek/deepseek-v4-flash-0731`, pinned to `deepinfra/fp8`, with
  no fallback. Shared output ceiling 8192, temperature 1, reasoning high and
  top-p 1. The durable protocol fingerprint governs requests from every harness.
- Equal estimated per-trial model allowance: US$0.023. A budget stop remains
  part of the trial outcome. Setup, development and final accounting are separate;
  the original US$1 setup ledger is cumulative, never reset. Preserve US$2 account
  reserve; no purchase or automatic top-up. See `budget_policy.json`.
- Setup and verification time are recorded separately from agent time. Receipt
  reconciliation happens after model access is revoked and outside agent time.
- Uniform package preparation uses the documented Bullseye security snapshot
  amendment in `task_preparation.py`. Task/reference/test source bytes stay
  unchanged. This is disclosed, not claimed to be unmodified leaderboard setup.
- A separately logged POV-Ray reference-only transport check changes three
  failed HTTPS download URLs to the publisher's documented anonymous FTP URLs
  in a private reference copy. It changes no scoring-task inputs or model
  environment. The original reference failure remains visible alongside this
  qualification check; it is not a model retry or extra model assistance.

## Systems and development

Preselected established comparators are Terminus-2 (primary) and OpenHands
0.62.0. Their native decision loops, prompts and tools remain inherited;
connection/retry and dependency-install compatibility changes are disclosed in
`native_agents.py`. Neither is handicapped after seeing scores.

The custom agent uses the same model through the same guarded billing gateway,
Deep Agents and LangGraph, with tools executed through Harbor's task environment.
It has no reference/verifier access, task-ID-specific policy, model delegation,
external fallback or unmetered auxiliary model calls.

| Candidate | Single design change |
|---|---|
| C0 | Minimal common controller, file/shell tools and explicit completion |
| C1 | C0 plus a concise task-specific planning instruction |
| C2 | The registered C0/C1 parent plus requirement-based completion checks |

The parent/finalist selection rule is implemented in `development_selection.py`:
accuracy first, then charged cost, simplicity and runtime. Completion checks
are model claims, never substituted for the official verifier result.
All custom variants, diagnostics and the frozen finalist use the registered
100-model-call controller ceiling and at most two explicit repair cycles.
This is an additional custom-only safety ceiling, not extra budget or time;
native baseline iteration defaults remain unchanged. The common cost and
task deadlines govern every system. These limits are registered before scored
outcomes rather than selected to favour an observed custom result.

Run the first 20 Terminus trials and review actual parser, routing and environment
evidence. Expansion requires at least ten verified passes, at most two
budget-stopped trials, reconciled billing and cleanup. A failed gate must be
reported; it must not be lowered to spend the remaining credit.

If qualified, run OpenHands, C0, C1 and C2 on the same 20 tasks, followed by the
registered diagnostic block. The maximum is 120 development cells. Retain all
attempts, zeros and charges. An infrastructure correction requires a disclosed
amendment and fresh qualification; it does not turn a model failure into a retry.

## Frozen final evaluation and success

Freeze the selected custom implementation, dependencies, limits and all relevant
source hashes before any final result. Run 267 fresh final trials: all 89 tasks
for each established harness and the single frozen custom finalist. No tuning
based on final outcomes, assembling scores from different candidates, selective
reruns or choosing a comparator after seeing which one is weakest.

Primary research success requires the frozen custom system to have more verified
passes than at least one of the two preselected comparators on the complete
matched 89-task evaluation. Report both comparisons, all task outcomes and the
69 tasks outside development separately. An observed lead is not a guarantee
of repeatability or statistical significance; paired statistics are exploratory.

Matching accuracy with at least 20% lower cost can be an efficiency finding,
but **cannot** be labelled assignment success without mentor acceptance. Zero
passes across conditions are not a meaningful efficiency victory. Record tokens
and measured runtime alongside cost; do not selectively report a favourable metric.

Technical deliverables are the tested harness repository, change history,
per-trial metrics, billing audit, trace evidence, final comparison and technical
handoff bundle. Self-hosted Langfuse is deployed after timed runs to avoid
resource contention; export/dashboard verification is separate from local traces.
Leaderboard eligibility/submission and scientific success are separate from
working code. Neither a fixture pass nor an incomplete matrix proves completion.

## Later prospective amendment: fixed-study completion, 20 September 2026

The user explicitly approved [the fixed-study completion amendment](COMPLETION_AMENDMENT_20260920.md)
after the first six development outcomes. The preceding original protocol and
one-hold amendment remain preserved as historical rules. For the separately
validated v2 continuation only, the first-20 thresholds of ten passes and at
most two budget-stopped trials become reported, nonblocking performance
observations. Exactly two evidence-bound historical unknown requests retain
their combined US$0.212992 reservation; neither becomes a known charge or a
verified-billing result. The original qualification gate remains failed.

This supersedes only the original performance stop rule and the one-hold
maximum for the exact named second request. It does not supersede systemic
review, fresh source-bound qualification, complete first-20 evidence, cleanup,
new-request billing verification, fair limits, existing allowances, the US$2
reserve, selection/freeze rules or the matched 267-cell fresh final evaluation.
No third unknown-request exception or increase in spending is authorised.
