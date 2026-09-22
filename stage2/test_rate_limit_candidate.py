from dataclasses import asdict, FrozenInstanceError
from datetime import datetime, timedelta, timezone
import json
import math
import unittest
from unittest.mock import patch

from rate_limit_candidate import (HeaderState, RetryReason,
                                 parse_retry_after, plan_retry)


NOW = datetime(2026, 9, 22, 20, 0, 0, tzinfo=timezone.utc)


def decision(**changes):
    values = dict(http_status=429, retry_after_values=(), observed_at_utc=NOW,
                  now_monotonic=100., deadline_monotonic=1000.,
                  consecutive_rejections=1, trial_active=True,
                  response_delivered=False, jitter_sample=1.)
    values.update(changes)
    return plan_retry(**values)


class RetryAfterTests(unittest.TestCase):
    def parse(self, values, **changes):
        return parse_retry_after(values, observed_at_utc=changes.get('now', NOW))

    def test_missing_header(self):
        for values in (None, (), []):
            with self.subTest(values=values):
                result = self.parse(values)
                self.assertEqual(result.state, HeaderState.ABSENT)
                self.assertIsNone(result.delay_seconds)

    def test_ascii_integer_and_ows(self):
        for value, seconds in [('60', 60.), ('0', 0.), ('0005', 5.), (' \t120\t ', 120.)]:
            with self.subTest(value=value):
                result = self.parse([value])
                self.assertEqual(result.state, HeaderState.DELTA_SECONDS)
                self.assertEqual(result.delay_seconds, seconds)

    def test_future_http_date(self):
        result = self.parse(['Tue, 22 Sep 2026 20:01:30 GMT'])
        self.assertEqual(result.state, HeaderState.HTTP_DATE)
        self.assertEqual(result.delay_seconds, 90.)

    def test_obsolete_http_dates(self):
        for value in ('Tuesday, 22-Sep-26 20:01:30 GMT', 'Tue Sep 22 20:01:30 2026'):
            with self.subTest(value=value):
                self.assertEqual(self.parse([value]).delay_seconds, 90.)
        single_day = self.parse(['Tue Sep  1 20:00:00 2026'], now=NOW.replace(day=1))
        self.assertEqual(single_day.state, HeaderState.HTTP_DATE)

    def test_rfc850_uses_rolling_50_year_rule(self):
        recent = self.parse(['Sunday, 22-Sep-69 20:00:00 GMT'])
        self.assertEqual(recent.delay_seconds,
                         (NOW.replace(year=2069) - NOW).total_seconds())
        self.assertEqual(self.parse(['Tuesday, 22-Sep-77 20:00:00 GMT']).delay_seconds, 0.)
        boundary = self.parse(['Tuesday, 22-Sep-76 20:00:00 GMT'])
        self.assertEqual(boundary.delay_seconds,
                         (NOW.replace(year=2076) - NOW).total_seconds())
        self.assertEqual(self.parse(['Tuesday, 22-Sep-76 20:00:01 GMT']).delay_seconds, 0.)

    def test_past_date_and_fractional_observation(self):
        self.assertEqual(self.parse(['Tue, 22 Sep 2026 19:59:59 GMT']).delay_seconds, 0.)
        result = self.parse(['Tue, 22 Sep 2026 20:00:01 GMT'], now=NOW.replace(microsecond=1))
        self.assertEqual(result.delay_seconds, 1.)

    def test_identical_duplicates_allowed(self):
        result = self.parse(['60', ' 60\t'])
        self.assertEqual(result.state, HeaderState.DELTA_SECONDS)
        self.assertEqual(result.delay_seconds, 60.)

    def test_conflicting_duplicates_do_not_fallback(self):
        for values in (['60', '120'], ['60', 'bad'], ['60', None], ['60'] * 17):
            with self.subTest(values=values):
                result = self.parse(values)
                self.assertEqual(result.state, HeaderState.CONFLICTING)
                self.assertIsNone(result.delay_seconds)

    def test_invalid_shapes_and_numbers(self):
        for values in ('60', 60, {}, {'Retry-After': '60'}, [None], [True], [60],
                       ['-1'], ['+60'], ['1.5'], ['1e2'], ['NaN'], ['Infinity'],
                       ['６０'], ['٦٠'], [''], [' \t'], ['60\r\nAuthorization: canary']):
            with self.subTest(values=values):
                self.assertEqual(self.parse(values).state, HeaderState.INVALID)

    def test_rejects_invalid_or_coalesced_dates(self):
        for value in ('Tue, 31 Sep 2026 20:00:00 GMT',
                      'Tue, 22 Sep 2026 20:00:00 PST',
                      'Tue, 22 Sep 2026 20:00:00 GMT, 120',
                      'Tue, 22 Sep 2026 20:00:00 GMT canary',
                      '60, 120', 'Tue, 22 Sep 2026 99:00:00 GMT'):
            with self.subTest(value=value):
                self.assertEqual(self.parse([value]).state, HeaderState.INVALID)

    def test_large_provider_delay_not_capped_or_rounded_down(self):
        for integer in (9000, 2**53 + 1, 10**255):
            result = self.parse([str(integer)])
            self.assertEqual(result.state, HeaderState.DELTA_SECONDS)
            self.assertTrue(math.isfinite(result.delay_seconds))
            self.assertGreaterEqual(result.delay_seconds, integer)

    def test_oversized_header_stops_instead_of_short_fallback(self):
        for value in ('9' * 257, 'canary' * 100):
            self.assertEqual(self.parse([value]).state, HeaderState.UNREPRESENTABLE)

    def test_trusted_observation_must_be_aware_utc(self):
        for value in (None, '2026-09-22', NOW.replace(tzinfo=None),
                      NOW.astimezone(timezone(timedelta(hours=10)))):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.parse([], now=value)


