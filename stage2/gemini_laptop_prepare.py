"""Prepare frozen official task bytes and a new qualified portable Python bundle."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import urllib.request
from custom_python_runtime import PythonBundle


def prepare(root):
    private = root / '.runtime/gemini-dev20-laptop-20260930'
    private.mkdir(parents=True, exist_ok=True, mode=0o700)
    provenance = json.loads((root / 'stage2/dataset_provenance.json').read_text())
    cache = root / '.cache/gemini-laptop'
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / 'dataset.tar.gz'
    if not archive.exists():
        url = 'https://codeload.github.com/harbor-framework/terminal-bench-2-1/tar.gz/' + provenance['revision']
        with urllib.request.urlopen(url, timeout=120) as response, archive.open('wb') as stream:
            import shutil
            shutil.copyfileobj(response, stream)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != provenance['archive_sha256']:
        raise RuntimeError('Dataset archive differs from frozen provenance')
    unpacked = cache / ('terminal-bench-2-1-' + provenance['revision'])
    if not unpacked.exists():
        with tarfile.open(archive) as tar:
            tar.extractall(cache, filter='data')
    tasks = unpacked / 'tasks'
    expected = provenance['canonical']['file_hashes']
    for row in expected:
        path = tasks / row['path']
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise RuntimeError('Frozen task file hash mismatch')
    if {p.relative_to(tasks).as_posix() for p in tasks.rglob('*') if p.is_file()} != {r['path'] for r in expected}:
        raise RuntimeError('Dataset file inventory differs')
    canonical = root / provenance['dataset_path']
    if not canonical.exists():
        canonical.parent.mkdir(parents=True,exist_ok=True)
        canonical.symlink_to(tasks,target_is_directory=True)
    python_tar = private / 'python-runtime.tar.gz'
    if not python_tar.exists():
        vendor = private / 'vendor'
        subprocess.run(['uv', 'python', 'install', '3.12.13', '--install-dir', str(vendor)], check=True)
        source = next(vendor.glob('cpython-3.12.13-linux-x86_64-gnu'))
        def header(member):
            member.uid = member.gid = member.mtime = 0
            member.uname = member.gname = ''
            return member
        with python_tar.open('wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode='w') as tar:
                tar.add(source, arcname='python', filter=header)
    bundle = PythonBundle(python_tar, hashlib.sha256(python_tar.read_bytes()).hexdigest())
    proof = dict(dataset_revision=provenance['revision'],
        archive_sha256=provenance['archive_sha256'], verified_task_files=len(expected),
        tasks_path=str(tasks), python_bundle=bundle.validate(),
        python_runtime='CPython 3.12.13; newly packed for this experiment; not historic archive')
    (private / 'preparation.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({k:v for k,v in proof.items() if k != 'tasks_path'}))


if __name__ == '__main__':
    prepare(Path.cwd())
