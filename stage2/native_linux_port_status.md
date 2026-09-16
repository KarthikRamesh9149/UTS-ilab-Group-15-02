# Native Linux host identity: partial portability work

Host identity collection now supports native Linux x86-64 with a local Unix
Docker endpoint, without requiring macOS, Colima or translation registrations.
It records Docker architecture/resources/version/kernel, context/endpoint and
the Linux client kernel/architecture. ARM and remote-endpoint configurations
are rejected by this native path; conflicting Docker host overrides fail closed.

This is identification, not host qualification. It does not bypass runtime
isolation, resource admission, reference task checks or live-model proofs.
The existing macOS identity representation remains unchanged. The runtime
source hash changes, so earlier admission proofs cannot authorise paid runs
of the changed implementation.

Current access checks found only local Mac Docker contexts. GitHub Codespaces
inspection returned HTTP 403 and reported missing `codespace` scope; that does
not prove no Codespace exists. No scopes were added, host purchased or created,
account changed, cluster restriction bypassed, or API credit spent.

The Linux path has mocked unit coverage, not verification on a real Linux host.
Other Mac-specific health/resource/bridge assumptions still require a full
portability audit and actual runtime qualification once a compatible host is
available. This change does not make the current Mac a qualified scoring host.
