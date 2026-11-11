"""Serial MNE1.13.2 FIF-reader custody and logical read accounting.

Only the two reviewed FIF getter bindings are replaced. Native filenames must
already belong to the complete staged source manifest. No fileno escape,
preloading cache, writable native handle, gzip decoding or unknown file opener
is part of this profile. It is a prospective adapter, not native qualification.
"""
import os
import operator
from pathlib import Path
import stat

from custody import below, need, signature


class Reader:
    def __init__(self, owner, path, relative):
        self.owner = owner
        self.name = str(path)
        self.relative = relative
        self.fd = below(owner.stage_fd, relative, os.O_RDONLY)
        try:
            self.before = os.fstat(self.fd)
            entry = owner.files[relative]
            need(stat.S_ISREG(self.before.st_mode) and self.before.st_size == entry['bytes'],
                 'selected native file extent')
            need(signature(self.before) == tuple(owner.stage_signatures[relative]),
                 'same immutable native snapshot')
        except BaseException as original:
            fd, self.fd = self.fd, None
            try:
                os.close(fd)
            except BaseException as cleanup:
                if not isinstance(original, Exception): raise original
                raise cleanup from original
            raise

    @property
    def closed(self):
        return self.fd is None

    def tell(self):
        need(not self.closed, 'open native handle')
        return os.lseek(self.fd, 0, os.SEEK_CUR)

    def seek(self, offset, whence=os.SEEK_SET):
        self.owner.budget.check()
        need(type(offset) is not bool, 'native integer offset')
        offset = operator.index(offset)
        need(type(whence) is int and whence in (os.SEEK_SET, os.SEEK_CUR, os.SEEK_END),
             'explicit bounded native seek')
        origin = 0 if whence == os.SEEK_SET else self.tell() if whence == os.SEEK_CUR else self.before.st_size
        need(0 <= origin + offset <= self.before.st_size, 'native seek within selected file')
        return os.lseek(self.fd, offset, whence)

    def read(self, size=-1):
        need(type(size) is not bool, 'native integer read size')
        size = operator.index(size)
        need(size >= -1, 'native read size')
        if size == -1:
            size = self.before.st_size - self.tell()
        need(size <= self.owner.max_single_read, 'native single-read allocation bound')
        self.owner.budget.charge('read', size)
        # Charge the entire request before allocation; short reads are
        # conservative over-accounting, never an unreserved second read.
        chunks = []; remaining = size
        while remaining:
            self.owner.budget.check()
            raw = os.read(self.fd, min(remaining, 1 << 20))
            if not raw:
                break
            chunks.append(raw); remaining -= len(raw)
        result = b''.join(chunks)
        self.owner.budget.check()
        return result

    def readinto(self, target):
        view = memoryview(target)
        need(not view.readonly and view.c_contiguous, 'writable contiguous native readinto')
        view = view.cast('B')
        raw = self.read(view.nbytes)
        view[:len(raw)] = raw
        return len(raw)

    def readable(self): return not self.closed
    def seekable(self): return not self.closed
    def writable(self): return False

    def close(self):
        if self.fd is None:
            return
        fd = self.fd
        self.fd = None
        errors = []
        try:
            need(signature(self.before) == signature(os.fstat(fd)), 'native snapshot changed during read')
        except BaseException as exc:
            errors.append(exc)
        try:
            os.close(fd)
        except BaseException as exc:
            errors.append(exc)
        if errors:
            self.owner.failures.extend(type(e).__name__ for e in errors)
            raise errors[0]
        self.owner.closed_count += 1

    def fileno(self):
        raise OSError('native descriptor bypass outside counted FIF reader profile')

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        try:
            self.close()
        except BaseException as exc:
            if value is not None and not isinstance(value, Exception):
                raise value
            raise exc from value


class NativeIO:
    def __init__(self, *, stage, stage_fd, files, stage_signatures, budget,
                 fiff_module, raw_module, max_single_read=134217728):
        self.stage = Path(stage).absolute()
        self.stage_fd = stage_fd
        self.files = files
        self.stage_signatures = stage_signatures
        self.budget = budget
        self.max_single_read = max_single_read
        self.fiff_module = fiff_module
        self.raw_module = raw_module
        self.handles = []
        self.opened_count = self.closed_count = 0
        self.failures = []
        self.saved = None

    def getter(self, fname):
        self.budget.check()
        need(isinstance(fname, Path) and fname.is_absolute(), 'selected absolute native path')
        relative = str(fname.relative_to(self.stage))
        need(relative in self.files and relative.endswith('.fif'), 'native file belongs to staged manifest')
        self.handles = [h for h in self.handles if not h.closed]
        need(len(self.handles) < 256, 'native open-handle bound')
        reader = Reader(self, fname, relative)
        self.handles.append(reader)
        self.opened_count += 1
        return reader

    def close_paths(self, paths):
        errors = []
        for reader in self.handles:
            if reader.relative in paths and not reader.closed:
                try:
                    reader.close()
                except BaseException as exc:
                    errors.append(exc)
        if errors:
            raise errors[0]

    def __enter__(self):
        need(self.saved is None, 'single-use native I/O context')
        first = self.fiff_module._fiff_get_fid
        second = self.raw_module._fiff_get_fid
        need(first is second, 'exact MNE FIF getter aliases before adaptation')
        self.saved = (first, second)
        replacement = self.getter
        try:
            self.fiff_module._fiff_get_fid = replacement
            self.raw_module._fiff_get_fid = replacement
        except BaseException as original:
            errors = []
            for module, old in zip((self.fiff_module, self.raw_module), self.saved):
                try:
                    module._fiff_get_fid = old
                except BaseException as exc:
                    errors.append(exc)
            if not isinstance(original, Exception) or not errors:
                raise
            raise errors[0] from original
        return self

    def __exit__(self, kind, value, traceback):
        errors = []
        try:
            self.close_paths(set(self.files))
        except BaseException as exc:
            errors.append(exc)
        # Both restoration operations are attempted independently.
        for module, original in zip((self.fiff_module, self.raw_module), self.saved):
            try:
                module._fiff_get_fid = original
            except BaseException as exc:
                errors.append(exc)
        if value is not None and not isinstance(value, Exception):
            raise value
        if errors:
            raise errors[0] from value
        need(not self.failures and self.opened_count == self.closed_count,
             'all native handle closures established')
        self.budget.check()
