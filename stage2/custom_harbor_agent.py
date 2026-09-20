"""Harbor lifecycle adapter for the candidate Deep Agents controller.

No task identity, reference solution or verifier is accepted by this adapter.
The trusted trial runner owns environment destruction and model revocation.
"""
import math
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
from scored_gateway import durable_json


class CustomHarborAgent(BaseAgent):
    @staticmethod
    def name():
        return 'uts-deepagents'

    def version(self):
        return 'stage2-candidate-0.1.0'

    def __init__(self, logs_dir, *, condition, parent=None, api_base, trial_token,
                 max_output_tokens, max_model_calls, trial_timeout_seconds, completion_wait_seconds,
                 model_name=MODEL, temperature=None, reasoning_effort=None, **kwargs):
        if model_name != MODEL:
            raise ValueError('Pinned model required')
        if isinstance(trial_timeout_seconds, bool) or not isinstance(trial_timeout_seconds, (int, float)) or not math.isfinite(trial_timeout_seconds) or trial_timeout_seconds <= 0:
            raise ValueError('Official positive task timeout required')
        if type(max_model_calls) is not int or max_model_calls <= 0:
            raise ValueError('Explicit shared model-call limit required')
        completion_wait_seconds = validate_completion_wait(completion_wait_seconds)
        super().__init__(logs_dir=Path(logs_dir), model_name=model_name, **kwargs)
        self.condition = Condition(condition, parent)
        self.model = gateway_model(api_base, trial_token, max_output_tokens=max_output_tokens,
                                   temperature=temperature, reasoning_effort=reasoning_effort,
                                   completion_wait_seconds=completion_wait_seconds)
        self.max_model_calls = max_model_calls
        self.timeout = trial_timeout_seconds
        self.used = False
        self.runner = None

    async def setup(self, environment):
        check = await environment.exec('command -v python && command -v bash && command -v timeout', timeout_sec=15)
        if check.return_code != 0:
            raise RuntimeError('Task image lacks required Python, bash or timeout executable')

    async def run(self, instruction, environment, context):
        if self.used:
            raise RuntimeError('Custom trial replay is prohibited')
        self.used = True
        self.logs_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        marker = self.logs_dir / 'custom-started.json'
        durable_json(marker, {'condition': self.condition.name, 'parent': self.condition.parent,
                             'version': self.version(), 'benchmark_success': None})
        backend = HarborSandbox(environment, identifier=self.session_id or 'single-custom-trial')
        # Task services may need to remain alive for the verifier. Revoke model
        # access at agent completion, but clean up commands after verification.
        runner = CustomRunner(self.model, backend, self.condition,
            max_model_calls=self.max_model_calls, defer_job_cleanup=True)
        self.runner = runner
        outcome = None
        error_type = None
        try:
            # Do not inherit an unrelated project's LangSmith export settings.
            # Local evidence remains authoritative; approved Langfuse wiring is
            # a separate explicit integration, not a vendor-default fallback.
            with tracing_context(enabled=False):
                outcome = await runner.run(instruction, timeout_seconds=self.timeout)
        except BaseException as exc:
            error_type = type(exc).__name__
            raise
        finally:
            # Explicit message-only serialization excludes client configuration,
            # API credentials and graph objects. Raw task observations stay local.
            state = runner.state or {}
            durable_json(self.logs_dir / 'custom-trajectory.json', {
                'messages': messages_to_dict(state.get('messages', [])),
                'condition': self.condition.name, 'parent': self.condition.parent,
                'outcome': outcome, 'error_type': error_type,
                'model_attempts': runner.model_limit.attempts,
                'control_events': runner.control.events, 'benchmark_success': None})
            context.metadata = dict(context.metadata or {}, custom_condition=self.condition.name,
                custom_parent=self.condition.parent, custom_outcome=outcome,
                custom_error_type=error_type, model_attempts=runner.model_limit.attempts,
                billing_source='authoritative_gateway_ledger', benchmark_success=None)

    async def cleanup_after_verification(self):
        """Required in the orchestrator's finally block, before container teardown.

        The container must still be destroyed if command cleanup raises.
        """
        if self.runner is not None:
            await self.runner.jobs.close()
