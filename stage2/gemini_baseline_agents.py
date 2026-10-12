"""Native baseline loops with Gemini transport and cached installation only."""
import hashlib
import math
import shlex
import time
from pathlib import Path
from native_agents import NoRetryTerminus, CompatibleOpenHands
from gemini_laptop_policy import MODEL, CONTEXT, MAX_OUTPUT

MODEL_INFO = {'max_input_tokens': CONTEXT - MAX_OUTPUT, 'max_output_tokens': MAX_OUTPUT,
              'max_tokens': CONTEXT, 'input_cost_per_token': 0, 'output_cost_per_token': 0}


def bundle_digest(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


class CachedOpenHands(CompatibleOpenHands):
    def __init__(self, *args, bundle, bundle_sha256, **kwargs):
        self.bundle = Path(bundle)
        if self.bundle.is_symlink() or bundle_digest(self.bundle) != bundle_sha256:
            raise ValueError('OpenHands bundle hash mismatch')
        self.bundle_sha256 = bundle_sha256
        super().__init__(*args, **kwargs)

    async def exec_as_agent(self, environment, command, env=None, **kwargs):
        if env is not None and 'LLM_MODEL' in env:
            env = {**env, 'LITELLM_LOCAL_MODEL_COST_MAP': 'True', 'SKIP_VSCODE_BUILD': 'true'}
            for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS',
                         'NUMEXPR_NUM_THREADS', 'MALLOC_ARENA_MAX'):
                value = self._get_env(name)
                if value is not None:
                    env[name] = value
        return await super().exec_as_agent(environment, command=command, env=env, **kwargs)

    async def install(self, environment):
        await self.ensure_system_dependencies(environment, ('curl', 'git', 'build_tools', 'tmux'))
        await environment.upload_file(source_path=self.bundle, target_path='/tmp/uts-openhands-bundle.tar.gz')
        command = ('set -e; printf "%s  %s\\n" ' + shlex.quote(self.bundle_sha256)
            + ' /tmp/uts-openhands-bundle.tar.gz | sha256sum -c -; '
            'tar -xzf /tmp/uts-openhands-bundle.tar.gz -C /opt; '
            'chmod -R a+rX /opt/openhands-venv /opt/uts-openhands-python; '
            'SKIP_VSCODE_BUILD=true LITELLM_LOCAL_MODEL_COST_MAP=True '
            '/opt/openhands-venv/bin/python -m openhands.core.main --version')
        result = await self.exec_as_root(environment, command=command)
        if result.return_code != 0:
            raise RuntimeError('Cached OpenHands installation failed')


def native_agent(harness, *, logs_dir, api_base, token, timeout, bundle=None, bundle_sha256=None,
                 runtime_cpus=None):
    if (type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0):
        raise ValueError('Explicit positive agent deadline required')
    if not isinstance(token, str) or not token:
        raise ValueError('Trial-scoped gateway token required')
    if runtime_cpus is not None and (type(runtime_cpus) not in (int, float)
            or not math.isfinite(runtime_cpus) or runtime_cpus <= 0):
        raise ValueError('Positive official runtime CPU quota required')
    shared = dict(logs_dir=logs_dir, model_name='openai/' + MODEL,
        temperature=1.0, reasoning_effort='high', model_info=dict(MODEL_INFO))
    if harness == 'terminus-2':
        return NoRetryTerminus(**shared, max_turns=1000000, api_base=api_base,
            llm_kwargs={'api_key': token, 'num_retries': 0, 'timeout': min(600, timeout)},
            llm_call_kwargs={'max_tokens': MAX_OUTPUT, 'top_p': 1.0,
                'extra_body': {'reasoning': {'effort': 'high'}}})
    if harness == 'openhands':
        runtime_env = {}
        if runtime_cpus is not None:
            workers = str(max(1, math.ceil(runtime_cpus)))
            runtime_env = {name: workers for name in ('OPENBLAS_NUM_THREADS',
                'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')}
            runtime_env['MALLOC_ARENA_MAX'] = '2'
        return CachedOpenHands(**shared, bundle=bundle, bundle_sha256=bundle_sha256,
            version='0.62.0', python_version='3.12', api_base=api_base, top_p=1.0,
            num_retries=0, max_iterations=1000000,
            extra_env={'LLM_API_KEY': token, 'LLM_TIMEOUT': str(int(min(600, timeout))),
                **runtime_env,
                'LLM_COMPLETION_KWARGS': repr({'extra_body': {'reasoning': {'effort': 'high'}}}),
                'LITELLM_LOCAL_MODEL_COST_MAP': 'True'})
    raise ValueError('Registered native harness required')


class ActivatedBaseline:
    def __init__(self, agent, gateway, trial_id, timeout):
        self.agent, self.gateway, self.trial_id, self.timeout = agent, gateway, trial_id, timeout

    async def setup(self, environment):
        await self.agent.setup(environment)

    async def run(self, instruction, environment, context):
        self.gateway.activate(self.trial_id, time.monotonic() + self.timeout)
        await self.agent.run(instruction, environment, context)
