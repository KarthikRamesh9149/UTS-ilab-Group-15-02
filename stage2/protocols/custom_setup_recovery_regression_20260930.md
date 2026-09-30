# Linux qualification test isolation correction

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
