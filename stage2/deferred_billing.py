"""Evidence-bound terminal billing deferrals, not receipts or permission to retry.

Only the trusted host registers a closed attempt. Original results, requests,
charges and reservations remain unchanged. Every use revalidates the closure
and raw evidence inside the caller's canonical ledger transaction.
"""
from contextlib import closing
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

POLICY = 'deferred-billing-policy-v1.json'
DIRECTORY = 'deferred-billing'


def canonical_policy_document():
    return {'schema_version': 1, 'amendment_id': 'bounded-terminal-billing-continuation-20260920',
            'classification': 'explicit_user_approved_standing_prospective_amendment',
            'model_protocol_sha256': 'b9f42d3bcc9a4f416bcaaf8ee0f175d96a2bbd493943c64199d46e671719e27f',
            'allow_terminal_unknown_dispatch': True, 'allow_terminal_unavailable_receipt': True,
            'require_revocation_and_cleanup': True, 'same_trial_replay_authorized': False,
            'active_request_exception_authorized': False, 'billing_verified': False,
            'setup_cap_nanodollars': 1_000_000_000, 'scored_cap_nanodollars': 8_901_000_000,
            'scored_trial_cap_nanodollars': 23_000_000, 'reserve_nanodollars': 2_000_000_000,
            'stage_caps_nanodollars': {'development': 2_760_000_000, 'final': 6_141_000_000}}


def _json(raw, *, billing=False):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('Duplicate deferred billing field')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=unique, **({'parse_float': Decimal} if billing else {}))


def _encoded(document):
    return json.dumps(document, sort_keys=True, separators=(',', ':')).encode()


def _read(path, runtime):
    path, runtime = Path(path), Path(runtime)
    relative = path.relative_to(runtime)
    if '..' in relative.parts:
        raise ValueError('Deferred evidence escaped canonical runtime')
    for parent in (runtime, *(runtime / Path(*relative.parts[:index]) for index in range(1, len(relative.parts)))):
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('Private owned deferred evidence directories required')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('Private owned regular deferred evidence required')
        return handle.read()


def _write(path, document):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as handle:
        handle.write(_encoded(document))
        handle.flush()
        os.fsync(handle.fileno())
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def validate_policy(runtime):
    runtime = Path(runtime).absolute()
    path = runtime / POLICY
    if not path.exists() and not path.is_symlink():
        return None
    raw = _read(path, runtime)
    value = _json(raw)
    if _encoded(value) != _encoded(canonical_policy_document()):
        raise ValueError('Deferred billing policy differs from approved standing amendment')
    return dict(value, sidecar_sha256=hashlib.sha256(raw).hexdigest())


def register_policy(runtime):
    """Explicit host action after approval; never called by gateway admission."""
    runtime = Path(runtime).absolute()
    policy = validate_policy(runtime)
    if policy is not None:
        return policy
    info = runtime.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('Private canonical runtime required')
    _write(runtime / POLICY, canonical_policy_document())
    return validate_policy(runtime)


def _database(runtime, db, kind):
    if kind not in {'setup', 'scored'}:
        raise ValueError('Registered deferred ledger kind required')
    path = runtime / (kind + '_budget.sqlite')
    _read(path, runtime)  # Validate the original private file, not a substitute.
    if not db.in_transaction or not any(name == 'main' and Path(filename).resolve() == path.resolve()
            for _, name, filename in db.execute('PRAGMA database_list')):
        raise ValueError('Canonical ledger transaction required')
    if db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
        raise ValueError('Deferred ledger integrity failure')
    expected_policy = (1_000_000_000, 1_000_000_000) if kind == 'setup' else (8_901_000_000, 23_000_000)
    expected_stages = {'setup': 1_000_000_000} if kind == 'setup' else {'development': 2_760_000_000, 'final': 6_141_000_000}
    if (db.execute('SELECT ceiling,trial_cap FROM policy WHERE id=1').fetchone() != expected_policy
            or dict(db.execute('SELECT name,cap FROM stages')) != expected_stages
            or db.execute('SELECT enabled FROM estimation_policy WHERE id=1').fetchone() != (int(kind == 'scored'),)):
        raise ValueError('Deferred billing cannot change budget or estimation policy')
    if db.execute('SELECT COUNT(*) FROM incidents').fetchone()[0]:
        raise ValueError('Actual billing incident cannot be deferred')


