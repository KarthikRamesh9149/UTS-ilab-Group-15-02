"""Task-independent custom experiment controls. No verifier or task IDs here."""
from dataclasses import dataclass, field

BASE_PROMPT = '''Work only in the provided task environment. Use the supplied tools.
Finish by calling complete_task with an honest summary of your outcome.
Do not claim that a command exit code proves task success. A task may legitimately
need no edits. Do not use hidden tests, reference solutions, or other tasks.
Completion is your report, not a benchmark pass. At most two explicit repair
cycles are available after an incomplete completion attempt.'''
PLAN_PROMPT = '''Before acting, briefly state your interpretation of the request and
a short task-specific plan in your normal response. Update it only when useful.
Do not make a separate planning call or delegate work.'''
CHECK_PROMPT = '''Before completing, check the task's actual requirements against
observations available to you. In complete_task, supply at least one check with
criterion, observation, and satisfied=true. Include every material requirement.
Never invent an observation. If no edit was necessary, explain why. If checks
fail, use the remaining repair allowance or report that you could not finish.'''


@dataclass(frozen=True)
class Condition:
    name: str
    parent: str | None = None

    def __post_init__(self):
        if self.name not in {'C0', 'C1', 'C2'}:
            raise ValueError('Unknown condition')
        if (self.name == 'C2' and self.parent not in {'C0', 'C1'}) or (self.name != 'C2' and self.parent is not None):
            raise ValueError('Only C2 requires an explicitly selected C0/C1 parent')

    @property
    def prompt(self):
        parts = [BASE_PROMPT]
        if self.name == 'C1' or self.parent == 'C1':
            parts.append(PLAN_PROMPT)
        if self.name == 'C2':
            parts.append(CHECK_PROMPT)
        return '\n\n'.join(parts)


@dataclass
class CompletionControl:
    condition: Condition
    repairs_used: int = 0
    terminal: bool = False
    outcome: str | None = None
    events: list = field(default_factory=list)

    def incomplete(self, reason):
        if self.terminal:
            return {'status': self.outcome, 'terminal': True}
        if self.repairs_used >= 2:
            self.terminal = True
            self.outcome = 'repair_exhausted'
            event = {'status': self.outcome, 'reason': reason, 'terminal': True}
        else:
            self.repairs_used += 1
            event = {'status': 'repair_requested', 'reason': reason,
                     'repair_number': self.repairs_used, 'terminal': False}
        self.events.append(event)
        return event

    def complete(self, summary, checks=None, no_edit_reason=''):
        if self.terminal:
            return {'status': self.outcome, 'terminal': True}
        if not isinstance(summary, str) or not summary.strip():
            return self.incomplete('A nonempty completion summary is required.')
        checks = [] if checks is None else checks
        if self.condition.name == 'C2':
            valid = isinstance(checks, list) and bool(checks) and all(
                isinstance(c, dict) and isinstance(c.get('criterion'), str) and c['criterion'].strip()
                and isinstance(c.get('observation'), str) and c['observation'].strip()
                and c.get('satisfied') is True for c in checks)
            if not valid:
                return self.incomplete('Supply requirement-specific observed checks, all satisfied, or report inability to finish.')
        self.terminal = True
        self.outcome = 'agent_reported_complete'
        event = {'status': self.outcome, 'summary': summary, 'checks': checks,
                 'no_edit_reason': no_edit_reason, 'terminal': True,
                 'benchmark_success': None}
        self.events.append(event)
        return event

    def abandon(self, reason):
        if self.terminal:
            return {'status': self.outcome, 'terminal': True}
        self.terminal = True
        self.outcome = 'agent_reported_incomplete'
        event = {'status': self.outcome, 'reason': reason, 'terminal': True}
        self.events.append(event)
        return event
