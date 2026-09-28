"""Isolated, read-only installed-baseline inspection; not a study rehearsal.

This standard-library producer is sent to each deployment's own interpreter.
It reads installed files and constructs the original factories with a dummy
key, but never calls setup(), run(), a tool, Docker or a model. Its observation
is current byte parity, not retrospective proof of historical installed bytes.
"""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import sys
import sysconfig
from types import SimpleNamespace


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def relative_name(name):
    if not isinstance(name, str) or any(c in name for c in ('\\', '\n', '\r', '\x00')):
        raise ValueError('Normalised relative inspection path required')
    relative = PurePosixPath(name)
    if (not name or relative.is_absolute() or str(relative) != name
            or any(part in ('', '.', '..') for part in name.split('/'))):
        raise ValueError('Normalised relative inspection path required')
    return relative


def regular(root, name):
    relative = relative_name(name)
    current = Path(root)
    if current.is_symlink() or not current.is_dir():
        raise ValueError('Regular inspection root required')
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError('Symlinked inspection evidence refused')
    if not stat.S_ISREG(current.stat().st_mode):
        raise ValueError('Regular inspection file required')
    return current


def check_files(root, bindings):
    if not isinstance(bindings, dict) or not bindings:
        raise ValueError('Nonempty pinned inspection inputs required')
    for name, sha in bindings.items():
        if not isinstance(sha, str) or not re.fullmatch('[a-f0-9]{64}', sha):
            raise ValueError('Exact inspection SHA256 required')
        path = regular(root, name)
        if name.startswith('.runtime/'):
            info = path.stat()
            if info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise ValueError('Owned private inspection inputs required')
        if digest(path) != sha:
            raise ValueError('Pinned baseline inspection input changed')


