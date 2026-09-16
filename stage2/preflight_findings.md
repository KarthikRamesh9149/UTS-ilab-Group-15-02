# CETUS preflight — 2026-09-16

Status: **basic preflight successful; autonomous-agent execution NOT approved by evidence**.

PBS jobs 88368.hpc-head01 (Alpine) and 88369.hpc-head01 (Ubuntu) ran on
hpc-exec02, requesting 2 CPUs, 4 GB RAM, 10 minutes and no GPUs. These were
deterministic fixtures, not benchmark trials. No API keys were copied to CETUS.

Verified compute-node findings:
- OpenRouter model metadata and PyPI reachable (HTTP 200).
- Docker registry reachable (HTTP 401 is its unauthenticated challenge).
- Apptainer can pull OCI images and execute contained commands.
- Explicit suppression of home/default mounts hides /shared/homes.
- A dedicated evidence bind supports file round-tripping.
- An isolated network namespace with no networking starts successfully.
- Ubuntu supports basic root-emulation. Alpine failed loading the host faked
  helper; this must not be generalised to all images.
- Scratch has approximately 6.2 TB free at inspection, not a personal quota.

## Unresolved security and comparability issues

Installed Harbor 0.22.0's built-in SingularityEnvironment:
- launches its command server on shared-host localhost without authentication;
- does not request a private network namespace in its launch command;
- explicitly omits CPU/memory cgroup flags, delegating enforcement to scheduler;
- its memory watchdog uses kill_threshold=0.95, rather than the full stated limit;
- requires prebuilt docker_image/SIF rather than building arbitrary Dockerfiles.

Sources inspected: harbor/environments/singularity/singularity.py and server.py
in the installed package. No agent was launched through this adapter. Shared
localhost is not an adequate boundary between mutually untrusted node tenants.
The no-network preflight does not establish useful networked benchmark isolation.

Next decision: obtain an administrator-approved isolated network/runtime route
on CETUS, or authorise the additional hardened adapter work and its security
validation. Do not silently launch against the default adapter. Do not alter
official task limits or silently mark incompatible tasks failed.

Additional gates: newer isolated Python; personal storage/allocation and DMP
confirmation; full dataset provenance; all89 runtime qualification; local Git
licence blocker; spending gateway; Langfuse destination. No scored results exist.

## Financial check (read-only, no generation)

OpenRouter key endpoint: limit $30, remaining key allowance $30, key usage $0.
Account credit endpoint: total_credits $150, total_usage $124.734823195;
available account credit is therefore $25.265176805 at this check. The account
balance is distinct from the key cap and may be shared with other consumers.
The original $30 guaranteed allocation is not established. With a $2 reserve,
only $23.265176805 is currently usable, less than the planned $24.22 core maximum
(even before contingency). Stop paid execution pending a budget decision; no
automatic top-up. Actual costs might be lower, but must not be assumed to fund
the full worst-case allocation.

Tests: three new offline manifest tests and twelve existing project tests passed.
Both PBS diagnostics finished; no project jobs remain queued or running.
