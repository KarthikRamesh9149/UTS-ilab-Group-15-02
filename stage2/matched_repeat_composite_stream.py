"""Exact original-frame adapter plus final commitment over both handoffs.

The unchanged archived reader still receives its exact original bytes and
EOF. That EOF is exposed only after the real outer sender's final commitment
and transport EOF, so a late recovery-source refusal cannot admit a baseline.
Descriptor type is not peer authentication; the pinned service supplies that.
"""
import hashlib
import json
import os
import re
import struct

import matched_repeat_stream as wire

END=b'UTS-BASELINE-COMPOSITE-COMMIT-V1\n'


def _hash(value):
    if type(value) is not str or not re.fullmatch('[a-f0-9]{64}',value):
        raise ValueError('Exact composite archive/document checksum required')
    return bytes.fromhex(value)


def finish(stream,recovery_sha256,original):
    wire.pipe_only(stream)
    if (type(original) is not dict or set(original)!={'kind','operator_document_sha256','archive_sha256','paid_launch_ready'}
            or original['kind']!='amended_off_server_predecessor_bytes_sent_not_admission'
            or original['paid_launch_ready'] is not False):
        raise ValueError('Exact original sender completion required')
    wire._write(stream,END+_hash(recovery_sha256)+_hash(original['operator_document_sha256'])+_hash(original['archive_sha256']))
    stream.flush()


class _OriginalFrame:
    def __init__(self,stream,header,remaining,footer):
        self.stream=stream;self.header=header;self.remaining=remaining;self.footer=footer;self.finished=False
        state=os.fstat(stream.fileno());self.identity=(state.st_dev,state.st_ino,state.st_mode)

    def fileno(self):return self.stream.fileno()

    def _current(self):
        state=os.fstat(self.fileno())
        if (state.st_dev,state.st_ino,state.st_mode)!=self.identity:
            raise ValueError('Actual composite descriptor identity changed')

    def read(self,size=-1):
        self._current()
        if type(size) is not int:raise ValueError('Integer original stream read size required')
        if size==0:return b''
        size=wire.CHUNK if size<0 else min(size,wire.CHUNK)
        if self.header:
            raw=self.header[:size];self.header=self.header[len(raw):];return raw
        if self.remaining:
            raw=wire._exact(self.stream,min(size,self.remaining));self.remaining-=len(raw)
            self._current();return raw
        if not self.finished:
            if wire._exact(self.stream,len(self.footer))!=self.footer or self.stream.read(1):
                raise ValueError('Final composite sender commitment and exact transport EOF required')
            self._current();self.finished=True
        return b''


def original_frame(stream,recovery_sha256):
    """Read the actual post-audit original header before any ancestor checks."""
    wire.pipe_only(stream);_hash(recovery_sha256)
    before=os.fstat(stream.fileno());identity=(before.st_dev,before.st_ino,before.st_mode)
    prefix=wire._exact(stream,len(wire.MAGIC)+8)
    if prefix[:len(wire.MAGIC)]!=wire.MAGIC:raise ValueError('Actual original handoff header required')
    size=struct.unpack('!Q',prefix[-8:])[0]
    if not 0<size<=wire.METADATA_LIMIT:raise ValueError('Original metadata parser window exceeded')
    raw=wire._exact(stream,size);header=wire.loads(raw)
    if type(header.get('backup')) is not str or type(header.get('operator')) is not dict:
        raise ValueError('Actual original backup and operator header required')
    receipt=wire.loads(header['backup']).get('receipt')
    if type(receipt) is not dict:
        raise ValueError('Actual original compressed archive receipt required')
    count=receipt.get('compressed_bytes')
    if type(count) is not int or count<=0:raise ValueError('Exact original compressed frame length required')
    document_sha=hashlib.sha256(json.dumps(header['operator'],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    footer=END+_hash(recovery_sha256)+_hash(document_sha)+_hash(receipt.get('sha256'))
    after=os.fstat(stream.fileno())
    if (after.st_dev,after.st_ino,after.st_mode)!=identity:raise ValueError('Original frame descriptor replaced')
    return _OriginalFrame(stream,prefix+raw,count+len(wire.COMMIT)+64,footer)
