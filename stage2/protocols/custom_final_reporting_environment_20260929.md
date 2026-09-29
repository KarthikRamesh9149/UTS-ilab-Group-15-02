# Completed-final reporting import environment, 29 September 2026

## Retained version-2 outcome

The approved 28-file installation at revision
`2fbdc93892ee7189f11d84103edf577948488e7e` succeeded at 12:34:30 UTC in
`/opt/uts-capstone-custom-no-cutoff-final-reporting-20260929-r2`.
Its one audit began at 12:35:13 UTC and failed at 12:35:39 UTC. The native
ValueError occurred at 9.862414 seconds, SSH exited 1, and the transport elapsed
time was 16.353344 seconds. No stdout or unrecognised stderr was returned.
The bound traceback reached report.collect line310 then _context line88:
the exact environment/absent-cache guard, after reader preload but BEFORE
collector lineage authentication, ancestor locks or the 89-row audit.
This was not the transport timeout or a successful completed audit.

The private version-2 audit directory retains only intent.json/failure.json.
At12:37:27 UTC a read-only check verified PID 1155311 absent, all 234 native,
28 version-2 and 21 original reporter bindings, completion/protection evidence,
and absent reporting backup state. Both installed roots and every earlier
failure remain intact. This correction never retries or replaces either root.

## Diagnosis and its limits

A local isolated import reproduced two added environment keys, without printing
their values: OPENROUTER_API_KEY and TIKTOKEN_CACHE_DIR. Native source inspection
at 12:43:47 UTC found LiteLLM 1.101.0 importing dotenv by default, and assigning its
bundled tokenizer directory to TIKTOKEN_CACHE_DIR. Installed python-dotenv 1.2.3
supports PYTHON_DOTENV_DISABLED. Native inspection read ONLY .env path metadata,
not credential contents. These observations explain a reproducible import
environment hazard; the failed audit did not retain the exact native variable
delta, so that delta and the causes of the older failures are not invented.
Starting a process with env-i alone did not prove it stayed credential-free.

Guarded native import observations at 12:45:48 and12:47:09 UTC preserved the
proposed environment, with no credential-file read, collector or native write.
The diagnostic effect guard blocked urllib3's import-time IPv6 capability bind;
the library handled that refusal. This is disclosed, not presented as an
unmodified full runtime audit or evidence of a provider request. The production
credential/environment guard below does not suppress that capability probe.

## Version-3 reporting-only contract

The NEW exclusive root is
`/opt/uts-capstone-custom-no-cutoff-final-reporting-20260929-r3`.
No frozen execution source, result, qualification, service, permission, library
or benchmark setting changes. The user has authorised needed routine in-scope
corrections; this is not permission to erase failures, replay tasks, change
scores, pay/topup, or cancel the VPS. There is no automatic retry loop.

The fixed reporting environment adds LITELLM_MODE=PRODUCTION,
PYTHON_DOTENV_DISABLED=1, and the exact existing bundled tokenizer path. It
contains no provider credentials. These controls are set BEFORE any project
reader imports, never by clearing unexpected variables afterward. The exact
environment must remain equal before and after imports, before lineage, and at
the final evidence boundary. A same-value tokenizer assignment is harmless;
new keys, changed values, deletions or credential-file reads are refused.
The in-process audit hook latches refusals even if a library catches them.
It is defence in depth, not an OS sandbox or a hook inherited by child processes.

The three actually inspected library control sources are separately pinned,
read before project imports/deployment writes, checked at their actual loaded
origins, and reread at final boundaries. They are CURRENT reporting dependencies,
not a full installed-library manifest or historical paid-execution attestation.
Their real bytes join the supporting-file map and the private archive; the
strict snapshot/public projection retain the separate environment contract and
these limitations. The original 211 qualification/source set is unchanged.

Unchanged lineage readers inherit the disabled dotenv controls through their
existing environment propagation. They keep their own original interpreters,
source checks, collectors, time bounds and ancestor locks. No old reader is
patched and no saved result is substituted for a fresh actual audit.

The same fixed environment and source checks are used by actual audit, backup,
export and native-handoff callers. Project import closure, loaded-source checks,
manager/procfs/protection, lineage-before-lock, full locks, official limits,
accounting, cleanup/revocation, true absence and 182 historical-result rereads
remain mandatory. Missing verifier outcomes and unexecuted phases stay null.

## One-shot state and sequence

`no_cutoff_final_environment_audit.collect(full_commit)` owns only the NEW
`.runtime/netcup/custom-no-cutoff-final89-environment-audit-20260929` directory.
Existing/partial state refuses reuse. It preserves all earlier state and saves
a snapshot only after full native return, schema validation and local rereads.
Audit/backup/handoff transport bounds remain 1800/2700/4500 seconds, not benchmark
deadlines or native service runtime caps. Native children are never signalled.

Local checks and import observations are not a completed audit. A reviewed,
tested, committed candidate must pass fresh protected deployment/import checks
before its new one-shot installation/audit. Actual completed audit, ONE verified
private backup, allowlisted export and push remain prerequisites. Recovery 63-65
and fixed Terminus-2/OpenHands repeat sequencing remain separately authorised
and separately reported, with no score merging or guaranteed outcome.
