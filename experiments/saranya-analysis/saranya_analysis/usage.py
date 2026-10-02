"""Cost, token and runtime totals. Unknown values are counted, never added as zero."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from statistics import median

from saranya_analysis.load import Trial


@dataclass(frozen=True)
class Usage:
    harness: str
    trials: int
    model_requests: int
    accepted_responses: int
    http_429_requests: int
    unknown_cost_requests: int
    known_cost_usd: Decimal
    trials_with_complete_cost: int
    known_input_tokens: int
    known_output_tokens: int
    trials_with_complete_tokens: int
    agent_seconds_total: float
    agent_seconds_median: float | None
    trials_with_agent_time: int

    @property
    def total_cost_known(self) -> bool:
        return self.unknown_cost_requests == 0 and self.trials_with_complete_cost == self.trials


def _sum(values) -> int:
    return sum(v for v in values if v is not None)


def usage(harness: str, trials: dict[str, Trial]) -> Usage:
    rows = list(trials.values())
    agent_times = [t.agent_seconds for t in rows if t.agent_seconds is not None]
    return Usage(
        harness=harness, trials=len(rows),
        model_requests=_sum(t.model_requests for t in rows),
        accepted_responses=_sum(t.accepted_responses for t in rows),
        http_429_requests=_sum(t.http_429_requests for t in rows),
        unknown_cost_requests=_sum(t.unknown_cost_requests for t in rows),
        known_cost_usd=sum((t.known_cost_usd for t in rows if t.known_cost_usd is not None), Decimal(0)),
        trials_with_complete_cost=sum(1 for t in rows if t.total_cost_usd is not None),
        known_input_tokens=_sum(t.known_input_tokens for t in rows),
        known_output_tokens=_sum(t.known_output_tokens for t in rows),
        trials_with_complete_tokens=sum(1 for t in rows if t.input_tokens is not None and t.output_tokens is not None),
        agent_seconds_total=sum(agent_times),
        agent_seconds_median=median(agent_times) if agent_times else None,
        trials_with_agent_time=len(agent_times),
    )
