"""Pure request validation, not a live gateway or a qualified cost estimator.

Reject unsupported features rather than silently changing baseline behaviour.
Pricing and billable input bounds must be qualified separately before dispatch.
"""
from copy import deepcopy
import json

MODEL = 'deepseek/deepseek-v4-flash-0731'
ENDPOINT = 'deepinfra/fp8'
MAX_BODY = 2 * 1024 * 1024
ALLOWED = {'model', 'messages', 'tools', 'tool_choice', 'max_tokens',
           'temperature', 'top_p', 'seed', 'stop', 'stream', 'reasoning',
           'parallel_tool_calls', 'response_format'}


def prepare_request(payload):
    if not isinstance(payload, dict) or set(payload) - ALLOWED:
        raise ValueError('Unsupported request fields')
    if payload.get('model') != MODEL:
        raise ValueError('Model drift')
    if payload.get('stream', False) is not False:
        raise ValueError('Streaming is not yet qualified')
    messages = payload.get('messages')
    if not isinstance(messages, list) or not messages:
        raise ValueError('Messages required')
    for message in messages:
        if not isinstance(message, dict) or message.get('role') not in {'system', 'user', 'assistant', 'tool'}:
            raise ValueError('Invalid message')
        if message.get('content') is not None and not isinstance(message['content'], str):
            raise ValueError('Multimodal input is not cost-qualified')
    maximum = payload.get('max_tokens')
    if type(maximum) is not int or not 0 < maximum <= 384000:
        raise ValueError('Explicit bounded max_tokens required')
    encoded = json.dumps(payload, allow_nan=False).encode()
    if len(encoded) > MAX_BODY:
        raise ValueError('Request body too large')
    result = deepcopy(payload)
    result['stream'] = False
    result['provider'] = {
        'only': [ENDPOINT], 'order': [ENDPOINT], 'allow_fallbacks': False,
        'require_parameters': True, 'quantizations': ['fp8'],
        'max_price': {'prompt': 0.10, 'completion': 0.20},
    }
    return result
