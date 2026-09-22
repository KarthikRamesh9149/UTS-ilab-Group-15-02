"""Read-only call summaries and metadata traces; unknown costs are never zero."""
from decimal import Decimal
import json
from pathlib import Path

from credit_only_policy import MODE
from credit_only_gateway import exact_cost, count
from paid_trace import PaidTrialTrace


def call_records(evidence):
    evidence = Path(evidence)
    records = []
    for path in sorted(evidence.glob('*.request.json')):
        prefix = path.name.removesuffix('.request.json')
        outcome = path.with_name(prefix + '.outcome.json')
        record = json.loads(outcome.read_text()) if outcome.exists() else {
            'status': 'interrupted', 'cost_usd': None, 'input_tokens': None, 'output_tokens': None}
        record['prefix'] = prefix
        record['cost_usd'] = exact_cost(record.get('cost_usd'))
        for key in ('input_tokens', 'output_tokens'):
            record[key] = count(record.get(key))
        records.append(record)
    return records


def summarise(runtime, trial_id):
    evidence = Path(runtime) / 'scored-attempts' / trial_id
    records = call_records(evidence)
    known = [Decimal(r['cost_usd']) for r in records if r['cost_usd'] is not None]
    unknown = len(records) - len(known)
    total = str(sum(known, Decimal(0)))
    result = dict(accounting_mode=MODE, requests=len(records),
        known_charged_usd=total, charged_usd=total if not unknown else None,
        unknown_cost_requests=unknown, costs_complete=unknown == 0,
        billing_verified=False, independent_receipts_verified=False,
        cost_source='openrouter_response_usage_cost_when_present')
    for field, source in (('prompt_tokens', 'input_tokens'), ('completion_tokens', 'output_tokens')):
        counts = [r[source] for r in records if r[source] is not None]
        result[field] = sum(counts) if len(counts) == len(records) else None
        result['known_' + field] = sum(counts)
    stop = evidence / 'provider-stop.json'
    result['provider_stop'] = json.loads(stop.read_text()) if stop.exists() else None
    return result


def metrics_for(record):
    metrics = {'requests': 1}
    for field in ('input_tokens', 'output_tokens'):
        value = count(record.get(field))
        if value is not None:
            metrics[field] = value
    cost = exact_cost(record.get('cost_usd'))
    if cost is not None:
        amount = Decimal(cost) * 10**9
        if amount == amount.to_integral_value():
            metrics['charged_nanodollars'] = int(amount)
    return metrics


class PassiveTrialTrace(PaidTrialTrace):
    def finish(self, evidence, billing):
        if self.root_event is None:
            raise ValueError('Completed lifecycle required for trace export')
        observed = 0
        for record in call_records(evidence):
            timing_path = Path(evidence) / (record['prefix'] + '.timing.json')
            if not timing_path.exists():
                continue  # Interrupted call: summary retains unknown amount.
            timing = json.loads(timing_path.read_text())
            if not self.root_event['started_ns'] <= timing['started_ns'] <= timing['ended_ns'] <= self.root_event['ended_ns']:
                raise ValueError('Generation outside observed lifecycle')
            self.recorder(kind='generation', started_ns=timing['started_ns'], ended_ns=timing['ended_ns'],
                seconds=timing['seconds'], status=timing['status'], metrics=metrics_for(record))
            observed += 1
        metrics = metrics_for({'cost_usd': billing.get('charged_usd'),
            'input_tokens': billing.get('prompt_tokens'), 'output_tokens': billing.get('completion_tokens')})
        metrics['requests'] = billing['requests']
        self.recorder(**self.root_event, metrics=metrics)
        return dict(status='metadata_spool_not_cloud_export', events=len(self.spool.events()),
            generations=observed, missing_generation_timings=billing['requests'] - observed,
            unknown_cost_requests=billing['unknown_cost_requests'])
