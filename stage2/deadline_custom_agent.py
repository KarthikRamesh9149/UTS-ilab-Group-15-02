"""Offline C3 candidate: deadline-governed execution on a C0/C1/C2 parent.

Not admitted by the existing 0.3 registry. A new source-bound qualification and
development registration are required before any paid execution. Never deploy
this module or its shared-runner changes into the running 0.3 experiment.
"""
from pathlib import Path
import re

from custom_control import Condition
from custom_deadline_guidance import DeadlineGuidance
from custom_deadline_execution import (TaskDeadline, DeadlineHarborSandbox,
    DeadlineCustomRunner, EXECUTION_POLICY_VERSION, execution_contract)
from portable_custom_agent import PortableCustomHarborAgent, runtime_bundle
from retry_policy import SETTINGS
from retry_runtime import Clock, deadline_factory, deadline_for
from deadline_custom_contract import CANDIDATE_VERSION


class DeadlineCustomHarborAgent(PortableCustomHarborAgent):
    @staticmethod
    def name():
        return 'uts-deepagents-deadline'

    def version(self):
        return CANDIDATE_VERSION

    def __init__(self, logs_dir, *, root, trial_id, base_condition, python_bundle,
                 api_base, trial_token, trial_timeout_seconds, completion_wait_seconds):
        if type(base_condition) is not Condition:
            raise ValueError('Explicit unchanged C0/C1/C2 parent required')
        if not isinstance(trial_id, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}', trial_id):
            raise ValueError('Exact trial identity required')
        self.runtime = Path(root) / '.runtime/stage2'
        self.trial_id = trial_id
        self.guidance = None
        self.task_deadline = None
        super().__init__(logs_dir, python_bundle=python_bundle,
            condition=base_condition.name, parent=base_condition.parent,
            api_base=api_base, trial_token=trial_token,
            trial_timeout_seconds=trial_timeout_seconds,
            completion_wait_seconds=completion_wait_seconds)

    def make_runner(self, backend):
        if self.guidance is None or self.task_deadline is None:
            raise RuntimeError('Authoritative task clock must be active')
        return DeadlineCustomRunner(self.model, backend, self.condition,
            deadline=self.task_deadline, guidance=self.guidance, defer_job_cleanup=True)

    def backend(self, environment):
        if self.prepared_environment is None or environment is not self.original_environment:
            raise RuntimeError('Use only the prepared task environment')
        return DeadlineHarborSandbox(self.prepared_environment,
            identifier=self.session_id or 'single-custom-trial', deadline=self.task_deadline)

    def execution_metadata(self):
        return dict(super().execution_metadata(), condition='C3', parent=self.condition.name,
            base_parent=self.condition.parent, design_lever=EXECUTION_POLICY_VERSION,
            execution_contract=execution_contract(),
            deadline_guidance=self.guidance.metadata() if self.guidance is not None else None)

    async def run(self, instruction, environment, context):
        if self.used:
            raise RuntimeError('Custom trial replay is prohibited')
        clock = Clock()
        deadline = deadline_for(self.runtime, self.trial_id, SETTINGS, clock)
        self.task_deadline = TaskDeadline(deadline_monotonic=deadline,
            official_timeout_seconds=self.timeout, monotonic=clock.monotonic)
        self.guidance = DeadlineGuidance(deadline_monotonic=deadline,
            official_timeout_seconds=self.timeout, monotonic=clock.monotonic)
        try:
            return await super().run(instruction, environment, context)
        finally:
            # Metadata only. The private trajectory retains the detailed timing
            # events; neither this context nor those events contain task text.
            if self.runner is not None:
                context.metadata = dict(context.metadata or {}, custom_base_parent=self.condition.parent,
                    custom_design_lever=EXECUTION_POLICY_VERSION,
                    custom_execution_contract=execution_contract(),
                    deadline_guidance_model_requests=len(self.guidance.events))


def agent_factory(root, base_condition, *, base_parent=None):
    """Construct a candidate, not a registration or permission to call a model.

    The successor registration must bind the parent selected from all complete,
    audited C0/C1/C2 results before C3 is run. Synthetic fixtures may exercise
    every possible parent without making a benchmark selection.
    """
    variant = Condition(base_condition, base_parent)
    bundle = runtime_bundle(root)

    def create(*, paths, host_api_base, container_api_base, trial_token,
               agent_timeout_seconds, completion_wait_seconds):
        return DeadlineCustomHarborAgent(paths.agent_dir, root=root,
            trial_id=paths.trial_dir.name, base_condition=variant, python_bundle=bundle,
            api_base=host_api_base, trial_token=trial_token,
            trial_timeout_seconds=agent_timeout_seconds,
            completion_wait_seconds=completion_wait_seconds)

    create.harness = 'C3'
    create.model_protocol_sha256 = SETTINGS.fingerprint()
    wrapped = deadline_factory(create, Path(root), SETTINGS)
    wrapped.custom_parent = variant.name
    wrapped.custom_base_parent = variant.parent
    wrapped.custom_version = CANDIDATE_VERSION
    wrapped.custom_design_lever = EXECUTION_POLICY_VERSION
    wrapped.python_runtime_sha256 = bundle.sha256
    return wrapped
