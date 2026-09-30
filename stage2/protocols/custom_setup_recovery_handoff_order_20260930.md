# Recovery handoff startup ordering, 30 September 2026 UTC

This amendment changes orchestration only. The fixed recovery plan, three new
keys, order, separate denominator, C0-NC agent/tools/model, original preparation
and official allowances remain unchanged. No paid attempt has started.

## Retained r4 failure

Revision `0ddd5f673633ea367a4be1ddc3da3c833ed648cd` was installed exclusively
into `/opt/uts-capstone-custom-no-cutoff-recovery-20260930-r4` at 05:17:51 UTC.
The actual source-bound import check passed at 05:20:46. One qualification
connection began at 05:21:51 and returned BrokenPipeError at 05:28:15.
The service failed before handoff acceptance, qualifier intent, image build,
regression execution, lifecycle rehearsals or paid tasks.

Read-only checks at 05:32:21 and the complete retained inventory at 05:39:23
verified the exact failed unit invocation, exit1/MainPID0, absent service/relay
processes, all 326 installed source/input bindings and five additional private
connection files. The 87-byte service log contains only a fixed failure status,
not the historical exception or traceback. Its SHA256 is
`3f767f4ee721f508fb2c9f7d5be320b4a48cff70b6b5c332d42259fe09ca22c6`.
Both failure-marker hashes are
`18b4e2cd7bbdac03f8672e6946eea24e6b8031ce5164d711f28e2e7f991f542d`.
Installation source/input-map SHA256 is
`34242e32cf1fb1b3cba96ddbfb2a8f6e75741c65817b2fce4c5c15894c253e75`.

The exact static entry prerequisites passed independently at 05:34:06 after
the sender's audit ended. Source inspection shows a scheduling race: after
receiver-ready the Mac must perform its fresh original audit, while the native
session previously checked that no process occupied the original root before
reading the sender's header. The unchanged original guard correctly refuses
that concurrent audit process. A deterministic local real-pipe test reproduces
this ordering failure and passes after the correction. This establishes the
code defect, not the unavailable historical r4 exception or exact cause.

## Corrected ordering

The pinned bootstrap still checks actual inactive original/retired services,
procfs, protected complete source/private bytes and loaded origins before
receiver-ready. The sender still performs a fresh actual completed original
audit and strictly reads the SAME existing original archive on every handoff.
It cannot emit the header until these finish. The receiver now waits for that
bounded header, then performs the full actual ancestor/stop checks before
archive authentication, witness creation or locks. Header/readiness metadata
alone never grants authority. Truncated headers refuse; an actual post-header
active/stopped ancestor still refuses before archive verification/native audit.

Both original audits, full archive verification, final commitment/EOF,
same-process/main-thread/async-task witness ownership and under-lock final
rereads remain mandatory. The archived 35-file original reporter/guard is
unchanged. No saved audit, precomputed witness, guard bypass, archive recreation,
task replay or new financial/model/request/retry ceiling is introduced.

The recovery completed-reporting transport now has the same strict readiness
barrier: exact fixed root/mode/commit/source-binding metadata must arrive after
the native bootstrap checks and before the sender begins its original audit.
This fixes an equivalent race before the later ONE recovery backup/export.
Readiness is not an audit, backup, qualification or paid admission.

New service failure diagnostics retain only a fixed stage and allowlisted error
class with non-admission/no-resume flags. Unknown subclass names become
OtherException. No message, stack, task payload, command output or model
exchange is serialized; files are exclusive/private and cannot be replaced.

## Exclusive corrected location

Only `/opt/uts-capstone-custom-no-cutoff-recovery-20260930-r5` can receive the
corrected frozen sources. The installer must freshly prove absence and all
45 existing ancestor locks before exclusive creation. The live session holds
46 locks; its scored/gateway locks stay owned by the unchanged trial lifecycle.
Mac installation state ends `20260930-r6`; inspection/qualification/paid
operation states end `20260930-r5`. Existing r1/r2/r3/r4 roots, failures,
source/runtime identities, manager invocations and Mac operation states remain
strictly pinned and are never restarted, patched, removed or reused.

Local tests remain local evidence. Actual new-root absence, installation,
committed fresh handoff, native regressions and all six isolated fake-model
cases remain required before registration or the three paid attempts. Any
uncertain/failed operation is retained and inspected without automatic retry or
native signalling. The VPS and explicit hourly progress notifications stay on.
