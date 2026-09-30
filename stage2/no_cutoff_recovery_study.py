"""Session-bound registration and single-trial admission, not a launcher.

Only a live, locked prerequisite session can register or open this scope. The
future native service/dispatcher must consume it in the same process and async
task after a fresh real handoff. Saved inspection receipts are not authority.
This module does not produce qualification, start a service or call a model.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import stat
from types import FunctionType
import weakref

import no_cutoff_recovery_policy as policy
import no_cutoff_recovery_session as session
import no_cutoff_recovery_files as evidence
import no_cutoff_recovery_qualification as qualification
from no_cutoff_recovery_result import RetainedPreparation, validate as validate_preparation, empty_agent_context
check_files = evidence.check
from credit_only_experiment import cleanup_complete
from completion_wait import completion_wait_for
from no_cutoff_recovery_files import save as durable_json

_CURRENT = ContextVar('no_cutoff_recovery_dispatch', default=None)
_PERMITS = weakref.WeakKeyDictionary()


class _Permit:
    __slots__ = ('__weakref__',)

    def __reduce__(self):
        raise TypeError('Recovery permits cannot be saved or copied')


def _private(root, name):
    return evidence.private(root, name)


def _qualified(active):
    verified = qualification.for_dispatch(active)
    return (verified['root'], verified['proof'], verified['block'],
        verified['files'], verified['identities'])


def _attempts(root, block, *, observe_provider_stops=False):
    """Strict retained coverage metadata; not the completed trace/export audit."""
    rt = root / '.runtime/stage2'
    intended = {cell['trial_id']: cell for cell in block['cells']}
    seen_attempts = set()
    for folder in ('scored-trials', 'scored-attempts'):
        base = rt / folder
        if not base.exists() and not base.is_symlink():
            continue
        paths = [base, *base.iterdir()] if base.is_dir() and not base.is_symlink() else [base]
        for path in paths:
            evidence.bootstrap.directories(path, private=True)
            info = path.lstat()
            if (not stat.S_ISDIR(info.st_mode) or path.resolve() != path
                    or info.st_uid != os.getuid() or info.st_mode & 0o077
                    or (path != base and path.name not in intended)):
                raise ValueError('Owned private registered attempt directories required')
            if path != base: seen_attempts.add(path.name)
            stop = path / 'provider-stop.json'
            if not observe_provider_stops and (stop.exists() or stop.is_symlink()):
                raise ValueError('Persistent provider stop forbids further recovery admission')
    bindings, identities, records = {}, {}, {}
    for cell in block['cells']:
        for name in ('started.json', 'result.json'):
            path = rt / 'scored-trials' / cell['trial_id'] / name
            if path.exists() or path.is_symlink():
                relative = path.relative_to(root).as_posix()
                raw, captured = evidence.read(root, relative)
                bindings[relative] = hashlib.sha256(raw).hexdigest()
                identities[relative] = captured['identity']
                records[(cell['trial_id'], name)] = evidence.bootstrap.loads(raw)
    if bindings:
        check_files(root, bindings)
    complete = {}
    for name in seen_attempts:
        if (name, 'result.json') in records:
            if (name, 'started.json') not in records:
                raise ValueError('A retained recovery result requires its original start')
            complete[name] = records[(name, 'result.json')]
    partial = sorted(seen_attempts - set(complete))
    started = set(complete) | set(partial)
    if started != {cell['trial_id'] for cell in block['cells'][:len(started)]}:
        raise ValueError('Retained attempts must be the fixed sequential prefix')
    for name, result in complete.items():
        expected = dict(trial_id=name, task_id=intended[name]['task_id'], harness=policy.CONDITION,
            stage='final', recovery_experiment=policy.EXPERIMENT,
            recovery_registration_sha256=policy.fingerprint(block),
            model_protocol_sha256=policy.MODEL_SHA256, accounting_mode='provider-credit-only')
        for key, value in expected.items():
            if policy.fingerprint(result.get(key)) != policy.fingerprint(value):
                raise ValueError('Retained recovery result identity differs from registration')
        if result.get('model_revoked') is not True or not cleanup_complete(result):
            raise ValueError('Retained recovery requires model revocation and owned cleanup')
        if any(result.get(k) is not None for k in ('custom_study', 'accounting_runtime_transition_sha256',
                'matched_repeat_experiment', 'recovery_fixture')):
            raise ValueError('Legacy, synthetic or receipt-transition results are not paid recoveries')
        observation = validate_preparation(result.get('recovery_preparation'))
        if not observation['observation_complete']:
            raise ValueError('Incomplete setup diagnostics require inspection, never replay')
        inner = observation['observation']
        if inner['terminal'] != 'returned' and ('agent' in result.get('phase_seconds', {})
                or 'verifier' in result.get('phase_seconds', {}) or not empty_agent_context(result.get('agent_context'))
                or result.get('billing', {}).get('requests') != 0
                or result.get('verifier_result') is not None):
            raise ValueError('Failed preparation cannot have agent/model/verifier execution')
        reward = ((result.get('verifier_result') or {}).get('rewards') or {}).get('reward')
        if reward is not None and (type(reward) not in (int, float) or reward not in (0, 1)):
            raise ValueError('Recovery verifier outcome must be zero, one or genuinely missing')
        started_record, saved = _private(root, 'scored-trials/' + name + '/started.json')
        if (any(policy.fingerprint(started_record.get(k)) != policy.fingerprint(v) for k, v in expected.items())
                or any(started_record.get(k) != result.get(k) for k in ('project', 'started_utc',
                    'gateway_image_id', 'guard_image_id'))):
            raise ValueError('Retained result differs from its original start identity')
        bindings.update(saved)
    if bindings:
        check_files(root, bindings, identities)
    return complete, partial, bindings


def _images(root, proof, complete):
    host, _ = _private(root, policy.RUNTIME_FILE)
    for value in complete.values():
        for name, digest in value['recovery_preparation']['observation']['sources'].items():
            policy._same(proof['sources'].get(name), digest)
        if (value.get('gateway_image_id') != proof['gateway_image']
                or value.get('guard_image_id') != proof['guard_image']
                or value.get('task_image_id') != host['task_inventory'][value['task_id']]['image_id']):
            raise ValueError('Retained recovery gateway, guard or task image differs from qualification')


def _clear(root):
    session.handoff._no_stop(root)
    qualification.no_failure(root)
    path = root / '.runtime/stage2/accounting-runtime-transition-v1.json'
    if path.exists() or path.is_symlink():
        raise ValueError('Historical receipt runtime transitions cannot alter a qualified recovery')


def register(active):
    """Exclusive immutable registration, only after actual live qualification checks."""
    root, proof, expected, files, identities = _qualified(active)
    _clear(root)
    path = root / '.runtime/stage2' / policy.REGISTRATION_FILE
    exists = path.exists() or path.is_symlink()
    if exists:
        block, bound = _private(root, policy.REGISTRATION_FILE)
        if policy.fingerprint(block) != policy.fingerprint(expected):
            raise ValueError('Recovery registration is immutable')
        files.update(bound)
        identities.update(evidence.capture(root, bound)[1])
    complete, partial, _ = _attempts(root, expected)
    _images(root, proof, complete)
    if partial or (complete and not exists):
        raise ValueError('Started recovery keys cannot be registered again or replayed')
    check_files(root, files, identities); _clear(root)
    if not exists:
        durable_json(path, expected)
    recorded, _ = _private(root, policy.REGISTRATION_FILE)
    if policy.fingerprint(recorded) != policy.fingerprint(expected):
        raise ValueError('Saved recovery registration changed')
    return deepcopy(recorded)


def _state(permit=None):
    permit = _CURRENT.get() if permit is None else permit
    if not isinstance(permit, _Permit) or permit not in _PERMITS or _CURRENT.get() is not permit:
        raise ValueError('Use the active qualified recovery dispatch scope, not saved metadata')
    state = _PERMITS[permit]
    # The session enforces PID, thread and async-task ownership, including a
    # ContextVar inherited by a child task, and stays locked until scope exit.
    try:
        session._live(state['session'])
    except BaseException:
        _PERMITS.pop(permit, None)
        raise
    return permit, state


def _quick(state):
    _clear(state['root']); check_files(state['root'], state['files'], state['identities'])


@contextmanager
def dispatch_permit(active):
    """No callback or saved record can replace the real same-task session."""
    if _CURRENT.get() is not None:
        raise ValueError('Nested recovery dispatch scopes are refused')
    root, proof, block, files, identities = _qualified(active)
    recorded, bound = _private(root, policy.REGISTRATION_FILE)
    if policy.fingerprint(recorded) != policy.fingerprint(block):
        raise ValueError('Exact qualified recovery registration required')
    files.update(bound)
    identities.update(evidence.capture(root, bound)[1])
    complete, partial, retained = _attempts(root, block)
    _images(root, proof, complete)
    if partial:
        raise ValueError('Started or interrupted recovery key cannot be replayed')
    _clear(root); check_files(root, files, identities)
    permit = _Permit()
    state = dict(session=active, root=root, proof=proof, block=block, files=files, identities=evidence.capture(root, files)[1],
        retained=retained, retained_identities=evidence.capture(root, retained)[1],
        issued=None, factory=None, shape=None, constructed=False, preparation=None)
    _PERMITS[permit] = state
    token = _CURRENT.set(permit)
    try:
        yield permit
    finally:
        _PERMITS.pop(permit, None)
        _CURRENT.reset(token)


def _shape(function, seen=None):
    """Identity of the issued wrapper and nested original factory closures.

    This detects accidental callable substitution/mutation in trusted host
    orchestration; it is not a sandbox against arbitrary code in that process.
    """
    if not isinstance(function, FunctionType):
        raise ValueError('Original C0-NC function factory required')
    seen = set() if seen is None else seen
    if function in seen:
        return function, function.__code__
    seen.add(function)
    return (function, function.__code__, deepcopy(function.__dict__), function.__defaults__,
        deepcopy(function.__kwdefaults__), tuple(_shape(cell.cell_contents, seen)
            if isinstance(cell.cell_contents, FunctionType) else id(cell.cell_contents)
            for cell in function.__closure__ or ()))


def agent_factory(permit):
    """Issue the unchanged C0-NC factory, never a caller-selected callable."""
    _, state = _state(permit)
    if state['factory'] is not None:
        return state['factory']
    from no_cutoff_custom_agent import agent_factory as original_factory
    _quick(state)
    native = original_factory(state['root'], 'C0')

    def create(**kwargs):
        try:
            _, current = _state(permit)
            _quick(current)
            cell = current['issued']
            if cell is None or current['constructed'] or _shape(create) != current['shape']:
                raise ValueError('One original factory construction per admitted recovery key required')
            task = session.describe(current['session'])['runtime']['task_inventory'][cell['task_id']]
            expected_path = current['root'] / '.runtime/stage2/scored-trials' / cell['trial_id']
            if (Path(kwargs['paths'].trial_dir) != expected_path
                    or kwargs['agent_timeout_seconds'] != task['agent_timeout_seconds']
                    or kwargs['completion_wait_seconds'] != completion_wait_for(task['agent_timeout_seconds'])):
                raise ValueError('Factory paths and official deadline must match the admitted task')
            current['constructed'] = True
            return native(**kwargs)
        except BaseException:
            _PERMITS.pop(permit, None)
            raise

    create.harness = policy.CONDITION
    create.model_protocol_sha256 = policy.MODEL_SHA256
    state['factory'] = create
    state['shape'] = _shape(create)
    return create


def admit_trial(root, *, trial_id, task_id, stage, factory, settings, gateway_image, guard_image,
                setup_timeout_seconds):
    permit, state = _state()
    try:
        if Path(root) != state['root']:
            raise ValueError('Recovery scope belongs to a different native root')
        root, proof, block, files, identities = _qualified(state['session'])
        _quick(state)
        if (files != {k: v for k, v in state['files'].items()
                if k != '.runtime/stage2/' + policy.REGISTRATION_FILE}
                or policy.fingerprint(block) != policy.fingerprint(state['block'])):
            raise ValueError('Qualified recovery bindings changed during dispatch')
        complete, partial, retained = _attempts(root, block)
        _images(root, proof, complete)
        if any(retained.get(name) != sha for name, sha in state['retained'].items()):
            raise ValueError('Previously retained recovery start or result bytes changed')
        check_files(root, state['retained'], state['retained_identities'])
        if partial or len(complete) == 3:
            raise ValueError('No fresh next recovery key; partial keys are never replayed')
        cell = block['cells'][len(complete)]
        if (state['issued'] is not None and state['issued']['trial_id'] not in complete
                or (trial_id, task_id, stage) != (cell['trial_id'], cell['task_id'], 'final')
                or factory is not state['factory'] or factory is None
                or _shape(factory) != state['shape'] or settings != policy.SETTINGS
                or gateway_image != proof['gateway_image'] or guard_image != proof['guard_image']
                or type(setup_timeout_seconds) not in (int, float) or setup_timeout_seconds != 900):
            raise ValueError('Only the next registered key and issued original C0-NC factory are admitted')
        _quick(state)
        evidence.extend(root, retained, state['retained_identities'])
        state.update(retained=retained, issued=deepcopy(cell), constructed=False,
            preparation=RetainedPreparation())
        return policy.fingerprint(block)
    except BaseException:
        _PERMITS.pop(permit, None)
        raise


def require_task_image(root, task_id, actual_image):
    permit, state = _state()
    try:
        _quick(state)
        cell = state['issued']
        if Path(root) != state['root'] or cell is None or cell['task_id'] != task_id:
            raise ValueError('Post-start image check needs this same admitted recovery task')
        expected = session.describe(state['session'])['runtime']['task_inventory'][task_id]['image_id']
        if actual_image != expected:
            raise ValueError('Started recovery container differs from its qualified original image')
    except BaseException:
        _PERMITS.pop(permit, None)
        raise


def preparation(root, trial_id):
    """Issue only the fixed observer associated with this actual admitted key."""
    _, state = _state()
    _quick(state)
    if (Path(root) != state['root'] or state['issued'] is None
            or state['issued']['trial_id'] != trial_id or state['preparation'] is None):
        raise ValueError('The current admitted recovery key must own its observer')
    return state['preparation']
