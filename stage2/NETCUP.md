# Netcup + OpenRouter continuation

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
- 363 Stage 2 unit/integration checks and 30 separately discovered custom checks
  passed on the server with the current sources, plus two graph-tracing checks;
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
