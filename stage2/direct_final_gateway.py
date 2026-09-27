"""Direct-final admission with unchanged shared retry and passive accounting.

Not installed into any active study. A separately qualified final deployment
and host runner are still required. No ledger reservations or receipt gates.
"""
from direct_final_policy import require_trial, fingerprint
from retry_gateway import RetrySession, serve


class DirectFinalSession(RetrySession):
    def require_session_policy(self):
        block = require_trial(self.runtime, self.trial_id, self.stage)
        binding = fingerprint(block)
        if getattr(self, 'registration_sha256', binding) != binding:
            raise ValueError('Final registration changed within an attempt')
        self.registration_sha256 = binding

    def require_recovery_policy(self):
        self.require_session_policy()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'trial', 'stage', 'token-file', 'credential-file', 'socket'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--completion-wait-seconds', type=float, required=True)
    args = parser.parse_args()
    try:
        serve(args.root, args.trial, args.stage, args.token_file, args.credential_file,
            args.socket, completion_wait_seconds=args.completion_wait_seconds,
            session_factory=DirectFinalSession)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        raise SystemExit('Final gateway stopped: ' + type(exc).__name__) from None
