"""Current-source/import coverage tests, not native historical attestation."""
from copy import deepcopy
import ast
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import no_cutoff_final_dependencies as dependencies
import no_cutoff_final_report as report
import no_cutoff_final_archive as archive
import test_no_cutoff_final_archive as fixtures


class ClosureTests(unittest.TestCase):
    def test_transitive_unbound_import_refuses_even_when_entry_is_bound(self):
        files = {'stage2/entry.py': b'import helper', 'stage2/helper.py': b'import missing'}
        with self.assertRaisesRegex(ValueError, 'Unbound'):
            dependencies._closure(files, {'entry', 'helper', 'missing'}, ('entry',))
        files['stage2/missing.py'] = b'import os'
        self.assertEqual(dependencies._closure(files, {'entry', 'helper', 'missing'}, ('entry',)),
            ['entry', 'helper', 'missing'])

    def test_conditional_class_and_try_imports_are_conservatively_included(self):
        raw = b'if False:\n import a\ntry:\n import b\nexcept Exception:\n import c\nclass X:\n import d\n'
        self.assertEqual(dependencies._imports(raw), {'a', 'b', 'c', 'd'})

    def test_fixed_deferred_native_reader_imports_are_all_closure_roots(self):
        tree = ast.parse(Path(report.__file__).read_bytes())
        entry = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_native')
        names = set()
        for node in ast.walk(entry):
            if isinstance(node, ast.Import): names.update(v.name.split('.')[0] for v in node.names)
            elif isinstance(node, ast.ImportFrom): names.add(node.module.split('.')[0])
        self.assertEqual(names - {'harbor'}, set(dependencies.NATIVE_MODULES))

    def test_deferred_imports_need_explicit_roots_and_loaded_runtime_checks(self):
        raw = b'def later():\n import hidden\n'
        self.assertEqual(dependencies._imports(raw), set())
        with self.assertRaises(ValueError):
            dependencies._closure({'stage2/entry.py': raw}, {'entry', 'hidden'}, ('entry', 'hidden'))

    def test_relative_import_is_not_silently_ignored(self):
        with self.assertRaises(ValueError): dependencies._imports(b'from . import hidden')

    def test_current_five_hashes_match_sources_without_historical_claim(self):
        base = Path(__file__).resolve().parent.parent
        for name, sha in dependencies.FILES.items():
            self.assertEqual(hashlib.sha256((base / name).read_bytes()).hexdigest(), sha)
        value = dependencies.contract()
        self.assertEqual(len(value['files']), 5)
        self.assertFalse(value['historical_installed_bytes_attested'])
        self.assertFalse(value['original_qualification_modified'])
        value['files'].clear(); self.assertEqual(len(dependencies.FILES), 5)


class LoadedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(self.tmp).resolve(); self.reporting = self.root / 'reporting'
        self.reporting.mkdir(); (self.root / 'stage2').mkdir()
        self.enterContext(patch.object(report, 'ROOT', self.root))
        self.enterContext(patch.object(report, 'REPORTING', self.reporting))
        self.files = {}
        for name, sha in dependencies.FILES.items():
            target = self.root / name
            target.write_bytes((Path(dependencies.__file__).parent / Path(name).name).read_bytes())
            target.chmod(0o600); self.files[name] = sha
        self.modules = {'helper': NS(__file__=str(self.root / next(iter(self.files))))}
        self.enterContext(patch.object(report.sys, 'modules', self.modules))

    def test_current_helper_is_bound_without_changing_original_sources(self):
        proof = {'sources': {}}; report._loaded(proof, {})
        self.assertEqual(proof, {'sources': {}})

    def test_unknown_loaded_project_helper_is_rejected(self):
        self.modules['extra'] = NS(__file__=str(self.root / 'stage2/unbound.py'))
        with self.assertRaisesRegex(ValueError, 'Unbound'): report._loaded({'sources': {}}, {})

    def test_wrong_root_and_changed_helper_are_rejected(self):
        name = next(iter(self.files)); self.modules['helper'].__file__ = str(self.reporting / Path(name).name)
        with self.assertRaises(ValueError): report._loaded({'sources': {}}, {})
        self.modules['helper'].__file__ = str(self.root / name)
        (self.root / name).write_bytes(b'# changed')
        with self.assertRaises(ValueError): report._loaded({'sources': {}}, {})


class SnapshotDependencyTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.ArchiveTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)

    def test_helpers_are_separate_support_and_archive_members_not_qualification(self):
        data = self.f.data
        self.assertEqual(data['reporting_dependencies'], dependencies.contract())
        for name, sha in dependencies.FILES.items():
            self.assertEqual(data['supporting_file_sha256'][name], sha)
            self.assertNotIn(name.removeprefix('stage2/'), data['sources'])
            self.assertIn(name, self.f.members)
        self.f.verify()

    def test_old_schema_and_retrospective_attestation_are_rejected(self):
        for transform in (lambda d: d.pop('reporting_dependencies'),
                lambda d: d['reporting_dependencies'].update(historical_installed_bytes_attested=True),
                lambda d: d.update(kind='completed_c0_nc_final89_phase_amendment_v1')):
            data = deepcopy(self.f.data); transform(data)
            with self.assertRaises(ValueError): archive.validate_snapshot(data, self.f.anchors)

    def test_missing_changed_or_extra_current_helper_fails(self):
        name = next(iter(dependencies.FILES))
        for change in (lambda d: d['supporting_file_sha256'].pop(name),
                lambda d: d['supporting_file_sha256'].update({name: '0' * 64}),
                lambda d: d['reporting_dependencies']['files'].update({'stage2/extra.py': '0' * 64})):
            data = deepcopy(self.f.data); change(data)
            with self.assertRaises(ValueError): archive.validate_snapshot(data, self.f.anchors)
        with self.assertRaises(ValueError): self.f.verify(omit={name})

    def test_changed_helper_during_audit_is_not_accepted(self):
        path = self.f.root / next(iter(dependencies.FILES))
        def mutate(*args): path.write_bytes(b'# mutation')
        self.f.f.native.original.authenticate.side_effect = mutate
        with self.assertRaises(ValueError): report.collect()
