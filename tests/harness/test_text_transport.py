"""Synthetic text/media messages only; no task trajectories or paid provider."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

import httpx
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI

from uts_harness.model import gateway_model
from uts_harness.text_transport import ATTACHMENT_NOTICE, TEXT_PROFILE, TextGatewayChatOpenAI, text_content
from uts_harness.model_protocol import MODEL
from uts_harness.settings import SETTINGS
from uts_harness.sandbox import HarborSandbox
from uts_harness.control import Condition
from uts_harness.controller import CustomRunner


class TextTransportTests(unittest.TestCase):
    def model(self, **overrides):
        return gateway_model('http://127.0.0.1:9/v1', 'synthetic-only',
            max_output_tokens=384000, completion_wait_seconds=60,
            temperature=1., top_p=1., reasoning_effort='high', **overrides)

    def test_legacy_default_is_unchanged(self):
        self.assertIs(type(self.model()), ChatOpenAI)

    def test_explicit_transport_profile_and_protocol(self):
        model = self.model(text_only_transport=True)
        self.assertIsInstance(model, TextGatewayChatOpenAI)
        self.assertEqual(model.profile, TEXT_PROFILE)
        self.assertEqual((model.max_tokens, model.temperature, model.top_p), (384000, 1., 1.))
        self.assertEqual(model.max_retries, 0)
        self.assertEqual(model.extra_body, {'reasoning': {'effort': 'high'}})
        for invalid in (None, 0, 1, 'yes'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.model(text_only_transport=invalid)

    def test_text_is_preserved_and_input_is_not_mutated(self):
        content = [{'type': 'text', 'text': 'alpha'}, 'beta', {'type': 'text', 'text': 'gamma'}]
        before = deepcopy(content)
        self.assertEqual(text_content(content), 'alpha\nbeta\ngamma')
        self.assertEqual(content, before)
        self.assertEqual(text_content('unchanged'), 'unchanged')
        self.assertIsNone(text_content(None))
        self.assertEqual(text_content([]), '')

    def test_attachment_bytes_and_urls_are_never_sent_as_text(self):
        for block in ({'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,SECRET'}},
                      {'type': 'image', 'base64': 'SECRET'},
                      {'type': 'file', 'file': {'file_data': 'SECRET'}},
                      {'type': 'input_audio', 'input_audio': {'data': 'SECRET'}},
                      {'type': 'video', 'url': 'https://private.invalid/SECRET'},
                      {'type': 'unknown', 'text': 'SECRET'}):
            with self.subTest(kind=block['type']):
                self.assertEqual(text_content([block]), ATTACHMENT_NOTICE)

    def test_real_client_serialization_preserves_tool_identity_and_removes_attachment(self):
        model = self.model(text_only_transport=True)
        messages = [HumanMessage(content="Synthetic file read"),
            AIMessage(content="", tool_calls=[{"name": "read_file", "id": "file-read", "args": {"file_path": "/tmp/fixture.png"}}]),
            ToolMessage(content=[{"type": "image_url", "image_url": {"url": "data:image/png;base64,SECRET"}}], tool_call_id="file-read")]
        payload = model._get_request_payload(messages)
        self.assertEqual(payload["messages"][-1]["content"], ATTACHMENT_NOTICE)
        self.assertEqual(payload["messages"][-1]["tool_call_id"], "file-read")
        self.assertEqual(payload["messages"][-2]["tool_calls"][0]["id"], "file-read")
        self.assertNotIn("SECRET", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