def _snapshot(runtime, db, *, kind, trial_id, relative_result, policy):
    from budget_ledger import dollars
    from gateway_core import reconcile_receipt
    from gateway_policy import MODEL, ENDPOINT
    from model_protocol import read_protocol
    from setup_probe import full_context_bound
    settings = read_protocol(runtime)
    if settings.fingerprint() != policy['model_protocol_sha256']:
        raise ValueError('Standing deferral policy cannot change the frozen study model')
    if not isinstance(trial_id, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}', trial_id):
        raise ValueError('Invalid deferred trial identity')
    relative = Path(relative_result)
    expected = Path('scored-trials') / trial_id / 'result.json'
    if kind == 'setup':
        if (len(relative.parts) != 6 or not relative.parts[0].startswith('native-live-')
                or Path(*relative.parts[1:]) != Path('.runtime/stage2') / expected
                or not trial_id.startswith('setup-native-')):
            raise ValueError('Original native setup fixture result required')
    elif relative != expected:
        raise ValueError('Original scored result required')
    raw = _read(runtime / relative, runtime)
    result = _json(raw)
    if result.get('trial_id') != trial_id or result.get('status') not in {'billing_unresolved', 'verified', 'infrastructure_failed', 'interrupted'}:
        raise ValueError('Closed terminal result identity required')
    if not all(result.get(key) is True for key in ('model_revoked', 'containers_removed', 'networks_removed', 'volumes_removed')):
        raise ValueError('Deferred request requires verified revocation and complete cleanup')
    fingerprint = result.get('model_protocol_sha256')
    if fingerprint != settings.fingerprint():
        raise ValueError('Deferred result model protocol required')
    evidence = runtime / ('native-setup-attempts' if kind == 'setup' else 'scored-attempts') / trial_id
    inventory = {path.name: hashlib.sha256(_read(path, runtime)).hexdigest() for path in evidence.iterdir()}
    started = _json(_read(evidence / 'started.json', runtime))
    stage = 'setup' if kind == 'setup' else result.get('stage')
    if (started.get('trial_id') != trial_id or started.get('stage') != stage
            or started.get('model_protocol_sha256') != fingerprint
            or (kind == 'scored' and stage not in {'development', 'final'})):
        raise ValueError('Deferred gateway/result identity mismatch')
    rows = db.execute('''SELECT r.id,r.trial,r.reserved,r.charged,r.state,g.generation_id,c.state,e.amount
        FROM requests r LEFT JOIN generations g ON r.id=g.request_id
        LEFT JOIN receipt_checks c ON r.id=c.request_id LEFT JOIN trial_estimates e ON r.id=e.request_id
        WHERE r.trial=? ORDER BY r.id''', (trial_id,)).fetchall()
    if not rows or db.execute('SELECT stage FROM trial_stages WHERE trial=?', (trial_id,)).fetchone() != (stage,):
        raise ValueError('Original deferred trial ledger rows required')
    mapped = {}
    for path in evidence.glob('*.reservation.json'):
        association = _json(_read(path, runtime))
        prefix = path.name.removesuffix('.reservation.json')
        identifier = association.get('reservation_id')
        if (association.get('trial_id') != trial_id or identifier in mapped
                or not re.fullmatch(r'[0-9]{6}', prefix)
                or type(association.get('sequence')) is not int or association['sequence'] != int(prefix)):
            raise ValueError('Ambiguous deferred reservation association')
        mapped[identifier] = prefix
    if set(mapped) != {row[0] for row in rows}:
        raise ValueError('Every deferred-trial request requires its original reservation association')
    prefixes = set(mapped.values())
    for suffix in ('request', 'response', 'receipt', 'response-headers', 'transport-error', 'timing'):
        observed = {path.name.removesuffix('.' + suffix + '.json') for path in evidence.glob('*.' + suffix + '.json')}
        if not observed <= prefixes or (suffix == 'request' and observed != prefixes):
            raise ValueError('Unmapped deferred request or response evidence')
    unknown, receipt_missing, known, pending, extra, full = [], [], 0, 0, 0, 0
    for identifier, _, reserve, charge, state, generation, receipt_state, estimate in rows:
        if type(reserve) is not int or reserve <= 0 or (charge is not None and (type(charge) is not int or charge < 0 or charge > reserve)):
            raise ValueError('Invalid deferred charge or reservation')
        if estimate is not None and charge is not None and charge > estimate:
            raise ValueError('Actual estimated trial overcharge cannot be deferred')
        prefix = mapped[identifier]
        request = _json(_read(evidence / (prefix + '.request.json'), runtime))
        settings.enforce(request)
        if reserve != dollars(full_context_bound(request)):
            raise ValueError('Deferred reservation differs from qualified full-context bound')
        provider = request.get('provider', {})
        if (request.get('model') != MODEL or provider.get('only') != [ENDPOINT]
                or provider.get('allow_fallbacks') is not False):
            raise ValueError('Deferred request provider routing mismatch')
        for suffix in ('response-headers', 'transport-error'):
            diagnostic_path = evidence / (prefix + '.' + suffix + '.json')
            if diagnostic_path.exists():
                diagnostic_entry = _json(_read(diagnostic_path, runtime))
                diagnostic = diagnostic_entry.get('diagnostic', {}) if suffix == 'response-headers' else diagnostic_entry
                if (diagnostic.get('identifier_conflict') or
                        (diagnostic.get('generation_id') is not None and diagnostic['generation_id'] != generation)):
                    raise ValueError('Conflicting deferred provider response identifiers')
                if suffix == 'response-headers' and (diagnostic_entry.get('reservation_id') != identifier
                        or diagnostic_entry.get('trial_id') != trial_id):
                    raise ValueError('Deferred provider header association mismatch')
        response_path, receipt_path = evidence / (prefix + '.response.json'), evidence / (prefix + '.receipt.json')
        if state == 'pending' and charge is None:
            if receipt_path.exists():
                raise ValueError('Available receipt requires reconciliation, not deferral')
            if response_path.exists():
                response = _json(_read(response_path, runtime), billing=True)
                if (response.get('id') != generation or response.get('model') != MODEL
                        or response.get('provider') != 'DeepInfra'):
                    raise ValueError('Conflicting deferred response identity')
                if response.get('usage', {}).get('is_byok') is True:
                    raise ValueError('Explicit BYOK billing identity cannot be deferred')
                cost = response.get('usage', {}).get('cost')
                if cost is not None:
                    actual = dollars(cost)
                    if actual > reserve or (estimate is not None and actual > estimate):
                        raise ValueError('Actual response overcharge cannot be deferred')
            unknown.append(identifier); pending += reserve; full += reserve
        elif state == 'settled' and charge is not None:
            response = _json(_read(response_path, runtime), billing=True)
            if response.get('usage', {}).get('is_byok') is True:
                raise ValueError('Explicit BYOK billing identity cannot be deferred')
            if (not generation or response.get('id') != generation or response.get('model') != MODEL
                    or response.get('provider') != 'DeepInfra' or dollars(response.get('usage', {}).get('cost')) != charge):
                raise ValueError('Deferred known charge conflicts with original response')
            known += charge
            if receipt_path.exists():
                receipt = _json(_read(receipt_path, runtime), billing=True)
                if dollars(reconcile_receipt(response, receipt)) != charge or receipt_state == 'pending':
                    raise ValueError('Available or conflicting receipt must not be deferred')
            elif receipt_state == 'pending':
                receipt_missing.append(identifier); extra += reserve - charge; full += reserve
            else:
                raise ValueError('Missing settled receipt without pending cross-check')
        else:
            raise ValueError('Unknown deferred ledger state')
    if not unknown and not receipt_missing:
        raise ValueError('No terminal billing uncertainty to defer')
    return {'schema_version': 1, 'kind': kind, 'trial_id': trial_id,
            'stage': stage, 'harness': result.get('harness'), 'task_id': result.get('task_id'),
            'model_protocol_sha256': fingerprint, 'policy_sha256': policy['sidecar_sha256'],
            'result_path': relative.as_posix(), 'result_sha256': hashlib.sha256(raw).hexdigest(),
            'original_result_sha256': hashlib.sha256(raw).hexdigest(),
            'evidence_sha256': inventory, 'ledger_rows': [list(row) for row in rows],
            'request_count': len(rows), 'unknown_request_ids': unknown,
            'unverified_receipt_request_ids': receipt_missing,
            'deferred_request_ids': sorted(unknown + receipt_missing),
            'reserved_nanodollars': full, 'pending_reserved_nanodollars': pending,
            'extra_reserved_nanodollars': extra, 'retained_liability_nanodollars': pending + extra,
            'known_charged_nanodollars': known, 'settled_subtotal_nanodollars': known,
            'budget_stop_count': len(list(evidence.glob('*.budget-stop.json'))),
            'billing_verified': False, 'charged_usd': None, 'prompt_tokens': None,
            'completion_tokens': None, 'replay_authorized': False,
            'status': 'terminal_billing_deferred_not_verified'}


