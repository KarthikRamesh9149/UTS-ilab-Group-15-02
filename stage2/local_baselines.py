"""Prepared native baseline configuration; no launch or provider requests.

Does not import the historical OpenRouter factory. Endpoint reachability,
native installation and enforcement by a trial gateway need live qualification.
"""
from urllib.parse import urlsplit
from local_study import LocalProtocol


def local_api_base(value):
    parsed = urlsplit(value)
    if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', '::1') or
            not parsed.port or parsed.username or parsed.password or parsed.query or
            parsed.fragment or parsed.path != '/v1'):
        raise ValueError('Explicit loopback trial-gateway URL ending /v1 required')
    return value


def baseline_config(harness, *, api_base, trial_token, protocol=None):
    p = protocol or LocalProtocol()
    if not isinstance(p, LocalProtocol) or harness not in ('terminus-2', 'openhands'):
        raise ValueError('Frozen protocol and registered native baseline required')
    if not isinstance(trial_token, str) or not trial_token or '\n' in trial_token or '\r' in trial_token:
        raise ValueError('Trial-scoped credential required')
    common = dict(model_name='openai/' + p.model, api_base=local_api_base(api_base),
                  temperature=p.temperature, model_info={'max_input_tokens': p.context_tokens - p.max_output_tokens,
                  'max_output_tokens': p.max_output_tokens, 'max_tokens': p.context_tokens,
                  'input_cost_per_token': 0, 'output_cost_per_token': 0})
    if harness == 'terminus-2':
        return dict(common, llm_kwargs={'api_key': trial_token, 'num_retries': 0, 'timeout': 120},
                    llm_call_kwargs={'max_tokens': p.max_output_tokens, 'top_p': p.top_p,
                                     'extra_body': {'top_k': p.top_k}})
    return dict(common, version='0.62.0', python_version='3.12', top_p=p.top_p, num_retries=0,
                reasoning_effort='', extra_env={'LLM_API_KEY': trial_token, 'LLM_TIMEOUT': '120',
                    'LLM_COMPLETION_KWARGS': repr({'extra_body': {'top_k': p.top_k}})})


def create_baseline(harness, *, logs_dir, api_base, trial_token):
    # Constructors only. No change to native prompts, tools or reasoning loops.
    import os
    from pathlib import Path
    import shlex
    import types
    os.environ.setdefault('LITELLM_LOCAL_MODEL_COST_MAP', 'True')
    from harbor.agents.terminus_2.terminus_2 import Terminus2
    from harbor.agents.installed.openhands import OpenHands

    class LocalTerminus(Terminus2):
        def _init_llm(self, *args, **kwargs):
            client = super()._init_llm(*args, **kwargs)
            client.call = types.MethodType(type(client).call.__wrapped__, client)
            return client

    class LocalOpenHands(OpenHands):
        async def install(self, environment):
            # Reuse the existing hash-locked native OpenHands dependency set.
            # This changes installation compatibility, not the native agent loop.
            await self.ensure_system_dependencies(environment, ('curl', 'git', 'build_tools', 'tmux'))
            user = str(environment.default_user or 'root')
            await self.exec_as_root(environment, command='mkdir -p /opt/openhands-venv && chown ' +
                                    shlex.quote(user + ':' + user) + ' /opt/openhands-venv')
            await environment.upload_file(Path(__file__).with_name('openhands-requirements.lock'),
                                          '/opt/openhands-requirements.lock')
            await self.exec_as_root(environment, command='chmod 644 /opt/openhands-requirements.lock')
            await self.exec_as_agent(environment, command=(
                'set -euo pipefail; curl -LsSf https://astral.sh/uv/install.sh | sh && '
                'if [ -f "$HOME/.local/bin/env" ]; then source "$HOME/.local/bin/env"; fi && '
                'uv python install 3.12 && uv venv /opt/openhands-venv --python 3.12 && '
                'source /opt/openhands-venv/bin/activate && export SKIP_VSCODE_BUILD=true && '
                'uv pip install --require-hashes -r /opt/openhands-requirements.lock && '
                '/opt/openhands-venv/bin/python -m openhands.core.main --version'))

        async def exec_as_agent(self, environment, command, env=None, **kwargs):
            if env is not None and 'LLM_MODEL' in env:
                env = dict(env)
                env.pop('LLM_REASONING_EFFORT', None)
                for name in ('LLM_COMPLETION_KWARGS', 'LLM_TIMEOUT'):
                    env[name] = self._get_env(name)
            return await super().exec_as_agent(environment, command=command, env=env, **kwargs)

    config = baseline_config(harness, api_base=api_base, trial_token=trial_token)
    cls = LocalTerminus if harness == 'terminus-2' else LocalOpenHands
    return cls(logs_dir=logs_dir, **config)
