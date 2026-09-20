"""One disclosed historical liability, never a receipt or a charge correction.

The opt-in document is specific to the interrupted 2026-09-19 dispatch. Every
use rechecks the original evidence and ledger rows. No caller supplies an
exception request ID, charge, allowance, or alternative evidence location.
"""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat

from model_protocol import read_protocol

REQUEST_ID = '03d8ac6c-f2c8-4e3a-9781-be9c8ddadf9f'
TRIAL_ID = 'dev-terminus-2-00-video-processing'
RESERVED_NANODOLLARS = 106_496_000
TRIAL_ESTIMATE_NANODOLLARS = 9_804_200
SETTLED_NANODOLLARS = 374_460
RESULT_SHA256 = 'f534d15c22f53a7de2df316372271f18a259a6387a13e0f7892eb2e3003ef541'
MODEL_PROTOCOL_SHA256 = 'b9f42d3bcc9a4f416bcaaf8ee0f175d96a2bbd493943c64199d46e671719e27f'
SIDECAR = 'historical-hold-v1.json'
ATTEMPT_HASHES = {
    'started.json': '5c3b372c749387aa9095ecda80c78106876bafe43ea2e73ddad72313716ac176',
    '000001.request.json': '84d176eb75ff8b885c4741c8682e82edb02d58bf1d2d811508d29093520072af',
    '000001.response.json': '716eb16594f53fe986b7c7b7fc6aa83e658b4e0f738286c9c5ed998e53aecdfb',
    '000001.receipt.json': '80e7eaa4b8c881362f462e53196de26b6e4964c6b8615e08e5f138f720ae0306',
    '000001.timing.json': '413b5ad1b1ff95224f445a4976e08fb91a8bae609c674be81d1770519ce23207',
    '000001.budget-stop.json': '4f172c8877e5e7faaedf082995f66cd3786abb565cc2bc88881b773b31183f62',
    '000002.request.json': '5e265dcc999adaf9ab47234bc033decbe83a6e9694d55d94eea3f45fd03b10ac',
    '000002.response.json': '86bc46cd7ea51096d0c596b1d761f21dc7182e991a01107a192e9f0a1674b599',
    '000002.receipt.json': '32b5686229a18539fbb64ede7634e2cad04e3702566b15a421fbdc73939c7676',
    '000002.timing.json': 'd0077e72b76f34062f45e7d2326217e7be1c5b08fdcdaaecee6ee5b7d109a335',
    '000002.budget-stop.json': '4f172c8877e5e7faaedf082995f66cd3786abb565cc2bc88881b773b31183f62',
    '000003.request.json': '693d1fc90837a2aa26ac0912889401396bad2c83cd69169cc66f5b7c088e2224',
    '000003.timing.json': '0d35bb583c59b5499eb7a25b92c24b56a7f6c8b5c02a10c860eb4ab8441d19ba',
    '000003.gateway-error.json': '7b0d05670d1bb745c7b826ca5c9dced1d10b1ea1f1307319270fcacf6e10ec5a',
}
ORIGINAL_ROWS = (
    ('086704f4-8d00-40b8-b400-3284fdeb0af3', RESERVED_NANODOLLARS, 149820, 'settled',
     4448200, 'gen-1789828749-tkNrgh9lhqdj66lg1HqG', 'verified'),
    ('b79fcc70-748c-4726-b66e-9d20cf012482', RESERVED_NANODOLLARS, 224640, 'settled',
     5080800, 'gen-1789828759-u4JNkd8GOr1sjV7kuN6w', 'verified'),
    (REQUEST_ID, RESERVED_NANODOLLARS, None, 'pending', TRIAL_ESTIMATE_NANODOLLARS, None, None),
)


def canonical_hold_document():
    """Reviewable document only; this function does not register an amendment."""
    return {
        'schema_version': 1, 'amendment_id': 'bounded-historical-hold-v1',
        'classification': 'post_incident_amendment',
        'request_id': REQUEST_ID, 'trial_id': TRIAL_ID, 'task_id': 'video-processing',
        'harness': 'terminus-2', 'stage': 'development',
        'reserved_nanodollars': RESERVED_NANODOLLARS,
        'trial_estimate_nanodollars': TRIAL_ESTIMATE_NANODOLLARS,
        'settled_subtotal_nanodollars': SETTLED_NANODOLLARS,
        'charged_nanodollars': None, 'generation_id': None, 'state': 'pending',
        'billing_verified': False, 'replay_authorized': False,
        'original_result_sha256': RESULT_SHA256,
        'model_protocol_sha256': MODEL_PROTOCOL_SHA256,
        'evidence_sha256': dict(ATTEMPT_HASHES),
        'original_scored_ledger_sha256': '4504d4289a06643ee93d1690502d7d8b978ff9e20c0cb75fa56440d95fb34359',
        'aggregate_cap_nanodollars': 8_901_000_000,
        'trial_cap_nanodollars': 23_000_000,
        'stage_caps_nanodollars': {'development': 2_760_000_000, 'final': 6_141_000_000},
    }


