"""Offline accounting qualification on an isolated native candidate ONLY.

No provider credential is read and no inference client is constructed. Original
production evidence is read for byte comparisons, never modified. Each mode
writes one new immutable qualification record into the candidate's private state.
"""
import argparse
from contextlib import ExitStack, closing
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'stage2'))
from deferred_billing import (_encoded, _json, _read, _write, validate_deferrals,
    extra_exposure_nanodollars, unresolved_liability_nanodollars)
from receipt_accounting import activate, DIRECTORY
from receipt_runtime_transition import CHECKS, TRANSITION, digest
from scoring_admission import source_hashes, validate
from model_protocol import ModelSettings
import host_environment


def command(*arguments, **kwargs):
    return subprocess.check_output(list(arguments), text=True, timeout=120, **kwargs).strip()


def protected(runtime):
    names = ['setup_budget.sqlite', 'scored_budget.sqlite']
    names += [str(path.relative_to(runtime)) for path in runtime.glob('*.json')]
    for folder in ('scored-attempts', 'scored-trials', 'deferred-billing'):
        names.extend(str(path.relative_to(runtime)) for path in (runtime / folder).rglob('*') if path.is_file())
    return {name: hashlib.sha256((runtime / name).read_bytes()).hexdigest()
            for name in sorted(names) if (runtime / name).is_file() and not name.endswith(TRANSITION)}


