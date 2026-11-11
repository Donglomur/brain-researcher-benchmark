"""Closed ordinary metadata, bounded ownership and original-error-preserving I/O."""
import hashlib
import json
import math
import os
import re
import stat
import time
from pathlib import Path, PurePosixPath

class Refusal(ValueError):
    pass

class DependencyUnavailable(Refusal):
    def __init__(self, role, detail):
        super().__init__(role + ": " + detail)
        self.role, self.detail = role, detail

def need(condition, message):
    if not condition:
        raise Refusal(message)

def integer(value, low=0):
    need(type(value) is int and low <= value <= 9007199254740991, "exact bounded integer")
    return value

def finite(value):
    need(type(value) in (int, float) and math.isfinite(value), "finite exact number")
    return value

def closed(value, fields):
    need(type(value) is dict and set(value) == set(fields), "closed exact fields")
    return value

def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                       allow_nan=False) + "\n").encode("utf8")

def pin(raw):
    need(type(raw) is bytes, "original bytes")
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

def parse(raw, cap):
    need(type(raw) is bytes and len(raw) <= integer(cap, 1) and not raw.startswith(b"\xef\xbb\xbf"),
         "bounded UTF8 JSON without BOM")
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, "duplicate JSON member")
            out[key] = value
        return out
    def number(value):
        result = float(value)
        finite(result)
        return result
    def bad(value):
        raise Refusal("nonfinite JSON constant")
    return json.loads(raw.decode("utf8"), object_pairs_hook=pairs, parse_float=number,
                      parse_constant=bad)

def relative(name):
    need(type(name) is str and 0 < len(name.encode("utf8")) <= 4096 and "\\" not in name,
         "bounded exact relative path")
    need(not name.startswith("/") and all(c not in (".", "..", "") for c in name.split("/"))
         and not any(ord(c) < 32 or ord(c) == 127 for c in name), "canonical path components")
    need(str(PurePosixPath(name)) == name, "no normalized alternate path")
    return name

def descriptor(row):
    closed(row, ("path", "bytes", "sha256"))
    relative(row["path"]); integer(row["bytes"])
    need(type(row["sha256"]) is str and re.fullmatch("[a-f0-9]{64}", row["sha256"]), "SHA256")
    return row

def same(a, b):
    return type(a) is type(b) and encode(a) == encode(b)

def failure(error):
    # Identity comparisons and literal strings only. Even type.__getattribute__
    # can invoke a descriptor on an arbitrary exception's metaclass. Unknown
    # classes keep their actual raw object in the owner, without inspecting it.
    typ = type(error)
    for cls, name in ((Exception,'Exception'),(RuntimeError,'RuntimeError'),
        (ValueError,'ValueError'),(TypeError,'TypeError'),(KeyError,'KeyError'),
        (IndexError,'IndexError'),(OSError,'OSError'),(FileNotFoundError,'FileNotFoundError'),
        (FileExistsError,'FileExistsError'),(PermissionError,'PermissionError'),
        (TimeoutError,'TimeoutError'),(InterruptedError,'InterruptedError'),
        (BlockingIOError,'BlockingIOError'),(BrokenPipeError,'BrokenPipeError'),
        (ConnectionError,'ConnectionError'),(UnicodeError,'UnicodeError'),
        (UnicodeDecodeError,'UnicodeDecodeError'),(UnicodeEncodeError,'UnicodeEncodeError'),
        (MemoryError,'MemoryError'),(KeyboardInterrupt,'KeyboardInterrupt'),(SystemExit,'SystemExit')):
        if typ is cls:return {'module':'builtins','type':name}
    return {'module':'unknown','type':'BaseException'}

