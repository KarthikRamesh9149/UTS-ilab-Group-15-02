"""Harbor's Terminus-2 with the reference model settings, for same-host comparisons.

Prompt, tools, context handling and loop are Harbor's own. Only the connection is
set here, to match the C0 reference runs: DeepSeek V4 Flash 0731 on DeepInfra FP8
via OpenRouter, temperature 1.0, reasoning effort high, 384k max output tokens, and
429/5xx/connection failures retried with backoff until Harbor's task deadline.
Other models from `harness.agent.MODEL_SETTINGS` are allowed for the cross-model check.
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

from harness.agent import resolve_model

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
        wire, settings = resolve_model(model_name)
        self._wire = wire
        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not set")
        kwargs.setdefault("temperature", 1.0)
        kwargs.setdefault("reasoning_effort", "high")
        llm_kwargs = {**(kwargs.pop("llm_kwargs", None) or {}), "api_key": api_key}
        llm_call_kwargs = {
            "max_tokens": settings["max_output_tokens"],
            "extra_body": {
                "provider": settings["route"],
                "reasoning": {"effort": kwargs["reasoning_effort"]},
                "usage": {"include": True},
            },
        }
        super().__init__(
            logs_dir, "openrouter/" + wire, *args,
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
                "pinned_model": self._wire,
                "model_retries": self._model_retries,
            }