def exposure(runtime):
    with closing(sqlite3.connect((runtime / 'scored_budget.sqlite').as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('BEGIN')
        entries = validate_deferrals(runtime, db, kind='scored')
        rows = db.execute("SELECT id,reserved FROM requests WHERE state='pending' ORDER BY id").fetchall()
        known = db.execute('SELECT COALESCE(SUM(charged),0) FROM requests').fetchone()[0]
        stages = {}
        for stage, cap in db.execute('SELECT name,cap FROM stages'):
            base = db.execute('''SELECT COALESCE(SUM(COALESCE(r.charged,r.reserved)),0)
                FROM requests r JOIN trial_stages s ON r.trial=s.trial WHERE s.stage=?''', (stage,)).fetchone()[0]
            stages[stage] = {'exposure': base + extra_exposure_nanodollars(entries, stage=stage), 'cap': cap}
        return {'known': known, 'pending_rows': rows, 'stages': stages,
                'unresolved': unresolved_liability_nanodollars(db, entries),
                'extra_receipt_hold': extra_exposure_nanodollars(entries)}


def replay(root, production, admission):
    runtime, canonical = root / '.runtime/stage2', production / '.runtime/stage2'
    original, copied = protected(canonical), protected(runtime)
    before = exposure(runtime)
    entries = validate_deferrals(runtime, kind='scored')
    identifiers = [identifier for entry in entries for identifier in entry['unverified_receipt_request_ids']
                   if (runtime / 'deferred-receipt-recovery-v1' / ('scored--' + identifier + '.json')).is_file()]
    result = activate(runtime, kind='scored', request_ids=identifiers)
    after = exposure(runtime)
    repeat = activate(runtime, kind='scored', request_ids=identifiers)
    stale_rejected = False
    try:
        validate(root, admission)
    except ValueError as exc:
        stale_rejected = str(exc) == 'Runtime code changed since qualification'
    reduction = before['extra_receipt_hold'] - after['extra_receipt_hold']
    checks = {'originals_unchanged': protected(canonical) == original and protected(runtime) == copied,
        'unknown_reservations_unchanged': before['pending_rows'] == after['pending_rows'],
        'exact_hold_reduction': result['hold_reduction_nanodollars'] == reduction > 0
            and before['known'] == after['known']
            and before['unresolved'] - after['unresolved'] == reduction,
        'idempotent_activation': repeat['activated_receipts'] == repeat['hold_reduction_nanodollars'] == 0
            and repeat['already_activated'] == len(identifiers),
        'stale_admission_rejected': stale_rejected}
    return {'checks': checks, 'receipts_activated': len(identifiers),
        'hold_reduction_nanodollars': reduction, 'before': before['stages'], 'after': after['stages'],
        'protected_original_files': len(original),
        'activation_files': {str(path.relative_to(runtime)): hashlib.sha256(path.read_bytes()).hexdigest()
                             for path in (runtime / DIRECTORY).glob('*.json')},
        'preserved_results': {name: checksum for name, checksum in copied.items()
                              if name.startswith('scored-trials/') and name.endswith('/result.json')}}


def offline(root, sources):
    interfaces = json.loads(command('ip', '-json', 'link', 'show'))
    if {entry['ifname'] for entry in interfaces} != {'lo'}:
        raise ValueError('Native suite must execute in a private loopback-only network namespace')
    files = sorted(set(root.glob('stage2/test_*.py')) | set(root.glob('stage2/*_tests.py')) |
                   set(root.glob('tests/test_*.py')))
    if any('spending' in path.name for path in files):
        raise ValueError('Paused spending work must not be included in candidate qualification')
    if not files or not (root / 'tests/test_custom_harness.py').is_file():
        raise ValueError('Complete stage2, custom and legacy suite required')
    names = [str(path.relative_to(root).with_suffix('')).replace('/', '.') for path in files]
    sys.path.insert(0, str(root))
    suite = unittest.defaultTestLoader.loadTestsFromNames(names)
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    return {'checks': {'all_tests_passed': result.wasSuccessful() and not result.skipped,
                      'external_network_disabled': True, 'sources_unchanged': source_hashes(root) == sources},
            'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
            'skipped': len(result.skipped),
            'test_source_hashes': {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}}


def gateway(root, admission, image, sources):
    parent = json.loads(command('docker', 'image', 'inspect', admission['gateway_image']))[0]
    candidate = json.loads(command('docker', 'image', 'inspect', image))[0]
    common = ['docker', 'run', '--rm', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
              '--security-opt', 'no-new-privileges', '--entrypoint', 'python']
    code = "import hashlib,json,pathlib; print(json.dumps({n:hashlib.sha256((pathlib.Path('/study/stage2')/n).read_bytes()).hexdigest() for n in " + repr([n for n in sources if n.endswith('.py')]) + "}))"
    observed = json.loads(command(*common, image, '-c', code))
    # Execute this same read-only accounting function inside the candidate image.
    script = Path(__file__).read_text()
    prefix = script[:script.index('\ndef replay(')]
    prefix = prefix.replace('ROOT = Path(__file__).resolve().parents[2]', "ROOT = Path('/study')")
    code = prefix + "\nprint(json.dumps(exposure(Path('/study/.runtime/stage2'))))\n"
    container = json.loads(command(*common,
        '--mount', 'type=bind,source=' + str(root / '.runtime/stage2') + ',target=/study/.runtime/stage2,readonly',
        image, '-c', code))
    host = json.loads(json.dumps(exposure(root / '.runtime/stage2')))
    layers = parent['RootFS']['Layers']
    return {'parent_image': admission['gateway_image'], 'checks': {
        'parent_layers_preserved': candidate['RootFS']['Layers'][:len(layers)] == layers,
        'image_configuration_unchanged': candidate['Config'] == parent['Config'],
        'image_sources_match': observed == {name: value for name, value in sources.items() if name.endswith('.py')},
        'offline_accounting_matches_host': container == host},
        'image_source_hashes': observed}


def register_candidate(root, admission, image, sources):
    """Assemble and actually validate the transition in the isolated copy."""
    from run_baselines import validate_registration
    runtime = root / '.runtime/stage2'
    proofs = {}
    for role in CHECKS:
        relative = 'accounting-qualification-v1/' + role + '.json'
        raw = _read(runtime / relative, runtime)
        proofs[role] = {'path': relative, 'sha256': hashlib.sha256(raw).hexdigest()}
    rehearsal = _json(_read(runtime / proofs['replay']['path'], runtime))
    document = {'schema_version': 1, 'kind': 'qualified_additive_receipt_accounting_transition',
        'scope': 'accounting_only_no_replay_no_model_or_limit_change',
        'reviewer': 'Codex source review, native offline qualification and immutable-evidence rehearsal',
        'original_admission_sha256': digest(admission),
        'baseline_registration_sha256': hashlib.sha256(_read(runtime / 'baseline-matrix.json', runtime)).hexdigest(),
        'source_hashes': sources, 'gateway_image': image, 'guard_image': admission['guard_image'],
        'host_environment': admission['host_environment'],
        'model_protocol_sha256': ModelSettings(**admission['settings']).fingerprint(), 'proofs': proofs,
        'activation_files': rehearsal['activation_files'], 'preserved_results': rehearsal['preserved_results']}
    _write(runtime / TRANSITION, document)
    validate(root, admission)
    descriptor = validate_registration(root, admission)
    return {'candidate_transition_valid': True, 'original_baseline_cells': len(descriptor['cells']),
            'production_changed': False, 'live_api_calls': 0,
            'transition_sha256': hashlib.sha256((runtime / TRANSITION).read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('offline', 'replay', 'gateway', 'register'))
    parser.add_argument('--production-root', required=True, type=Path)
    parser.add_argument('--gateway-image', required=True)
    args = parser.parse_args()
    os.umask(0o077)
    production = args.production_root.resolve()
    if (ROOT.parent != production / '.runtime' or not ROOT.name.startswith('receipt-accounting-candidate-')
            or (ROOT / '.env').exists() or ROOT == production):
        raise ValueError('Credential-free isolated native accounting candidate required')
    runtime = ROOT / '.runtime/stage2'
    output = (runtime / TRANSITION if args.mode == 'register' else
              runtime / 'accounting-qualification-v1' / (args.mode + '.json'))
    if output.exists() or output.is_symlink():
        raise ValueError('Preserve the existing qualification attempt')
    original_admission = _json(_read(runtime / 'baseline-matrix.json', runtime))['admission']
    identity = host_environment.snapshot()
    if identity != original_admission['host_environment']:
        raise ValueError('Candidate host differs from original execution host')
    sources = source_hashes(ROOT)
    with ExitStack() as stack:
        # Holding canonical locks prevents a scheduler or collector from racing
        # this offline rehearsal; the copied runtime owns different lock inodes.
        for name in ('matrix.lock', 'scored.lock', 'gateway.lock'):
            fd = os.open(production / '.runtime/stage2' / name, os.O_RDWR | os.O_NOFOLLOW)
            handle = stack.enter_context(os.fdopen(fd, 'r+'))
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.mode == 'offline': evidence = offline(ROOT, sources)
        elif args.mode == 'replay': evidence = replay(ROOT, production, original_admission)
        elif args.mode == 'register':
            print(json.dumps(register_candidate(ROOT, original_admission, args.gateway_image, sources)))
            return
        else: evidence = gateway(ROOT, original_admission, args.gateway_image, sources)
    evidence.update(kind='native_offline_receipt_accounting_' + args.mode,
        source_hashes=sources, host_environment=identity, gateway_image=args.gateway_image,
        guard_image=original_admission['guard_image'],
        model_protocol_sha256=ModelSettings(**original_admission['settings']).fingerprint(),
        live_api_calls=0)
    evidence['checks']['sources_unchanged'] = source_hashes(ROOT) == sources
    evidence['status'] = 'passed' if all(evidence['checks'].values()) else 'failed'
    output.parent.mkdir(mode=0o700, exist_ok=True)
    _write(output, evidence)
    print(json.dumps({'mode': args.mode, 'status': evidence['status'], 'checks': evidence['checks'],
                     'proof_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                     'tests_run': evidence.get('tests_run'), 'live_api_calls': 0}))
    if evidence['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
