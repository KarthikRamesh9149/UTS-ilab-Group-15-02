"""Real Deep Agents + Harbor backend fixture. Scripted model; not frozen C0."""
import asyncio
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import tempfile
import uuid

from deepagents import create_deep_agent, register_harness_profile, HarnessProfile, GeneralPurposeSubagentProfile
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from pydantic import PrivateAttr
from harbor.environments.docker.docker import DockerEnvironment
from harbor.models.task.config import EnvironmentConfig
from harbor.models.trial.paths import TrialPaths
from custom_backend import HarborSandbox
from gateway_policy import MODEL


class ScriptedModel(BaseChatModel):
    model_name: str = MODEL
    _calls: list = PrivateAttr(default_factory=list)
    _tool_names: set = PrivateAttr(default_factory=set)

    @property
    def _llm_type(self):
        return 'openai'

    def _get_ls_params(self, **kwargs):
        return {'ls_provider': 'openai', 'ls_model_name': MODEL, 'ls_model_type': 'chat'}

    def bind_tools(self, tools, **kwargs):
        self._tool_names = {t.name if hasattr(t, 'name') else t['function']['name'] for t in tools}
        if 'task' in self._tool_names or 'write_todos' in self._tool_names:
            raise RuntimeError('Delegation or planning unexpectedly enabled')
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self._calls.append(messages)
        n = len(self._calls)
        if n == 1:
            name, args = 'write_file', {'file_path': '/tmp/custom-fixture.txt', 'content': 'UTS_CUSTOM_OK'}
        elif n == 2:
            name, args = 'execute', {'command': 'cat /tmp/custom-fixture.txt'}
        elif n == 3:
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content='Fixture complete.'))])
        else:
            raise RuntimeError('Unexpected model call')
        if name not in self._tool_names:
            raise RuntimeError('Required tool missing')
        message = AIMessage(content='', tool_calls=[{'name': name, 'args': args, 'id': 'fixture-' + str(n)}])
        return ChatResult(generations=[ChatGeneration(message=message)])


async def main(label):
    root = Path(__file__).resolve().parents[1]
    if not label.isalnum():
        raise ValueError('Alphanumeric evidence label required')
    output = root / ('stage2/custom_agent_probe_' + label + '.json')
    if output.exists():
        raise ValueError('Preserve existing fixture evidence')
    trial = Path(tempfile.mkdtemp(prefix='custom-agent-', dir=root / '.runtime/stage2'))
    name = 'uts-custom-fixture-' + uuid.uuid4().hex[:10]
    environment = DockerEnvironment(environment_dir=root / 'stage2/fixtures', environment_name=name,
        session_id=name, trial_paths=TrialPaths(trial_dir=trial),
        task_env_config=EnvironmentConfig(docker_image='sha256:f5a99e8abc07be76fa4a1bcc11618e055592213648f27366eeef523db8721f25', cpus=2, memory_mb=1024),
        extra_docker_compose=[root / 'stage2/fixtures/docker-compose-isolation.yaml'])
    evidence = {'kind': 'actual_deepagents_harbor_scripted_fixture_not_scored', 'live_api_calls': 0,
                'time_utc': datetime.now(timezone.utc).isoformat(), 'checks': {},
                'versions': {p: importlib.metadata.version(p) for p in ['deepagents', 'langgraph', 'langchain', 'harbor']}}
    try:
        await environment.start(force_build=False)
        backend = HarborSandbox(environment, identifier=name)
        # Explicit full-model registration; no optional delegation or shared
        # store/checkpointer/memory/skills. Planning tools disabled for control.
        register_harness_profile('openai:' + MODEL, HarnessProfile(
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
            excluded_tools=frozenset({'write_todos'})))
        model = ScriptedModel()
        graph = create_deep_agent(model=model, backend=backend,
            system_prompt='Perform the user task inside the supplied container. Report the observed outcome honestly.',
            subagents=[], memory=None, skills=None, store=None, checkpointer=None)
        result = await asyncio.wait_for(graph.ainvoke({'messages': [{'role': 'user',
            'content': 'Create /tmp/custom-fixture.txt containing UTS_CUSTOM_OK and read it back.'}]},
            config={'recursion_limit': 12}), timeout=90)
        read = await environment.exec('cat /tmp/custom-fixture.txt', timeout_sec=10)
        tools = [m for m in result['messages'] if m.type == 'tool']
        evidence['checks'].update(file_created=read.stdout == 'UTS_CUSTOM_OK',
            native_tools_succeeded=len(tools) == 2 and all(m.status == 'success' for m in tools),
            no_delegation='task' not in model._tool_names,
            no_planning_tool='write_todos' not in model._tool_names,
            exactly_three_scripted_calls=len(model._calls) == 3)
        # Exercise bounded foreground execution on the real backend too.
        timed = await backend.aexecute('sleep 10', timeout=.2)
        evidence['checks']['foreground_timeout'] = timed.exit_code == 124
        quoted = await backend.aupload_files([('/tmp/space and quote\' file', b'quoted')])
        downloaded = await backend.adownload_files(['/tmp/space and quote\' file'])
        evidence['checks']['quoted_path_roundtrip'] = quoted[0].error is None and downloaded[0].content == b'quoted'
        evidence['readback'] = {'stdout': read.stdout, 'stderr': read.stderr, 'code': read.return_code}
        evidence['tool_names'] = sorted(model._tool_names)
        evidence['status'] = 'passed' if all(evidence['checks'].values()) else 'failed'
        evidence['limitations'] = ['Not a frozen custom experimental condition.',
            'Polling, interruption, recovery control, context policy and live gateway integration remain outstanding.',
            'Fixture task only; no benchmark or provider quality claims.']
    except Exception as exc:
        evidence.update(status='failed', error_type=type(exc).__name__, error=str(exc)[:1000])
    finally:
        await environment.stop(delete=True)
    with output.open('x') as handle:
        json.dump(evidence, handle, indent=2)
        handle.write('\n')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', default='v2')
    asyncio.run(main(parser.parse_args().label))
