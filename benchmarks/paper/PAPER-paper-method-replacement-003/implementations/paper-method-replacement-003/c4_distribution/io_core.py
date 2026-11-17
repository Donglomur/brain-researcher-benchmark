"""Bounded ordinary-file capture and atomic no-replace tree publication.

These are filesystem mechanisms, not scientific/native/data-access authority.
Failures retain the original exception, any close failures, and partial custody.
"""
from __future__ import annotations
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import uuid

class SourceError(RuntimeError):
    pass

def _raise_with_close(primary, secondary):
    if primary is not None:
        if secondary:
            raise BaseExceptionGroup("original operation and resource-close failures", [primary, *secondary])
        raise primary
    if secondary:
        if len(secondary) == 1:
            raise secondary[0]
        raise BaseExceptionGroup("resource-close failures", secondary)

class OwnedFD:
    def __init__(self, fd):
        self.fd = fd
        self.close_attempted = False
        self.close_failure = None
    def __enter__(self):
        return self.fd
    def close(self):
        if self.close_attempted:
            raise SourceError("resource close already attempted; uncertain descriptor must not be retried")
        self.close_attempted = True
        try:
            os.close(self.fd)
        except BaseException as exc:
            self.close_failure = exc
            exc.c4_close_owner = self
            exc.add_note("Original C4 descriptor owner retained; close state uncertain, no automatic retry")
            raise
        self.fd = None
    def detach(self):
        if self.close_attempted or self.fd is None:
            raise SourceError("cannot detach uncertain or closed descriptor")
        fd, self.fd = self.fd, None
        return fd
    def __exit__(self, typ, primary, tb):
        failures = []
        try:
            self.close()
        except BaseException as exc:
            failures.append(exc)
        if failures:
            _raise_with_close(primary, failures)
        return False

class OwnedIterator:
    def __init__(self, iterator):
        self.iterator = iterator
    def __enter__(self):
        return self.iterator
    def __exit__(self, typ, primary, tb):
        failures = []
        try:
            self.iterator.close()
        except BaseException as exc:
            exc.c4_close_owner = self
            failures.append(exc)
        if failures:
            _raise_with_close(primary, failures)
        return False

def relative(value):
    if type(value) is not str or not value or len(value) > 1024 or "\\" in value:
        raise SourceError("bounded canonical relative path required")
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise SourceError("control character in path")
    p = PurePosixPath(value)
    if p.is_absolute() or p.as_posix() != value or any(x in ("", ".", "..") for x in value.split("/")):
        raise SourceError("canonical relative path required")
    return p

def _absolute(path):
    raw = os.fspath(path)
    if type(raw) is not str or not raw or "\x00" in raw:
        raise SourceError("plain filesystem path required")
    p = Path(os.path.abspath(raw))
    if len(raw) > 4096 or len(p.parts) > 128 or ".." in Path(raw).parts or any(ord(c) < 32 or ord(c) == 127 for c in raw):
        raise SourceError("ambiguous path")
    return p

def _dir_flags():
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise SourceError("no-follow directory opens unavailable")
    return os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY | os.O_NONBLOCK

def open_directory(path):
    p = _absolute(path)
    owners = []
    try:
        owners.append(OwnedFD(os.open("/", _dir_flags())))
        for part in p.parts[1:]:
            owners.append(OwnedFD(os.open(part, _dir_flags(), dir_fd=owners[-1].fd)))
    except BaseException as primary:
        secondary = []
        for owner in reversed(owners):
            try:
                owner.close()
            except BaseException as exc:
                secondary.append(exc)
        _raise_with_close(primary, secondary)
    result = owners.pop()
    failures = []
    for owner in reversed(owners):
        try:
            owner.close()
        except BaseException as exc:
            failures.append(exc)
    if failures:
        try:
            result.close()
        except BaseException as exc:
            failures.append(exc)
        _raise_with_close(None, failures)
    return result.detach()

def _identity(st):
    return (st.st_dev, st.st_ino, st.st_mode, st.st_size,
            st.st_mtime_ns, st.st_ctime_ns, st.st_nlink)

