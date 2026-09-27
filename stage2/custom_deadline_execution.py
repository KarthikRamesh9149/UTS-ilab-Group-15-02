"""C3 execution governed by the official deadline, not command or repair counts.

Only the separately versioned C3 adapter opts in. Existing experiment control,
backend and job defaults remain unchanged. This module grants no paid admission.
"""
import asyncio
import json
import math
import shlex
import uuid

from deepagents.middleware.filesystem import FilesystemMiddleware
from langchain_core.tools import tool

from custom_control import Condition, CompletionControl
from custom_deadline_guidance import finite_seconds
from custom_jobs import ContainerJobs
from custom_portable_backend import PortableHarborSandbox
from custom_runner import CustomRunner

EXECUTION_POLICY_VERSION = 'official-deadline-execution-v1'
LEGACY_REPAIR_NOTICE = ('At most two explicit repair\n'
                        'cycles are available after an incomplete completion attempt.')
DEADLINE_REPAIR_NOTICE = ('You may correct incomplete completion attempts while the official '
    'task time remains. There is no fixed completion-repair count. Commands without '
    'an explicit timeout may use the remaining official task time. Use start_command '
    'and poll_command when you need to keep working while a command runs; '
    'interrupt_command can cancel a command you no longer need. Background handles '
    'have no count quota, but all processes share the task\'s actual CPU and memory. '
    'Finite tool-result and context windows still apply; retrieve large outputs in parts.')


class TaskDeadline:
    """Read the one authoritative monotonic deadline, never renew it."""
    def __init__(self, *, deadline_monotonic, official_timeout_seconds, monotonic):
        self.deadline = finite_seconds(deadline_monotonic)
        self.duration = finite_seconds(official_timeout_seconds, positive=True)
        if not callable(monotonic):
            raise ValueError('Explicit monotonic clock required')
        self.monotonic = monotonic
        self.last_now = None

    def remaining(self):
        now = finite_seconds(self.monotonic())
        if self.last_now is not None and now < self.last_now:
            raise ValueError('Monotonic clock moved backwards')
        if now < self.deadline - self.duration:
            raise ValueError('Deadline exceeds official task allowance')
        self.last_now = now
        value = self.deadline - now
        if value <= 0:
            raise TimeoutError('Official task deadline reached')
        return value

    def command_timeout(self, requested=None):
        # A shorter timeout is an explicit agent choice, not a harness default.
        chosen = None if requested is None else finite_seconds(requested, positive=True)
        left = self.remaining()
        return left if chosen is None else min(left, chosen)


class DeadlineCondition(Condition):
    @property
    def prompt(self):
        parent_prompt = super().prompt
        if parent_prompt.count(LEGACY_REPAIR_NOTICE) != 1:
            raise ValueError('Parent completion contract changed; review the C3 amendment')
        return parent_prompt.replace(LEGACY_REPAIR_NOTICE, DEADLINE_REPAIR_NOTICE).replace(
            'use the remaining repair allowance', 'use the remaining official task time')


class DeadlineCompletionControl(CompletionControl):
    def incomplete(self, reason):
        if self.terminal:
            return {'status': self.outcome, 'terminal': True}
        self.repairs_used += 1
        event = dict(status='repair_requested', reason=reason,
            repair_number=self.repairs_used, terminal=False)
        self.events.append(event)
        return event


class DeadlineHarborSandbox(PortableHarborSandbox):
    def __init__(self, environment, *, identifier, deadline):
        if type(deadline) is not TaskDeadline:
            raise ValueError('Authoritative task deadline required')
        self.deadline = deadline
        super().__init__(environment, identifier=identifier, command_timeout=None)

    async def aexecute(self, command, *, timeout=None):
        # The container-side helper receives only time left on the same task.
        # Harbor's extra transport/cleanup grace is not model execution time.
        return await super().aexecute(command, timeout=self.deadline.command_timeout(timeout))


class DeadlineJobs(ContainerJobs):
    def __init__(self, backend, deadline):
        if type(deadline) is not TaskDeadline:
            raise ValueError('Authoritative task deadline required')
        super().__init__(backend)
        self.deadline = deadline

    async def start(self, command, timeout_seconds=None):
        if not isinstance(command, str) or not command.strip() or '\x00' in command:
            raise ValueError('Nonempty command required')
        timeout = self.deadline.command_timeout(timeout_seconds)
        identifier = uuid.uuid4().hex
        pid_path = '/tmp/uts-command-' + identifier + '.pgid'
        prefix = 'python3 -c ' + shlex.quote('import os; print(os.getpgrp())') + ' > ' + shlex.quote(pid_path)
        task = asyncio.create_task(self.backend.aexecute(prefix + ' && ' + command, timeout=timeout))
        self.jobs[identifier] = (task, pid_path)
        return {'job_id': identifier, 'status': 'started'}


class DeadlineCustomRunner(CustomRunner):
    def __init__(self, model, backend, condition, *, deadline, guidance, defer_job_cleanup=True):
        if type(deadline) is not TaskDeadline:
            raise ValueError('Authoritative task deadline required')
        self.deadline = deadline
        variant = DeadlineCondition(condition.name, condition.parent)
        # The library otherwise rejects explicit execute timeouts above one
        # hour. Use the official allowance instead; the backend clips to time
        # actually remaining. No independent execute ceiling is introduced.
        filesystem = FilesystemMiddleware(backend=backend,
            max_execute_timeout=math.ceil(deadline.duration))
        super().__init__(model, backend, variant, max_model_calls=None,
            defer_job_cleanup=defer_job_cleanup,
            model_middleware=(filesystem, guidance))

    def make_control(self, condition):
        return DeadlineCompletionControl(condition)

    def make_jobs(self, backend):
        return DeadlineJobs(backend, self.deadline)

    def command_tools(self, defaults):
        @tool
        async def start_command(command: str, timeout_seconds: float | None = None) -> str:
            """Start a command until the official deadline, or choose a shorter timeout; poll/interrupt its handle."""
            return json.dumps(await self.jobs.start(command, timeout_seconds))
        return [start_command, *defaults[1:]]

    async def run(self, instruction, *, timeout_seconds):
        if finite_seconds(timeout_seconds, positive=True) != self.deadline.duration:
            raise ValueError('Use the unchanged official task allowance')
        if self.used:
            raise RuntimeError('Create a fresh runner for each trial; replay is prohibited')
        # Graph construction and other host work have already consumed some
        # of the allowance. Never restart a full-duration clock here.
        return await super().run(instruction, timeout_seconds=self.deadline.remaining())


def execution_contract():
    return dict(version=EXECUTION_POLICY_VERSION,
        overall_deadline='official-authoritative-unchanged',
        default_command_timeout='remaining-official-task-time',
        agent_chosen_shorter_timeout=True, completion_repair_count_cap=None,
        background_active_count_cap=None, background_lifetime_count_cap=None,
        model_call_cap=None, no_replay=True, output_and_context_windows='finite-unchanged',
        provider_auth_credit_identity='enforced', container_isolation='unchanged')
