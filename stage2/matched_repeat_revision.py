"""Read-only preservation of both terminal pre-acceptance Terminus attempts.

Pins came from the read-only captures completed 2026-10-02T10:36:27Z and
2026-10-03T01:03:04Z, never from a retried qualification.
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
SECOND_ROOT = Path('/opt/uts-capstone-matched-repeat-terminus-2-20261002-r2')
# Exact read-only capture returned 2026-10-03T01:03:04.174230Z.
SECOND = dict(root=SECOND_ROOT, **{
    "commit": "56d0ab602e4c516513da56f2fd204105d4e11966",
    "sources_sha": "77ba99952a112d6f5e8b85cc334956ed8faac19979963f12a299150730a0cddc",
    "source_count": 424,
    "input_count": 435,
    "unit": "uts-matched-repeat-terminus-2-qualify-4d22b6ee82841c72f1dc7e2de236814c.service",
    "invocation": "94d60ba0aced40f0bd623bc2fd8bc66a",
    "processes": [
        [
            2020947,
            112731229
        ],
        [
            2023803,
            112784983
        ]
    ],
    "metadata": {
        "installation-files.json": {
            "bytes": 2553148,
            "identity": [
                "65028",
                "8752031",
                "33152",
                "0",
                "0",
                "1",
                "2553148",
                "1790946560755199604",
                "1790946560755199604"
            ],
            "sha256": "4cf67cf0e3e2dd7dfa6596a225c2849de2e2e85efa3acbb707a7bc8731c1b1f6"
        },
        "installation-intent.json": {
            "bytes": 193,
            "identity": [
                "65028",
                "8733875",
                "33152",
                "0",
                "0",
                "1",
                "193",
                "1790946287288399653",
                "1790946287288399653"
            ],
            "sha256": "e79db0fd781962e33c02c5f08d9e7e5cc58375368bc6658f76005895fb25c47d"
        },
        "installation-result.json": {
            "bytes": 513,
            "identity": [
                "65028",
                "8752032",
                "33152",
                "0",
                "0",
                "1",
                "513",
                "1790946581399410672",
                "1790946581399410672"
            ],
            "sha256": "bf3b401e8175f3f4540c100782cc76fef8f04199a93b32b07ddc9bb3ac8ceaf0"
        },
        "source-commit.txt": {
            "bytes": 41,
            "identity": [
                "65028",
                "8752030",
                "33152",
                "0",
                "0",
                "1",
                "41",
                "1790946383173382346",
                "1790946383173382346"
            ],
            "sha256": "5dad6a1324c37943a8808b82849bee4368e709fd9fad2d6a4adb3931da1bee23"
        }
    },
    "evidence": {
        "failure-diagnostic.json": {
            "bytes": 123,
            "identity": [
                "65028",
                "8752038",
                "33152",
                "0",
                "0",
                "1",
                "123",
                "1790954685747519042",
                "1790954685747519042"
            ],
            "sha256": "0a45f44e9444d9e858716077e4a9e049a8037295039499655d9ffe3be732471a"
        },
        "failure.json": {
            "bytes": 613,
            "identity": [
                "65028",
                "8752037",
                "33152",
                "0",
                "0",
                "1",
                "613",
                "1790954685743519001",
                "1790954685743519001"
            ],
            "sha256": "6f639a4524235ea4d7de1d7d94009203bf8a6bee3eacaa7114882d2a113b2aee"
        },
        "intent.json": {
            "bytes": 662,
            "identity": [
                "65028",
                "8752034",
                "33152",
                "0",
                "0",
                "1",
                "662",
                "1790948319553303341",
                "1790948319553303341"
            ],
            "sha256": "c1230be9d7b07a99b7c3904cbd19d21812c73e24d07d3f174292fd847e6ddce4"
        },
        "service-started.json": {
            "bytes": 665,
            "identity": [
                "65028",
                "8752036",
                "33152",
                "0",
                "0",
                "1",
                "665",
                "1790948726529468611",
                "1790948726529468611"
            ],
            "sha256": "4de1379205bdb737f8b8f9ba1beeea585063f66d13632c3a4c4a4e0f23e4b170"
        },
        "service.log": {
            "bytes": 3041,
            "identity": [
                "65028",
                "8752035",
                "33152",
                "0",
                "0",
                "1",
                "3041",
                "1790954685751519083",
                "1790954685751519083"
            ],
            "sha256": "a69aa6dacaf7d8a87d935110aeb55f391b0f5d78b454432a487b4dd3e84b298a"
        }
    },
    "tree": {
        "entries": 18164,
        "sha256": "ca78f3713389834724b0e98f0b7421c319c38d641d1049fcad1b83b9edac4abd"
    }
})
LOCAL.update({
    ".runtime/netcup/matched-repeat-terminus-2-installation-20261002-r2": {
        "directory_identity": [
            "16777230",
            "130860727",
            "16832",
            "501",
            "20",
            "4",
            "128",
            "1790946612920315164",
            "1790946612920315164"
        ],
        "files": {
            "intent.json": {
                "bytes": 228,
                "sha256": "13a6b43b66d389b65736b39d1ff7fed1ee5757a9bfb66ddc09d541ad184a6db3",
                "identity": [
                    "16777230",
                    "130860728",
                    "33152",
                    "501",
                    "20",
                    "1",
                    "228",
                    "1790945937035174580",
                    "1790945937035174580"
                ]
            },
            "result.json": {
                "bytes": 513,
                "sha256": "bf3b401e8175f3f4540c100782cc76fef8f04199a93b32b07ddc9bb3ac8ceaf0",
                "identity": [
                    "16777230",
                    "130861334",
                    "33152",
                    "501",
                    "20",
                    "1",
                    "513",
                    "1790946612920417456",
                    "1790946612920417456"
                ]
            }
        }
    },
    ".runtime/netcup/matched-repeat-terminus-2-qualify-20261002-r2": {
        "directory_identity": [
            "16777230",
            "130862281",
            "16832",
            "501",
            "20",
            "5",
            "160",
            "1790954687170751661",
            "1790954687170751661"
        ],
        "files": {
            "intent.json": {
                "bytes": 550,
                "sha256": "bda249b05fcbf2ef62870be32e0df52a75ae1db6e21a96694eb3513a082e62f4",
                "identity": [
                    "16777230",
                    "130862282",
                    "33152",
                    "501",
                    "20",
                    "1",
                    "550",
                    "1790947898434460662",
                    "1790947898434460662"
                ]
            },
            "receiver.json": {
                "bytes": 665,
                "sha256": "36c00a268193fd064dcd3c0982dae0c2743d5abf980b38632f8711e1458c8d66",
                "identity": [
                    "16777230",
                    "130863654",
                    "33152",
                    "501",
                    "20",
                    "1",
                    "665",
                    "1790948726768141995",
                    "1790948726768141995"
                ]
            },
            "failure.json": {
                "bytes": 611,
                "sha256": "e06ea9ff7c14656879c98d28d7acdf341b74de45859525eaf0ae60b69c3e8df5",
                "identity": [
                    "16777230",
                    "130868629",
                    "33152",
                    "501",
                    "20",
                    "1",
                    "611",
                    "1790954687171245956",
                    "1790954687171245956"
                ]
            }
        }
    }
})
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
    return dict(kind='retained_failed_baseline_local_not_admission',
        files=sum(len(v['files']) for v in LOCAL.values()), paid_launch_ready=False)


def _first():
    return dict(root=ROOT, commit=COMMIT, sources_sha=SOURCES_SHA, source_count=419, input_count=430,
        unit=UNIT, invocation=INVOCATION, processes=((1967904, 109593681), (1970801, 109644236)),
        metadata=METADATA, evidence=EVIDENCE, tree=TREE)


def _tree(boot, root=None):
    root = ROOT if root is None else root
    rows = []
    for current, children, names in os.walk(root, followlinks=False):
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
            rows.append([path.relative_to(root).as_posix(), [str(v) for v in boot.identity(item)], target])
        children[:] = [n for n in children if not (base / n).is_symlink()]
    return dict(entries=len(rows), sha256=boot._fingerprint(sorted(rows)))


def _files(boot, attempt=None):
    attempt = _first() if attempt is None else attempt
    root = attempt['root']
    boot.directories(root, private=True)
    _same({p.name for p in (root / TERMINAL).iterdir()}, set(attempt['evidence']))
    saved = {}
    for name, expected in dict(attempt['metadata'], **{TERMINAL + '/' + n: v for n, v in attempt['evidence'].items()}).items():
        raw, identity = boot.raw(root, name, expected['sha256'])
        _same(_record(raw, identity), expected); saved[name] = (raw, identity)
    for name in ABSENT:
        if os.path.lexists(root / RT / name): raise ValueError('Retired execution or stop state appeared')
    inventory = boot.loads(saved['installation-files.json'][0])
    _same(set(inventory), {'files', 'runtime'}); _same(len(inventory['files']), attempt['input_count'])
    final = boot.loads(boot.raw(root, boot.FINAL_INPUT, boot.FINAL_SHA)[0])
    names = set(final['sources']) | boot._required(boot.raw(root, 'stage2/matched_repeat_policy.py')[0])
    source_map = {n: inventory['files']['stage2/' + n] for n in names}
    _same(len(source_map), attempt['source_count']); _same(boot._fingerprint(source_map), attempt['sources_sha'])
    _same(inventory['files'][boot.FINAL_INPUT], boot.FINAL_SHA)
    _same(inventory['files'][boot.BASELINE_INPUT], boot.BASELINE_SHA)
    identities = {n: boot.raw(root, n, digest)[1] for n, digest in inventory['files'].items()}
    _same(saved['source-commit.txt'][0], (attempt['commit'] + '\n').encode())
    _same(boot.loads(saved['installation-intent.json'][0])['commit'], attempt['commit'])
    result = boot.loads(saved['installation-result.json'][0])
    _same((result['commit'], result['root'], result['paid_launch_ready']), (attempt['commit'], str(root), False))
    _same(_tree(boot, root), attempt['tree'])
    return saved, identities


def _manager(attempt=None):
    attempt = _first() if attempt is None else attempt
    expected = dict(LoadState='loaded', ActiveState='failed', SubState='failed', MainPID='0',
        ExecMainPID=str(attempt['processes'][-1][0]), Result='exit-code', ExecMainCode='1', ExecMainStatus='1',
        InvocationID=attempt['invocation'], Restart='no', NRestarts='0', Type='exec',
        RemainAfterExit='yes', WorkingDirectory=str(attempt['root']), ControlPID='0', ControlGroup='')
    raw = subprocess.check_output(['systemctl', 'show', attempt['unit'], '--property=' + ','.join(expected)],
        text=True, timeout=10)
    pairs = [line.split('=', 1) for line in raw.splitlines() if '=' in line]
    _same(len(pairs), len(expected)); _same(dict(pairs), expected)
    return expected


def _process(pid):
    parts = (Path('/proc') / str(pid) / 'stat').read_bytes().rpartition(b') ')[2].split()
    if len(parts) < 20 or not parts[1].isdigit() or not parts[19].isdigit():
        raise ValueError('Retired process observation uncertain')
    return int(parts[1]), int(parts[19])


def _quiet(attempt=None):
    attempt = _first() if attempt is None else attempt
    root = attempt['root']
    for pid, start in attempt['processes']:
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
            if str(root).encode() in raw or cwd == str(root) or cwd.startswith(str(root) + '/'):
                raise ValueError('Unexpected live retired-root process')
        except (FileNotFoundError, ProcessLookupError): continue


def native(boot):
    """Current old evidence/process reads; no historical module import or job."""
    if platform.system() != 'Linux' or os.getuid() != 0 or os.getgid() != 0:
        raise ValueError('Actual native retired-root inspection required')
    attempts = (_first(), SECOND)
    saved = []
    for attempt in attempts:
        manager = _manager(attempt); _quiet(attempt)
        saved.append((manager, _files(boot, attempt)))
    for attempt, (manager, observed) in zip(attempts, saved):
        _quiet(attempt); _same(_manager(attempt), manager)
        _same(_files(boot, attempt), observed)
    return dict(kind='retained_failed_baseline_native_not_admission',
        attempts=[dict(root=str(a['root']), source_bindings=a['source_count'],
            installed_inputs=a['input_count'], terminal_files=len(a['evidence']), tree_identity=dict(a['tree']))
            for a in attempts],
        qualification_remains_terminal=True, paid_launch_ready=False,
        historical_runtime_bytes_attested=False)
