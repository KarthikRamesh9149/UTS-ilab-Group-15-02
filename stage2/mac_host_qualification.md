# Mac host qualification — 2026-09-16

User authorised moving task execution from CETUS to the Mac, conditional on
resource qualification. Model, tasks, budgets and scoring remain unchanged.

## Read-only findings

- Physical Mac: 16 GiB RAM, 10 logical CPUs.
- No macOS thermal/performance warning; memory free percentage 43 at inspection.
- Host data volume: approximately 28 GiB available; preserve the 20 GB floor.
- Active Docker context: local Colima, aarch64, 2 CPUs, 4094447616 bytes RAM.
- Docker supports memory and CPU quota limits and cgroup v2.
- Docker data filesystem: approximately 12 GiB free.
- 21 of the 89 task declarations exceed current VM CPU or memory capacity.
  Maximum requirements: 4 CPUs, 8192 MB RAM, 10240 MB storage per task.
- Six unrelated Orchestra containers are running: worker, web, API, TLS,
  PostgreSQL and Redis. No containers were stopped or changed.
- Docker reports about 16.78 GB reclaimable build cache. This is an estimate,
  not guaranteed host-space recovery; unused layers may belong to other work.

## Status and next gate

NOT QUALIFIED for the full study. No images pulled, no VM restarted/resized,
no cache/volumes deleted, and no model calls made by this inspection.

Candidate remediation requires explicit approval to interrupt Orchestra and
remove only unused build cache (never volumes, images or project files). Then
verify recovered host space, increase VM resources with adequate host headroom,
and qualify amd64 emulation/image behavior and isolated Docker networking.
The remediation is not a promise the 16 GiB Mac will pass all89 qualification.
Keep official task limits intact; do not score capacity failures as agent failures.

## Approved remediation completed

2026-09-16: User explicitly approved stopping the six Orchestra services,
resizing Docker and deleting unused build cache. All six containers were
gracefully stopped. Their `unless-stopped` restart policies were left unchanged.
Colima was restarted with 4 CPUs and 10 GiB RAM; Docker reports 10404311040 bytes
usable memory. No disk resize, architecture switch or Rosetta installation.

Unused build cache was removed. The first prune lost its connection during the
VM restart; a second prune completed with 0 B remaining. Docker reports zero
build cache. No accurate first-prune total is available. Host free space rose
from about 28 to 48 GiB; Docker filesystem free space rose from 12 to 27 GiB.
All pre-existing image IDs and volume names were compared before/after and
remain present (297 images, 71 volumes). No project files were deleted.
Deleted cache is regenerable through future builds, not restored from trash.

After restart: no running containers; macOS memory free percentage 39, no
thermal/performance warning. Orchestra intentionally remains stopped while
benchmark preparation continues. Restore those six named containers after
benchmark work; do not restart unrelated previously stopped containers.

A disposable cached ARM64 Node container passed a deterministic capacity smoke:
`cpu.max=400000 100000`, `memory.max=8589934592`, no host home or Docker socket
visible, and unauthenticated OpenRouter public metadata returned HTTP 200.
The container was removed after exit. No key was supplied and no inference ran.
This verifies configured limits, not a sustained 8 GiB load test, amd64 image
compatibility, network isolation from host/private services or all-task readiness.

Next gate: qualify the real Docker/Harbor task boundary and architecture, finish
the gateway and billing integration, then perform the bounded model probes.
