# Linux qualification test isolation correction

## R5 Linux symlink fixture correction and new R6 location

The r5 installation at `07661d7fcbecfb6a01d6b123780f0d1888f34800`
succeeded at 06:06:31 UTC on 30 September 2026. The actual installed import
check passed at 06:09:45. Its one qualification accepted the real original
audit/SAME-archive handoff and completed image build/verification. The actual
native regression child ran 826 tests in 866.962 seconds: 824 passed, two
errors, no failures or skips. Qualification failed at 07:22:43 UTC before
all six lifecycle cases, registration or paid work. This is not qualification
success or a benchmark outcome.

The two errors are AttributeError in the process-identity test fixtures.
Their global os.readlink mock assumed a Path argument. Linux realpath passes
str while resolving the genuine virtualenv interpreter symlink, so the mock
failed before the intended assertions. A local real-symlink reproduction
produced the same two error classes. This was not a recursion error.
The corrected mock intercepts only the exact synthetic procfs cwd/exe entries
and delegates every other path to the original os.readlink. The expected
executable is resolved before mocking. A real chained-symlink regression
executes both original test bodies. Production process/ownership/executable/
cwd/start-tick checks and all benchmark behaviour are unchanged.

Actual local pipe/socket tests also exercise qualification acknowledgement
before a still-running operation completes and paid-operation-body cleanup
after client acknowledgement loss, using synthetic bodies and real handoff/
session transport. They do not establish why r5's Mac acknowledgement was
missing. The native handoff was accepted; the Mac connection instead timed
out and retained failure at 07:34:41 UTC. Its exact acknowledgement-loss cause
remains unknown. No native process was signalled or restarted.

Read-only complete inventory at 08:00:17 UTC verified the exact failed unit
`uts-recovery-qualify-aa6e9b58cac893f63450d7fac8dbd0f9.service`,
invocation `590b186ef537475bb697bfd2489d5d14`, exit1/MainPID0, absent
service/relay/root processes, 327 installed source/input bindings, all 14923
retained file identities, 3148 directories and three image identities.
The source/input-map digest is
`681aaa459251d15f773fe891141ce91c7104d1f0c412dd92c361f3f12d238ec6`.
The native regression summary/log, accepted/failure records, original
installation and exact private Mac states are pinned in the revision reader.
The observed virtualenv bytecode file is retained, not deleted or presented
as historical installed-library proof. Credentials/runtime payloads were
identity-only in this inventory; no archive, collector or provider was called.

Only the new prospective
`/opt/uts-capstone-custom-no-cutoff-recovery-20260930-r6` can receive this
corrected committed candidate. The installer must prove actual absence and
all 48 existing ancestor locks before exclusive creation. The live session
holds 49 locks. Mac installation state ends r7 and operation states end r6.
Every r1-r5 failure/root/image/operation is preserved. No saved local pass,
accepted handoff or previous image build grants new qualification/admission.
All native regressions, six actual isolated lifecycle cases and actual
producer/source/image/host rereads remain required before the same three
fresh separately reported attempts. Recovery remains 0/3 and both baseline
repeats remain unstarted.

The following r3/r4 checkpoint is retained history, superseded above where
it describes the current location or readiness.

This changes test isolation and the exclusive prospective execution location,
not the three approved recovery attempts or benchmark behaviour.

## Actual failure

The r3 installation at `7596aaed36f1a41b0d382d732a44ce392ada569b`
succeeded on 30 September 2026 at 03:30:36 UTC. Its single qualification
handoff authenticated the fresh original audit and SAME retained archive.
The actual gateway build and installed-image verification passed at 04:10:11
UTC. The actual isolated native regression child then ran 806 tests in
267.840 seconds and reported 238 errors. Qualification failed before any of
the six lifecycle cases, registration or paid task. Local success before
deployment did not establish Linux qualification.

The first failing test called the fixed library inspection entry expecting a
non-native-context refusal. On the actual qualified Linux interpreter that
assumption was false. The inspection entry installed its permanent effect
guard and changed its bytecode prefix, then the deliberately invalid binding
raised FileNotFoundError. The guard contaminated the shared unittest process;
later synthetic filesystem/process/socket tests and the final bootstrap
context check refused. This diagnosis uses the actual retained test names and
source frames, not benchmark payloads or inferred preparation failures.

The correction explicitly supplies an unqualified context in negative tests.
They assert no guard installation or environment/cache mutation. An isolated
child simulates the otherwise valid Linux/root/interpreter context and checks
that later temporary-file work is unaffected. The separate real C0-NC
constructor child still runs under the actual effect guard. Production guard,
source checks, original preparation, prompts, tools, model and limits remain
unchanged apart from the new fixed location.

## Preserve failure and use one new installation

The r3 unit is `uts-recovery-qualify-7f1c3287f20e1ee133e07336ac901ee0.service`,
invocation `e9ea53fbea8c470e816a4cb122d7ff54`. Read-only inspection at
04:41:33 UTC verified failed/exit1, MainPID0 and absent service, relay and
regression processes. Only the verified owned Mac SSH client was closed;
the Mac operation ended at 04:41:56 UTC. No native signal was sent.

The failed regression log remains 581652 bytes with SHA256
`e06fe0acb2c1e77c66e9250991844a7db1fcc003425ac607891284f43b84e821`.
The actual failed qualification, image result, operation and exact private Mac
states are independently pinned. At 04:51:15 UTC read-only inventory checked
the 325 installed source/input bindings, extra evidence files, empty test
directory and three image identities. The observed additional virtualenv
bytecode file is retained and hash-bound, not deleted or presented as an
installed-library attestation. All r1/r2/r3 roots and original evidence remain
untouched. The reader rechecks manager/process/image state before final
protected tree/byte/identity reads; changed or extra evidence refuses.

Only `/opt/uts-capstone-custom-no-cutoff-recovery-20260930-r4` may receive
the corrected committed installation, after a fresh actual absence check.
The installer requires all 42 existing ancestor locks; the new live session
holds 43, leaving its scored/gateway locks to the unchanged lifecycle.
The private Mac installation destination ends `20260930-r5`; qualification,
inspection and paid operation destinations end `20260930-r4`. Every existing
or partial state is terminal. No old operation is restarted or overwritten.

The fixed three keys/order and separate denominator remain unchanged. The
fresh original audit and retained archive must again be authenticated before
the complete lock chain. Actual native regressions, all six isolated lifecycle
cases and genuine producer rereads must pass before paid execution. Recovery
is still 0/3; the original 89 remain 50 passes, 36 verified zero-score failures
and three setup-only missing verifier outcomes. Both baseline repeats remain
unstarted. This document and local tests are not native qualification.
