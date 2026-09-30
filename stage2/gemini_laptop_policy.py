"""Separate, fixed Gemini development experiment. No historic scores reused."""
from decimal import Decimal
import hashlib
import json
import re

MODEL = 'google/gemini-3.7-flash'
SNAPSHOT = 'google/gemini-3.7-flash-20260813'
PROVIDER = 'google-ai-studio'
VERSION = 'stage2-c0-nc-gemini-0.1.0'
MAX_OUTPUT = 65536
CONTEXT = 1048576
INPUT_PRICE = Decimal('0.00000075')
OUTPUT_PRICE = Decimal('0.00000375')
# Reserve an entire context window plus maximum output, rounded UP with margin.
# Cache savings never fund a request until authoritative cost is available.
RESERVATION = Decimal('1.10')
CAP = Decimal('20')
PROTOCOL = dict(model=MODEL, expected_snapshot=SNAPSHOT, provider=PROVIDER,
    allow_fallbacks=False, temperature=1.0, top_p=1.0, reasoning_effort='high',
    max_output_tokens=MAX_OUTPUT, condition='C0-NC', version=VERSION,
    max_model_calls=None, automatic_retries=0, text_only=True, sequential=True,
    new_spending_cap_usd=str(CAP), request_reservation_usd=str(RESERVATION),
    resources='official', deadlines='official', task_attempts=20)


def fingerprint():
    return hashlib.sha256(json.dumps(PROTOCOL, sort_keys=True).encode()).hexdigest()


def credential(path):
    value = ''.join(path.read_text().split())
    if re.fullmatch('[0-9a-fA-F]{64}', value):
        value = 'sk-or-v1-' + value
    if not re.fullmatch(r'sk-or-v1-[0-9a-fA-F]{64}', value):
        raise ValueError('Invalid OpenRouter credential format')
    return value


def money(value):
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError('Invalid monetary evidence')
    return result


def wire(payload):
    """Fail closed on overrides, attachments, plugins, or other billable tools."""
    allowed = {'model', 'messages', 'tools', 'tool_choice', 'parallel_tool_calls',
        'temperature', 'top_p', 'max_tokens', 'max_completion_tokens',
        'reasoning', 'stream'}
    if set(payload) - allowed or payload.get('model') != MODEL or payload.get('stream'):
        raise ValueError('Unsupported model request')
    if not isinstance(payload.get('messages'), list) or not payload['messages']:
        raise ValueError('Messages required')
    for message in payload['messages']:
        if message.get('content') is not None and not isinstance(message['content'], str):
            raise ValueError('Text-only request required')
    if any(tool.get('type') != 'function' for tool in payload.get('tools', [])):
        raise ValueError('Only local function tools allowed')
    result = {k: v for k, v in payload.items() if k in
        {'messages', 'tools', 'tool_choice', 'parallel_tool_calls'}}
    result.update(model=MODEL, stream=False, temperature=1.0, top_p=1.0,
        max_tokens=MAX_OUTPUT, reasoning={'effort': 'high'}, usage={'include': True},
        provider={'only': [PROVIDER], 'allow_fallbacks': False,
            'require_parameters': True, 'max_price': {'prompt': 0.75, 'completion': 3.75}})
    return result


class BudgetStop(RuntimeError):
    pass


def atomic_json(path, value):
    """Replace a progress snapshot atomically; immutable trial evidence is separate."""
    import os
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix('.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class Ledger:
    """Durably reserve before dispatch; unknown charges keep their full reserve."""
    def __init__(self, path, available):
        self.path = path
        if path.exists():
            self.data = json.loads(path.read_text())
        else:
            self.data = dict(cap_usd=str(min(CAP, money(available))), requests=[])
            self.save()

    def save(self):
        atomic_json(self.path, self.data)

    @property
    def known(self):
        return sum((money(r['cost_usd']) for r in self.data['requests']
            if r.get('cost_usd') is not None), Decimal(0))

    @property
    def unresolved(self):
        return sum((money(r['reserved_usd']) for r in self.data['requests']
            if r.get('cost_usd') is None), Decimal(0))

    def reserve(self, trial_id, available):
        if (self.known + self.unresolved + RESERVATION > money(self.data['cap_usd'])
                or self.unresolved + RESERVATION > money(available)):
            raise BudgetStop('Insufficient allowance for maximum possible charge')
        row = dict(sequence=len(self.data['requests']), trial_id=trial_id,
            reserved_usd=str(RESERVATION), cost_usd=None, status='reserved')
        self.data['requests'].append(row)
        self.save()
        return row

    def settle(self, row, cost):
        cost = money(cost)
        if cost > money(row['reserved_usd']):
            raise RuntimeError('Provider charge exceeds reservation; stop study')
        row.update(cost_usd=str(cost), status='settled')
        self.save()

    def report(self):
        return dict(cap_usd=self.data['cap_usd'], known_spending_usd=str(self.known),
            unresolved_reserved_usd=str(self.unresolved),
            unresolved_requests=sum(r.get('cost_usd') is None for r in self.data['requests']),
            physical_requests=len(self.data['requests']))
