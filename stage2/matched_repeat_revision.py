"""Read-only preservation of the terminal pre-acceptance Terminus attempt.

Pins came from the ONE read-only capture completed 2026-10-02T10:36:27Z.
No old root, unit, lock or state may be repaired, resumed, removed or relabelled.
The tree fingerprint attests current metadata, not historical runtime bytes.
This module contains no operation dispatcher and never grants paid admission.
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import stat
import subprocess

ROOT = Path('/opt/uts-capstone-matched-repeat-terminus-2-20260928')
COMMIT = '4ee7f6672629ec7b22304954ab274e2560c973f0'
SOURCES_SHA = '6913f8f6a7a33cbeda05dffac9ad2092973425a9e967736f8b18e88559173f7c'
UNIT = 'uts-matched-repeat-terminus-2-qualify-ea39c17005796622a42655a89b51ccdc.service'
INVOCATION = '860b6970c2d24766a922be5f7ff977a0'
RT = '.runtime/stage2/'
TERMINAL = RT + 'matched-repeat-qualify-connection'
TREE = {
    "entries": 18160,
    "sha256": "0f3537c1f903bad845cbc6fe947a8b7490d77518e4b05ad32878813aef112b5c"
}
METADATA = {
    "installation-files.json": {
        "bytes": 2552570,
        "identity": [
            "65028",
            "8733865",
            "33152",
            "0",
            "0",
            "1",
            "2552570",
            "1790915406942661933",
            "1790915406942661933"
        ],
        "sha256": "6d6afbec401de3f146fd9303d94d6b5442b3a15c25671a178d1bce7d038a0698"
    },
    "installation-intent.json": {
        "bytes": 193,
        "identity": [
            "65028",
            "8715019",
            "33152",
            "0",
            "0",
            "1",
            "193",
            "1790915130751949757",
            "1790915130751949757"
        ],
        "sha256": "1bfab490ed8efa32d2b176ad4f721b8ce76d35c1fccffffddd8eea69fca3813b"
    },
    "installation-result.json": {
        "bytes": 510,
        "identity": [
            "65028",
            "8733866",
            "33152",
            "0",
            "0",
            "1",
            "510",
            "1790915427742866088",
            "1790915427742866088"
        ],
        "sha256": "95dffabe6ff4a6c4534688d784f43c51a81902dbf4f027269e6771a13a6bbfcf"
    },
    "source-commit.txt": {
        "bytes": 41,
        "identity": [
            "65028",
            "8733864",
            "33152",
            "0",
            "0",
            "1",
            "41",
            "1790915234052964500",
            "1790915234052964500"
        ],
        "sha256": "0fcd2d3bca348840158274722ffb6c24b2d2e64c7d188872f5b5c5a54f210b88"
    }
}
EVIDENCE = {
    "failure-diagnostic.json": {
        "bytes": 119,
        "identity": [
            "65028",
            "8733873",
            "33152",
            "0",
            "0",
            "1",
            "119",
            "1790921801796939994",
            "1790921801796939994"
        ],
        "sha256": "ab62cd27f360dbbb5b9ee51d7f83a3e07aba5877a7ac39a716ad6219131ea1ab"
    },
    "failure.json": {
        "bytes": 610,
        "identity": [
            "65028",
            "8733872",
            "33152",
            "0",
            "0",
            "1",
            "610",
            "1790921801792939955",
            "1790921801792939955"
        ],
        "sha256": "9d28e98ef298a6a0c30edcb6910ca5eb228296098a795e28f3f70d72d0f7907a"
    },
    "intent.json": {
        "bytes": 659,
        "identity": [
            "65028",
            "8733868",
            "33152",
            "0",
            "0",
            "1",
            "659",
            "1790916921965505965",
            "1790916921965505965"
        ],
        "sha256": "36f1a01e3bfa693d3c8983443224c5ed2a623e45e1d43f18e6c1483ad1ca2fef"
    },
    "relay-failure.json": {
        "bytes": 610,
        "identity": [
            "65028",
            "8733871",
            "33152",
            "0",
            "0",
            "1",
            "610",
            "1790921801792939955",
            "1790921801792939955"
        ],
        "sha256": "9d28e98ef298a6a0c30edcb6910ca5eb228296098a795e28f3f70d72d0f7907a"
    },
    "service-started.json": {
        "bytes": 662,
        "identity": [
            "65028",
            "8733870",
            "33152",
            "0",
            "0",
            "1",
            "662",
            "1790917301633223473",
            "1790917301633223473"
        ],
        "sha256": "ee99c5de60237d2b6f0aaeda1cb67f7b940f8404344a1885f125cf0aabc0d38b"
    },
    "service.log": {
        "bytes": 87,
        "identity": [
            "65028",
            "8733869",
            "33152",
            "0",
            "0",
            "1",
            "87",
            "1790921801800940034",
            "1790921801800940034"
        ],
        "sha256": "c2b09a78607ff6a4ba005cd3266f8c16a0d4e5c801498697c44edc3fde919354"
    }
}
LOCAL = {
    ".runtime/netcup/matched-repeat-terminus-2-installation-20260930": {
        "directory_identity": [
            "16777230",
            "128978710",
            "16832",
            "501",
            "20",
            "4",
            "128",
            "1790915458689707988",
            "1790915458689707988"
        ],
        "files": {
            "intent.json": {
                "bytes": 228,
                "identity": [
                    "16777230",
                    "128978711",
                    "33152",
                    "501",
                    "20",
                    "1",
                    "228",
                    "1790914802125845070",
                    "1790914802125845070"
                ],
                "sha256": "86c49ec1b1f922674aed74a6db6652daeb766db30bd0cd52bd66cdf1cde39e71"
            },
            "result.json": {
                "bytes": 510,
                "identity": [
                    "16777230",
                    "128979498",
                    "33152",
                    "501",
                    "20",
                    "1",
                    "510",
                    "1790915458689801320",
                    "1790915458689801320"
                ],
                "sha256": "95dffabe6ff4a6c4534688d784f43c51a81902dbf4f027269e6771a13a6bbfcf"
            }
        }
    },
    ".runtime/netcup/matched-repeat-terminus-2-qualify-20260930": {
        "directory_identity": [
            "16777230",
            "128980844",
            "16832",
            "501",
            "20",
            "5",
            "160",
            "1790922472191507497",
            "1790922472191507497"
        ],
        "files": {
            "failure.json": {
                "bytes": 608,
                "identity": [
                    "16777230",
                    "128987898",
                    "33152",
                    "501",
                    "20",
                    "1",
                    "608",
                    "1790922472191611997",
                    "1790922472191611997"
                ],
                "sha256": "da8468ef47bc1a053bb78e0bf34cd47edfed553c45faad9634ff43d4dfefb24b"
            },
            "intent.json": {
                "bytes": 547,
                "identity": [
                    "16777230",
                    "128980845",
                    "33152",
                    "501",
                    "20",
                    "1",
                    "547",
                    "1790916523793184653",
                    "1790916523793184653"
                ],
                "sha256": "e80d64242feeac59e63ead34e2f9cb1b1edf58d8f7a79d955ec1062985c6a942"
            },
            "receiver.json": {
                "bytes": 662,
                "identity": [
                    "16777230",
                    "128981781",
                    "33152",
                    "501",
                    "20",
                    "1",
                    "662",
                    "1790917301852736016",
                    "1790917301852736016"
                ],
                "sha256": "3cd8a5826ad7986f4c72c6877efe77134911e5e3f5559d727adeb4a4effa7935"
            }
        }
    }
}
ABSENT = ('matched-repeat-qualification-intent.json', 'matched-repeat-qualification-failure.json',
    'matched-repeat-qualification-result.json', 'matched-repeat-matrix.json',
    'matched-repeat-image-build.json', 'matched-repeat-images.json', 'scored-trials',
    'matched-repeat-run-connection', 'operator-stop-request.json', 'provider-stop.json')


def _same(actual, expected):
    if actual != expected: raise ValueError('Retired baseline preservation mismatch')


def _record(raw, identity):
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), identity=[str(v) for v in identity])


def local(repo, mac):
    """Actual protected Darwin files; never cached admission or a native read."""
    for folder, pinned in LOCAL.items():
        path = Path(repo) / folder; parents = mac.directories(path, private=True)
        _same([str(v) for v in mac.identity(path.lstat())], pinned['directory_identity'])
        _same({p.name for p in path.iterdir()}, set(pinned['files']))
        for name, expected in pinned['files'].items():
            _same(_record(*mac.raw(repo, folder + '/' + name, expected['sha256'])), expected)
        _same(mac.directories(path, private=True), parents)
        _same([str(v) for v in mac.identity(path.lstat())], pinned['directory_identity'])
    return dict(kind='retained_failed_baseline_local_not_admission', files=5, paid_launch_ready=False)


def _tree(boot):
    rows = []
    for current, children, names in os.walk(ROOT, followlinks=False):
        base = Path(current); boot.directories(base)
        for name in sorted(children + names):
            path = base / name; item = path.lstat(); boot.acl(path)
            if item.st_uid != os.getuid() or item.st_gid != os.getgid():
                raise ValueError('Retired root ownership changed')
            if stat.S_ISLNK(item.st_mode):
                target = os.readlink(path)
            else:
                if (not (stat.S_ISREG(item.st_mode) or stat.S_ISDIR(item.st_mode))
                        or item.st_mode & 0o7022 or stat.S_ISREG(item.st_mode) and item.st_nlink != 1):
                    raise ValueError('Retired tree protection changed')
                target = None
            rows.append([path.relative_to(ROOT).as_posix(), [str(v) for v in boot.identity(item)], target])
        children[:] = [n for n in children if not (base / n).is_symlink()]
    return dict(entries=len(rows), sha256=boot._fingerprint(sorted(rows)))


def _files(boot):
    boot.directories(ROOT, private=True)
    _same({p.name for p in (ROOT / TERMINAL).iterdir()}, set(EVIDENCE))
    saved = {}
    for name, expected in dict(METADATA, **{TERMINAL + '/' + n: v for n, v in EVIDENCE.items()}).items():
        raw, identity = boot.raw(ROOT, name, expected['sha256'])
        _same(_record(raw, identity), expected); saved[name] = (raw, identity)
    for name in ABSENT:
        if os.path.lexists(ROOT / RT / name): raise ValueError('Retired execution or stop state appeared')
    inventory = boot.loads(saved['installation-files.json'][0])
    _same(set(inventory), {'files', 'runtime'}); _same(len(inventory['files']), 430)
    final = boot.loads(boot.raw(ROOT, boot.FINAL_INPUT, boot.FINAL_SHA)[0])
    names = set(final['sources']) | boot._required(boot.raw(ROOT, 'stage2/matched_repeat_policy.py')[0])
    source_map = {n: inventory['files']['stage2/' + n] for n in names}
    _same(len(source_map), 419); _same(boot._fingerprint(source_map), SOURCES_SHA)
    _same(inventory['files'][boot.FINAL_INPUT], boot.FINAL_SHA)
    _same(inventory['files'][boot.BASELINE_INPUT], boot.BASELINE_SHA)
    identities = {n: boot.raw(ROOT, n, digest)[1] for n, digest in inventory['files'].items()}
    _same(saved['source-commit.txt'][0], (COMMIT + '\n').encode())
    _same(boot.loads(saved['installation-intent.json'][0])['commit'], COMMIT)
    result = boot.loads(saved['installation-result.json'][0])
    _same((result['commit'], result['root'], result['paid_launch_ready']), (COMMIT, str(ROOT), False))
    _same(_tree(boot), TREE)
    return saved, identities


def _manager():
    expected = dict(LoadState='loaded', ActiveState='failed', SubState='failed', MainPID='0',
        ExecMainPID='1970801', Result='exit-code', ExecMainCode='1', ExecMainStatus='1',
        InvocationID=INVOCATION, Restart='no', NRestarts='0', Type='exec',
        RemainAfterExit='yes', WorkingDirectory=str(ROOT), ControlPID='0', ControlGroup='')
    raw = subprocess.check_output(['systemctl', 'show', UNIT, '--property=' + ','.join(expected)],
        text=True, timeout=10)
    pairs = [line.split('=', 1) for line in raw.splitlines() if '=' in line]
    _same(len(pairs), len(expected)); _same(dict(pairs), expected)
    return expected


def _process(pid):
    parts = (Path('/proc') / str(pid) / 'stat').read_bytes().rpartition(b') ')[2].split()
    if len(parts) < 20 or not parts[1].isdigit() or not parts[19].isdigit():
        raise ValueError('Retired process observation uncertain')
    return int(parts[1]), int(parts[19])


def _quiet():
    for pid, start in ((1967904, 109593681), (1970801, 109644236)):
        try: current = _process(pid)
        except (FileNotFoundError, ProcessLookupError): continue
        if current[1] == start: raise ValueError('Recorded retired process remains live')
    exempt = {}; pid = os.getpid()
    while pid > 0:
        if pid in exempt: raise ValueError('Uncertain observer ancestry')
        parent, start = _process(pid); exempt[pid] = start; pid = parent
    for path in Path('/proc').iterdir():
        if not path.name.isdigit(): continue
        try:
            pid = int(path.name); first = _process(pid)
            if exempt.get(pid) == first[1]: continue
            raw = (path / 'cmdline').read_bytes()
            try: cwd = os.readlink(path / 'cwd')
            except FileNotFoundError: cwd = ''
            _same(_process(pid), first)
            if str(ROOT).encode() in raw or cwd == str(ROOT) or cwd.startswith(str(ROOT) + '/'):
                raise ValueError('Unexpected live retired-root process')
        except (FileNotFoundError, ProcessLookupError): continue


def native(boot):
    """Current old evidence/process reads; no historical module import or job."""
    if platform.system() != 'Linux' or os.getuid() != 0 or os.getgid() != 0:
        raise ValueError('Actual native retired-root inspection required')
    first = _manager(); _quiet(); saved, identities = _files(boot)
    _quiet(); _same(_manager(), first)
    _same(_files(boot), (saved, identities))
    return dict(kind='retained_failed_baseline_native_not_admission', source_bindings=419,
        installed_inputs=430, terminal_files=6, tree_identity=dict(TREE),
        qualification_remains_terminal=True, paid_launch_ready=False,
        historical_runtime_bytes_attested=False)
