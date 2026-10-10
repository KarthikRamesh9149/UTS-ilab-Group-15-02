"""Carry the original Gemini allowance into a separately authorized comparison.

This ledger neither dispatches model calls nor authorizes another paid run.
Original requests, including unresolved charges, are immutable inherited evidence.
"""
import copy
import hashlib
import json
from pathlib import Path
from gemini_laptop_policy import CAP, Ledger, money, atomic_json

HARNESSES = frozenset({'terminus-2', 'openhands'})


class SharedBaselineLedger(Ledger):
    def __init__(self, path, available, *, prior_path, prior_sha256, cells):
        prior_path, path = Path(prior_path), Path(path)
        if prior_path.is_symlink() or path.is_symlink() or path.resolve() == prior_path.resolve():
            raise ValueError('Separate non-symlink baseline ledger required')
        raw = prior_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != prior_sha256:
            raise ValueError('Original ledger hash differs')
        prior = json.loads(raw)
        if money(prior['cap_usd']) != CAP or not isinstance(prior['requests'], list):
            raise ValueError('Original US$20 ledger required')
        self.prior = copy.deepcopy(prior)
        self.cells = dict(cells)
        if not self.cells or any(not isinstance(k, str) or not k or v not in HARNESSES
                                 for k, v in self.cells.items()):
            raise ValueError('Registered native baseline cells required')
        if not path.exists():
            # Credit exhaustion is evaluated by reserve(), never by discarding
            # prior charges or increasing the original experiment allowance.
            atomic_json(path, prior)
        super().__init__(path, available)
        self.check_inherited()

    def check_inherited(self):
        count = len(self.prior['requests'])
        if (self.data['cap_usd'] != self.prior['cap_usd']
                or self.data['requests'][:count] != self.prior['requests']
                or self.known + self.unresolved > CAP):
            raise ValueError('Inherited charge evidence or spending cap changed')
        for row in self.data['requests'][count:]:
            if self.cells.get(row['trial_id']) != row.get('harness'):
                raise ValueError('Unregistered baseline ledger entry')

    def reserve(self, trial_id, available):
        self.check_inherited()
        if trial_id not in self.cells:
            raise ValueError('Unregistered baseline trial')
        row = super().reserve(trial_id, available)
        row['harness'] = self.cells[trial_id]
        self.save()
        return row

    def settle(self, row, cost):
        self.check_inherited()
        new_rows = self.data['requests'][len(self.prior['requests']):]
        if not any(row is current for current in new_rows):
            raise ValueError('Only this comparison can settle its own requests')
        return super().settle(row, cost)
