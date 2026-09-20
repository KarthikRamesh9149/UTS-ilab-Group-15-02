# Netcup + OpenRouter continuation

## Prospective continuation amendment, 20 September 2026

The [accounting amendment](ACCOUNTING_AMENDMENT_20260920.md) permits a
separately labelled, conservatively funded continuation past exactly one
historical unresolved request. It does not certify that request's charge,
replay the failed trial, change the task list or lower qualification thresholds.
The original billing-completeness rule remains unsatisfied and is reported
separately from any amended clearance.

Current continuation service: `uts-stage2-qualification-netcupv6p.service`,
private log `.runtime/stage2/netcup-qualification-v6p.log`. The runner candidate
passed 491 tests on each host and independent source review. The synthetic
runtime and all three fresh live model/harness checks passed. Their seven
model calls cost $0.00186342 with matching receipts. The initial live check
had stopped before any dispatch on a legacy ledger-file permission mismatch;
that precise configuration was corrected without changing ledger bytes. See
[activation and verification evidence](netcup/accounting_continuation_verification_20260920.md).
`admission_netcupv6p.json` binds the actual passed proofs. At the 20 September
resumption checkpoint the first-20 Terminus block was active on
`dev-terminus-2-01-build-pov-ray`, after retaining the historical first cell.
This is real resumed execution, not a completed benchmark score or a harness win.

The implementation preserves the full $0.106496 reservation and original
ledger rows/result bytes. It checks both setup and scoring ledgers before
new spending. Any additional unknown request, pending prior-trial receipt or
billing incident stops continuation. Fresh source-bound native qualification
is required; the old `netcupv5` admission is not valid for changed code.

The client spending audit, recorded before this continuation, is in
[`output/spending-audit-20260920`](../output/spending-audit-20260920/README.md).
It lists all 46 recorded generation requests, $0.00774516 confirmed charges
and the unknown reservation separately. The approximately $13.23 remainder
of the account-level balance decline cannot be attributed from this project's
key evidence and is explicitly not described as verified project spending.
That audit is a dated snapshot; subsequent calls stay in the authoritative
ledgers and must be included in the next client spending export.

`export_development.py` provides a separate read-only CSV/JSON snapshot of the
five primary fixed-20 development conditions. It does not authorise spending
or claim final-89 success. Partial conditions have no accuracy rate; unknown
costs/tokens stay unknown. Run it on the qualified host only when the matrix
lock is free, with the current admission and a fresh output directory. The
reporter has 14 regression tests and an independent read-only review. After
adding it, all 505 local tests passed; the timed native benchmark was not
interrupted to rerun unrelated tests.

The subsequent host-only timing extension exports recorded setup, agent and
verifier durations, their measured subtotals and coverage counts. Full-20
runtime totals remain unknown until all measurements exist; absent durations
are never treated as zero. All 18 targeted exporter tests pass locally. The
47 frozen scoring-source hashes still match the live admission; no timed
benchmark code or per-trial limit was changed for this reporting improvement.

## Earlier stopped checkpoint, 20 September 2026 (Sydney)

**Paid benchmark execution is stopped, not complete. No harness victory is established.**
The earlier running/queued checkpoints below are historical.

- On explicit request to try again, one separate endpoint diagnostic succeeded
  at 20 September 00:14 UTC using the same model, provider and frozen model
  settings. It returned `UTS_OK`; the response and independent receipt matched
  $0.00000918 for 93 input and 20 output tokens. Original aggregate setup spend
  is now $0.0073707. See [the diagnostic evidence](netcup/endpoint_recheck_20260920a.json).
  This verifies current key/endpoint operation, not the cause of the earlier
  error, native harness qualification or completed benchmark billing recovery.
  The original scored ledger and failed-result hashes are unchanged, and the
  $0.106496 unknown reservation remains held. No failed scored call was replayed.
  The diagnostic has six regression tests; all 395 Stage 2 discovery tests
  passed on both Mac and native server after this addition. Its one-dispatch
  and budget handling received a separate read-only review.
  A fresh read-only account check reported $12.028542692 remaining. The updated
  private runtime was archived outside the rental under
  `.runtime/netcup/endpoint-recheck-20260920-eahIfK/stage2-runtime.tar.gz`, with
  SHA-256 `2eaeaa01452bb8b10a0d786b5d6a4d38eeca935d916b5692303694619dba50e5`.
  The archive gzip integrity check passed; it is excluded from Git.
