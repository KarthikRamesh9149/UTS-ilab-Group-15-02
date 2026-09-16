# Host translation correction: reference qualification remains pending

2026-09-16. The initial reference run had 15 passes, four zero rewards and one
timeout. Infrastructure-only inspection found:

- build-pov-ray: HTTP 403 download rejection, reference exit code 8.
- install-windows-3.11: segmentation fault during a build, exit code 2.
- qemu-alpine-ssh and qemu-startup: system-boot timeout indicators.
- regex-chess: official agent timeout; no reference log was produced.

All five images are amd64; the Colima daemon is aarch64. Before correction,
Colima had `rosetta: false` and registered `/usr/bin/qemu-x86_64` for translation.
Architecture translation is a plausible contributor, not a proven explanation
for every failure. The HTTP rejection may be independent of translation.

Under the user's installation authorisation, Apple's Rosetta installer completed
successfully (package version 1.0.0.0.1786586848). Colima was restarted using its
supported `--vm-type vz --vz-rosetta --cpus 4 --memory 10` configuration. No task
containers were running when it stopped. Registration now reports enabled with
interpreter `/mnt/lima-rosetta/rosetta`. No task definitions, CPU/memory limits,
timeouts, verifiers, model settings or harness policies were changed.

Official references:
- https://colima.run/docs/commands/
- https://lima-vm.io/docs/config/multi-arch/

The same frozen dev20 reference sequence is now requalified using
`qualify_oracle.py --rosetta-requalification`. It requires the actual Rosetta
registration and writes to a distinct private `oracle-dev20-rosetta-v1`
namespace. Existing QEMU reference results, including failures, remain intact.
This is an environment correction, not a resampled model trial or a new task
selection. No inference runs in this reference process.

The reference runner now preserves pinned images on cleanup, as the scored
runner does. Containers, networks and temporary volumes are still removed.
The original reference export still describes the original run; it must not be
mislabelled as the Rosetta outcome. No post-change qualification success is
claimed yet. Existing model compatibility proofs predate this host change and
must be rechecked before scored execution. Runtime admission alone does not
establish host qualification.

Immediately after restart: no running containers, approximately 26.8 GB host
free space. Standard 20 GB floor, memory and thermal checks remain enforced at
each reference trial boundary.

## Host identity admission safeguard

Runtime/live proofs now capture the Docker architecture, kernel, engine version,
CPU count and memory capacity, Docker context, macOS build and actual x86
translation registrations. Proofs must match the live host and the admission,
and the probe must verify that its host identity remained unchanged. Missing
host provenance is rejected; old proofs are retained as historical evidence,
not silently upgraded. Current registration confirms Rosetta enabled and
qemu-x86_64 disabled.

191 stage-two unit tests passed after adding host checks, followed by 12 focused
admission tests after requiring the explicit unchanged-host check. A single
`scored_runtime_probe.py --label rosettav1 --harness custom --rebuild-gateway --wait`
process is queued behind the active reference owner. It will make no model calls
and creates no containers until that owner releases the lock. No paid matrix is
queued. Initial post-change reference results: video-processing passed;
build-pov-ray remained zero. Remaining outcomes are pending, not assumed passes.
