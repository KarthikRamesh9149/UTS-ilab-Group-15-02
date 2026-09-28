# Matched baseline repeats after custom final89

## Authority and order

On 28 September 2026, before the custom final89 score was known, the user
explicitly accepted this sequence: finish C0-NC validation and final
qualification, freeze that exact harness and run its 89 tasks, then run
separately registered Terminus-2 and OpenHands repeats while keeping their
original results intact. This supersedes the earlier advice-only discussion.

This authorises one fresh 89-task repeat per baseline, 178 additional attempts
in total. The order is custom final89, its audit and verified private backup,
Terminus-2 repeat89, then OpenHands repeat89. The repeats are sequential and
must not overlap any study matrix. This is not authority for parallel dispatch,
another server, additional variants, per-task retries, top-ups, payments or
account/key-limit increases. Do not condition the repeat decision or order on
the custom final score.

This document records the agreed design, not a completed qualification,
registration or launch. Exact new experiment IDs, private paths, deployment
source, image bindings and launch registrations must be recorded before any
repeat starts. Existing baseline registries and results must not be reused or
overwritten. A started, interrupted or completed attempt cannot be replayed.

## Matched conditions

- Use the same frozen 89-task manifest and task order as the custom final
  registration: the fixed development20, followed by the remaining69 in the
  registered order. Do not select tasks after outcomes.
- Keep each baseline's original native agent and tool behaviour. Matching
  the study setup does not mean replacing baseline tools with custom tools.
  Audit and disclose any harness-specific controls before qualification;
  a material behaviour change needs an explicit protocol amendment before
  launch, not an undocumented repair after a result.
- Use `deepseek/deepseek-v4-flash-0731` only through `deepinfra/fp8`, with no
  fallback, temperature 1, top_p 1, high reasoning and maximum output 384000.
  The model protocol SHA256 remains
  `75718eac81a70390e879743b3c760e942281ac205f577960beec845d50057238`.
- Preserve the qualified native host, official task images, CPU/memory
  resources and deadlines. Use the shared Retry-After implementation and
  passive accounting. Do not introduce project/task financial reserves,
  model-call ceilings or physical-request-count ceilings. Unknown cost stays
  unknown; it is neither zero nor a dispatch gate.
- Preserve actual provider credit, authentication, identity, rate and context
  constraints, isolation, cancellation, revocation and owned-resource cleanup.
  This does not authorise buying credit or increasing provider limits.

Each repeat needs a separately source-bound runner/gateway admission, all
ancestor locks, no-overlap/no-replay checks, isolated native synthetic
qualification, pinned images and exact registration. Qualification must test
the actual repeat lifecycle without paid model calls. Do not repeat old
completed qualification or run another paid access probe merely to confirm
already established provider access.

## Reporting and interpretation

Keep the original corrected scores unchanged: Terminus-2 52/89 and OpenHands
44/89. Retain and report both original runs and both new repeats separately.
Terminus-2 remains the primary comparator and OpenHands the secondary; do not
switch the primary after outcomes or select per-task best attempts.

Report full89 and the development20/remaining69 breakdowns, including zeros,
missing verifier outcomes, elapsed time, physical requests, retries and unknown
costs. Provider-reported costs are not independent billing receipts. Audit
exact registered coverage, official limits, source/runtime/image bindings,
revocation and cleanup, and make one verified private off-server backup per
completed block. Publish curated metadata only, never private archives, raw
model exchanges, credentials or task solutions.

One repeat per baseline does not establish causal effects or eliminate
stochastic uncertainty. Sequential runs avoid competition between our study
matrices but do not eliminate provider drift over time. The earlier custom
confirmation60 and diagnostic20 remain deferred, not completed or silently
replaced by baseline repeats.

The server remains required until all authorised work, including these repeats,
has finished and its evidence is secured. The extra 178 attempts extend the
schedule; the September 30 target does not justify shortening official task
limits or skipping qualification. Cancellation still requires action-time
confirmation after verified backups and no required jobs.

## Offline schedule checkpoint

`matched_repeat_schedule.py` fixes the two repeat blocks and their task order
without reading custom outcomes or dispatching anything. It uses the exact
full89 manifest and model-protocol fingerprints, matches the custom final
task order, and assigns 178 distinct `matchedrepeat1-terminus-2-` and
`matchedrepeat1-openhands-` identities. Its prerequisite labels require the
custom final audit/private backup first, then the Terminus-2 repeat audit and
backup before OpenHands. They are planning requirements, not evidence those
events have happened. The eventual host must authenticate them.

This schedule is explicitly not a registration, native qualification or paid
admission. It leaves the original primary/secondary comparison and 52/89 and
44/89 scores unchanged, has no outcome-dependent selection, retains unknown
costs and adds no study spending or model/physical-request-count ceiling.
Confirmation60 and diagnostic20 remain deferred. The existing capped
`prepare_baseline_repeat.py` / `run_baseline_repeat.py` route is a historical
experiment and must not be reused as this new repeat's admission.

The original corrected baseline presets do retain one-million-turn guards:
Terminus-2's default and OpenHands' configured maximum iterations. These are
baseline-harness settings, not benchmark requirements, and the schedule
discloses them separately from the absence of additional study request caps.
It does not call the baselines literally unrestricted or claim the guards
cannot affect behaviour. Removing them would change the preserved baseline
behaviour and require an explicit pre-launch protocol amendment. The planned
native source audit must verify these and any other baseline-specific controls;
this local inspection is not completed native authentication. These guards
are not introduced into the custom C0-NC harness.

All 15 new local tests passed, covering exact coverage/order, distinct keys,
unchanged comparators, uncapped passive-accounting declarations, disclosed
native guards, deferred phases, no outcome input, no paid-ready flags,
tampering, deterministic isolated state and lightweight imports. Ordering
parity uses the real custom-final cell builder with its separate candidate
validation mocked; it is not a real final freeze. No native source, gateway,
registration or benchmark attempt was changed by this checkpoint.

The combined affected run passed 55 tests. Full local discovery ran 1,588
tests: 1,587 passed and one pre-existing skip. A separate read-only check
verified the original 178-row baseline CSV hash and found no overlap with
the 178 new planned IDs. The deterministic schedule's canonical SHA256 is
`bd26df6c19c88c238d0795423699fa9030a12f4ea925b42667ad75321817a6e1`.
No real repeat registration, native source authentication, qualification or
provider call occurred. The custom final source inventory and active C0-NC
execution source were not changed.
