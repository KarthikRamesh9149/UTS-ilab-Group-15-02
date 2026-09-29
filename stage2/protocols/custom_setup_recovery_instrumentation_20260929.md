# Recovery-only setup observation

This is the implementation companion to the already fixed
[separate three-task plan](custom_setup_recovery_20260929.md). It changes no
task, attempt identity, agent, prompt, model, tool, preparation command,
repository repair, signature check, resource allowance or phase deadline.
The original diagnosis and its published bytes remain historical evidence.

## Implemented component, not execution admission

`no_cutoff_recovery_setup.PreparationObservation` is a single-use observer for
the existing `prepare_environment` callback in the unchanged shared lifecycle.
The future recovery host constructs it and passes its `prepare` method to that
lifecycle. It calls the original `task_preparation.refresh_package_metadata`
once through an environment proxy. Only that original function's exact root
context and exact command with its existing 180-second timeout can reach the
environment. There is no second command, fallback, install, upgrade, retry,
package-specific repair, output-based remediation or shorter deadline.

The original preparation source is pinned to SHA256
`fb1cf6c9e3a6ee79579de2ebcbfd0f97cac39e989000bbb77b20a00f114b6815`.
Its command's UTF-8 SHA256 is
`ce4b19308a2c727d159110d218fb6a8d5492d1f3842b2156d3e9fc9500fc2d76`.
Source bytes, the actual original function's code/origin/globals, and current
observer/test/protocol bytes are checked before execution, immediately before
the command, after execution and before metadata is returned. Reads require
canonical regular single-link files with before/after identity checks. These
component checks do not replace the future launcher's protected-root,
pre-import/loaded-module, native runtime and source-inventory guards.

The observer has no CLI, root override, file writer, provider client, model
credential access, task loader, registration or paid-launch entry. It holds no
native admission scope. Its in-memory single-use guard does not provide durable
no-replay protection across objects or processes; the actual future scoped
dispatcher must independently enforce that protection against retained state.
It cannot be copied, pickled or moved to another process/thread. The callback
binds the real setup child task created by the existing lifecycle; the owning
parent can read completed metadata afterward. No host admission handle is
moved into another task by this component.

## Retained metadata and limits

The observation distinguishes context creation/entry/exit, command execution,
command binding refusal and preparation-result handling. It preserves the
actual original return or raised exception, including cancellation and process
exit exceptions. Context suppression/replacement semantics remain unchanged.
Diagnostic capture failures are latched as incomplete metadata, not substituted
for the original task outcome. Source failures before execution refuse before
an environment command; source changes observed after execution or during a
later metadata read cannot be restored into a complete observation.

Only fixed metadata fields are returned: stage, allowlisted exception class,
an integer command return code when actually available, monotonic elapsed
times, and returned stdout/stderr UTF-8 byte counts and hashes. Arbitrary error
subclass names use `OtherException`; messages, arguments, stacks, output text,
task payloads and model exchanges are never returned. Diagnostic field access
does not invoke result properties, stringification or serialisation methods.

Output counts/hashes describe UTF-8 re-encoding of the returned text, **not**
original process-wire bytes. Empty text is a measured zero-byte output; a null,
missing, unsupported or non-encodable value has null count/hash with an explicit
observation label. Missing fields or diagnostic capture failures prevent a
complete observation. Chunked hashing has no total output-size truncation or
new command-output allowance; the existing environment's output handling is
unchanged. Command elapsed time covers its awaited execution, excluding output
hashing. Callback-body elapsed time includes observation work inside the body
but excludes the observer's surrounding source reads. Neither replaces the
shared lifecycle's actual setup-phase duration or its unchanged 900-second
allowance. Observation overhead remains inside that allowance.

A returned nonzero code is classified only as `preparation_command_nonzero`.
Even exit 124 does not prove a timeout. An actual `TimeoutError` from execution
is labelled `command_timeout_exception`, without asserting a network, mirror,
SSH or other lower-level cause. Other execution/context errors have broad
fixed categories; unknown stays unknown. No output-text classifier exists.
The metadata always says `paid_launch_ready:false`,
`native_qualification:false` and `historical_cause_established:false`.

`validate` checks the exact metadata schema, fixed preparation/command identity,
null/type/elapsed relationships and derived categories. It does not authenticate
a producer or prove that any saved observation was actually executed. It must
never turn self-consistent JSON into admission.

## Remaining integration and native requirements

This component is not wired into `scored_trial.py`, a gateway, a dispatcher or a
native service yet. The original runner, lifecycle, preparation and all frozen
roots/reporters are unchanged. No recovery root, qualification, registration
or attempt is created by the local implementation or its tests.

The separate recovery policy/gateway, actual host/runtime and live original
audit/archive handoff, same-scope service/qualification/scored admission,
sequential dispatcher and separate completed reporting/backup/export still
must be implemented and source-bound before launch. The real host must attach
and durably retain the completed observation with the exact new trial even when
preparation raises or is cancelled. No missing/incomplete observation may be
silently accepted or replaced with an invented one, and an already started
attempt must never be replayed to repair diagnostic evidence.

Actual isolated native regression tests and fake-model lifecycle rehearsals
must exercise the successful/not-applicable path, returned nonzero, execution
exception, setup cancellation and cooperative stopping; genuinely produced
diagnostics, result/trace/accounting bytes, revocation and owned cleanup must
be reread. Local fake-environment tests exercise the real observer and shared
phase engine, not Docker/native compatibility, paid provider behaviour or
production qualification. The fixed original archive is only reread by a
future actual authenticated handoff, never recreated or expanded.