def validate_deferrals(runtime, db=None, *, kind='scored', active_trial=None):
    runtime = Path(runtime).absolute()
    policy = validate_policy(runtime)
    folder = runtime / DIRECTORY
    if not folder.exists() and not folder.is_symlink():
        return ()
    info = folder.lstat()
    if not policy or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('Registered private terminal deferral directory required')
    if db is None:
        database = runtime / (kind + '_budget.sqlite')
        with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as reader:
            reader.execute('BEGIN')
            return validate_deferrals(runtime, reader, kind=kind, active_trial=active_trial)
    _database(runtime, db, kind)
    entries = []
    for path in sorted(folder.iterdir()):
        if not re.fullmatch(r'(setup|scored)--[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}\.json', path.name):
            raise ValueError('Unexpected terminal deferral registry artifact')
        raw = _read(path, runtime)
        entry = _json(raw)
        if path.name != entry['kind'] + '--' + entry['trial_id'] + '.json':
            raise ValueError('Terminal deferral registration identity mismatch')
        if entry['kind'] != kind:
            continue
        if entry['trial_id'] == active_trial:
            raise ValueError('Terminal deferred attempt cannot dispatch again')
        expected = _snapshot(runtime, db, kind=kind, trial_id=entry['trial_id'],
                             relative_result=entry['result_path'], policy=policy)
        if _encoded(entry) != _encoded(expected):
            raise ValueError('Deferred ledger, result or evidence changed')
        digest = hashlib.sha256(raw).hexdigest()
        entries.append(dict(entry, sidecar_sha256=digest, registration_sha256=digest))
    return tuple(entries)


