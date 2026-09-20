"""Reaudit final evidence and export allowlisted metrics, never raw agent text."""
import argparse
import csv
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path

from final_analysis import analyze
from final_schedule import schedule
from finalist_freeze import verify
from matrix_resume import DEFERRED_TERMINAL, completed_cell
from qualification_review import assess, expansion_allowed
from run_baselines import validate_registration
from run_final import prerequisites
from scored_gateway import durable_json, private_directory
from scoring_admission import validate


def collect(root):
    root = Path(root).resolve()
    runtime = private_directory(root / '.runtime/stage2')
    fd = os.open(runtime / 'matrix.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        path = runtime / 'final-matrix.json'
        if path.is_symlink() or not path.is_file():
            raise ValueError('Final registration missing or unsafe')
        registration_raw = path.read_bytes()
        descriptor = json.loads(registration_raw)
        freeze, review = descriptor['freeze'], descriptor['review']
        selected = verify(root, freeze)
        settings = validate(root, freeze['admission'])
        if not expansion_allowed(root, assess(root, freeze['admission'], review)):
            raise ValueError('Qualification review does not clear final evaluation')
        manifest = json.loads((root / 'stage2/input_manifest.json').read_text())
        parent = freeze['selection']['selected_parent'] if selected == 'C2' else None
        cells = schedule(manifest['all_task_ids'], custom_condition=selected, custom_parent=parent)
        evidence = prerequisites(root, freeze, review, manifest['development_ids'], settings)
        expected = {'kind': 'final_evaluation_started', 'freeze': freeze, 'review': review,
                    'development_evidence': evidence, 'cells': cells}
        baseline_path = runtime / 'baseline-matrix.json'
        baseline_raw = None
        if baseline_path.exists() or baseline_path.is_symlink():
            if baseline_path.is_symlink() or not baseline_path.is_file():
                raise ValueError('Original baseline registration missing or unsafe')
            baseline_raw = baseline_path.read_bytes()
            if validate_registration(root, freeze['admission']) is None or baseline_path.read_bytes() != baseline_raw:
                raise ValueError('Original baseline registration changed during validation')
            expected['baseline_registration_sha256'] = hashlib.sha256(baseline_raw).hexdigest()
        if descriptor != expected:
            raise ValueError('Final registration or prerequisite evidence changed')
        records, hashes, exported = [], {}, []
        for cell in cells:
            result_path = runtime / 'scored-trials' / cell['trial_id'] / 'result.json'
            if result_path.is_symlink() or not result_path.is_file():
                raise ValueError('Final matrix incomplete or unsafe')
            before = result_path.read_bytes()
            row = completed_cell(root, cell, settings)
            if row is None or before != result_path.read_bytes():
                raise ValueError('Final evidence missing or changed during audit')
            records.append(row)
            hashes[cell['trial_id']] = hashlib.sha256(before).hexdigest()
        summary = analyze(records, all_tasks=manifest['all_task_ids'],
            development_tasks=manifest['development_ids'], custom_condition=selected,
            custom_parent=parent, protocol=settings.fingerprint(), runtime=runtime)
        deferred_hashes = {}
        for cell, row in zip(cells, records):
            billing = row['billing']
            deferred = row.get('resume_disposition') == DEFERRED_TERMINAL
            charge = billing['charged_usd']
            exported.append(dict(trial_id=cell['trial_id'], task_id=cell['task_id'],
                role=cell['role'], harness=cell['harness'], parent=cell['parent'] or '',
                development_exposed=cell['task_id'] in manifest['development_ids'],
                model_protocol_sha256=settings.fingerprint(),
                status=row['status'], billing_verified=billing['billing_verified'],
                resume_disposition=row.get('resume_disposition', 'verified_terminal'),
                accounting_coverage='deferred' if deferred else 'complete',
                reward=row['verifier_result']['rewards']['reward'],
                charged_usd=str(charge) if charge is not None else None,
                known_billed_subtotal_usd=(billing['known_billed_subtotal_usd'] if deferred else str(charge)),
                retained_reservation_nanodollars=(billing['retained_reservation_nanodollars'] if deferred else 0),
                hard_reserved_nanodollars=billing.get('hard_reserved_nanodollars') if deferred else None,
                result_sha256=hashes[cell['trial_id']],
                original_result_sha256=row.get('original_result_sha256', hashes[cell['trial_id']]),
                deferred_billing_sha256=row.get('deferred_billing_sha256'),
                billing_deferral_policy_sha256=row.get('billing_deferral_policy_sha256'),
                prompt_tokens=billing['prompt_tokens'],
                completion_tokens=billing['completion_tokens'], requests=billing['requests'],
                budget_stop_count=billing['budget_stop_count'], agent_seconds=row['phase_seconds']['agent']))
            if deferred:
                deferred_hashes[cell['trial_id']] = {
                    'registration_sha256': row['deferred_billing_sha256'],
                    'original_result_sha256': row['original_result_sha256'],
                    'policy_sha256': row['billing_deferral_policy_sha256']}
        verify(root, freeze)
        if path.read_bytes() != registration_raw:
            raise ValueError('Final registration changed during audit')
        if baseline_raw is not None:
            if (validate_registration(root, freeze['admission']) is None
                    or baseline_path.is_symlink() or not baseline_path.is_file()
                    or baseline_path.read_bytes() != baseline_raw):
                raise ValueError('Original baseline registration changed during audit')
        elif baseline_path.exists() or baseline_path.is_symlink():
            raise ValueError('Baseline registration appeared during final audit')
        return {'summary': summary, 'rows': exported, 'provenance': {
            'final_registration_sha256': hashlib.sha256(registration_raw).hexdigest(),
            'baseline_registration_sha256': hashlib.sha256(baseline_raw).hexdigest() if baseline_raw is not None else None,
            'result_sha256': hashes, 'model_protocol_sha256': settings.fingerprint(),
            'scope': 'final_267_only_not_project_total', 'receipt_reaudited': True,
            'receipt_reaudit_scope': 'available_receipts_and_registered_deferred_evidence',
            'all_receipts_verified': summary['billing_complete'],
            'accuracy_complete': summary['accuracy_complete'],
            'billing_complete': summary['billing_complete'],
            'billing_deferred_trials': summary['accounting']['billing_deferred_trials'],
            'accounting_coverage': summary['accounting']['accounting_coverage'],
            'deferred_billing_registrations': deferred_hashes}}


def export(root, destination):
    bundle = collect(root)  # Validate everything before creating any export.
    destination = Path(destination)
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    rows = bundle['rows']
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    raw = buffer.getvalue().encode('utf-8')
    descriptor = os.open(destination / 'final_trials.csv', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    durable_json(destination / 'comparison.json', bundle['summary'])
    durable_json(destination / 'provenance.json', bundle['provenance'])
    # Last file is the completion marker. A partial directory is never complete.
    durable_json(destination / 'export_complete.json', {'rows': len(rows),
        'files': {name: hashlib.sha256((destination / name).read_bytes()).hexdigest()
                  for name in ('final_trials.csv', 'comparison.json', 'provenance.json')}})
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(export(Path(__file__).resolve().parents[1], args.output))
