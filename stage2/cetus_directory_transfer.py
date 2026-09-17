"""Bounded regular-file directory transfer; also executed inside the container.

No shell, network, third-party dependencies or unrestricted tar extraction.
Directory trees containing links/devices are rejected, not silently changed.
"""
import io
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import tarfile

MAX_ENTRIES = 4096


def pack(directory, limit):
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Regular directory required')
    buffer = io.BytesIO()
    count = 0
    with tarfile.open(fileobj=buffer, mode='w', format=tarfile.PAX_FORMAT) as archive:
        for base, dirs, files in os.walk(str(root), followlinks=False):
            dirs.sort()
            files.sort()
            for name in dirs + files:
                count += 1
                if count > MAX_ENTRIES:
                    raise ValueError('Too many transfer entries')
                path = Path(base) / name
                metadata = path.lstat()
                relative = path.relative_to(root).as_posix()
                info = tarfile.TarInfo(relative)
                info.mode = stat.S_IMODE(metadata.st_mode) & 0o777
                if stat.S_ISDIR(metadata.st_mode):
                    info.type = tarfile.DIRTYPE
                    archive.addfile(info)
                elif stat.S_ISREG(metadata.st_mode):
                    if metadata.st_size > limit:
                        raise ValueError('Transfer file too large')
                    info.size = metadata.st_size
                    fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                    with os.fdopen(fd, 'rb') as handle:
                        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                            raise ValueError('File changed during transfer')
                        archive.addfile(info, handle)
                else:
                    raise ValueError('Links and special files are unsupported')
                if buffer.tell() > limit:
                    raise ValueError('Directory transfer too large')
    data = buffer.getvalue()
    if len(data) > limit:
        raise ValueError('Directory transfer too large')
    return data


def unpack(data, directory, limit, private=False):
    """Validate entire archive before writes; only a fresh or empty target.

    The trusted controller selects the destination. No existing file is replaced.
    A write failure may leave partial new output for diagnosis, never success.
    """
    if len(data) > limit:
        raise ValueError('Directory transfer too large')
    root = Path(directory)
    if root.is_symlink() or (root.exists() and (not root.is_dir() or any(root.iterdir()))):
        raise ValueError('Directory destination must be fresh or empty')
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as archive:
        members = archive.getmembers()
        if len(members) > MAX_ENTRIES:
            raise ValueError('Too many transfer entries')
        seen, total = {}, 0
        for entry in members:
            path = PurePosixPath(entry.name)
            if path.is_absolute() or '..' in path.parts or not path.parts or '\x00' in entry.name:
                raise ValueError('Unsafe archive path')
            key = path.as_posix()
            if key in seen or not (entry.isdir() or entry.isfile()) or entry.issparse():
                raise ValueError('Duplicate or unsupported archive entry')
            if entry.size < 0:
                raise ValueError('Invalid archive size')
            total += entry.size
            if total > limit:
                raise ValueError('Expanded transfer too large')
            seen[key] = entry
        for name in seen:
            if any(p.as_posix() in seen and not seen[p.as_posix()].isdir()
                   for p in PurePosixPath(name).parents):
                raise ValueError('Archive file used as parent directory')
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        for entry in members:
            target = root / entry.name
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if entry.isdir():
                target.mkdir(mode=0o700, exist_ok=True)
                continue
            fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as output, archive.extractfile(entry) as source:
                remaining = entry.size
                while remaining:
                    chunk = source.read(min(65536, remaining))
                    if not chunk:
                        raise ValueError('Truncated transfer')
                    output.write(chunk)
                    remaining -= len(chunk)
            target.chmod((0o600 | (entry.mode & 0o100)) if private else entry.mode & 0o777)
        # Defer directory permissions until descendants have been written.
        for entry in reversed(members):
            if entry.isdir():
                (root / entry.name).chmod(0o700 if private else entry.mode & 0o777)


if __name__ == '__main__':
    action, directory, raw_limit = sys.argv[1:]
    limit = int(raw_limit)
    if action == 'pack':
        sys.stdout.buffer.write(pack(directory, limit))
    elif action == 'unpack':
        unpack(sys.stdin.buffer.read(limit + 1), directory, limit)
    else:
        raise ValueError('Unknown transfer operation')
