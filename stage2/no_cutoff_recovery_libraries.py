"""Stdlib-only current C0-NC library/constructor producer, not native proof.

The recovery reader sends these exact committed bytes to each installation's
own isolated interpreter. It never installs in the original tree, calls an
agent lifecycle/tool/model, or claims historical installed-byte attestation.
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

ORIGINAL = Path('/opt/uts-capstone-custom-no-cutoff-final-20260928')
RECOVERY = Path('/opt/uts-capstone-custom-no-cutoff-recovery-20260930-r4')
KIND = 'current_C0_NC_library_constructor_observation_not_admission'
_VIOLATION = False
_SOCKET_CONSTRUCTOR_REFUSALS = 0
_ENVIRONMENT = None


def environment(root):
    return dict(PATH='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
        LANG='C.UTF-8', LITELLM_LOCAL_MODEL_COST_MAP='True', LITELLM_MODE='PRODUCTION',
        PYTHON_DOTENV_DISABLED='1', DO_NOT_TRACK='1',
        TIKTOKEN_CACHE_DIR=str(Path(root) / '.venv/lib/python3.12/site-packages/litellm/litellm_core_utils/tokenizers'))


def identity(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid, s.st_nlink,
        s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def relative(name):
    if (type(name) is not str or not name or str(PurePosixPath(name)) != name
            or PurePosixPath(name).is_absolute() or '\\' in name
            or any(p in ('', '.', '..') for p in name.split('/'))
            or any(ord(c) < 32 for c in name)):
        raise ValueError('Normalised inspection path required')
    return name


def acl(path):
    if not hasattr(os, 'listxattr') or any(n in ('system.posix_acl_access', 'system.posix_acl_default')
            for n in os.listxattr(path, follow_symlinks=False)):
        raise ValueError('Actual ACL-free inspection paths required')


def _directory_chain(root, path):
    return [*reversed(root.parents), root,
        *reversed([p for p in path.parents if p != root and p.is_relative_to(root)])]


def protected(root, name):
    root = Path(root); path = root / relative(name)
    directories = _directory_chain(root, path)
    saved = []
    for directory in directories:
        s = directory.lstat()
        # Only the already protected original root permits root-group writes
        # below its private boundary. A new recovery tree has no such exception.
        mask = 0o7002 if root == ORIGINAL and directory.is_relative_to(root / 'stage2') else 0o7022
        ancestor = not directory.is_relative_to(root)
        if (directory.resolve() != directory or directory.is_symlink() or not stat.S_ISDIR(s.st_mode)
                or s.st_uid not in ({0, os.getuid()} if ancestor else {os.getuid()})
                or s.st_gid not in ({0, os.getgid()} if ancestor else {os.getgid()}) or s.st_mode & mask
                or directory == root and stat.S_IMODE(s.st_mode) != 0o700):
            raise ValueError('Protected canonical inspection ancestry required')
        acl(directory); saved.append((str(directory), identity(s)))
    if path.exists() or path.is_symlink(): acl(path)
    return tuple(saved)


def read(root, name, expected=None):
    """Hash/read regular bytes only; no FIFO wait or linked evidence."""
    root = Path(root); protection = protected(root, name); path = root / name
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        before = os.fstat(stream.fileno())
        mask = 0o7002 if root == ORIGINAL and name.startswith('stage2/') else 0o7022
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_uid != os.getuid()
                or before.st_gid != os.getgid() or before.st_mode & mask
                or name.startswith('.runtime/') and stat.S_IMODE(before.st_mode) != 0o600):
            raise ValueError('Owned regular protected inspection file required')
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        after = os.fstat(stream.fileno())
    if (identity(before) != identity(after) or identity(after) != identity(path.lstat())
            or protection != protected(root, name) or expected is not None and digest != expected):
        raise ValueError('Inspection bytes or file identity changed')
    return digest


def check_files(root, bindings):
    if type(bindings) is not dict or not bindings:
        raise ValueError('Actual source/private inspection bindings required')
    for name, sha in bindings.items():
        if type(sha) is not str or not re.fullmatch('[a-f0-9]{64}', sha):
            raise ValueError('Exact inspection SHA256 required')
        read(root, name, sha)


def installed_tree(root, site):
    """All site-package files, including unrecorded files and RECORD bytes."""
    root, site = Path(root), Path(site)
    protected(root, str(site.relative_to(root)) + '/unused-tree-selector')
    if not site.is_dir() or site.resolve() != site:
        raise ValueError('Own regular installed library tree required')
    files = {}
    for folder, directories, names in os.walk(site, followlinks=False):
        base = Path(folder)
        protected(root, base.relative_to(root).as_posix() + '/unused-tree-selector')
        for name in directories + names:
            if (base / name).is_symlink():
                raise ValueError('Symlinked installed library refused')
        directories[:] = sorted(n for n in directories if n != '__pycache__')
        for name in sorted(names):
            if name.endswith(('.pyc', '.pyo')): continue
            path = base / name
            files[path.relative_to(site).as_posix()] = read(root, path.relative_to(root).as_posix())
    if not files: raise ValueError('Installed library inventory is empty')
    return files


def versions(site, lock):
    pins = {re.sub('[-_.]+', '-', n).lower(): v for n, v in
        re.findall(r'^([A-Za-z0-9_.-]+)==([^\s\\]+)', lock, re.MULTILINE)}
    required = {'harbor', 'deepagents', 'langgraph', 'langchain', 'langchain-core',
        'langchain-openai', 'openai', 'httpx'}
    if not required.issubset(pins): raise ValueError('Pinned C0-NC dependency lock required')
    found = {}
    for distribution in importlib.metadata.distributions(path=[str(site)]):
        name = distribution.metadata.get('Name')
        if type(name) is not str or not name: raise ValueError('Distribution identity missing')
        name = re.sub('[-_.]+', '-', name).lower()
        if (name in found or not distribution.version
                or name not in pins and name not in {'pip', 'setuptools', 'wheel'}
                or name in pins and distribution.version != pins[name]):
            raise ValueError('Duplicate, unpinned or changed installed distribution')
        found[name] = distribution.version
    if not required.issubset(found): raise ValueError('Required C0-NC libraries missing')
    return dict(sorted(found.items()))


def no_effects(event, args):
    """Latched defence in depth, not an OS sandbox or paid scope."""
    global _VIOLATION, _SOCKET_CONSTRUCTOR_REFUSALS
    if event == 'socket.__new__':
        # Library import capability probes handle this denial. No socket is
        # created and no network operation occurs. Retain only a count;
        # credential/write/process/connection refusals still latch failure.
        _SOCKET_CONSTRUCTOR_REFUSALS += 1
        raise RuntimeError('Recovery inspection refuses socket construction')
    refused = (event.startswith(('socket.', 'subprocess.', 'os.exec', 'os.spawn', 'os.posix_spawn'))
        or event in {'os.system', 'os.fork', 'os.forkpty', 'os.remove', 'os.rename', 'os.rmdir',
            'os.mkdir', 'os.link', 'os.symlink', 'os.truncate', 'os.chmod', 'os.chown', 'os.utime',
            'shutil.copyfile', 'os.unsetenv'})
    if event == 'open':
        path, mode, flags = args
        name = Path(os.fsdecode(path)).name if isinstance(path, (str, bytes, os.PathLike)) else ''
        refused = (name == '.env' or name.startswith('.env.')
            or name in {'.jwt_secret', 'id_ed25519', 'id_rsa'}
            or isinstance(mode, str) and any(c in mode for c in 'wax+')
            or bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)))
    if event == 'os.putenv':
        key, value = (os.fsdecode(v) for v in args)
        refused = _ENVIRONMENT is None or _ENVIRONMENT.get(key) != value
    if refused:
        _VIOLATION = True
        raise RuntimeError('Recovery library inspection forbids external effects or credentials')


def controls(root):
    """Real original factory construction only, no setup/run/graph/tool call."""
    from no_cutoff_custom_agent import agent_factory, NoCutoffCustomHarborAgent
    from custom_text_transport import TextGatewayChatOpenAI
    from retry_policy import SETTINGS
    path = Path(root) / '.runtime/unused-recovery-constructor-inspection'
    factory = agent_factory(root, 'C0')
    agent = factory(paths=SimpleNamespace(agent_dir=path, trial_dir=path),
        host_api_base='http://127.0.0.1:1/v1', container_api_base='http://127.0.0.1:1/v1',
        trial_token='synthetic-recovery-inspection-no-provider-access',
        agent_timeout_seconds=7200., completion_wait_seconds=7200.)
    if (type(agent) is not NoCutoffCustomHarborAgent or type(agent.model) is not TextGatewayChatOpenAI
            or Path(agent.run.__code__.co_filename).resolve() != Path(root) / 'stage2/retry_runtime.py'
            or agent.used or agent.runner is not None or agent.task_deadline is not None
            or agent.prepared_environment is not None):
        raise ValueError('Exact unexecuted C0-NC construction required')
    client = agent.model
    return dict(factory_harness=factory.harness, parent=factory.custom_parent,
        base_parent=factory.custom_base_parent, version=factory.custom_version,
        design_lever=factory.custom_design_lever, python_runtime_sha256=factory.python_runtime_sha256,
        model_protocol_sha256=SETTINGS.fingerprint(), metadata=agent.execution_metadata(),
        client=dict(kind=type(client).__name__, model=client.model_name,
            temperature=client.temperature, top_p=client.top_p, max_tokens=client.max_tokens,
            max_retries=client.max_retries, fixture_timeout=client.request_timeout,
            extra_body=client.extra_body, streaming=client.streaming,
            use_responses_api=client.use_responses_api, profile=client.profile))


def loaded(root, site, bindings, libraries):
    root, site = Path(root), Path(site); stage = root / 'stage2'
    names = {p.stem for p in stage.glob('*.py')}
    for label, module in tuple(sys.modules.items()):
        filename = getattr(module, '__file__', None)
        if not filename:
            if label in names: raise ValueError('Project module lacks source origin')
            continue
        path = Path(filename).absolute()
        if 'site-packages' in path.parts:
            if (not path.is_relative_to(site) or path.resolve() != path
                    or path.relative_to(site).as_posix() not in libraries):
                raise ValueError('Loaded library outside current inspected bytes')
        elif label in names or path.is_relative_to(stage):
            if path.parent != stage or path.resolve() != path or path.suffix != '.py':
                raise ValueError('Loaded project source from another deployment')
            name = 'stage2/' + path.name
            if name not in bindings: raise ValueError('Unbound loaded project source')
            read(root, name, bindings[name])


def inspect(root, bindings):
    """Fixed source-bound child entry, not a host/service or scored entry."""
    global _ENVIRONMENT
    root = Path(root)
    if (root not in (ORIGINAL, RECOVERY) or platform.system() != 'Linux' or os.getuid() != 0
            or platform.machine() not in ('x86_64', 'amd64') or root.resolve() != root
            or Path(sys.prefix).resolve() != root / '.venv' or (root / '.venv').is_symlink()
            or Path(sys.executable).absolute() != root / '.venv/bin/python'
            or not sys.flags.isolated or not sys.dont_write_bytecode):
        raise ValueError('Own fixed isolated native recovery/original interpreter required')
    _ENVIRONMENT = environment(root)
    if dict(os.environ) != _ENVIRONMENT: raise ValueError('Exact credential-free environment required')
    cache = root / '.runtime/unused-recovery-inspection-bytecode'
    if cache.exists() or cache.is_symlink(): raise ValueError('Inspection bytecode prefix must be absent')
    sys.pycache_prefix = str(cache)
    sys.addaudithook(no_effects)
    check_files(root, bindings)
    site = Path(sysconfig.get_path('purelib'))
    if (site != Path(sysconfig.get_path('platlib')) or not site.is_relative_to(root / '.venv')
            or site.resolve() != site): raise ValueError('Own library directory required')
    before = installed_tree(root, site)
    lock_path = root / 'stage2/custom-requirements.lock'
    lock = lock_path.read_text(); packages = versions(site, lock)
    loaded(root, site, bindings, before)
    sys.path.insert(0, str(root / 'stage2'))
    observed = controls(root)
    loaded(root, site, bindings, before)
    if (installed_tree(root, site) != before or versions(site, lock_path.read_text()) != packages
            or _VIOLATION or dict(os.environ) != _ENVIRONMENT
            or sys.pycache_prefix != str(cache) or cache.exists() or cache.is_symlink()
            or not sys.dont_write_bytecode):
        raise ValueError('Current library bytes or guarded environment changed')
    check_files(root, bindings)
    return dict(kind=KIND, root=str(root), inputs=bindings, python=platform.python_version(),
        site_relative=site.relative_to(root).as_posix(), versions=packages,
        library_files=before, controls=observed, historical_installed_bytes_attested=False,
        denied_socket_constructions=_SOCKET_CONSTRUCTOR_REFUSALS,
        recovery_execution_qualified=False, live_api_calls=0, paid_launch_ready=False)
