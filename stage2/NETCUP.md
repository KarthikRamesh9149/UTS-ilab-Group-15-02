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
- 332 Stage 2 unit/integration checks and 32 custom checks passed on the server;
  the 12 legacy pilot tests also passed after transferring their source modules.
- Synthetic full Docker/Harbor checks and fresh paid native-agent probes are
  the next admission requirements. These fixtures are not benchmark scores.
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