def _regular_bytes(path, runtime, *, private=False):
    # Reject replaced parent directories as well as a symlink at the leaf.
    for parent in (path.parent, *path.parent.parents):
        if parent == runtime.parent:
            break
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError('Unsafe historical hold evidence directory')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as handle:
        info = os.fstat(handle.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or (private and info.st_mode & 0o077)):
            raise ValueError('Private owned regular historical hold artifact required')
        return handle.read()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate historical hold document field')
        result[key] = value
    return result


def validate_historical_hold(runtime, db=None, *, active_trial=None):
    """Return the exact verified hold, or None when no amendment is registered.

    A supplied connection must be the canonical ledger and must already be in
    a transaction. Reserve passes its BEGIN IMMEDIATE connection, keeping the
    exception check and new reservation atomic. Current-trial receipt checks
    may remain deferred; unrelated unresolved billing always blocks admission.
    """
    runtime = Path(runtime).absolute()
    path = runtime / SIDECAR
    if not path.exists() and not path.is_symlink():
        return None
    try:
        info = runtime.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('Historical hold runtime must be owned and private')
        data = _regular_bytes(path, runtime, private=True)
        document = json.loads(data, object_pairs_hook=_unique_object)
        expected = canonical_hold_document()
        if json.dumps(document, sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise ValueError('Historical hold amendment identity mismatch')
        if active_trial == TRIAL_ID:
            raise ValueError('Historical trial cannot dispatch or verify again')
        if read_protocol(runtime).fingerprint() != MODEL_PROTOCOL_SHA256:
            raise ValueError('Historical hold model protocol mismatch')
        attempt = runtime / 'scored-attempts' / TRIAL_ID
        if {p.name for p in attempt.iterdir()} != set(ATTEMPT_HASHES):
            raise ValueError('Historical request evidence inventory changed')
        for name, digest in ATTEMPT_HASHES.items():
            if hashlib.sha256(_regular_bytes(attempt / name, runtime)).hexdigest() != digest:
                raise ValueError('Historical request evidence changed')
        result = runtime / 'scored-trials' / TRIAL_ID / 'result.json'
        if hashlib.sha256(_regular_bytes(result, runtime)).hexdigest() != RESULT_SHA256:
            raise ValueError('Historical result changed')
        database = runtime / 'scored_budget.sqlite'
        info = database.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError('Original scored ledger required for historical hold')
        if db is None:
            reader = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)
            try:
                reader.execute('PRAGMA query_only=ON')
                reader.execute('BEGIN')
                _validate_rows(reader, active_trial)
            finally:
                reader.close()
        else:
            databases = db.execute('PRAGMA database_list').fetchall()
            if not db.in_transaction or not any(name == 'main' and Path(filename).resolve() == database.resolve()
                                               for _, name, filename in databases):
                raise ValueError('Historical hold requires canonical transaction')
            _validate_rows(db, active_trial)
        # Raw markers stay unchanged. Original Ledger.reserve checked the
        # pending barrier before all caps. Both pinned markers occurred after
        # generation 3 failed and retained this reservation, with no dispatch 4.
        return dict(expected, sidecar_sha256=hashlib.sha256(data).hexdigest(),
                    budget_stop_count=2, budget_stop_classification='historical_pending_barrier',
                    capacity_budget_stop_count=0)
    except (OSError, sqlite3.Error, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError('Historical hold evidence unavailable or invalid') from exc


def _validate_rows(db, active_trial):
    if db.execute('SELECT ceiling,trial_cap FROM policy WHERE id=1').fetchone() != (8_901_000_000, 23_000_000):
        raise ValueError('Historical hold cannot change budget policy')
    if dict(db.execute('SELECT name,cap FROM stages')) != {'development': 2_760_000_000, 'final': 6_141_000_000}:
        raise ValueError('Historical hold cannot change stage allocations')
    if db.execute('SELECT enabled FROM estimation_policy WHERE id=1').fetchone() != (1,):
        raise ValueError('Historical hold requires original estimation policy')
    rows = db.execute('''SELECT r.id,r.reserved,r.charged,r.state,e.amount,g.generation_id,c.state
        FROM requests r LEFT JOIN trial_estimates e ON e.request_id=r.id
        LEFT JOIN generations g ON g.request_id=r.id LEFT JOIN receipt_checks c ON c.request_id=r.id
        WHERE r.trial=?''', (TRIAL_ID,)).fetchall()
    if sorted(rows) != sorted(ORIGINAL_ROWS):
        raise ValueError('Original historical ledger rows changed')
    if db.execute('SELECT stage FROM trial_stages WHERE trial=?', (TRIAL_ID,)).fetchone() != ('development',):
        raise ValueError('Historical trial stage changed')
    if db.execute('SELECT COUNT(*) FROM incidents').fetchone()[0]:
        raise ValueError('Billing incident blocks historical hold admission')
    if db.execute("SELECT COUNT(*) FROM requests WHERE (state!='settled' OR charged IS NULL) AND id!=?",
                  (REQUEST_ID,)).fetchone()[0]:
        raise ValueError('Another unresolved dispatch blocks historical hold admission')
    if db.execute('''SELECT COUNT(*) FROM receipt_checks c LEFT JOIN requests r ON r.id=c.request_id
        WHERE c.state='pending' AND (r.trial IS NULL OR ? IS NULL OR r.trial!=?)''',
                  (active_trial, active_trial)).fetchone()[0]:
        raise ValueError('Unverified prior receipts block historical hold admission')
