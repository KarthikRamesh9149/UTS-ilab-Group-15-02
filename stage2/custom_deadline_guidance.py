"""Per-request time context; not an extra timer, retry loop or model-call cap.

The separately versioned adapter supplies the gateway's already active deadline.
Only that deadline and the host monotonic clock are observed. Task content,
verifiers, balances and earlier trials are not inputs to this component.
"""
from copy import deepcopy
import math

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import SystemMessage

GUIDANCE_VERSION = 'deadline-context-v1'
MARKER = '[Task time remaining]'
VERIFY_FRACTION = .20
FINISH_FRACTION = .05


def finite_seconds(value, *, positive=False):
    if (type(value) not in (int, float) or value < 0 or (positive and value == 0)):
        raise ValueError('Finite nonnegative seconds required')
    try:
        if not math.isfinite(value):
            raise ValueError('Finite nonnegative seconds required')
        return float(value)
    except OverflowError:
        raise ValueError('Finite nonnegative seconds required') from None


class DeadlineGuidance(AgentMiddleware):
    """Append one transient system note, invoking the model handler once.

    The note is derived anew for each request, never added to persisted graph
    history. Expiry remains the existing orchestrator/gateway's responsibility.
    Thresholds are advice, not early termination or reserved execution time.
    """
    def __init__(self, *, deadline_monotonic, official_timeout_seconds, monotonic):
        self.deadline = finite_seconds(deadline_monotonic)
        self.duration = finite_seconds(official_timeout_seconds, positive=True)
        if not callable(monotonic):
            raise ValueError('Explicit monotonic clock required')
        self.monotonic = monotonic
        self.last_now = None
        self.events = []

    def note(self):
        now = finite_seconds(self.monotonic())
        if self.last_now is not None and now < self.last_now:
            raise ValueError('Monotonic clock moved backwards')
        if now < self.deadline - self.duration:
            raise ValueError('Deadline exceeds the official task allowance')
        self.last_now = now
        remaining = max(0., self.deadline - now)
        fraction = remaining / self.duration
        if remaining == 0:
            phase = 'expired'
            advice = 'The official deadline has been reached; the runtime controls termination.'
        elif fraction <= FINISH_FRACTION:
            phase = 'finish'
            advice = ('Time is nearly exhausted. Prioritise a usable result and the most important '
                      'remaining checks; avoid starting a broad new approach.')
        elif fraction <= VERIFY_FRACTION:
            phase = 'verify'
            advice = ('Time is running short. Focus on completing the current approach and '
                      'checking its outputs against the task requirements.')
        else:
            phase = 'work'
            advice = 'Allocate time between implementation and checking the resulting work.'
        event = dict(model_request=len(self.events) + 1,
            remaining_seconds=math.floor(remaining), phase=phase)
        self.events.append(event)
        return (f'{MARKER}\nAbout {event["remaining_seconds"]} seconds remain of the '
                f'{self.duration:g}-second official agent allowance, as of this request. '
                'Model waiting and tool execution both consume this time. '
                f'{advice} This is guidance, not extra time or a requirement to stop early. '
                'Elapsed time is not evidence of success; report only what you actually observed.')

    def prepare(self, request):
        note = self.note()
        system = request.system_message
        if system is None:
            updated = SystemMessage(content=note)
        else:
            content = system.content
            if isinstance(content, str):
                content = content + '\n\n' + note
            else:
                content = deepcopy(content) + [{'type': 'text', 'text': note}]
            updated = system.model_copy(update={'content': content})
        # Keep all tool-call IDs, messages, tools, model settings and metadata.
        return request.override(system_message=updated)

    def wrap_model_call(self, request, handler):
        return handler(self.prepare(request))

    async def awrap_model_call(self, request, handler):
        return await handler(self.prepare(request))

    def metadata(self):
        return dict(version=GUIDANCE_VERSION, official_timeout_seconds=self.duration,
            source='authoritative_gateway_deadline', verify_fraction=VERIFY_FRACTION,
            finish_fraction=FINISH_FRACTION, advisory_only=True,
            model_requests=len(self.events), events=deepcopy(self.events))
