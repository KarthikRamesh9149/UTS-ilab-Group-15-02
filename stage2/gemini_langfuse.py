"""Backfill completed Gemini trials to laptop-only Langfuse without model calls.

Reads the immutable metadata spool; raw exchanges and tool outputs stay private.
Stable span IDs and durable batch receipts support interrupted imports. Readback
checks every observation ID, rather than treating HTTP acceptance as completion.
"""
import argparse
import base64
from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, build_opener, ProxyHandler

from local_langfuse import NoRedirect, attribute, payload
from local_trace import validate

BASE_URL = 'http://127.0.0.1:3300'


def load_events(directory):
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('Non-symlink existing evidence directory required')
    events = []
    for path in sorted(directory.glob('*.json')):
        if path.is_symlink():
            raise ValueError('Symlink in evidence')
        event = validate(json.loads(path.read_text(encoding='utf-8')))
        if path.stem != event['event_id']:
            raise ValueError('Spool filename mismatch')
        events.append(event)
    return sorted(events, key=lambda event: event['sequence'])


def trial_payload(events, row, *, experiment='gemini-dev20-laptop-20260930'):
    if not events or {e['trial_id'] for e in events} != {row['trial_id']}:
        raise ValueError('Trial/result mismatch')
    if {e['task_id'] for e in events} != {row['task_id']}:
        raise ValueError('Task/result mismatch')
    body = payload(events, track='gemini-laptop')
    spans = body['resourceSpans'][0]['scopeSpans'][0]['spans']
    event_by_id = {e['event_id'][:16]: e for e in events}
    for span in spans:
        event = event_by_id[span['spanId']]
        attrs = span['attributes']
        for key, value in (
            ('experiment', experiment),
            ('classification', row['classification']),
            ('physical_requests', row['physical_requests']),
            ('known_spending_usd', row['known_spending_usd']),
            ('unresolved_requests', row['unresolved_requests']),
            ('reward_status', 'unscored' if row.get('reward') is None else 'official'),
        ):
            attrs.append(attribute('langfuse.trace.metadata.' + key, value))
        if row.get('reward') is not None:
            attrs.append(attribute('langfuse.trace.metadata.official_verifier_reward', row['reward']))
        attrs.append(attribute('langfuse.observation.level',
                               'DEFAULT' if event['status'] == 'ok' else 'ERROR'))
        attrs.append(attribute('uts.sequence', event['sequence']))
        for entry in attrs:
            if entry['key'] == 'langfuse.observation.type':
                kind = {'agent': 'agent', 'tool': 'tool', 'graph': 'chain'}.get(event['kind'])
                if kind:
                    entry['value'] = {'stringValue': kind}
    return body


def batches(body, size=200):
    if type(size) is not int or not 1 <= size <= 1000:
        raise ValueError('Invalid batch size')
    resource = body['resourceSpans'][0]
    scope = resource['scopeSpans'][0]
    for start in range(0, len(scope['spans']), size):
        yield {'resourceSpans': [{
            'resource': resource['resource'],
            'scopeSpans': [{'scope': scope['scope'], 'spans': scope['spans'][start:start + size]}],
        }]}


