"""Actual Darwin path wrapper around the unchanged strict baseline byte reader."""
from pathlib import Path

import mac_operator_files as mac
import matched_repeat_archive as archive


def verify(path, data, record, receipt, manifest, sources):
    """Read the same retained archive with real Mac protection, never extract."""
    with mac.opened(Path(path), private=True) as (stream, identity):
        if identity[6] != receipt.get('compressed_bytes'):
            raise ValueError('Exact compressed baseline archive size required')
        result = archive.verify_stream(stream, data, record, receipt, manifest, sources)
        if stream.read(1):
            raise ValueError('Unexpected trailing baseline archive bytes')
    return result
