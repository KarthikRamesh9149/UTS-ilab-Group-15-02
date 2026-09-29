"""Strict amended metadata and existing-archive verification, never admission.

No writer, network, native collector, extraction, deployment or dispatch entry.
The future trusted caller still owes a fresh native audit and authenticated
off-server handoff. Valid JSON, matching bytes and the returned metadata cannot
prove those actions or replace the live predecessor witness.
"""
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile

import no_cutoff_final_phase_audit as phase
import no_cutoff_final_report as report

KIND = 'c0_nc_final89_reporting_environment_archive_v3'
CHUNK = 64 * 1024
# Parser window for the five pinned metadata anchors, not a task/model limit.
ANCHOR_WINDOW = 64 * 1024 * 1024
EXCLUDED = frozenset({'token', '.env', '.jwt_secret', 'id_ed25519', 'id_rsa', '__pycache__', '.DS_Store'})
SNAPSHOT_FIELDS = frozenset({'kind', 'condition', 'registration', 'qualification_sha256', 'sources',
    'bindings', 'supporting_file_sha256', 'absent_paths', 'directory_entries', 'reporting_source_files',
    'amendment', 'amendment_sha256', 'reporting_dependencies', 'reporting_environment', 'preserved_result_files', 'service', 'model_protocol', 'policy',
    'rows', 'aggregates', 'collected_utc', 'audit_checks', 'completed_final_audit', 'paid_launch_ready',
    'off_server_backup_verified', 'archive_export_and_handoff_integrated'})
RECEIPT_FIELDS = frozenset({'kind', 'sha256', 'compressed_bytes', 'files', 'bytes', 'excluded',
    'snapshot_sha256', 'reporting_sources_sha256', 'absent_paths_sha256'})
COUNTS = ('model_requests', 'accepted_model_responses', 'interrupted_requests', 'error_requests',
    'other_unaccepted_requests', 'unknown_cost_requests', 'http_429_requests', 'transport_error_requests',
    'retry_records', 'known_input_tokens', 'known_output_tokens', 'generation_timings', 'missing_generation_timings')


def _name(value):
    if (not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.\-/]+', value)
            or PurePosixPath(value).is_absolute() or str(PurePosixPath(value)) != value
            or any(p in ('', '.', '..') or p in EXCLUDED for p in value.split('/'))):
        raise ValueError('Normalised non-credential archive name required')
    return value


def _map(value):
    if not isinstance(value, dict) or not value:
        raise ValueError('Nonempty exact file bindings required')
    for name, sha in value.items():
        _name(name); phase._hash(sha)


def _same(actual, expected):
    # Equality alone accepts True == 1 and 1 == 1.0. Bound JSON must not.
    if phase.fingerprint(actual) != phase.fingerprint(expected):
        raise ValueError('Exact amended metadata binding differs')


def _utc(value):
    report._utc(value)
    return datetime.fromisoformat(value)


def reporting_sources():
    """Current local reporting bytes, not retrospective execution attestation."""
    root = Path(__file__).absolute().parent.parent
    if (Path(report.__file__).absolute().parent.parent != root
            or Path(phase.__file__).absolute().parent.parent != root):
        raise ValueError('Use one separately bound reporting source bundle')
    files = {}
    for name in report.REPORTING_FILES:
        phase._file(root, 'stage2/' + name, files)
    trace_root = Path(phase.local_trace.__file__).absolute().parent.parent
    phase._file(trace_root, 'stage2/local_trace.py', {}, expected=phase.FROZEN_HELPERS['local_trace.py'])
    return files


def anchor_hashes():
    return {**{phase.RT + name: report.INPUTS[name] for name in (
        'no-cutoff-final-qualification.json', 'no-cutoff-final-matrix.json', 'no-cutoff-final-runtime.json')},
        **report.HISTORICAL_INPUTS}