class LocalClient:
    def __init__(self, credentials):
        if credentials.get('LANGFUSE_BASE_URL') != BASE_URL:
            raise ValueError('Only the configured laptop Langfuse origin is allowed')
        public = credentials['LANGFUSE_PUBLIC_KEY']
        secret = credentials['LANGFUSE_SECRET_KEY']
        if not public.startswith('pk-lf-') or not secret.startswith('sk-lf-'):
            raise ValueError('Invalid Langfuse project credentials')
        self.destination = hashlib.sha256((BASE_URL + ':' + public).encode()).hexdigest()
        self.auth = 'Basic ' + base64.b64encode((public + ':' + secret).encode()).decode()
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, path, body=None):
        if not path.startswith('/api/public/'):
            raise ValueError('Public API path required')
        request = Request(BASE_URL + path,
            data=None if body is None else json.dumps(body, allow_nan=False).encode(),
            headers={'Authorization': self.auth, 'Content-Type': 'application/json',
                     'x-langfuse-ingestion-version': '4'})
        with self.opener.open(request, timeout=30) as response:
            return json.loads(response.read() or b'{}')

    def send(self, body, state, *, reexport=False):
        encoded = json.dumps(body, sort_keys=True, allow_nan=False).encode()
        digest = hashlib.sha256(self.destination.encode() + encoded).hexdigest()
        receipt = Path(state) / (digest + '.json')
        if receipt.is_symlink():
            raise ValueError('Invalid receipt')
        if receipt.exists() and not reexport:
            return 'previously_acknowledged'
        answer = self.request('/api/public/otel/v1/traces', body)
        partial = answer.get('partialSuccess', {})
        if int(partial.get('rejectedSpans', 0)) or partial.get('errorMessage'):
            raise RuntimeError('Partial ingestion; metadata retained for retry')
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps({'status': 'transport_acknowledged',
            'payload_sha256': hashlib.sha256(encoded).hexdigest()}), encoding='utf-8')
        return 'transport_acknowledged'

    def readback(self, events):
        earliest = min(e['started_ns'] for e in events) / 1e9
        latest = max(e['ended_ns'] for e in events) / 1e9
        query = dict(traceId=events[0]['trace_id'][:32], fields='core,basic,usage,model,metadata',
            limit=1000, fromStartTime=datetime.fromtimestamp(earliest, timezone.utc).isoformat(),
            toStartTime=(datetime.fromtimestamp(latest, timezone.utc) + timedelta(seconds=1)).isoformat())
        found = {}
        cursors = set()
        while True:
            result = self.request('/api/public/v2/observations?' + urlencode(query))
            for row in result['data']:
                found[row['id']] = row
            cursor = result.get('meta', {}).get('cursor')
            if not cursor:
                break
            if cursor in cursors:
                raise RuntimeError('Repeated readback cursor')
            cursors.add(cursor)
            query['cursor'] = cursor
        expected = {e['event_id'][:16] for e in events}
        return dict(expected_observations=len(expected), observed_observations=len(found),
            missing_observations=len(expected - set(found)),
            unexpected_observations=len(set(found) - expected),
            matched=expected == set(found))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--credentials', type=Path)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--readback-only', action='store_true')
    parser.add_argument('--reexport', action='store_true')
    parser.add_argument('--experiment', default='gemini-dev20-laptop-20260930')
    args = parser.parse_args()
    rows = json.loads((args.results / 'tasks.json').read_text(encoding='utf-8'))
    prepared = []
    for row in rows:
        events = load_events(args.source / row['trial_id'])
        prepared.append((row, events, trial_payload(events, row, experiment=args.experiment)))
    report = {'experiment': args.experiment, 'base_url': BASE_URL,
        'model_api_calls': 0, 'trials': [], 'status': 'prepared_metadata_only'}
    client = None
    if not args.prepare_only:
        if args.credentials is None:
            raise ValueError('Private credential file required')
        client = LocalClient(json.loads(args.credentials.read_text(encoding='utf-8')))
    for row, events, body in prepared:
        item = dict(trial_id=row['trial_id'], task_id=row['task_id'],
            observations=len(events), kinds=dict(Counter(e['kind'] for e in events)),
            official_reward=row.get('reward'), classification=row['classification'])
        if client:
            if not args.readback_only:
                item['batches'] = [client.send(batch, args.state, reexport=args.reexport)
                                   for batch in batches(body)]
            item['readback'] = client.readback(events)
        report['trials'].append(item)
    if client:
        report['status'] = ('verified_all_observation_ids' if all(
            t['readback']['matched'] for t in report['trials']) else 'ingestion_pending_readback')
    report['observations'] = sum(t['observations'] for t in report['trials'])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'status': report['status'], 'trials': len(rows),
                      'observations': report['observations'], 'model_api_calls': 0}))
    return 0 if report['status'] != 'ingestion_pending_readback' else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        # Do not expose credentials or private HTTP response bodies.
        print(json.dumps({'status': 'backfill_failed_evidence_retained', 'error_type': type(exc).__name__}))
        raise SystemExit(1)
