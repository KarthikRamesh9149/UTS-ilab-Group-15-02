"""Pinned Python fallback installed privately in the task container.

Existing task interpreters and packages remain ahead of the fallback on PATH."""
from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import posixpath
import re
import shlex
import tarfile


@dataclass(frozen=True)
class PythonBundle:
    path: Path
    sha256: str

    def validate(self):
        path = Path(self.path)
        if (path.is_symlink() or not path.is_file() or not re.fullmatch(r'[0-9a-f]{64}', self.sha256)
                or path.stat().st_size > 100 * 1024**2):
            raise ValueError('Invalid pinned Python bundle')
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != self.sha256:
                raise ValueError('Python bundle hash changed')
        names, links, total = set(), set(), 0
        with tarfile.open(path, 'r:gz') as archive:
            for member in archive:
                name = member.name.rstrip('/')
                if (not name or name in names or not (name == 'python' or name.startswith('python/'))
                        or name != posixpath.normpath(name) or member.mode & 0o6000
                        or not (member.isfile() or member.isdir() or member.issym())):
                    raise ValueError('Unsafe Python bundle member')
                names.add(name)
                total += member.size
                if len(names) > 10000 or total > 300 * 1024**2:
                    raise ValueError('Python bundle extraction limit exceeded')
                if member.issym():
                    target = posixpath.normpath(posixpath.join(posixpath.dirname(name), member.linkname))
                    if member.linkname.startswith('/') or not target.startswith('python/'):
                        raise ValueError('Python bundle link escapes distribution')
                    links.add(name)
            if 'python/bin/python3' not in names:
                raise ValueError('Python bundle lacks interpreter')
        if any(str(parent) in links for name in names for parent in PurePosixPath(name).parents):
            raise ValueError('Python bundle contains a symlink parent')
        return dict(sha256=self.sha256, members=len(names), unpacked_bytes=total)


class PythonFallbackEnvironment:
    def __init__(self, environment, bin_path):
        if not re.fullmatch(r'/tmp/uts-python-[A-Za-z0-9]+/python/bin', bin_path):
            raise ValueError('Unexpected private interpreter location')
        self.environment = environment
        self.bin_path = bin_path

    async def exec(self, command, **kwargs):
        # Append: keep a task's existing interpreter/packages ahead of the
        # fallback. bash -c in the capture helper preserves this PATH.
        return await self.environment.exec('export PATH="$PATH":' + shlex.quote(self.bin_path)
            + '; ' + command, **kwargs)

    def __getattr__(self, name):
        return getattr(self.environment, name)


async def prepare_python(environment, bundle):
    proof = bundle.validate()
    check = await environment.exec('command -v bash && command -v tar && command -v sha256sum', timeout_sec=15)
    if check.return_code:
        raise RuntimeError('Task image lacks bootstrap bash, tar or sha256sum')
    created = await environment.exec('mktemp -d /tmp/uts-python-XXXXXXXXXXXX', timeout_sec=15)
    target = (created.stdout or '').strip()
    if created.return_code or not re.fullmatch(r'/tmp/uts-python-[A-Za-z0-9]+', target):
        raise RuntimeError('Private Python directory could not be created')
    archive = target + '/bundle.tar.gz'
    await environment.upload_file(bundle.path, archive)
    command = ('printf "%s  %s\\n" ' + shlex.quote(bundle.sha256) + ' ' + shlex.quote(archive)
        + ' | sha256sum -c - >/dev/null && tar -xzf ' + shlex.quote(archive)
        + ' -C ' + shlex.quote(target) + ' --no-same-owner --no-same-permissions && '
        + shlex.quote(target + '/python/bin/python3')
        + " -I -c 'import json,selectors,ssl,subprocess; print(\"runtime-ready\")'")
    installed = await environment.exec(command, timeout_sec=120)
    if installed.return_code or (installed.stdout or '').strip() != 'runtime-ready':
        raise RuntimeError('Pinned Python runtime did not load')
    wrapped = PythonFallbackEnvironment(environment, target + '/python/bin')
    check = await wrapped.exec("python3 -c 'import json,selectors,subprocess; print(\"backend-ready\")'", timeout_sec=15)
    if check.return_code or (check.stdout or '').strip() != 'backend-ready':
        raise RuntimeError('Task Python cannot support the backend')
    return wrapped, dict(proof, installation='container_private_fallback',
        task_python_preserved=True, network_downloads=0)
