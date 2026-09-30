"""Prove the separate baseline reader retains the archived phase algorithm."""
import ast
from pathlib import Path
import unittest

import matched_repeat_phase as phase

STAGE = Path(__file__).resolve().parent


class PhaseParityTests(unittest.TestCase):
    def test_ast_has_only_explicit_baseline_identity_guard_and_trace_identity_delta(self):
        old = ast.parse((STAGE/'no_cutoff_final_phase_audit.py').read_bytes())
        new = ast.parse((STAGE/'matched_repeat_phase.py').read_bytes())
        previous = next(n for n in old.body if isinstance(n, ast.FunctionDef) and n.name == '_phase_row')
        current = next(n for n in new.body if isinstance(n, ast.FunctionDef) and n.name == 'read')
        guard = ast.parse("if (result.get('harness') not in ('terminus-2', 'openhands') "
            "or result.get('model_protocol_sha256') != MODEL):\n"
            " raise ValueError('Exact original baseline identity and model required')").body[0]
        self.assertEqual(ast.dump(current.body[1]), ast.dump(guard))
        current.body.pop(1); current.name = previous.name
        class IdentityOnly(ast.NodeTransformer):
            def visit_Constant(self, node):
                if node.value == 'C0-NC':
                    return ast.parse("identity['harness']", mode='eval').body
                if node.value == 'Trace identity differs from retained final result':
                    return ast.Constant(value='Trace identity differs from retained baseline result')
                return node
        previous = IdentityOnly().visit(previous)
        self.assertEqual(ast.dump(previous), ast.dump(current))

    def test_rejects_custom_unknown_or_wrong_model_before_reading_any_phase(self):
        for result in ({'harness':'C0-NC','model_protocol_sha256':phase.MODEL},
                {'harness':'caller-selected','model_protocol_sha256':phase.MODEL},
                {'harness':'terminus-2','model_protocol_sha256':'0'*64},
                {'harness':'openhands','model_protocol_sha256':'0'*64}):
            with self.subTest(result=result), self.assertRaisesRegex(ValueError, 'baseline identity'):
                phase.read(result, [], None, [], 0, {})