def register_terminal_deferral(runtime, *, kind, trial_id, result_path):
    runtime = Path(runtime).absolute()
    policy = validate_policy(runtime)
    if policy is None:
        raise ValueError('Explicit approved standing policy must be registered first')
    path = Path(result_path)
    relative = path.relative_to(runtime) if path.is_absolute() else path
    descriptor = os.open(runtime / 'gateway.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        database = runtime / (kind + '_budget.sqlite')
        with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as db:
            db.execute('BEGIN')
            _database(runtime, db, kind)
            document = _snapshot(runtime, db, kind=kind, trial_id=trial_id,
                                 relative_result=relative, policy=policy)
            folder = runtime / DIRECTORY
            folder.mkdir(mode=0o700, exist_ok=True)
            if folder.is_symlink():
                raise ValueError('Unsafe deferral registry')
            _write(folder / (kind + '--' + trial_id + '.json'), document)
    return next(entry for entry in validate_deferrals(runtime, kind=kind) if entry['trial_id'] == trial_id)


def validate_terminal_deferral(runtime, trial_id, raw_result, *, kind='scored'):
    entry = next((entry for entry in validate_deferrals(runtime, kind=kind) if entry['trial_id'] == trial_id), None)
    if entry is not None:
        original = _json(_read(Path(runtime).absolute() / entry['result_path'], Path(runtime).absolute()))
        if _encoded(original) != _encoded(raw_result):
            raise ValueError('Deferred view differs from immutable original result')
    return entry


def extra_exposure_nanodollars(entries, *, trial=None, stage=None):
    return sum(entry['extra_reserved_nanodollars'] for entry in entries
               if (trial is None or entry['trial_id'] == trial) and (stage is None or entry['stage'] == stage))


def deferred_request_ids(entries):
    return {identifier for entry in entries for identifier in entry['deferred_request_ids']}


def unresolved_liability_nanodollars(db, entries):
    pending = db.execute("SELECT COALESCE(SUM(reserved),0) FROM requests WHERE state='pending'").fetchone()[0]
    return pending + extra_exposure_nanodollars(entries)


def deferred_audit(entry):
    """Explicitly incomplete cost/usage, separate from the known subtotal."""
    return {key: entry[key] for key in ('billing_verified', 'charged_usd', 'prompt_tokens',
            'completion_tokens', 'model_protocol_sha256', 'budget_stop_count', 'reserved_nanodollars',
            'retained_liability_nanodollars', 'known_charged_nanodollars', 'sidecar_sha256')} | {
                'requests': None, 'billing_deferred': True, 'accounting_bounded': True}
