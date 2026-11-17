"""Same-open custody, original clocks and bounded operator-only failure accounting."""
from contextlib import contextmanager
from pathlib import Path
import hashlib
import json
import math
import os
import stat
import time
from . import contracts as c


def root(value, exists=True):
    c.need(type(value) is str and value.startswith("/") and value != "/", "absolute selected root")
    c.need(str(Path(value)) == value and not value.startswith("//")
           and all(x not in ("", ".", "..") for x in value.split("/")[1:]), "canonical absolute root")
    p = Path(value)
    for ancestor in reversed((p if exists else p.parent).parents):
        c.need(not ancestor.is_symlink(), "no symlink ancestor")
    q = p if exists else p.parent
    c.need(not q.is_symlink() and q.is_dir(), "real root directory")
    c.need(q.resolve(strict=True) == q, "physical canonical root")
    if not exists:
        c.need(not os.path.lexists(p), "fresh output root; no automatic retry")
    return p


def disjoint(*roots):
    for i, a in enumerate(roots):
        for b in roots[i + 1:]:
            c.need(a != b and a not in b.parents and b not in a.parents, "disjoint roots")


def child(base, rel, exists=True):
    c.relative(rel)
    p = base / rel
    c.need(not base.is_symlink(), "root symlink")
    q = base
    for segment in p.relative_to(base).parts[:-1]:
        q = q / segment
        c.need(not q.is_symlink(), "symlink path component")
    if exists:
        c.need(not p.is_symlink(), "symlink file")
    return p


def stamp(s):
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink, s.st_mode)


def error(exc, phase):
    try:
        message = str(exc)[:512]
    except BaseException:
        message = "exception message unavailable"
    return {"phase": str(phase)[:128], "type": type(exc).__name__[:128], "message": message}


class OperationFailure(c.Refused):
    """Caller retains record even if all output publication fails; not a public view."""
    def __init__(self, record):
        self.record = record
        super().__init__(record["primary"]["type"] + ": " + record["primary"]["message"])


def failure_record(exc, meter, phase, later=()):
    previous = exc.record if isinstance(exc, OperationFailure) else None
    errors = list(previous["later_errors"] if previous else [])
    omitted = previous.get("omitted_later_errors", 0) if previous else 0
    for where, item in later:
        if isinstance(item, OperationFailure):
            errors.append({**item.record["primary"], "during": str(where)[:128]})
            errors.extend(item.record["later_errors"])
            omitted += item.record.get("omitted_later_errors", 0)
        else:
            errors.append(error(item, where))
    omitted += max(0, len(errors) - 24)
    record = {"schema": "neural049_preparation_failure_v1", "status": "failed_or_incomplete",
              "primary": previous["primary"] if previous else error(exc, phase),
              "later_errors": errors[:24], "omitted_later_errors": omitted,
              "last_scope": str(phase)[:128], "cost_snapshot": meter.record() if meter else None,
              "no_automatic_retry": True, "manual_inspection_required": True,
              "unknowns": ["partial output extent and namespace durability require external inspection",
                           "physical IO, allocator/native overhead and external natural closure are unmeasured"],
              "failure_publication": previous.get("failure_publication", "not_attempted") if previous else "not_attempted"}
    return record


def raise_failed(store, output, exc, phase):
    """Always raises a bounded fallback; a FAILED file is evidence, never the sole account."""
    meter = store.meter if store else None
    record = failure_record(exc, meter, phase)
    later = []
    publication = "not_attempted_no_admitted_output_root"
    if output is not None:
        publication = "attempted_outcome_uncertain"
        try:
            body = c.canonical(record)
            store.put(output, "FAILED.json", body)
            publication = "returned_durable_under_original_clock"
        except BaseException as publishing:
            later.append(("FAILED.json publication", publishing))
    record = failure_record(exc, meter, phase, later)
    record["failure_publication"] = publication
    # This is a bounded operator return, independent of the remaining disk/clock allowance.
    raise OperationFailure(record) from exc


