"""Fail-closed reservation ledger. Integration with a billing gateway is pending.

Amounts are integer nanodollars, never binary floating point. Reserve BEFORE
dispatch; interrupted/ambiguous requests retain their full reservation. A retry
requires a new reservation. External account balances must be checked upstream.
"""
from contextlib import contextmanager
from decimal import Decimal
import sqlite3

UNIT = 1_000_000_000


def dollars(value):
    amount = Decimal(str(value)) * UNIT
    if not amount.is_finite() or amount < 0 or amount != amount.to_integral_value():
        raise ValueError('Amount must be nonnegative exact nanodollars')
    return int(amount)


class BudgetExceeded(RuntimeError):
    pass


class Ledger:
    def __init__(self, path, ceiling, trial_cap):
        self.db = sqlite3.connect(path, timeout=30, isolation_level=None)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS policy (id INTEGER PRIMARY KEY CHECK(id=1), ceiling INTEGER, trial_cap INTEGER);
            CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY, trial TEXT NOT NULL, reserved INTEGER NOT NULL,
                charged INTEGER, state TEXT NOT NULL CHECK(state IN ('pending','settled')));
            CREATE TABLE IF NOT EXISTS incidents (request_id TEXT, actual INTEGER);
        ''')
        with self.transaction():
            self.db.execute('INSERT OR IGNORE INTO policy VALUES (1,?,?)', (dollars(ceiling), dollars(trial_cap)))
            policy = self.db.execute('SELECT ceiling,trial_cap FROM policy WHERE id=1').fetchone()
            if policy != (dollars(ceiling), dollars(trial_cap)):
                raise ValueError('Existing ledger policy is immutable')
        self.ceiling, self.trial_cap = policy

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def exposure(self, trial=None):
        query = 'SELECT COALESCE(SUM(COALESCE(charged,reserved)),0) FROM requests'
        return self.db.execute(query + (' WHERE trial=?' if trial is not None else ''),
                               (trial,) if trial is not None else ()).fetchone()[0]

    def reserve(self, request_id, trial, maximum, available_account_credit):
        amount = dollars(maximum)
        if amount <= 0 or not request_id or not trial:
            raise ValueError('Positive reservation and identifiers required')
        # Caller supplies a fresh account balance; leave $2 untouched and also
        # reserve all unresolved charges that may not yet appear in that balance.
        available = dollars(available_account_credit) - dollars('2')
        with self.transaction():
            if self.db.execute('SELECT COUNT(*) FROM incidents').fetchone()[0]:
                raise BudgetExceeded('Ledger halted by billing incident')
            pending = self.db.execute("SELECT COALESCE(SUM(reserved),0) FROM requests WHERE state='pending'").fetchone()[0]
            if self.exposure() + amount > self.ceiling or self.exposure(trial) + amount > self.trial_cap or pending + amount > available:
                raise BudgetExceeded('Reservation refused before dispatch')
            self.db.execute('INSERT INTO requests VALUES (?,?,?,NULL,?)',
                            (request_id, trial, amount, 'pending'))

    def settle(self, request_id, actual):
        charged = dollars(actual)
        overcharge = False
        with self.transaction():
            row = self.db.execute('SELECT reserved,charged,state FROM requests WHERE id=?', (request_id,)).fetchone()
            if row is None:
                raise ValueError('Unknown request')
            if row[2] == 'settled':
                if row[1] != charged:
                    raise ValueError('Conflicting billing evidence')
                return
            if charged > row[0]:
                # Persist a halt, including across process restarts.
                self.db.execute('INSERT INTO incidents VALUES (?,?)', (request_id, charged))
                overcharge = True
            self.db.execute("UPDATE requests SET charged=?,state='settled' WHERE id=?", (charged, request_id))
        if overcharge:
            raise BudgetExceeded('Charge exceeds reservation; ledger halted')

    def close(self):
        self.db.close()
