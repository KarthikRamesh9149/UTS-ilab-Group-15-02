"""Pure allowlisted baseline projection, never a writer or admission receipt.

The actual exporter must freshly audit and read the SAME retained archive
before calling this function. Valid saved JSON alone proves neither action.
"""
import csv
import io
import json

import matched_repeat_archive as archive
import matched_repeat_policy as policy
import matched_repeat_report as report
from no_cutoff_final_archive import _same as same

OUTPUTS = ('summary.json', 'trials.json', 'trials.csv')
ROW_FIELDS_CSV = (report.ROW_FIELDS - {'phase_observation'}) | {
    'setup_observation', 'agent_observation', 'verifier_observation'}


def _json(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, indent=2).encode('utf-8') + b'\n'


def projection(data, manifest, sources, verified):
    """Deterministic bytes only; the caller retains actual audit/archive proof."""
    report.validate(data, manifest, sources)
    fields = {'kind', 'sha256', 'compressed_bytes', 'files', 'bytes', 'snapshot_sha256',
        'inventory_sha256', 'verified_result_files', 'verified_bound_files', 'verified_absent_paths',
        'private_archive_not_published', 'paid_launch_ready', 'full_runtime_restore_exercised'}
    if type(verified) is not dict or set(verified) != fields:
        raise ValueError('Exact verified baseline archive projection required')
    for name in ('sha256', 'snapshot_sha256', 'inventory_sha256'): policy._hash(verified[name])
    for name in ('compressed_bytes', 'files', 'bytes', 'verified_bound_files'):
        if type(verified[name]) is not int or verified[name] <= 0:
            raise ValueError('Actual positive archive counts required')
    for name, expected in dict(kind=archive.KIND, snapshot_sha256=policy.fingerprint(data),
            verified_result_files=89, verified_bound_files=verified['files'],
            verified_absent_paths=len(data['absent_paths']), private_archive_not_published=True,
            paid_launch_ready=False, full_runtime_restore_exercised=False).items():
        same(verified[name], expected)
    if verified['files'] < len(data['supporting_files']):
        raise ValueError('Verified archive must contain all required evidence')
    harness = data['harness']
    summary = dict(kind='separate_completed_matched_baseline89_projection_not_admission',
        experiment=policy.EXPERIMENT, harness=harness, intended=89,
        original_scores=dict(data['original_scores']), original_results_replaced=False,
        repeat_merged_into_original89=False, best_of_selection=False,
        primary_comparator='terminus-2', secondary_comparator='openhands',
        confirmation60_status='deferred_not_run', diagnostic20_status='deferred_not_run',
        inherited_baseline_turn_guards=dict(policy.POLICY['inherited_baseline_turn_guards']),
        native_guards_are_benchmark_rules=False,
        aggregate=data['aggregate'], development20=data['development20'], remaining69=data['remaining69'],
        collected_utc=data['collected_utc'], qualification_sha256=data['qualification_sha256'],
        registration_sha256=policy.fingerprint(data['registration']), sources_sha256=data['sources_sha256'],
        snapshot_sha256=policy.fingerprint(data), archive_sha256=verified['sha256'],
        full_runtime_restore_exercised=False, historical_installed_bytes_attested=False,
        paid_launch_ready=False)
    output = io.StringIO(newline=''); fields = sorted(ROW_FIELDS_CSV)
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator='\n'); writer.writeheader()
    for row in data['rows']:
        flat = {k:v for k,v in row.items() if k != 'phase_observation'}
        flat.update({p+'_observation':row['phase_observation'][p] for p in ('setup','agent','verifier')})
        writer.writerow(flat)
    return {'summary.json':_json(summary),
        'trials.json':_json(dict(experiment=policy.EXPERIMENT, harness=harness, rows=data['rows'])),
        'trials.csv':output.getvalue().encode('utf-8')}
