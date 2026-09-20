"""Read-only, fixed-20 development snapshots; never a final score or spending gate.

An existing matrix lock is required. Snapshot collection never creates runtime
files, dispatches a trial, or repairs evidence. Output is written only to a new
directory outside runtime, source, and synced-reference directories.
"""
import argparse
from contextlib import closing
import csv
from decimal import Decimal, InvalidOperation
import fcntl
import hashlib
import io
import json
from math import fsum, isfinite
import os
from pathlib import Path
import re
import sqlite3
import stat

from historical_hold import validate_historical_hold
from development_selection import select
from matrix_resume import completed_cell, validated_held_cell, HELD_TERMINAL
from scoring_admission import validate
from study_budget import TRIAL_CAP


CONDITIONS = ('terminus-2', 'openhands', 'C0', 'C1', 'C2')
UNIT = Decimal(1_000_000_000)
SCOPE = 'fixed_20_development_primary_conditions_not_final_89'
PHASES = ('setup', 'agent', 'verifier')
FIELDS = ('trial_id', 'task_id', 'stage', 'harness', 'parent', 'state', 'status',
          'reward', 'billing_verified', 'charged_usd', 'known_billed_subtotal_usd',
          'prompt_tokens', 'completion_tokens', 'requests',
          'setup_seconds', 'agent_seconds', 'verifier_seconds',
          'budget_stop_markers', 'capacity_budget_stopped', 'historical_pending_barrier_markers',
          'retained_liability_usd', 'result_sha256', 'historical_hold_sha256')


def _kind(root, path):
    current = root
    for part in path.relative_to(root).parts:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            return None
        if stat.S_ISLNK(info.st_mode) or (current != path and not stat.S_ISDIR(info.st_mode)):
            raise ValueError('Unsafe development evidence path')
    return info


def _read(root, path):
    info = _kind(root, path)
    if info is None or not stat.S_ISREG(info.st_mode):
        raise ValueError('Missing or nonregular development evidence')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError('Nonregular development evidence')
        return handle.read()


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def _ledger_trials(root, runtime):
    path = runtime / 'scored_budget.sqlite'
    info = _kind(root, path)
    if info is None:
        return set()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('Unsafe canonical scored ledger')
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        return {row[0] for row in db.execute('SELECT trial FROM trial_stages UNION SELECT trial FROM requests')}


def _cell(condition, index, task, parent=None):
    return dict(trial_id=f'dev-{condition}-{index:02d}-{task}', task_id=task,
                stage='development', harness=condition,
                **({'parent': parent} if condition == 'C2' else {}))


def _registered_parent(root, runtime, tasks, admission, watched):
    path = runtime / 'development-blocks/C2.json'
    if _kind(root, path) is None:
        watched[path] = None
        return None
    raw = _read(root, path)
    watched[path] = raw
    descriptor = json.loads(raw)
    cells = descriptor.get('cells')
    if not isinstance(cells, list) or len(cells) != 20 or not isinstance(cells[0], dict):
        raise ValueError('Registered C2 development cells required')
    parent = cells[0].get('parent')
    if (parent not in {'C0', 'C1'} or descriptor.get('block') != 'C2'
            or descriptor.get('admission') != admission
            or cells != [_cell('C2', i, task, parent) for i, task in enumerate(tasks)]):
        raise ValueError('C2 registration or parent mismatch')
    return parent


def _empty_row(cell, state):
    return dict.fromkeys(FIELDS) | {key: cell[key] for key in ('trial_id', 'task_id', 'stage', 'harness')} | {
        'parent': cell.get('parent'), 'state': state}