- All 20 fixed development environments qualified: 19 original reference
  passes and the disclosed reference-only POV-Ray download repair. These are
  not model scores. All three `netcupv5` live model/tool fixtures passed with
  independently matched billing, tracing and cleanup.
- The first scored Terminus trial, `dev-terminus-2-00-video-processing`,
  retained reward zero and `APIError`. Its third upstream request returned no
  usable response or generation identity. The result is `billing_unresolved`,
  not a verified completed cell. No second scored cell or replacement attempt
  was launched. Containers, networks and volumes from this trial were removed.
- Both known request receipts were recovered without another generation.
  At the recorded 19 September 14:53 UTC account check, cumulative setup cost
  was $0.00736152, known scored cost $0.00037446, and key usage $0.00773598.
  The account had $12.028551872 available. The unresolved request retains its
  $0.106496 upper-bound reservation; this is not a confirmed charge. Aggregate
  key usage matching known charges does not individually reconcile that call.
  See `netcup/billing_interruption_20260919.json` and
  [the exact recovery handoff](netcup/BILLING_RECOVERY.md).
- Two historical local retry markers are named `budget-stop.json`, because
  the pending-request barrier uses the same exception as budget admission.
  They are preserved. They do **not** establish exhausted credit or duplicate
  upstream dispatches. This trial cannot enter an audited comparison yet.
- Transport errors now retain allowlisted HTTP status, error category and
  request/generation identifiers when provided. No raw error text, credentials
  or task content is added to diagnostics. Unknown outcomes still retain their
  reservations and cannot be replayed. The old missing identifier cannot be
  reconstructed by this fix.
- The error-diagnostic patch changes runtime hashes. The preserved
  `admission_netcupv5.json` documents the setup used for the first trial; it
  is not admission for the patched runtime. New live qualification must wait
  until billing recovery or the separately reviewed prospective amendment
  above, then bind the patched sources before paid resumption.
- Self-hosted Langfuse 4.38.0 was deployed with six content-pinned images and
  loopback-only ports. Actual observations API readback matched all 22 setup
  events: seven generations, 22,469 input tokens, 1,202 output tokens and
  $0.00106914. Exact trial/parent associations, protocol metadata, measured
  phase durations and official fixture rewards all matched the local spools.
  See `netcup/langfuse_*_netcupv5_verified_metrics.json`. This is live service
  evidence, not benchmark accuracy or visual dashboard verification. No raw
  task text or provider credentials were exported.
- The first baseline block, development comparisons, finalist freeze, fresh
  267-cell final evaluation, final evidence bundle and leaderboard submission
  remain unfinished. Do not fill their tables with setup or historical pilot
  results. Efficiency-only assignment success still needs mentor acceptance.

`netcup/deploy_observability.py` refuses a competing benchmark and pins images
before starting services. `netcup/verify_observability.py` performs post-run
metadata readback without model calls. Stop dashboard services before any timed
benchmark resumes; retain their volumes and private credentials for restoration.

The final checkpoint has 433 tests passing on each host, private archives of
runtime evidence and stopped dashboard volumes saved outside the rental, and
all six dashboard services stopped. The 19 September 19:18 UTC read-only account
recheck showed unchanged credit and known usage; the missing request remains
unreconciled. See [verification and backup details](netcup/verification_20260920.md).
The rental still incurs recurring charges until its contract is terminated.

## Scope and accounting

Authorised 19 September 2026: use the provisioned Netcup x86-64 server and finish
the study within the remaining OpenRouter balance, without top-ups. This is a
host/budget amendment, not evidence of success and not a change to the model or
the fixed task selection. Earlier Mac pilot and CETUS experiments remain separate.

- Terminal-Bench 2.1, official revision recorded in `dataset_provenance.json`.
- Harbor 0.22.0, Terminus-2, OpenHands 0.62.0, custom Deep Agents/LangGraph agent.
- Same model: `deepseek/deepseek-v4-flash-0731`, pinned `deepinfra/fp8`, no fallback.
- Same requested output limit 8192, temperature 1, reasoning high, top-p 1.
- Fixed 20 development tasks, one-change-at-a-time custom development, then
  fresh 89-task final scoring per harness if qualification/budget gates pass.
