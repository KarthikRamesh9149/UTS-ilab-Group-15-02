# Baseline pre-acceptance transport correction, 2 October 2026

## Original source enclosure and separately bound R4, 3 October 2026

The human requested “Fix it properly pls” after the R3 failure. R3's one
qualification connection failed before acceptance at 04:23:05 UTC. The actual
native service failed with exit 1; its saved service and relay processes were
observed absent. No actual qualifier or paid repeat task started. R3 remains
terminal and must never be patched, resumed or reused.

Its retained schema-2 diagnostic contained seven source-site hashes. Resolving
them against the actual bound source led from the execution service/session
through `matched_repeat_original.authenticate` to the generic
`matched_repeat_locks.directories` guard. A bounded native observation then
reproduced that guard's rejection on the first original source input: the
original `stage2` directory is owned by UID 501/GID 50 with mode 0755, not by
the native root operator. The enclosing original root is root-owned 0700.
A separate read-only observation verified all 88 bound source hashes and exact
identities: 53 files retain 501:50 ownership and 35 are root-owned. All are 0600
or 0644, with canonical non-writable-by-group/others, ACL-free ancestry.
These are current native observations, not historical runtime-byte attestation.

The correction is limited to the original reader's source identity checks.
It requires the actual private operator-owned enclosing root, permits only the
current operator or the observed 501:50 source owner/group pair, and checks
canonical ancestry, restrictive modes, absence of ACLs, regular single-link
files, no-follow opens, pinned hashes, descriptor identity and final rereads.
Private evidence continues through the unchanged strict generic file reader.
The generic lock/file ownership guards are not relaxed. Authentication compares
identities across the actual collector; the under-lock recheck also compares
identities before and after its real reads. No original owner, permission,
source byte, result or archive is changed.

Local tests first reproduced the legacy-source refusal and missing enclosure
contracts. Tests use real temporary bytes, descriptors and locks; native
ownership and ACL observations are explicitly synthetic. They cover the
private enclosure, unrelated owner refusal, private-evidence exclusion, ACLs,
unsafe modes, symlinks, hardlinks, byte changes, file/parent replacement and
late recheck drift. Passing these tests does not establish native qualification.

The R3 preservation capture completed at 2026-10-03T05:49:27.824101Z, with
native final observation 05:49:22.465297Z. It reread all 436 installed inputs,
four installation metadata records, five terminal records, exact saved manager
invocation/process absence and the full installation tree metadata. The tree
has 18165 entries and SHA256
`894457077e0972b0b156f78f86ce7655381fb026c91c634abf05035bd000d4d9`.
The original baseline CSV is present with the required pinned hash. The proposed
R4 root was absent; no directory was created by this observation.

Use ONLY `/opt/uts-capstone-matched-repeat-terminus-2-20261003-r4` and exclusive
Mac installation/qualification/run state dated `20261003-r4` for the separately
bound corrected attempt. All three failed roots and all fifteen protected Mac
records are retained. Native preservation rechecks all three attempts, including
their exact source/input/record/tree identities, failed manager invocations and
saved process absence. Sessions use 61 Terminus / 64 OpenHands locks; installers
acquire 60 / 63 existing locks and create only their own three. The first 49
locks keep R6 order; the R3 locks follow the R1/R2 locks.

Fresh affected and full final-candidate tests, exact committed-source publication,
new exclusive installation, actual isolated native imports and actual native
qualification are still mandatory. Only the exact successful qualifier service
exit and fresh execution admission may precede the single paid Terminus run.
This amendment changes no provider/model/benchmark/deadline/spending policy.
The older R3 and R2 deployment instructions below are historical, not authority
to reuse those roots. Preserve all failures and keep the sequential reporting
and OpenHands gates unchanged.

## Missing original-baseline CSV and separately bound R3, 3 October 2026

The human again directly requested “FIX EVERYTHING AND RUN THE 2 BASELINE
TESTS”, then “then do it”. The following grounded input correction and separate
deployment continue that authority; the older R2 deployment sequence below is
historical and must not be executed again.

`matched_repeat_original._anchors` requires the original baseline's
`stage2/results/baseline-corrected-20260923/trials.csv`. Both baseline installers
omitted it from their exact payload inventories. The original-audit fixtures
created that file independently, so they did not detect the producer/consumer
gap. A new local contract failed for both installers before the correction.

One read-only native preservation capture completed at
2026-10-03T01:03:04.174230Z (native final observation01:03:02.067410Z).
It confirmed that this CSV is absent from the failed R2 filesystem, installation
input map and runtime inventory. It verified the actual failed service, both
recorded processes absent, all424 source bindings plus two private anchors,
all435 installed inputs, the same five terminal records, and four installation
metadata files. R2 tree metadata has18164 entries and SHA256
`ca78f3713389834724b0e98f0b7421c319c38d641d1049fcad1b83b9edac4abd`.
This establishes a current native missing-input defect, not the discarded
historical traceback or historical runtime-byte attestation. No existing
native bytes were changed, and no qualifier or benchmark was invoked.