def read_at(root_fd, rel, cap):
    parts = relative(rel).parts
    if type(cap) is not int or not 0 <= cap <= 20000000:
        raise SourceError("bounded runtime member cap exceeded")
    def descend(fd, remaining):
        if len(remaining) > 1:
            with OwnedFD(os.open(remaining[0], _dir_flags(), dir_fd=fd)) as child:
                return descend(child, remaining[1:])
        name = remaining[0]
        before = os.stat(name, dir_fd=fd, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 <= before.st_size <= cap:
            raise SourceError("bounded regular single-link member required")
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        with OwnedFD(os.open(name, flags, dir_fd=fd)) as source:
            initial = os.fstat(source)
            if _identity(initial) != _identity(before):
                raise SourceError("file changed before capture")
            chunks = []
            remaining_bytes = before.st_size
            while remaining_bytes:
                block = os.read(source, min(65536, remaining_bytes))
                if not block:
                    raise SourceError("truncated member")
                chunks.append(block)
                remaining_bytes -= len(block)
            if os.read(source, 1):
                raise SourceError("growing member")
            after = os.fstat(source)
            named = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if _identity(initial) != _identity(after) or _identity(after) != _identity(named):
                raise SourceError("member changed during capture")
            return b"".join(chunks)
    return descend(root_fd, parts)

def capture_path(path, cap):
    p = _absolute(path)
    with OwnedFD(open_directory(p.parent)) as parent:
        return read_at(parent, p.name, cap)

def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise SourceError("duplicate JSON key")
            result[key] = value
        return result
    def reject(value):
        raise SourceError("nonfinite JSON")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=reject)

def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()

def verify_inventory(root_fd, paths, *, immutable=True, root_immutable=True):
    expected_files = set(paths)
    expected_dirs = set()
    if len(expected_files) != len(paths) or len(paths) > 2048:
        raise SourceError("complete bounded inventory required")
    for path in paths:
        p = relative(path)
        for parent in p.parents:
            if parent.as_posix() != ".":
                expected_dirs.add(parent.as_posix())
    seen_files, seen_dirs = set(), set()
    scanned = 0
    def walk(fd, prefix):
        nonlocal scanned
        with OwnedIterator(os.scandir(fd)) as entries:
            for entry in entries:
                scanned += 1
                if scanned > 4096:
                    raise SourceError("inventory enumeration cap")
                name = entry.name if not prefix else prefix + "/" + entry.name
                relative(name)
                st = os.stat(entry.name, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISDIR(st.st_mode):
                    if name not in expected_dirs:
                        raise SourceError("unselected directory in dependency root")
                    seen_dirs.add(name)
                    if immutable and st.st_mode & 0o222:
                        raise SourceError("writable prepared directory")
                    with OwnedFD(os.open(entry.name, _dir_flags(), dir_fd=fd)) as child:
                        walk(child, name)
                else:
                    if name not in expected_files or not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
                        raise SourceError("unselected/nonregular dependency member")
                    if immutable and st.st_mode & 0o222:
                        raise SourceError("writable prepared member")
                    seen_files.add(name)
    walk(root_fd, "")
    if seen_files != expected_files or seen_dirs != expected_dirs:
        raise SourceError("incomplete dependency inventory")
    if immutable and root_immutable and os.fstat(root_fd).st_mode & 0o222:
        raise SourceError("writable prepared root")

def _write_at(root_fd, rel, body):
    parts = relative(rel).parts
    def descend(fd, remaining):
        if len(remaining) > 1:
            try:
                os.mkdir(remaining[0], 0o700, dir_fd=fd)
            except FileExistsError:
                pass
            with OwnedFD(os.open(remaining[0], _dir_flags(), dir_fd=fd)) as child:
                return descend(child, remaining[1:])
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK
        with OwnedFD(os.open(remaining[0], flags, 0o600, dir_fd=fd)) as output:
            view = memoryview(body)
            while view:
                n = os.write(output, view)
                if n <= 0:
                    raise SourceError("short output write")
                view = view[n:]
            os.fchmod(output, 0o444)
            os.fsync(output)
    descend(root_fd, parts)

def _seal_dirs(root_fd, files, *, seal_root=True):
    dirs = {p.as_posix() for f in files for p in PurePosixPath(f).parents if p.as_posix() != "."}
    for rel in sorted(dirs, key=lambda x: len(PurePosixPath(x).parts), reverse=True):
        def descend(fd, parts):
            if not parts:
                os.fchmod(fd, 0o555)
                os.fsync(fd)
                return
            with OwnedFD(os.open(parts[0], _dir_flags(), dir_fd=fd)) as child:
                descend(child, parts[1:])
        descend(root_fd, PurePosixPath(rel).parts)
    if seal_root:
        os.fchmod(root_fd, 0o555)
    os.fsync(root_fd)

def _rename_no_replace(parent_fd, old, new):
    # Refuse unsupported platforms; do not replace this with racy exists()+rename().
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        function = getattr(libc, "renameatx_np", None)
        flag = 0x00000004  # RENAME_EXCL
    elif sys.platform.startswith("linux"):
        function = getattr(libc, "renameat2", None)
        flag = 1  # RENAME_NOREPLACE
    else:
        raise SourceError("atomic no-replace directory publication unsupported")
    if function is None:
        raise SourceError("atomic no-replace syscall unavailable")
    function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    function.restype = ctypes.c_int
    if function(parent_fd, os.fsencode(old), parent_fd, os.fsencode(new), flag):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), new)

