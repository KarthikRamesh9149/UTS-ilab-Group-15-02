"""Separate host-infrastructure failures from model/harness failures.

Development runs happen on an Apple Silicon Mac, where x86-64 task images run
under Rosetta. The Stage 2 C0 result ran on a native x86-64 Linux host and
never faced these limits, so a Mac failure caused by the host must not be
counted as a harness failure.

The known-host list is taken from Karthik Ramesh's Mac reference run,
stage2/rosetta_requalification.md: the official reference solutions failed
on these dev20 tasks on the Mac, so no agent can pass them there.
"""
from __future__ import annotations

import re

# Only explicit translation-layer errors. Messages such as "exec format error"
# are excluded: an agent can cause them itself (for example by downloading a
# binary for the wrong architecture), and counting those as infrastructure
# would flatter the harness.
ROSETTA_SIGNATURES = (
    re.compile(r'rosetta error', re.IGNORECASE),
    re.compile(r'Unimplemented syscall', re.IGNORECASE),
)

MAC_REFERENCE_FAILURES = {
    # Confirmed on Saranya's Mac: Oracle run oracle-dev20-mac-r1, 1 October 2026
    # (see oracle/ORACLE_MAC_DEV20.md). The official solution crashed with
    # "rosetta error: Unimplemented syscall number 282".
    'install-windows-3.11': 'reference solution crashed on Saranya\'s Mac: Rosetta unsupported syscall 282',
    'qemu-alpine-ssh': 'reference solution crashed on Saranya\'s Mac: Rosetta unsupported syscall 282',
    # Not yet observed on Saranya's Mac (that trial hit a DNS failure); kept on
    # the evidence of Karthik's Mac run, stage2/rosetta_requalification.md.
    'qemu-startup': 'reference solution failed on Karthik\'s Mac run: Rosetta unsupported syscall 282 '
                    '(not yet confirmed on Saranya\'s Mac)',
}

# The host's network failed: Docker could not pull the task image, or the
# verifier could not download its own test tools. These say nothing about
# the agent. Matched only in Harbor exception messages and verifier output,
# never in agent command output.
NETWORK_SIGNATURES = (
    re.compile(r"Could not resolve '"),
    re.compile(r'Temporary failure resolving'),
    re.compile(r'no such host'),
)
# build-pov-ray's Mac reference also failed, but on an HTTP 403 from the
# reference's own download URL, not on Rosetta; C0 passed it on Netcup. An
# agent failure there is not assumed to be infrastructure.

# Failures that belong to the agent or model, not the host.
AGENT_SIDE_EXCEPTIONS = frozenset({'AgentTimeoutError', 'ModelError'})
# Failures of Harbor or the container host before or around the agent.
INFRASTRUCTURE_EXCEPTIONS = frozenset({
    'EnvironmentStartTimeoutError', 'AgentSetupTimeoutError', 'SandboxBuildFailedError',
    'HealthcheckError', 'AddTestsDirError', 'DownloadVerifierDirError',
    'VerifierOutputParseError', 'RewardFileNotFoundError', 'RewardFileEmptyError',
})
# VerifierTimeoutError is deliberately in neither set: processes the agent left
# running can cause it, so it goes to manual review.


def scan_output(text: str | None) -> list[str]:
    """Return the host-translation signatures found in command output."""
    if not text:
        return []
    return [pattern.pattern for pattern in ROSETTA_SIGNATURES if pattern.search(text)]


def scan_network(text: str | None) -> list[str]:
    """Return the host-network failure signatures found in Harbor or verifier output."""
    if not text:
        return []
    return [pattern.pattern for pattern in NETWORK_SIGNATURES if pattern.search(text)]


def classify_trial(*, task_id: str, reward: float | None, exception_type: str | None,
                   infrastructure_signals: list[str] | None, host: str,
                   stop_reason: str | None = None,
                   network_signals: list[str] | None = None) -> tuple[str, str]:
    """Return (category, reason).

    Categories: passed, model_failure, budget_stop, not_attempted (no spending
    approval, so the model was never called), infrastructure, and
    infrastructure_review (unrecognised exception; a person must decide).
    """
    if reward is not None and reward > 0:
        return 'passed', 'verifier reward > 0'
    if stop_reason == 'no_spending_approval':
        return 'not_attempted', 'no spending approval; the model was not called'
    # Evidence observed in this trial comes before the known-host list.
    if infrastructure_signals:
        return 'infrastructure', 'host translation signature: ' + ', '.join(infrastructure_signals)
    if network_signals:
        return 'infrastructure', 'host network failure: ' + ', '.join(network_signals)
    if host == 'mac' and task_id in MAC_REFERENCE_FAILURES:
        return 'infrastructure', MAC_REFERENCE_FAILURES[task_id]
    if exception_type in INFRASTRUCTURE_EXCEPTIONS:
        return 'infrastructure', f'Harbor exception {exception_type}'
    if stop_reason and stop_reason.startswith('budget_'):
        return 'budget_stop', 'spending safety stop triggered'
    if reward is None and exception_type not in AGENT_SIDE_EXCEPTIONS:
        return 'infrastructure_review', f'no verifier reward; exception {exception_type}'
    if exception_type is not None and exception_type not in AGENT_SIDE_EXCEPTIONS:
        return 'infrastructure_review', f'unrecognised exception {exception_type}'
    return 'model_failure', 'verifier reward 0'
