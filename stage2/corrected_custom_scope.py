"""Read-only matched-dev20 contract; not permission to dispatch paid work."""
import csv
import hashlib
import json
from pathlib import Path
import re

from freeze_inputs import select_dev
from retry_policy import SETTINGS

PRIMARY_COMPARATOR = 'terminus-2'
COMPARATORS = ('terminus-2', 'openhands')
BASELINES = Path('stage2/results/baseline-corrected-20260923')
# The immutable dev-only export from the completed corrected baseline study.
MATCHED_CSV_SHA256 = '8d7a7ba671d3987c7fe92246f2580e737f66c59a68e1513e85ac3b73c9959783'


def matched_baselines(manifest, rows, *, model_protocol):
    """Require every preselected task once in each baseline; retain zeros.

    This accepts only the already exported dev20 metadata, never held-out
    trajectories, tests or answers. It does not select easier tasks or choose
    the weakest comparator after observing scores.
    """
    if (model_protocol != SETTINGS.document()
            or type(model_protocol.get('max_output_tokens')) is not int
            or type(model_protocol.get('temperature')) not in (int, float)
            or type(model_protocol.get('top_p')) not in (int, float)):
        raise ValueError('Corrected baseline model settings required')
    tasks = manifest.get('all_task_ids')
    if (not isinstance(tasks, list) or any(not isinstance(t, str) or not t for t in tasks)
            or len(tasks) != 89 or len(set(tasks)) != 89):
        raise ValueError('Frozen 89-task input inventory required')
    development = manifest.get('development_ids')
    if development != select_dev(tasks):
        raise ValueError('Preserve the original deterministic 20-task split and order')
    expected = {(h, t) for h in COMPARATORS for t in development}
    if not isinstance(rows, list) or len(rows) != 40:
        raise ValueError('Exactly 40 matched development baseline rows required')
    seen, identifiers = set(), set()
    counts = {h: {'attempted': 20, 'passed': 0, 'failed': 0} for h in COMPARATORS}
    bindings = {}
    for row in rows:
        key = row.get('harness'), row.get('task_id')
        identifier = row.get('trial_id')
        if (key not in expected or key in seen or not isinstance(identifier, str)
                or not identifier or identifier in identifiers):
            raise ValueError('Duplicate, missing or non-development baseline cell')
        if row.get('reward') not in ('0', '1'):
            raise ValueError('Binary recorded verifier reward required; unknown is not zero')
        if row.get('cleanup_complete') != 'True' or row.get('model_revoked') != 'True':
            raise ValueError('Baseline cleanup and model revocation must be confirmed')
        result_hash = row.get('result_sha256')
        if not isinstance(result_hash, str) or not re.fullmatch('[a-f0-9]{64}', result_hash):
            raise ValueError('Original result hash required')
        seen.add(key)
        identifiers.add(identifier)
        counts[key[0]]['passed' if row['reward'] == '1' else 'failed'] += 1
        bindings[identifier] = result_hash
    if seen != expected:
        raise ValueError('Incomplete matched development baseline coverage')
    return dict(development_ids=development, primary_comparator=PRIMARY_COMPARATOR,
        secondary_comparator='openhands', conditions=counts, original_results_sha256=bindings,
        model_protocol_sha256=SETTINGS.fingerprint(), paired_task_count=20,
        baseline_reruns_needed=False, custom_scored_attempts_in_this_artifact=0,
        paid_launch_ready=False)


def inspect(root):
    root = Path(root)
    manifest_path = root / 'stage2/input_manifest.json'
    summary_path = root / BASELINES / 'summary.json'
    csv_path = root / BASELINES / 'development-baselines.csv'
    summary = json.loads(summary_path.read_text())
    manifest_raw = manifest_path.read_bytes()
    manifest_hash = hashlib.sha256(manifest_raw).hexdigest()
    if summary.get('sources_sha256', {}).get('input_manifest.json') != manifest_hash:
        raise ValueError('Input inventory differs from the completed baseline registration')
    if summary.get('model_protocol_sha256') != SETTINGS.fingerprint():
        raise ValueError('Baseline model protocol binding changed')
    csv_hash = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    if csv_hash != MATCHED_CSV_SHA256:
        raise ValueError('Matched baseline CSV differs from the audited export')
    with csv_path.open(newline='') as handle:
        rows = list(csv.DictReader(handle))
    result = matched_baselines(json.loads(manifest_raw), rows,
        model_protocol=summary.get('model_protocol'))
    result.update(input_manifest_sha256=manifest_hash,
        development_baselines_sha256=csv_hash,
        baseline_summary_sha256=hashlib.sha256(summary_path.read_bytes()).hexdigest(),
        baseline_registration_sha256=summary['registration_sha256'])
    return result


if __name__ == '__main__':
    print(json.dumps(inspect(Path(__file__).resolve().parents[1]), indent=2))
