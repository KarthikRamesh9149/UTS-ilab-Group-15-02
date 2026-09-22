"""Pure retry policy shared by the separately registered recovery gateway.

No I/O, credentials, billing, sleeping or model calls. The caller must retain
physical-request evidence and enforce one shared provider/model cooldown. A
decision is not dispatch permission: recheck lifecycle and deadline after waits.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from enum import Enum
import math
import re


class HeaderState(str, Enum):
    ABSENT = 'absent'
    INVALID = 'invalid'
    DELTA_SECONDS = 'delta-seconds'
    HTTP_DATE = 'http-date'
    CONFLICTING = 'conflicting'
    UNREPRESENTABLE = 'unrepresentable'
    NOT_EXAMINED = 'not-examined'


class RetryReason(str, Enum):
    ELIGIBLE = 'eligible'
    NOT_HTTP_429 = 'not-http-429'
    RESPONSE_DELIVERED = 'response-delivered'
    TRIAL_INACTIVE = 'trial-inactive'
    CONFLICTING_HEADERS = 'conflicting-headers'
    UNREPRESENTABLE_DELAY = 'unrepresentable-delay'
    DEADLINE_REACHED = 'deadline-reached'
    WAIT_REACHES_DEADLINE = 'wait-reaches-deadline'


@dataclass(frozen=True)
class RetryAfter:
    state: HeaderState
    delay_seconds: float | None = None


@dataclass(frozen=True)
class RetryDecision:
    reason: RetryReason
    header_state: HeaderState
    delay_seconds: float | None = None
    not_before_monotonic: float | None = None

    @property
    def can_retry(self) -> bool:
        return self.reason is RetryReason.ELIGIBLE


_DAY = r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)'
_LONG_DAY = r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)'
_MONTH = r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
_TIME = r'[0-9]{2}:[0-9]{2}:[0-9]{2}'
_IMF = re.compile(rf'{_DAY}, [0-9]{{2}} {_MONTH} [0-9]{{4}} {_TIME} GMT')
_RFC850 = re.compile(rf'{_LONG_DAY}, [0-9]{{2}}-{_MONTH}-(?P<year>[0-9]{{2}}) {_TIME} GMT')
_ASCTIME = re.compile(rf'{_DAY} {_MONTH} (?: [0-9]|[0-9]{{2}}) {_TIME} [0-9]{{4}}')
_MAX_HEADER_LENGTH = 256
_MAX_HEADER_VALUES = 16


def _check_utc(value: datetime) -> None:
    if not isinstance(value, datetime) or value.utcoffset() != timedelta(0):
        raise ValueError('Observation time must be an aware UTC datetime')


def _finite_clock(value: float) -> float:
    try:
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError
        return float(value)
    except (ValueError, OverflowError):
        raise ValueError('Clock values must be finite nonnegative numbers') from None


def _http_date(value: str, observed_at_utc: datetime) -> datetime | None:
    legacy = _RFC850.fullmatch(value)
    if not (legacy or _IMF.fullmatch(value) or _ASCTIME.fullmatch(value)):
        return None
    try:
        stamp = parsedate_to_datetime(value).replace(tzinfo=timezone.utc)
        if legacy:
            # RFC 9110's rolling 50-year rule, not email.utils' fixed 1969 cutoff.
            year = ((observed_at_utc.year + 50) // 100) * 100 + int(legacy['year'])
            future_limit = (observed_at_utc.year + 50, observed_at_utc.month,
                            observed_at_utc.day, observed_at_utc.hour,
                            observed_at_utc.minute, observed_at_utc.second)
            if (year, stamp.month, stamp.day, stamp.hour, stamp.minute, stamp.second) > future_limit:
                year -= 100
            stamp = stamp.replace(year=year)
        return stamp
    except (TypeError, ValueError, OverflowError):
        return None


def parse_retry_after(values: object, *, observed_at_utc: datetime) -> RetryAfter:
    """Parse separate header values, never a comma-joined header or raw message.

    Untrusted malformed input returns INVALID; conflicting/oversized headers
    return a stop state. No raw text leaves this boundary. Bad trusted clocks
    raise ValueError, independently of the provider response.
    """
    _check_utc(observed_at_utc)
    if values is None or (type(values) in (tuple, list) and not values):
        return RetryAfter(HeaderState.ABSENT)
    if type(values) not in (tuple, list):
        return RetryAfter(HeaderState.INVALID)
    if len(values) > _MAX_HEADER_VALUES:
        return RetryAfter(HeaderState.CONFLICTING)
    if any(type(value) is not str for value in values):
        return RetryAfter(HeaderState.CONFLICTING if len(values) > 1 else HeaderState.INVALID)
    if any(len(value) > _MAX_HEADER_LENGTH for value in values):
        return RetryAfter(HeaderState.UNREPRESENTABLE)
    clean = [value.strip(' \t') for value in values]
    if any(value != clean[0] for value in clean[1:]):
        return RetryAfter(HeaderState.CONFLICTING)
    value = clean[0]
    if re.fullmatch(r'[0-9]+', value):
        integer = int(value)
        seconds = float(integer)
        # Do not round a large, valid provider delay downward.
        if seconds < integer:
            seconds = math.nextafter(seconds, math.inf)
        return RetryAfter(HeaderState.DELTA_SECONDS, seconds)
    stamp = _http_date(value, observed_at_utc)
    if stamp is None:
        return RetryAfter(HeaderState.INVALID)
    # Round toward the future, never earlier than the provider's date.
    seconds = float(max(0, math.ceil((stamp - observed_at_utc).total_seconds())))
    return RetryAfter(HeaderState.HTTP_DATE, seconds)


def plan_retry(*, http_status: int | None, retry_after_values: object,
               observed_at_utc: datetime, now_monotonic: float,
               deadline_monotonic: float, consecutive_rejections: int,
               trial_active: bool, response_delivered: bool,
               jitter_sample: float, allow_transport_recovery: bool = False) -> RetryDecision:
    """Plan recovery without extending the official task deadline.

    Pass the raw HTTP status, NOT error.code from a body or a guessed status.
    Fallback backoff is 5, 10, 20, 40, 60 seconds, with equal jitter (half to
    all of the base). A valid provider delay overrides that fallback without a
    cap; zero/past dates get a one-second floor. There is no retry-count or
    financial limit. A shared coordinator must preserve the not-before time
    even when this trial cannot retry. Monotonic timestamps are not portable
    across hosts/reboots and cannot alone be used as persistent cooldown state.
    The default supports only 429. Explicit transport recovery also permits
    transient failures classified by the gateway, never usable completions.
    """
    _check_utc(observed_at_utc)
    now = _finite_clock(now_monotonic)
    deadline = _finite_clock(deadline_monotonic)
    if type(consecutive_rejections) is not int or consecutive_rejections < 1:
        raise ValueError('Rejection count must be a positive integer')
    if type(trial_active) is not bool or type(response_delivered) is not bool:
        raise ValueError('Lifecycle flags must be booleans')
    if type(jitter_sample) not in (int, float) or not 0 <= jitter_sample <= 1:
        raise ValueError('Jitter must be a finite sample between zero and one')
    if type(allow_transport_recovery) is not bool:
        raise ValueError('Transport recovery must be explicitly configured')
    eligible = type(http_status) is int and http_status == 429
    if allow_transport_recovery:
        # The shared gateway must first establish that a transport failure (not
        # a usable completion) occurred. Never retry auth/credit/bad-request codes.
        eligible = eligible or http_status is None or (
            type(http_status) is int and http_status in (200, 408, 500, 502, 503, 504))
    if not eligible:
        return RetryDecision(RetryReason.NOT_HTTP_429, HeaderState.NOT_EXAMINED)

    parsed = parse_retry_after(retry_after_values, observed_at_utc=observed_at_utc)
    if parsed.state is HeaderState.CONFLICTING:
        return RetryDecision(RetryReason.CONFLICTING_HEADERS, parsed.state)
    if parsed.state is HeaderState.UNREPRESENTABLE:
        return RetryDecision(RetryReason.UNREPRESENTABLE_DELAY, parsed.state)
    if parsed.delay_seconds is None:
        base = min(60., 5. * 2 ** min(consecutive_rejections - 1, 4))
        delay = base * (.5 + .5 * jitter_sample)
    else:
        delay = max(1., parsed.delay_seconds)
    not_before = now + delay
    if not_before - now < delay:
        not_before = math.nextafter(not_before, math.inf)
    if not math.isfinite(not_before):
        return RetryDecision(RetryReason.UNREPRESENTABLE_DELAY, parsed.state)

    # Compute cooldown even for a closed/expired trial: switching tasks must not
    # erase a provider wait. No metadata field implies that a retry was sent.
    if response_delivered:
        reason = RetryReason.RESPONSE_DELIVERED
    elif not trial_active:
        reason = RetryReason.TRIAL_INACTIVE
    elif now >= deadline:
        reason = RetryReason.DEADLINE_REACHED
    elif not_before >= deadline:
        reason = RetryReason.WAIT_REACHES_DEADLINE
    else:
        reason = RetryReason.ELIGIBLE
    return RetryDecision(reason, parsed.state, delay, not_before)