def _anchors(raw):
    if not isinstance(raw, dict) or set(raw) != set(anchor_hashes()):
        raise ValueError('The five exact original metadata byte strings are required')
    for name, sha in anchor_hashes().items():
        if (not isinstance(raw[name], bytes) or len(raw[name]) > ANCHOR_WINDOW
                or hashlib.sha256(raw[name]).hexdigest() != sha):
            raise ValueError('Original metadata bytes differ from their pinned hashes')
    proof, block, host = [phase._loads(raw[phase.RT + name]) for name in (
        'no-cutoff-final-qualification.json', 'no-cutoff-final-matrix.json', 'no-cutoff-final-runtime.json')]
    _same(phase.fingerprint(proof), phase.QUALIFICATION)
    _same(phase.fingerprint(block), phase.REGISTRATION)
    _same(phase.fingerprint(host), proof['runtime_identity_sha256'])
    _same(phase.fingerprint(proof['sources']), phase.SOURCE_SET)
    _same(proof['sources_sha256'], phase.SOURCE_SET)
    _same(block['sources_sha256'], phase.SOURCE_SET)
    _same(block['qualification_sha256'], phase.QUALIFICATION)
    if any(proof['sources'].get(n) != h for n, h in phase.FROZEN_HELPERS.items()) or len(proof['evidence_files']) != 8:
        raise ValueError('Frozen helpers and all eight original producers required')
    _map(proof['sources']); _map(proof['evidence_files'])
    old = list(csv.DictReader(io.StringIO(raw[report.BASELINE_CSV].decode('utf-8'))))
    stopped = phase._loads(raw[report.STOPPED_JSON])['rows']
    preserved = {}
    for base, rows, count in ((report.BASELINE, old, 178), (report.STOPPED, stopped, 4)):
        if len(rows) != count or len({r['trial_id'] for r in rows}) != count:
            raise ValueError('All original178 and stopped-four bindings required')
        preserved[str(base)] = {phase.RT + 'scored-trials/' + r['trial_id'] + '/result.json': r['result_sha256'] for r in rows}
        _map(preserved[str(base)])
    return proof, block, host, preserved


def _inventories(directories, absent):
    if (not isinstance(directories, dict) or not isinstance(absent, list)
            or any(not isinstance(n, str) for n in absent) or absent != sorted(set(absent))):
        raise ValueError('Exact ordered inventory and absence sets required')
    for name in absent: _name(name)
    for name, entries in directories.items():
        _name(name)
        if (not isinstance(entries, list) or any(not isinstance(n, str) for n in entries)
                or entries != sorted(set(entries))
                or any(not re.fullmatch(r'[A-Za-z0-9_.-]+\.json', n) for n in entries)):
            raise ValueError('Exact unique sorted JSON directory inventory required')


