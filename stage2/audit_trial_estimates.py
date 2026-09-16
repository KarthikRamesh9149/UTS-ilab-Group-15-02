"""Offline estimate audit against already reconciled setup requests. No API."""
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from gateway_policy import prepare_request
from trial_estimator import estimate_details
from setup_probe import full_context_bound


def main(root):
    report = {'kind': 'offline_estimate_audit_no_paid_calls', 'cases': [],
              'limitations': ['Only three previously reconciled setup requests.',
                  'Empirical coverage is not a provider guarantee or benchmark result.']}
    for label in ['unicode-history', 'openhands-tool-history-chat', 'openhands-tool-history-default']:
        prefix = root / '.runtime/stage2' / ('token-calibration-' + label + '-v1')
        raw = prefix.with_suffix('.request.json').read_bytes()
        request = prepare_request(json.loads(raw))
        response = json.loads(prefix.with_suffix('.response.json').read_text(), parse_float=Decimal)
        estimate = estimate_details(root, request)
        actual = response['usage']
        report['cases'].append({'fixture': label, 'request_sha256': hashlib.sha256(raw).hexdigest(),
            **estimate, 'hard_global_reservation_usd': str(full_context_bound(request)),
            'actual_prompt_tokens': actual['prompt_tokens'], 'actual_cost_usd': str(actual['cost']),
            'input_covered': actual['prompt_tokens'] <= estimate['estimated_input_tokens'],
            'cost_covered': Decimal(str(actual['cost'])) <= Decimal(estimate['estimated_usd']),
            'fits_initial_trial_cap': Decimal(estimate['estimated_usd']) <= Decimal('.055')})
    report['passed'] = all(r['input_covered'] and r['cost_covered'] and r['fits_initial_trial_cap'] for r in report['cases'])
    with (root / 'stage2/trial_estimate_audit.json').open('x') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main(Path(__file__).resolve().parents[1])
