"""Sequential trusted delivery, with a durable CV commitment before full data.

The participant sees only observe()'s payload. This is not a process sandbox,
resume mechanism, execution attestation or permission to reuse participant state.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import stat


def _load_collector():
    path = Path(__file__).with_name("submissions.py")
    spec = importlib.util.spec_from_file_location("temporal026_delivery_collector", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _new_json(path, value, encode, maximum):
    raw = encode(value)
    if not raw.endswith(b"\n"):
        raw += b"\n"
    _require(len(raw) <= maximum, "delivery receipt exceeds bound")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
        os.fchmod(handle.fileno(), 0o400)
    return {"path": path.name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _verify_file(directory, pin):
    from pathlib import PurePosixPath
    path = PurePosixPath(pin["path"])
    _require(not path.is_absolute() and ".." not in path.parts and
             str(path) == pin["path"] and "\\" not in pin["path"],
             "noncanonical committed record path")
    _require(type(pin["bytes"]) is int and 0 < pin["bytes"] <= 16 * 1024 * 1024,
             "committed record size bound")
    parent = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            os.close(parent)
            parent = child
        fd = os.open(path.parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
        with os.fdopen(fd, "rb") as handle:
            before = os.fstat(handle.fileno())
            _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                     before.st_size == pin["bytes"], "committed record identity/extent changed")
            hasher = hashlib.sha256()
            count = 0
            while count <= pin["bytes"]:
                chunk = handle.read(min(65536, pin["bytes"] + 1 - count))
                if not chunk:
                    break
                hasher.update(chunk)
                count += len(chunk)
            after = os.fstat(handle.fileno())
        _require(count == pin["bytes"] and hasher.hexdigest() == pin["sha256"] and
                 (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
                  before.st_ctime_ns) ==
                 (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
                  after.st_ctime_ns), "committed record bytes changed")
    finally:
        os.close(parent)


class DeliverySession:
    """One fresh operator-owned run; no filesystem or participant-state resume.

    Freeze the participant procedure before construction. Invoke each observation
    in a fresh participant context, then commit its returned prediction or failure.
    Neither this object nor the source/input roots may be passed to participants.
    """

    def __init__(self, protocol, directory):
        self.protocol = protocol
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o700, parents=False, exist_ok=False)
        self.predictions_directory = self.directory / "predictions"
        self.predictions_directory.mkdir(mode=0o700)
        self._collector = _load_collector()
        self._writer = self._collector.Writer(self.predictions_directory, protocol)
        self._jobs = protocol.delivery_jobs
        self._cursor = 0
        self._pending = None
        self._pins = []
        self._cv_pin = None
        self._closed = False

    @property
    def complete(self):
        return self._cursor == len(self._jobs)

    @property
    def committed_jobs(self):
        return self._cursor

    def observe(self, input_root):
        _require(not self._closed and not self.complete, "delivery already complete or closed")
        _require(self._pending is None, "commit the current response before another observation")
        job = self._jobs[self._cursor]
        if job["mode"] == "full":
            _require(self._cv_pin is not None, "all CV outputs must freeze before full observations")
            _verify_file(self.directory, self._cv_pin)
        # A failed projection leaves no active candidate observation; do not
        # infer that a participant ran or advance the original support.
        observation = self.protocol.project_job(input_root, job["id"])
        self._pending = job["id"]
        return observation

    def submit(self, *, predictions=None, failure=None):
        _require(not self._closed and self._pending is not None,
                 "an original observation must precede its submission")
        pin = self._writer.write(self._pending, predictions=predictions, failure=failure)
        self._pins.append({"job_id": self._pending,
                           **{key: pin[key] for key in ("path", "bytes", "sha256")}})
        self._cursor += 1
        self._pending = None
        if self._cursor == 1896:
            # All original CV record bodies are stable before this immutable
            # commitment is written; no full-data observations were delivered.
            for committed in self._pins:
                _verify_file(self.predictions_directory, committed)
            self._cv_pin = _new_json(
                self.directory / "CV_FREEZE.json",
                {"schema": "temporal026-cv-output-commitment/v1",
                 "protocol_sha256": self.protocol.protocol_sha256,
                 "method_sha256": self.protocol.method_sha256,
                 "count": 1896, "records": self._pins[:],
                 "limit": "content commitment in operator custody; no OS/provider isolation attestation"},
                self._collector.encoded, 2 * 1024 * 1024)
        return pin

    def seal(self):
        _require(not self._closed and self.complete and self._pending is None,
                 "all 2054 original jobs must be committed before sealing")
        _require(self._cv_pin is not None, "CV commitment required")
        _verify_file(self.directory, self._cv_pin)
        # Later full-data access cannot retroactively replace held-out outputs.
        for pin in self._pins[:1896]:
            _verify_file(self.predictions_directory, pin)
        final = self._collector.seal(self.predictions_directory, self.protocol)
        receipt = _new_json(
            self.directory / "DELIVERY_RECEIPT.json",
            {"schema": "temporal026-sequential-delivery-receipt/v1",
             "protocol_sha256": self.protocol.protocol_sha256,
             "plan_sha256": self.protocol.plan_sha256,
             "method_sha256": self.protocol.method_sha256,
             "condition": self.protocol.condition,
             "cv_jobs_committed_before_full_observations": 1896,
             "full_jobs_committed": 158,
             "cv_commitment": self._cv_pin,
             "complete_submission": {**final, "path": "predictions/" + final["path"]},
             "runtime_isolation_qualified": False,
             "scientific_qualification": False}, self._collector.encoded, 65536)
        self._closed = True
        return {"submission": final, "delivery_receipt": receipt}
