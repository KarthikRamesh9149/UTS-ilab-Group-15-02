"""Immutable model settings and request validation."""
from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import stat

MODEL = 'deepseek/deepseek-v4-flash-0731'
CANONICAL_MODEL = 'deepseek/deepseek-v4-flash-20260731'
ENDPOINT = 'deepinfra/fp8'


@dataclass(frozen=True)
class ModelSettings:
    max_output_tokens: int
    temperature: float
    reasoning_effort: str

    def __post_init__(self):
        if type(self.max_output_tokens) is not int or not 0 < self.max_output_tokens <= 384000:
            raise ValueError('Explicit provider output bound required')
        if type(self.temperature) not in (int, float) or not 0 <= self.temperature <= 2:
            raise ValueError('Explicit finite temperature required')
        if self.reasoning_effort not in {'low', 'medium', 'high'}:
            raise ValueError('Explicit qualified reasoning effort required')

    @property
    def model_info(self):
        return {'max_input_tokens': 1048576, 'max_output_tokens': self.max_output_tokens,
                'input_cost_per_token': .00000006, 'output_cost_per_token': .00000018,
                'cache_read_input_token_cost': .000000015, 'cache_creation_input_token_cost': 0}

    def document(self):
        return dict(schema_version=1, model=MODEL, endpoint=ENDPOINT, top_p=1.0, **asdict(self))

    def fingerprint(self):
        return hashlib.sha256(json.dumps(self.document(), sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def enforce(self, request):
        if request.get('model') != MODEL or type(request.get('max_tokens')) is not int or not 0 < request['max_tokens'] <= self.max_output_tokens:
            raise ValueError('Model or output protocol drift')
        if type(request.get('temperature')) not in (int, float) or request['temperature'] != self.temperature:
            raise ValueError('Temperature protocol drift')
        if request.get('reasoning') != {'effort': self.reasoning_effort}:
            raise ValueError('Reasoning protocol drift')
        if 'seed' in request or ('top_p' in request and (type(request['top_p']) not in (int, float) or request['top_p'] != 1.0)):
            raise ValueError('Sampling protocol drift')
        result = deepcopy(request)
        # Uniform documented default for clients that omit nucleus sampling.
        result['top_p'] = 1.0
        return result


def read_protocol(runtime):
    path = Path(runtime) / 'model-protocol.json'
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise ValueError('Private regular model protocol required')
    document = json.loads(path.read_text())
    settings = ModelSettings(document['max_output_tokens'], document['temperature'], document['reasoning_effort'])
    if document != settings.document():
        raise ValueError('Unsupported model protocol')
    return settings


def freeze_protocol(runtime, settings):
    from .private_io import durable_json
    if not isinstance(settings, ModelSettings):
        raise ValueError('Explicit validated model settings required')
    try:
        durable_json(Path(runtime) / 'model-protocol.json', settings.document())
    except FileExistsError:
        pass
    if read_protocol(runtime).document() != settings.document():
        raise ValueError('Existing study model protocol is immutable')
    return settings.fingerprint()