def _row(row, limits, collected):
    if not isinstance(row, dict) or set(row) != report.ROW_FIELDS:
        raise ValueError('Exact allowlisted amended row required')
    if _utc(row['started_utc']) > _utc(row['completed_utc']) or _utc(row['completed_utc']) > collected:
        raise ValueError('Ordered actual UTC timestamps required')
    if row['reward'] is not None and (type(row['reward']) is not int or row['reward'] not in (0, 1)):
        raise ValueError('Actual binary or missing verifier outcome required')
    if row['cleanup_complete'] is not True or row['model_revoked'] is not True:
        raise ValueError('Revocation and cleanup required')
    for key in ('agent_error_type', 'verifier_error_type'):
        if not isinstance(row[key], str) or row[key] and not re.fullmatch(r'[A-Z][A-Za-z0-9_]*', row[key]):
            raise ValueError('Only exception class metadata permitted')
    for key in COUNTS:
        if type(row[key]) is not int or row[key] < 0:
            raise ValueError('Nonnegative integer accounting and trace counts required')
    requests = row['model_requests']
    if (sum(row[k] for k in COUNTS[1:5]) != requests or row['unknown_cost_requests'] > requests
            or row['generation_timings'] + row['missing_generation_timings'] != requests
            or row['http_429_requests'] > row['transport_error_requests']):
        raise ValueError('Physical accounting and trace counts do not balance')
    try:
        known = Decimal(row['known_cost_usd']) if isinstance(row['known_cost_usd'], str) else Decimal('NaN')
    except InvalidOperation:
        raise ValueError('Finite response-reported cost required') from None
    if (not known.is_finite() or known < 0
            or row['total_cost_usd'] != (None if row['unknown_cost_requests'] else row['known_cost_usd'])):
        raise ValueError('Unknown costs cannot be presented as complete or zero')
    for key in ('input_tokens', 'output_tokens'):
        if row[key] is not None and (type(row[key]) is not int or row[key] != row['known_' + key]):
            raise ValueError('Complete token counts must match actual known subtotals')
    for key, source in (('official_agent_timeout_seconds', 'agent_timeout_seconds'),
            ('official_verifier_timeout_seconds', 'verifier_timeout_seconds'), ('official_cpus', 'cpus'),
            ('official_memory_mb', 'memory_mb')):
        phase._number(row[key], positive=True); _same(row[key], limits[source])
    _same(row['setup_timeout_seconds'], 900)
    setup_only = row['status'] == 'setup_failed'
    if (row['status'] not in ('setup_failed', 'verified', 'verifier_failed')
            or setup_only and (not row['agent_error_type'] or row['verifier_error_type'] or row['reward'] is not None or requests)
            or row['status'] == 'verified' and row['verifier_error_type']
            or row['status'] == 'verifier_failed' and (not row['verifier_error_type'] or row['reward'] is not None)):
        raise ValueError('Unsupported or contradictory lifecycle category')
    observations = {k: 'not_run_setup_failed' if setup_only and k != 'setup' else 'measured' for k in phase.PHASES}
    _same(row['phase_observation'], observations)
    for kind, observation in observations.items():
        seconds = row[kind + '_seconds']
        if observation == 'measured': phase._number(seconds)
        elif seconds is not None: raise ValueError('Unexecuted phases must remain null, never zero')
    for kind, error in (('setup' if setup_only else 'agent', row['agent_error_type']), ('verifier', row['verifier_error_type'])):
        limit = 900 if kind == 'setup' else row['official_' + kind + '_timeout_seconds']
        if error == 'TimeoutError' and row[kind + '_seconds'] < limit - .1:
            raise ValueError('Recorded timeout must consume its actual allowance')
    phase._hash(row['result_sha256'])


