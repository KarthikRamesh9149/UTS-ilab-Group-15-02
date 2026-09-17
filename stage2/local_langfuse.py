"""Explicit post-run metadata export to Langfuse using OTLP/HTTP JSON.

No SDK autoinstrumentation, model traffic or task text is exported here.
Transport contract: https://langfuse.com/integrations/native/opentelemetry
Live provider acceptance remains a separate qualification check.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler

from cetus_local_probe import MODEL
from local_trace import TraceSpool, validate

BASES = {'https://cloud.langfuse.com', 'https://us.cloud.langfuse.com', 'https://jp.cloud.langfuse.com'}


def attribute(key, value):
    if type(value) is int:
        data = {'intValue': str(value)}
    elif type(value) is float:
        data = {'doubleValue': value}
    else:
        data = {'stringValue': str(value)}
    return {'key': key, 'value': data}


def payload(events):
    if not events:
        raise ValueError('No completed observations to export')
    for event in events:
        validate(event)
    roots = {}
    for event in events:
        if event['kind'] == 'trial':
            if event['trace_id'] in roots:
                raise ValueError('Multiple roots in one trial')
            roots[event['trace_id']] = event
    if {e['trace_id'] for e in events} != set(roots):
        raise ValueError('Only completed trials with root observations may export')
    spans = []
    for event in events:
        root = roots[event['trace_id']]
        if not root['started_ns'] <= event['started_ns'] <= event['ended_ns'] <= root['ended_ns']:
            raise ValueError('Observation outside trial lifetime')
        attrs = [attribute('langfuse.observation.type', 'generation' if event['kind'] == 'generation' else 'span'),
                 attribute('langfuse.trace.name', 'cetus-local-' + event['harness']),
                 attribute('langfuse.session.id', event['trial_id'])]
        for key in ('harness', 'task_id', 'protocol_sha256', 'status'):
            attrs.append(attribute('langfuse.trace.metadata.' + key, event[key]))
        for key, value in event['metrics'].items():
            attrs.append(attribute('uts.' + key, value))
        if event['reward'] is not None:
            attrs.append(attribute('uts.official_verifier_reward', event['reward']))
        if event['kind'] == 'generation':
            attrs.append(attribute('gen_ai.request.model', MODEL))
            for key, name in [('input_tokens', 'gen_ai.usage.input_tokens'),
                              ('output_tokens', 'gen_ai.usage.output_tokens')]:
                if key in event['metrics']:
                    attrs.append(attribute(name, event['metrics'][key]))
        span = dict(traceId=event['trace_id'][:32], spanId=event['event_id'][:16],
            name=event['kind'], kind=1, startTimeUnixNano=str(event['started_ns']),
            endTimeUnixNano=str(event['ended_ns']), attributes=attrs,
            status={'code': 1 if event['status'] == 'ok' else 2})
        if event is not root:
            span['parentSpanId'] = root['event_id'][:16]
        spans.append(span)
    return {'resourceSpans': [{'resource': {'attributes': [attribute('service.name', 'uts-cetus-harbor')]},
        'scopeSpans': [{'scope': {'name': 'uts.cetus.local', 'version': '1'}, 'spans': spans}]}]}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Langfuse export redirects prohibited')


def export(spool, *, base_url, public_key, secret_key):
    if base_url not in BASES:
        raise ValueError('Unapproved Langfuse Cloud origin')
    if not public_key.startswith('pk-lf-') or not secret_key.startswith('sk-lf-'):
        raise ValueError('Langfuse project credentials required')
    events = TraceSpool(spool).events()
    # A stable digest covers the entire event collection. Re-export after a
    # crash uses the same OTEL span IDs; do not invent new IDs for retries.
    body = json.dumps(payload(events), sort_keys=True, allow_nan=False).encode()
    destination = (base_url + ':' + public_key).encode()
    receipt = Path(spool) / ('.exported-' + hashlib.sha256(destination + body).hexdigest())
    if receipt.is_symlink():
        raise ValueError('Invalid export receipt')
    if receipt.exists():
        return {'status': 'previously_acknowledged', 'events': len(events)}
    auth = base64.b64encode((public_key + ':' + secret_key).encode()).decode()
    request = Request(base_url + '/api/public/otel/v1/traces', data=body, method='POST',
        headers={'Content-Type': 'application/json', 'Authorization': 'Basic ' + auth,
                 'x-langfuse-ingestion-version': '4'})
    # Do not inherit a proxy capable of receiving project credentials.
    with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError('Langfuse export was not acknowledged')
        answer = json.loads(response.read() or b'{}')
    partial = answer.get('partialSuccess', {})
    if int(partial.get('rejectedSpans', 0)) or partial.get('errorMessage'):
        raise RuntimeError('Langfuse reported partial ingestion; spool retained')
    fd = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as handle:
        handle.write(json.dumps({'status': 'transport_acknowledged_not_dashboard_verified', 'events': len(events)}))
        handle.flush()
        os.fsync(handle.fileno())
    return {'status': 'transport_acknowledged_not_dashboard_verified', 'events': len(events)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spool', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(export(args.spool, base_url=os.environ.get('LANGFUSE_BASE_URL', ''),
            public_key=os.environ.get('LANGFUSE_PUBLIC_KEY', ''), secret_key=os.environ.get('LANGFUSE_SECRET_KEY', ''))))
    except Exception as exc:
        # Do not print HTTP bodies or request representations containing keys.
        print(json.dumps({'status': 'export_failed_spool_retained', 'error_type': type(exc).__name__}))
        raise SystemExit(1)
