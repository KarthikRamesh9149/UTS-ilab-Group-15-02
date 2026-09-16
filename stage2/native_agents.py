"""Native agent factories for single-trial orchestration, not scoring admission.

Connection/retry and OpenHands install compatibility changes only. Baseline
prompts, tools, context management and decision loops remain inherited.
"""
import shlex
import types
from pathlib import Path

from harbor.agents.installed.openhands import OpenHands
from harbor.agents.terminus_2.terminus_2 import Terminus2
from gateway_policy import MODEL
from model_protocol import ModelSettings


class NoRetryTerminus(Terminus2):
    def _init_llm(self, *args, **kwargs):
        client = super()._init_llm(*args, **kwargs)
        # The adapter's retry decorator is additional to LiteLLM num_retries.
        # Fail closed if a library change removes the known wrapper contract.
        native = type(client).call.__wrapped__
        client.call = types.MethodType(native, client)
        return client


class CompatibleOpenHands(OpenHands):
    async def exec_as_agent(self, environment, command, env=None, **kwargs):
        # Harbor forwards declared settings but not arbitrary LLM_* extras.
        # Preserve these explicit connection settings on the native run only.
        if env is not None and 'LLM_MODEL' in env:
            env = dict(env)
            for name in ('LLM_COMPLETION_KWARGS', 'LLM_TIMEOUT'):
                value = self._get_env(name)
                if value is not None:
                    env[name] = value
        return await super().exec_as_agent(environment, command=command, env=env, **kwargs)

    async def install(self, environment):
        await self.ensure_system_dependencies(environment, ('curl', 'git', 'build_tools', 'tmux'))
        user = environment.default_user or 'root'
        await self.exec_as_root(environment,
            command='mkdir -p /opt/openhands-venv && chown ' + shlex.quote(user + ':' + user) + ' /opt/openhands-venv')
        # Freeze the complete previously tested dependency set, not only the
        # four top-level compatibility pins. No task base replacement.
        await environment.upload_file(
            source_path=Path(__file__).with_name('openhands-requirements.lock'),
            target_path='/opt/openhands-requirements.lock')
        await self.exec_as_root(environment, command='chmod 644 /opt/openhands-requirements.lock')
        await self.exec_as_agent(environment, command=(
            'set -euo pipefail; curl -LsSf https://astral.sh/uv/install.sh | sh && '
            'if [ -f "$HOME/.local/bin/env" ]; then source "$HOME/.local/bin/env"; fi && '
            'uv python install 3.12 && uv venv /opt/openhands-venv --python 3.12 && '
            'source /opt/openhands-venv/bin/activate && export SKIP_VSCODE_BUILD=true && '
            'uv pip install --require-hashes -r /opt/openhands-requirements.lock && '
            '/opt/openhands-venv/bin/python -m openhands.core.main --version'))


def agent_factory(harness, settings, *, custom_max_model_calls=None, parent=None):
    if not isinstance(settings, ModelSettings):
        raise ValueError('Validated explicit model settings required')
    if harness not in {'terminus-2', 'openhands', 'C0', 'C1', 'C2'}:
        raise ValueError('Unregistered harness')
    custom = harness.startswith('C')
    if custom:
        from custom_control import Condition
        Condition(harness, parent)
        if type(custom_max_model_calls) is not int or custom_max_model_calls <= 0:
            raise ValueError('Explicit custom controller safety limit required')
    elif parent is not None or custom_max_model_calls is not None:
        raise ValueError('Custom-only options on baseline')

    def create(*, paths, host_api_base, container_api_base, trial_token, agent_timeout_seconds):
        shared = dict(logs_dir=paths.agent_dir, model_name='openai/' + MODEL,
                      temperature=settings.temperature, reasoning_effort=settings.reasoning_effort,
                      model_info=settings.model_info)
        if harness == 'terminus-2':
            return NoRetryTerminus(**shared, api_base=host_api_base,
                llm_kwargs={'api_key': trial_token, 'num_retries': 0, 'timeout': 120},
                llm_call_kwargs={'max_tokens': settings.max_output_tokens,
                    'extra_body': {'reasoning': {'effort': settings.reasoning_effort}}})
        if harness == 'openhands':
            return CompatibleOpenHands(**shared, version='0.62.0', python_version='3.12',
                top_p=1.0,
                api_base=container_api_base, extra_env={'LLM_API_KEY': trial_token, 'LLM_TIMEOUT': '120',
                    'LLM_COMPLETION_KWARGS': repr({'extra_body': {'reasoning': {'effort': settings.reasoning_effort}}})},
                num_retries=0)
        # Import only in the separately pinned Deep Agents environment.
        from custom_harbor_agent import CustomHarborAgent
        return CustomHarborAgent(logs_dir=paths.agent_dir, condition=harness, parent=parent,
            api_base=host_api_base, trial_token=trial_token,
            max_output_tokens=settings.max_output_tokens, max_model_calls=custom_max_model_calls,
            temperature=settings.temperature, reasoning_effort=settings.reasoning_effort,
            trial_timeout_seconds=agent_timeout_seconds)
    create.harness = harness
    create.model_protocol_sha256 = settings.fingerprint()
    return create
