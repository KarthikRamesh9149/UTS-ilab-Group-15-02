"""Final C0-NC execution contract and measured implementation version."""
from .deadline_contract import execution_contract as deadline_contract

CANDIDATE_VERSION = 'stage2-candidate-0.5.0'
EXECUTION_POLICY_VERSION = 'parent-no-cutoff-without-time-advice-v1'


def revision_name(parent):
    if parent not in ('C0', 'C1', 'C2'):
        raise ValueError('An original C0/C1/C2 whole parent is required')
    return parent + '-NC'


def execution_contract():
    return dict(deadline_contract(), version=EXECUTION_POLICY_VERSION,
        remaining_time_guidance=False,
        prompt_amendment='command-and-completion-contract-only',
        capture_transport='encoded-helper-source-v1')
