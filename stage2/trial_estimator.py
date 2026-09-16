"""Approved conservative *estimate*, never the global worst-case reservation.

Use identically for all harnesses. Provider transformation drift remains a risk;
the ledger halts persistently on any actual cost exceeding this estimate.
"""
import json

from extended_token_calibration import token_candidates
from setup_probe import CONTEXT, INPUT_PRICE, OUTPUT_PRICE

VERSION = 'utf8-envelope-v1'


def estimate_details(root, request):
    # Reject data that the pinned text serializer cannot represent, rather than
    # ignoring it. The gateway separately validates model, top-level fields,
    # provider policy, bounded output, body size and non-streaming execution.
    for message in request['messages']:
        if set(message) - {'role', 'content', 'tool_calls', 'tool_call_id', 'reasoning_content', 'name'}:
            raise ValueError('Unqualified message field for trial estimate')
        for name in ['content', 'reasoning_content', 'name', 'tool_call_id']:
            if message.get(name) is not None and not isinstance(message[name], str):
                raise ValueError('Only text message fields are estimated')
    for tool in request.get('tools', []):
        if tool.get('type') != 'function' or set(tool) != {'type', 'function'}:
            raise ValueError('Only local function tool schemas are estimated')
    # Schemas and all request metadata are also present in this byte envelope,
    # including fields not injected by the candidate chat encoder. Two times
    # BOTH envelopes + 8192 tokens is intentionally conservative, not a proof
    # of the provider's exact template or a cost guarantee for one trial.
    try:
        candidates = token_candidates(root, request)
    except (KeyError, TypeError, AssertionError, AttributeError) as exc:
        raise ValueError('Unsupported serialized conversation for trial estimate') from exc
    wire_bytes = len(json.dumps(request, ensure_ascii=False, allow_nan=False).encode('utf-8'))
    rendered_bytes = max(v['rendered_utf8_bytes'] for v in candidates.values())
    estimated_input = min(CONTEXT, 2 * (wire_bytes + rendered_bytes) + 8192)
    maximum = request['max_tokens']
    if type(maximum) is not int or not 0 < maximum <= 384000:
        raise ValueError('Explicit output allowance required')
    charge = estimated_input * INPUT_PRICE + maximum * OUTPUT_PRICE
    return {'version': VERSION, 'wire_bytes': wire_bytes, 'max_rendered_bytes': rendered_bytes,
            'estimated_input_tokens': estimated_input, 'maximum_output_tokens': maximum,
            'estimated_usd': str(charge), 'provider_guaranteed': False}


def trial_charge_estimator(root):
    return lambda request: estimate_details(root, request)['estimated_usd']
