"""Failure categories from the recorded outcome and exception fields only.

Categories describe what was recorded, not proven causes. Anything the fields
cannot settle is "needs review" rather than a guess.

- timeout: agent hit the official task deadline, no HTTP 429 recorded.
- rate limit: agent hit the deadline, or raised an API error, and at least one
  HTTP 429 was recorded. Waiting out rate limits uses task time, so these are
  not pure capability failures. Stage 2's timeout diagnostic reran 30 such
  failures and 10 passed, but how much each failure owes to rate limiting is
  unknown.
- setup error: no verifier outcome because the task setup failed.
- verifier fail: the agent finished without a recorded exception and the
  official checks failed.
- other: never assigned automatically. Every unrecognised case is "needs
  review", with the recorded exception kept in the note.
"""
from __future__ import annotations

from collections import Counter

from saranya_analysis.load import Trial

CATEGORIES = ('timeout', 'rate limit', 'setup error', 'verifier fail', 'other', 'needs review')

# Recorded exceptions whose cause the CSV fields cannot settle.
REVIEW_NOTES = {
    'NetworkConnectionError': 'startup/connection error; Stage 2 records its cause as unconfirmed',
    'OpenAIPermissionDeniedError': 'model access denied near the task deadline; possibly revocation at the deadline',
    'ContainerCaptureError': 'container output-capture helper error',
}


def categorise(trial: Trial) -> tuple[str, str]:
    """Return (category, note) for a failed or missing trial. Passes are not categorised."""
    if trial.passed:
        raise ValueError('Only failed or missing trials are categorised')
    rate_limited = (trial.http_429_requests or 0) > 0
    error = trial.agent_error_type
    if not trial.valid:
        if trial.status == 'setup_failed':
            return 'setup error', f'status setup_failed; agent exception {error}'
        return 'needs review', f'no verifier outcome; status {trial.status}'
    if trial.verifier_error_type:
        return 'needs review', f'verifier error {trial.verifier_error_type}'
    if error == 'TimeoutError':
        if rate_limited:
            return 'rate limit', f'agent timeout with {trial.http_429_requests} HTTP 429 responses'
        return 'timeout', 'agent timeout, no HTTP 429 recorded'
    if error == 'APIError':
        if rate_limited:
            return 'rate limit', f'API error with {trial.http_429_requests} HTTP 429 responses'
        return 'needs review', 'API error without a recorded HTTP 429'
    if error is None:
        return 'verifier fail', 'no agent exception; official checks failed'
    note = REVIEW_NOTES.get(error, 'unrecognised exception')
    if rate_limited:
        note += f'; {trial.http_429_requests} HTTP 429 responses'
    return 'needs review', f'{error}: {note}'


def failure_counts(trials: dict[str, Trial]) -> Counter:
    return Counter(categorise(t)[0] for t in trials.values() if not t.passed)


def passes_with_agent_error(trials: dict[str, Trial]) -> int:
    """Passes where an agent exception was also recorded, such as a timeout after the work was done."""
    return sum(1 for t in trials.values() if t.passed and t.agent_error_type)