def validate_snapshot(data, anchor_bytes):
    """Schema/byte-anchor validation only. No native audit or admission witness."""
    if not isinstance(data, dict) or set(data) != SNAPSHOT_FIELDS:
        raise ValueError('Exact amended completed-report schema required')
    if (data['kind'] != report.KIND or data['condition'] != 'C0-NC' or data['completed_final_audit'] is not True
            or any(data[k] is not False for k in ('paid_launch_ready', 'off_server_backup_verified', 'archive_export_and_handoff_integrated'))):
        raise ValueError('Amended audit metadata cannot assert backup or dispatch authority')
    proof, block, host, preserved = _anchors(anchor_bytes)
    _same(data['registration'], block); _same(data['sources'], proof['sources'])
    _same(data['qualification_sha256'], phase.QUALIFICATION)
    _same(data['preserved_result_files'], preserved)
    _same(data['amendment'], phase.contract()); _same(data['amendment_sha256'], phase.fingerprint(phase.contract()))
    _same(data['reporting_source_files'], reporting_sources())
    _same(data['reporting_dependencies'], report.dependencies.contract())
    _same(data['reporting_environment'], report.guard.environment_contract())
    if any(n.removeprefix('stage2/') in proof['sources'] for n in report.dependencies.FILES):
        raise ValueError('Current helper inventory cannot alter original qualification')
    _same(data['audit_checks'], dict.fromkeys(report.CHECKS, True))
    phase.guard.validate_service(data['service'])
    _same(phase.fingerprint(data['model_protocol']), block['model_protocol_sha256'])
    _same(phase.fingerprint(data['policy']), block['policy_sha256'])
    bindings = {phase.RT + name: sha for name, sha in report.INPUTS.items()}
    report._merge(bindings, proof['evidence_files']); _same(data['bindings'], bindings)
    support = data['supporting_file_sha256']; _map(support)
    required = {'stage2/' + n: h for n, h in proof['sources'].items()}
    report._merge(required, bindings); report._merge(required, report.HISTORICAL_INPUTS)
    report._merge(required, report.dependencies.FILES)
    report._merge(required, report.guard.REPORTING_LIBRARY_FILES)
    if any(support.get(n) != h for n, h in required.items()):
        raise ValueError('Actual source/input/producer/historical byte bindings required')
    rows = data['rows']; collected = _utc(data['collected_utc'])
    if (not isinstance(rows, list) or len(rows) != 89 or any(not isinstance(r, dict) for r in rows) or len(block['cells']) != 89
            or [tuple(r.get(k) for k in ('trial_id', 'task_id', 'harness')) for r in rows] != [
                tuple(c[k] for k in ('trial_id', 'task_id', 'harness')) for c in block['cells']]
            or len({r['trial_id'] for r in rows}) != 89 or len({r['task_id'] for r in rows}) != 89):
        raise ValueError('Every registered final cell in its fixed order is required')
    directories = data['directory_entries']; absent = data['absent_paths']
    _inventories(directories, absent)
    allowed_directories = set(); expected_absent = set(); expected_files = set(required)
    for row in rows:
        _row(row, host['task_inventory'][row['task_id']], collected)
        trial = phase.RT + 'scored-trials/' + row['trial_id']
        accounting = phase.RT + 'scored-attempts/' + row['trial_id']
        lifecycle = phase.RT + 'retry-lifecycle/' + row['trial_id'] + '.json'
        expected_files.update((trial + '/started.json', trial + '/result.json'))
        if support.get(trial + '/result.json') != row['result_sha256']:
            raise ValueError('Result hash differs from actual support bindings')
        allowed_directories.add(trial + '/traces')
        traces = directories.get(trial + '/traces', [])
        if (not isinstance(traces, list) or len(traces) < 3
                or row['status'] == 'setup_failed' and len(traces) != 3
                or row['status'] != 'setup_failed' and len(traces) < 5):
            raise ValueError('Required actual phase event inventory is missing')
        if accounting in directories: allowed_directories.add(accounting)
        else: expected_absent.add(accounting)
        if row['status'] == 'setup_failed': expected_absent.add(lifecycle)
        else: expected_files.add(lifecycle)
        entries = directories.get(accounting, [])
        if (row['status'] == 'setup_failed' and entries not in ([], ['started.json'])
                or 'provider-stop.json' in entries):
            raise ValueError('Setup-only or stopped accounting cannot be silently admitted')
        for suffix, count in (('.request.json', row['model_requests']), ('.timing.json', row['generation_timings']),
                ('.retry.json', row['retry_records']), ('.transport-error.json', row['transport_error_requests'])):
            if sum(n.endswith(suffix) for n in entries) != count:
                raise ValueError('Actual request/trace inventory count differs')
    if set(directories) != allowed_directories or set(absent) != expected_absent:
        raise ValueError('Only corroborated lifecycle/accounting absences and inventories allowed')
    for name, entries in directories.items():
        for entry in entries:
            expected_files.add(name + '/' + entry)
    if set(support) != expected_files:
        raise ValueError('Missing or extra actual supporting-file binding')
    if any(n == a or n.startswith(a + '/') for n in support for a in absent):
        raise ValueError('Absent evidence cannot have a bound file or descendant')
    _same(data['aggregates'], dict(full89=report.aggregate(rows), development20=report.aggregate(rows[:20]),
        remaining69=report.aggregate(rows[20:])))
    return dict(kind='amended_snapshot_schema_checked_not_native_audit', completed_final_audit=False, paid_launch_ready=False)


