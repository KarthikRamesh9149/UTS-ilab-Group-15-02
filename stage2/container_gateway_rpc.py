"""Fixed-route stdin/stdout gateway RPC, executed in the trusted relay only."""
import argparse
import json
import sys

from container_model_relay import UnixConnection, MAX_RESPONSE
from gateway_policy import MAX_BODY
from completion_wait import validate_completion_wait


def forward(envelope, connection_factory=UnixConnection, *, completion_wait_seconds):
    completion_wait_seconds = validate_completion_wait(completion_wait_seconds)
    if not isinstance(envelope, dict) or set(envelope) != {'token', 'payload'}:
        raise ValueError('Invalid envelope')
    token = envelope['token']
    if not isinstance(token, str) or not token or any(c in token for c in '\r\n'):
        raise ValueError('Invalid trial token')
    body = json.dumps(envelope['payload'], allow_nan=False).encode()
    if len(body) > MAX_BODY:
        raise ValueError('Request too large')
    connection = connection_factory('/socket/private/model.sock',
                                    completion_wait_seconds=completion_wait_seconds)
    try:
        connection.request('POST', '/v1/chat/completions', body,
                           {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        response = connection.getresponse()
        raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ValueError('Response too large')
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError('Invalid response')
        return {'status': response.status, 'body': value}
    finally:
        connection.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--completion-wait-seconds', type=float, required=True)
    args = parser.parse_args()
    completion_wait_seconds = validate_completion_wait(args.completion_wait_seconds)
    try:
        raw = sys.stdin.buffer.read(MAX_BODY * 2 + 1)
        if len(raw) > MAX_BODY * 2:
            raise ValueError('Envelope too large')
        result = forward(json.loads(raw), completion_wait_seconds=completion_wait_seconds)
    except Exception:
        result = {'status': 502, 'body': {'error': {'message': 'Private gateway outcome unavailable; do not retry'}}}
    print(json.dumps(result, allow_nan=False))