def publish_tree(output, pairs, *, max_files=2048, max_bytes=16777216, max_member_bytes=1048576):
    if type(max_files) is not int or not 1 <= max_files <= 2048 or type(max_bytes) is not int or not 0 <= max_bytes <= 40000000:
        raise SourceError("bounded publication capacity required")
    if type(max_member_bytes) is not int or not 0 <= max_member_bytes <= 20000000:
        raise SourceError("explicit bounded member capacity required")
    rows = []
    names = set()
    total = 0
    for name, body in pairs:
        relative(name)
        if name.casefold() in names or type(body) is not bytes or len(body) > max_member_bytes:
            raise SourceError("unique ordinary byte members required")
        try:
            body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SourceError("ordinary UTF-8 source required") from exc
        if b"\0" in body:
            raise SourceError("binary member refused")
        names.add(name.casefold())
        total += len(body)
        rows.append((name, body))
        if len(rows) > max_files or total > max_bytes:
            raise SourceError("publication capacity exceeded before writes")
    if not rows:
        raise SourceError("empty publication refused")
    paths = [name for name, body in rows]
    pathset = set(paths)
    if any(p.as_posix() in pathset for name in paths for p in PurePosixPath(name).parents):
        raise SourceError("file/directory path collision")
    target = _absolute(output)
    relative(target.name)
    stage = ".c4-source-stage-" + uuid.uuid4().hex
    created = published = False
    try:
        with OwnedFD(open_directory(target.parent)) as parent:
            try:
                os.stat(target.name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise FileExistsError(errno.EEXIST, "destination already exists", str(target))
            os.mkdir(stage, 0o700, dir_fd=parent)
            created = True
            with OwnedFD(os.open(stage, _dir_flags(), dir_fd=parent)) as staging:
                for name, body in rows:
                    _write_at(staging, name, body)
                # Darwin requires the renamed directory itself to be writable.
                # All contents/child directories are sealed before the atomic
                # rename; final root sealing remains inside the same owner and
                # any post-rename failure reports published custody, not success.
                _seal_dirs(staging, paths, seal_root=False)
                verify_inventory(staging, paths, root_immutable=False)
                for name, body in rows:
                    if read_at(staging, name, len(body)) != body:
                        raise SourceError("staged byte readback mismatch")
                _rename_no_replace(parent, stage, target.name)
                published = True
                os.fchmod(staging, 0o555)
                os.fsync(staging)
                verify_inventory(staging, paths)
            os.fsync(parent)
        return {"schema": "c4.atomic-source-publication.v1", "output": str(target),
                "files": [{"path": n, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()} for n, b in rows],
                "bytes": total, "atomic_no_replace": True,
                "readonly_root_seal_verified_after_atomic_rename": True,
                "scientific_qualification": False}
    except BaseException as exc:
        exc.add_note("C4 source custody: stage_created=" + str(created) + "; published=" + str(published)
                     + "; partial_or_published_path=" + str(target if published else target.parent / stage)
                     + "; no automatic deletion or success claim")
        raise
