"""UTS C0-NC custom coding-agent harness.

The package exposes the measured Harbor adapter and its single-agent runner.
Model requests require an explicitly supplied local gateway; imports never
launch tasks, create containers or contact a provider.
"""
from .agent import NoCutoffCustomHarborAgent, NoCutoffCustomRunner, agent_factory
from .control import Condition

__all__ = [
    "NoCutoffCustomHarborAgent",
    "NoCutoffCustomRunner",
    "Condition",
    "agent_factory",
]
