"""Opt-in backend revision. Frozen legacy backends remain unchanged."""
import json
import shlex
from contextvars import ContextVar

from deepagents.backends.protocol import ExecuteResponse

from custom_backend import HarborSandbox
from custom_process_capture import capture_script


class ContainerCaptureError(RuntimeError):
    def __init__(self, reason, return_code=None):
        self.reason = reason
        self.return_code = return_code
        # Do not include container stdout or agent commands in public errors.
        super().__init__('Container capture: ' + reason)


class PortableHarborSandbox(HarborSandbox):
    # A filesystem helper emits JSON, not a user-facing shell observation.
    # Truncating that envelope at 64 KB corrupts otherwise valid file reads.
    # The pinned library itself bounds file content at 500 KiB; allow its
    # worst-case JSON escaping, then let its read-window logic paginate text.
    _capture_limit = ContextVar('custom_capture_limit', default=64000)

    async def aread(self, *args, **kwargs):
        token = self._capture_limit.set(4 * 1024**2)
        try:
            return await super().aread(*args, **kwargs)
        finally:
            self._capture_limit.reset(token)

    def read(self, *args, **kwargs):
        return self._sync(lambda: self.aread(*args, **kwargs))

    async def aexecute(self, command, *, timeout=None):
        seconds = self.command_timeout if timeout is None else timeout
        maximum = self._capture_limit.get()
        script = capture_script(command, seconds, maximum)
        result = await self.environment.exec('python3 -c ' + shlex.quote(script), timeout_sec=seconds + 10)
        if result.return_code != 0:
            raise ContainerCaptureError('helper_exit', result.return_code)
        try:
            captured = json.loads(result.stdout)
            if (not isinstance(captured, dict) or set(captured) != {'output', 'exit_code', 'truncated'}
                    or not isinstance(captured['output'], str) or type(captured['exit_code']) is not int
                    or type(captured['truncated']) is not bool
                    or len(captured['output']) > maximum):
                raise ValueError('Invalid helper result')
            return ExecuteResponse(**captured)
        except (ValueError, TypeError, KeyError) as exc:
            raise ContainerCaptureError('invalid_output') from exc
