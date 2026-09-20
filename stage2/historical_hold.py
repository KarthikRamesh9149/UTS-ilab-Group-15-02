"""Exact disclosed historical liabilities, never receipts or charge corrections.

Version one names the interrupted 2026-09-19 dispatch. The append-only second
version names exactly one additional 2026-09-20 dispatch and preserves v1.
Every use rechecks original evidence and ledger facts. No caller supplies an
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
SIDECAR_V2 = 'historical-holds-v2.json'
PRIOR_SIDECAR_SHA256 = '0b0d8f9419ab41f3b2f4cb7e4407e02a461de8b9f1b7d772385462755be43c92'
SECOND_REQUEST_ID = '5464bb2d-0767-42ff-86d7-66b11ab737ad'
SECOND_TRIAL_ID = 'dev-terminus-2-05-reshard-c4-data'
SECOND_TRIAL_ESTIMATE_NANODOLLARS = 7_624_600
SECOND_SETTLED_NANODOLLARS = 2_876_760
SECOND_RESULT_SHA256 = '45abaf15c1a88ea01dcbbfb019596cb7cf322a208bd2f734e657216b7af01c05'
SECOND_LEDGER_SHA256 = '9eb1a8b631c55b48c2018317c0835683175484e41a42fa3686dd12b39e988484'
SECOND_ATTEMPT_HASHES = {
    'started.json': '5372d562dc54c5e1485f53dad75e584769f26ae0120785b82381488760e53d33',
    '000001.request.json': '2e359d1424756e1dd697c85624cfff5dc7fe5e7287c855013468f242c0575289',
    '000001.response.json': '4ac4d318b1693afdee39c945db80c819b9d2910825b0b59e91d45e7e200999bf',
    '000001.receipt.json': '5f4831e7aebb29268ddc10700558cec3d7aaae90021babb2a653a9a9fc9ec5a8',
    '000001.timing.json': '617a9a1aee09d559dcabfd668c66af7346a2776ceae5529d2794618a2f5406ca',
    '000002.request.json': '85a0e63d9966bb98b544df0f3fc1e00f8bc7def306123918239bcb8034903eb5',
    '000002.response.json': '0070795c6c1dba4fb8c61a301a8c3f9d0910851278e1c7cbc2acab17af12f51d',
    '000002.receipt.json': 'b4cbf5148e37456f268a8656077dc4a1aba566f8a66e5d28713999ad0c5f7959',
    '000002.timing.json': 'd6226786bcb8c9f3e97bc2dc0d46f1149b1a44950478c7ea2bfbbfc9108c2940',
    '000003.request.json': 'ec368a8191a4a0422356427a2f3c537f714edc929bcfa2c94f5f092667faa666',
    '000003.response.json': '40845a92ebe2c167cf6244e41a1daeb634c49afcf95464bc677983e5f31f3f7f',
    '000003.receipt.json': '44ad580d254a553feaa8bb284d7f71481eb5711a5c249adbf1a48f3cc04166c0',
    '000003.timing.json': '52c4492e29936b2c44ab8860f3c24cdd0f0af4de81508f8b0c78b9c73b82855a',
    '000004.request.json': 'c3d53782bcf35de2de178f578a0b16749df662f72e82ff5f8acda42294170af8',
    '000004.response.json': '39e39e3af1e0a39b54254be8d492f8014319f6eb63147efce26e8775a2262b9f',
    '000004.receipt.json': 'cc05fb0ff1110305ad46cde0b368ff6c41dfe78975caf11e45a447dccc452ede',
    '000004.timing.json': 'db92137f610e5056d105cb5b2cfc7874ba9a32323fd8f55b4451fd83ee45bdbb',
    '000005.request.json': 'db8ee6c57c7c1265956ed41e4409abeb8b008d17b7a1b4029016f026f86eae81',
    '000005.response.json': '8f311e3db290f68b60d73250b34a45b00ab726446dc638e8b482881ddec69af7',
    '000005.receipt.json': 'bf17162a0c60ef2223a0bda9f01c6c272c0d562e92227a171bea9e2f01cf6d34',
    '000005.timing.json': '5247bc950b1edecbd58db32974b891a652e143ec3a75193f17e38ca64abdf9d4',
    '000006.request.json': 'db8ee6c57c7c1265956ed41e4409abeb8b008d17b7a1b4029016f026f86eae81',
    '000006.timing.json': '375a7e7eb5176e8965c3f7beea1875f58916d0c69b795bbce291513050f645c7',
}
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
# Original identity/money facts, with receipt state required AFTER the separate
# retained-receipt repair. The archived five settled-row flags were pending.
SECOND_ORIGINAL_ROWS = (
    ('7648c6c2-a378-4dc3-8f7e-45929c96d7d9', RESERVED_NANODOLLARS, 113940, 'settled',
     4390200, 'gen-1789867291-QS8Jt4lBZ1clrQBBFsqv', 'verified'),
    ('788d4e5f-b6c1-47b7-9e46-2e55cc2e5d4e', RESERVED_NANODOLLARS, 96660, 'settled',
     4733000, 'gen-1789867304-WcQGJGGOFgAduTuHZXX8', 'verified'),
    ('ec31e18b-e893-4aff-b4bd-78306df6add8', RESERVED_NANODOLLARS, 160740, 'settled',
     5712400, 'gen-1789867325-eGYlaiyxowSDHtZr9ScW', 'verified'),
    ('2061ccb0-d591-45a4-9620-21eae8bb7ae5', RESERVED_NANODOLLARS, 824280, 'settled',
     7065400, 'gen-1789867341-FGiNiLJeaBx3apUcv2tQ', 'verified'),
    ('fa13d9d4-a9d8-43ba-bb62-fdd60565c20d', RESERVED_NANODOLLARS, 1681140, 'settled',
     7624600, 'gen-1789867430-CnN2r9EJ5IN1pky315wV', 'verified'),
    (SECOND_REQUEST_ID, RESERVED_NANODOLLARS, None, 'pending',
     SECOND_TRIAL_ESTIMATE_NANODOLLARS, None, None),
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


def canonical_v2_document():
    """Two named holds plus explicit prospective completion approval; no writes.

    The original ledger digest is provenance, not a current database digest:
    five retained receipts must be verified separately before this registry can
    validate. No reservation, charge, generation or result is changed here.
    """
    first = canonical_hold_document()
    second = dict(first, request_id=SECOND_REQUEST_ID, trial_id=SECOND_TRIAL_ID,
                  task_id='reshard-c4-data', trial_estimate_nanodollars=SECOND_TRIAL_ESTIMATE_NANODOLLARS,
                  settled_subtotal_nanodollars=SECOND_SETTLED_NANODOLLARS,
                  original_result_sha256=SECOND_RESULT_SHA256,
                  evidence_sha256=dict(SECOND_ATTEMPT_HASHES),
                  original_scored_ledger_sha256=SECOND_LEDGER_SHA256)
    for entry in (first, second):
        for name in ('schema_version', 'amendment_id', 'classification',
                     'aggregate_cap_nanodollars', 'trial_cap_nanodollars', 'stage_caps_nanodollars'):
            del entry[name]
    return {
        'schema_version': 2,
        'amendment_id': 'bounded-historical-holds-v2-completion-20260920',
        'classification': 'post_incident_prospective_completion_amendment',
        'approval_scope': 'user_approved_two_named_holds_and_collection_despite_preliminary_performance',
        'prior_amendment': {'path': SIDECAR, 'sha256': PRIOR_SIDECAR_SHA256},
        'model_protocol_sha256': MODEL_PROTOCOL_SHA256,
        'holds': [first, second],
        'reserved_nanodollars': 2 * RESERVED_NANODOLLARS,
        'charged_nanodollars': None, 'billing_verified': False,
        'replay_authorized': False, 'additional_unknown_hold_authorized': False,
        'completion_despite_preliminary_performance': True,
        'original_qualification_gate_satisfied': False,
        'aggregate_cap_nanodollars': 8_901_000_000,
        'trial_cap_nanodollars': 23_000_000,
        'stage_caps_nanodollars': {'development': 2_760_000_000, 'final': 6_141_000_000},
        'setup_cap_nanodollars': 1_000_000_000, 'account_reserve_nanodollars': 2_000_000_000,
        'required_known_receipt_state': 'verified',
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


def hold_entries(validated):
    """Entries from an already validated registry; never caller exceptions."""
    if validated is None:
        return ()
    if validated.get('schema_version') == 2:
        return tuple(validated['holds'])
    return (validated,)


def hold_for_trial(validated, trial_id):
    return next((entry for entry in hold_entries(validated) if entry['trial_id'] == trial_id), None)


def validate_historical_hold(runtime, db=None, *, active_trial=None):
    """Return the evidence-validated registry, or None without an amendment.

    A supplied connection must be the canonical ledger and must already be in
    a transaction. Reserve passes its BEGIN IMMEDIATE connection, keeping the
    exception check and new reservation atomic. Current-trial receipt checks
    may remain deferred; unrelated unresolved billing always blocks admission.
    """
    runtime = Path(runtime).absolute()
    version_two = (runtime / SIDECAR_V2).exists() or (runtime / SIDECAR_V2).is_symlink()
    path = runtime / (SIDECAR_V2 if version_two else SIDECAR)
    if not path.exists() and not path.is_symlink():
        return None
    try:
        info = runtime.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('Historical hold runtime must be owned and private')
        data = _regular_bytes(path, runtime, private=True)
        document = json.loads(data, object_pairs_hook=_unique_object)
        expected = canonical_v2_document() if version_two else canonical_hold_document()
        if json.dumps(document, sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise ValueError('Historical hold amendment identity mismatch')
        entries = expected['holds'] if version_two else [expected]
        if version_two:
            prior = _regular_bytes(runtime / SIDECAR, runtime, private=True)
            if (hashlib.sha256(prior).hexdigest() != PRIOR_SIDECAR_SHA256
                    or json.dumps(json.loads(prior, object_pairs_hook=_unique_object), sort_keys=True)
                    != json.dumps(canonical_hold_document(), sort_keys=True)):
                raise ValueError('Original historical hold amendment changed')
        if any(active_trial == entry['trial_id'] for entry in entries):
            raise ValueError('Historical trial cannot dispatch or verify again')
        if read_protocol(runtime).fingerprint() != MODEL_PROTOCOL_SHA256:
            raise ValueError('Historical hold model protocol mismatch')
        for entry in entries:
            attempt = runtime / 'scored-attempts' / entry['trial_id']
            if {p.name for p in attempt.iterdir()} != set(entry['evidence_sha256']):
                raise ValueError('Historical request evidence inventory changed')
            for name, digest in entry['evidence_sha256'].items():
                if hashlib.sha256(_regular_bytes(attempt / name, runtime)).hexdigest() != digest:
                    raise ValueError('Historical request evidence changed')
            result = runtime / 'scored-trials' / entry['trial_id'] / 'result.json'
            if hashlib.sha256(_regular_bytes(result, runtime)).hexdigest() != entry['original_result_sha256']:
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
                _validate_rows(reader, active_trial, entries)
            finally:
                reader.close()
        else:
            databases = db.execute('PRAGMA database_list').fetchall()
            if not db.in_transaction or not any(name == 'main' and Path(filename).resolve() == database.resolve()
                                               for _, name, filename in databases):
                raise ValueError('Historical hold requires canonical transaction')
            _validate_rows(db, active_trial, entries)
        # Raw markers stay unchanged. Original Ledger.reserve checked the
        # pending barrier before all caps. Both pinned markers occurred after
        # generation 3 failed and retained this reservation, with no dispatch 4.
        # The second trial has no durable stop marker; its error type alone is
        # not evidence of capacity exhaustion.
        sidecar_sha256 = hashlib.sha256(data).hexdigest()
        views = [dict(entry, sidecar_sha256=sidecar_sha256,
                      budget_stop_count=2 if entry['trial_id'] == TRIAL_ID else 0,
                      budget_stop_classification='historical_pending_barrier'
                      if entry['trial_id'] == TRIAL_ID else 'no_budget_stop',
                      capacity_budget_stop_count=0) for entry in entries]
        if version_two:
            return dict(expected, sidecar_sha256=sidecar_sha256, holds=views)
        return views[0]
    except (OSError, sqlite3.Error, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError('Historical hold evidence unavailable or invalid') from exc


def _validate_rows(db, active_trial, entries):
    if db.execute('SELECT ceiling,trial_cap FROM policy WHERE id=1').fetchone() != (8_901_000_000, 23_000_000):
        raise ValueError('Historical hold cannot change budget policy')
    if dict(db.execute('SELECT name,cap FROM stages')) != {'development': 2_760_000_000, 'final': 6_141_000_000}:
        raise ValueError('Historical hold cannot change stage allocations')
    if db.execute('SELECT enabled FROM estimation_policy WHERE id=1').fetchone() != (1,):
        raise ValueError('Historical hold requires original estimation policy')
    for entry in entries:
        rows = db.execute('''SELECT r.id,r.reserved,r.charged,r.state,e.amount,g.generation_id,c.state
            FROM requests r LEFT JOIN trial_estimates e ON e.request_id=r.id
            LEFT JOIN generations g ON g.request_id=r.id LEFT JOIN receipt_checks c ON c.request_id=r.id
            WHERE r.trial=?''', (entry['trial_id'],)).fetchall()
        expected = ORIGINAL_ROWS if entry['trial_id'] == TRIAL_ID else SECOND_ORIGINAL_ROWS
        if sorted(rows) != sorted(expected):
            raise ValueError('Original historical ledger rows changed or retained receipts unverified')
        if db.execute('SELECT stage FROM trial_stages WHERE trial=?', (entry['trial_id'],)).fetchone() != ('development',):
            raise ValueError('Historical trial stage changed')
    if db.execute('SELECT COUNT(*) FROM incidents').fetchone()[0]:
        raise ValueError('Billing incident blocks historical hold admission')
    excluded = ','.join('?' for entry in entries)
    if db.execute("SELECT COUNT(*) FROM requests WHERE (state!='settled' OR charged IS NULL) AND id NOT IN ("
                  + excluded + ')', tuple(entry['request_id'] for entry in entries)).fetchone()[0]:
        raise ValueError('Another unresolved dispatch blocks historical hold admission')
    if db.execute('''SELECT COUNT(*) FROM receipt_checks c LEFT JOIN requests r ON r.id=c.request_id
        WHERE c.state='pending' AND (r.trial IS NULL OR ? IS NULL OR r.trial!=?)''',
                  (active_trial, active_trial)).fetchone()[0]:
        raise ValueError('Unverified prior receipts block historical hold admission')