class Meter:
    """One selected adapter reservation, distinct from each original programme Budget."""
    def __init__(self, limits, *, origin_ns, deadline_ns, owner, reservation_id):
        closed(limits, ("read_bytes", "write_bytes", "work_units", "retained_bytes"))
        self.limits = {k: integer(v) for k, v in limits.items()}
        self.spent = dict.fromkeys(self.limits, 0)
        self.origin_ns, self.deadline_ns = integer(origin_ns, 1), integer(deadline_ns, 1)
        need(self.origin_ns < self.deadline_ns, "unchanged original interval")
        self.owner, self.reservation_id = owner, reservation_id
        self.first_error = None
        self.cleanup_errors = []
        self.unknown = set()
    def check(self):
        need(time.monotonic_ns() < self.deadline_ns, "original hard evidence cutoff")
    def charge(self, kind, amount):
        self.check(); integer(amount)
        need(kind in self.spent and self.spent[kind] + amount <= self.limits[kind],
             "prospective selected adapter reservation")
        self.spent[kind] += amount
    def own_error(self, error, dimension=None):
        if self.first_error is None:
            self.first_error = failure(error)
        if dimension is not None:
            self.unknown.add(dimension)
    def record(self):
        return {"owner": self.owner, "reservation_id": self.reservation_id,
                "limits": dict(self.limits), "spent": dict(self.spent),
                "origin_ns": self.origin_ns, "deadline_ns": self.deadline_ns,
                "first_error": self.first_error, "cleanup_errors": list(self.cleanup_errors),
                "unknown_dimensions": sorted(self.unknown), "physical_measurements": False}

