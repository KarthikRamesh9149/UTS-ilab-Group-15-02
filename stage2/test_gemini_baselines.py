"""Offline adapter and shared-budget qualification; no provider calls."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from decimal import Decimal
from gemini_baseline_agents import native_agent, bundle_digest, CachedOpenHands, MODEL_INFO
from gemini_baseline_budget import SharedBaselineLedger
from gemini_laptop_policy import MODEL, MAX_OUTPUT, BudgetStop, wire


class AdapterChecks(unittest.TestCase):
    def settings(self, harness, **extra):
        return native_agent(harness, logs_dir=Path('/tmp/synthetic-logs'),
            api_base='http://127.0.0.1:1/v1', token='synthetic-only', timeout=900, **extra)

    def test_terminus_fixed_model_and_no_transport_retries(self):
        with patch('gemini_baseline_agents.NoRetryTerminus') as create:
            self.settings('terminus-2')
        args = create.call_args.kwargs
        self.assertEqual(args['model_name'], 'openai/' + MODEL)
        self.assertEqual(args['llm_kwargs']['num_retries'], 0)
        self.assertEqual(args['llm_kwargs']['timeout'], 600)
        self.assertEqual(args['model_info'], MODEL_INFO)
        self.assertEqual(args['llm_call_kwargs']['max_tokens'], MAX_OUTPUT)
        self.assertEqual(args['reasoning_effort'], 'high')
        self.assertEqual(args['max_turns'], 1000000)

    def test_openhands_uses_same_protocol(self):
        with patch('gemini_baseline_agents.CachedOpenHands') as create:
            self.settings('openhands', bundle=Path('/tmp/bundle'), bundle_sha256='a' * 64)
        args = create.call_args.kwargs
        self.assertEqual(args['model_name'], 'openai/' + MODEL)
        self.assertEqual(args['num_retries'], 0)
        self.assertEqual(args['reasoning_effort'], 'high')
        self.assertEqual(args['temperature'], 1.0)
        self.assertEqual(args['top_p'], 1.0)
        self.assertEqual(args['extra_env']['LLM_TIMEOUT'], '600')
        self.assertEqual(args['version'], '0.62.0')

    def test_unknown_harness_and_invalid_deadlines_fail(self):
        for timeout in (False, 0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                native_agent('terminus-2', logs_dir=Path('/tmp'), api_base='http://localhost',
                    token='fixture', timeout=timeout)
        with self.assertRaises(ValueError):
            self.settings('unknown')

    def test_bundle_hash_failure_precedes_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bundle'
            path.write_bytes(b'synthetic')
            self.assertEqual(bundle_digest(path), hashlib.sha256(b'synthetic').hexdigest())
            with self.assertRaises(ValueError):
                CachedOpenHands(logs_dir=Path(directory), bundle=path, bundle_sha256='0' * 64)

    def test_gateway_keeps_frozen_route_for_native_tools(self):
        body = wire({'model': MODEL, 'messages': [{'role': 'assistant', 'content': None,
            'tool_calls': [{'id': 'fixture', 'type': 'function', 'function': {
                'name': 'finish', 'arguments': '{}'}}]}],
            'tools': [{'type': 'function', 'function': {'name': 'finish', 'parameters': {}}}]})
        self.assertEqual(body['provider']['only'], ['google-ai-studio'])
        self.assertFalse(body['provider']['allow_fallbacks'])
        self.assertEqual(body['max_tokens'], MAX_OUTPUT)

    def test_native_reasoning_alias_preserves_original_wire(self):
        original = {'model': MODEL, 'messages': [{'role': 'user', 'content': 'synthetic'}]}
        self.assertEqual(wire(original), wire({**original, 'reasoning_effort': 'high'}))
        with self.assertRaises(ValueError):
            wire({**original, 'reasoning_effort': 'low'})

    def test_native_text_blocks_accept_only_plain_text(self):
        body = {'model': MODEL, 'messages': [{'role': 'user', 'content': [
            {'type': 'text', 'text': 'Synthetic OpenHands message'}]}]}
        self.assertEqual(wire(body)['messages'], body['messages'])
        for content in ([{'type': 'image_url', 'image_url': {'url': 'https://example.com'}}],
                        [{'type': 'text', 'text': 'x', 'cache_control': {'type': 'ephemeral'}}],
                        [{'type': 'text', 'text': 1}], []):
            with self.assertRaises(ValueError):
                wire({'model': MODEL, 'messages': [{'role': 'user', 'content': content}]})

    def test_empty_native_assistant_content_requires_local_tool_call(self):
        message = {'role': 'assistant', 'content': [], 'tool_calls': [{
            'id': 'fixture', 'type': 'function', 'function': {'name': 'finish', 'arguments': '{}'}}]}
        self.assertEqual(wire({'model': MODEL, 'messages': [message]})['messages'], [message])
        for calls in ([], [{'type': 'image'}], None):
            with self.assertRaises(ValueError):
                wire({'model': MODEL, 'messages': [{**message, 'tool_calls': calls}]})


class BudgetChecks(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.prior_path = self.root / 'original.json'
        self.prior = {'cap_usd': '20', 'requests': [
            {'sequence': 0, 'cost_usd': '11.229632850', 'reserved_usd': '1.10'},
            {'sequence': 1, 'cost_usd': None, 'reserved_usd': '1.10'}]}
        self.prior_path.write_text(json.dumps(self.prior))
        self.hash = hashlib.sha256(self.prior_path.read_bytes()).hexdigest()

    def create(self, **extra):
        settings = dict(prior_path=self.prior_path, prior_sha256=self.hash,
                        cells={'t': 'terminus-2', 'o': 'openhands'})
        settings.update(extra)
        return SharedBaselineLedger(self.root / 'comparison.json', 40, **settings)

    def test_total_cap_and_unknown_charge_survive_new_credit(self):
        ledger = self.create()
        for index in range(6):
            ledger.reserve('t' if index % 2 == 0 else 'o', 40)
        with self.assertRaises(BudgetStop):
            ledger.reserve('t', 40)
        self.assertEqual(ledger.known, Decimal('11.229632850'))
        self.assertEqual(ledger.unresolved, Decimal('7.70'))
        self.assertEqual(ledger.data['cap_usd'], '20')
        self.assertEqual(hashlib.sha256(self.prior_path.read_bytes()).hexdigest(), self.hash)

    def test_only_authoritative_new_cost_releases_new_reservation(self):
        ledger = self.create()
        row = ledger.reserve('t', 40)
        ledger.settle(row, '.01')
        self.assertEqual(ledger.unresolved, Decimal('1.10'))
        self.assertEqual(ledger.known, Decimal('11.239632850'))
        with self.assertRaises(ValueError):
            ledger.settle(ledger.data['requests'][1], 0)

    def test_available_credit_and_registration_stop_before_reservation(self):
        ledger = self.create()
        with self.assertRaises(BudgetStop):
            ledger.reserve('t', '2.19')
        with self.assertRaises(ValueError):
            ledger.reserve('unknown', 40)
        self.assertEqual(len(ledger.data['requests']), 2)

    def test_resume_keeps_exact_prior_prefix(self):
        ledger = self.create()
        ledger.reserve('o', 40)
        loaded = self.create()
        self.assertEqual(loaded.unresolved, Decimal('2.20'))
        loaded.data['requests'][1]['cost_usd'] = '0'
        loaded.save()
        with self.assertRaises(ValueError):
            self.create()

    def test_source_hash_and_separate_path_are_required(self):
        with self.assertRaises(ValueError):
            self.create(prior_sha256='0' * 64)
        with self.assertRaises(ValueError):
            SharedBaselineLedger(self.prior_path, 40, prior_path=self.prior_path,
                prior_sha256=self.hash, cells={'t': 'terminus-2'})

    def test_cap_cannot_be_increased_on_resume(self):
        ledger = self.create()
        ledger.data['cap_usd'] = '40'
        ledger.save()
        with self.assertRaises(ValueError):
            self.create()


if __name__ == '__main__':
    unittest.main()
