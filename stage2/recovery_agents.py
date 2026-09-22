"""Frozen native baselines, deadline recovery and no practical turn restriction."""
from gateway_policy import MODEL
from native_agents import CompatibleOpenHands, agent_factory as native_factory
from retry_policy import SETTINGS
from retry_runtime import deadline_factory


def agent_factory(harness, root):
    native = native_factory(harness, SETTINGS)
    def create(**kwargs):
        if harness == 'terminus-2':
            return native(**kwargs)
        if harness != 'openhands':
            raise ValueError('Only the two registered baselines are allowed')
        # Terminus defaults to 1,000,000 turns. Match that effectively unreachable
        # guard in OpenHands instead of its native 100-iteration default. The
        # benchmark deadline, not a project turn or cost allowance, ends a task.
        return CompatibleOpenHands(logs_dir=kwargs['paths'].agent_dir,
            model_name='openai/' + MODEL, temperature=SETTINGS.temperature,
            reasoning_effort=SETTINGS.reasoning_effort, model_info=SETTINGS.model_info,
            version='0.62.0', python_version='3.12', top_p=1.,
            api_base=kwargs['container_api_base'], max_iterations=1000000,
            extra_env={'LLM_API_KEY': kwargs['trial_token'],
                'LLM_TIMEOUT': str(int(kwargs['completion_wait_seconds'])),
                'LLM_COMPLETION_KWARGS': repr({'extra_body': {'reasoning': {'effort': 'high'}}})},
            num_retries=0)
    create.harness = harness
    create.model_protocol_sha256 = SETTINGS.fingerprint()
    return deadline_factory(create, root, SETTINGS)