def _terminal_row(root, runtime, cell, row, protocol, raw):
    held = validated_held_cell(runtime, row, protocol)
    billing = row.get('billing') or {}
    reward = (row.get('verifier_result') or {}).get('rewards', {}).get('reward')
    if type(reward) not in (int, float) or reward not in (0, 1):
        raise ValueError('Binary terminal development reward required')
    if any(row.get(key) != cell[key] for key in ('trial_id', 'task_id', 'stage', 'harness')):
        raise ValueError('Audited development cell identity mismatch')
    if row.get('model_protocol_sha256') != protocol:
        raise ValueError('Audited development model protocol mismatch')
    if held is None and (row.get('status') != 'verified' or billing.get('billing_verified') is not True):
        raise ValueError('Unverified development result cannot be exported as terminal')
    result = _empty_row(cell, HELD_TERMINAL if held else 'verified_terminal')
    result.update(status=row['status'], reward=int(reward), billing_verified=billing['billing_verified'],
                  result_sha256=_digest(raw))
    phases = row.get('phase_seconds')
    if phases is None:
        phases = {}
    if not isinstance(phases, dict):
        raise ValueError('Recorded development phase durations must be an object')
    for phase in PHASES:
        seconds = phases.get(phase)
        if seconds is not None and (type(seconds) not in (int, float) or not isfinite(seconds) or seconds < 0):
            raise ValueError('Recorded development phase duration must be finite and nonnegative')
        result[phase + '_seconds'] = seconds
    if held:
        result.update(known_billed_subtotal_usd=str(Decimal(held['settled_subtotal_nanodollars']) / UNIT),
                      retained_liability_usd=str(Decimal(held['reserved_nanodollars']) / UNIT),
                      budget_stop_markers=held['budget_stop_count'],
                      capacity_budget_stopped=held['capacity_budget_stop_count'] > 0,
                      historical_pending_barrier_markers=held['budget_stop_count'],
                      historical_hold_sha256=held['sidecar_sha256'])
    else:
        try:
            charge = Decimal(str(billing['charged_usd']))
            if not charge.is_finite() or not 0 <= charge <= Decimal(TRIAL_CAP):
                raise ValueError('Invalid audited development charge')
        except (KeyError, InvalidOperation) as exc:
            raise ValueError('Known audited development charge required') from exc
        result.update(charged_usd=str(charge), known_billed_subtotal_usd=str(charge))
        count = billing.get('budget_stop_count')
        if type(count) is not int or count < 0:
            raise ValueError('Known audited budget stop count required')
        result.update(budget_stop_markers=count, capacity_budget_stopped=count > 0,
                      historical_pending_barrier_markers=0)
        for key in ('prompt_tokens', 'completion_tokens', 'requests'):
            value = billing.get(key)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError('Invalid audited development usage')
            result[key] = value
    return result


