"""Fixed CURRENT reporting dependencies; never historical qualification proof.

Standard library only so the source-bound bootstrap can check import closure
before importing project modules or writing an exclusive reporting deployment.
"""
import ast
from pathlib import Path

ORIGINAL_COMMIT = 'fb2d5cc569745e3087a9b3c7b65e695aebc5c0a3'
FILES = {
    'stage2/setup_probe.py': '2067bff9b38bbab912c52691b6b6f76b624234c70ab9f63aa4861f3eb12cd0d9',
    'stage2/extended_token_calibration.py': '51461f8dcdd94882313ad5e733f911f83caa284a37d4f75e229ee8dad5014daf',
    'stage2/calibrate_tokenizer.py': '96ea02bc5108e3603162a988d969a2ab78cfb2077c06b97f7bfeffe940ecccf9',
    'stage2/final_schedule.py': 'b8875605865bf4429eea0b1142936720f54fe835704222a816d4e8b0bd9869d5',
    'stage2/freeze_inputs.py': '65c9a6659b7f248657a21789b1c2ee92f41a7bb17a06c69f34f35f5b31698787'}
NATIVE_MODULES = ('no_cutoff_final_study', 'no_cutoff_final_runtime',
    'no_cutoff_final_policy', 'no_cutoff_final_evidence', 'run_no_cutoff_final',
    'credit_only_accounting', 'qualify_oracle')
CLOSURE_ROOTS = (*NATIVE_MODULES, 'no_cutoff_final_report',
    'no_cutoff_final_archive', 'no_cutoff_final_backup')


def contract():
    return dict(kind='current_reporting_dependencies_not_historical_attestation_v1',
        files=dict(FILES), original_git_revision=ORIGINAL_COMMIT,
        original_qualification_modified=False, historical_installed_bytes_attested=False,
        current_bytes_must_be_reread=True)


def _imports(raw):
    """Conservative module-level imports, including conditional/try/class code.

Function bodies are not executed by import. The fixed collector's deferred
reader imports are explicit roots; dynamic runtime imports need loaded checks.
"""
    pending = list(ast.parse(raw).body); names = set()
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Import):
            names.update(v.name.split('.')[0] for v in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                raise ValueError('Unreviewed relative project import in reporting closure')
            if node.module: names.add(node.module.split('.')[0])
        pending.extend(ast.iter_child_nodes(node))
    return names


def _closure(raw_sources, project_names, roots=CLOSURE_ROOTS):
    """AST-only coverage. All bytes must already be checked by the caller."""
    modules = {Path(n).stem: raw for n, raw in raw_sources.items()
        if n.startswith('stage2/') and n.endswith('.py') and n.count('/') == 1}
    if len(modules) != sum(n.startswith('stage2/') and n.endswith('.py') and n.count('/') == 1
            for n in raw_sources):
        raise ValueError('Ambiguous project module source inventory')
    pending = list(roots); seen = set()
    while pending:
        name = pending.pop()
        if name in seen: continue
        if name not in modules:
            raise ValueError('Unbound project module in transitive reporting import closure')
        seen.add(name)
        pending.extend(_imports(modules[name]) & set(project_names) - seen)
    return sorted(seen)