class Meter:
    def __init__(self, authority):
        self.origin, self.deadline = authority["origin"], authority["deadline"]
        self.limits = authority["limits"]
        c.need(type(self.origin) in (int, float) and type(self.deadline) in (int, float)
               and math.isfinite(self.origin) and math.isfinite(self.deadline)
               and self.deadline > self.origin, "selected original clock types")
        c.need(type(self.limits) is dict and set(self.limits) ==
               {"read_bytes", "write_bytes", "array_bytes", "metadata_bytes", "files"}
               and all(c.integer(v, 1) for v in self.limits.values()), "selected complete I/O limits")
        self.read_bytes = self.observed_read_bytes = self.write_bytes = self.observed_write_bytes = 0
        self.files = self.file_creation_attempts = self.directory_creation_attempts = 0
        self.operation_attempts = self.operation_returns = 0
        self.last_operation = "meter_created"
        try:
            self.tick()
        except BaseException as exc:
            raise OperationFailure(failure_record(exc, self, "inherited_initial_clock")) from exc

    def tick(self):
        now = time.monotonic()
        c.need(self.origin <= now < self.deadline, "original preparation clock expired/invalid")

    def call(self, label, fn, *args, **kwargs):
        self.tick()
        self.operation_attempts += 1
        self.last_operation = label + ":entered"
        result = fn(*args, **kwargs)
        self.operation_returns += 1
        self.last_operation = label + ":returned"
        self.tick()
        return result

    def charge(self, kind, n):
        self.tick()
        c.need(c.integer(n), "nonnegative I/O amount")
        key = kind + "_bytes"
        value = getattr(self, key) + n
        c.need(value <= self.limits[key], "selected cumulative " + kind + " limit")
        setattr(self, key, value)

    def array(self, n):
        self.tick()
        c.need(c.integer(n) and n <= self.limits["array_bytes"], "complete array exceeds selected working allocation")

    def record(self):
        return {"origin": self.origin, "deadline": self.deadline,
                "charged_read_request_bytes": self.read_bytes, "observed_logical_read_bytes": self.observed_read_bytes,
                "charged_write_request_bytes": self.write_bytes, "observed_logical_write_bytes": self.observed_write_bytes,
                "created_files": self.files, "file_creation_attempts": self.file_creation_attempts,
                "directory_creation_attempts": self.directory_creation_attempts,
                "operation_attempts": self.operation_attempts, "operation_returns": self.operation_returns,
                "last_operation": self.last_operation, "physical_io": "unmeasured",
                "snapshot_precedes_its_own_final_receipt_publication": True}


def bootstrap(path, expected, meter):
    """The caller supplies the independent original clock/read grant BEFORE any operand."""
    store = IO(meter)
    try:
        c.pin(expected)
        c.need(expected["bytes"] <= meter.limits["metadata_bytes"], "authority metadata cap")
        p = Path(path)
        base = root(str(p.parent))
        # Exact extent plus same-open authentication; both hash and JSON reads are charged.
        authority = store.json(base, {"path": p.name, "pin": expected})
        c.need(type(authority) is dict and c.typed_equal(
            {k: authority.get(k) for k in ("origin", "deadline", "limits")},
            {"origin": meter.origin, "deadline": meter.deadline, "limits": meter.limits}),
            "authority cannot reset independently inherited clock or read allowance")
        meter.tick()
        return authority, base
    except BaseException as exc:
        raise OperationFailure(failure_record(exc, meter, "authority_bootstrap")) from exc


