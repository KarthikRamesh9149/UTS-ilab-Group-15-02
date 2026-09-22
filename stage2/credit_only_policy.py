"""Explicit, separate experiment policy. No balance or accounting admission."""
import json
import os
from pathlib import Path
import stat

MODE = 'provider-credit-only'
EXPERIMENT = 'baseline-provider-credit-only-20260922'
POLICY_FILE = 'credit-only-policy.json'
POLICY = {
    'schema_version': 1,
    'experiment': EXPERIMENT,
    'accounting_mode': MODE,
    'authorised_date': '2026-09-22',
    'per_task_cap_usd': None,
    'stage_cap_usd': None,
    'project_cap_usd': None,
    'reserve_usd': '0',
    'provider_max_price': None,
    'accounting_blocks_dispatch': False,
    'automatic_top_up': False,
    'automatic_replay': False,
}


def require_policy(runtime):
    path = Path(runtime) / POLICY_FILE
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('Owned private provider-credit-only policy required')
    value = json.loads(path.read_text())
    if value != POLICY:
        raise ValueError('Provider-credit-only experiment policy drift')
    return value
