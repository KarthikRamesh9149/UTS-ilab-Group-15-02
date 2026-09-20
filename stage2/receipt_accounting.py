"""Additive, opt-in consumption of exact receipts for immutable terminal holds.

Staging alone has no accounting effect. Explicit private activation batches bind
the staged bytes; each budget use revalidates the original deferral, response,
charge and native tokens. No database row, outcome or original registry changes.
This module cannot qualify changed runtime sources or start a benchmark.
"""
from contextlib import ExitStack, closing
import fcntl
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import stat

from deferred_billing import _encoded, _json, _read, _write

DIRECTORY = 'receipt-accounting-activations-v1'


def _directory(path):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('Private owned receipt accounting directory required')


def _requests(entries):
    mapping = {}
    for entry in entries:
        for identifier in entry['unverified_receipt_request_ids']:
            if identifier in mapping:
                raise ValueError('Ambiguous original receipt request identity')
            mapping[identifier] = entry
    return mapping


def _staged(runtime, kind, identifier, entries):
    from collect_deferred_receipts import DIRECTORY as STAGED, _document
    if not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9-]{1,100}', identifier):
        raise ValueError('Safe explicit receipt request identity required')
    if identifier not in entries or entries[identifier]['kind'] != kind:
        raise ValueError('Only registered settled missing-receipt holds may be reduced')
    name = kind + '--' + identifier + '.json'
    raw = _read(runtime / STAGED / name, runtime)
    record = _json(raw)
    expected = _document(runtime, entries[identifier], identifier, record.get('receipt'))
    if _encoded(record) != _encoded(expected):
        raise ValueError('Staged receipt differs from exact original billing evidence')
    return name, hashlib.sha256(raw).hexdigest(), record


def activated_receipt_adjustments(runtime, entries, *, kind):
    """Called only AFTER original deferral/database validation in one snapshot."""
    runtime = Path(runtime).absolute()
    if kind not in {'setup', 'scored'}:
        raise ValueError('Explicit original ledger kind required')
    folder = runtime / DIRECTORY
    if not folder.exists() and not folder.is_symlink():
        return {}
    _directory(folder)
    mapping = _requests(entries)
    seen, totals = set(), {}
    for path in sorted(folder.iterdir()):
        match = re.fullmatch(r'(setup|scored)--([a-f0-9]{64})\.json', path.name)
        if match is None:
            raise ValueError('Unexpected receipt activation artifact')
        if match[1] != kind:
            continue
        raw = _read(path, runtime)
        if hashlib.sha256(raw).hexdigest() != match[2]:
            raise ValueError('Receipt activation digest changed')
        batch = _json(raw)
        if (set(batch) != {'schema_version', 'kind', 'receipts'}
                or type(batch['schema_version']) is not int or batch['schema_version'] != 1
                or batch['kind'] != kind or not isinstance(batch['receipts'], dict)
                or not 1 <= len(batch['receipts']) <= 64):
            raise ValueError('Exact bounded receipt activation schema required')
        for identifier, expected_hash in batch['receipts'].items():
            if identifier in seen:
                raise ValueError('Receipt hold cannot be reduced twice')
            name, digest, record = _staged(runtime, kind, identifier, mapping)
            if digest != expected_hash:
                raise ValueError('Activated receipt bytes changed')
            seen.add(identifier)
            entry = mapping[identifier]
            total = totals.setdefault(entry['trial_id'], {'hold_reduction_nanodollars': 0,
                                  'receipts': {}, 'activation_sha256': {}})
            total['hold_reduction_nanodollars'] += record['potential_hold_reduction_nanodollars']
            total['receipts'][name] = digest
            total['activation_sha256'][path.name] = match[2]
            if not 0 <= total['hold_reduction_nanodollars'] <= entry['extra_reserved_nanodollars']:
                raise ValueError('Receipt reductions exceed original extra hold')
    return totals


def activate(runtime, *, kind, request_ids):
    """Explicit maintenance only; qualification remains a separate prerequisite.

    Owns all execution locks. The original database is opened read-only. A new
    immutable batch is the only write; callers must not infer paid admission.
    """
    if (kind not in {'setup', 'scored'} or not isinstance(request_ids, (tuple, list))
            or not 1 <= len(request_ids) <= 64
            or any(not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9-]{1,100}', value)
                   for value in request_ids) or len(set(request_ids)) != len(request_ids)):
        raise ValueError('Bounded unique explicit receipt requests required')
    from deferred_billing import validate_deferrals, extra_exposure_nanodollars
    runtime = Path(runtime).absolute()
    _directory(runtime)
    with ExitStack() as stack:
        for name in ('matrix.lock', 'scored.lock', 'gateway.lock'):
            fd = os.open(runtime / name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            handle = stack.enter_context(os.fdopen(fd, 'r+'))
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise ValueError('Private owned execution lock required')
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        database = runtime / (kind + '_budget.sqlite')
        _read(database, runtime)
        db = stack.enter_context(closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)))
        db.execute('BEGIN')
        entries = validate_deferrals(runtime, db, kind=kind)
        before = extra_exposure_nanodollars(entries)
        mapping = _requests(entries)
        already = {name for entry in entries for name in entry.get('receipt_recovery', {}).get('receipts', {})}
        selected = {}
        for identifier in request_ids:
            name, digest, _ = _staged(runtime, kind, identifier, mapping)
            if name not in already:
                selected[identifier] = digest
        activation_sha = None
        if selected:
            batch = {'schema_version': 1, 'kind': kind, 'receipts': selected}
            activation_sha = hashlib.sha256(_encoded(batch)).hexdigest()
            folder = runtime / DIRECTORY
            if not folder.exists() and not folder.is_symlink():
                folder.mkdir(mode=0o700)
            _directory(folder)
            _write(folder / (kind + '--' + activation_sha + '.json'), batch)
        after = extra_exposure_nanodollars(validate_deferrals(runtime, db, kind=kind))
        return {'activated_receipts': len(selected), 'already_activated': len(request_ids) - len(selected),
                'activation_sha256': activation_sha, 'hold_reduction_nanodollars': before - after,
                'original_ledgers_or_results_changed': False, 'generation_calls': 0,
                'continuation_authorised': False}
