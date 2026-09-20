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
from matrix_resume import completed_cell
from qualification_review import assess, expansion_allowed
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
            custom_parent=parent, protocol=settings.fingerprint())
        for cell, row in zip(cells, records):
            billing = row['billing']
            exported.append(dict(trial_id=cell['trial_id'], task_id=cell['task_id'],
                role=cell['role'], harness=cell['harness'], parent=cell['parent'] or '',
                development_exposed=cell['task_id'] in manifest['development_ids'],
                model_protocol_sha256=settings.fingerprint(),
                reward=row['verifier_result']['rewards']['reward'],
                charged_usd=str(billing['charged_usd']), prompt_tokens=billing['prompt_tokens'],
                completion_tokens=billing['completion_tokens'], requests=billing['requests'],
                budget_stop_count=billing['budget_stop_count'], agent_seconds=row['phase_seconds']['agent']))
        verify(root, freeze)
        if path.read_bytes() != registration_raw:
            raise ValueError('Final registration changed during audit')
        return {'summary': summary, 'rows': exported, 'provenance': {
            'final_registration_sha256': hashlib.sha256(registration_raw).hexdigest(),
            'result_sha256': hashes, 'model_protocol_sha256': settings.fingerprint(),
            'scope': 'final_267_only_not_project_total', 'receipt_reaudited': True}}


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
