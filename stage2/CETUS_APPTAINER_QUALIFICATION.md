# CETUS supported Apptainer qualification

Date: 17 September 2026. Outcome: **diagnostic completed; full study not admitted**.

This was an actual PBS compute-node test, not a documentation-only assessment.
No model-generated commands, scored benchmark tasks, model requests or external
inference requests were used. No privileged configuration was changed and no
previously denied network mode was retried.

## Execution and provenance

- PBS job: `89281.hpc-head01`, `smallq`, compute node `hpc-exec02`.
- Requested allocation: one CPU, 2 GB RAM, eight-minute walltime.
- Scheduler records: start 11:34:05, finish 11:34:27 (scheduler-displayed time),
  `Exit_status = 0`. Exit zero means the diagnostic finished, not that its
  capability checks passed.
- Probe: `cetus_apptainer_qualification.py`, submitted with the adjacent PBS file.
- Benign fixture image: `docker://python:3.12-slim-bookworm`.
- Resulting SIF SHA256:
  `fc533f8f121a97009cfef74088c6c5f851658ca6b522152eabb12bbb56ada73b`.
- Private raw result retained on CETUS in the preflight job's
  `apptainer-capabilities-89281.hpc-head01/result.json`, with a local copy at
  `.runtime/cetus-apptainer-89281-result.json` (gitignored).
- Raw-result SHA256:
  `5a64924d9e3b2320098ca0c2669def8c96818c19e88c621d1854b9ea8ff39522`.

The fixture image was fetched by tag and hashed afterwards. It is not a pinned
benchmark task image, and this probe makes no task-equivalence claim.

## Results

| Mode | Start | Resource enforcement | Narrow fixture outcome |
| --- | --- | --- | --- |
| Ordinary user, explicit limits | Rejected, exit 255 | Cgroups v2 unified mode required | Not run |
| Fakeroot, explicit limits | Rejected, exit 255 | Rootless cgroups unusable in fakeroot mode | Not run |
| Fakeroot, no explicit limits, network none | Started | Not verified; effectively unlimited observed values | Listed checks passed |

The explicit limit request was `--cpus 1 --memory 512M --pids-limit 64`.
Apptainer reported these failures:

```text
cannot use cgroups - system is not configured for cgroups v2 in unified mode
cannot use cgroups - rootless cgroups is not usable in fakeroot mode
```

The running offline fixture and the PBS process were in the same observed v1
controller paths, `/system.slice/pbs.service`, with:

```text
memory.limit_in_bytes = 9223372036854771712
cpu.cfs_quota_us = -1
cpu.cfs_period_us = 100000
pids.max = max
```

CPU affinity exposed all 24 CPUs. The probe did not stress memory or CPUs and
did not use that visibility as permission to consume unallocated resources.
These observations do not rule out every PBS monitoring or accounting control;
they fail to establish the hard per-task limits required by our admission gate.

The offline fixture passed the following specific checks:

- Synthetic controller environment secret absent; `/shared/homes`, the checked
  controller home path, and the standard Docker socket path absent.
- Mount, PID, network and IPC namespaces differed from the controller.
- IPv4 route table empty; loopback socket bind succeeded.
- A synthetic file persisted between separate instance exec calls.
- An in-container one-second timeout interrupted a five-second sleep.
- Instance stop succeeded and subsequent exec was rejected.

Fakeroot reported a root-mapped namespace without a subordinate UID mapping.
Container UID 0 does not mean host-root privileges. The controller-path test
checked the default home path, not every possible host path. A missing socket
at one standard path is not an exhaustive socket exposure audit. Empty IPv4
routes are not a complete IPv6 or egress audit. The timeout check did not prove
arbitrary descendant cleanup. These checks are deliberately narrower than a
full adversarial sandbox qualification.

Failed-start logs included fuse-overlayfs cleanup warnings, including a failed
unmount message for the limited fakeroot attempt. Neither failed start left a
listed instance, and subsequent exec was rejected. Those checks are not an
exhaustive process/mount-leak audit. The successfully started fixture stopped
with exit zero. Scratch evidence was retained; no broad deletion was performed.

## Tests and decision

Four probe helper tests passed locally and with CETUS Python 3.6. PBS shell
syntax checks passed. Full local suites passed: 282 Stage 2 tests, 30 custom
dependency tests, 12 pilot tests (324 total). Mock helper tests and the trusted
fixture are not benchmark results or proof of general sandbox safety.

**Do not start the 89-task study from this evidence.** The supported resource
flags failed on the compute node, and network-none is not yet qualified against
the canonical tasks. The existing earlier bridge denial remains in force.
Resource and runtime-semantic requirements must not be silently weakened.

Model qualification job `89247.hpc-head01` was still queued in `med_gpuq` after
this probe finished; it was left unchanged. No duplicate GPU job was submitted.
No UTS support message was sent. A supported isolated runtime with demonstrable
resource enforcement remains necessary before scored execution.
