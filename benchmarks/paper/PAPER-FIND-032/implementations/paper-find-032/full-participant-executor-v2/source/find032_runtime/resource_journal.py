"""Parent-owned FIND032 resource journal. Import does not open or execute anything."""
import hashlib
import json
import os
import time

from .n071_linux.capacity import Capacity
from .n071_linux.custody import Owner, require
from .n071_linux.filesystem import Directory, acquire_fd

EVENTS = 29
FIRST_BYTES = 1024
EVENT_BYTES = 1024
BODY_CAP = FIRST_BYTES + (EVENTS - 1) * EVENT_BYTES


class Journal:
    """One append-only original file, retained even after a partial failed write."""
    def __init__(self, root, name, deadline, byte_cap):
        require(type(root) is Directory and type(root.owner) is Owner and
                type(root.capacity) is Capacity, "actual-journal-owner")
        require(name == "RESOURCE_JOURNAL.jsonl" and
                type(deadline) in (int, float) and time.monotonic() < deadline and
                type(byte_cap) is int and BODY_CAP <= byte_cap <= 20000000,
                "fixed-journal-extent-and-original-deadline")
        self.root, self.owner, self.capacity = root, root.owner, root.capacity
        self.owner_pid = os.getpid()
        self.deadline, self.byte_cap = deadline, byte_cap
        self.sequence, self.offset, self.attempts = 0, 0, 0
        self.first, self.failures, self.raw_returns = None, [], []
        self.fd = None
        self.closed = False
        self.digest = hashlib.sha256()
        self.birth = self.owner.begin("find032-journal-birth")
        self.owner.retain(self)
        try:
            self.capacity.consume_attempt("creation_attempts", "find032-journal-create")
            self.fd = acquire_fd(self.owner, self.capacity, name,
                os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_EXCL,
                parent=root.fd.require_live(), mode=0o600)
            self.birth.returned.append(self.fd)
            self.birth.finish()
        except BaseException as error:
            self._fail(error, "journal-birth")
            raise

    def _fail(self, error, where):
        if self.first is None:
            self.first = error
        self.failures.append((where, error))
        self.birth.fail(error, where)

    def append(self, record):
        require(os.getpid() == self.owner_pid, "original-journal-process")
        require(not self.closed and self.first is None and self.fd is not None,
                "journal-live-with-no-original-failure")
        require(self.attempts < EVENTS and type(record) is dict and
                record.get("sequence") == self.sequence, "finite-original-event-order")
        self.attempts += 1
        attempt = self.owner.begin("find032-journal-event")
        raw = None
        token = None
        count = 0
        pending = False
        start = self.offset
        try:
            require(time.monotonic() < self.deadline, "original-journal-clock")
            raw = (json.dumps(record, sort_keys=True, separators=(",", ":"),
                              allow_nan=False) + "\n").encode("utf8")
            bound = FIRST_BYTES if self.sequence == 0 else EVENT_BYTES
            require(len(raw) <= bound and self.offset + len(raw) <= self.byte_cap,
                    "actual-event-and-whole-journal-bound")
            # Raw bytes and their original effect remain held on every failure.
            attempt.returned.append(raw)
            memory = self.capacity.reserve("rss_bytes", len(raw), "journal-original-buffer")
            self.capacity.settle(memory, len(raw))
            token = self.capacity.reserve("write_bytes", len(raw), "journal-append")
            while count < len(raw):
                require(time.monotonic() < self.deadline, "original-journal-write-clock")
                pending = True
                n = os.write(self.fd.require_live(), memoryview(raw)[count:])
                count += n
                self.offset += n
                pending = False
                require(0 < n <= len(raw) - (count - n), "journal-write-progress")
            pending = True
            os.fsync(self.fd.require_live())
            pending = False
            result = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                      "offset": start, "sequence": self.sequence}
            self.raw_returns.append(result)
            self.digest.update(raw)
            self.sequence += 1
            attempt.returned.append(result)
        except BaseException as error:
            self._fail(error, "journal-append")
            attempt.fail(error, "journal-append")
            if pending:
                attempt.uncertain("journal-unacknowledged-prefix",
                                  {"known_bytes": count, "offset": self.offset})
        finally:
            if token is not None:
                try:
                    self.capacity.settle(token, count, unknown=pending)
                except BaseException as error:
                    self._fail(error, "journal-settlement")
                    attempt.fail(error, "journal-settlement")
            # Raw buffers remain in original attempt custody. No invented release.
        attempt.raise_first()
        attempt.finish()
        return result

    def close(self):
        require(os.getpid() == self.owner_pid, "original-journal-closing-process")
        if self.closed:
            return
        self.closed = True
        errors = []
        if self.fd is not None:
            try:
                require(time.monotonic() < self.deadline, "journal-close-original-clock")
                os.fsync(self.fd.require_live())
                os.fchmod(self.fd.require_live(), 0o400)
            except BaseException as error:
                errors.append(error)
                self._fail(error, "journal-finalization")
            try:
                self.fd.close()
            except BaseException as error:
                errors.append(error)
                self._fail(error, "journal-close")
        if errors:
            raise errors[0]

    def projection(self):
        return {"schema": "find032_original_resource_journal_v1",
                "events_returned": self.sequence, "append_attempts": self.attempts,
                "acknowledged_bytes": self.offset,
                "complete_event_digest": self.digest.hexdigest(),
                "closed": self.closed, "failed": self.first is not None,
                "partial_originals_retained": True,
                "scientific_or_native_qualification": False}

