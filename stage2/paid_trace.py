"""Passive Harbor phase and reconciled generation spans, without task text."""
from pathlib import Path
from budget_ledger import dollars
from gateway_core import reconcile_receipt
from local_trace import PhaseRecorder, TraceSpool
from scored_accounting import read_json


class PaidTrialTrace:
    def __init__(self, directory, **identity):
        self.spool = TraceSpool(directory)
        self.recorder = PhaseRecorder(self.spool, **identity)
        self.root_event = None

    def __call__(self, **event):
        if event['kind'] == 'trial':
            if self.root_event is not None:
                raise ValueError('Duplicate trial root')
            self.root_event = event
        else:
            self.recorder(**event)

    def finish(self, evidence, billing):
        if self.root_event is None or billing.get('billing_verified') is not True:
            raise ValueError('Completed lifecycle and reconciled billing required for export')
        paths = sorted(Path(evidence).glob('*.response.json'))
        if len(paths) != billing['requests']:
            raise ValueError('Trace generation count does not match audited billing')
        charge = 0
        for response_path in paths:
            prefix = response_path.name.removesuffix('.response.json')
            timing = read_json(response_path.with_name(prefix + '.timing.json'))
            response = read_json(response_path)
            receipt = read_json(response_path.with_name(prefix + '.receipt.json'))
            cost = dollars(reconcile_receipt(response, receipt))
            charge += cost
            if not self.root_event['started_ns'] <= timing['started_ns'] <= timing['ended_ns'] <= self.root_event['ended_ns']:
                raise ValueError('Generation outside observed trial lifetime')
            self.recorder(kind='generation', started_ns=timing['started_ns'], ended_ns=timing['ended_ns'],
                seconds=float(timing['seconds']), status=timing['status'], metrics={
                    'requests': 1, 'input_tokens': response['usage']['prompt_tokens'],
                    'output_tokens': response['usage']['completion_tokens'], 'charged_nanodollars': cost})
        if charge != dollars(billing['charged_usd']):
            raise ValueError('Trace charges do not match audited billing')
        self.recorder(**self.root_event, metrics={'charged_nanodollars': charge,
            'requests': billing['requests'], 'input_tokens': billing['prompt_tokens'],
            'output_tokens': billing['completion_tokens']})
        return {'status': 'complete_metadata_spool_not_cloud_export',
                'events': len(self.spool.events()), 'generations': len(paths)}
