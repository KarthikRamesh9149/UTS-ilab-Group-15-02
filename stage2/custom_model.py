"""Explicit single-model client; only a host loopback gateway is accepted."""
from urllib.parse import urlsplit
from langchain_openai import ChatOpenAI
from completion_wait import validate_completion_wait
from gateway_policy import MODEL


def gateway_model(base_url, trial_token, *, max_output_tokens, completion_wait_seconds,
                  temperature=None, reasoning_effort=None, top_p=None, text_only_transport=False):
    completion_wait_seconds = validate_completion_wait(completion_wait_seconds)
    parsed = urlsplit(base_url)
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1'
            or parsed.path != '/v1' or not parsed.port or parsed.username
            or parsed.password or parsed.query or parsed.fragment):
        raise ValueError('Explicit loopback gateway URL required')
    if not isinstance(trial_token, str) or not trial_token:
        raise ValueError('Explicit trial token required')
    if type(max_output_tokens) is not int or not 0 < max_output_tokens <= 384000:
        raise ValueError('Explicit output bound required')
    if type(text_only_transport) is not bool:
        raise ValueError('Explicit text-only transport selection required')
    client_type = ChatOpenAI
    options = {}
    if text_only_transport:
        from custom_text_transport import TextGatewayChatOpenAI, TEXT_PROFILE
        client_type = TextGatewayChatOpenAI
        options['profile'] = dict(TEXT_PROFILE)
    if temperature is not None:
        if type(temperature) not in (int, float) or not 0 <= temperature <= 2:
            raise ValueError('Invalid temperature')
        options['temperature'] = temperature
    if reasoning_effort is not None:
        if reasoning_effort not in {'low', 'medium', 'high'}:
            raise ValueError('Invalid reasoning effort')
        options['extra_body'] = {'reasoning': {'effort': reasoning_effort}}
    if top_p is not None:
        if type(top_p) not in (int, float) or not 0 < top_p <= 1:
            raise ValueError('Invalid top_p')
        options['top_p'] = top_p
    return client_type(model=MODEL, base_url=base_url, api_key=trial_token,
                      max_tokens=max_output_tokens, max_retries=0,
                      timeout=completion_wait_seconds, streaming=False, use_responses_api=False, **options)
