"""Custom Harbor adapter for the corrected baseline model/deadline protocol.

This is a separately versioned candidate, not a registered paid experiment.
The caller must qualify the native runtime and register the fixed development
split and permitted spending policy before calling the scored orchestrator.
No task solutions, verifier internals, budget ledger or provider key enter
this adapter. The trusted orchestrator still owns revocation and teardown.
"""
from pathlib import Path

from harbor.agents.base import BaseAgent
from langchain_core.messages import messages_to_dict
from langsmith.run_helpers import tracing_context

from completion_wait import validate_completion_wait
from custom_backend import HarborSandbox
from custom_control import Condition
from custom_model import gateway_model
from custom_runner import CustomRunner
from gateway_policy import MODEL
from retry_policy import SETTINGS
from retry_runtime import deadline_factory
from scored_gateway import durable_json


class CorrectedCustomHarborAgent(BaseAgent):
    @staticmethod
    def name():
        return 'uts-deepagents-corrected'

    def version(self):
        return 'stage2-candidate-0.2.0'

    def __init__(self, logs_dir, *, condition, api_base, trial_token,
                 trial_timeout_seconds, completion_wait_seconds, parent=None):
        variant = Condition(condition, parent)
        trial_timeout_seconds = validate_completion_wait(trial_timeout_seconds)
        completion_wait_seconds = validate_completion_wait(completion_wait_seconds)
        super().__init__(logs_dir=Path(logs_dir), model_name=MODEL)
        self.condition = variant
        # No configurable model/settings/call-count overrides: every variant
        # gets precisely the corrected baselines' protocol. Routing, physical
        # request retries and credit/auth decisions remain in the gateway.
        self.model = gateway_model(api_base, trial_token,
            max_output_tokens=SETTINGS.max_output_tokens,
            temperature=SETTINGS.temperature, top_p=1.,
            reasoning_effort=SETTINGS.reasoning_effort,
            completion_wait_seconds=completion_wait_seconds)
        self.timeout = trial_timeout_seconds
        self.used = False
        self.runner = None

    def execution_metadata(self):
        return dict(version=self.version(), condition=self.condition.name,
            parent=self.condition.parent, model_protocol_sha256=SETTINGS.fingerprint(),
            max_model_calls=None, official_agent_timeout_seconds=self.timeout,
            billing_source='passive_gateway_physical_request_evidence',
            benchmark_success=None)

    async def setup(self, environment):
        check = await environment.exec(
            'command -v python3 && command -v bash && command -v timeout', timeout_sec=15)
        if check.return_code != 0:
            raise RuntimeError('Task image lacks required Python 3, bash or timeout executable')

    async def run(self, instruction, environment, context):
        if self.used:
            raise RuntimeError('Custom trial replay is prohibited')
        self.used = True
        self.logs_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        durable_json(self.logs_dir / 'custom-started.json', self.execution_metadata())
        backend = HarborSandbox(environment, identifier=self.session_id or 'single-custom-trial')
        self.runner = CustomRunner(self.model, backend, self.condition,
            max_model_calls=None, defer_job_cleanup=True)
        outcome = None
        error_type = None
        try:
            # Avoid accidental export through unrelated LangSmith credentials.
            # The scored orchestrator's metadata-only tracing is separate.
            with tracing_context(enabled=False):
                outcome = await self.runner.run(instruction, timeout_seconds=self.timeout)
        except BaseException as exc:
            error_type = type(exc).__name__
            raise
        finally:
            state = self.runner.state or {}
            metadata = dict(self.execution_metadata(), outcome=outcome,
                error_type=error_type, model_attempts=self.runner.model_limit.attempts,
                graph_recursion_safety_bound=self.runner.graph_recursion_limit)
            # Raw observations are private; only the separate metrics exporter
            # may produce curated public artifacts. Never serialize clients.
            durable_json(self.logs_dir / 'custom-trajectory.json', dict(metadata,
                messages=messages_to_dict(state.get('messages', [])),
                control_events=self.runner.control.events))
            context.metadata = dict(context.metadata or {},
                custom_condition=self.condition.name, custom_parent=self.condition.parent,
                custom_version=self.version(), custom_outcome=outcome,
                custom_error_type=error_type, model_attempts=self.runner.model_limit.attempts,
                model_protocol_sha256=SETTINGS.fingerprint(), max_model_calls=None,
                billing_source=metadata['billing_source'], benchmark_success=None)

    async def cleanup_after_verification(self):
        """Leave task services available to the verifier, then stop owned jobs."""
        if self.runner is not None:
            await self.runner.jobs.close()


def agent_factory(root, condition, *, parent=None):
    """Same clock activation wrapper used by the corrected native baselines.

    This factory is not admission or a paid-run entry point. The registered
    matrix must enforce task membership, source bindings and one attempt.
    """
    variant = Condition(condition, parent)

    def create(*, paths, host_api_base, container_api_base, trial_token,
               agent_timeout_seconds, completion_wait_seconds):
        # Host-run Deep Agents uses only the pinned loopback bridge. The
        # container URL is supplied for native installed harnesses, not used.
        return CorrectedCustomHarborAgent(paths.agent_dir,
            condition=variant.name, parent=variant.parent,
            api_base=host_api_base, trial_token=trial_token,
            trial_timeout_seconds=agent_timeout_seconds,
            completion_wait_seconds=completion_wait_seconds)

    create.harness = variant.name
    create.model_protocol_sha256 = SETTINGS.fingerprint()
    return deadline_factory(create, Path(root), SETTINGS)
