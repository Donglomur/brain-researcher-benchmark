"""Bounded ordinary metadata and anchored custody; no scientific imports."""
import hashlib
import json
import math
import os
import stat
import time
from .errors import Refusal, DeadlineExceeded

def require(condition, message):
    if not condition:
        raise Refusal(message)

def number(x, name="number"):
    require(type(x) in (int, float) and math.isfinite(x), name)
    return float(x)

def integer(x, name="integer", minimum=0):
    require(type(x) is int and x >= minimum, name)
    return x

def unique(values, name):
    require(type(values) is list, name)
    require(all(type(x) in (str,int,float) and (type(x) is not float or math.isfinite(x)) for x in values), name+" finite scalar identifiers")
    require(len(set(values)) == len(values), name)
    return values

def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()

def digest(body):
    return hashlib.sha256(body).hexdigest()

def decode(body):
    def pairs(rows):
        out = {}
        for k, v in rows:
            require(k not in out, "duplicate JSON key")
            out[k] = v
        return out
    def bad(x):
        raise Refusal("nonfinite JSON literal")
    try:
        value = json.loads(body.decode("utf-8"), object_pairs_hook=pairs, parse_constant=bad)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise Refusal("invalid UTF-8 JSON") from exc
    def finite(x):
        if type(x) is float:
            require(math.isfinite(x), "JSON exponent overflow")
        elif isinstance(x, list):
            for y in x: finite(y)
        elif isinstance(x, dict):
            for y in x.values(): finite(y)
    finite(value)
    return value

def relative(path):
    require(type(path) is str and path and "\x00" not in path and "\\" not in path, "bad relative path")
    require(not path.startswith("/") and all(x not in ("", ".", "..") for x in path.split("/")), "noncanonical path")
    return path.split("/")

class Clock:
    """One original operation interval; stages cannot reset it."""
    def __init__(self, start_ns, duration_ns, cleanup_ns):
        self.start_ns = integer(start_ns, "original start", 1)
        self.end_ns = self.start_ns + integer(duration_ns, "duration", 1)
        self.cleanup_end_ns = self.end_ns + integer(cleanup_ns, "cleanup", 1)
    @classmethod
    def begin(cls, duration_ns, cleanup_ns):
        return cls(time.monotonic_ns(), duration_ns, cleanup_ns)
    def check(self, cleanup=False):
        now = time.monotonic_ns()
        if now >= (self.cleanup_end_ns if cleanup else self.end_ns):
            raise DeadlineExceeded("original interval exhausted")
        return now
    def remaining(self, cleanup=False):
        return max(0.0, ((self.cleanup_end_ns if cleanup else self.end_ns)-time.monotonic_ns())/1e9)
    def child(self, duration_ns, cleanup_ns):
        self.check()
        now=time.monotonic_ns()
        end=min(self.end_ns,now+integer(duration_ns,"child duration",1))
        cleanup_end=min(self.cleanup_end_ns,end+integer(cleanup_ns,"child cleanup",1))
        out=Clock(self.start_ns,end-self.start_ns,cleanup_end-end)
        out.admission_ns=now
        return out

class Root:
    """Keep directory descriptors; reject aliases, symlinks and nonregular leaves."""
    def __init__(self, path, *, private=False):
        require(type(path) is str and path.startswith("/") and "\x00" not in path, "absolute root required")
        parts = path.split("/")[1:]
        require(all(x not in ("", ".", "..") for x in parts), "noncanonical absolute root")
        fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in parts:
                new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd); fd = new
            st = os.fstat(fd)
            if private:
                require(st.st_uid == os.geteuid() and stat.S_IMODE(st.st_mode) == 0o700, "private root custody")
            self.fd = fd
            self.identity = [st.st_dev, st.st_ino, st.st_uid, stat.S_IMODE(st.st_mode)]
            self.path = path
        except BaseException:
            os.close(fd)
            raise
    def close(self):
        if self.fd is not None:
            os.close(self.fd); self.fd = None
    def __enter__(self): return self
    def __exit__(self, *args): self.close()
    def parent(self, rel):
        parts = relative(rel)
        fd = os.dup(self.fd)
        try:
            for part in parts[:-1]:
                new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd); fd = new
            return fd, parts[-1]
        except BaseException:
            os.close(fd); raise
    def read(self, rel, cap, *, pin=None, clock=None, cleanup=False):
        integer(cap, "read cap", 0)
        if clock: clock.check(cleanup)
        fd, leaf = self.parent(rel)
        try:
            f = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        finally: os.close(fd)
        try:
            before = os.fstat(f)
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= cap, "regular bounded single-link input required")
            chunks = []; total = 0
            while True:
                if clock: clock.check(cleanup)
                b = os.read(f, min(65536, cap-total+1))
                if not b: break
                total += len(b); require(total <= cap, "input exceeded bound")
                chunks.append(b)
            after = os.fstat(f)
            require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns), "input changed")
            body = b"".join(chunks)
            if pin:
                require(set(pin) >= {"bytes","sha256"}, "input pin")
                require(len(body)==pin["bytes"] and digest(body)==pin["sha256"], "input pin mismatch")
            return body
        finally: os.close(f)
    def json(self, rel, cap, **kw): return decode(self.read(rel,cap,**kw))
    def authenticate(self, rel, pin, *, cap, clock):
        """Stream the complete object without allocating its full body."""
        require(type(pin.get("sha256")) is str and len(pin["sha256"])==64,"digest pin")
        integer(pin.get("bytes"),"pinned bytes");require(pin["bytes"]<=cap,"stream cap")
        clock.check();p,leaf=self.parent(rel)
        try:f=os.open(leaf,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=p)
        finally:os.close(p)
        try:
            before=os.fstat(f)
            require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==pin["bytes"],"stream identity")
            h=hashlib.sha256();total=0
            while True:
                clock.check();b=os.read(f,65536)
                if not b:break
                total+=len(b);require(total<=cap,"stream grew");h.update(b)
            after=os.fstat(f)
            require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),"stream changed")
            require(total==pin["bytes"] and h.hexdigest()==pin["sha256"],"stream pin mismatch")
            clock.check();return {"path":rel,"bytes":total,"sha256":h.hexdigest()}
        finally:os.close(f)
    def write_new(self, rel, body, cap, *, clock, cleanup=False):
        require(type(body) is bytes and len(body) <= cap, "bounded bytes output")
        clock.check(cleanup)
        fd, leaf = self.parent(rel)
        f = None; created = False
        try:
            clock.check(cleanup)
            f = os.open(leaf, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600, dir_fd=fd)
            created = True
            offset = 0
            while offset < len(body):
                clock.check(cleanup)
                n = os.write(f, body[offset:offset+65536])
                require(n > 0, "short output write")
                offset += n
            clock.check(cleanup)
            os.fsync(f)
            clock.check(cleanup)
            os.fsync(fd)
            clock.check(cleanup)
            return {"path":rel,"bytes":len(body),"sha256":digest(body)}
        except BaseException as exc:
            # A partial file remains evidence; never masquerade as complete or overwrite it.
            if created: exc.add_note("Exclusive output may be partial; preserve it as failed-attempt evidence.")
            raise
        finally:
            if f is not None: os.close(f)
            os.close(fd)

