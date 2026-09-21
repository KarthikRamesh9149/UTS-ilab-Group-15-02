"""Explicit budget profile for a separate, user-authorised baseline repeat.

Absent profile means the original experiment is unchanged. A repeat must carry
forward all old unresolved liability, use a fresh ledger and preserve $1.
"""
import json
from decimal import Decimal
from pathlib import Path
import stat

NAME = 'baseline-repeat-budget-v1.json'


def read_profile(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    path = root / '.runtime/stage2' / NAME
    if not path.exists() and not path.is_symlink():
        return None
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise ValueError('Private regular repeat budget required')
    value = json.loads(path.read_text())
    if set(value) != {'experiment', 'authorised_utc_date', 'reserve_usd',
                      'historical_liability_usd', 'starting_balance_usd', 'ceiling_usd'}:
        raise ValueError('Exact repeat budget fields required')
    if (value['experiment'] != 'baseline-repeat-20260921'
            or value['authorised_utc_date'] != '2026-09-21'
            or value['reserve_usd'] != '1.00'):
        raise ValueError('Unsupported repeat authorisation')
    amounts = {}
    for key in ('reserve_usd', 'historical_liability_usd', 'starting_balance_usd', 'ceiling_usd'):
        amount = Decimal(value[key])
        if not amount.is_finite() or amount < 0 or amount * 10**9 != (amount * 10**9).to_integral_value():
            raise ValueError('Exact nonnegative USD required')
        amounts[key] = amount
    if amounts['ceiling_usd'] <= 0 or amounts['ceiling_usd'] > (
            amounts['starting_balance_usd'] - amounts['reserve_usd'] - amounts['historical_liability_usd']):
        raise ValueError('Repeat ceiling exceeds available funded credit')
    return value
