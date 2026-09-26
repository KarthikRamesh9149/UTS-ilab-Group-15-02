"""Offline 0.3 candidate; not admitted by the frozen 0.2 study registry."""
from pathlib import Path
import traceback

from corrected_custom_agent import CorrectedCustomHarborAgent
from custom_portable_backend import ContainerCaptureError, PortableHarborSandbox
from custom_python_runtime import PythonBundle, prepare_python


class PortableCustomHarborAgent(CorrectedCustomHarborAgent):
    def version(self):
        return 'stage2-candidate-0.3.0'

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
