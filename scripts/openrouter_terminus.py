"""Terminus-2 compatibility adapter for OpenRouter credentials.

Harbor 0.22.0 does not declare a model connection for its built-in
Terminus-2 agent. This adapter resolves the key from Harbor's agent
environment and passes it to LiteLLM in memory, without putting the key in
agent kwargs or committed configuration.
"""

import os
from pathlib import Path
from typing import Any

import litellm
from harbor.agents.terminus_2.terminus_2 import Terminus2


class OpenRouterTerminus2(Terminus2):
    """Terminus-2 with explicit, environment-backed OpenRouter credentials."""

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        api_base: str | None = None,
        llm_kwargs: dict[str, Any] | None = None,
        extra_env: dict[str, str] | None = None,
        key_file: str | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        env = extra_env or {}
        api_key = env.get("OPENROUTER_API_KEY")
        if api_key and api_key.startswith("${") and api_key.endswith("}"):
            api_key = None
        api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            path = Path(key_file).expanduser() if key_file else Path.home() / ".openrouter_api_key"
            if path.is_file():
                api_key = path.read_text(encoding="utf-8").strip()
        if not api_key:
            raise ValueError(
                "OpenRouter key must be supplied through the environment or ~/.openrouter_api_key"
            )

        # Terminus-2's LiteLLM wrapper can rely on LiteLLM's process-global key
        # rather than forwarding the constructor kwarg to the provider adapter.
        litellm.api_key = api_key
        os.environ["OPENROUTER_API_KEY"] = api_key

        resolved_base = (
            api_base
            or env.get("OPENROUTER_BASE_URL")
            or os.environ.get("OPENROUTER_BASE_URL")
            or "https://openrouter.ai/api/v1"
        )
        resolved_kwargs = dict(llm_kwargs or {})
        resolved_kwargs["api_key"] = api_key
        headers = dict(resolved_kwargs.get("extra_headers") or {})
        headers.setdefault("Authorization", f"Bearer {api_key}")
        resolved_kwargs["extra_headers"] = headers

        super().__init__(
            logs_dir=logs_dir,
            model_name=model_name,
            api_base=resolved_base,
            llm_kwargs=resolved_kwargs,
            extra_env=extra_env,
            *args,
            **kwargs,
        )

    @staticmethod
    def name() -> str:
        return "terminus-2-openrouter"

    def version(self) -> str:
        return "2.0.0-openrouter-adapter"
