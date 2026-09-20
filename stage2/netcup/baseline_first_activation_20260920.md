# Baseline-first continuation: verified deployment

This is technical execution evidence, not a completed benchmark score or the
assignment report. It implements the user's explicit direction to finish both
89-task baselines and continue past unresolved provider billing while retaining
the full liability. See the [amendment](../DEFERRED_BILLING_AMENDMENT_20260920.md).

## Verification and deployment

Commit `17f342a6d7ed504ee487f2bc11d78a5e2c15cc02` is pushed to
`codex/netcup-openrouter-study`. The final candidate passed **721 tests on each
host**: 673 Stage 2, 34 custom-agent, two graph-callback and 12 legacy tests.
There were no failures, errors or skips. Native tests ran in an isolated copy
with external networking disabled. Independent review cleared the corrected
accounting, registration, replay prevention and final-export paths.

The native final verification summary has SHA-256
`6099683ade0000594c9225cfc91b82179119d345ea25d372c835f8bb003f5582`.
All 283 candidate file hashes were checked. The 41-file committed deployment
archive has SHA-256
`224d5089dfc3ca835176379eb3b529756043d82e13ab40545d444621cabff612`.

Deployment acquired the matrix, scored-trial and gateway ownership locks,
verified no active study service or container, backed up replaced sources and
installed only those 41 allowlisted files. Twelve protected files, including
both ledgers, the model protocol, historical hold registries and all six scored
results, remained byte-identical. No provider calls occurred during deployment.
The private deployment after-proof has SHA-256
`46fe04721690f580c69f20c1372541b2bf0f87c183ce03e83acfd873945335b4`;
all 36 replaced source backups were copied off-server and hash-verified.

## Additive accounting activation

At **04:00:47 UTC, 20 September 2026**, the approved standing policy and the
closed `setup-native-terminus-2-netcupv7` registration were activated. The failed
setup result and all prior results/ledger bytes remained unchanged. The old
attempt was not replayed, and its US$0.106496 maximum charge remains reserved.
Together with the historical scored holds, unresolved liability is US$0.319488
at this activation checkpoint. This is not confirmed spending.

- Standing policy SHA-256:
  `26301b5c9dbb9585d5da8f950da4762f9449836af70ba2b7018133f3d3990a92`.
- New setup registration SHA-256:
  `65571d606e91ff391ac310f083abaec3c5728344c662ef3346ab2d13e1f93897`.
- Off-server private activation proof SHA-256:
  `a933017e48d63a604e67b56ff258e429185de496dc4d574feb551a3afaa2bfb4`.

Unknown costs remain unknown, full exposure stays in the original caps, and
the US$2 reserve remains enforced. This permits a new scheduled task, not a
retry of a genuine failed task or an efficiency claim from incomplete costs.

## Live execution and remaining scope

At **04:01 UTC**, `uts-stage2-qualification-netcupv8.service` was confirmed
active with PID 1019812. Its private log is
`.runtime/stage2/netcup-qualification-v8.log`. The fresh synthetic full-runtime
check passed with no live model calls and all resource/cleanup checks true.
Actual Terminus-2, OpenHands and custom model/tool checks must also pass before
the new source-bound admission can resume the 14 missing initial Terminus tasks.
The six existing development results are retained, not rerun.

The fresh Terminus-2 live check subsequently passed every required check,
including an actual model/tool roundtrip, receipt-matched billing and cleanup.
Its two requests cost US$0.00019314, with 1,752 prompt and 617 completion tokens.
This is setup evidence, not a scored benchmark task. OpenHands and custom
qualification were still pending at that observation.

At **04:09 UTC**, all three actual harness checks had passed and
`admission_netcupv8.json` existed. Terminus-2 and custom each used two requests;
OpenHands used three. Total receipt-matched setup cost for these seven requests
was US$0.00131724. The same persistent service then resumed the first missing
scored cell, `dev-terminus-2-06-install-windows-3.11`, without replacing any of
the six prior outcomes. This is actual resumed scoring, not full-89 completion.

After the initial 20-task systemic review, `run_baselines.py` is the next
priority: exactly **89 Terminus-2 + 89 OpenHands final tasks**, registered before
dispatch. Those same 178 results will be retained in the final comparison;
custom development then uses only the fixed 20 tasks, followed by 89 new tasks
for one frozen custom finalist. Non-development baseline outcomes must not be
used to tune the custom harness.

At this activation checkpoint neither full-89 baseline had started. Software
tests and successful setup fixtures are not scored benchmark successes. The
background continuation is enabled, and the progress panel separates these
states. No spending PDF, assignment report or final ZIP was generated.
