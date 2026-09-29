# Separate recovery policy and gateway

This component implements the lightweight private-input contracts for the
already approved [three-cell plan](custom_setup_recovery_20260929.md). It does
not authenticate a host, perform a native audit, read an archive, qualify,
register, dispatch or create any production input. Structural validation of
saved metadata is never proof of those operations.

## Fixed inputs and lineage

The seven recovery-only private inputs contain the exact credit policy, fixed
plan, original full89 manifest, original final qualification, original evidence
binding, new qualification and new three-cell registration. Their names use
`no-cutoff-recovery-`; no original or baseline input is overwritten or accepted
as a recovery registration. Pure builders write nothing and retain
`paid_launch_ready:false`. The original 89-result hash map, retained snapshot,
same archive, backup record, reporter revision and three public outputs are
pinned. The audit digest excludes only `collected_utc`, allowing a genuinely
fresh successful audit to bind the same immutable evidence across qualification
and paid sessions. The future live reader must actually audit, check freshness
against the retained snapshot and compare every other field. This stable digest
neither performs nor authenticates an audit, and is never a saved live witness.

Only original tasks 63, 64 and 65 have fresh `customrecovery1-c0-nc-` identities,
in the fixed order. The original denominator remains 89; recovery remains a
separate three. There is no score input, pass floor, best-of choice or automatic
replay. The plan digest and baseline schedules are unchanged.

The prospective source inventory retains every original final source. Only
`scored_trial.py` may have an explicit new orchestration hook; agent, prompt,
tools, preparation, shared lifecycle, retry, model, trace and old evidence code
must remain identical. This component makes no such hook change. New component
and unchanged import-helper bindings are current controls, not historical
additions to the original211 or archived35. Import-closure inspection also found
five original regression module names and six unchanged helper imports outside
that original inventory. Their actual current bytes are explicitly included;
this does not establish their historical installed bytes. Future host/service/producer files
must be added and byte-bound before their actual native qualification/freeze.

## Qualification contract, not qualification execution

The metadata requires the original C0-NC candidate and execution contract,
model/provider/sampling, original dependencies, Python archive, host metadata
and unchanged guard image. A new gateway image must have a full immutable ID
and both actual image-build producer hashes. Metadata matching does not inspect
an installed image or establish current runtime compatibility.

Native qualification must run the original final regression modules plus the
new recovery modules, with zero skips/errors/failures, then six actual fake-model
native lifecycle cases: tools, preparation not applicable, returned nonzero,
raised execution exception, setup cancellation and cooperative boundary stop.
These are harmless qualification fixtures, never benchmark retries. Each must
retain the real setup observation inside its result, bind its canonical hash,
and corroborate it against the actual result/trace/accounting bytes. All fourteen
regression/lifecycle producer files and both image-build producers are required.
The real qualifier must reread these bytes; `checks:true` cannot replace them.

The nonzero/exception/cancellation cases must prove no model request and no
agent/verifier execution. Tool/stop cases must prove the original graph/tool
roundtrip and unchanged shared transient recovery. Revocation, owned cleanup,
official resources, actual setup observation and no raw diagnostic retention
are mandatory for every case. Missing diagnostic evidence is never repaired by
replaying a started task or fabricating an observation.

## Runtime gateway behaviour

The reader opens only the seven fixed input names under a canonical private
runtime directory, using directory-relative no-follow descriptors. Files must
be owned regular single-link mode0600; the runtime is owned mode0700. Duplicate
JSON fields, nonfinite numbers, unexpected schema fields and bool/int changes
are refused. The original qualification and manifest additionally require their
exact pinned original file bytes, not merely canonical JSON equality. File bytes
and identities are reread after structural validation.
These checks do not replace the future native protected-root/ACL/source/import,
service, ancestor-lock, live-session and actual producer/image checks.

The gateway remembers the raw input bytes and identities, not just canonical
JSON. It checks before each physical provider call, including shared retries.
A refusal permanently invalidates that gateway object; restoring a file cannot
revive it. Inherited exclusive accounting directories and the gateway lock
remain, preventing same-key gateway restart and overlap. Host-level durable
start/result/prefix checks are still required to prevent task replay or another
attempt through a new process.

`RetrySession`, passive accounting, actual provider credit/authentication/model
identity constraints, cancellation/revocation, official deadline and shared
Retry-After behaviour are unchanged. No spending, request-count, iteration,
preparation retry or speculative package/network repair is added. Unknown cost
remains unknown. An operator boundary stop must still finish the current task;
the future host, not a new mid-request gateway stop, owns the next-cell gate.

## Unfinished native route

The actual original audit and same-retained-archive handoff must complete before
the full ancestor locks. The exclusive new root/input set, current runtime and
installed images, process/main-thread/async-task live session, trusted service,
real qualifier, scoped scored hook, sequential dispatcher and separate completed
audit/one-backup/export remain required. No component test or saved metadata
grants paid launch. No recovery native root, service, registration or attempt
has been created by this component.