def _receipt(data, receipt):
    if not isinstance(receipt, dict) or set(receipt) != RECEIPT_FIELDS or receipt['kind'] != KIND:
        raise ValueError('Exact absence-aware archive receipt required')
    for key in ('sha256', 'snapshot_sha256', 'reporting_sources_sha256', 'absent_paths_sha256'): phase._hash(receipt[key])
    for key in ('compressed_bytes', 'files', 'bytes', 'excluded'):
        if type(receipt[key]) is not int or receipt[key] < (0 if key == 'excluded' else 1):
            raise ValueError('Actual archive sizes and counts required')
    for key, value in (('snapshot_sha256', data), ('reporting_sources_sha256', data['reporting_source_files']),
            ('absent_paths_sha256', data['absent_paths'])):
        _same(receipt[key], phase.fingerprint(value))


class _Compressed:
    def __init__(self, stream, size):
        self.stream, self.remaining = stream, size
        self.digest = hashlib.sha256()

    def read(self, size=-1):
        count = min(self.remaining, CHUNK, size if size >= 0 else CHUNK)
        if not count: return b''
        raw = self.stream.read(count)
        if not isinstance(raw, bytes) or not raw or len(raw) > count:
            raise ValueError('Incomplete compressed archive')
        self.remaining -= len(raw); self.digest.update(raw)
        return raw


class _TarInfo(tarfile.TarInfo):
    @classmethod
    def frombuf(cls, buf, encoding, errors):
        member = super().frombuf(buf, encoding, errors)
        # Inspect extension headers before tarfile allocates their bodies.
        # Ordinary evidence payloads remain streamed without an added size cap.
        if member.type not in (tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE,
                tarfile.XHDTYPE, tarfile.GNUTYPE_LONGNAME):
            raise ValueError('Only regular files, directories and bounded path/time metadata allowed')
        if member.size < 0 or member.type in (tarfile.XHDTYPE, tarfile.GNUTYPE_LONGNAME) and member.size > ANCHOR_WINDOW:
            raise ValueError('Archive extension metadata exceeds parser window')
        return member


