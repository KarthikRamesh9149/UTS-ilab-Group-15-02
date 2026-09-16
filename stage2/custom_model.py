"""Explicit single-model client; only a host loopback gateway is accepted."""
from urllib.parse import urlsplit
from langchain_openai import ChatOpenAI
from gateway_policy import MODEL


def gateway_model(base_url, trial_token, *, max_output_tokens, temperature=None, reasoning_effort=None):
    parsed = urlsplit(base_url)
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1'
            or parsed.path != '/v1' or not parsed.port or parsed.username
            or parsed.password or parsed.query or parsed.fragment):
        raise ValueError('Explicit loopback gateway URL required')
    if not isinstance(trial_token, str) or not trial_token:
        raise ValueError('Explicit trial token required')
    if type(max_output_tokens) is not int or not 0 < max_output_tokens <= 384000:
        raise ValueError('Explicit output bound required')
    options = {}
    if temperature is not None:
        if type(temperature) not in (int, float) or not 0 <= temperature <= 2:
            raise ValueError('Invalid temperature')
        options['temperature'] = temperature
    if reasoning_effort is not None:
        if reasoning_effort not in {'low', 'medium', 'high'}:
            raise ValueError('Invalid reasoning effort')
        options['extra_body'] = {'reasoning': {'effort': reasoning_effort}}
    return ChatOpenAI(model=MODEL, base_url=base_url, api_key=trial_token,
                      max_tokens=max_output_tokens, max_retries=0,
                      timeout=120, streaming=False, use_responses_api=False, **options)
