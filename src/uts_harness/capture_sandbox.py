"""Encoded command-helper transport using the official task deadline."""
import base64
import json
import shlex

from deepagents.backends.protocol import ExecuteResponse

from .deadlines import DeadlineHarborSandbox
from .portable_sandbox import ContainerCaptureError
from .process_capture import capture_script


def encoded_capture_script(command, seconds, maximum):
    # Keep the established capture/timeout/drain implementation byte-for-byte.
    # Encoding prevents a service-name search from matching literal command
    # text carried by the helper's own process arguments.
    source = capture_script(command, seconds, maximum)
    encoded = base64.b64encode(source.encode()).decode('ascii')
    return "import base64;exec(compile(base64.b64decode(" + repr(encoded) + "),'<uts-capture>','exec'))"


class NoCutoffHarborSandbox(DeadlineHarborSandbox):
    async def aexecute(self, command, *, timeout=None):
        seconds = self.deadline.command_timeout(timeout)
        maximum = self._capture_limit.get()
        script = encoded_capture_script(command, seconds, maximum)
        result = await self.environment.exec('python3 -c ' + shlex.quote(script), timeout_sec=seconds + 10)
        if result.return_code != 0:
            raise ContainerCaptureError('helper_exit', result.return_code)
        try:
            captured = json.loads(result.stdout)
            if (not isinstance(captured, dict) or set(captured) != {'output', 'exit_code', 'truncated'}
                    or not isinstance(captured['output'], str) or type(captured['exit_code']) is not int
                    or type(captured['truncated']) is not bool or len(captured['output']) > maximum):
                raise ValueError('Invalid helper result')
            return ExecuteResponse(**captured)
        except (ValueError, TypeError, KeyError) as exc:
            raise ContainerCaptureError('invalid_output') from exc
