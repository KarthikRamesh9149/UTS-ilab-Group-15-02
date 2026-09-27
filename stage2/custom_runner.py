"""Candidate Deep Agents trial controller. No paid-run defaults or score claims."""
import asyncio
import json
import math
import sys

from deepagents import create_deep_agent, register_harness_profile, HarnessProfile, GeneralPurposeSubagentProfile
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from custom_control import Condition, CompletionControl
from custom_jobs import ContainerJobs
from gateway_policy import MODEL


class ModelLimitReached(RuntimeError):
    pass


class TrialModelLimit(AgentMiddleware):
    """Count across graph reinvocations; None explicitly means no call cap."""
    def __init__(self, limit):
        if limit is not None and (type(limit) is not int or limit <= 0):
            raise ValueError('Positive model call limit or explicit None required')
        self.limit = limit
        self.attempts = 0

    def before_model(self, state, runtime):
        if self.limit is not None and self.attempts >= self.limit:
            raise ModelLimitReached('Per-trial model-call limit reached')
        self.attempts += 1

    async def abefore_model(self, state, runtime):
        return self.before_model(state, runtime)


class CustomRunner:
    def __init__(self, model, backend, condition: Condition, *, max_model_calls,
                 defer_job_cleanup=False, model_middleware=()):
        if getattr(model, 'model_name', None) != MODEL:
            raise ValueError('Explicit pinned model required')
        if max_model_calls is not None and (type(max_model_calls) is not int or max_model_calls <= 0):
            raise ValueError('Positive model call limit or explicit None required')
        if not isinstance(model_middleware, tuple) or any(
                not isinstance(item, AgentMiddleware) for item in model_middleware):
            raise ValueError('Explicit tuple of model middleware required')
        # Preserve the historical capped runner exactly. The separately
        # versioned corrected adapter explicitly selects None and still has
        # the official wall-clock deadline. LangGraph requires a positive
        # integer; sys.maxsize is an unreachable recursion safety bound, not
        # a task allowance or another hidden 100-call limit.
        self.graph_recursion_limit = sys.maxsize if max_model_calls is None else 10000
        self.control = self.make_control(condition)
        if type(defer_job_cleanup) is not bool:
            raise ValueError('Explicit cleanup lifecycle required')
        self.defer_job_cleanup = defer_job_cleanup
        self.jobs = self.make_jobs(backend)
        self.used = False
        self.state = None

        @tool(return_direct=True)
        def complete_task(summary: str, checks: list[dict] | None = None, no_edit_reason: str = '') -> str:
            """Report completion with observed requirement checks, not a verifier score."""
            return json.dumps(self.control.complete(summary, checks, no_edit_reason))

        @tool(return_direct=True)
        def abandon_task(reason: str) -> str:
            """Finish honestly when the task cannot be completed."""
            return json.dumps(self.control.abandon(reason))

        @tool
        async def start_command(command: str, timeout_seconds: int = 60) -> str:
            """Start a container command and receive a per-trial handle to poll or interrupt."""
            return json.dumps(await self.jobs.start(command, timeout_seconds))

        @tool
        def poll_command(job_id: str) -> str:
            """Read a known command handle's state and bounded output after it finishes."""
            return json.dumps(self.jobs.poll(job_id))

        @tool
        async def interrupt_command(job_id: str) -> str:
            """Stop the process group of a known command inside this trial's container."""
            return json.dumps(await self.jobs.interrupt(job_id))

        register_harness_profile('openai:' + MODEL, HarnessProfile(
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
            excluded_tools=frozenset({'write_todos'}),
            excluded_middleware=frozenset({'SummarizationMiddleware'})))
        self.model_limit = TrialModelLimit(max_model_calls)
        self.graph = create_deep_agent(model=model, backend=backend, system_prompt=condition.prompt,
            tools=[complete_task, abandon_task,
                   *self.command_tools([start_command, poll_command, interrupt_command])],
            middleware=[self.model_limit, *model_middleware],
            subagents=[], memory=None, skills=None, store=None, checkpointer=None)

    def make_control(self, condition):
        return CompletionControl(condition)

    def make_jobs(self, backend):
        return ContainerJobs(backend)

    def command_tools(self, defaults):
        return defaults

    async def run(self, instruction, *, timeout_seconds):
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError('Explicit positive trial timeout required')
        if self.used:
            raise RuntimeError('Create a fresh runner for each trial; replay is prohibited')
        self.used = True
        self.state = {'messages': [HumanMessage(content=instruction)]}
        try:
            async with asyncio.timeout(timeout_seconds):
                while not self.control.terminal:
                    events_before = len(self.control.events)
                    # Keep each committed graph state so a later timeout or
                    # provider error does not erase earlier tool observations.
                    # This streams graph states, not provider token responses.
                    async for snapshot in self.graph.astream(self.state,
                            config={'recursion_limit': self.graph_recursion_limit}, stream_mode='values'):
                        self.state = snapshot
                    if self.control.terminal:
                        break
                    if len(self.control.events) == events_before:
                        feedback = self.control.incomplete('The model ended without complete_task or abandon_task.')
                    else:
                        feedback = self.control.events[-1]
                    if not self.control.terminal:
                        self.state['messages'].append(HumanMessage(content=json.dumps(feedback)))
            return {'outcome': self.control.outcome, 'repair_cycles': self.control.repairs_used,
                    'events': self.control.events, 'benchmark_success': None}
        finally:
            # Caller must destroy the trial container even if cleanup fails.
            primary = sys.exception()
            try:
                if not self.defer_job_cleanup:
                    await self.jobs.close()
            except Exception as cleanup_error:
                if primary is None:
                    raise
                primary.add_note('Container job cleanup also failed: ' + type(cleanup_error).__name__)
