"""Transport waiting independent of the official task deadline."""
import math


def validate_completion_wait(value):
    if type(value) not in (int, float):
        raise ValueError('Positive finite completion wait required')
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise ValueError('Positive finite completion wait required') from None
    if not math.isfinite(result) or result <= 0:
        raise ValueError('Positive finite completion wait required')
    return result


def completion_wait_for(agent_timeout_seconds):
    """Derive once from trusted task configuration, never request JSON."""
    return validate_completion_wait(validate_completion_wait(agent_timeout_seconds) + 60)
