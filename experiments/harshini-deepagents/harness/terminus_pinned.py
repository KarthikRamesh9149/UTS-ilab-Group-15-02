"""Harbor's Terminus-2 with the reference model settings, for same-host comparisons.

Prompt, tools, context handling and loop are Harbor's own. Only the connection is
set here, to match the C0 reference runs: DeepSeek V4 Flash 0731 on DeepInfra FP8
via OpenRouter, temperature 1.0, reasoning effort high, 384k max output tokens, and
429/5xx/connection failures retried with backoff until Harbor's task deadline.
"""
from __future__ import annotations

import asyncio
import os
import random
from pathlib import Path
from typing import Any

import litellm
from harbor.agents.terminus_2.terminus_2 import Terminus2
from harbor.models.agent.context import AgentContext

from harness.agent import PINNED_MODEL, PROVIDER_ROUTE

TRANSIENT_ERRORS = (
    litellm.RateLimitError,
    litellm.ServiceUnavailableError,
    litellm.InternalServerError,
    litellm.APIConnectionError,
    litellm.Timeout,
)


class PinnedTerminus2(Terminus2):
    @staticmethod
    def name() -> str:
        return "terminus-2-pinned"

    def version(self) -> str:
        return "0.1.0"

    def __init__(self, logs_dir: Path, model_name: str | None = None, *args: Any, **kwargs: Any) -> None:
        wire = model_name or PINNED_MODEL
        for prefix in ("openrouter/", "openai/"):
            if wire.startswith(prefix):
                wire = wire[len(prefix):]
        if wire != PINNED_MODEL:
            raise ValueError(f"model must be {PINNED_MODEL}, got {wire}")
        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not set")
        kwargs.setdefault("temperature", 1.0)
        kwargs.setdefault("reasoning_effort", "high")
        llm_kwargs = {**(kwargs.pop("llm_kwargs", None) or {}), "api_key": api_key}
        llm_call_kwargs = {
            "max_tokens": 384000,
            "extra_body": {
                "provider": PROVIDER_ROUTE,
                "reasoning": {"effort": kwargs["reasoning_effort"]},
                "usage": {"include": True},
            },
        }
        super().__init__(
            logs_dir, "openrouter/" + PINNED_MODEL, *args,
            llm_kwargs=llm_kwargs, llm_call_kwargs=llm_call_kwargs, **kwargs,
        )
        self._model_retries = 0
        native_call = self._llm.call

        async def call_with_retry(*call_args: Any, **call_kwargs: Any):
            delay = 2.0
            while True:
                try:
                    return await native_call(*call_args, **call_kwargs)
                except TRANSIENT_ERRORS:
                    self._model_retries += 1
                    await asyncio.sleep(delay * random.uniform(0.8, 1.2))
                    delay = min(delay * 2, 60.0)

        self._llm.call = call_with_retry

    async def run(self, instruction: str, environment, context: AgentContext) -> None:
        try:
            await super().run(instruction, environment, context)
        finally:
            context.metadata = {
                **(context.metadata or {}),
                "harness": self.name(),
                "harness_version": self.version(),
                "pinned_model": PINNED_MODEL,
                "model_retries": self._model_retries,
            }
