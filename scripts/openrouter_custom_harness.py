"""OpenRouter-backed custom harness for the Remith Gemini experiment."""

from pathlib import Path
from typing import Any

from openai import AsyncOpenAI
from scripts.custom_harness import QwenCustomHarness


class GeminiOpenRouterHarness(QwenCustomHarness):
    """Reuse the bounded Harbor loop with a private OpenRouter key file."""

    def __init__(
        self,
        *args: Any,
        api_base: str = "https://openrouter.ai/api/v1",
        api_key_file: str | None = None,
        **kwargs: Any,
    ) -> None:
        key_path = (
            Path(api_key_file).expanduser()
            if api_key_file
            else Path.home() / ".openrouter_api_key"
        )
        if not key_path.is_file():
            raise ValueError(f"OpenRouter key file not found: {key_path}")
        api_key = key_path.read_text(encoding="utf-8").strip()
        if not api_key:
            raise ValueError(f"OpenRouter key file is empty: {key_path}")
        super().__init__(
            *args,
            api_base=api_base,
            api_key=api_key,
            **kwargs,
        )
        self._client = AsyncOpenAI(
            base_url=api_base,
            api_key=api_key,
            default_headers={"Authorization": f"Bearer {api_key}"},
        )

    @staticmethod
    def name() -> str:
        return "uts-gemini-openrouter-harness"

    def version(self) -> str:
        return "1.0.0"
