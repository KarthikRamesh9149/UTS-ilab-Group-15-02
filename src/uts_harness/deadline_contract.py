"""Official-deadline command and completion contract."""
EXECUTION_POLICY_VERSION = 'official-deadline-execution-v1'
CANDIDATE_VERSION = 'stage2-candidate-0.4.1'


def execution_contract():
    return dict(version=EXECUTION_POLICY_VERSION,
        overall_deadline='official-authoritative-unchanged',
        default_command_timeout='remaining-official-task-time',
        agent_chosen_shorter_timeout=True, completion_repair_count_cap=None,
        background_active_count_cap=None, background_lifetime_count_cap=None,
        model_call_cap=None, no_replay=True, output_and_context_windows='finite-unchanged',
        provider_auth_credit_identity='enforced', container_isolation='unchanged')
