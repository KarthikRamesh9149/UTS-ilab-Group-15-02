# Native continuation verification, 20 September 2026

This checkpoint is technical evidence, not the assignment report, final scoring
or proof that the custom harness beats a baseline.

## Tests

The candidate transport diagnostics, private dashboard deployment and actual
readback implementation passed the following suites on both the Mac and the
native Netcup host, using their existing Python 3.12 environments:

| Suite | Passed on each host |
|---|---:|
| `unittest discover -s stage2 -p 'test_*.py'` | 389 |
| `unittest discover -s stage2 -p 'custom_*_tests.py'` | 30 |
| `unittest stage2/local_graph_callbacks_tests.py` | 2 |
| `unittest discover -s tests` | 12 |
| Total | 433 |

Stage 2 tests use `PYTHONPATH=stage2`. These exercise synthetic responses and
local libraries, not paid benchmark accuracy. The first remote test connection
stalled after reporting the 389-test suite; no test process remained remotely.
The other three suites were rerun through a bounded SSH connection and returned
success. No model request was made by these test runs.

Source review checked error-field allowlisting, private diagnostic creation,
single upstream dispatch, retained unknown reservations, loopback dashboard
bindings, content-pinned images, exact readback identity/metric matching and
rejection of missing/duplicate observations. This was direct review, not an
independent third-party audit. No old runtime admission was silently refreshed.

## Actual Langfuse service evidence

Langfuse health returned HTTP 200 with version 4.38.0. All six services were
started from the pinned inventory in `langfuse_image_inventory_20260919.json`.
Only 127.0.0.1:3300 and 127.0.0.1:3390 were published. Verified metrics:

| Setup fixture | Events | Model calls | Input tokens | Output tokens | USD |
|---|---:|---:|---:|---:|---:|
| Terminus-2 | 8 | 3 | 2,798 | 748 | 0.00022188 |
| OpenHands | 7 | 2 | 13,357 | 225 | 0.00055392 |
| Custom | 7 | 2 | 6,314 | 229 | 0.00029334 |
| Total | 22 | 7 | 22,469 | 1,202 | 0.00106914 |

The live API matched exact event sets, parent/trial identity, constant-model
metadata, tokens, charges, recorded phase durations and fixture rewards. Each
fixture reward was one. These are lifecycle fixtures, not the 20 development
tasks. No dashboard screenshot or visual UI inspection is claimed. The failed
scored trial's incomplete trace was not made artificially complete or exported
as a successful trial.

After verification, all six dedicated observability containers were stopped,
without deleting their data. No benchmark container or matrix remained active.

## Private recovery backup

Private archives on the Mac:
`.runtime/netcup/verified-checkpoint-20260920-CPr8GR/`.
Both files are mode 0600 inside the private directory and are Git-ignored.

| Archive | Bytes | SHA-256 |
|---|---:|---|
| `stage2-runtime.tar.gz` | 2265413 | `7f1398adb8d0a73f08035b4b533cad81d11ae1dcc9a4111343682875cd63ebd0` |
| `langfuse-cold-volumes.tar.gz` | 70849391 | `e39ba2c5842e6f0d09c82a81e671da63f6fb541625c4b7b79e4e32248ae83559` |

The runtime capture held the matrix, trial and gateway ownership locks. The
dashboard archive contains its five dedicated volumes after all services
stopped. Both gzip streams and tar listings passed integrity checks. A full
database restore has not been exercised. These are recovery archives, not a
code-free public handoff bundle; they contain private configuration/logs and
must not be uploaded to GitHub.

Archived SQLite bytes match the source host exactly:

- Setup ledger: `39cb007839f4829e44e90451779dd1681723624e27dd9101756f6d894aedac00`.
- Scored ledger: `4504d4289a06643ee93d1690502d7d8b978ff9e20c0cb75fa56440d95fb34359`.

The original failed result retains its recorded SHA-256, reward zero and
unresolved status. The 19 September 19:18:47 UTC read-only account recheck
reported the same $12.028551872 balance and $0.00773598 key usage. No missing
charge was inferred from that aggregate equality. Billing recovery still
requires the specific provider record described in `BILLING_RECOVERY.md`.

The rental has not been cancelled: the study is incomplete, and stopping Docker
services does not stop the recurring server charge.
