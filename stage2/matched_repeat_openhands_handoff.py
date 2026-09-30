"""OpenHands-context consumer of the unchanged original-final subframe.

The archived frame still identifies ONLY its original custom dependency. Its
bytes, anchors, strict archive algorithm and real original native collector are
unchanged. This separate consumer adds the genuinely live completed-Terminus
witness and constructs the real two-block OpenHands lineage. It never opens a
Terminus session or calls the archived reader with a false deployment context.
"""
from copy import deepcopy
import os
import threading
import weakref

import matched_repeat_amended_handoff as original
import matched_repeat_terminus_handoff as terminus
import matched_repeat_policy as policy

KIND = 'live_original_and_terminus_for_openhands_not_admission'
_WITNESSES = weakref.WeakKeyDictionary()


class _Witness:
    __slots__ = ('__weakref__',)

    def __reduce__(self):
        raise TypeError('Live OpenHands predecessor witnesses cannot be saved or copied')


def invalidate(witness):
    if type(witness) is _Witness: _WITNESSES.pop(witness, None)


def _live(witness):
    if type(witness) is not _Witness or witness not in _WITNESSES:
        raise ValueError('Actual live OpenHands predecessor witness required')
    state = _WITNESSES[witness]
    try:
        if (state['pid'] != os.getpid() or state['thread'] != threading.get_ident()
                or state['task'] is None or state['task'] is not original._task()
                or threading.current_thread() is not threading.main_thread()):
            raise ValueError('OpenHands predecessor cannot cross lifetime, process, thread or task')
        terminus._live(state['terminus'])
        return state
    except BaseException:
        invalidate(witness); raise


def _record(value, verified, earlier):
    retained = terminus.recheck(earlier)
    if retained['operator_commit'] != value['document']['operator_commit']:
        raise ValueError('Actual original and Terminus captures must share a committed revision')
    lineage = deepcopy(value['document']['predecessors'])
    original.archive._same(lineage, terminus._live(earlier)['data']['predecessors'])
    lineage['successor_harness'] = 'openhands'; lineage['blocks'].append(retained['block'])
    policy.validate_predecessors(lineage, terminus._live(earlier)['manifest'], 'openhands')
    record = original._record('openhands', value, verified)
    record.update(kind=KIND, predecessors=lineage, completed_terminus=retained)
    return record


def authenticate(root, baseline, final, harness, stream, earlier):
    root = terminus._context(root, harness); original.wire.pipe_only(stream)
    terminus._live(earlier); original._no_stop(root)
    header, digest = original.wire.read_header(stream)
    # The helper validates the historical dependency envelope, not an
    # execution harness. Current source/private reads use the REAL OH root.
    value = original._anchors(root, baseline, final, 'terminus-2', header)
    original._check(root, value)
    verified = original.archive.verify_stream(stream, value['data'], value['backup']['receipt'])
    original.archive._same(verified, value['backup']['verification'])
    trailer = original.wire.COMMIT + digest + bytes.fromhex(verified['sha256'])
    if original.wire._exact(stream, len(trailer)) != trailer or stream.read(1):
        raise ValueError('All three real commitments and exact original/transport EOF required')
    original._check(root, value)
    fresh = original._native_audit(value)  # Real collector, before all successor locks.
    original.archive.validate_snapshot(fresh, value['anchors'])
    original.archive._same(original.operator._audit_hash(fresh), original.operator._audit_hash(value['data']))
    if original.archive._utc(fresh['collected_utc']) < original.archive._utc(value['data']['collected_utc']):
        raise ValueError('Actual original audit cannot predate the retained snapshot')
    if original._anchors(root, baseline, final, 'terminus-2', header) != value:
        raise ValueError('Original predecessor bytes changed during OpenHands authentication')
    original._check(root, value)
    witness = _Witness()
    _WITNESSES[witness] = dict(pid=os.getpid(), thread=threading.get_ident(), task=original._task(),
        root=root, harness=harness, header=deepcopy(header), terminus=earlier,
        record=_record(value, verified, earlier))
    return witness


def recheck(root, baseline, final, harness, witness):
    state = _live(witness)
    try:
        root = terminus._context(root, harness)
        if root != state['root'] or harness != state['harness']:
            raise ValueError('OpenHands witness belongs to another actual root')
        value = original._anchors(root, baseline, final, 'terminus-2', state['header'])
        original._check(root, value)
        observed = _record(value, state['record']['streamed_backup'], state['terminus'])
        original.archive._same(observed, state['record'])
        return deepcopy(state['record'])
    except BaseException:
        invalidate(witness); raise
