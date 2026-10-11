"""Key-free admission preparation for an unchanged US$50 native allowance.

Closed outcomes and ledger objects are immutable. This module grants no money
and does not dispatch model requests. The launcher exposes this path only for
synthetic qualification until the unresolved-charge stop has been reviewed.
"""
import copy
import hashlib
import json
from pathlib import Path

from gemini_baseline_budget import HARNESSES, SharedBaselineLedger
from gemini_laptop_policy import Ledger, atomic_json, money


def suffix_inputs(directory, manifest, cells):
    directory = Path(directory)
    paths = [('ledger.json', 'prior_ledger_sha256'),
             ('tasks.json', 'completed_tasks_sha256')]
    for name, field in paths:
        path = directory / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != manifest[field]:
            raise ValueError('Closed suffix evidence differs')
    rows = json.loads((directory / 'tasks.json').read_text())
    if (type(manifest['completed_attempts']) is not int
            or not 0 < len(rows) < 40 or len(rows) != manifest['completed_attempts']
            or len(cells) != 40 or len({c['trial_id'] for c in cells}) != 40
            or [c['order'] for c in cells] != list(range(1, 41))):
        raise ValueError('Exact closed prefix and forty ordered cells required')
    identities = ('order', 'trial_id', 'task_id', 'harness')
    for row, cell in zip(rows, cells):
        if (any(row.get(k) != cell[k] for k in identities)
                or not row.get('task_containers_removed')
                or not row.get('model_revoked') or row.get('cleanup_errors')
                or row.get('trace_errors')):
            raise ValueError('Closed prefix or cleanup differs')
    remaining = cells[len(rows):]
    if (manifest['scope'] != 'preparation_only_not_a_paid_run_authorization'
            or manifest['remaining_cells'] != remaining
            or manifest['closed_attempt_replays'] != 0):
        raise ValueError('Only the exact unstarted suffix is admitted')
    return directory / 'ledger.json', rows, remaining


class SameCapBaselineLedger(SharedBaselineLedger):
    """Copy a closed US$50 ledger, without applying another budget amendment."""
    def __init__(self, path, available, *, prior_path, prior_sha256, cells, manifest):
        path, prior_path = Path(path), Path(prior_path)
        if path.is_symlink() or prior_path.is_symlink() or path.resolve() == prior_path.resolve():
            raise ValueError('Separate non-symlink suffix ledger required')
        raw = prior_path.read_bytes()
        if (hashlib.sha256(raw).hexdigest() != prior_sha256
                or manifest['prior_ledger_sha256'] != prior_sha256):
            raise ValueError('Closed predecessor ledger hash differs')
        prior = json.loads(raw)
        grant = prior.get('authorization') or {}
        if (prior['cap_usd'] != '50' or manifest['inherited_cap_usd'] != '50'
                or manifest['proposed_total_cap_usd'] != '50'
                or manifest['additional_allowance_usd'] != '0'
                or grant.get('total_cap_usd') != '50'
                or grant.get('additional_cap_usd') != '30'
                or grant.get('user_answer') != 'Allow up to US$30 additional, spending as little as possible'):
            raise ValueError('Existing US$50 authorization must be preserved unchanged')
        self.prior, self.cells = copy.deepcopy(prior), dict(cells)
        if (not self.cells or any(not k or v not in HARNESSES for k,v in self.cells.items())
                or set(self.cells) & {r['trial_id'] for r in prior['requests']}):
            raise ValueError('Distinct unstarted native cells required')
        if (not isinstance(prior['requests'], list)
                or len(prior['requests']) != manifest['inherited_physical_requests']
                or [r['sequence'] for r in prior['requests']] != list(range(len(prior['requests'])))):
            raise ValueError('Complete ordered predecessor requests required')
        self.path, self.data = path, copy.deepcopy(prior)
        if (self.known != money(manifest['inherited_known_usd'])
                or self.unresolved != money(manifest['inherited_unresolved_reserved_usd'])
                or money('50') - self.known - self.unresolved != money(manifest['remaining_conservative_usd'])):
            raise ValueError('Predecessor amounts or unknown reserves differ')
        if not path.exists():
            atomic_json(path, prior)
        Ledger.__init__(self, path, available)
        self.check_inherited()

    def check_inherited(self):
        count = len(self.prior['requests'])
        if ({k:v for k,v in self.data.items() if k != 'requests'}
                != {k:v for k,v in self.prior.items() if k != 'requests'}
                or self.data['requests'][:count] != self.prior['requests']
                or self.known + self.unresolved > money('50')):
            raise ValueError('Inherited evidence or existing cap changed')
        for index, row in enumerate(self.data['requests'][count:], count):
            if row['sequence'] != index or self.cells.get(row['trial_id']) != row.get('harness'):
                raise ValueError('Unregistered or unordered suffix request')