class RetryPlanTests(unittest.TestCase):
    def test_fallback_backoff_and_jitter(self):
        for count, base in enumerate((5., 10., 20., 40., 60., 60.), 1):
            for jitter in (0., .5, 1.):
                with self.subTest(count=count, jitter=jitter):
                    result = decision(consecutive_rejections=count, jitter_sample=jitter)
                    self.assertTrue(result.can_retry)
                    self.assertEqual(result.delay_seconds, base * (.5 + .5 * jitter))
                    self.assertEqual(result.not_before_monotonic, 100. + result.delay_seconds)

    def test_invalid_header_uses_backoff(self):
        result = decision(retry_after_values=['not a date'])
        self.assertEqual(result.header_state, HeaderState.INVALID)
        self.assertTrue(result.can_retry)
        self.assertEqual(result.delay_seconds, 5.)

    def test_valid_provider_wait_overrides_backoff_and_its_cap(self):
        result = decision(retry_after_values=['120'], consecutive_rejections=100, jitter_sample=0.)
        self.assertTrue(result.can_retry)
        self.assertEqual(result.delay_seconds, 120.)
        self.assertEqual(result.not_before_monotonic, 220.)
        self.assertEqual(decision(retry_after_values=['2'], consecutive_rejections=100).delay_seconds, 2.)

    def test_zero_and_past_dates_get_positive_floor(self):
        for value in ('0', 'Tue, 22 Sep 2026 19:00:00 GMT'):
            result = decision(retry_after_values=[value])
            self.assertTrue(result.can_retry)
            self.assertEqual(result.delay_seconds, 1.)

    def test_actual_http_429_only(self):
        for status in (None, 200, 400, 401, 402, 403, 408, 500, 502, 503, '429', True, 429.):
            with self.subTest(status=status):
                result = decision(http_status=status, retry_after_values=['120'])
                self.assertFalse(result.can_retry)
                self.assertEqual(result.reason, RetryReason.NOT_HTTP_429)
                self.assertEqual(result.header_state, HeaderState.NOT_EXAMINED)
                self.assertIsNone(result.not_before_monotonic)

    def test_delivered_response_never_replayed(self):
        result = decision(response_delivered=True, retry_after_values=['120'])
        self.assertFalse(result.can_retry)
        self.assertEqual(result.reason, RetryReason.RESPONSE_DELIVERED)
        self.assertEqual(result.not_before_monotonic, 220.)

    def test_closed_trial_keeps_shared_cooldown(self):
        result = decision(trial_active=False, retry_after_values=['120'])
        self.assertFalse(result.can_retry)
        self.assertEqual(result.reason, RetryReason.TRIAL_INACTIVE)
        self.assertEqual(result.not_before_monotonic, 220.)

    def test_expired_trial_keeps_shared_cooldown(self):
        for deadline in (0., 99., 100.):
            result = decision(deadline_monotonic=deadline, retry_after_values=['120'])
            self.assertFalse(result.can_retry)
            self.assertEqual(result.reason, RetryReason.DEADLINE_REACHED)
            self.assertEqual(result.not_before_monotonic, 220.)

    def test_wait_cannot_reach_or_extend_deadline(self):
        for deadline in (101., 104., 105.):
            result = decision(deadline_monotonic=deadline)
            self.assertEqual(result.reason, RetryReason.WAIT_REACHES_DEADLINE)
            self.assertFalse(result.can_retry)
            self.assertEqual(result.not_before_monotonic, 105.)
        self.assertTrue(decision(deadline_monotonic=105.1).can_retry)

    def test_long_provider_delay_survives_trial_boundary(self):
        result = decision(retry_after_values=['3600'])
        self.assertFalse(result.can_retry)
        self.assertEqual(result.reason, RetryReason.WAIT_REACHES_DEADLINE)
        self.assertEqual(result.not_before_monotonic, 3700.)

    def test_conflict_and_unrepresentable_are_stop_states(self):
        for values, reason in [(['60', '120'], RetryReason.CONFLICTING_HEADERS),
                               (['9' * 257], RetryReason.UNREPRESENTABLE_DELAY)]:
            result = decision(retry_after_values=values)
            self.assertFalse(result.can_retry)
            self.assertEqual(result.reason, reason)
            self.assertIsNone(result.not_before_monotonic)

    def test_no_retry_count_cap_or_large_exponent(self):
        result = decision(consecutive_rejections=10**1000)
        self.assertTrue(result.can_retry)
        self.assertEqual(result.delay_seconds, 60.)

    def test_bad_clocks_raise_sanitised_validation_error(self):
        for name in ('now_monotonic', 'deadline_monotonic'):
            for value in (None, True, -1, 'private-canary', float('nan'), float('inf'), 10**1000):
                with self.subTest(name=name, value=str(value)), self.assertRaises(ValueError) as error:
                    decision(**{name: value})
                self.assertNotIn('private-canary', str(error.exception))

    def test_invalid_count_jitter_and_flags(self):
        bad = [('consecutive_rejections', v) for v in (0, -1, True, 1.5, '1', None)]
        bad += [('jitter_sample', v) for v in (-.1, 1.1, True, None, '1', float('nan'), float('inf'))]
        bad += [(name, v) for name in ('trial_active', 'response_delivered') for v in (0, 1, None, 'yes')]
        for name, value in bad:
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                decision(**{name: value})

    def test_float_clock_rounding_never_shortens_wait(self):
        result = decision(now_monotonic=1e16, deadline_monotonic=1e16 + 100,
                          retry_after_values=['1'])
        self.assertTrue(result.can_retry)
        self.assertGreaterEqual(result.not_before_monotonic - 1e16, 1.)

    def test_clock_addition_overflow_stops(self):
        result = decision(now_monotonic=float.fromhex('0x1.fffffffffffffp+1023'),
                          deadline_monotonic=float.fromhex('0x1.fffffffffffffp+1023'))
        self.assertFalse(result.can_retry)
        self.assertEqual(result.reason, RetryReason.UNREPRESENTABLE_DELAY)

    def test_decisions_are_immutable_and_export_only_safe_metadata(self):
        result = decision(retry_after_values=['private-canary'])
        with self.assertRaises(FrozenInstanceError):
            result.reason = RetryReason.ELIGIBLE
        data = asdict(result)
        self.assertEqual(set(data), {'reason', 'header_state', 'delay_seconds', 'not_before_monotonic'})
        self.assertNotIn('private-canary', json.dumps(data, allow_nan=False))

    def test_planning_has_no_io_sleep_billing_or_dispatch(self):
        with patch('socket.socket', side_effect=AssertionError('No network')), \
             patch('builtins.open', side_effect=AssertionError('No files')), \
             patch('time.sleep', side_effect=AssertionError('No sleep')):
            self.assertTrue(decision().can_retry)


if __name__ == '__main__':
    unittest.main()