def _summary(rows):
    terminal = [row for row in rows if row['state'] in {'verified_terminal', HELD_TERMINAL}]
    passes = sum(row['reward'] for row in terminal)
    complete_cost = len(terminal) == 20 and all(row['charged_usd'] is not None for row in rows)
    known_liability = str(sum((Decimal(row['retained_liability_usd'])
        for row in rows if row['retained_liability_usd'] is not None), Decimal(0)))
    summary = {
        'intended_cells': 20, 'terminal_cells': len(terminal),
        'verified_cells': sum(row['state'] == 'verified_terminal' for row in rows),
        'held_cells': sum(row['state'] == HELD_TERMINAL for row in rows),
        'incomplete_cells': sum(row['state'] == 'incomplete' for row in rows),
        'unstarted_cells': sum(row['state'] == 'unstarted' for row in rows),
        'passes': passes, 'terminal_zero_rewards': len(terminal) - passes,
        'pass_rate_fixed_20': passes / 20 if len(terminal) == 20 else None,
        'known_billed_subtotal_usd': str(sum((Decimal(row['known_billed_subtotal_usd'])
            for row in rows if row['known_billed_subtotal_usd'] is not None), Decimal(0))),
        'full_cost_usd': str(sum((Decimal(row['charged_usd']) for row in rows), Decimal(0))) if complete_cost else None,
        'unknown_terminal_cost_cells': sum(row['charged_usd'] is None for row in terminal),
        'known_retained_liability_usd': known_liability,
        'retained_liability_usd': None if any(row['state'] == 'incomplete' for row in rows) else known_liability,
        'billing_complete': len(terminal) == 20 and all(row['billing_verified'] is True for row in rows),
        'known_budget_stop_markers': sum(row['budget_stop_markers'] for row in terminal),
        'known_capacity_budget_stopped_trials': sum(row['capacity_budget_stopped'] for row in terminal),
        'historical_pending_barrier_markers': sum(row['historical_pending_barrier_markers'] for row in terminal),
    }
    for key in ('prompt_tokens', 'completion_tokens', 'requests'):
        known = [row[key] for row in rows if row[key] is not None]
        summary['known_' + key + '_subtotal'] = sum(known)
        summary['cells_with_known_' + key] = len(known)
        summary['full_' + key] = sum(known) if len(known) == 20 else None
    summary['usage_complete'] = all(summary['full_' + key] is not None
                                  for key in ('prompt_tokens', 'completion_tokens', 'requests'))
    for phase in PHASES:
        key = phase + '_seconds'
        known = [row[key] for row in rows if row[key] is not None]
        summary['known_' + key + '_subtotal'] = fsum(known)
        summary['cells_with_known_' + key] = len(known)
        summary['full_' + key] = fsum(known) if len(known) == 20 else None
    summary['timing_complete'] = all(summary['full_' + phase + '_seconds'] is not None for phase in PHASES)
    return summary


