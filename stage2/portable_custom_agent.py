"""Portable 0.3 candidate; admitted only by its separate qualified registry."""
from pathlib import Path
import traceback

from corrected_custom_agent import CorrectedCustomHarborAgent
from custom_portable_backend import ContainerCaptureError, PortableHarborSandbox
from custom_python_runtime import PythonBundle, prepare_python
from custom_control import Condition
from portable_custom_policy import CANDIDATE_VERSION, PYTHON_SHA256, SETTINGS
from retry_runtime import deadline_factory


def runtime_bundle(root):
    return PythonBundle(Path(root) / '.runtime/stage2/python-runtime.tar.gz', PYTHON_SHA256)


class PortableCustomHarborAgent(CorrectedCustomHarborAgent):
    def version(self):
        return CANDIDATE_VERSION

    def __init__(self, logs_dir, *, python_bundle, **kwargs):
        if not isinstance(python_bundle, PythonBundle):
            raise ValueError('Explicit pinned Python runtime required')
        self.python_bundle = python_bundle
        self.prepared_environment = None
        self.original_environment = None
        self.runtime_proof = None
        super().__init__(logs_dir, **kwargs)

    def client_options(self):
        return dict(text_only_transport=True)

    async def setup(self, environment):
        if self.prepared_environment is not None:
            raise RuntimeError('Runtime setup replay is prohibited')
        self.prepared_environment, self.runtime_proof = await prepare_python(environment, self.python_bundle)
        self.original_environment = environment

    def backend(self, environment):
        if self.prepared_environment is None or environment is not self.original_environment:
            raise RuntimeError('Use only the prepared task environment')
        return PortableHarborSandbox(self.prepared_environment,
            identifier=self.session_id or 'single-custom-trial')

    def execution_metadata(self):
        return dict(super().execution_metadata(), text_only_transport=True,
            python_runtime=self.runtime_proof)

    def failure_metadata(self, exc):
        # Stack locations, not source lines, exception text, locals or task
        # observations. Enough to locate a transport/backend failure safely.
        result = dict(error_type=type(exc).__name__, frames=[dict(
            file=Path(frame.filename).name, function=frame.name, line=frame.lineno)
            for frame in traceback.extract_tb(exc.__traceback__)[-8:]])
        if isinstance(exc, ContainerCaptureError):
            result.update(component='container_capture', reason=exc.reason,
                return_code=exc.return_code)
        return result


def agent_factory(root, condition, *, parent=None):
    variant = Condition(condition, parent)
    bundle = runtime_bundle(root)

    def create(*, paths, host_api_base, container_api_base, trial_token,
               agent_timeout_seconds, completion_wait_seconds):
        return PortableCustomHarborAgent(paths.agent_dir, python_bundle=bundle,
            condition=variant.name, parent=variant.parent, api_base=host_api_base,
            trial_token=trial_token, trial_timeout_seconds=agent_timeout_seconds,
            completion_wait_seconds=completion_wait_seconds)

    create.harness = variant.name
    create.model_protocol_sha256 = SETTINGS.fingerprint()
    wrapped = deadline_factory(create, Path(root), SETTINGS)
    wrapped.custom_parent = variant.parent
    wrapped.custom_version = CANDIDATE_VERSION
    wrapped.python_runtime_sha256 = bundle.sha256
    return wrapped
