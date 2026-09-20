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

## Native activation and zero-dispatch permissions correction

The historical sidecar was registered under all three ownership locks. Its
SHA-256 is `0b0d8f9419ab41f3b2f4cb7e4407e02a461de8b9f1b7d772385462755be43c92`.
The scored ledger, setup ledger and original result hashes remained unchanged;
the actual retained cell resolved to the explicit historical-held zero, still
with `billing_verified=false`. Registration made no model call.

The `netcupv6` full synthetic runtime check passed all checks with zero live
API calls. The subsequent Terminus setup stopped before its gateway became
healthy: the legacy scored ledger was mode 0644 inside its private 0700
directory, whereas the new cross-ledger guard requires the file itself to be
private. Exact-image, read-only, network-disabled reproduction identified this
specific failure. The paid-provider ledger stayed at 43 setup requests and
three scored requests, with no new reservation or charge. Docker cleanup was
verified. The original failed setup proof is retained, not marked passed.

Only `/opt/uts-capstone/.runtime/stage2/scored_budget.sqlite` was changed to
mode 0600. Both ledger byte hashes stayed unchanged. Repeating the read-only
check in the same gateway image then returned the correct retained liability,
0.106496. No source, prompt, model setting, task input or budget changed.

Fresh live setup attempts use the explicit `netcupv6p` label after that
configuration correction. They reuse the successful `netcupv6` synthetic
proof because its exact sources, host and image are unchanged. A new admission
may be built only if all three live checks pass. The persistent service is
`uts-stage2-qualification-netcupv6p.service`; its private log is
`.runtime/stage2/netcup-qualification-v6p.log`. It then runs only the first-20
Terminus block and stops for the actual evidence review before expansion.

## Live qualification passed and scoring resumed

All three corrected live fixtures passed every required check: native tool
execution, exact model settings, receipt/usage reconciliation, metadata trace,
runtime identity and cleanup. Costs below are setup costs, not benchmark scores.

| Harness | Calls | Input tokens | Output tokens | USD |
|---|---:|---:|---:|---:|
| Terminus-2 | 2 | 1770 | 519 | 0.00015354 |
| OpenHands | 3 | 20415 | 236 | 0.00126738 |
| Custom C0 | 2 | 6463 | 304 | 0.00044250 |
| Total | 7 | 28648 | 1059 | 0.00186342 |

The cumulative original setup ledger was $0.00923412 after these checks.
`admission_netcupv6p.json` was built from the passed proofs and independently
validated against current native-host sources and images. Model fingerprint
remained `b9f42d3bcc9a4f416bcaaf8ee0f175d96a2bbd493943c64199d46e671719e27f`.

The same persistent service then resumed the first-20 Terminus block, retained
the original terminal-held zero, and started the untouched `build-pov-ray`
cell. An in-progress task has no score yet. Qualification, comparisons, the
finalist freeze and fresh final evaluation remain subject to their existing
evidence and funding requirements.

## Separate development snapshot exporter

The new host-side `export_development.py` collects the five primary fixed-20
conditions only (100 planned cells, diagnostics excluded), under the existing
nonblocking matrix lock. It validates canonical evidence and admission without
editing the runtime, dispatching a task or changing source admission. Partial
conditions have no pass rate; unstarted cells are not counted as failures.
Unknown full costs, token totals and incomplete liabilities remain unknown,
separate from known subtotals. The original held zero and exact evidence hashes
are preserved. C2's parent must match audited C0/C1 selection.

All 14 reporter tests passed, and independent review cleared the corrected
candidate. Full local suites then passed 461 Stage 2 + 30 custom + 2 graph +
12 legacy = 505 tests. The new reporter is not a paid-runtime source change;
the previously verified 491-test native runner and live admission remain
unchanged. No additional native test load was introduced during timed scoring.

The next reporting-only extension adds all three recorded phase durations:
setup, agent and verifier. It exports observed subtotals and measurement
coverage separately from complete-condition totals. Missing/null measurements
remain unknown, malformed/nonfinite/negative values are rejected, and a known
duration on the historical held trial does not imply known billing. All 18
targeted reporter tests passed locally after this extension; the 47 frozen
runtime hashes were rechecked against `admission_netcupv6p.json` and matched.
Native reporter tests and the actual export wait for the matrix lock to be
free so that reporting work does not contend with timed benchmark execution.
