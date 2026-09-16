"""Freeze a development-selected candidate, never infer success from its choice."""
import hashlib
import json
from pathlib import Path
import re

from development_selection import select
from scored_accounting import audit_trial
from scored_gateway import durable_json
from scoring_admission import RUNTIME_FILES, validate

FROZEN_FILES = tuple(sorted(set(RUNTIME_FILES) | {
    'custom-requirements.lock', 'gateway-requirements.lock', 'budget_policy.json',
    'input_manifest.json', 'dataset_provenance.json', 'development_selection.py',
    'finalist_freeze.py', 'final_schedule.py', 'matrix_resume.py',
    'run_qualification.py', 'run_development.py', 'qualification_review.py',
    'custom_execution_limits.json'}))


def file_hashes(root):
    result = {}
    for name in FROZEN_FILES:
        path = Path(root) / 'stage2' / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('Missing or unsafe freeze input')
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def result_path(root, trial_id):
    if not isinstance(trial_id, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}', trial_id):
        raise ValueError('Invalid trial identity')
    parent = Path(root) / '.runtime/stage2/scored-trials'
    path = parent / trial_id / 'result.json'
    if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
        raise ValueError('Missing or unsafe trial evidence')
    return path


def build(root, *, admission, trials, c2_parent, custom_max_model_calls):
    root = Path(root)
    settings = validate(root, admission)
    if type(custom_max_model_calls) is not int or custom_max_model_calls <= 0:
        raise ValueError('Explicit custom call ceiling required')
    limits = json.loads((root / 'stage2/custom_execution_limits.json').read_text())
    if limits != {'max_model_calls': custom_max_model_calls, 'max_repair_cycles': 2}:
        raise ValueError('Custom execution limits differ from registered configuration')
    if set(trials) != {'C0', 'C1', 'C2'}:
        raise ValueError('All three development variants required')
    manifest = json.loads((root / 'stage2/input_manifest.json').read_text())
    blocks, evidence, seen = {}, {}, set()
    for condition, identifiers in trials.items():
        blocks[condition] = []
        for identifier in identifiers:
            if identifier in seen:
                raise ValueError('Development attempt reused')
            seen.add(identifier)
            raw = result_path(root, identifier).read_bytes()
            row = json.loads(raw)
            if row.get('trial_id') != identifier:
                raise ValueError('Trial path and record identity differ')
            row['billing'] = audit_trial(root / '.runtime/stage2', identifier, 'development')
            blocks[condition].append(row)
            evidence[identifier] = hashlib.sha256(raw).hexdigest()
    selection = select(blocks, task_ids=manifest['development_ids'],
                       protocol=settings.fingerprint(), c2_parent=c2_parent)
    return {'kind': 'frozen_custom_finalist_not_final_score', 'selection': selection,
            'admission': admission, 'custom_max_model_calls': custom_max_model_calls,
            'development_evidence': evidence, 'files': file_hashes(root),
            'development_trials': trials,
            'preselected_baselines': ['terminus-2', 'openhands'],
            'final_evaluation_started': False}


def verify(root, document):
    if document.get('kind') != 'frozen_custom_finalist_not_final_score':
        raise ValueError('Unknown freeze document')
    validate(root, document['admission'])
    if document.get('files') != file_hashes(root):
        raise ValueError('Frozen implementation or configuration changed')
    for identifier, digest in document['development_evidence'].items():
        if hashlib.sha256(result_path(root, identifier).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen selection evidence changed')
    rebuilt = build(root, admission=document['admission'], trials=document['development_trials'],
                    c2_parent=document['selection']['selected_parent'],
                    custom_max_model_calls=document['custom_max_model_calls'])
    if document != rebuilt:
        raise ValueError('Frozen selection or limits do not match reaudited evidence')
    return document['selection']['selected']


def save(root, path, document):
    verify(root, document)
    durable_json(Path(path), document)
