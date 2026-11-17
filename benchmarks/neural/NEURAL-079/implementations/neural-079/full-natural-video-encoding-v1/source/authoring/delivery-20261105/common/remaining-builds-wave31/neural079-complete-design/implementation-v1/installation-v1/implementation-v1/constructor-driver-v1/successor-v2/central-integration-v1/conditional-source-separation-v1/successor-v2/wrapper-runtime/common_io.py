"""Task-local adaptation of accepted NEURAL010 central metadata I/O.

Original integer-nanosecond cutoffs and independent, once-only cleanup preserve
the initiating error. This is metadata accounting, not physical-resource proof.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time


def need(ok, message):
    if not ok: raise ValueError(message)


def integer(x, minimum=0):
    need(type(x) is int and x >= minimum, "exact bounded integer, not bool")
    return x


def finite(x):
    need(type(x) in (int, float) and math.isfinite(x) and x >= 0, "finite nonnegative clock")
    return float(x)


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(x): return hashlib.sha256(canonical(x)).hexdigest()


def pin(body): return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def only_pin(p):
    need(type(p) is dict and set(p) in ({"bytes", "sha256"}, {"path", "bytes", "sha256"}), "closed pin fields")
    integer(p["bytes"])
    need(type(p["sha256"]) is str and re.fullmatch("[a-f0-9]{64}", p["sha256"]), "SHA256")
    return {k: p[k] for k in ("bytes", "sha256")}


def relative(s):
    need(type(s) is str and 0 < len(s) <= 4096 and not s.startswith("/") and "\\" not in s and "\0" not in s
         and all(p not in ("", ".", "..") for p in s.split("/")), "confined relative path")
    return s


def absolute(s):
    need(type(s) is str and s.startswith("/") and not s.startswith("//") and len(s) <= 4096
         and "\\" not in s and "\0" not in s and Path(s).as_posix() == s and ".." not in Path(s).parts, "canonical absolute path")
    return Path(s)


def descriptor(p):
    need(type(p) is dict and set(p) == {"path", "bytes", "sha256"}, "closed artifact descriptor")
    absolute(p["path"]); only_pin(p)
    return p


def parse(body):
    def pairs(rows):
        out = {}
        for k, v in rows:
            need(k not in out, "duplicate JSON field"); out[k] = v
        return out
    return json.loads(body.decode("utf-8", "strict"), object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, "nonfinite JSON value"))


def bounded_canonical(value, cap):
    integer(cap, 1)
    def visit(x, depth=0):
        need(depth <= 64, "bounded metadata nesting")
        if x is None or type(x) is bool: return 5
        if type(x) is int:
            need(x.bit_length() <= 128, "bounded metadata integer"); return len(str(x))
        if type(x) is float:
            need(math.isfinite(x), "finite metadata float"); return len(json.dumps(x))
        if type(x) is str:
            need(len(x) <= cap, "bounded string")
            return len(json.dumps(x, ensure_ascii=False).encode("utf-8"))
        need(type(x) in (dict, list, tuple), "plain JSON metadata only")
        total = 2
        for i, item in enumerate(x.items() if type(x) is dict else enumerate(x)):
            k, v = item
            if type(x) is dict:
                need(type(k) is str, "string JSON keys"); total += visit(k, depth + 1) + 1
            total += int(i > 0) + visit(v, depth + 1)
            need(total <= cap, "whole metadata extent cap")
        return total
    need(visit(value) <= cap, "bounded complete metadata")
    body = canonical(value); need(len(body) <= cap, "encoded metadata extent")
    return body


def stamp(s):
    return tuple(getattr(s, k) for k in ("st_dev", "st_ino", "st_mode", "st_size", "st_nlink", "st_mtime_ns", "st_ctime_ns", "st_uid"))


def cleanup(operations, primary=None):
    first=primary
    for label, action in operations:
        try:action()
        except BaseException as error:
            if first is None:first=error
            else:
                first.central_secondary_errors=list(getattr(first,'central_secondary_errors',[]))+[{'phase':label,'type':type(error).__name__}]
    if primary is None and first is not None:raise first


def parent_fd(p):
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in p.parent.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            old=fd;fd=child;os.close(old)
        return fd
    except BaseException as error:
        cleanup([('directory traversal close',lambda:os.close(fd))],error);raise


class Reader:
    def __init__(self, *, read_limit, write_limit, deadline, clock=time.monotonic_ns):
        self.read_limit = integer(read_limit, 1); self.write_limit = integer(write_limit)
        self.deadline = integer(deadline,1); self.clock = clock; self.last = integer(clock(),1)
        self.read_reserved = self.read_observed = self.write_reserved = self.write_observed = 0
        self.hash_bytes = self.decode_bytes = 0; self.failures = []; self.tick()

    def tick(self, end=None):
        now = integer(self.clock(),1); limit = self.deadline if end is None else min(self.deadline, integer(end,1))
        need(self.last <= now < limit, "original deadline/monotonic rollback")
        self.last = now; return now

    def tighten(self, end):
        end = integer(end,1); need(end <= self.deadline, "no deadline extension")
        self.deadline = end; self.tick()

    def reserve_read(self, n):
        self.tick(); self.read_reserved += integer(n)
        need(self.read_reserved <= self.read_limit, "full read reservation exhausted")

    def reserve_write(self, n):
        self.tick(); self.write_reserved += integer(n)
        need(self.write_reserved <= self.write_limit, "full write reservation exhausted")

    def chunks(self, path, cap, expected, *, end=None):
        p = absolute(str(path)); expected = only_pin(expected); integer(cap, 1)
        need(expected["bytes"] <= cap, "whole body fits declared cap")
        directory = fd = None; primary=None
        try:
            self.tick(end); directory = parent_fd(p)
            self.tick(end)
            fd = os.open(p.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            first = os.fstat(fd)
            need(stat.S_ISREG(first.st_mode) and first.st_nlink == 1 and first.st_size == expected["bytes"], "ordinary exact full file")
            self.reserve_read(first.st_size + 1); left = first.st_size; h = hashlib.sha256()
            while left:
                self.tick(end); block = os.read(fd, min(left, 65536)); self.read_observed += len(block)
                need(block, "unexpected EOF"); left -= len(block); h.update(block); self.hash_bytes += len(block)
                yield block
            self.tick(end); extra = os.read(fd, 1); self.read_observed += len(extra)
            need(not extra and stamp(first) == stamp(os.fstat(fd)) == stamp(os.stat(p.name, dir_fd=directory, follow_symlinks=False))
                 and h.hexdigest() == expected["sha256"], "complete unchanged exact file")
        except BaseException as e:
            primary=e;self.failures.append({"operation": "read", "error_type": type(e).__name__}); raise
        finally:
            operations=[]
            if fd is not None: operations.append(('metadata file close',lambda fd=fd:os.close(fd)))
            if directory is not None: operations.append(('metadata directory close',lambda directory=directory:os.close(directory)))
            cleanup(operations,primary)
        self.tick(end)  # after EOF and every close; late artifacts remain failures

    def read(self, path, cap, expected=None, *, end=None):
        if expected is None:
            p = absolute(str(path)); self.tick(end); directory = parent_fd(p); primary=None
            try:
                self.tick(end)
                s = os.stat(p.name, dir_fd=directory, follow_symlinks=False)
                need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and 0 < s.st_size <= cap, "bounded ordinary metadata")
            except BaseException as error:primary=error;raise
            finally:cleanup([("unbound stat directory close",lambda:os.close(directory))],primary)
            # No preknown hash: same robust descriptor path with an explicit open.
            return self._unbound(p, cap, s, end=end)
        body = b"".join(self.chunks(path, cap, expected, end=end)); self.tick(end); return body

    def _unbound(self, p, cap, selected, *, end=None):
        directory = fd = None; primary=None
        try:
            self.tick(end); directory = parent_fd(p)
            self.tick(end)
            fd = os.open(p.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            first = os.fstat(fd); need(stamp(first) == stamp(selected), "metadata identity changed before open")
            self.reserve_read(first.st_size + 1); left = first.st_size; parts = []
            while left:
                self.tick(end); b = os.read(fd, min(left, 65536)); self.read_observed += len(b)
                need(b, "unexpected EOF"); left -= len(b); parts.append(b)
            self.tick(end); extra = os.read(fd, 1); self.read_observed += len(extra)
            need(not extra and stamp(first) == stamp(os.fstat(fd)) == stamp(os.stat(p.name, dir_fd=directory, follow_symlinks=False)), "stable metadata")
            body = b"".join(parts); self.hash_bytes += len(body)
        except BaseException as e:
            primary=e;self.failures.append({"operation": "unbound_read", "error_type": type(e).__name__}); raise
        finally:
            operations=[]
            if fd is not None: operations.append(('metadata file close',lambda fd=fd:os.close(fd)))
            if directory is not None: operations.append(('metadata directory close',lambda directory=directory:os.close(directory)))
            cleanup(operations,primary)
        self.tick(end); return body

    def json(self, path, cap, expected=None, *, end=None):
        body = self.read(path, cap, expected, end=end); self.decode_bytes += len(body)
        value = parse(body); self.tick(end); return value, pin(body)

    def opaque(self, p, cap, *, end=None):
        descriptor(p)
        for _ in self.chunks(p["path"], cap, only_pin(p), end=end): pass
        self.tick(end); return p

    def write_new(self, path, body, cap, *, end=None):
        p = absolute(str(path)); need(type(body) is bytes and 0 < len(body) <= integer(cap, 1), "bounded complete write")
        self.tick(end); self.reserve_write(len(body)); directory = fd = None; primary=None
        try:
            directory = parent_fd(p)
            self.tick(end)
            fd = os.open(p.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444, dir_fd=directory)
            offset = 0
            while offset < len(body):
                self.tick(end); n = os.write(fd, memoryview(body)[offset:offset + 65536]); need(n > 0, "short write")
                offset += n; self.write_observed += n
            self.tick(end); os.fsync(fd); self.tick(end); os.fsync(directory)
        except BaseException as e:
            primary=e;self.failures.append({"operation": "write", "error_type": type(e).__name__}); raise
        finally:
            operations=[]
            if fd is not None: operations.append(('metadata file close',lambda fd=fd:os.close(fd)))
            if directory is not None: operations.append(('metadata directory close',lambda directory=directory:os.close(directory)))
            cleanup(operations,primary)
        self.tick(end); return {"path": str(p), **pin(body)}

    def report(self):
        return {k: getattr(self, k) for k in ("read_limit", "write_limit", "read_reserved", "read_observed", "write_reserved", "write_observed", "hash_bytes", "decode_bytes", "deadline", "last", "failures")} | {"physical_IO_RSS_certified": False}
