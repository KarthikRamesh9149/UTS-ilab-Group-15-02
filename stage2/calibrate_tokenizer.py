"""Offline calibration against existing paid fixtures; never a spending bound.

Requires the reviewed upstream assets in the ignored cache. Verifies their
hashes before importing code. Does not download anything or call a provider.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

from tokenizers import Tokenizer
from setup_probe import fixture_request

REVISION = '7872f01b1d1fe23eabc4c98b48bffcef5a386062'
HASHES = {
    'encoding_dsv4.py': 'abc0d26120250dda0ae077dc64aa28836026e61e970854aaeb792445e6a0dde6',
    'tokenizer.json': '8f9f37ca37fdc4f5fd36d5cf4d3b0e8392edb4e894fd10cc0d70b4957c8633cf',
}


def calibrate(root):
    cache = root / '.cache' / 'stage2-tokenizer'
    for name, expected in HASHES.items():
        if hashlib.sha256((cache / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Unreviewed tokenizer asset: ' + name)
    spec = importlib.util.spec_from_file_location('reviewed_dsv4', cache / 'encoding_dsv4.py')
    encoder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(encoder)
    tokenizer = Tokenizer.from_file(str(cache / 'tokenizer.json'))
    evidence = {'kind': 'offline_calibration_not_scored_not_a_cost_bound',
                'source': 'deepseek-ai/DeepSeek-V4-Flash-0731',
                'revision': REVISION, 'sha256': HASHES, 'fixtures': {}}
    for kind, receipt_name in [('plain', 'setup_probe_reconciled.json'),
                               ('tools', 'setup_tools_probe_reconciled.json')]:
        request = fixture_request(kind)
        messages = copy.deepcopy(request['messages'])
        if request.get('tools'):
            messages.insert(0, {'role': 'system', 'content': '', 'tools': request['tools']})
        rendered = encoder.encode_messages(messages, thinking_mode='chat')
        count = len(tokenizer.encode(rendered, add_special_tokens=False).ids)
        # Initial snapshots can omit usage when the receipt was delayed; use
        # the durable private response only to extract its non-secret count.
        response = json.loads((root / '.runtime' / 'stage2' /
                               ('compatibility-' + kind + '-v1.response.json')).read_text())
        actual = response['usage']['prompt_tokens']
        evidence['fixtures'][kind] = {'local_prompt_tokens': count,
            'provider_prompt_tokens': actual, 'matches': count == actual,
            'generation_id': response['id'], 'reconciliation_artifact': receipt_name}
    evidence['qualified_for_scored_reservations'] = False
    evidence['limitations'] = ['Only two first-turn chat-mode fixtures were compared.',
        'Tool results, multi-turn history, reasoning, response schemas and provider template drift are not qualified.',
        'The gateway continues using the full-context reservation for setup only.']
    return evidence


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    evidence = calibrate(root)
    with (root / 'stage2' / 'tokenizer_calibration.json').open('x') as handle:
        json.dump(evidence, handle, indent=2)
        handle.write('\n')
    print(json.dumps(evidence, indent=2))