- Primary established comparator: Terminus-2. A win is not guaranteed.

| Allowance | USD |
|---|---:|
| Observed account balance before this migration | 12.031657772 |
| Untouched account reserve | 2.00 |
| Original aggregate setup allowance, including all prior setup spend | 1.00 |
| Equal estimated per-scored-trial cap | 0.023 |
| 120 development cells maximum | 2.760 |
| 267 final cells maximum | 6.141 |
| Total setup plus scored maximum | 9.901 |

Fresh account balance and conservative request reservations govern every
dispatch. The estimated per-trial cap is not an absolute tokenizer guarantee;
an estimate underestimate or unreconciled receipt halts further dispatch. The
global/stage/account reservation uses the full model-context upper bound.
Other account users can reduce available credit. Budget-stopped trials count
as such, not infrastructure retries or successes. No automatic top-up.

The original private setup ledger was migrated, not reset. Prior reconciled
setup spending was US$0.00463008. The server ledger is authoritative from
migration onward; never run a second paid runner against the stale Mac copy.
All setup receipts, even failed probes, must be included in final accounting.

Before any scored trials, the receipt policy was revised in response to two
retained setup failures: OpenRouter's historical generation lookup returned
404 for more than 40 seconds after successful completions. The response's
documented `usage.cost` now settles the charge immediately; the historical
receipt must independently match after agent revocation, outside task time,
before another trial may dispatch. Missing response costs retain reservations;
receipt mismatches persist a halt. No failed generation is replayed to recover
billing. This policy is identical for all three harnesses.

Passive metadata traces record phases, generation times, tokens and exact
charges without exporting prompts or task content. A complete local trace is
not proof of a successful Langfuse cloud export.

## Deployment and qualification

The new server is Debian 13, native x86-64, 8 vCPU, approximately 16 GB RAM and
512 GB storage. Docker 29.8.1 and Compose 5.5.1 are installed from Docker's
official Debian repository. Host-key verification matched the provisioning
email. A dedicated SSH key was tested before disabling password authentication.
No model endpoint or Docker TCP port is exposed publicly.

The project is private at `/opt/uts-capstone`; its Python 3.12 environment uses
the hash-locked `custom-requirements.lock` for a unified baseline/custom runner.
This resolves LiteLLM 1.101.0 rather than the older Mac baseline's 1.98.0. The
new version emits both reasoning aliases; only exactly equal aliases are now
canonicalised. Conflicting settings still fail. No baseline prompt or decision
loop was altered. Fresh live qualification is required on the new dependency set.

Mac AppleDouble transfer sidecars were moved to a private metadata quarantine
outside the canonical dataset. Source/task bytes were not edited. Subsequent
transfers disable Mac metadata and verify the exact canonical file hashes.

Host checks measure disk space, available memory, CPU affinity and Linux memory
pressure. The VPS does not expose trustworthy physical thermal readings, so
none are invented. Trial CPU/memory limits remain the official task values.
The runtime retains task isolation, guarded internet access, private credentials,
sequential ownership locks, durable billing and verified cleanup.

Progress and remaining work:

- Server provisioned, key login verified, dependencies installed.
- 373 Stage 2 unit/integration checks passed locally and on the native server
  after the reference-download amendment. The unchanged custom and tracing
  components also have 30 separately discovered custom checks and two
  graph-tracing checks passing on the server;
  the 12 legacy pilot tests also passed after transferring their source modules.
- The `netcupv4` synthetic custom check and all three real-model native checks
  passed with billing, metadata tracing and cleanup verified. This established
  working model/tool integration, not benchmark accuracy. Their admission is
  now superseded by the package-index preparation change described below;
  fresh proofs must bind that change before scored trials begin.
- Reference-solution environment checks cost no model credit. Do not inspect
  reference contents to tune the model or the custom harness.
- First scored block is the existing 20-task Terminus qualification. Its frozen
  expansion rules require at least 10 successes, no more than 2 budget stops,
  verified accounting/cleanup and an actual systemic-failure review.