def verify_stream(stream, data, receipt):
    """Read one bounded archive frame; framing/peer/commitment belong to caller.

    Regular streams are allowed here, not as live-handoff authority. The future
    authenticated transport must verify its final commitment separately. This
    function neither claims an off-server location nor returns a live witness.
    """
    if not isinstance(data, dict) or set(data) != SNAPSHOT_FIELDS:
        raise ValueError('Exact amended completed-report schema required')
    _receipt(data, receipt)
    original_snapshot = phase.fingerprint(data); original_receipt = phase.fingerprint(receipt)
    _map(data['supporting_file_sha256']); _map(data['reporting_source_files'])
    expected = dict(data['supporting_file_sha256'])
    report._merge(expected, {'reporting/' + n: h for n, h in data['reporting_source_files'].items()})
    directories = data['directory_entries']; absent = data['absent_paths']
    # A strict schema check follows as soon as all five pinned anchors are read.
    # Pre-read structural checks prevent ambiguous or unsafe inventory lookups.
    _inventories(directories, absent)
    if (not isinstance(data['rows'], list) or len(data['rows']) != 89
            or any(not isinstance(r, dict) or not isinstance(r.get('trial_id'), str) for r in data['rows'])):
        raise ValueError('Registered trial identity rows required')
    trial_roots = {phase.RT + 'scored-trials/' + r['trial_id'] for r in data['rows']}
    for name in trial_roots: _name(name)
    parents = {str(p) for n in expected for p in PurePosixPath(n).parents if str(p) != '.'}
    parents.update(directories)
    source = _Compressed(stream, receipt['compressed_bytes'])
    names = set(); seen = set(); seen_directories = set(); anchors = {}; files = unpacked = 0
    try:
        with gzip.GzipFile(fileobj=source, mode='rb') as compressed:
            with tarfile.open(fileobj=compressed, mode='r|', tarinfo=_TarInfo) as archive:
                for member in archive:
                    name = _name(member.name)
                    if (name in names or not (member.isfile() or member.isdir())
                            or member.issym() or member.islnk()
                            or set(member.pax_headers) - {'path', 'mtime', 'atime', 'ctime'}
                            or member.sparse is not None or type(member.size) is not int or member.size < 0):
                        raise ValueError('Duplicate, linked, extended or special archive member refused')
                    names.add(name)
                    if any(name == a or name.startswith(a + '/') for a in absent):
                        raise ValueError('Archive contains evidence bound as actually absent')
                    for folder, entries in directories.items():
                        if name.startswith(folder + '/') and name[len(folder) + 1:] not in entries:
                            raise ValueError('Archive contradicts an exact evidence inventory')
                    if member.isdir():
                        if name in expected or name not in parents and not any(name.startswith(t + '/') for t in trial_roots):
                            raise ValueError('Unexpected archive directory')
                        seen_directories.add(name)
                        continue
                    if name in parents:
                        raise ValueError('Archive directory cannot be replaced by a file')
                    if name not in expected and not any(name.startswith(t + '/') for t in trial_roots):
                        raise ValueError('Unexpected file outside registered private trial evidence')
                    files += 1; unpacked += member.size
                    if files > receipt['files'] or unpacked > receipt['bytes']:
                        raise ValueError('Archive exceeds its exact source receipt counts')
                    with archive.extractfile(member) as contents:
                        if name in anchor_hashes():
                            if member.size > ANCHOR_WINDOW: raise ValueError('Pinned metadata exceeds parser window')
                            raw = contents.read(); anchors[name] = raw; sha = hashlib.sha256(raw).hexdigest()
                        else:
                            sha = hashlib.file_digest(contents, 'sha256').hexdigest()
                    if name in expected:
                        if sha != expected[name]: raise ValueError('Archived source/input/producer/result/support bytes changed')
                        seen.add(name)
                # Drain tarfile's own buffer too, not just gzip: hidden members
                # after an early tar end marker must not escape absence checks.
                padding = 0
                while tail := archive.fileobj.read(CHUNK):
                    if tail.strip(b'\0'): raise ValueError('Non-padding data after the tar end marker')
                    padding += len(tail)
                if padding < tarfile.BLOCKSIZE:
                    raise ValueError('Both complete tar end-marker blocks required')
            while compressed.read(CHUNK):
                raise ValueError('Unexpected trailing decompressed data')
    except (OSError, EOFError, tarfile.TarError):
        raise ValueError('Invalid or incomplete compressed archive') from None
    if (source.remaining or source.digest.hexdigest() != receipt['sha256'] or seen != set(expected)
            or not set(directories) <= seen_directories
            or files != receipt['files'] or unpacked != receipt['bytes']):
        raise ValueError('Archive checksum, bound coverage or retained counts differ')
    validate_snapshot(data, anchors)
    if phase.fingerprint(data) != original_snapshot or phase.fingerprint(receipt) != original_receipt:
        raise ValueError('Snapshot or archive receipt changed during byte verification')
    return dict(receipt, verified_result_files=89, verified_bound_files=len(seen), verified_absent_paths=len(absent),
        completed_final_audit=False, paid_launch_ready=False, off_server_location_verified=False,
        full_runtime_restore_exercised=False)


def verify_archive(path, data, receipt):
    """Re-read an existing private regular single-link archive without writing."""
    path = Path(path)
    if not isinstance(receipt, dict): raise ValueError('Exact archive receipt required')
    if not path.is_absolute() or path.resolve() != path or path.is_symlink():
        raise ValueError('Canonical private archive path required')
    try:
        # A substituted FIFO must fail the regular-file check without waiting
        # for a writer. NONBLOCK does not change regular-file reads.
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
            before = os.fstat(stream.fileno())
            if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_uid != os.getuid()
                    or before.st_mode & 0o077 or before.st_size != receipt.get('compressed_bytes')):
                raise ValueError('Owned private single-link archive with exact size required')
            result = verify_stream(stream, data, receipt)
            after = os.fstat(stream.fileno()); current = path.stat(follow_symlinks=False)
            identity = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            if stream.read(1) or identity(before) != identity(after) or identity(before) != identity(current):
                raise ValueError('Archive changed while verifying its actual bytes')
    except OSError:
        raise ValueError('Private archive unavailable') from None
    return result
