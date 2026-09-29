"""Recovery-only input checks over unchanged deadline-bound passive retry.

This container entry is not a host service, qualification or dispatch scope.
Only the future authenticated, qualified host may mount its private inputs and
start it for one of the three fresh attempts. No provider probe is added.
"""
from no_cutoff_recovery_policy import read_trial
from retry_gateway import RetrySession, serve


class NoCutoffRecoverySession(RetrySession):
    def require_session_policy(self):
        if getattr(self, '_policy_invalid', False):
            raise ValueError('Recovery input refusal is terminal for this gateway')
        try:
            _, binding = read_trial(self.runtime, self.trial_id, self.stage)
            if getattr(self, '_input_binding', binding) != binding:
                raise ValueError('Recovery private input bytes or identities changed')
            self._input_binding = binding
        except BaseException:
            self._policy_invalid = True
            self.stopped = True
            raise

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
            session_factory=NoCutoffRecoverySession)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        raise SystemExit('Recovery gateway stopped: ' + type(exc).__name__) from None
