# Historical billing hold: implementation verification

Recorded 20 September 2026. This is implementation evidence, not a benchmark
score, the assignment report or proof of a custom-harness win. The prospective
methodology change is disclosed in
[ACCOUNTING_AMENDMENT_20260920.md](../ACCOUNTING_AMENDMENT_20260920.md).

## Executed tests and independent review

The same final candidate passed these suites on both the Mac and native Netcup
server using their existing Python 3.12 environments. No paid API calls were
made by these tests.

| Suite | Passed on each host |
|---|---:|
| Stage 2 `test_*.py` discovery | 447 |
| Custom `custom_*_tests.py` discovery | 30 |
| Local graph callback tests | 2 |
| Legacy `tests` discovery | 12 |
| Total | 491 |

The 47 runtime-source hashes matched exactly between hosts. An independent
read-only review inspected the exception validator, atomic reservations,
cross-ledger funding, immutable trial disposition, qualification consumers,
strict new receipt/usage evidence and unchanged final-evaluation requirements.

Review identified and implementation corrected three concrete gaps: scored
dispatch must check unresolved setup billing; setup dispatch must reject any
unknown scored request beyond the single registered hold; an amended runtime
must not treat a lost setup ledger as clean accounting. Startup and per-request
regressions cover these cases, including private-file and dangling-symlink
checks. The final review found no remaining actionable issue in its scope.
This is not a guarantee against all possible defects.

Reviewed final implementation hashes:

- `scored_gateway.py`: `a0e89ebdd8f4701aa3bccad328356cae5e3671b997431f7eef5a81b2dd545f78`
- `native_setup_gateway.py`: `366012a0aa54c9857b05b2adec51d4b5ad72b9643b8d2c96f828e355b3cf2a24`
- `historical_hold.py`: `209e275eec986657db587fefd0847d3208b46260aed832a06f95d4bf94292232`

## Evidence integrity and operational boundary

The validator also passed against the exact archived ledger, original result
and all 14 pinned request-evidence files, without substituting production
hashes. That read-only validation left the archived ledger byte-identical.

The candidate does not convert the original failed trial into a verified
result. Its charge remains unknown and its full $0.106496 reservation remains
held. New trials must independently reconcile their receipts and usage. The
original gate stays distinct from an explicitly labelled accounting-bounded
continuation decision; performance thresholds and financial limits are not
lowered.

These tests and review do not replace live provider qualification. The old
`netcupv5` admission is preserved and cannot admit this changed code. Fresh
source-bound synthetic and real-model harness checks are required before the
remaining first-20 Terminus block. Full baseline and final scores are not
established by this document.