Both installers now include and independently pin the exact CSV bytes at
SHA256`8769a865d19bc81132166d67f85a5fb84725f2cda8f5b2a45f98b1d9993d5429`.
Mac preparation checks agreement with the consumer's path/hash and rechecks
the file's identity through normal SSH completion. Missing bytes, altered bytes
with a recomputed caller hash, or same-byte file replacement refuse. No original
score is changed or merged; this is a prerequisite input, not a new result.

Use ONLY `/opt/uts-capstone-matched-repeat-terminus-2-20261003-r3` and exclusive
Mac installation/qualification/run state dated`20261003-r3` for the separately
corrected Terminus attempt. That root was observed absent by the capture;
installation must freshly require absence again. Neither R1 nor R2 may be
patched, resumed, removed or reused. OpenHands retains its still-unstarted
destination and remains strictly after completed Terminus reporting.

`matched_repeat_revision.py` now preserves BOTH failed attempts, including
their exact installation and terminal file identities, source inventories,
tree metadata, retained failed manager invocations and saved process absence.
All ten protected Mac installation/failure records are checked. Each native
preservation call rechecks both attempts before returning; any late drift
refuses. Both old roots' three existing locks precede the new baseline locks.
Terminus/OpenHands sessions hold58/61 locks; installers acquire57/60 existing
locks and create only their own three. The first49 locks retain R6 order.

The combined candidate requires fresh affected and full local gates after the
last bound source/protocol edit, publication with exact identities, ONE exclusive
installation, actual native imports and qualification, and the genuine successful
qualifier service exit before ONE paid89-task dispatch. Local tests and a
read-only capture are not admission. Preserve all failed evidence and every
original/recovery result/archive. No provider, model, benchmark, deadline, retry,
spending, signal, cancellation or scoring policy is changed.

## Subsequent local diagnostic correction

The corrected qualification connection also failed before acceptance. Its
`20261002-r2` root, records and installed sources are terminal evidence, not an
available deployment target. No actual qualifier or paid repeat task started.
The historical underlying exception was not retained and remains unknown.

The current local service correction addresses a confirmed information-loss
defect only: exact known exception types such as `AuditTransportError`,
`CalledProcessError`, `JSONDecodeError` and `FileNotFoundError` were collapsed
into `OtherException`. Future failure diagnostics retain allowlisted exact
type categories, validated child return codes and selected transport metadata.
They include at most eight chained exceptions and sixteen source-site hashes,
with bounded traceback traversal. A site hash is SHA256 of the bound source
SHA256, a colon and the decimal line number. It is a lookup hint, not proof of
executed-code identity. Unknown types and transport values remain redacted.
Messages, commands, stdout/stderr, raw paths, frames and locals are not saved.

The existing exclusive protected writer, terminal failure marker and disabled
resume/paid-readiness flags remain. Diagnostic collection failure falls back to
a fixed unavailable record without replacing the original exception. Local
tests cover redaction, exact types, bounds, the actual failure-file writer and
refusal to reuse the failed synthetic attempt. Native facts in those tests are
mocked. This does not recover the old exception or establish an execution fix.

This correction alone does not authorise a replacement root, installation,
qualification replay or paid dispatch. No existing native source or evidence
is modified. The earlier deployment sequence below is historical, not an
instruction to reuse either failed Terminus attempt.

## Authority and immutable history

The human directly requested: “Pls fix everything and start baseline runs once
everything is fixed.” This authorises a narrowly scoped transport correction
and the already planned sequential Terminus-2 then OpenHands 89-task baselines.
It does not authorise scored-key replay, merged/best-of scores, an extra
benchmark variant, model/provider changes, paid probes, account-limit changes,
payments, arbitrary native signals or cancellation.

The original Terminus installation at
`/opt/uts-capstone-matched-repeat-terminus-2-20260928` remains frozen at
`4ee7f6672629ec7b22304954ab274e2560c973f0`. Its ONE qualification connection
failed before durable acceptance; no actual qualifier or paid baseline task
started. That attempt remains terminal. Never overwrite, resume, delete or
relabel its local/native files, unit, root or result history.

The bounded read-only preservation capture ended successfully at
2026-10-02T10:36:27.412539Z, with native observation at10:36:25.305074Z.
It checked419 source bindings, two private anchors,430 installed inputs,
six exact terminal files, the actual retained failed unit, both recorded
processes absent, and the proposed corrected root absent. Its tree metadata
fingerprint has18160 entries and SHA256
`0f3537c1f903bad845cbc6fe947a8b7490d77518e4b05ad32878813aef112b5c`.
This is preservation evidence, not admission or historical runtime-byte proof.
The exact historical exception branch was not retained. Source and timing
support expiry of the pre-handoff transport window, not a fabricated traceback.

