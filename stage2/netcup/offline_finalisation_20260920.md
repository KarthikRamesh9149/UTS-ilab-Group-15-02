# Offline finalisation corrections, 20 September 2026

Implementation commit: `2a91cd8`, branch `codex/netcup-openrouter-study`.
These corrections were completed while the native v7 setup request remained
rate-limited with unresolved billing. They made no provider calls and changed
no benchmark outcomes, limits, model settings or financial records.

## Corrected selection provenance

`finalist_freeze.py` now accepts only the canonical registered C0/C1/C2
development cells. It binds the three original block registrations, current
admission, runner hash, limits and C2 parent. Each stored systemic review must
independently clear the existing review gate. Valid differences in review notes
or attribution are permitted, as they are by the development runner.

The independent review caught and corrected an initial implementation that
unnecessarily required identical review prose. No development result or
registration was rewritten to satisfy the new checks. No real finalist exists.

## Code-free local handoff implementation

`final_handoff.py` freshly reaudits all 267 final cells before creating a ZIP
under ignored `output/final-evidence/`. Its exact allowlist contains the four
audited export files, a technical README, a source-hash/model-settings manifest
bound to the audited final registration, and member checksums. A separate
completion marker records the archive hash. Partial outputs cannot claim
completion; existing outputs and symlinks are rejected.

No real final archive was generated. Only synthetic temporary test archives
were exercised. No source code, private review text, raw logs, hidden verifier
content or credentials enter the archive. No upload, publication, spending PDF
or assignment report action is part of this command.

## Verification and deployment boundary

Both the Mac and an isolated native Linux candidate passed 653 tests:
605 Stage 2, 34 custom, two graph-callback and 12 legacy tests, with zero
failures, errors or skips. Independent focused review passed 70 related tests
and reported no remaining actionable findings. The Linux test namespace had
external networking disabled and launched no Docker container.

All 211 candidate-file hashes and 1,037 opaque canonical-data hashes were
verified. All 48 paid-runtime hashes remained identical to deployed commit
`9384d84`; these offline changes alone do not require new paid qualification.
The stopped production checkout, ledgers, protocol, admission and hold registry
were unchanged by the isolated tests. These new finalisation modules are
committed and native-offline tested, not yet deployed to production.

- Final native overlay SHA-256: `eea9ea41f5dfe24fd2e0118f2dfb1ac37fd0bbcf878b5de664911dcc3153c497`.
- Candidate manifest SHA-256: `16b2d675a2c87167d6211d72e020b5afb83e1d5c1ab228b16be1e3274e8e3fff`.
- Before/after production verification SHA-256: `ccbe0419ef42e01118c8dcd0e5289b7db1e322d3f92c26cfc532b33630fc91e2`.

The existing v7 setup billing failure still prevents paid resumption. The
03:00 UTC read-only receipt lookup again returned 404; the service was confirmed
failed with no live containers. Retain its original evidence and reservation.
Passing these tests is not a benchmark score, completed comparison or custom win.
