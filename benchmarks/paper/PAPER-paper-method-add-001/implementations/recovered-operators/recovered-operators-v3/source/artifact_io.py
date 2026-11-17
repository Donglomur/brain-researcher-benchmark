"""Actual bounded file capture. Scientific imports belong only in explicit workers."""
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import stat


class Refused(ValueError):
    pass


def require(value, message):
    if not value:
        raise Refused(message)


def integer(value, minimum=0):
    require(type(value) is int and value >= minimum, 'exact bounded integer')
    return value


def relative(value):
    require(type(value) is str and value and '\\' not in value and '\x00' not in value,
            'ordinary relative path')
    p = PurePosixPath(value)
    require(not p.is_absolute() and str(p) == value and not set(p.parts) & {'.', '..'},
            'canonical relative path')
    return value


def strict_json(raw):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, 'duplicate JSON key')
            out[key] = value
        return out
    def invalid(value):
        raise Refused('nonfinite JSON number')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=unique, parse_constant=invalid)


def json_bytes(value):
    return (json.dumps(value, allow_nan=False, sort_keys=True, indent=2) + '\n').encode()


def identity(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


@dataclass(frozen=True)
class Pin:
    bytes: int
    sha256: str

    def __post_init__(self):
        integer(self.bytes)
        require(type(self.sha256) is str and len(self.sha256) == 64 and
                all(c in '0123456789abcdef' for c in self.sha256), 'exact SHA256')

    @classmethod
    def parse(cls, value):
        require(type(value) is dict and set(value) == {'bytes', 'sha256'}, 'closed pin')
        return cls(**value)

    def check(self, raw):
        require(identity(raw) == {'bytes': self.bytes, 'sha256': self.sha256}, 'captured identity')


class Failures:
    """Raw occurrence ownership; a cleanup error never replaces an earlier error."""
    def __init__(self):
        self.occurrences = []

    def add(self, operation, error):
        self.occurrences.append((operation, error, error.__traceback__))

    def attempt(self, operation, function, *args):
        try:
            return function(*args)
        except BaseException as error:
            self.add(operation, error)

    def raise_first(self):
        if self.occurrences:
            _, error, traceback = self.occurrences[0]
            raise error.with_traceback(traceback)

    def metadata(self):
        return [{'operation': label, 'type': type(error).__name__, 'occurrence': i}
                for i, (label, error, _) in enumerate(self.occurrences)]


class Store:
    """One live owner covers captures, copies, and all independent descriptor closes."""
    def __init__(self, read_limit, write_limit):
        self.read_limit = integer(read_limit, 1)
        self.write_limit = integer(write_limit, 1)
        self.read_reserved = self.write_reserved = 0
        self.failures = Failures()

    def read(self, path, cap, expected=None):
        cap = integer(cap, 1)
        fd = None
        result = None
        begin = len(self.failures.occurrences)
        try:
            p = Path(path)
            require(not any(x.is_symlink() for x in (p, *p.parents)), 'symlink in capture path')
            fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                    before.st_size <= cap, 'bounded regular capture')
            require(self.read_reserved + before.st_size <= self.read_limit, 'read extent')
            self.read_reserved += before.st_size
            chunks, size = [], 0
            while size <= before.st_size:
                value = os.read(fd, min(65536, before.st_size + 1 - size))
                if not value:
                    break
                chunks.append(value)
                size += len(value)
            result = b''.join(chunks)
            after = os.fstat(fd)
            stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            require(stamp(before) == stamp(after) and len(result) == before.st_size,
                    'complete stable capture')
            if expected is not None:
                expected.check(result)
        except BaseException as error:
            self.failures.add('capture', error)
        finally:
            if fd is not None:
                self.failures.attempt('capture.close', os.close, fd)
        if len(self.failures.occurrences) != begin:
            self.failures.raise_first()
        return result

    def write(self, path, raw, mode=0o400):
        require(type(raw) is bytes and type(mode) is int, 'literal output bytes/mode')
        require(self.write_reserved + len(raw) <= self.write_limit, 'write extent')
        self.write_reserved += len(raw)
        fd = None
        begin = len(self.failures.occurrences)
        try:
            p = Path(path)
            require(not any(x.is_symlink() for x in p.parents), 'output parent symlink')
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
            offset = 0
            while offset < len(raw):
                n = os.write(fd, raw[offset:offset + 65536])
                require(n > 0, 'complete output write')
                offset += n
            os.fsync(fd)
        except BaseException as error:
            self.failures.add('write', error)
        finally:
            if fd is not None:
                self.failures.attempt('write.close', os.close, fd)
        if len(self.failures.occurrences) != begin:
            self.failures.raise_first()
        return identity(raw)

    def capture_tree(self, root, destination, member_cap, total_cap, file_cap):
        """Capture every regular product, including failed-run products; no silent filtering."""
        root, destination = Path(root), Path(destination)
        require(root.is_dir() and not root.is_symlink(), 'product directory')
        destination.mkdir(mode=0o700, parents=False, exist_ok=False)
        files, total = [], 0
        for base, dirs, names in os.walk(root, followlinks=False):
            for name in dirs:
                require(not (Path(base) / name).is_symlink(), 'product directory symlink')
            for name in sorted(names):
                source = Path(base) / name
                rel = relative(source.relative_to(root).as_posix())
                require(len(files) < file_cap, 'complete product count')
                raw = self.read(source, member_cap)
                total += len(raw)
                require(total <= total_cap, 'complete product extent')
                target = destination / rel
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                files.append({'path': rel, **self.write(target, raw)})
        return {'files': files, 'bytes': total, 'complete': True}
