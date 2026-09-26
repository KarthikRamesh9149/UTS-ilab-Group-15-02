# Custom harness setup checks

26 September 2026. The native setup passed; paid custom tasks have not started.

- Local tests: 954 passed, one pre-existing skip; 34 legacy custom tests passed.
- Server tests: 120 passed.
- Real Docker rehearsals: C0, C1, C2-on-C0 and C2-on-C1 passed with a synthetic model. They checked command execution, verification, retry recovery, traces, access revocation and cleanup.
- Paid API calls: zero. The new deployment has no real API credential yet.
- All 178 original baseline result hashes are unchanged.

The first rehearsal caught a tokenizer-cache symlink that Docker's mount validator rejected. We replaced it with a real directory in the new deployment and retained the failed setup evidence. No scored task was replayed.

The qualified source is `da9b4a8a58f89465f6eb8850081252e08be0e0cf`. Machine-readable checks and bindings are in [summary.json](summary.json). Runtime and model settings are described in the [protocol](../../protocols/custom_corrected_candidate_20260926.md).

The custom runner has no project/task spending cap, reserve or artificial call-count ceiling. Official task limits and actual provider credit, authentication and identity checks still apply. It cannot buy credit automatically.

These checks do not establish accuracy or a win. Next is registered development on the same fixed 20 tasks as the saved baseline comparison: Terminus-2 14/20 and OpenHands 10/20. Change one design lever at a time, retain every attempt, and freeze the finalist before the full custom evaluation.