def collect(root, admission):
    root = Path(root).resolve()
    runtime = root / '.runtime/stage2'
    lock_path = runtime / 'matrix.lock'
    info = _kind(root, lock_path)
    if info is None or not stat.S_ISREG(info.st_mode):
        raise ValueError('Existing matrix ownership lock required for a development snapshot')
    descriptor = os.open(lock_path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        settings = validate(root, admission)
        protocol = settings.fingerprint()
        manifest_path = root / 'stage2/input_manifest.json'
        manifest_raw = _read(root, manifest_path)
        tasks = json.loads(manifest_raw)['development_ids']
        if (not isinstance(tasks, list) or len(tasks) != 20 or len(set(tasks)) != 20
                or any(not isinstance(task, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,80}', task) for task in tasks)):
            raise ValueError('Exactly the frozen 20 safe unique development task IDs required')
        watched = {manifest_path: manifest_raw}
        hold = validate_historical_hold(runtime)
        parent = _registered_parent(root, runtime, tasks, admission, watched)
        cells = [_cell(condition, i, task, parent) for condition in CONDITIONS for i, task in enumerate(tasks)]
        expected = {cell['trial_id'] for cell in cells}
        ledger_trials = _ledger_trials(root, runtime)
        seen = set(ledger_trials)
        for tree in ('scored-trials', 'scored-attempts'):
            directory = runtime / tree
            info = _kind(root, directory)
            if info is not None:
                if not stat.S_ISDIR(info.st_mode):
                    raise ValueError('Unsafe development attempt inventory')
                seen.update(path.name for path in directory.iterdir())
        if any(any(identifier.startswith('dev-' + condition + '-') for condition in CONDITIONS)
               and identifier not in expected for identifier in seen):
            raise ValueError('Unexpected primary development trial identity; no substitutions')
        rows, audited = [], {condition: [] for condition in CONDITIONS}
        for cell in cells:
            identifier = cell['trial_id']
            attempt = runtime / 'scored-trials' / identifier
            gateway = runtime / 'scored-attempts' / identifier
            attempt_info, gateway_info = _kind(root, attempt), _kind(root, gateway)
            if any(info is not None and not stat.S_ISDIR(info.st_mode) for info in (attempt_info, gateway_info)):
                raise ValueError('Unsafe development attempt directory')
            started = attempt_info is not None or gateway_info is not None or identifier in ledger_trials
            if cell['harness'] == 'C2' and started and parent is None:
                raise ValueError('Started C2 cell lacks registered parent')
            path = attempt / 'result.json'
            if _kind(root, path) is None:
                watched[path] = None
                rows.append(_empty_row(cell, 'incomplete' if started else 'unstarted'))
                continue
            raw = _read(root, path)
            watched[path] = raw
            row = completed_cell(root, cell, settings)
            if row is None or _read(root, path) != raw:
                raise ValueError('Development evidence changed during audit')
            audited[cell['harness']].append(row)
            rows.append(_terminal_row(root, runtime, cell, row, protocol, raw))
        if parent is not None and select({condition: audited[condition] for condition in ('C0', 'C1')},
                task_ids=tasks, protocol=protocol)['selected_parent'] != parent:
            raise ValueError('C2 parent differs from audited registered selection')
        for path, before in watched.items():
            after = None if _kind(root, path) is None else _read(root, path)
            if before != after:
                raise ValueError('Development evidence changed during snapshot')
        if validate_historical_hold(runtime) != hold or validate(root, admission).fingerprint() != protocol:
            raise ValueError('Development protocol or historical hold changed during snapshot')
        summaries = {condition: _summary([row for row in rows if row['harness'] == condition]) for condition in CONDITIONS}
        return {'scope': SCOPE, 'intended_cells': 100, 'tasks_per_condition': 20,
            'diagnostic_trials_included': False, 'final_accuracy_or_win_claimed': False,
            'selection_or_expansion_authorized': False,
            'all_primary_cells_terminal': all(value['terminal_cells'] == 20 for value in summaries.values()),
            'conditions': summaries, 'rows': rows,
            'limitations': ['Partial conditions have no pass rate; unstarted and incomplete cells are not scored failures.',
                'The historical held zero remains in its fixed-20 denominator; its complete cost and token totals are unknown.',
                'Known billed subtotals exclude unknown charges. Retained liability is not an actual charge.',
                'Known billed, usage and liability subtotals cover audited terminal evidence only; incomplete attempts may contain additional settled charges or reservations.',
                'Phase durations use recorded setup, agent and verifier measurements; full totals require all 20 measurements, and missing durations are not zero.',
                'Development outcomes do not establish final-89 performance or a custom-harness win.'],
            'provenance': {'model_protocol_sha256': protocol, 'manifest_sha256': _digest(manifest_raw),
                'admission_sha256': _digest(_json_bytes(admission)),
                'historical_hold_sha256': hold['sidecar_sha256'] if hold else None,
                'c2_registration_sha256': (_digest(watched[runtime / 'development-blocks/C2.json'])
                    if watched[runtime / 'development-blocks/C2.json'] is not None else None),
                'result_sha256': {row['trial_id']: row['result_sha256'] for row in rows if row['result_sha256'] is not None}}}


def export(root, admission, destination):
    root = Path(root).resolve()
    destination = Path(destination).absolute()
    resolved = destination.resolve()
    if any(resolved == root / name or root / name in resolved.parents for name in ('.runtime', 'stage2', 'sources')):
        raise ValueError('Development exports must be outside runtime and source directories')
    bundle = collect(root, admission)
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=FIELDS, lineterminator='\n')
    writer.writeheader()
    writer.writerows(bundle['rows'])
    files = {'development_trials.csv': buffer.getvalue().encode(), 'development_comparison.json': _json_bytes(bundle)}
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    for name, raw in files.items():
        descriptor = os.open(destination / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    marker = _json_bytes({'scope': SCOPE, 'rows': 100,
        'snapshot_export_complete_not_experiment_complete': True,
        'files': {name: _digest(raw) for name, raw in files.items()}})
    descriptor = os.open(destination / 'export_complete.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as handle:
        handle.write(marker)
        handle.flush()
        os.fsync(handle.fileno())
    descriptor = os.open(destination, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--admission', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    arguments = parser.parse_args()
    print(export(Path(__file__).resolve().parents[1], json.loads(arguments.admission.read_text()), arguments.output))
