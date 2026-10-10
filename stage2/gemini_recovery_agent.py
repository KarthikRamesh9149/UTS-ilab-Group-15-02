"""Opt-in command-handle recovery for a future, separately registered experiment.

The recorded Gemini v0.1.0 adapter keeps its original job behavior. This adapter
changes only unknown-handle feedback; it grants no new paid-run admission.
"""
from custom_deadline_execution import DeadlineJobs
from gemini_laptop_agent import GeminiAgent, GeminiRunner

RECOVERY_VERSION = 'stage2-c0-nc-gemini-0.2.0'


class RecoveringDeadlineJobs(DeadlineJobs):
    def known(self, identifier):
        return isinstance(identifier, str) and identifier in self.jobs

    @staticmethod
    def unknown_handle():
        return {'status': 'error', 'error': 'unknown_command_handle',
                'message': 'Use a job_id returned by start_command in this trial. '
                           'A command run with execute does not create a job_id.'}

    def poll(self, identifier):
        if not self.known(identifier):
            return self.unknown_handle()
        return super().poll(identifier)

    async def interrupt(self, identifier):
        if not self.known(identifier):
            return self.unknown_handle()
        return await super().interrupt(identifier)


class RecoveryGeminiRunner(GeminiRunner):
    def make_jobs(self, backend):
        return RecoveringDeadlineJobs(backend, self.deadline)


class RecoveryGeminiAgent(GeminiAgent):
    @staticmethod
    def name():
        return 'uts-c0-nc-gemini-laptop-recovery'

    def version(self):
        return RECOVERY_VERSION

    def make_runner(self, backend, deadline):
        return RecoveryGeminiRunner(self.model, backend, deadline)
