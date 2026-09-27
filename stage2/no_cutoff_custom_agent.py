"""No-cutoff revision of an older whole parent, without C3's time advice.

Offline assembly only: no registry, source freeze or paid admission is granted.
The parent must later come from the audited four-variant selection, not from
per-task outcomes. The new revision needs its own qualification and fixed20
validation before final89; it cannot inherit the original parent's score.
"""
import math
from pathlib import Path
import re

from deepagents.middleware.filesystem import FilesystemMiddleware

from custom_control import Condition
from custom_deadline_execution import (TaskDeadline, DeadlineCondition,
    DeadlineCustomRunner)
from custom_runner import CustomRunner
from no_cutoff_capture_backend import NoCutoffHarborSandbox
from no_cutoff_custom_contract import (CANDIDATE_VERSION, EXECUTION_POLICY_VERSION,
    execution_contract, revision_name)
from portable_custom_agent import PortableCustomHarborAgent, runtime_bundle
from retry_policy import SETTINGS
from retry_runtime import Clock, deadline_factory, deadline_for


class NoCutoffCustomRunner(DeadlineCustomRunner):
    """Reuse the reviewed execution mechanics, not C3's advisory middleware."""
    def __init__(self, model, backend, condition, *, deadline, defer_job_cleanup=True):
        if type(deadline) is not TaskDeadline or type(condition) is not Condition:
            raise ValueError('Explicit original parent and authoritative deadline required')
        self.deadline = deadline
        variant = DeadlineCondition(condition.name, condition.parent)
        filesystem = FilesystemMiddleware(backend=backend,
            max_execute_timeout=math.ceil(deadline.duration))
        # Deliberately bypass only the C3 constructor that adds time advice.
        # Inherited control/jobs/tools/run still use the same official clock.
        CustomRunner.__init__(self, model, backend, variant, max_model_calls=None,
            defer_job_cleanup=defer_job_cleanup, model_middleware=(filesystem,))


class NoCutoffCustomHarborAgent(PortableCustomHarborAgent):
    @staticmethod
    def name():
        return 'uts-deepagents-parent-no-cutoff'

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
        self.task_deadline = None
        super().__init__(logs_dir, python_bundle=python_bundle,
            condition=base_condition.name, parent=base_condition.parent,
            api_base=api_base, trial_token=trial_token,
            trial_timeout_seconds=trial_timeout_seconds,
            completion_wait_seconds=completion_wait_seconds)

    def make_runner(self, backend):
        if self.task_deadline is None:
            raise RuntimeError('Authoritative task clock must be active')
        return NoCutoffCustomRunner(self.model, backend, self.condition,
            deadline=self.task_deadline, defer_job_cleanup=True)

    def backend(self, environment):
        if self.prepared_environment is None or environment is not self.original_environment:
            raise RuntimeError('Use only the prepared task environment')
        return NoCutoffHarborSandbox(self.prepared_environment,
            identifier=self.session_id or 'single-custom-trial', deadline=self.task_deadline)

    def execution_metadata(self):
        return dict(super().execution_metadata(), condition=revision_name(self.condition.name),
            parent=self.condition.name, base_parent=self.condition.parent,
            design_lever=EXECUTION_POLICY_VERSION, execution_contract=execution_contract())

    async def run(self, instruction, environment, context):
        if self.used:
            raise RuntimeError('Custom trial replay is prohibited')
        clock = Clock()
        deadline = deadline_for(self.runtime, self.trial_id, SETTINGS, clock)
        self.task_deadline = TaskDeadline(deadline_monotonic=deadline,
            official_timeout_seconds=self.timeout, monotonic=clock.monotonic)
        try:
            return await super().run(instruction, environment, context)
        finally:
            if self.runner is not None:
                context.metadata = dict(context.metadata or {}, custom_base_parent=self.condition.parent,
                    custom_design_lever=EXECUTION_POLICY_VERSION,
                    custom_execution_contract=execution_contract())


def agent_factory(root, base_condition, *, base_parent=None):
    """Construct an unadmitted revision; do not choose a finalist or launch."""
    variant = Condition(base_condition, base_parent)
    bundle = runtime_bundle(root)

    def create(*, paths, host_api_base, container_api_base, trial_token,
               agent_timeout_seconds, completion_wait_seconds):
        return NoCutoffCustomHarborAgent(paths.agent_dir, root=root,
            trial_id=paths.trial_dir.name, base_condition=variant, python_bundle=bundle,
            api_base=host_api_base, trial_token=trial_token,
            trial_timeout_seconds=agent_timeout_seconds,
            completion_wait_seconds=completion_wait_seconds)

    create.harness = revision_name(variant.name)
    create.model_protocol_sha256 = SETTINGS.fingerprint()
    wrapped = deadline_factory(create, Path(root), SETTINGS)
    wrapped.custom_parent = variant.name
    wrapped.custom_base_parent = variant.parent
    wrapped.custom_version = CANDIDATE_VERSION
    wrapped.custom_design_lever = EXECUTION_POLICY_VERSION
    wrapped.python_runtime_sha256 = bundle.sha256
    return wrapped
