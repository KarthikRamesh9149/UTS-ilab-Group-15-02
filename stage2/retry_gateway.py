"""Shared deadline-bound recovery, passive accounting and no task replays.

Each physical request still passes through PassiveSession, which writes new
immutable request/outcome records. Only undelivered transport failures recover;
auth, credit, integrity and usable model responses are never replayed here.
"""
from dataclasses import asdict
import hashlib
import hmac
from pathlib import Path
import signal
import threading

from credit_only_gateway import (PassiveSession, CreditOnlyError, CreditOnlyHandler,
    prepare_credit_request)
from gateway_http import make_unix_server
from model_protocol import read_protocol
from openrouter_transport import load_key
from rate_limit_candidate import plan_retry
from retry_runtime import Clock, Cooldown, TRANSIENT_HTTP, deadline_for
from retry_transport import ObservedOpenRouter
from scored_gateway import durable_json, private_directory


class RetryHandler(CreditOnlyHandler):
    def reply(self, status, payload):
        if isinstance(payload, dict) and isinstance(payload.get('error'), dict):
            payload = dict(payload, error=dict(payload['error'], message=
                'Request ended; shared recovery exhausted or unavailable. Do not replay this task.'))
        super().reply(status, payload)


class RetrySession(PassiveSession):
    def require_recovery_policy(self):
        from retry_policy import require_policy
        require_policy(self.runtime)

    def __init__(self, *args, clock=None, **kwargs):
        self.clock = clock or Clock()
        self.cancelled = threading.Event()
        self.logical_mutex = threading.Lock()
        self.logical_sequence = 0
        super().__init__(*args, **kwargs)
        try:
            from retry_policy import SETTINGS
            self.require_recovery_policy()
            if self.settings != SETTINGS: raise ValueError('Corrected model protocol required')
            self.cooldown = Cooldown(self.runtime, self.clock)
        except BaseException:
            self.close()
            raise

    def authorised(self, token):
        if self.closed or self.cancelled.is_set() or not isinstance(token, str) or not hmac.compare_digest(
                hashlib.sha256(token.encode()).digest(), self.token_hash):
            raise CreditOnlyError('trial_unauthorised')

    def complete(self, token, payload):
        with self.logical_mutex:
            self.authorised(token)
            if self.stopped: raise CreditOnlyError('attempt_stopped')
            prepare_credit_request(payload, self.settings)
            deadline = deadline_for(self.runtime, self.trial_id, self.settings, self.clock)
            self.logical_sequence += 1
            logical = self.logical_sequence
            first = self.sequence + 1
            accepted = False
            try:
                while True:
                    self.authorised(token)
                    if not self.cooldown.wait(deadline, self.cancelled):
                        self.stopped = True
                        raise CreditOnlyError('upstream_unavailable')
                    self.authorised(token)
                    remaining = deadline - self.clock.monotonic()
                    if remaining <= 0:
                        self.stopped = True
                        raise CreditOnlyError('upstream_unavailable')
                    self.client.completion_wait_seconds = remaining
                    try:
                        response = super().complete(token, payload)
                    except CreditOnlyError as exc:
                        observed = getattr(self.client, 'last_failure', None)
                        if exc.code != 'upstream_unavailable' or not isinstance(observed, dict):
                            raise
                        status = observed.get('http_status')
                        diagnostic = observed.get('diagnostic', {})
                        # Recover uncertain transport losses too, retaining each
                        # possible charge as unknown. No already-delivered output
                        # is replayed, and no tool command is repeated by us.
                        transient = status is None or status in TRANSIENT_HTTP or (
                            status == 200 and diagnostic.get('error_code') in TRANSIENT_HTTP)
                        if not transient: raise
                        decision = plan_retry(http_status=status,
                            retry_after_values=observed.get('retry_after_values'),
                            observed_at_utc=observed['observed_at_utc'],
                            now_monotonic=observed['now_monotonic'], deadline_monotonic=deadline,
                            consecutive_rejections=self.cooldown.count + 1,
                            trial_active=not self.cancelled.is_set(), response_delivered=False,
                            jitter_sample=.5, allow_transport_recovery=True)
                        durable_json(self.evidence / f'{self.sequence:06d}.retry.json', dict(
                            logical_completion=logical, actual_http_status=status,
                            **asdict(decision)))
                        if decision.not_before_monotonic is None:
                            durable_json(self.evidence / 'provider-stop.json', dict(
                                trial_id=self.trial_id, reason='retry_header_invalid'))
                            raise
                        self.cooldown.reject(decision)
                        if not decision.can_retry: raise
                        self.authorised(token)
                        # Only this new gateway owns recovery. The native SDKs
                        # still cannot secretly replay a rejected logical call.
                        self.stopped = False
                        continue
                    accepted = True
                    self.cooldown.success()
                    return response
            finally:
                durable_json(self.evidence / f'logical-{logical:06d}.json', dict(
                    logical_completion=logical, first_physical_sequence=first,
                    last_physical_sequence=self.sequence, accepted_for_agent=accepted))

    def close(self):
        self.cancelled.set()  # Wake the wait before acquiring the parent mutex.
        super().close()


def serve(root, trial_id, stage, token_file, credential_file, socket_path, *, completion_wait_seconds,
          client_factory=ObservedOpenRouter, session_factory=RetrySession):
    runtime = Path(root) / '.runtime/stage2'
    settings = read_protocol(runtime)
    # load_key validates credentials; the inherited compose validates the private
    # trial-token mount. Reuse the same private-file check for this process.
    import stat, re
    info = Path(token_file).lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise ValueError('Private trial token required')
    token = Path(token_file).read_text().strip()
    if not re.fullmatch(r'[a-f0-9]{64}', token): raise ValueError('Invalid trial token')
    clock = Clock()
    client = client_factory(load_key(credential_file), clock=clock, generation_enabled=True,
        completion_wait_seconds=completion_wait_seconds)
    session = session_factory(root, trial_id, stage, token, client, settings=settings, clock=clock)
    socket_path = Path(socket_path)
    private_directory(socket_path.parent)
    def interrupted(signum, frame):
        session.cancelled.set()
        raise KeyboardInterrupt
    previous = signal.signal(signal.SIGTERM, interrupted)
    server = None
    try:
        with session:
            server = make_unix_server(lambda: session, socket_path, handler=RetryHandler)
            server.serve_forever()
    finally:
        if server is not None:
            server.server_close()
            socket_path.unlink(missing_ok=True)
        signal.signal(signal.SIGTERM, previous)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'trial', 'stage', 'token-file', 'credential-file', 'socket'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--completion-wait-seconds', type=float, required=True)
    args = parser.parse_args()
    try:
        serve(args.root, args.trial, args.stage, args.token_file, args.credential_file,
              args.socket, completion_wait_seconds=args.completion_wait_seconds)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        raise SystemExit('Gateway stopped: ' + type(exc).__name__) from None
