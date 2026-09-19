"""Explicit private dashboard deployment while benchmark execution is stopped.

This consumes only the already-rented host. It never calls model APIs, reads
provider credentials, changes benchmark results or publishes a network port.
Stop these services before resuming timed benchmark work; retain their volumes.
"""
import argparse
from contextlib import ExitStack
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from netcup.prepare_observability import EXPECTED, SOURCE, DIGEST
from scored_gateway import durable_json


def validate(document):
    if document.get('name') != 'uts-observability' or set(document.get('services', {})) != EXPECTED:
        raise ValueError('Expected the dedicated study dashboard')
    for name, service in document['services'].items():
        ports = {'langfuse-web': ['127.0.0.1:3300:3000'], 'minio': ['127.0.0.1:3390:9000']}.get(name, [])
        if service.get('ports', []) != ports or service.get('restart') != 'no':
            raise ValueError('Only registered loopback bindings and explicit service start allowed')
        if any(service.get(key) for key in ('privileged', 'network_mode', 'build', 'env_file', 'cap_add', 'devices')):
            raise ValueError('Unexpected host capability or inherited credentials')
        for mount in service.get('volumes', []):
            if not isinstance(mount, str) or mount.split(':')[0] not in document.get('volumes', {}):
                raise ValueError('Only dedicated named volumes allowed')
        if not isinstance(service.get('image'), str):
            raise ValueError('Explicit container image required')
    return document


def run(root, directory, *, execute=subprocess.run, output=subprocess.check_output):
    root, directory = Path(root).resolve(), Path(directory)
    if directory.is_symlink() or not directory.is_dir() or directory.stat().st_mode & 0o077:
        raise ValueError('Private prepared directory required')
    directory = directory.resolve()
    if directory.parent != root / '.runtime/stage2':
        raise ValueError('Prepared configuration must be inside the private study runtime')
    path = directory / 'compose.json'
    for name in ('compose.json', 'source.json', 'credentials.json'):
        candidate = directory / name
        if candidate.is_symlink() or not candidate.is_file() or candidate.stat().st_mode & 0o077:
            raise ValueError('Private prepared files required')
    source = json.loads((directory / 'source.json').read_text())
    if source.get('url') != SOURCE or source.get('sha256') != DIGEST:
        raise ValueError('Pinned official source required')
    document = validate(json.loads(path.read_text()))
    with ExitStack() as stack:
        for name in ('matrix.lock', 'scored.lock'):
            fd = os.open(root / '.runtime/stage2' / name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            handle = stack.enter_context(os.fdopen(fd, 'r+'))
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # No benchmark containers may remain from a stopped/interrupted job.
        running = output(['docker', 'ps', '--format', '{{.Names}}'], text=True, timeout=30).splitlines()
        if any(name.startswith(('uts-scored-', 'uts-oracle-')) for name in running):
            raise ValueError('Benchmark containers still running')
        pinned = directory / 'compose.pinned.json'
        if pinned.exists() or pinned.is_symlink():
            raise ValueError('Existing deployment requires inspection; never silently upgrade it')
        execute(['docker', 'compose', '-f', str(path), 'config', '--quiet'], check=True, timeout=30)
        execute(['docker', 'compose', '-f', str(path), 'pull'], check=True, timeout=900)
        images = {}
        for name, service in document['services'].items():
            info = json.loads(output(['docker', 'image', 'inspect', service['image']], text=True, timeout=30))[0]
            digests = info.get('RepoDigests', [])
            # Each freshly pulled image has at least one content-addressed ref.
            # Require its repository to match the originally requested source.
            repository = service['image'].rsplit(':', 1)[0] if ':' in service['image'].split('/')[-1] else service['image']
            repository = repository.removeprefix('docker.io/')
            choices = [value for value in digests if value.split('@')[0].removeprefix('docker.io/') == repository]
            if len(choices) != 1 or '@sha256:' not in choices[0]:
                raise ValueError('Unambiguous content-addressed image required')
            images[name] = {'requested': service['image'], 'pinned': choices[0], 'image_id': info['Id']}
            service['image'] = choices[0]
        durable_json(pinned, validate(document))
        durable_json(directory / 'images.json', images)
        execute(['docker', 'compose', '-f', str(pinned), 'up', '-d', '--wait', '--wait-timeout', '180'],
                check=True, timeout=240)
        return {'status': 'services_started_trace_export_not_yet_verified',
                'loopback_dashboard': 'http://127.0.0.1:3300', 'pinned_services': sorted(images)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(Path(__file__).resolve().parents[2], args.directory)))
