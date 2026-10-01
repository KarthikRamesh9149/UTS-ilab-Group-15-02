"""OpenRouter chat client pinned to the Stage 2 model settings.

The model settings below are copied from Karthik Ramesh's Stage 2 code so this
harness is compared on the same model, provider and sampling. Nothing in
stage2/ is imported or modified; the values are duplicated here and cited:

- MODEL, ENDPOINT and the provider-pinning block: stage2/gateway_policy.py
  (``prepare_request``). The ``max_price`` entry is omitted, as in
  stage2/credit_only_gateway.py, which the corrected baselines and C0 used.
- Output allowance, temperature, top_p and reasoning effort:
  stage2/retry_policy.py (``ModelSettings(384000, 1., 'high')``) and
  stage2/model_protocol.py (``top_p`` 1.0, no seed).
- Per-token list prices: stage2/model_protocol.py (``model_info``).
- Retrying only undelivered transient errors, with no retry-count cap, inside
  the official task deadline: stage2/retry_policy.py
  (``physical_request_retry``). The implementation here is my own.

The API key is read from the OPENROUTER_API_KEY environment variable only.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal
import os
from typing import Any, Awaitable, Callable

import httpx

BASE_URL = 'https://openrouter.ai/api/v1'
MODEL = 'deepseek/deepseek-v4-flash-0731'
ENDPOINT = 'deepinfra/fp8'
EXPECTED_PROVIDER = 'DeepInfra'
MAX_OUTPUT_TOKENS = 384_000
TEMPERATURE = 1.0
TOP_P = 1.0
REASONING_EFFORT = 'high'
PROVIDER = {
    'only': [ENDPOINT], 'order': [ENDPOINT], 'allow_fallbacks': False,
    'require_parameters': True, 'quantizations': ['fp8'],
}

# USD per token, uncached. Used only when a response does not report cost.
INPUT_PRICE = Decimal('0.00000006')
OUTPUT_PRICE = Decimal('0.00000018')

# Undelivered transient failures: retried without a count cap. The official
# task deadline (enforced by Harbor cancelling the agent) is the only limit.
RETRY_STATUSES = frozenset({429, 502, 503})
RETRY_EXCEPTIONS = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)
MAX_BACKOFF_SECONDS = 60.0


class ModelError(RuntimeError):
    """A non-retryable model failure. The message never contains the API key."""

    def __init__(self, message: str, *, status: int | None = None, error_type: str | None = None):
        super().__init__(message)
        self.status = status
        self.error_type = error_type


@dataclass
class Completion:
    content: str
    prompt_tokens: int | None
    completion_tokens: int | None
    cached_tokens: int | None
    reported_cost_usd: Decimal | None
    generation_id: str | None
    provider: str | None
    model: str | None
    retries: int


def build_payload(messages: list[dict[str, str]]) -> dict[str, Any]:
    return {
        'model': MODEL,
        'messages': messages,
        'max_tokens': MAX_OUTPUT_TOKENS,
        'temperature': TEMPERATURE,
        'top_p': TOP_P,
        'reasoning': {'effort': REASONING_EFFORT},
        'stream': False,
        'provider': dict(PROVIDER),
    }


def estimate_cost(prompt_tokens: int | None, completion_tokens: int | None) -> Decimal | None:
    """Uncached list-price cost; an upper bound when the provider cached input."""
    if prompt_tokens is None or completion_tokens is None:
        return None
    return prompt_tokens * INPUT_PRICE + completion_tokens * OUTPUT_PRICE


def _int_or_none(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def parse_response(document: dict[str, Any], retries: int) -> Completion:
    choices = document.get('choices')
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ModelError('Response contained no choices')
    message = choices[0].get('message') or {}
    content = message.get('content')
    usage = document.get('usage') if isinstance(document.get('usage'), dict) else {}
    details = usage.get('prompt_tokens_details') if isinstance(usage.get('prompt_tokens_details'), dict) else {}
    cost = usage.get('cost')
    reported = Decimal(str(cost)) if type(cost) in (int, float) and cost >= 0 else None
    return Completion(
        content=content if isinstance(content, str) else '',
        prompt_tokens=_int_or_none(usage.get('prompt_tokens')),
        completion_tokens=_int_or_none(usage.get('completion_tokens')),
        cached_tokens=_int_or_none(details.get('cached_tokens')),
        reported_cost_usd=reported,
        generation_id=document.get('id') if isinstance(document.get('id'), str) else None,
        provider=document.get('provider') if isinstance(document.get('provider'), str) else None,
        model=document.get('model') if isinstance(document.get('model'), str) else None,
        retries=retries,
    )


def _retry_after(response: httpx.Response, attempt: int) -> float:
    header = response.headers.get('retry-after')
    try:
        if header is not None:
            return min(max(float(header), 0.0), MAX_BACKOFF_SECONDS)
    except ValueError:
        pass
    return min(2.0 ** attempt, MAX_BACKOFF_SECONDS)


class OpenRouterClient:
    """Sends one chat completion per ``complete`` call.

    ``transport`` and ``sleep`` exist so tests can run without network access.
    """

    def __init__(self, api_key: str | None = None, *, transport: httpx.AsyncBaseTransport | None = None,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep):
        key = api_key if api_key is not None else os.environ.get('OPENROUTER_API_KEY')
        if not key:
            raise ModelError('OPENROUTER_API_KEY is not set')
        self._headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
        # No read timeout: the official task deadline governs, as in Stage 2.
        self._client = httpx.AsyncClient(base_url=BASE_URL, transport=transport,
                                         timeout=httpx.Timeout(None, connect=30.0))
        self._sleep = sleep

    async def aclose(self) -> None:
        await self._client.aclose()

    async def complete(self, messages: list[dict[str, str]]) -> Completion:
        payload = build_payload(messages)
        attempt = 0
        while True:
            try:
                response = await self._client.post('/chat/completions', json=payload, headers=self._headers)
            except RETRY_EXCEPTIONS:
                await self._sleep(min(2.0 ** attempt, MAX_BACKOFF_SECONDS))
                attempt += 1
                continue
            if response.status_code in RETRY_STATUSES:
                await self._sleep(_retry_after(response, attempt))
                attempt += 1
                continue
            try:
                document = response.json()
            except ValueError:
                raise ModelError(f'Non-JSON response (HTTP {response.status_code})',
                                 status=response.status_code) from None
            if response.status_code != 200 or 'error' in document:
                error = document.get('error') if isinstance(document.get('error'), dict) else {}
                metadata = error.get('metadata') if isinstance(error.get('metadata'), dict) else {}
                raise ModelError(f'Model request failed (HTTP {response.status_code})',
                                 status=response.status_code, error_type=metadata.get('error_type'))
            return parse_response(document, attempt)
