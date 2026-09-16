"""Hard aggregate reservation ledger with optional approved trial estimates.

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
    def __init__(self, path, ceiling, trial_cap, stage_caps=None, *, allow_estimated_trials=False):
        if type(allow_estimated_trials) is not bool:
            raise ValueError('Explicit boolean estimation policy required')
        self.db = sqlite3.connect(path, timeout=30, isolation_level=None)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS policy (id INTEGER PRIMARY KEY CHECK(id=1), ceiling INTEGER, trial_cap INTEGER);
            CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY, trial TEXT NOT NULL, reserved INTEGER NOT NULL,
                charged INTEGER, state TEXT NOT NULL CHECK(state IN ('pending','settled')));
            CREATE TABLE IF NOT EXISTS incidents (request_id TEXT, actual INTEGER);
            CREATE TABLE IF NOT EXISTS stages (name TEXT PRIMARY KEY, cap INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS trial_stages (trial TEXT PRIMARY KEY, stage TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS generations (
                request_id TEXT PRIMARY KEY, generation_id TEXT UNIQUE NOT NULL);
            CREATE TABLE IF NOT EXISTS estimation_policy (
                id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS trial_estimates (
                request_id TEXT PRIMARY KEY, amount INTEGER NOT NULL);
        ''')
        with self.transaction():
            mode = self.db.execute('SELECT enabled FROM estimation_policy WHERE id=1').fetchone()
            if mode is None:
                if allow_estimated_trials and self.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]:
                    raise ValueError('Cannot change an existing funded ledger to estimated mode')
                self.db.execute('INSERT INTO estimation_policy VALUES (1,?)', (int(allow_estimated_trials),))
            elif mode[0] != int(allow_estimated_trials):
                raise ValueError('Existing estimation policy is immutable')
            self.db.execute('INSERT OR IGNORE INTO policy VALUES (1,?,?)', (dollars(ceiling), dollars(trial_cap)))
            policy = self.db.execute('SELECT ceiling,trial_cap FROM policy WHERE id=1').fetchone()
            if policy != (dollars(ceiling), dollars(trial_cap)):
                raise ValueError('Existing ledger policy is immutable')
            supplied = {name: dollars(cap) for name, cap in (stage_caps or {}).items()}
            stored = dict(self.db.execute('SELECT name,cap FROM stages'))
            if supplied and not stored:
                if self.exposure() or sum(supplied.values()) > policy[0]:
                    raise ValueError('Stage allocations must fit the ceiling and precede spending')
                self.db.executemany('INSERT INTO stages VALUES (?,?)', supplied.items())
            elif supplied != stored:
                raise ValueError('Existing stage allocations are immutable')
        self.ceiling, self.trial_cap = policy
        self.allow_estimated_trials = allow_estimated_trials

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

    def reserve(self, request_id, trial, maximum, available_account_credit, stage=None, *, trial_estimate=None):
        amount = dollars(maximum)
        if trial_estimate is not None and not self.allow_estimated_trials:
            raise ValueError('Estimated trial admission is not enabled for this ledger')
        trial_amount = amount if trial_estimate is None else dollars(trial_estimate)
        if not 0 < trial_amount <= amount:
            raise ValueError('Trial estimate must be positive and no greater than the hard reservation')
        if amount <= 0 or not request_id or not trial:
            raise ValueError('Positive reservation and identifiers required')
        # Caller supplies a fresh account balance; leave $2 untouched and also
        # reserve all unresolved charges that may not yet appear in that balance.
        available = dollars(available_account_credit) - dollars('2')
        with self.transaction():
            if self.db.execute('SELECT COUNT(*) FROM incidents').fetchone()[0]:
                raise BudgetExceeded('Ledger halted by billing incident')
            pending = self.db.execute("SELECT COALESCE(SUM(reserved),0) FROM requests WHERE state='pending'").fetchone()[0]
            if pending:
                raise BudgetExceeded('Resolve the outstanding request before dispatching another')
            stages = dict(self.db.execute('SELECT name,cap FROM stages'))
            if stages:
                if stage not in stages:
                    raise ValueError('A registered stage is required')
                linked = self.db.execute('SELECT stage FROM trial_stages WHERE trial=?', (trial,)).fetchone()
                if linked and linked[0] != stage:
                    raise ValueError('Trial cannot change stages')
                spent = self.db.execute('''SELECT COALESCE(SUM(COALESCE(r.charged,r.reserved)),0)
                    FROM requests r JOIN trial_stages t ON r.trial=t.trial WHERE t.stage=?''', (stage,)).fetchone()[0]
                if spent + amount > stages[stage]:
                    raise BudgetExceeded('Stage allocation exhausted')
                self.db.execute('INSERT OR IGNORE INTO trial_stages VALUES (?,?)', (trial, stage))
            # All earlier requests are settled (the pending barrier above).
            # Only the per-trial admission uses an approved estimate. Project,
            # stage and account checks retain the entire worst-case charge.
            if self.exposure() + amount > self.ceiling or self.exposure(trial) + trial_amount > self.trial_cap or pending + amount > available:
                raise BudgetExceeded('Reservation refused before dispatch')
            self.db.execute('INSERT INTO requests VALUES (?,?,?,NULL,?)',
                            (request_id, trial, amount, 'pending'))
            if trial_estimate is not None:
                self.db.execute('INSERT INTO trial_estimates VALUES (?,?)', (request_id, trial_amount))

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
            estimate = self.db.execute('SELECT amount FROM trial_estimates WHERE request_id=?', (request_id,)).fetchone()
            if charged > row[0] or (estimate is not None and charged > estimate[0]):
                # Persist a halt, including across process restarts.
                self.db.execute('INSERT INTO incidents VALUES (?,?)', (request_id, charged))
                overcharge = True
            self.db.execute("UPDATE requests SET charged=?,state='settled' WHERE id=?", (charged, request_id))
        if overcharge:
            raise BudgetExceeded('Charge exceeds reservation or trial estimate; ledger halted')

    def attach_generation(self, request_id, generation_id):
        if not isinstance(generation_id, str) or not generation_id or len(generation_id) > 256:
            raise ValueError('Invalid generation identifier')
        with self.transaction():
            if not self.db.execute('SELECT 1 FROM requests WHERE id=?', (request_id,)).fetchone():
                raise ValueError('Unknown request')
            self.db.execute('INSERT INTO generations VALUES (?,?)', (request_id, generation_id))

    def pending(self):
        return self.db.execute('''SELECT r.id,r.trial,r.reserved,g.generation_id
            FROM requests r LEFT JOIN generations g ON r.id=g.request_id
            WHERE r.state='pending' ORDER BY r.id''').fetchall()

    def close(self):
        self.db.close()
