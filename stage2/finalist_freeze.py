"""Freeze a development-selected candidate, never infer success from its choice."""
import hashlib
import json
from pathlib import Path
import re

from development_selection import select
from qualification_review import assess, expansion_allowed
from scored_accounting import audit_trial
from scored_gateway import durable_json
from scoring_admission import RUNTIME_FILES, validate

FROZEN_FILES = tuple(sorted(set(RUNTIME_FILES) | {
    'custom-requirements.lock', 'gateway-requirements.lock', 'budget_policy.json',
    'input_manifest.json', 'dataset_provenance.json', 'development_selection.py',
    'finalist_freeze.py', 'final_schedule.py', 'matrix_resume.py',
    'run_qualification.py', 'run_development.py', 'run_diagnostic.py', 'qualification_review.py',
    'run_final.py', 'final_analysis.py', 'custom_execution_limits.json'}))


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


def registered_blocks(root, *, admission, trials, tasks, c2_parent, limits):
    """Bind selection to the original, source-qualified development attempts.

    A diagnostic/repeat has the same condition and task but is not selectable
    development evidence. Block registrations exist before any model dispatch.
    """
    if c2_parent not in {'C0', 'C1'}:
        raise ValueError('Registered C2 parent required')
    if len(tasks) != 20 or len(set(tasks)) != 20:
        raise ValueError('Exactly the registered development tasks required')
    folder = Path(root) / '.runtime/stage2/development-blocks'
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError('Original custom development registrations required')
    runner_hash = hashlib.sha256((Path(root) / 'stage2/run_development.py').read_bytes()).hexdigest()
    hashes, scheduled = {}, {}
    for condition in ('C0', 'C1', 'C2'):
        cells = [dict(trial_id=f'dev-{condition}-{index:02d}-{task}', task_id=task,
                      stage='development', harness=condition,
                      **({'parent': c2_parent} if condition == 'C2' else {}))
                 for index, task in enumerate(tasks)]
        identifiers = [cell['trial_id'] for cell in cells]
        if trials[condition] != identifiers:
            raise ValueError('Selection must use the exact canonical development cells')
        path = folder / (condition + '.json')
        if path.is_symlink() or not path.is_file():
            raise ValueError('Missing or unsafe custom development registration')
        raw = path.read_bytes()
        registration = json.loads(raw)
        review = registration.get('qualification_review')
        if not isinstance(review, dict):
            raise ValueError('Development registration lacks its qualification review')
        expected = {'block': condition, 'cells': cells, 'admission': admission,
                    'qualification_review': review, 'limits': limits,
                    'runner_sha256': runner_hash}
        # Serialized comparison distinguishes JSON Booleans from numeric limits.
        if json.dumps(registration, sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise ValueError('Development registration source, admission, limits or parent changed')
        # The runner permits a separately assessed review for each block. Bind
        # and revalidate each original review, rather than requiring identical
        # reviewer attribution or notes across independently reviewed blocks.
        if not expansion_allowed(root, assess(root, admission, review)):
            raise ValueError('Development registration review has not cleared expansion')
        hashes[condition] = hashlib.sha256(raw).hexdigest()
        scheduled[condition] = cells
    return hashes, scheduled


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
    registrations, scheduled = registered_blocks(root, admission=admission, trials=trials,
        tasks=manifest['development_ids'], c2_parent=c2_parent, limits=limits)
    blocks, evidence, seen = {}, {}, set()
    for condition, identifiers in trials.items():
        blocks[condition] = []
        for identifier, cell in zip(identifiers, scheduled[condition]):
            if identifier in seen:
                raise ValueError('Development attempt reused')
            seen.add(identifier)
            raw = result_path(root, identifier).read_bytes()
            row = json.loads(raw)
            if any(row.get(key) != cell[key] for key in ('trial_id', 'task_id', 'harness', 'stage')):
                raise ValueError('Trial path, task or registered condition identity differs')
            row['billing'] = audit_trial(root / '.runtime/stage2', identifier, 'development')
            blocks[condition].append(row)
            evidence[identifier] = hashlib.sha256(raw).hexdigest()
    selection = select(blocks, task_ids=manifest['development_ids'],
                       protocol=settings.fingerprint(), c2_parent=c2_parent)
    return {'kind': 'frozen_custom_finalist_not_final_score', 'selection': selection,
            'admission': admission, 'custom_max_model_calls': custom_max_model_calls,
            'development_evidence': evidence, 'files': file_hashes(root),
            'development_block_evidence': registrations,
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