def no_effects(event, args):
    """Defence in depth for this probe, not an OS sandbox or paid admission."""
    if (event.startswith(('socket.', 'subprocess.', 'os.exec', 'os.spawn', 'os.posix_spawn'))
            or event in {'os.system', 'os.fork', 'os.forkpty', 'os.remove', 'os.rename',
                'os.rmdir', 'os.mkdir', 'os.link', 'os.symlink', 'os.truncate',
                'os.chmod', 'os.chown', 'os.utime', 'shutil.copyfile'}):
        raise RuntimeError('Installed-baseline inspection forbids external effects')
    if event == 'open':
        _, mode, flags = args
        if ((isinstance(mode, str) and any(c in mode for c in 'wax+'))
                or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
            raise RuntimeError('Installed-baseline inspection forbids writes')


def installed_tree(site):
    """Hash every installed library/data/metadata file, not just version labels.

    Installer RECORD files are included as bytes, not trusted as the inventory.
    Unrecorded files are therefore included too. Only bytecode caches are
    excluded; scripts outside site-packages and the OS/Python stdlib are not
    claimed by this inventory. Host/image/Python checks remain separate.
    """
    site = Path(site)
    if site.is_symlink() or not site.is_dir():
        raise ValueError('Regular installed library tree required')
    files = {}
    for folder, directories, names in os.walk(site, followlinks=False):
        base = Path(folder)
        for name in directories + names:
            if (base / name).is_symlink():
                raise ValueError('Symlinked installed library refused')
        directories[:] = sorted(name for name in directories if name != '__pycache__')
        for name in sorted(names):
            if name.endswith(('.pyc', '.pyo')):
                continue
            path = regular(site, (base / name).relative_to(site).as_posix())
            files[path.relative_to(site).as_posix()] = digest(path)
    if not files:
        raise ValueError('Installed library tree is empty')
    return files


def versions(site, lock):
    pins = {re.sub('[-_.]+', '-', name).lower(): version for name, version in
        re.findall(r'^([A-Za-z0-9_.-]+)==([^\s\\]+)', lock, re.MULTILINE)}
    required = {'harbor', 'litellm', 'openai', 'httpx', 'httpcore', 'tenacity'}
    if not required.issubset(pins):
        raise ValueError('Pinned baseline host requirements required')
    found = {}
    for distribution in importlib.metadata.distributions(path=[str(site)]):
        name = distribution.metadata.get('Name')
        if not isinstance(name, str) or not name:
            raise ValueError('Installed distribution name is missing')
        name = re.sub('[-_.]+', '-', name).lower()
        if name in found or not distribution.version:
            raise ValueError('Duplicate or invalid installed distribution')
        # Seed installers can be absent from the application lock. Their
        # actual versions and files still have to match across deployments.
        if name not in pins and name not in {'pip', 'setuptools', 'wheel'}:
            raise ValueError('Unpinned installed application distribution')
        if name in pins and distribution.version != pins[name]:
            raise ValueError('Installed version differs from original pinned lock')
        found[name] = distribution.version
    if not required.issubset(found):
        raise ValueError('Required installed baseline libraries are missing')
    return dict(sorted(found.items()))


def controls(root):
    """Actual constructors only, with no provider credentials or execution."""
    from harbor.agents.terminus_2.terminus_2 import Terminus2
    from native_agents import NoRetryTerminus, CompatibleOpenHands
    from recovery_agents import agent_factory
    from retry_policy import SETTINGS

    path = Path(root) / '.runtime/unused-baseline-inspection'
    args = dict(paths=SimpleNamespace(agent_dir=path, trial_dir=path),
        host_api_base='http://127.0.0.1:1/v1', container_api_base='http://127.0.0.1:1/v1',
        trial_token='synthetic-baseline-inspection-no-provider-access',
        agent_timeout_seconds=7200., completion_wait_seconds=7200.)
    terminus = agent_factory('terminus-2', root)(**args)
    openhands = agent_factory('openhands', root)(**args)
    if (type(terminus) is not NoRetryTerminus or type(openhands) is not CompatibleOpenHands
            or NoRetryTerminus._query_llm is not Terminus2._query_llm.__wrapped__
            or terminus._llm.call.__func__ is not type(terminus._llm).call.__wrapped__
            or any(Path(agent.run.__code__.co_filename).resolve() != Path(root) / 'stage2/retry_runtime.py'
                for agent in (terminus, openhands))):
        raise ValueError('Original baseline factories, retry bodies or deadline wrapper differ')
    return dict(model_protocol_sha256=SETTINGS.fingerprint(),
        terminus=dict(model=terminus.model_name, max_turns=terminus._max_episodes,
            parser=terminus._parser_name, summarize=terminus._enable_summarize,
            summarization_free_tokens=terminus._proactive_summarization_threshold,
            tmux_columns=terminus._tmux_pane_width, tmux_rows=terminus._tmux_pane_height,
            temperature=terminus._temperature, reasoning=terminus._reasoning_effort,
            model_info=terminus._llm._model_info, call_kwargs=terminus._llm_call_kwargs,
            num_retries=terminus._llm._llm_kwargs['num_retries'],
            fixture_completion_timeout=terminus._llm._llm_kwargs['timeout']),
        openhands=dict(model=openhands.model_name, version=openhands._version,
            python_version=openhands._python_version, disable_tool_calls=openhands._disable_tool_calls,
            resolved_env=openhands._resolved_env_vars, model_info=openhands._model_info,
            fixture_completion_timeout=openhands._get_env('LLM_TIMEOUT'),
            completion_kwargs=openhands._get_env('LLM_COMPLETION_KWARGS')))


def inspect(root, bindings):
    """Called in a fresh isolated interpreter, never in a scored process."""
    root = Path(root)
    if (platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'amd64')
            or root.is_symlink() or not root.is_absolute()
            or (root / '.venv').is_symlink() or Path(sys.prefix).resolve() != root / '.venv'
            or not sys.flags.isolated or not sys.dont_write_bytecode):
        raise ValueError('Own isolated native deployment interpreter required')
    check_files(root, bindings)
    site = Path(sysconfig.get_path('purelib'))
    if (site != Path(sysconfig.get_path('platlib')) or not site.is_relative_to(root / '.venv')
            or site.resolve() != site):
        raise ValueError('Own installed library directory required')
    before = installed_tree(site)
    packages = versions(site, regular(root, 'stage2/custom-requirements.lock').read_text())
    # -B prevents writes, not reads of existing bytecode. Use an absent cache
    # prefix so library imports below compile the inspected source bytes.
    cache = root / '.runtime/unused-baseline-inspection-bytecode'
    if cache.exists() or cache.is_symlink():
        raise ValueError('Inspection bytecode location must not exist')
    sys.pycache_prefix = str(cache)
    sys.path.insert(0, str(root / 'stage2'))
    sys.addaudithook(no_effects)
    observed = controls(root)
    # Reject modules actually loaded from another checkout or virtualenv.
    for module in tuple(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if not filename:
            continue
        path = Path(filename)
        if 'site-packages' in path.parts:
            if (not path.is_relative_to(site) or path.is_symlink()
                    or path.relative_to(site).as_posix() not in before):
                raise ValueError('Loaded baseline library is outside the inspected byte inventory')
        elif path.name in {PurePosixPath(name).name for name in bindings if name.startswith('stage2/')}:
            if path.is_symlink() or path.resolve() != root / 'stage2' / path.name:
                raise ValueError('Loaded baseline project source is from another deployment')
    if installed_tree(site) != before or versions(site,
            regular(root, 'stage2/custom-requirements.lock').read_text()) != packages:
        raise ValueError('Installed baseline bytes changed during inspection')
    check_files(root, bindings)
    return dict(kind='current_installed_baseline_constructor_observation', root=str(root),
        python=platform.python_version(), site_relative=site.relative_to(root).as_posix(),
        versions=packages, library_files=before, controls=observed, inputs=bindings,
        historical_installed_bytes_attested=False, baseline_execution_qualified=False,
        live_api_calls=0, paid_launch_ready=False)
