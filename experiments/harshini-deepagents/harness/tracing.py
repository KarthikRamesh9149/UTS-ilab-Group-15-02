"""Optional Langfuse tracing for one trial.

Active only when LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set (LANGFUSE_HOST
selects the region; the SDK default is the EU cloud). Tracing must never change or end
a run, so every Langfuse call is guarded and failures are only recorded.
"""
from __future__ import annotations

import contextlib
import os
from typing import Any


def enabled() -> bool:
    return bool(os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"))


class TrialTrace:
    """One Langfuse trace per trial: a root `agent` observation, with every model call
    and tool call nested under it through the LangChain callback handler."""

    def __init__(self) -> None:
        self.callbacks: list[Any] = []
        self.trace_id: str | None = None
        self.url: str | None = None
        self.error: str | None = None
        self._client = None
        self._root = None
        self._stack = contextlib.ExitStack()

    def start(self, *, name: str, session_id: str, version: str, tags: list[str],
              metadata: dict[str, str], input: Any) -> None:
        if not enabled():
            return
        try:
            from langfuse import get_client, propagate_attributes
            from langfuse.langchain import CallbackHandler

            self._client = get_client()
            self._root = self._stack.enter_context(
                self._client.start_as_current_observation(name=name, as_type="agent", input=input, version=version)
            )
            self._stack.enter_context(propagate_attributes(
                trace_name=name, session_id=session_id, version=version, tags=tags, metadata=metadata,
            ))
            self.callbacks = [CallbackHandler()]
            self.trace_id = self._client.get_current_trace_id()
            self.url = self._client.get_trace_url(trace_id=self.trace_id)
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"[:300]
            self.callbacks = []
            with contextlib.suppress(Exception):
                self._stack.close()

    def end(self, output: dict[str, Any], failed: bool = False) -> None:
        if self._root is None:
            return
        try:
            self._root.update(output=output, level="ERROR" if failed else None)
        except Exception as exc:
            self.error = self.error or f"{type(exc).__name__}: {exc}"[:300]
        with contextlib.suppress(Exception):
            self._stack.close()

    def flush(self) -> None:
        if self._client is not None:
            with contextlib.suppress(Exception):
                self._client.flush()

    def stats(self) -> dict[str, Any]:
        if not enabled():
            return {}
        return {"langfuse_trace_id": self.trace_id, "langfuse_trace_url": self.url, "langfuse_error": self.error}