class IO:
    def __init__(self, meter):
        self.meter = meter

    def _cleanup(self, later, phase, fn):
        # Expiry must be recorded but must not prevent the independent closure attempt.
        try:
            self.meter.tick()
        except BaseException as exc:
            later.append((phase + " preclock", exc))
        try:
            self.meter.operation_attempts += 1
            self.meter.last_operation = phase + ":entered"
            fn()
            self.meter.operation_returns += 1
            self.meter.last_operation = phase + ":returned"
        except BaseException as exc:
            later.append((phase, exc))
        try:
            self.meter.tick()
        except BaseException as exc:
            later.append((phase + " postclock", exc))

    def _name(self, p, expected, directory=False):
        # Recheck ancestors and current final name, not just the still-open descriptor.
        c.need(not any(x.is_symlink() for x in (p, *p.parents)), "current named custody has no symlinks")
        now = os.stat(p, follow_symlinks=False)
        c.need((stat.S_ISDIR(now.st_mode) if directory else stat.S_ISREG(now.st_mode) and now.st_nlink == 1)
               and stamp(now) == expected, "current name no longer matches authenticated descriptor")

    @contextmanager
    def opened(self, p, flags, *, write=False, directory=False):
        fd = raw = initial = None
        primary = None
        later = []
        try:
            self.meter.tick()
            if write:
                c.need(self.meter.files < self.meter.limits["files"], "output member count cap")
                self.meter.file_creation_attempts += 1
            # Assign the FD before the post-open clock check, retaining closure custody on expiry.
            self.meter.operation_attempts += 1; self.meter.last_operation = "open:entered"
            fd = os.open(p, flags, 0o600) if write else os.open(p, flags)
            self.meter.operation_returns += 1; self.meter.last_operation = "open:returned"
            if write:
                self.meter.files += 1
            self.meter.tick()
            initial = os.fstat(fd)
            c.need(stat.S_ISDIR(initial.st_mode) if directory else
                   stat.S_ISREG(initial.st_mode) and initial.st_nlink == 1, "ordinary same-open operand")
            self._name(p, stamp(initial), directory)
            if not directory:
                raw = os.fdopen(fd, "wb" if write else "rb", closefd=False)
            yield fd, raw, initial
        except BaseException as exc:
            primary = exc
        finally:
            closing_stamp = []
            if fd is not None:
                def custody():
                    now = os.fstat(fd)
                    if initial is not None:
                        c.need((now.st_dev, now.st_ino) == (initial.st_dev, initial.st_ino), "same descriptor inode")
                        if not write and not directory:
                            c.need(stamp(now) == stamp(initial), "source changed during decode")
                    self._name(p, stamp(now), directory)
                    closing_stamp.append(stamp(now))
                self._cleanup(later, "preclose descriptor/name custody", custody)
            if raw is not None:
                self._cleanup(later, "buffer close", raw.close)
            if fd is not None:
                self._cleanup(later, "descriptor close", lambda: os.close(fd))
            if closing_stamp:
                self._cleanup(later, "postclose name custody", lambda: self._name(p, closing_stamp[0], directory))
            try:
                self.meter.tick()
            except BaseException as exc:
                later.append(("operation final clock", exc))
            if primary is not None or later:
                if primary is None:
                    phase, primary = later.pop(0)
                else:
                    phase = "same_open_operation"
                raise OperationFailure(failure_record(primary, self.meter, phase, later)) from primary

    def sync_directory(self, p):
        with self.opened(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY, directory=True) as (fd, _, _):
            self.meter.call("directory fsync", os.fsync, fd)

    def mkdir(self, p):
        self.meter.tick()
        self.meter.directory_creation_attempts += 1
        try:
            self.meter.call("directory mkdir", p.mkdir, mode=0o700)
            self.sync_directory(p)
            self.sync_directory(p.parent)
            self.meter.tick()
        except BaseException as exc:
            raise OperationFailure(failure_record(exc, self.meter, "directory_setup")) from exc

    def parents(self, base, target):
        q = base
        c.need(not q.is_symlink() and q.is_dir(), "admitted existing output root")
        for part in target.relative_to(base).parts:
            q = q / part
            if not os.path.lexists(q):
                self.mkdir(q)
            c.need(not q.is_symlink() and q.is_dir(), "real output parent")

    @contextmanager
    def verified(self, base, descriptor):
        c.artifact(descriptor)
        p = child(base, descriptor["path"])
        expected = descriptor["pin"]
        with self.opened(p, os.O_RDONLY | os.O_NOFOLLOW) as (_, raw, before):
            c.need(before.st_size == expected["bytes"], "source exact extent")
            f = ReadView(raw, self.meter)
            h = hashlib.sha256(); left = expected["bytes"]
            while left:
                n = min(left, 1048576); block = f.read(n)
                c.need(len(block) == n, "short authenticated source")
                h.update(block); left -= n
            c.need(h.hexdigest() == expected["sha256"], "source hash")
            f.seek(0)
            yield f

    def json(self, base, descriptor):
        c.need(descriptor["pin"]["bytes"] <= self.meter.limits["metadata_bytes"], "metadata body cap")
        with self.meter.hold(descriptor["pin"]["bytes"] * 12 + 4096, "bounded JSON capture/decoder"):
            with self.verified(base, descriptor) as f:
                value = c.parse_json(f.read())
        self.meter.tick()
        return value

    def put(self, base, rel, body, private=False):
        c.need(type(body) is bytes, "explicit output bytes")
        c.need(len(body) <= self.meter.limits["metadata_bytes"], "metadata output cap")
        with self.writer(base, rel, private=private) as f:
            f.write(body)
        result = self.describe(base, rel)
        self.meter.tick()
        return result

    @contextmanager
    def writer(self, base, rel, private=False):
        p = child(base, rel, exists=False)
        self.parents(base, p.parent)
        c.need(not os.path.lexists(p), "fresh output member")
        with self.opened(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, write=True) as (fd, raw, _):
            f = WriteView(raw, self.meter)
            yield f
            f.flush()
            self.meter.call("file readonly chmod", os.fchmod, fd, 0o400 if private else 0o444)
            self.meter.call("file fsync", os.fsync, fd)
        self.sync_directory(p.parent)
        self.meter.tick()

    def describe(self, base, rel):
        p = child(base, rel)
        with self.opened(p, os.O_RDONLY | os.O_NOFOLLOW) as (_, raw, before):
            f = ReadView(raw, self.meter); h = hashlib.sha256(); left = before.st_size
            while left:
                n = min(left, 1048576); b = f.read(n)
                c.need(len(b) == n, "short output")
                h.update(b); left -= n
            result = {"path": rel, "pin": {"bytes": before.st_size, "sha256": h.hexdigest()}}
        self.meter.tick()
        return result

    def copy(self, source, desc, output, rel):
        with self.verified(source, desc) as src, self.writer(output, rel) as dst:
            left = desc["pin"]["bytes"]
            while left:
                b = src.read(min(left, 1048576)); c.need(b, "copy source incomplete")
                dst.write(b); left -= len(b)
        return self.describe(output, rel)


