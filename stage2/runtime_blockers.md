# Remaining runtime qualification gates

Inspection date: 2026-09-16. No paid inference or scored Stage 2 task ran.

## Verified inventory

Static inspection of all 89 task environment configurations found prebuilt
images for every task, no Compose definitions, and maximum declared resources
of 4 CPUs and 8192 MB RAM. See runtime_inventory.json for file hashes and rows.
This is not evidence that the images execute correctly under Apptainer.

## Network permission

On the login node, Apptainer configuration has no active `allow net users`,
`allow net groups` or `allow net networks` entries. This account has no subuid
or subgid mapping. No slirp4netns, pasta or rootlesskit executable was found on
the login PATH. Network-disabled execution passed the prior compute-node test.
Compute-node network permissions have not been independently established.

Apptainer documents `none` as the default network available to unprivileged
users; other configurations require administrator permission:
https://apptainer.org/docs/user/latest/networking.html

Do not install networking workarounds, alter cluster configuration, or expose
agent commands to the shared host network to bypass this gate. Ask UTS for an
approved internet-enabled isolated runtime or a supported isolated execution
service. Ordinary login-node/compute-node internet connectivity is not proof
of sandbox network isolation.

## Additional containment and comparability gaps

- The Unix-socket fixture mounts its control directory and authentication token
  inside the same container as commands. This tests host-tenant access control,
  NOT protection from a malicious command inside that container. The study's
  requirement that tasks cannot access their control socket is not met.
  Follow-up: native instance fixture PBS 88380 avoids this custom socket/token
  entirely and preserves file changes between commands. Prefer this route for
  the real backend. This small fixture is not an adversarial containment audit.
- Exact task CPU/RAM enforcement, storage limits, process cleanup, arbitrary
  user behavior and image compatibility have not been qualified.
  PBS 88380 explicitly reports that rootless cgroups is not usable in fakeroot
  mode. Scheduler enforcement must be verified independently; no unsupported
  cgroup flags or a 95-percent watchdog may stand in for official task limits.
- The scratch overlay used by the fixture is not a qualified persistent task
  filesystem backend. Filesystem continuity through verification needs tests.
- Account/project allocation, DMP and approved trace-export destination remain
  unconfirmed. No administrator approval is inferred from user permission.

## Request to UTS eResearch (prepared, not sent)

We are evaluating terminal agents against Terminal-Bench 2.1 using PBS compute
jobs and OpenRouter inference. We need an approved runtime for untrusted task
commands, with private filesystem/process/network isolation, outbound public
HTTPS, and no access to shared home storage, credentials, other jobs or runtime
control sockets. Tasks declare up to 4 CPUs and 8 GB RAM; all have OCI images.
Is there a supported container execution service or approved Apptainer network
configuration and resource-enforcement method for this use? Please also confirm
the permitted project/account arrangement, storage allocation and DMP steps.

No cluster safeguards have been changed and no agent workloads have launched.