## Separate corrected deployment

Use ONLY `/opt/uts-capstone-matched-repeat-terminus-2-20261002-r2` for the
corrected first baseline, with new exclusive Mac installation, qualification
and run state dated `20261002-r2`. Its89 existing schedule keys remain unstarted.
No old installation, import probe or qualification is reinvoked. OpenHands
keeps its still-uninstalled original destination and must receive the same
corrected, committed source union before its first freeze.

`matched_repeat_revision.py` binds the actual old native installation metadata,
old419 source-map fingerprint,430 protected installed inputs, terminal files
and their exact decimal identity strings. It independently reads the retained
failed service and procfs, requires no old qualifier/image/registration/scored
or paid state, checks old stop markers and the entire pinned tree metadata.
The Mac side reads both original installation records and all three failed
connection records with actual protected-file checks. No credential contents
or old runtime payloads are read to claim historical attestation.

The bootstrap, each installer and actual under-lock session rechecks require
this preservation. Add the retired root's three existing locks after the
unchanged51 inherited installer locks, before the current baseline locks.
Terminus has55 session locks and OpenHands58; the first49 retain R6 order.
Installers acquire54 and57 existing locks, respectively, and each creates only
its own three new locks. Missing or held locks refuse; none are repaired.

## Duplex transport and completion

The new source-bound transport wraps, but does not modify, the authenticated
composite handoff bytes. Frames have a fixed distinct prefix, bounded data,
zero-length liveness and explicit completion. A reader exposes inner EOF only
after explicit outer completion and real descriptor EOF. Truncation, malformed
lengths, extra data, wrong prefixes and missing replies refuse.

The Mac owner performs every genuine fresh audit and SAME-archive handoff on
its original main thread. A transport-only thread sends liveness every30seconds;
it cannot invoke an audit, collector, provider, admission check or completion.
Native acknowledgement liveness similarly continues during real native
validation. Only the owning execution task can send the actual acknowledgement
after durable acceptance. The relay forwards both directions with bounded
buffers, so native liveness reaches the Mac even when a native audit temporarily
backpressures the archive stream. The bounded Mac reverse reader validates only
framing; the owning thread validates the exact original acknowledgement schema,
nonce, native process, source bindings and all predecessor archive identities.

The4500-second transport window bounds unresponsive waiting, not total healthy
audit duration. Genuine peer activity can sustain backpressured writes. No
benchmark deadline, setup limit, retry policy, context constraint or disclosed
million-turn guard changes. Liveness does not prove audit progress or success.
No transport layer retries or resumes an uncertain operation.

The still-unstarted Terminus and OpenHands completed-reporting paths use the
same framing in both directions. Their old single absolute receive deadline
is removed; each waiting read still has the same unresponsive window. A
transport-only reverse reader drains liveness during the owner's prerequisite
audits, with a two-chunk queue and bounded reader/consumer buffers. Metadata
validation, all archive writes and hashes, and strict verification remain on
the owner. Only after normal session exit, final rereads and the unchanged
inner commitment may the native owner emit outer completion. The Mac requires
both commitments, real EOF, normal SSH exit and strict complete archive checks.
No historical reporter or existing archive is changed, copied or repaired.

Readiness is consumed precisely through its newline so a coalesced following
transport prefix is neither discarded nor misclassified. Owned transport
threads stop before their descriptors are closed. Sender failure never emits
completion. After durable native acceptance a lost acknowledgement does not
cancel native work; the Mac retains uncertainty and must not replay it.

## Mandatory gates and reporting

Local owned-pipe/socket tests are not native qualification. Run the targeted
tests and the applicable full source-bound final suite on the final candidate.
Preserve frozen R6's318 sources, archived35 reporter sources, native reporting
payloads, original/recovery outputs, SAME verified archives and every failed
attempt. Commit only explicit task files; fetch/inspect before pushing and
verify both GitHub author and committer identities. Freeze the complete source
union during each native operation.

After those gates: ONE exclusive corrected installation, actual isolated native
imports, ONE real qualification handoff, its exact genuinely successful retained
service exit, then ONE89-task paid Terminus dispatch. Acceptance is not service
completion. Any failure or uncertainty is terminal and must be preserved and
diagnosed before a separately bound correction; no blind retries. Actual
Terminus89 audit, ONE backup/export and publication must precede OpenHands
installation/qualification/ONE89 dispatch. Preserve separate denominators.

Keep the SAME five-minute monitor and requested hourly reports active, with no
overlapping operations. The VPS stays active. No completion date is guaranteed;
the historic roughly51-hour pair estimate starts only when Terminus actually
starts, plus qualification, audits and reporting. Cancellation still needs
whole-project completion, verified off-server backups, no required jobs and
action-time irreversible confirmation.
