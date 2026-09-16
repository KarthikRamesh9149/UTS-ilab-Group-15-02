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
