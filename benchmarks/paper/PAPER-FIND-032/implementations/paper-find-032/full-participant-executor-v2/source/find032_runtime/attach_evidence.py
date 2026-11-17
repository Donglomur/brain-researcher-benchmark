"""Precharged durable original attach prefixes, before any arm retirement.

This task-specific receipt reuses the existing failure-evidence byte writer and
bounded structural projections. It never fabricates a command exception or
replaces the original carrier. Success publication is also required, so a later
inspection/capture failure cannot lose already observed candidate streams.
"""
import os
from pathlib import Path
import time

from find032.core import encode_json
from .failure_evidence import _write, _exception, _command, _record, METADATA_CAP
from .staging import need


class AttachEvidence:
    def __init__(self, arm, budget, byte_cap, stdio_cap, deadline):
        self.arm, self.budget, self.byte_cap = arm, budget, byte_cap
        self.stdio_cap, self.deadline = stdio_cap, deadline
        self.body_token = budget.reserve("write", byte_cap)
        self.files_token = budget.reserve("files", 4)
        self.path = None
        self.attempted = False
        self.original = None
        self.errors = []
        self.products = []
        self.metadata = None
        self.complete = False

    def bind(self, workspace):
        need(self.path is None, "one original attach evidence location")
        root = Path(workspace)
        block = os.statvfs(root).f_frsize
        need(type(block) is int and block > 0 and
             self.stdio_cap + 1 + METADATA_CAP + 6 * block <= self.byte_cap,
             "selected full original attach streams, metadata and filesystem rounding fit")
        self.path = root / (self.arm + "_ATTACH_EVIDENCE")

    def publish(self, carrier, first):
        need(not self.attempted and self.path is not None, "one preselected original attach publication")
        self.attempted = True
        self.original = carrier
        root_fd = parent_fd = None
        try:
            need(time.monotonic() < self.deadline, "original reserved attach receipt cutoff")
            fields = {"exception", "rawstdout", "rawstderr", "record", "secondary_exceptions",
                      "command", "original_result", "wait_returns", "eof"}
            need(type(carrier) is dict and set(carrier) == fields and
                 type(carrier["rawstdout"]) in (bytes, bytearray) and
                 type(carrier["rawstderr"]) in (bytes, bytearray) and
                 len(carrier["rawstdout"]) + len(carrier["rawstderr"]) <= self.stdio_cap + 1,
                 "actual bounded attach carrier including original overflow probe")
            parent_fd = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            os.mkdir(self.path.name, 0o700, dir_fd=parent_fd)
            os.fsync(parent_fd)
            root_fd = os.open(self.path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
            # Attempt both original streams independently. Existing _write keeps
            # partial/unknown effects and secondary descriptor errors explicit.
            for name, key in (("stdout.bin", "rawstdout"), ("stderr.bin", "rawstderr")):
                self.products.append(_write(self.path, root_fd, name, carrier[key], self.deadline, self.errors))
            secondaries = carrier["secondary_exceptions"]
            need(type(secondaries) is tuple and len(secondaries) <= 16,
                 "bounded original attach secondary evidence")
            record = {"schema": "FIND032_ORIGINAL_ATTACH_EVIDENCE_V1", "arm": self.arm,
                "original_command": _command(carrier["command"]), "record": _record(carrier["record"]),
                "original_attach_exception": None if carrier["exception"] is None else _exception(carrier["exception"]),
                "first_session_error_at_attach": None if first is None else _exception(first),
                "secondary_exceptions": [_exception(x) for x in secondaries],
                "wait_returns": list(carrier["wait_returns"]), "eof": dict(carrier["eof"]),
                "raw_streams": self.products,
                "prefix_only": not all(carrier["eof"].values()), "original_carrier_modified": False,
                "publication_errors_before_metadata": [_exception(x) for x in self.errors],
                "scientific_or_native_qualification": False}
            raw = encode_json(record)
            need(len(raw) <= METADATA_CAP, "complete preselected structural attach metadata")
            self.metadata = _write(self.path, root_fd, "EVIDENCE.json", raw, self.deadline, self.errors)
            need(time.monotonic() < self.deadline, "attach receipt before original owner admission cutoff")
        except BaseException as error:
            self.errors.append(error)
        finally:
            for fd in (root_fd, parent_fd):
                if fd is not None:
                    try:
                        os.close(fd)
                    except BaseException as error:
                        self.errors.append(error)
        self.complete = bool(self.metadata is not None and self.metadata["complete"] and
                             len(self.products) == 2 and all(x["complete"] for x in self.products) and not self.errors)
        if self.complete:
            try:
                self.budget.observed(self.body_token, sum(x["bytes_written"] for x in [*self.products, self.metadata]))
                self.budget.observed(self.files_token, 4)
            except BaseException as error:
                self.errors.append(error)
                self.complete = False
        if self.errors:
            raise self.errors[0]
        need(self.complete, "durable original attach evidence required")

    def report(self):
        return {"path": None if self.path is None else str(self.path), "attempted": self.attempted,
                "complete": self.complete, "raw_products": self.products, "metadata": self.metadata,
                "publication_errors": [_exception(x) for x in self.errors],
                "unavailable": not self.complete, "native_or_scientific_success": False}