@contextmanager
def closing(resource, meter, phase):
    """Preserve native/read-helper initiating errors if its independent close also fails."""
    primary = None
    later = []
    try:
        meter.tick()
        yield resource
        meter.tick()
    except BaseException as exc:
        primary = exc
    finally:
        IO(meter)._cleanup(later, phase + " close", resource.close)
        if primary is not None or later:
            if primary is None:
                where, primary = later.pop(0)
            else:
                where = phase
            raise OperationFailure(failure_record(primary, meter, where, later)) from primary


class ReadView:
    def __init__(self, raw, meter):
        self.raw, self.meter = raw, meter
    def read(self, n=-1):
        if n is None or n < 0:
            here = self.tell(); self.seek(0, 2); n = self.tell() - here; self.seek(here)
        self.meter.charge("read", n)
        # Observation precedes the post-read clock, including short reads and expiry.
        body = self.raw.read(n)
        self.meter.observed_read_bytes += len(body)
        self.meter.tick()
        return body
    def readinto(self, buffer):
        self.meter.charge("read", memoryview(buffer).nbytes)
        count = self.raw.readinto(buffer)
        self.meter.observed_read_bytes += count or 0
        self.meter.tick()
        return count
    def seek(self, *args):
        return self.meter.call("seek", self.raw.seek, *args)
    def tell(self):
        return self.meter.call("tell", self.raw.tell)
    def seekable(self):
        return True
    def readable(self):
        return True
    def writable(self):
        return False
    def flush(self):
        self.meter.tick()
    @property
    def closed(self):
        return self.raw.closed


class WriteView:
    def __init__(self, raw, meter):
        self.raw, self.meter = raw, meter
    def write(self, body):
        n = memoryview(body).nbytes
        self.meter.charge("write", n)
        count = self.raw.write(body)
        self.meter.observed_write_bytes += count or 0
        self.meter.tick()
        c.need(count == n, "short output write")
        return count
    def flush(self):
        return self.meter.call("buffer flush", self.raw.flush)
    def tell(self):
        return self.meter.call("tell", self.raw.tell)
