"""C0-NC execution mechanics with one explicitly pinned Gemini model."""
import math
import time
from pathlib import Path
from deepagents.middleware.filesystem import FilesystemMiddleware
from harbor.agents.base import BaseAgent
from langchain_core.messages import messages_to_dict
from langsmith.run_helpers import tracing_context
from custom_control import Condition
from custom_deadline_execution import TaskDeadline, DeadlineCondition, DeadlineCustomRunner
from custom_python_runtime import prepare_python
from custom_runner import CustomRunner
from custom_text_transport import TextGatewayChatOpenAI, TEXT_PROFILE
from no_cutoff_capture_backend import NoCutoffHarborSandbox
from scored_gateway import durable_json
from gemini_laptop_policy import MODEL, MAX_OUTPUT, VERSION


class GeminiRunner(DeadlineCustomRunner):
    def __init__(self, model, backend, deadline):
        self.deadline = deadline
        filesystem = FilesystemMiddleware(backend=backend,
            max_execute_timeout=math.ceil(deadline.duration))
        CustomRunner.__init__(self, model, backend, DeadlineCondition('C0', None),
            max_model_calls=None, defer_job_cleanup=True,
            model_middleware=(filesystem,), model_name=MODEL)


class GeminiAgent(BaseAgent):
    @staticmethod
    def name():
        return 'uts-c0-nc-gemini-laptop'

    def version(self):
        return VERSION

    def __init__(self, logs_dir, gateway, bundle, timeout, callbacks=None):
        super().__init__(logs_dir=Path(logs_dir), model_name=MODEL)
        self.gateway, self.bundle, self.timeout = gateway, bundle, timeout
        self.model = TextGatewayChatOpenAI(model=MODEL, api_key=gateway.token,
            base_url=gateway.url, temperature=1.0, top_p=1.0,
            max_tokens=MAX_OUTPUT, max_retries=0, timeout=timeout,
            streaming=False, use_responses_api=False, profile=TEXT_PROFILE,
            extra_body={'reasoning': {'effort': 'high'}})
        self.runner = None
        self.used = False
        self.callbacks = callbacks

    async def setup(self, environment):
        self.prepared, self.runtime_proof = await prepare_python(environment, self.bundle)

    async def run(self, instruction, environment, context):
        if self.used:
            raise RuntimeError('No replay permitted')
        self.used = True
        deadline = TaskDeadline(deadline_monotonic=time.monotonic() + self.timeout,
            official_timeout_seconds=self.timeout, monotonic=time.monotonic)
        self.gateway.activate(self.logs_dir.parent.name, deadline.deadline)
        backend = NoCutoffHarborSandbox(self.prepared, identifier=self.logs_dir.parent.name,
            deadline=deadline)
        self.runner = GeminiRunner(self.model, backend, deadline)
        if self.callbacks:
            self.runner.graph = self.runner.graph.with_config({'callbacks':[self.callbacks]})
        outcome = None
        try:
            with tracing_context(enabled=False):
                outcome = await self.runner.run(instruction, timeout_seconds=self.timeout)
        finally:
            self.logs_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            durable_json(self.logs_dir / 'private-trajectory.json', {
                'messages': messages_to_dict((self.runner.state or {}).get('messages', [])),
                'control_events': self.runner.control.events})
            context.metadata = dict(model_attempts=self.runner.model_limit.attempts,
                version=VERSION, outcome=outcome)

    async def cleanup_after_verification(self):
        if self.runner is not None:
            await self.runner.jobs.close()
