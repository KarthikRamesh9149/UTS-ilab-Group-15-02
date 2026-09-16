# Mac guarded runtime integration

2026-09-16. This is an integration fixture, not a scored benchmark run.
The older `runtime_blockers.md` records the abandoned CETUS path, not current
Mac execution requirements.

`guarded_runtime.py` joins a task to a dedicated firewall sidecar's network
namespace only after its firewall is healthy. The model gateway stays on its
separate network and is accessed through a read-only Unix-socket volume.
Task CPU and RAM declarations are not rewritten. The sidecar alone receives
NET_ADMIN; the task cannot administer the firewall or use raw sockets.
The helper rejects mutable guard image names, host networking, additional
task capabilities, privileged execution and published task ports.

The real OpenHands 0.62.0 fixture now exercises both boundaries together.
`openhands_agent_probe_guarded1.json` preserves the initial successful run.
The guarded2 run additionally inspects Docker's actual merged configuration
before starting the agent and checks trial-container removal afterwards.
Both use scripted model replies and no paid generation. Public metadata HTTPS
is a connectivity check only. Model token counts and billed cost are not
inferred from this fixture.

Remaining gates before scored execution:

- Production gateway credential loading, canonical scored ledger and lifecycle
  integration; the fixture gateway is deliberately network-disabled.
- Arbitrary task users and their access to the private model socket; this
  fixture uses root and must not be presented as all-user qualification.
- Official image compatibility and dev20 oracle validation. IPv6, raw sockets
  and privilege escalation are restricted and could affect task semantics.
- Fail-closed audit of the final merged configuration for every production
  trial, including all mounts and capabilities; the helper alone is not an
  adversarial security audit.
- Production cleanup verification, phase-specific model access revocation,
  native provider-agent qualification and approved tracing destination.

The fixture checks normal completion cleanup, not all crash/failure paths.
No scored Stage 2 result or harness-quality improvement is claimed.

## Production gateway lifecycle increment

`scored_gateway.py` now implements a trusted session and private-socket server
entry point. All conditions use the canonical `scored_budget.sqlite`, with
$21.285 aggregate, $6.600 development and $14.685 final allocations. The
existing $1 setup allowance is separate and unchanged; no contingency is
automatically released. The approved estimated $0.055 trial admission is wired
to full-context aggregate reservations and a persistent underestimate halt.

Every dispatch checks current endpoint metadata, account credit and key
allowance. An exclusive process lock prevents overlapping scored sessions.
Trial directories are single-use, including after interruption; request,
response and billing receipt files are private, exclusive and flushed to disk.
Uncertain billing blocks the next trial. The server closes its socket and
revokes its session on normal interruption; Docker lifecycle integration must
still enforce agent-to-verifier revocation and crash cleanup.

Nine new tests use a synthetic provider, including an actual Unix-socket
startup/interruption check. No production ledger or paid request was created
by these tests. The gateway image, production Compose wiring and scored runner
remain unfinished; the presence of the entry point is not launch qualification.

## Combined production-layout fixture

`production_compose.py` wires the gateway, socket initialiser, isolated relay
and task-network guard. The task has no model-socket, key, token-file or ledger
mount. A separate relay in its network namespace serves loopback HTTP, allowing
non-root task processes without relaxing Unix-socket permissions. The gateway
uses a pinned-base image and hash-locked Python dependencies.

`production_runtime_probe_v4.json` passed 14 actual Docker checks: non-root
model roundtrip through the real session/estimator, enforced CPU/RAM, private
path absence, public metadata HTTPS, durable synthetic receipt, model-access
revocation while retaining task files, and container/network/volume removal.
The upstream provider was synthetic; no API generation occurred. Earlier
failed fixture attempts v1-v3 are preserved rather than overwritten.

Colima maps these Mac-owned private bind mounts to UID 0 inside the VM. The
gateway and relay therefore use container UID 0 with all capabilities dropped;
the task fixture remains UID 65534. Host ownership and 0700/0600 permissions
were not weakened. This is a verified host mapping, not a portable assumption.
The v3 test also exposed capability-name normalisation and merged stderr in
Harbor output; v4 corrects those assertions and tests graceful server shutdown.

`qualify_oracle.py` starts reference-solution qualification on the unchanged
frozen dev20. It checks all canonical dataset hashes, preserves existing
attempts and reward-zero outcomes, uses official CPU/RAM and timeouts, and
checks disk, thermal/performance and critical-memory signals before each new
task. A shared process lock excludes concurrent scored sessions. Reference
solutions/verifier logs remain local and are not policy-development inputs.
No model gateway or API key is attached to these reference runs.

Full dev20 qualification, production native-agent integration, protocol freeze,
tracing and scored evaluation remain required. Reference-solution results are
infrastructure evidence, not model scores or evidence of a harness win.

The initial `video-processing` reference attempt enforced its declared 1 CPU
and 2048 MB but raised `RewardFileNotFoundError`: this manual adapter omitted
the explicit agent/verifier log mounts supplied by Harbor's stock Trial.
The original attempt remains in `.runtime/stage2/oracle-dev20`. Revision
`explicit-log-mounts-v2` restores those mounts and uses a separate preserved
attempt directory `.runtime/stage2/oracle-dev20-v2`. This is an infrastructure
correction, not a retry of a known reward-zero result. Runtime inspection
confirmed both log mounts with unchanged task CPU/RAM. Qualification is not
complete until the reference run produces a valid verifier result.

The corrected video-processing reference run subsequently returned reward 1.0
in 124.063 seconds with its original resource/time limits and verified cleanup.
`oracle_qualification_progress.json` preserves this partial snapshot. The
remaining frozen sequence has been started sequentially; it is not yet complete.
All 138 automated tests passed for this runtime increment. No API credit was
spent and no scored model evaluation started.
