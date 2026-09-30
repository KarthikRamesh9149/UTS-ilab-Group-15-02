"""Retain allowlisted setup observations inside the real scored result.

This object has no admission authority. Only the admitted host route supplies
its fixed callback to the unchanged lifecycle. It never retries preparation.
"""
import asyncio
from copy import deepcopy
import os
import threading

import no_cutoff_recovery_setup as setup

KIND = 'retained_recovery_preparation_not_admission'
ISSUES = frozenset({'metadata_unavailable', 'late_metadata_unavailable'})


def empty_agent_context(value):
    # The unchanged shared lifecycle always serialises an empty AgentContext,
    # even when preparation prevents setup/run. Presence alone is not execution.
    return value is None or (type(value) is dict and set(value) == {
        'n_input_tokens', 'n_cache_tokens', 'n_output_tokens', 'cost_usd', 'metadata'}
        and all(item is None for item in value.values()))


class RetainedPreparation:
    def __init__(self):
        self._pid = os.getpid(); self._thread = threading.get_ident()
        self._parent = asyncio.current_task()
        if self._parent is None or threading.current_thread() is not threading.main_thread():
            raise ValueError('Recovery result retention requires its main-thread scored task')
        self._observer = setup.PreparationObservation()
        self._used = False; self._done = False; self._finished = None
        self._captured = None; self._issues = set()

    def __reduce_ex__(self, protocol):
        raise TypeError('Recovery result handles cannot be copied or saved')

    def _owner(self):
        if (self._pid != os.getpid() or self._thread != threading.get_ident()
                or threading.current_thread() is not threading.main_thread()):
            raise ValueError('Recovery result handle owner changed')

    def _capture(self, *, late=False):
        try:
            current = setup.validate(self._observer.metadata())
            if self._captured is not None and current != self._captured:
                # A latched source/capture issue can make later metadata less
                # complete. Keep that newer actual observation, never repair it.
                self._issues.add('late_metadata_unavailable')
            self._captured = current
        except BaseException:
            # A diagnostic read cannot replace an already executed outcome or
            # mask its exception/cancellation. Earlier allowlisted data survives.
            self._issues.add('late_metadata_unavailable' if late else 'metadata_unavailable')

    async def prepare(self, environment):
        self._owner()
        if self._used or self._finished is not None:
            raise ValueError('Recovery preparation cannot be replayed')
        self._used = True
        try:
            return await self._observer.prepare(environment)
        finally:
            self._done = True
            self._capture()

    def finish(self):
        """Called before durable result.json, including failure/cancellation."""
        self._owner()
        if asyncio.current_task() is not self._parent:
            raise ValueError('Only the owning scored task may retain its observation')
        if self._finished is not None:
            return deepcopy(self._finished)
        if self._used and not self._done:
            raise ValueError('Preparation must settle before result retention')
        if self._done:
            self._capture(late=True)
        complete = bool(self._captured is not None
            and self._captured['observation_complete'] and not self._issues)
        self._finished = dict(kind=KIND, schema_version=1,
            callback_started=self._used, callback_finished=self._done,
            observation=deepcopy(self._captured), observation_complete=complete,
            retention_issues=sorted(self._issues), paid_launch_ready=False,
            native_qualification=False, historical_cause_established=False)
        return validate(self._finished)


def validate(value):
    keys = {'kind', 'schema_version', 'callback_started', 'callback_finished',
        'observation', 'observation_complete', 'retention_issues', 'paid_launch_ready',
        'native_qualification', 'historical_cause_established'}
    if (type(value) is not dict or set(value) != keys or value['kind'] != KIND
            or type(value['schema_version']) is not int or value['schema_version'] != 1
            or any(type(value[k]) is not bool for k in
                ('callback_started', 'callback_finished', 'observation_complete'))
            or any(value[k] is not False for k in
                ('paid_launch_ready', 'native_qualification', 'historical_cause_established'))):
        raise ValueError('Exact non-admitting retained setup metadata required')
    issues = value['retention_issues']; observation = value['observation']
    if (type(issues) is not list or any(type(k) is not str for k in issues)
            or issues != sorted(set(issues)) or not set(issues) <= ISSUES
            or value['callback_started'] is not value['callback_finished']):
        raise ValueError('Unsettled or unsupported recovery retention metadata')
    if observation is not None:
        setup.validate(observation)
        if not value['callback_finished']:
            raise ValueError('An unstarted callback cannot have an observation')
    if not value['callback_started'] and (observation is not None or issues):
        raise ValueError('Unstarted preparation cannot invent diagnostic evidence')
    if value['callback_finished'] and observation is None and not issues:
        raise ValueError('A missing completed observation must remain incomplete')
    complete = bool(observation is not None and observation['observation_complete'] and not issues)
    if value['observation_complete'] is not complete:
        raise ValueError('Diagnostic completeness cannot be fabricated')
    return deepcopy(value)
