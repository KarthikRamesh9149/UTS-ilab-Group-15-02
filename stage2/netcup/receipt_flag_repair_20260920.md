# Offline receipt verification maintenance, 20 September 2026

This is technical execution evidence, not a spending report or a benchmark
score. The five already-settled requests in
`dev-terminus-2-05-reshard-c4-data` had retained matching provider receipts but
their ledger receipt-verification flags were still pending.

The reviewed `verify_retained_receipts.py` maintenance helper passed 14 tests
on the Mac and all 14 on the native host in a network-disabled namespace.
Independent review verified identity, exact charge, provider-native token
counts and non-BYOK/non-cancelled receipt evidence. Normalised token counts
are not substituted for the provider-native counts. A length-limited billed
completion remains valid billing evidence, not a benchmark success.

Before application, all ten native response/receipt hashes and the original
result/ledger hashes matched the preserved stopped archive. A private SQLite
backup was retained. Under the matrix, scored-run and gateway locks, one
transaction verified only the five explicitly named settled receipt rows.

Verified native outcome:

- Exactly five receipt-check flags changed from pending to verified.
- Every other accounting table was semantically unchanged.
- Both unknown requests remain pending with NULL charges and their full
  combined 212,992,000-nanodollar reservation.
- All six existing task-result file hashes remain unchanged.
- No generation, provider lookup, network access or paid runner launch occurred.
- This operation does not register the new hold amendment or admit execution.

Evidence fingerprints:

- Original ledger: `9eb1a8b631c55b48c2018317c0835683175484e41a42fa3686dd12b39e988484`.
- Repaired ledger: `e73f33d1e1411161310f43398d35f30f59aacf2c67d21a2d56f64ace692a4522`.
- Private native repair proof: `f06964c86a9353c90b4b7933012eb23483c8977f5c6d50eff33129d31595c016`.
- Applied helper: `f325e45e5adf699b11fec761631fbddb12eb46974a1016a4ea06e47f2e8dad02`.

The old archive and reports remain intact; none is rewritten to reflect this
later maintenance operation. Fresh source-bound runtime qualification remains
required before scoring resumes.
