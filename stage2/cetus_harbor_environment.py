"""Development adapter connecting an owned CETUS instance to Harbor's API.

The caller owns instance creation/audit and supplies its async stop callback.
No CLI registration, image builder, scheduler or scored-study launcher yet.
Current transport supports offline, single-container, root-user fixtures only.
"""
import math
from contextlib import nullcontext
from harbor.environments.base import BaseEnvironment, ExecResult
from harbor.environments.capabilities import EnvironmentCapabilities, EnvironmentResourceCapabilities
from harbor.models.task.config import NetworkMode


class CetusAttachedEnvironment(BaseEnvironment):
    def __init__(self, *args, transport, stop_instance, command_timeout=30, detail_observer=None, **kwargs):
        if not callable(stop_instance):
            raise ValueError('Instance owner must supply cleanup')
        if not math.isfinite(command_timeout) or command_timeout <= 0:
            raise ValueError('Positive finite command timeout required')
        self.transport = transport
        self._stop_instance = stop_instance
        self.command_timeout = command_timeout
        self.detail_observer = detail_observer
        self._started = False
        self._start_attempted = False
        self._stop_requested = False
        self._stopped = False
        super().__init__(*args, **kwargs)
        if self._mounts:
            raise NotImplementedError('Host mounts not implemented by attached adapter')
        if any(policy.network_mode != NetworkMode.NO_NETWORK
               for policy in [self.network_policy] + self._phase_network_policies):
            raise NotImplementedError('Current attached adapter is offline-only; no policy substitution')

    @staticmethod
    def type():
        return 'cetus-attached-development'

    @property
    def capabilities(self):
        return EnvironmentCapabilities(disable_internet=True)

    @classmethod
    def resource_capabilities(cls):
        # No false claim that this adapter itself allocates or limits resources.
        return EnvironmentResourceCapabilities()

    def _validate_definition(self):
        if not self.environment_dir.is_dir():
            raise FileNotFoundError(self.environment_dir)

    async def start(self, force_build=False):
        if force_build:
            raise NotImplementedError('Attached adapter cannot rebuild task images')
        if self._start_attempted or self._stop_requested:
            raise RuntimeError('Attached environment is single-use')
        self._start_attempted = True
        # Instance creation and isolation are the caller's responsibility. This
        # command checks liveness only; it is not an isolation attestation.
        result = await self.transport.exec('true', timeout_sec=self.command_timeout)
        if result.return_code:
            raise RuntimeError('Attached instance liveness check failed')
        self._started = True

    async def stop(self, delete=True):
        if not self._stopped:
            self._stop_requested = True
            self._started = False
            await self._stop_instance()
            self._stopped = True

    def _ready(self):
        if not self._started or self._stopped:
            raise RuntimeError('Attached environment is not running')

    async def exec(self, command, cwd=None, env=None, timeout_sec=None, user=None):
        self._ready()
        observation = (self.detail_observer.operation('tool', {'tool_calls': 1})
                       if self.detail_observer else nullcontext())
        with observation:
            result = await self.transport.exec(command, cwd=cwd,
                env=self._merge_env({**self.task_env_config.env, **(env or {})}),
                timeout_sec=self.command_timeout if timeout_sec is None else timeout_sec,
                user=self.default_user if user is None else user)
        converted = ExecResult(return_code=result.return_code,
                          stdout=result.stdout.decode('utf-8', errors='replace'),
                          stderr=result.stderr.decode('utf-8', errors='replace'))
        callback = self._output_callback()
        if callback:
            for text, stream in ((converted.stdout, 'stdout'), (converted.stderr, 'stderr')):
                if text:
                    await callback(text, stream)
        return converted

    async def upload_file(self, source_path, target_path):
        self._ready()
        await self.transport.upload_file(source_path, target_path)

    async def upload_dir(self, source_dir, target_dir):
        self._ready()
        await self.transport.upload_dir(source_dir, target_dir)

    async def download_file(self, source_path, target_path):
        self._ready()
        await self.transport.download_file(source_path, target_path)

    async def download_dir(self, source_dir, target_dir):
        self._ready()
        await self.transport.download_dir(source_dir, target_dir)
