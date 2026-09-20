"""Explicit stopped-host deployment; never launches scoring or provider calls.

Requires the qualified isolated candidate and the original unchanged runtime.
Backs up source/evidence before replacing the eight allowlisted source files.
Activation is additive: original ledgers, outcomes and registration stay intact.
"""
import argparse
from contextlib import ExitStack
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def new_bytes(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(raw); handle.flush(); os.fsync(handle.fileno())
    fd = os.open(path.parent, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--production-root', type=Path, required=True)
    parser.add_argument('--candidate-root', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--execute', action='store_true', required=True)
    args = parser.parse_args()
    root, candidate = args.production_root.resolve(), args.candidate_root.resolve()
    if (candidate.parent != root / '.runtime' or not candidate.name.startswith('receipt-accounting-candidate-')
            or (candidate / '.env').exists() or not re.fullmatch(r'[a-f0-9]{40}', args.commit)):
        raise ValueError('Explicit credential-free isolated candidate and committed source required')
    sys.path.insert(0, str(candidate / 'stage2'))
    sys.path.insert(0, str(candidate / 'stage2/netcup'))
    from deferred_billing import _json, _read, _write, validate_deferrals
    from receipt_runtime_transition import CHANGED, ADDED, TRANSITION, qualified_transition
    from run_baselines import validate_registration
    from scoring_admission import source_hashes, validate
    from qualify_receipt_accounting import protected, exposure
    os.umask(0o077)
    runtime, copied = root / '.runtime/stage2', candidate / '.runtime/stage2'
    admission = _json(_read(runtime / 'baseline-matrix.json', runtime))['admission']
    with ExitStack() as stack:
        for name in ('matrix.lock', 'scored.lock', 'gateway.lock'):
            _read(runtime / name, runtime)
            fd = os.open(runtime / name, os.O_RDWR | os.O_NOFOLLOW)
            handle = stack.enter_context(os.fdopen(fd, 'r+'))
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = subprocess.check_output(['systemctl', 'show', 'uts-stage2-baselines-netcupv8.service',
            '--property=ActiveState', '--value'], text=True, timeout=10).strip()
        if state not in {'failed', 'inactive'} or subprocess.check_output(['docker', 'ps', '-q'], text=True, timeout=20).strip():
            raise ValueError('Study must be stopped with no running containers before deployment')
        if (runtime / TRANSITION).exists() or (runtime / TRANSITION).is_symlink():
            raise ValueError('Original runtime already has a transition; inspect instead of redeploying')
        transition = qualified_transition(candidate, admission)
        if transition is None or len(validate_registration(candidate, admission)['cells']) != 178:
            raise ValueError('Candidate has not actually qualified the original matrix')
        originals = protected(runtime)
        if originals != protected(copied):
            raise ValueError('Qualified copy and original evidence differ')
        for name, checksum in admission['source_hashes'].items():
            path = root / 'stage2' / name
            if path.is_symlink() or sha(path) != checksum:
                raise ValueError('Original admitted source changed: ' + name)
        names = sorted(CHANGED | ADDED)
        for name in ADDED:
            path = root / 'stage2' / name
            if path.is_symlink(): raise ValueError('Unsafe source destination')
            if path.exists():
                expected = ('f9c0711c14b46854b11e7a9eeb3a1238e63874b24b53e8a67c4c1d99d004ba0d'
                            if name == 'scoring_admission.py' else transition['source_hashes'][name])
                if sha(path) != expected: raise ValueError('Unrelated source would be overwritten: ' + name)
        for activation in transition['activation_files']:
            batch = _json(_read(copied / activation, copied))
            for identifier, checksum in batch['receipts'].items():
                receipt = runtime / 'deferred-receipt-recovery-v1' / (batch['kind'] + '--' + identifier + '.json')
                if hashlib.sha256(_read(receipt, runtime)).hexdigest() != checksum:
                    raise ValueError('Canonical receipt differs from qualified activation')
        validate_deferrals(runtime, kind='scored')
        before = exposure(runtime)
        backup = Path(tempfile.mkdtemp(prefix='receipt-accounting-deployment-v1-', dir=root / '.runtime'))
        with tarfile.open(backup / 'originals.tar.gz', 'x:gz', dereference=False) as archive:
            archive.add(runtime, arcname='runtime')
            for name in names:
                path = root / 'stage2' / name
                if path.exists(): archive.add(path, arcname='stage2/' + name)
        backup_sha = sha(backup / 'originals.tar.gz')
        # The three canonical locks remain held through installation/validation.
        for name in names:
            target = root / 'stage2' / name
            raw = (candidate / 'stage2' / name).read_bytes()
            if hashlib.sha256(raw).hexdigest() != transition['source_hashes'][name]:
                raise ValueError('Qualified candidate changed during deployment')
            fd, temporary = tempfile.mkstemp(prefix='.receipt-install-', dir=target.parent)
            with os.fdopen(fd, 'wb') as handle:
                handle.write(raw); handle.flush(); os.fsync(handle.fileno())
            os.replace(temporary, target)
        additions = [entry['path'] for entry in transition['proofs'].values()]
        additions += list(transition['activation_files']) + [TRANSITION]
        for relative in additions:
            target = runtime / relative
            target.parent.mkdir(mode=0o700, exist_ok=True)
            new_bytes(target, _read(copied / relative, copied))
        # Validate through a fresh process importing the DEPLOYED sources.
        verify_code = "import json; from pathlib import Path; from run_baselines import validate_registration; " \
            "r=Path('.').resolve(); a=json.loads((r/'.runtime/stage2/baseline-matrix.json').read_text())['admission']; " \
            "assert len(validate_registration(r,a)['cells'])==178; print('deployed_registration_valid')"
        verified = subprocess.check_output([str(root / '.venv/bin/python'), '-c', verify_code],
            cwd=root, env=dict(os.environ, PYTHONPATH=str(root / 'stage2')), text=True, timeout=120).strip()
        after = exposure(runtime)
        if (verified != 'deployed_registration_valid' or protected(runtime) != originals
                or source_hashes(root) != transition['source_hashes']
                or before['pending_rows'] != after['pending_rows']):
            raise ValueError('Deployment verification failed; keep scoring stopped')
        result = {'kind': 'verified_accounting_only_deployment', 'status': 'passed', 'commit': args.commit,
            'transition_sha256': sha(runtime / TRANSITION), 'original_files_unchanged': len(originals),
            'unknown_reservations_unchanged': True, 'generation_calls': 0, 'benchmark_restarted': False,
            'baseline_registration_sha256': sha(runtime / 'baseline-matrix.json'),
            'sources': transition['source_hashes'], 'gateway_image': transition['gateway_image'],
            'hold_reduction_nanodollars': before['unresolved'] - after['unresolved'],
            'before_stages': before['stages'], 'after_stages': after['stages'],
            'backup_path': str(backup), 'backup_sha256': backup_sha}
        _write(backup / 'verification.json', result)
        print(json.dumps(result))


if __name__ == '__main__':
    main()
