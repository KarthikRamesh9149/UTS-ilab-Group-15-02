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
