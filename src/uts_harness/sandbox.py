"""Container-bound Deep Agents file and shell backend.

Synchronous tools marshal onto Harbor's event loop. Model-selected paths are
container paths, never host paths; the container remains the isolation boundary."""
import asyncio
import base64
import json
import math
import shlex

from deepagents.backends.sandbox import BaseSandbox
from deepagents.backends.protocol import ExecuteResponse, FileUploadResponse, FileDownloadResponse


class HarborSandbox(BaseSandbox):
    MAX_FILE_BYTES = 1024 * 1024
    MAX_OUTPUT_CHARS = 64000
    supports_execute_offload = False

    def __init__(self, environment, *, identifier, command_timeout=60):
        self.environment = environment
        self._id = identifier
        self.loop = asyncio.get_running_loop()
        self.command_timeout = command_timeout

    @property
    def id(self):
        return self._id

    def _sync(self, factory):
        try:
            active = asyncio.get_running_loop()
        except RuntimeError:
            active = None
        if active is self.loop:
            raise RuntimeError('Use async backend operations on the Harbor event loop')
        if self.loop.is_closed() or not self.loop.is_running():
            raise RuntimeError('Harbor event loop is unavailable')
        return asyncio.run_coroutine_threadsafe(factory(), self.loop).result()

    @staticmethod
    def _path(path):
        if not isinstance(path, str) or not path.startswith('/') or '\x00' in path:
            raise ValueError('Absolute container path required')
        return path

    async def aexecute(self, command, *, timeout=None):
        if not isinstance(command, str) or '\x00' in command:
            raise ValueError('Invalid command')
        seconds = self.command_timeout if timeout is None else timeout
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds <= 0:
            raise ValueError('Positive finite command timeout required')
        # Container-side timeout kills this foreground process group. The
        # Harbor outer timeout is a transport bound, not the process killer.
        # Drain in the container and retain only a bounded prefix. Truncating
        # after Harbor captures stdout would still allow unbounded host RAM.
        argv = ['timeout', '--signal=TERM', '--kill-after=2', f'{seconds}s', 'bash', '-lc', command]
        script = f'''import json,subprocess
p = subprocess.Popen({argv!r}, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
kept = bytearray()
truncated = False
while True:
    chunk = p.stdout.read(8192)
    if not chunk:
        break
    remaining = {self.MAX_OUTPUT_CHARS} - len(kept)
    kept.extend(chunk[:remaining])
    truncated = truncated or len(chunk) > remaining
code = p.wait()
print(json.dumps({{"output": kept.decode("utf-8", errors="replace"), "exit_code": code, "truncated": truncated}}))
'''
        result = await self.environment.exec('python3 -c ' + shlex.quote(script), timeout_sec=seconds + 10)
        if result.return_code != 0:
            raise RuntimeError('Container output-capture helper failed')
        captured = json.loads(result.stdout)
        return ExecuteResponse(**captured)

    def execute(self, command, *, timeout=None):
        return self._sync(lambda: self.aexecute(command, timeout=timeout))

    async def aupload_files(self, files):
        results = []
        for path, content in files:
            self._path(path)
            if not isinstance(content, bytes) or len(content) > self.MAX_FILE_BYTES:
                results.append(FileUploadResponse(path, error='file_size_limit'))
                continue
            # Create as the container's execution user. Docker copy preserves
            # host ownership, which breaks a cap-drop container and leaks host
            # ownership semantics. Bounded chunks also avoid argv size limits.
            error = None
            for offset in range(0, max(1, len(content)), 16384):
                encoded = base64.b64encode(content[offset:offset + 16384]).decode()
                mode = 'wb' if offset == 0 else 'ab'
                code = f'import base64; open({path!r},{mode!r}).write(base64.b64decode({encoded!r}))'
                response = await self.environment.exec('python3 -c ' + shlex.quote(code), timeout_sec=30)
                if response.return_code:
                    error = 'container_write_failed'
                    break
            results.append(FileUploadResponse(path, error=error))
        return results

    def upload_files(self, files):
        return self._sync(lambda: self.aupload_files(files))

    async def adownload_files(self, paths):
        results = []
        for path in paths:
            self._path(path)
            code = (
                'import base64,json; '
                f'f=open({path!r},"rb"); b=f.read({self.MAX_FILE_BYTES + 1}); '
                'print(json.dumps({"data":base64.b64encode(b).decode()}))'
            )
            response = await self.environment.exec('python3 -c ' + shlex.quote(code), timeout_sec=30)
            if response.return_code:
                results.append(FileDownloadResponse(path, error='container_read_failed'))
                continue
            data = base64.b64decode(json.loads(response.stdout)['data'], validate=True)
            results.append(FileDownloadResponse(path, content=data) if len(data) <= self.MAX_FILE_BYTES
                           else FileDownloadResponse(path, error='file_size_limit'))
        return results

    def download_files(self, paths):
        return self._sync(lambda: self.adownload_files(paths))
