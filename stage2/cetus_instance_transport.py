"""Command/file-transfer primitives for an existing PBS Apptainer instance.

Development component, not a qualified Harbor environment or scored runner.
Does not create instances, change networking, build images, or request resources.
Requires Python 3.12 (the Harbor controller environment), including on CETUS.
"""
import asyncio
from dataclasses import dataclass
import math
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import signal

MAX_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class CommandResult:
    return_code: int
    stdout: bytes
    stderr: bytes


async def run_process(argv, *, input_data=b'', timeout=30, max_bytes=MAX_BYTES):
    """Bounded pipes; terminate the local exec process group on failure/cancel.

    This is not proof of in-container descendant cleanup. The instance owner
    must stop the instance after an interrupted command before reusing it.
    """
    if not math.isfinite(timeout) or timeout <= 0 or max_bytes < 1:
        raise ValueError('Positive finite timeout and output limit required')
    # Do not forward API keys, APPTAINER_BIND*, or shell startup overrides.
    env = {key: os.environ[key] for key in
           ('PATH', 'HOME', 'LANG', 'TMPDIR', 'APPTAINER_CACHEDIR', 'APPTAINER_TMPDIR')
           if key in os.environ}
    proc = await asyncio.create_subprocess_exec(
        *argv, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, env=env, start_new_session=True)

    async def read(stream):
        chunks, size = [], 0
        while True:
            chunk = await stream.read(65536)
            if not chunk:
                return b''.join(chunks)
            size += len(chunk)
            if size > max_bytes:
                raise ValueError('Command output exceeded transfer bound')
            chunks.append(chunk)

    async def write():
        try:
            proc.stdin.write(input_data)
            await proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            proc.stdin.close()

    tasks = [asyncio.create_task(read(proc.stdout)), asyncio.create_task(read(proc.stderr)),
             asyncio.create_task(write()), asyncio.create_task(proc.wait())]
    try:
        async with asyncio.timeout(timeout):
            stdout, stderr, _, code = await asyncio.gather(*tasks)
        return CommandResult(code, stdout, stderr)
    except BaseException:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        # Drain already-buffered pipes after killing the group so pipe flow
        # control cannot leave Process.wait() blocked during error cleanup.
        await asyncio.wait_for(proc.communicate(), timeout=5)
        raise


def container_path(value):
    if not isinstance(value, str) or '\x00' in value:
        raise ValueError('Container path must be text without NUL')
    path = PurePosixPath(value)
    if not path.is_absolute() or '..' in path.parts or str(path) == '/':
        raise ValueError('Absolute non-root container path required')
    return str(path)


READ_FILE = '''import os, stat, sys
fd = os.open(sys.argv[1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
with os.fdopen(fd, 'rb') as handle:
    assert stat.S_ISREG(os.fstat(handle.fileno()).st_mode), 'regular files only'
    data = handle.read(int(sys.argv[2]) + 1)
    assert len(data) <= int(sys.argv[2]), 'file too large'
    sys.stdout.buffer.write(data)
'''

WRITE_FILE = '''import os, sys, tempfile
from pathlib import Path
target = Path(sys.argv[1])
data = sys.stdin.buffer.read(int(sys.argv[2]) + 1)
assert len(data) <= int(sys.argv[2]), 'file too large'
target.parent.mkdir(parents=True, exist_ok=True)
fd, temporary = tempfile.mkstemp(prefix='.uts-transfer-', dir=str(target.parent))
try:
    with os.fdopen(fd, 'wb') as handle:
        handle.write(data)
    os.replace(temporary, str(target))
finally:
    if os.path.exists(temporary): os.unlink(temporary)
'''


class InstanceTransport:
    """Only executes inside an explicitly named instance from the current PBS job."""
    def __init__(self, instance, *, runner=run_process):
        job = os.environ.get('PBS_JOBID', '')
        if not re.fullmatch(r'[0-9]+\.[A-Za-z0-9.-]+', job):
            raise RuntimeError('CETUS transport requires a PBS allocation')
        if not re.fullmatch(r'uts-(?:caps|offline|harbor)-' + re.escape(job.split('.')[0]) +
                            r'(?:-[a-z0-9]+)*', instance):
            raise ValueError('Instance must belong to the current named PBS job')
        self.instance, self.runner = instance, runner
        self.interrupted = False

    async def _call(self, args, *, data=b'', timeout=30):
        if self.interrupted:
            raise RuntimeError('Interrupted instance requires owner cleanup; transport is unusable')
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('Positive finite timeout required')
        argv = ['apptainer', 'exec', '--cleanenv', 'instance://' + self.instance] + args
        try:
            return await self.runner(argv, input_data=data, timeout=timeout, max_bytes=MAX_BYTES)
        except BaseException:
            self.interrupted = True
            raise

    async def exec(self, command, *, cwd=None, env=None, timeout_sec=30, user=None):
        if user not in (None, 0, '0', 'root'):
            raise NotImplementedError('Non-root container user switching not implemented')
        if not isinstance(command, str) or '\x00' in command:
            raise ValueError('Command must be text without NUL')
        assignments = []
        for key, value in (env or {}).items():
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key) or not isinstance(value, str) or '\x00' in value:
                raise ValueError('Invalid explicit container environment')
            assignments.append(key + '=' + value)
        script = ('cd -- ' + shlex.quote(container_path(cwd)) + ' && ' if cwd and cwd != '/' else
                  'cd / && ' if cwd == '/' else '') + command
        return await self._call(['env', '--'] + assignments + ['bash', '--noprofile', '--norc', '-c', script],
                                timeout=timeout_sec)

    async def upload_file(self, source_path, target_path):
        source = Path(source_path)
        if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_BYTES:
            raise ValueError('Upload requires a bounded regular controller file')
        with source.open('rb') as handle:
            data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError('Upload grew beyond transfer bound')
        result = await self._call(['python3', '-c', WRITE_FILE, container_path(target_path), str(MAX_BYTES)], data=data)
        if result.return_code:
            raise RuntimeError('Container upload failed: exit ' + str(result.return_code))

    async def download_file(self, source_path, target_path):
        target = Path(target_path)
        # Refuse overwrite of controller data, including a symlink. Directories
        # must be selected by the trusted caller, never by container output.
        if not target.parent.is_dir() or target.exists() or target.is_symlink():
            raise ValueError('Download requires a fresh target in an existing controller directory')
        result = await self._call(['python3', '-c', READ_FILE, container_path(source_path), str(MAX_BYTES)])
        if result.return_code:
            raise RuntimeError('Container download failed: exit ' + str(result.return_code))
        if len(result.stdout) > MAX_BYTES:
            raise ValueError('Downloaded file exceeds transfer bound')
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(result.stdout)
