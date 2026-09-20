# Read-only live progress panel

Run locally with the existing environment:

```sh
PYTHONPATH=stage2 .tools/stage2-custom/bin/python stage2/progress_dashboard.py --port 8769
```

Open `http://127.0.0.1:8769/` on the same computer. The page refreshes every
five seconds; its background reader checks allowlisted Netcup trial metadata
over the existing pinned SSH connection at most once per minute. It does not
make model or billing API calls, open accounting ledgers, or start/resume runs.
Only the page and sanitised status endpoint are served. The server binds to
loopback, not the public network. Stop its owning process when no longer needed.

The panel separates:

- Each **full 89-task baseline**, Terminus-2 and OpenHands.
- The initial 20-task Terminus qualification block, which does not fill the
  full baseline bars.
- Each custom development variant, without combining favourable task results
  across variants, and the separate fresh 89-task frozen custom evaluation.
- Attempted cells, valid results with verified billing, and actual passes.
- Live metadata timestamps, manually maintained engineering checkpoints, and
  dated financial observations.

No arbitrary overall project-completion percentage is shown. Failed SSH reads
retain the last snapshot and mark it stale; a current connection to a stopped
runner is explicitly labelled stopped, not running. Genuine zero rewards count
as results, not passes. Setup fixtures and earlier local-model pilots are not
counted as current benchmark scores. This panel is an operational view, not the
final independent accounting/benchmark admission audit.

Update `progress_status.json` only with verified engineering facts. Its custom
condition selectors remain null until a development condition/finalist is
explicitly selected under the study protocol. Setting a panel selector does
not freeze an agent or authorise a run. When the runner service changes, update
the monitor's fixed service reader and its tests so it does not describe an old
service as the current one. Never place credentials, prompts, responses or raw
task logs in this file.

## Verification checkpoint

On 20 September 2026, 11 offline panel tests passed. The final local candidate
passed 526 Stage 2 tests (including those 11), 34 custom tests, two graph tests
and 12 legacy tests: 574 total. The corresponding core candidate without this
Mac-only panel passed 563 tests in an isolated, network-restricted native copy.
These tests are not benchmark task passes.

Live read-only SSH verification at 02:10 UTC matched six initial Terminus
attempts, four valid billing-verified outcomes, one pass and two unknown outcomes;
the known qualification service was failed/stopped. Browser accessibility and
visual inspection confirmed separate 0/89 baseline bars, the 4/20 valid-results
bar, an amber stopped label, and explicit dates. The page's time display uses
the viewer's locale. The running local panel polls metadata only; no benchmark
was restarted by this verification.
