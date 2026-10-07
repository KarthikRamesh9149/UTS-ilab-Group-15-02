"""Offline model, container and clock fixtures shared by harness tests."""
import json
from types import SimpleNamespace
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from pydantic import PrivateAttr
from uts_harness.model_protocol import MODEL


class FakeEnvironment:
    def __init__(self):
        self.calls = []
        self.output = 'ok'
        self.uploads = []
        self.capture = True

    async def exec(self, command, timeout_sec):
        self.calls.append((command, timeout_sec))
        output = json.dumps({'output': self.output[:64000], 'exit_code': 0, 'truncated': len(self.output) > 64000}) if self.capture else self.output
        return SimpleNamespace(stdout=output, stderr='', return_code=0)

    async def upload_file(self, source, target):
        self.uploads.append((source, target, source.read_bytes()))


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


def completion(summary='Done', checks=None):
    return AIMessage(content='', tool_calls=[{'name': 'complete_task', 'id': 'completion',
        'args': {'summary': summary, 'checks': checks}}])


class SequenceModel(ScriptedModel):
    _sequence: list = PrivateAttr(default_factory=list)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self._calls.append(messages)
        response = self._sequence.pop(0)
        if isinstance(response, Exception):
            raise response
        return ChatResult(generations=[ChatGeneration(message=response)])


class Clock:
    boot_id = 'test-boot'
    now = 100.
    def monotonic(self): return self.now
    def wall(self): return 1800000000. + self.now
