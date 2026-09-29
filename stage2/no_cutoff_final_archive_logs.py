"""Read-only protection for extra registered agent/verifier archive payloads.

Not an evidence reader, permission editor, collector or admission mechanism.
Required audit evidence always uses the unchanged strict private-file checks.
"""
import os
from pathlib import Path, PurePosixPath
import re
import stat

import no_cutoff_final_guard as guard

PREFIX = ('.runtime', 'stage2', 'scored-trials')
FAMILIES = frozenset({'agent', 'verifier'})
EXCLUDED = frozenset({'token', '.env', '.jwt_secret', 'id_ed25519', 'id_rsa', '__pycache__', '.DS_Store'})


def contract():
    return dict(kind='protected_registered_extra_logs_archive_v1',
        scope='extra_agent_and_verifier_payloads_only', required_evidence_permissions_unchanged=True,
        private_boundary_modes=['0700'], log_root_modes=['0700', '0777'],
        nested_directory_modes=['0700'], agent_file_modes=['0600'],
        verifier_file_modes=['0600', '0644', '0660'],
        root_owner_and_group_required=True, acl_and_links_refused=True,
        source_permissions_modified=False, payloads_hash_copy_only=True,
        archive_directory_mode='0700', archive_file_mode='0600',
        historical_payload_bytes_attested=False, full_runtime_restore_exercised=False)


def applies(name, trials):
    if not isinstance(name, str): return False
    parts = name.split('/')
    return (len(parts) >= 5 and tuple(parts[:3]) == PREFIX
        and parts[3] in trials and parts[4] in FAMILIES)


def _check(path):
    state = path.lstat()
    if (path.is_symlink() or path.resolve() != path or state.st_uid != guard.OWNER
            or state.st_gid != guard.GROUP or state.st_mode & 0o7000):
        raise ValueError('Protected owned log path required')
    guard._acl(path)
    return state


def protection(root, name, trials):
    """Actual protected ancestors and payload identities, never chmod/chown."""
    root = Path(root)
    if (root != guard.ROOT or not root.is_absolute() or not applies(name, trials)
            or not re.fullmatch(r'[A-Za-z0-9_.\-/]+', name)
            or PurePosixPath(name).is_absolute() or str(PurePosixPath(name)) != name
            or any(p in ('', '.', '..') or p in EXCLUDED or p.startswith('.env.') for p in name.split('/'))):
        raise ValueError('Only registered non-credential extra log payloads permitted')
    saved = []
    parent = root.parent; state = _check(parent)
    if not stat.S_ISDIR(state.st_mode) or state.st_mode & 0o022:
        raise ValueError('Protected execution parent required')
    saved.append((str(parent), guard.identity(state)))
    parts = name.split('/'); current = root
    for index, part in enumerate([None, *parts]):
        if part is not None: current /= part
        state = _check(current)
        if index <= 4:
            if not stat.S_ISDIR(state.st_mode) or stat.S_IMODE(state.st_mode) != 0o700:
                raise ValueError('Exact private root/runtime/registered-trial boundary required')
        elif stat.S_ISDIR(state.st_mode):
            modes = (0o700, 0o777) if index == 5 else (0o700,)
            if stat.S_IMODE(state.st_mode) not in modes:
                raise ValueError('Only the fixed log roots may be container-writable')
        else:
            if index != len(parts):
                raise ValueError('Regular log file cannot replace an ancestor')
            file_protection(name, state, trials)
        saved.append((str(current), guard.identity(state)))
    return tuple(saved)


def file_protection(name, state, trials):
    if not applies(name, trials) or len(name.split('/')) < 6:
        raise ValueError('Extra file below a registered log root required')
    modes = (0o600,) if name.split('/')[4] == 'agent' else (0o600, 0o644, 0o660)
    if (not stat.S_ISREG(state.st_mode) or state.st_nlink != 1
            or state.st_uid != guard.OWNER or state.st_gid != guard.GROUP
            or stat.S_IMODE(state.st_mode) not in modes):
        raise ValueError('Exact owned single-link log-file protection required')
