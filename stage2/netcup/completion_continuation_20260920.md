# Completion amendment: verification and activation

This is technical execution evidence, not a final score or assignment report.
The user explicitly approved the scope in
[COMPLETION_AMENDMENT_20260920.md](../COMPLETION_AMENDMENT_20260920.md).

## Candidate verification

Commit `9384d8474708446965a8e8e18fb4fa10b78a9ac2` was pushed to
`codex/netcup-openrouter-study`. Both the Mac and an isolated native copy passed
585 Stage 2 tests, 34 custom tests, two graph-callback tests and 12 legacy tests:
633 total, with no failures, errors or skips. The native run had external
networking disabled. All 48 runtime source hashes matched across hosts.

The native check also verified 209 candidate files and 1,037 opaque dataset
hashes without inspecting held-out solution content or changing production.
Independent review passed 159 relevant tests plus three focused regressions.
Its missing-scored-ledger finding was corrected: registered liabilities cannot
disappear from native setup admission when the accounting database is missing.

The five known receipt flags were separately repaired as recorded in
[receipt_flag_repair_20260920.md](receipt_flag_repair_20260920.md). Neither
unknown request was settled, retried or assigned an invented charge.

## Deployment and registration

The exact committed source archive had SHA-256
`124b8bc2989e28f9e055fbf3c9d23a5bff30ec0bd09d7ce4f84615e34dc583af`.
Under all three ownership locks, the previous sources were backed up and the
candidate deployed. Both ledgers, model protocol, original v1 sidecar and all
six existing result files remained byte-identical. Thirty-four previously
retained admission/runtime/live-proof files also remained unchanged.

The new v2 registry SHA-256 is
`eb70ce9bf6b6e0ef96a42f36474e81921ce50cde18f4b83bb6ceba4b28ae4174`.
Native validation confirmed both exact unknown reservations, totalling
US$0.212992, and all six retained cells: four billing-verified, one pass, two
terminal-held zeros. None was eligible for a replacement development attempt.
The old `netcupv6p` admission correctly rejected the changed runtime.

Private activation proof SHA-256:
`030434a24612f46baafd4d6c5780da61b3b03b0fcf570ae4b979f05ebcf5c769`.
Deployment and registry activation made no model calls.

## Current execution boundary

At 02:45 UTC on 20 September, the persistent
`uts-stage2-qualification-netcupv7.service` was verified active with main PID
1008316. It rechecked the retained reference qualification and started fresh
source-bound runtime qualification against the rebuilt gateway. Its private
log is `.runtime/stage2/netcup-qualification-v7.log`.

The sequence requires the synthetic runtime check and actual Terminus-2,
OpenHands and custom model/tool checks to pass before building a new admission.
It then resumes only the missing first-20 development cells and stops for
the real systemic-failure review. Low scores alone do not veto continuation
under the amendment, but accounting, environment, cleanup and budget checks do.

Full final scoring remains 89 fresh tasks per baseline and 89 for the frozen
custom finalist. No full89 run, completed comparison or custom victory is
claimed by this activation checkpoint. Spending-PDF work remains paused.

## Subsequent qualification failure

The fresh synthetic runtime proof passed with zero live API calls. At
02:45:38 UTC, the first Terminus-2 setup request reached OpenRouter and received
HTTP 429 in 0.803 seconds. The persistent service exited with status 1 before
the other native checks, admission creation or another scored task.

- Setup attempt: `setup-native-terminus-2-netcupv7`.
- Request: `3616b453-6975-41a9-9626-7b302cfe0751`.
- Generation: `gen-1789872338-wxnouHXqX94vz0iHZds5`.
- Preserved evidence: response headers, transport diagnostic, reservation,
  request, timing, failed fixture result and native-live proof.
- No completion response or billing receipt was available. The first
  read-only generation lookup returned HTTP 404, as did the bounded follow-up
  at 02:57:08 UTC; this does not prove zero cost.
- The original setup ledger retains `charged=NULL`, state `pending`, and the
  full US$0.106496 reservation. It is not included in the two-scored-hold
  exception. Total unresolved reserved exposure is now US$0.319488.
- The fixture confirmed model revocation and removal of containers, networks
  and volumes, with no cleanup errors. The six scored outcomes remain intact.

At 02:53:27 UTC, read-only checks showed account credit US$12.015073652 and key
usage US$0.0212142, unchanged from the earlier snapshot. These aggregate numbers
are not a substitute for an authoritative record of this request's charge.
Known project-ledger charges remained US$0.02061936. No automatic retry,
additional hold exception or zero-cost inference was applied.

The supported reconciliation helper requires a durable matching completion
response, which this attempt lacks. A provider receipt or explicit provider
billing confirmation is required before a reviewed accounting correction can
release the unresolved reservation. Paid work remains stopped. Original failed
proofs and fixture results must not be overwritten or relabelled as successful.

[OpenRouter's error documentation](https://openrouter.ai/docs/api/reference/errors-and-debugging)
identifies HTTP 429 as rate limiting. This is distinct from invalid credentials
or insufficient credit; a top-up alone is not established as a fix.

Preserved native proof SHA-256 values:

- Synthetic runtime: `d0e69df139929972d7d8ddb3e13ac039bf2a7f2e5249c26c914ee00085b3f6d8`.
- Failed native Terminus proof: `0e85911bb53d1647bbf35842cfd23b6836762b79bbe4f7b20b41b6f844517e72`.
- Failed fixture result: `1c5bfe2f912d2b7c5197d1ad0b0d9be2cca5d9512071e75cc23fc12fda242c9f`.

The dashboard-only service-name change passed all 12 targeted tests. It does
not change any of the 48 paid-runtime source fingerprints or qualify the
failed live check. Existing spending PDFs and reports were not modified.
