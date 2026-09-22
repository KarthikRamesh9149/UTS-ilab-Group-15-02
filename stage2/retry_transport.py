"""Observe rejection headers without changing the pinned HTTP implementation."""
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import build_opener

from openrouter_transport import OpenRouter, NoRedirect, TransportError


class ObservedOpenRouter(OpenRouter):
    def __init__(self, key, *, clock, generation_enabled=False, opener=None, completion_wait_seconds=45):
        self.clock = clock
        self.last_failure = None
        delegate = opener or build_opener(NoRedirect())
        owner = self
        class Observe:
            def open(self, request, **kwargs):
                try:
                    return delegate.open(request, **kwargs)
                except HTTPError as exc:
                    # These values only reach the bounded parser, never logs.
                    values = exc.headers.get_all('Retry-After', []) if exc.headers else []
                    owner.last_failure = dict(http_status=exc.code, retry_after_values=values,
                        observed_at_utc=datetime.fromtimestamp(clock.wall(), timezone.utc),
                        now_monotonic=clock.monotonic())
                    raise
        super().__init__(key, generation_enabled=generation_enabled, opener=Observe(),
                         completion_wait_seconds=completion_wait_seconds)

    def complete(self, payload, *, on_response_headers=None):
        self.last_failure = None
        try:
            return super().complete(payload, on_response_headers=on_response_headers)
        except TransportError as exc:
            if self.last_failure is None:
                self.last_failure = dict(http_status=(exc.diagnostic or {}).get('http_status'),
                    retry_after_values=[], observed_at_utc=datetime.fromtimestamp(self.clock.wall(), timezone.utc),
                    now_monotonic=self.clock.monotonic())
            self.last_failure['diagnostic'] = exc.diagnostic or {}
            raise