class Store:
    """An explicit typed root; never derives a base from a receipt parent."""
    def __init__(self, root, meter, *, forbidden=()):
        p = Path(root).absolute()
        need(p.is_dir() and not p.is_symlink() and p.resolve() == p, "canonical existing root")
        self.root, self.meter = p, meter
        self.forbidden = frozenset(relative(x) for x in forbidden)
        self.raw_close_errors=[];self.raw_close_diagnostic_errors=[]
        self.last_close_diagnostic_error=None
        self.raw_io_errors=[];self.raw_io_diagnostic_errors=[]
    def _own_error(self,error,dimension=None):
        self.raw_io_errors.append(error)
        try:self.meter.own_error(error,dimension)
        except BaseException as diagnostic:self.raw_io_diagnostic_errors.append(diagnostic)
    def _parent(self, name):
        relative(name)
        need(name not in self.forbidden, "held source/data identity excluded before access")
        fds = []
        try:
            self.meter.check()
            fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            fds.append(fd)
            for part in name.split("/")[:-1]:
                self.meter.check()
                fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                fds.append(fd)
            return fds, name.split("/")[-1]
        except BaseException as error:
            self._own_error(error)
            self._close(fds)
            raise
    def _close(self, fds):
        first = None
        for index in range(len(fds)-1,-1,-1):
            fd=fds[index];fds[index]=None
            if fd is None:continue
            try:
                os.close(fd)
            except BaseException as error:
                if first is None:
                    first = error
                self.raw_close_errors.append(error)
                # Original raw custody precedes diagnostic projection. The
                # descriptor retry slot is already clear on unknown close.
                try:self.meter.own_error(error,'store_fd_close')
                except BaseException as diagnostic:
                    # Keep closing other owned descriptors and return the
                    # original close error even if diagnostics cannot complete.
                    self.last_close_diagnostic_error=diagnostic
                    self.raw_close_diagnostic_errors.append(diagnostic)
                try:self.meter.cleanup_errors.append(failure(error))
                except BaseException as diagnostic:
                    self.last_close_diagnostic_error=diagnostic
                    self.raw_close_diagnostic_errors.append(diagnostic)
        return first
    def read(self, expected, cap, *, metadata=False):
        descriptor(expected); integer(cap, 1)
        need(expected["bytes"] <= cap, "source-selected complete byte cap")
        self.meter.charge("read_bytes", expected["bytes"] + 1)
        if metadata:
            self.meter.charge("work_units", 64 * expected["bytes"] + 4096)
        fds = []; primary = None; raw = None
        try:
            fds, name = self._parent(expected["path"])
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fds[-1])
            fds.append(fd)
            first = os.fstat(fd)
            need(stat.S_ISREG(first.st_mode) and first.st_nlink == 1 and
                 first.st_size == expected["bytes"], "ordinary exact original extent")
            parts = []; count = 0
            while count <= expected["bytes"]:
                self.meter.check()
                part = os.read(fd, min(65536, expected["bytes"] + 1 - count))
                if not part:
                    break
                parts.append(part); count += len(part)
            raw = b"".join(parts)
            self.meter.check()
            last = os.fstat(fd)
            named = os.stat(name, dir_fd=fds[-2], follow_symlinks=False)
            fields=("st_dev","st_ino","st_size","st_mtime_ns","st_ctime_ns","st_mode","st_nlink")
            need(all(getattr(first,k)==getattr(last,k)==getattr(named,k) for k in fields),
                 "stable original source")
            need(pin(raw) == {k: expected[k] for k in ("bytes","sha256")}, "exact whole original bytes")
        except BaseException as error:
            primary = error
            self._own_error(error, "failed_read_extent")
        cleanup = self._close(fds)
        if primary is not None:
            raise primary
        if cleanup is not None:
            self._own_error(cleanup, "reader_close")
            raise cleanup
        try:self.meter.check()
        except BaseException as error:
            self._own_error(error,"reader_final_cutoff");raise
        return raw
    def document(self, expected, cap):
        return parse(self.read(expected, cap, metadata=True), cap)
    def capture_created(self, name, cap, *, metadata=False):
        """Bounded actual output capture; callers must first admit its producer.

        The root and relative name are explicit. This never infers a root from
        a child-supplied receipt, discovers directory members, or reads a suffix
        after allowance exhaustion. The full prospective reservation is kept.
        """
        relative(name);integer(cap,1)
        self.meter.charge("read_bytes",cap+1)
        self.meter.charge("retained_bytes",cap+1)
        if metadata:self.meter.charge("work_units",cap*64+4096)
        fds=[];primary=None;raw=None
        try:
            fds,leaf=self._parent(name)
            fd=os.open(leaf,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fds[-1]);fds.append(fd)
            before=os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<=before.st_size<=cap,
                 "actual complete ordinary output within earlier extent")
            parts=[];count=0
            while count<=before.st_size:
                self.meter.check()
                part=os.read(fd,min(65536,before.st_size+1-count))
                if not part:break
                parts.append(part);count+=len(part)
            self.meter.check()
            raw=b"".join(parts);after=os.fstat(fd);named=os.stat(leaf,dir_fd=fds[-2],follow_symlinks=False)
            fields=("st_dev","st_ino","st_size","st_mtime_ns","st_ctime_ns","st_mode","st_nlink")
            need(len(raw)==before.st_size and all(getattr(before,k)==getattr(after,k)==getattr(named,k) for k in fields),
                 "same complete original produced object")
        except BaseException as error:
            primary=error;self._own_error(error,"captured_output_unknown_extent")
        cleanup=self._close(fds)
        if primary is not None:raise primary
        if cleanup is not None:
            self._own_error(cleanup,"captured_output_close");raise cleanup
        try:self.meter.check()
        except BaseException as error:
            self._own_error(error,"captured_output_final_cutoff");raise
        return raw,{"path":name,**pin(raw)}
    def write(self, name, raw):
        relative(name); need(type(raw) is bytes, "bounded explicit bytes")
        self.meter.charge("write_bytes", len(raw))
        self.meter.charge("retained_bytes", len(raw))
        fds = []; primary = None
        try:
            fds, leaf = self._parent(name)
            fd = os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=fds[-1])
            fds.append(fd); view = memoryview(raw); offset = 0
            while offset < len(view):
                self.meter.check()
                written = os.write(fd, view[offset:])
                need(written > 0, "positive partial write")
                offset += written
            os.fsync(fd)
        except BaseException as error:
            primary = error
            self._own_error(error, "failed_write_extent")
        cleanup = self._close(fds)
        if primary is not None:
            raise primary
        if cleanup is not None:
            self._own_error(cleanup, "writer_close")
            raise cleanup
        try:self.meter.check()
        except BaseException as error:
            self._own_error(error,"writer_final_cutoff");raise
        return {"path": name, **pin(raw)}
    def publish(self, name, value):
        self.meter.charge("work_units", bounded_size(value))
        return self.write(name, encode(value))

def bounded_size(value, *, depth=0):
    """Saturating pre-serialization upper bound; no arbitrary encoders/callbacks."""
    need(depth <= 64, "bounded metadata depth")
    if value is None or type(value) is bool:
        return 6
    if type(value) is int:
        integer(abs(value)); return 24
    if type(value) is float:
        finite(value); return 40
    if type(value) is str:
        need(len(value) <= 1048576, "bounded metadata string")
        return 6 * len(value) + 2
    if type(value) is list:
        need(len(value) <= 16384, "bounded metadata sequence")
        result = 2
        for member in value:
            result += 1 + bounded_size(member, depth=depth + 1)
            need(result <= 33554432, "metadata allocation cap")
        return result
    need(type(value) is dict and len(value) <= 16384, "closed JSON metadata value")
    result = 2
    for key, member in value.items():
        need(type(key) is str, "text metadata key")
        result += 2 + bounded_size(key, depth=depth + 1) + bounded_size(member, depth=depth + 1)
        need(result <= 33554432, "metadata allocation cap")
    return result