- If it does not qualify, retain the results and report the precise gate failure;
  do not lower the gate or substitute tasks after observing outcomes.
- Full benchmark results, a custom-harness victory, external Langfuse export,
  final evidence bundle and leaderboard submission are not yet established.

The rental is recurring until terminated. An existing completion follow-up
checks backups and pending jobs before preparing cancellation; merely stopping
the server does not cancel its contract. Do not delete it while results exist
only on the server.

## Latest execution checkpoint, 19 September 2026

- `netcupv4` setup charges: Terminus-2 $0.00017748 (3 requests), OpenHands
  $0.00099360 (3 requests), custom $0.00029016 (2 requests). All receipts match.
- Cumulative original setup ledger, including earlier probes and failures:
  $0.00629238. Live account balance after these checks: $12.029995472.
- The first native `qemu-startup` oracle result was reward zero because its
  verifier bootstrap could not download a package named by stale Debian
  indexes (HTTP 404); curl/uvx were consequently unavailable. The test runner
  did not start. The original outcome remains in `oracle-dev20-v2/qemu-startup`.
- Index refresh alone did not solve the issue: the refreshed official mirror
  also advertises the now-missing binary. That failed attempt is preserved in
  `oracle-dev20-apt-v3`. Direct HTTP/HTTPS checks confirmed 404s from both
  `deb.debian.org` and `security.debian.org`, while the dated official Debian
  snapshot successfully served the same `libnghttp2-14` version.
- Setup now redirects only classic `bullseye-security` entries on those two
  official hosts to Debian's fixed `20260831T235959Z` security snapshot and
  refreshes indexes. It preserves package signature/hash verification, signing
  key and architecture options; only the historical Release freshness check
  is waived for that snapshot, following Debian's documented usage. No packages
  are installed/upgraded by preparation, no task/test source bytes change, and
  all harnesses receive the identical amendment before their timed agent phase.
  A disposable no-model diagnostic successfully downloaded curl and all its
  dependencies through this setup. Snapshot documentation:
  <https://snapshot.debian.org/#usage>.
- This is a disclosed execution-environment amendment, not a claim of
  unmodified upstream leaderboard conditions or automatic submission eligibility.
- API-free reference requalification now uses `oracle-dev20-snapshot-v4`,
  preserving both earlier attempts. The active service is
  `uts-stage2-reference-snapshot-v4.service`; its private log is
  `.runtime/stage2/netcup-references-snapshot-v4.log`.
- The first repaired reference, `qemu-startup`, passed with reward 1, enforced
  resources and verified cleanup in 107.411 seconds. Remaining reference checks
  are still running; this is not a scored model result.
- `install-windows-3.11` and `adaptive-rejection-sampler` also passed, in
  387.875 and 55.331 seconds respectively. This resolves the three earlier
  architecture-sensitive reference failures on the native host. The latest
  committed progress snapshot has four passes from four completed references;
  the remaining sixteen are not yet certified.
- `start_qualification.py --references-only` cannot spend on models. After the
  references pass, rebuild the gateway and generate fresh synthetic/native
  proofs with a new label before constructing a fresh admission. Do not use
  `admission_netcupv4.json` with the changed sources.
- The original `uts-stage2-qualification-netcup.service` stopped at the failed
  reference gate; it did not start scored model trials. Do not treat its
  failed state as a second active matrix or reset its retained evidence.
- A private backup of setup evidence exists on the Mac under
  `.runtime/netcup/checkpoint-20260919-paGkKb`. It excludes the active reference
  attempt. Back up completed reference and scored artifacts again later.

The current executable study protocol, including candidate identity, fixed
custom controller limits and interpretation of success, is in
[EXPERIMENT_PROTOCOL.md](EXPERIMENT_PROTOCOL.md). Registering those limits does
not authorise skipping the first-20 review or weakening its thresholds.

## POV-Ray reference download and automatic next stage

