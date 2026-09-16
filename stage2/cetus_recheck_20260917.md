# CETUS compute-node recheck, 17 September 2026

Result: connectivity restored; benchmark execution remains unqualified.

SSH was authenticated through hpc-login01. No agent tooling was run on
hpc-login02. The benign probe `cetus_network_recheck.pbs` ran as PBS job
89220.hpc-head01 on hpc-exec02, requesting one CPU, 2 GB RAM and five minutes.
It completed at 23:48:35 UTC on 16 September (17 September Sydney time).
No API credentials, model requests, benchmark solutions or agent commands
were used. No cluster settings or permission workarounds were applied.

## Observations

- Compute node: Linux x86_64; Apptainer 1.5.3-3.el8.
- No Docker, Podman, slirp4netns, pasta or rootlesskit on the job's PATH.
  This does not rule out an administrator-provided service elsewhere.
- No active allow-net entries or account subuid/subgid entries were printed.
- Public OpenRouter model-catalog request returned HTTP 200.
- Ubuntu 24.04 OCI image pulled and converted successfully (exit 0).
- Standard isolated bridge network failed (exit 255):

  > network requires root or a suid installation with /etc/subuid --fakeroot;
  > non-root users can only use --network=none unless permitted by the administrator

- Network-none container succeeded (exit 0), showed no routes and did not
  expose /shared/homes. This is a narrow fixture, not a complete security audit.
- The job's memory cgroup was /system.slice/pbs.service and reported
  memory.limit_in_bytes=9223372036854771712. Its cpuset was 0-23, despite the
  one-CPU request. Thus this probe did not demonstrate hard per-job CPU/memory
  containment. PBS may apply other monitoring/limits; those are not verified.
- The job finished and no jobs remained in the account's qstat listing.

## Decision

Login access and host Internet connectivity are not the blockers now.
Compute-node isolated outbound networking is directly denied under the standard
configuration, and exact resource enforcement is still unqualified. Offline
fixtures can run; this is not sufficient for the unchanged 89-task study.
An approved runtime/network configuration and confirmed hard resource limits
from UTS are needed before untrusted benchmark agent execution. Do not use the
shared host network or install bypass mechanisms to evade the restriction.

The remote evidence log is retained in the existing preflight directory:
`network-recheck-89220.hpc-head01.log`. The probe scratch directory is retained
at `/scratch/uts-network-recheck.gn0UfG`; no broad cleanup was performed.

## Alternatives investigated

1. **Apptainer under PBS with a host-side model controller:** plausible for
   offline tasks. The controller can reach OpenRouter without giving its key
   to the task. Network-none has passed. However, this does not provide task
   dependency downloads or arbitrary task networking, and full filesystem,
   user and resource equivalence remains unqualified. It is not an unchanged
   full-study replacement. Do not preinstall task-specific answers or silently
   restrict the benchmark to make this work.
2. **Administrator-supported Docker/Podman/container service:** no executable
   on the tested job PATH, no standard Docker/Podman socket on the login host,
   and the visible module inventory contains only base module utilities.
   These checks do not establish that UTS offers no such service. Request its
   approved endpoint or provisioning procedure from eResearch.
3. **Dedicated PBS allocation with a VM:** /dev/kvm exists on the login host;
   this is not compute-node capability or authorisation to create a networked
   VM. A supported VM design could provide an internal Docker host and task
   resource limits, but requires UTS approval of compute-node virtualisation
   and isolated outbound networking. No VM or alternate user-space network
   mechanism was installed or launched to route around the denial.
4. **Default Apptainer shared networking:** rejected for untrusted task
   commands. UTS documentation explicitly notes container daemons share the
   host network, and default binds include shared storage. This is not the
   isolation required by the study, even though ordinary trusted scientific
   applications may use this documented configuration.
5. **CETUS for offline analysis only, external Docker host for tasks:** avoids
   asking CETUS to provide the missing execution boundary. This is a hybrid
   alternative, not evidence that all tasks execute on CETUS. A separate host
   still requires qualification and any applicable spending approval.

No supported full-study alternative has yet been established with this
account. Next external dependency is an eResearch response about an isolated
container/VM service and hard per-task resource enforcement. No support ticket
or email was sent on the user's behalf.

Official sources checked:
- https://hpc.research.uts.edu.au/software_general/apptainer/apptainer_and_pbs/
- https://hpc.research.uts.edu.au/software_general/apptainer/info/

PBS history confirms Exit_status=0 for the diagnostic job; this means the
probe completed, not that all the capabilities it tested passed.
