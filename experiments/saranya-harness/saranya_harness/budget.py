"""Spending safety stop for runs without a model-call ceiling.

C0 ran with no call ceiling, so this harness has none either. Instead, every
model call is checked against two USD caps before it is sent:

- a per-trial cap (default 1.50, about four times C0's highest observed
  per-trial known cost of 0.37851930 on video-processing), and
- an overall cap shared by every trial that uses the same ledger file. It has
  no default: without one the harness refuses to call the model at all.

The check is conservative. Before each call it reserves the worst case: the
full output allowance plus an over-estimate of the prompt. After the call it
records the provider-reported cost, or an uncached list-price estimate, or
(when nothing is known) the whole reservation. A call cancelled at the task
deadline keeps its whole reservation, because it may still be billed.

Every record and every triggered stop is appended to a JSON-lines ledger.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import fcntl
import json
import logging
import os
from pathlib import Path
from typing import Iterator

from saranya_harness.openrouter import INPUT_PRICE, MAX_OUTPUT_TOKENS, OUTPUT_PRICE

DEFAULT_PER_TRIAL_CAP_USD = Decimal('1.50')
OVERALL_CAP_ENV = 'SARANYA_HARNESS_OVERALL_CAP_USD'
LEDGER_ENV = 'SARANYA_HARNESS_LEDGER'
# Deliberately pessimistic: real tokenizers average more characters per token.
CHARS_PER_TOKEN_ESTIMATE = 2

logger = logging.getLogger(__name__)


def reservation_for(prompt_chars: int) -> Decimal:
    prompt_tokens = prompt_chars // CHARS_PER_TOKEN_ESTIMATE + 1
    return prompt_tokens * INPUT_PRICE + MAX_OUTPUT_TOKENS * OUTPUT_PRICE


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class BudgetStop:
    scope: str  # 'per_trial' or 'overall'
    cap_usd: Decimal
    spent_usd: Decimal
    reservation_usd: Decimal


class BudgetGuard:
    def __init__(self, ledger_path: Path, trial_id: str, *, per_trial_cap_usd: Decimal, overall_cap_usd: Decimal):
        if per_trial_cap_usd <= 0 or overall_cap_usd <= 0:
            raise ValueError('Spending caps must be positive')
        self.ledger_path = Path(ledger_path)
        self.trial_id = trial_id
        self.per_trial_cap = per_trial_cap_usd
        self.overall_cap = overall_cap_usd
        self.trial_spent = Decimal(0)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_environment(cls, trial_id: str, *, per_trial_cap_usd: str | None = None,
                         overall_cap_usd: str | None = None, ledger_path: str | None = None) -> 'BudgetGuard':
        overall = overall_cap_usd or os.environ.get(OVERALL_CAP_ENV)
        ledger = ledger_path or os.environ.get(LEDGER_ENV)
        if not overall:
            raise ValueError(f'No overall spending cap: set {OVERALL_CAP_ENV} to the approved USD ceiling')
        if not ledger:
            raise ValueError(f'No spending ledger: set {LEDGER_ENV} to a file path outside the repository')
        per_trial = Decimal(per_trial_cap_usd) if per_trial_cap_usd else DEFAULT_PER_TRIAL_CAP_USD
        return cls(Path(ledger), trial_id, per_trial_cap_usd=per_trial, overall_cap_usd=Decimal(overall))

    @contextmanager
    def _locked(self) -> Iterator[None]:
        with open(self.ledger_path.with_suffix(self.ledger_path.suffix + '.lock'), 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _overall_spent(self) -> Decimal:
        if not self.ledger_path.exists():
            return Decimal(0)
        total = Decimal(0)
        with open(self.ledger_path) as ledger:
            for line in ledger:
                record = json.loads(line)
                if record.get('kind') == 'request':
                    total += Decimal(record['charged_usd'])
        return total

    def _append(self, record: dict) -> None:
        with open(self.ledger_path, 'a') as ledger:
            ledger.write(json.dumps(record, sort_keys=True) + '\n')
            ledger.flush()
            os.fsync(ledger.fileno())

    def check(self, prompt_chars: int) -> tuple[Decimal, BudgetStop | None]:
        """Return the reservation for the next call, and a stop if it must not be sent."""
        reservation = reservation_for(prompt_chars)
        with self._locked():
            overall_spent = self._overall_spent()
            stop = None
            if self.trial_spent + reservation > self.per_trial_cap:
                stop = BudgetStop('per_trial', self.per_trial_cap, self.trial_spent, reservation)
            elif overall_spent + reservation > self.overall_cap:
                stop = BudgetStop('overall', self.overall_cap, overall_spent, reservation)
            if stop is not None:
                self._append({'kind': 'stop', 'utc': _now(), 'trial_id': self.trial_id, 'scope': stop.scope,
                              'cap_usd': str(stop.cap_usd), 'spent_usd': str(stop.spent_usd),
                              'reservation_usd': str(stop.reservation_usd)})
        if stop is not None:
            logger.warning('Budget stop (%s) for %s: spent %s + reservation %s exceeds cap %s',
                           stop.scope, self.trial_id, stop.spent_usd, stop.reservation_usd, stop.cap_usd)
        return reservation, stop

    def record(self, *, charged_usd: Decimal, cost_source: str, prompt_tokens: int | None = None,
               completion_tokens: int | None = None, generation_id: str | None = None) -> None:
        """Record one sent request. Synchronous so it also runs during cancellation."""
        self.trial_spent += charged_usd
        with self._locked():
            self._append({'kind': 'request', 'utc': _now(), 'trial_id': self.trial_id,
                          'charged_usd': str(charged_usd), 'cost_source': cost_source,
                          'prompt_tokens': prompt_tokens, 'completion_tokens': completion_tokens,
                          'generation_id': generation_id})