The native `build-pov-ray` reference failed with exit 8 when downloading
`POVDOC.TAR.Z`: the publisher's HTTPS endpoint returned HTTP 403 with
`cf-mitigated: challenge`. The original reward zero remains in the snapshot-v4
namespace. The [publisher's download page](https://www.povray.org/download/)
also explicitly offers anonymous FTP. All three required archive downloads
succeeded via that published endpoint on the native host; observed file sizes
and hashes are in `netcup/povray_download_diagnostic.json`.

`reference_download_repair.py` makes one private, separately recorded reference
copy. It checks the original script's pinned SHA-256 and changes only three
exact HTTPS archive URLs to their official FTP equivalents. It validates that
every other copied file remains byte-identical. The canonical dataset, task
instruction, verifier, model environment, prompts and tools are **not** changed
by this reference-only amendment. Original and amended reference outcomes are
reported together; an amended failure cannot be replaced by a better attempt.
No benchmark solution logic is copied into model policy. This qualifies host
capability, not automatic model success: models must still solve the unchanged
task and can encounter the original HTTPS download failure.

The amended attempt uses `oracle-povray-ftp-v1`, launched with
`qualify_oracle.py --task build-pov-ray --repair-povray-download --wait`.
The explicit wait acquires the same exclusive task lock after the current
reference batch finishes. No second task executes concurrently.

`start_qualification.py --prepare-and-qualify netcupv5` then requires the complete
reference qualification before rebuilding the gateway and running a fresh
synthetic fixture plus the three real-model compatibility probes. Only passed,
hash-bound evidence creates `admission_netcupv5.json` and starts the first 20
Terminus trials. It stops for the actual first20 review; it does not run custom
development or final scoring automatically. Existing probe labels, partial
attempts and failures cannot be silently replayed or assigned new labels.

This sequence is intended to avoid an idle server between already-authorized
steps. A queued or active sequence is not evidence that its future gates passed.
It is now queued as `uts-stage2-qualification-netcupv5.service`, with private log
`.runtime/stage2/netcup-qualification-v5.log`. Its first process waits for the
snapshot-v4 task owner before the amended reference attempt; the second runs
the fresh-proof sequence only if the first command exits successfully. The
explicit complete-reference check still blocks paid work if the new reference
has reward zero or any other task remains unqualified. Inspect both service
handles before starting anything else. Do not restart a terminal failed service
without inspecting its retained attempt and the cause.

### Verified advancement, 19 September 2026 at 14:30 UTC

All twenty task environments are now qualified: nineteen original snapshot-v4
references passed, and the separately amended POV-Ray reference passed in
78.654 seconds. The original POV-Ray failure is preserved in the exported
progress metadata. `oracle_netcup_qualification_progress.json` records twenty
qualified tasks and exactly one amended reference; this is not twenty model
passes or twenty unmodified reference passes.

The original snapshot-v4 service ended at its expected reference gate because
its unamended POV-Ray attempt was zero. The already-queued netcupv5 service then
acquired the execution lock, completed the amended check and advanced without
replaying any successful reference. Its fresh synthetic custom-runtime proof
passed. The real-model native compatibility checks are now underway, before
any scored trial. Gateway image:
`sha256:5c08c03ed9a8d6cb30777b75d23e260297227ef5e1627b888d67c7c1d05cf590`.

A private Mac checkpoint under `.runtime/netcup/reference-checkpoint-20260919-Wwznj9`
contains the seventeen reference attempts completed at capture time. This is
a partial raw-log backup, not the final twenty-task or study backup.

## Langfuse dashboard preparation

The passive Harbor traces are live and metadata-only. The official Langfuse
Compose source is pinned by revision and SHA-256 in
`netcup/prepare_observability.py`. Preparation generates fresh private service
and local-owner credentials, loopback-only ports, no automatic container
restart, and no inference-provider credentials. It starts no services.

Deploy the dashboard only after benchmark execution has stopped, so its
database/worker load cannot alter measured task runtimes. Resolve and retain
image digests at deployment. Then export with track `netcup-openrouter`, verify
trace/token/cost/reward records through the actual service and capture the UI.
Transport acknowledgement alone is not dashboard verification. Back up both
metadata spools and dashboard data outside the rental before cancellation.

References: [official Docker Compose guide](https://langfuse.com/self-hosting/deployment/docker-compose)
and [headless initialization](https://langfuse.com/self-hosting/administration/headless-initialization).
