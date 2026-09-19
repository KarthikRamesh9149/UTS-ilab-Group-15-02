"""Post-run Langfuse v4 readback of completed, metadata-only Harbor traces.

No model calls or benchmark mutations. A successful OTLP acknowledgement is
not readback evidence, and API readback is not a screenshot/dashboard check.
Contract: https://langfuse.com/docs/api-and-data-platform/features/public-api
"""
import argparse
import base64
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlencode
from urllib.request import Request, build_opener, ProxyHandler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gateway_policy import MODEL
from local_langfuse import NoRedirect, SELF_HOSTED_BASE, export, payload
from local_trace import TraceSpool
from scored_gateway import durable_json


def credentials(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise ValueError('Private, non-symlink credential file required')
    data = json.loads(path.read_text())
    if data.get('base_url') != SELF_HOSTED_BASE:
        raise ValueError('Only the private self-hosted study destination is allowed')
    for key, prefix in [('public_key', 'pk-lf-'), ('secret_key', 'sk-lf-')]:
        if not isinstance(data.get(key), str) or not data[key].startswith(prefix):
            raise ValueError('Langfuse project credentials required')
    return {key: data[key] for key in ('base_url', 'public_key', 'secret_key')}


def read_observations(events, auth, *, get=None):
    # Validate completion, identifiers and trial lifetimes before any request.
    payload(events, track='netcup-openrouter')
    if auth.get('base_url') != SELF_HOSTED_BASE:
        raise ValueError('Unapproved readback destination')
    opener = build_opener(ProxyHandler({}), NoRedirect())
    token = base64.b64encode((auth['public_key'] + ':' + auth['secret_key']).encode()).decode()

    def retrieve(query):
        req = Request(SELF_HOSTED_BASE + '/api/public/v2/observations?' + urlencode(query),
                      headers={'Authorization': 'Basic ' + token}, method='GET')
        with opener.open(req, timeout=30) as response:
            if response.status != 200:
                raise RuntimeError('Langfuse readback did not return HTTP 200')
            raw = response.read(4_000_001)
        if len(raw) > 4_000_000:
            raise ValueError('Unexpectedly large readback page')
        return json.loads(raw)

    fetch = get or retrieve
    rows = []
    for trace in sorted({event['trace_id'] for event in events}):
        subset = [event for event in events if event['trace_id'] == trace]
        start = min(event['started_ns'] for event in subset) // 1_000_000_000
        end = max(event['ended_ns'] for event in subset) // 1_000_000_000 + 1
        iso = lambda seconds: datetime.fromtimestamp(seconds, timezone.utc).isoformat()
        query = {'traceId': trace[:32], 'fields': 'core,basic,model,usage,metadata', 'limit': 1000,
                 'fromStartTime': iso(start), 'toStartTime': iso(end)}
        seen = set()
        for _ in range(50):
            result = fetch(dict(query))
            if not isinstance(result, dict) or not isinstance(result.get('data'), list) or not isinstance(result.get('meta'), dict):
                raise ValueError('Invalid observations response')
            rows.extend(result['data'])
            cursor = result['meta'].get('cursor')
            if cursor is None or cursor == '':
                break
            if not isinstance(cursor, str) or len(cursor) > 8192 or cursor in seen:
                raise ValueError('Invalid or repeated pagination cursor')
            seen.add(cursor)
            query['cursor'] = cursor
        else:
            raise ValueError('Observation pagination exceeds the explicit bound')
    return rows


def verify(events, rows):
    payload(events, track='netcup-openrouter')
    expected = {(event['trace_id'][:32], event['event_id'][:16]): event for event in events}
    if len(expected) != len(events):
        raise ValueError('Duplicate or colliding span identity')
    actual = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid observation row')
        identity = (row.get('traceId'), row.get('id'))
        if identity not in expected or identity in actual:
            raise ValueError('Unexpected or duplicate observation')
        actual[identity] = row
    if set(actual) != set(expected):
        raise ValueError('Langfuse observations incomplete; keep the local spool')
    roots = {event['trace_id']: event['event_id'][:16] for event in events if event['kind'] == 'trial'}
    totals = {'generations': 0, 'input_tokens': 0, 'output_tokens': 0, 'charged_nanodollars': 0}
    rewards = {}
    for identity, event in expected.items():
        row = actual[identity]
        generation = event['kind'] == 'generation'
        if row.get('name') != event['kind'] or row.get('type') != ('GENERATION' if generation else 'SPAN'):
            raise ValueError('Observation type/name mismatch')
        if row.get('sessionId') != event['trial_id']:
            raise ValueError('Observation trial association mismatch')
        parent = row.get('parentObservationId') or None
        if parent != (None if event['kind'] == 'trial' else roots[event['trace_id']]):
            raise ValueError('Observation parent mismatch')
        metadata = row.get('metadata') or {}
        if any(metadata.get(key) != event[key] for key in ('harness', 'task_id', 'protocol_sha256', 'status')):
            raise ValueError('Observation protocol/task metadata mismatch')
        if 'duration_seconds' in event['metrics']:
            duration = metadata.get('attributes.uts.duration_seconds')
            if type(duration) not in (int, float) or duration != event['metrics']['duration_seconds']:
                raise ValueError('Measured phase duration mismatch')
        if event['reward'] is not None:
            reward = metadata.get('attributes.uts.official_verifier_reward')
            if type(reward) not in (int, float) or reward != event['reward']:
                raise ValueError('Official verifier reward mismatch')
            rewards[event['trial_id']] = reward
        if generation:
            if row.get('model') != MODEL:
                raise ValueError('Observation model mismatch')
            usage = row.get('usageDetails') or {}
            for key, field in [('input_tokens', 'input'), ('output_tokens', 'output')]:
                number = usage.get(field)
                if type(number) not in (int, float) or number != event['metrics'].get(key):
                    raise ValueError('Generation token count mismatch')
                totals[key] += event['metrics'][key]
            charge = Decimal(str(row.get('totalCost'))) * 1_000_000_000
            expected_charge = event['metrics'].get('charged_nanodollars')
            if type(expected_charge) is not int or not charge.is_finite() or abs(charge - expected_charge) > Decimal('0.001'):
                raise ValueError('Generation charge mismatch')
            totals['charged_nanodollars'] += expected_charge
            totals['generations'] += 1
    canonical = json.dumps(events, sort_keys=True, allow_nan=False).encode()
    return {'status': 'observations_api_verified_dashboard_pending',
            'events': len(events), 'trials': len(roots), 'metrics': totals,
            'verifier_rewards': rewards,
            'event_collection_sha256': hashlib.sha256(canonical).hexdigest(),
            'checks': {'exact_span_set': True, 'trial_association': True,
                       'generation_model_tokens_cost': True,
                       'protocol_metadata_phase_durations_and_rewards': True},
            'dashboard_visually_verified': False, 'raw_task_text_exported': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spool', type=Path, required=True)
    parser.add_argument('--credentials', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--export', action='store_true', help='Idempotent metadata upload before readback')
    args = parser.parse_args()
    try:
        auth = credentials(args.credentials)
        events = TraceSpool(args.spool).events()
        if args.export:
            export(args.spool, track='netcup-openrouter', **auth)
        result = verify(events, read_observations(events, auth))
        durable_json(args.output, result)
        print(json.dumps(result))
    except Exception as exc:
        # Never print response bodies, credential values or raw task metadata.
        print(json.dumps({'status': 'readback_not_verified_spool_retained', 'error_type': type(exc).__name__}))
        raise SystemExit(1)
