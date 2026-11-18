"""Bounded host-side native slices and matched case delivery.

This module is source construction, not an admitted authentic run or sandbox.
The trusted host must first authenticate the complete accepted index manifest,
source receipt hashes and full saved-array proof. The source arrays must remain
in a host-owned immutable namespace. Closed descriptor/path signatures detect
replacement or ordinary modification; they are not a fresh whole-file rehash.
Participants must never import this module or receive its private arguments.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct

STAT_KEYS = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
WIDTHS = {"time": 8, "eeg": 16, "quality": 2}
SUFFIXES = {"time": "time.i64le.provisional", "eeg": "eeg.f64le.provisional",
            "quality": "quality.u8.provisional"}
SOURCE_PROOF = "f83503c5a6031c9043579b84bd48ae6925ceb9ace491c2c9abf1198fe00bd202"
SOURCE_COHORT = "1faf6f9c9d1b5c202c8d80a86fb779c50040f4ca94ab2e6b660984335464a2ed"
HASH = re.compile(r"[0-9a-f]{64}\Z")
MAX_SLICE_BYTES = 7501 * 26
DISCLOSURE = {
    "schema": "dosei_paired_workflow_disclosure_v1",
    "condition": "native_marker_relative_30s_v1",
    "target": "source_grouped_MOAAS_responsiveness_1_to_5",
    "time_relation": "retrospective_marker_association_not_verified_challenge_onset",
    "table_clock_hz": 250,
    "documented_nominal_EEG_channel_hz": 125,
    "source_blank_cells": "unobserved_common_grid_cells_not_imputed",
    "source_hardware_endpoints": "retained_and_flagged_not_removed",
    "display_policy": "dosei_observed_points_gap8_display_v1",
    "display_connections": "drawing_geometry_only_not_inserted_samples",
    "dataset_label_training": False,
    "demonstrations": [],
    "cross_case_feedback_or_memory": False,
    "task_specific_pretrained_detector": False,
    "clinical_diagnosis": False,
}


class DeliveryRefusal(ValueError):
    """No packet is publishable after an incomplete source projection."""


def require(value, message):
    if not value:
        raise DeliveryRefusal(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def signature(value):
    return {key: getattr(value, key) for key in STAT_KEYS}


class ReadBudget:
    """Logical array reads; interrupted attempts retain their requested charge.

    This excludes metadata, library/kernel and controller reads. A separately
    admitted driver must bound and report those costs and all output writes.
    """
    def __init__(self, limit):
        require(type(limit) is int and limit >= 0, "exact nonnegative array read limit")
        self.limit = limit
        self.confirmed = self.unknown = 0
        self.failed = False

    def read(self, fd, length, offset):
        require(not self.failed, "read budget is poisoned")
        require(type(length) is int and 0 < length <= 65536 and
                type(offset) is int and offset >= 0, "bounded positional read required")
        require(self.confirmed + self.unknown + length <= self.limit,
                "array read allowance exhausted")
        self.unknown += length
        try:
            raw = os.pread(fd, length, offset)
            require(type(raw) is bytes and len(raw) <= length, "unexpected read result")
        except BaseException:
            self.failed = True
            raise
        self.unknown -= length
        self.confirmed += len(raw)
        if len(raw) != length:
            self.failed = True
            raise DeliveryRefusal("short array slice; no retry")
        return raw

    def counters(self):
        return {"logical_array_read_bytes": self.confirmed,
                "unknown_attempt_bytes_charged": self.unknown,
                "limit_bytes": self.limit, "failed": self.failed}


def validate_binding(binding, root, rid, kind, rows):
    require(type(binding) is dict and set(binding) ==
            {"path", "bytes", "sha256", "closed_file_signature", "hash_scope"},
            "exact original closed array binding required")
    name = "recording-" + rid + "." + SUFFIXES[kind]
    require(binding["path"] == str(root / name), "array path differs from owned namespace")
    require(type(binding["bytes"]) is int and binding["bytes"] == rows * WIDTHS[kind],
            "complete array extent differs")
    require(type(binding["sha256"]) is str and HASH.fullmatch(binding["sha256"]),
            "complete verified array hash required")
    sig = binding["closed_file_signature"]
    require(type(sig) is dict and set(sig) == set(STAT_KEYS) and
            all(type(v) is int and v >= 0 for v in sig.values()) and
            sig["st_size"] == binding["bytes"], "closed array signature differs")
    require(type(binding["hash_scope"]) is str, "original hash scope required")
    return name, sig


def project_case(index, receipt, *, root, secret, budget, indexed, core, policy):
    """Read only the validated half-open slice, then form one public packet.

    `index` and `receipt` are trusted-host metadata authenticated by the complete
    admitted driver, not participant-provided objects. No original archive,
    event body, marker/future value or private label is exported. The same
    output packet is reused by both workflow transports.
    """
    require(type(budget) is ReadBudget and not budget.failed, "active logical read budget")
    clock, marker, start, end, coverage = indexed.validate_index(index, secret=secret, core=core)
    rid = index["evaluator"]["recording_id"]
    require(type(rid) is str and re.fullmatch("[1-9][0-9]*", rid), "exact recording key")
    require(type(receipt) is dict and receipt.get("schema") == "dosei_full_eeg_member_success_v1"
            and receipt.get("status") == "succeeded" and receipt.get("recording_id") == rid
            and type(receipt.get("source_rows")) is int and receipt["source_rows"] == clock.row_count
            and receipt.get("complete_source_EOF_CRC_SHA") is True
            and receipt.get("all_three_streams_closed_and_size_stat_checked") is True,
            "authenticated complete member receipt differs")
    outputs = receipt.get("outputs")
    require(type(outputs) is dict and set(outputs) == set(WIDTHS), "three native streams required")
    require(isinstance(root, Path) and root.is_absolute() and root.resolve() == root,
            "real absolute owned array directory required")
    require(hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY") and hasattr(os, "pread"),
            "no-follow positional filesystem interface required")
    expected = {kind: validate_binding(outputs[kind], root, rid, kind, clock.row_count)
                for kind in WIDTHS}
    require((end-start) * 26 <= MAX_SLICE_BYTES, "bounded complete half-open slice required")
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    handles = {}
    source_reads_before = budget.counters()
    try:
        root_before = os.fstat(directory)
        require(stat.S_ISDIR(root_before.st_mode) and not root_before.st_mode & 0o077 and
                signature(root_before) == signature(root.lstat()), "array directory identity differs")
        for kind, (name, wanted) in expected.items():
            fd = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=directory)
            handles[kind] = fd
            current = os.fstat(fd)
            require(stat.S_ISREG(current.st_mode) and not current.st_mode & 0o077 and signature(current) == wanted and
                    signature(os.stat(name, dir_fd=directory, follow_symlinks=False)) == wanted,
                    "accepted array identity changed before read")
        raw = {}
        for kind, width in WIDTHS.items():
            offset, remaining = start * width, (end-start) * width
            blocks = []
            while remaining:
                amount = min(65536, remaining)
                blocks.append(budget.read(handles[kind], amount, offset))
                offset += amount
                remaining -= amount
            raw[kind] = b"".join(blocks)
        for kind, (name, wanted) in expected.items():
            require(signature(os.fstat(handles[kind])) == wanted and
                    signature(os.stat(name, dir_fd=directory, follow_symlinks=False)) == wanted,
                    "accepted array identity changed during read")
        require(signature(os.fstat(directory)) == signature(root_before) == signature(root.lstat()),
                "array directory changed during read")
        def rows():
            for n in range(end-start):
                t = struct.unpack_from("<q", raw["time"], n*8)[0]
                v1, v2 = struct.unpack_from("<dd", raw["eeg"], n*16)
                q1, q2 = struct.unpack_from("BB", raw["quality"], n*2)
                require(q1 in (0, 1, 16) and q2 in (0, 1, 16),
                        "slice quality contradicts accepted release profile")
                yield start+n, t, v1, v2, q1, q2
        packet = indexed.project_window(index, rows(), secret=secret, core=core, policy=policy)
        encoded = canonical(packet)
        array_identity = {kind: {key: outputs[kind][key] for key in
                          ("bytes", "sha256", "closed_file_signature")} for kind in WIDTHS}
        evidence = {"schema": "dosei_host_slice_projection_receipt_v1",
                    "visibility": "evaluator_private", "case_id": packet["case_id"],
                    "observation_sha256": hashlib.sha256(encoded).hexdigest(),
                    "observation_bytes": len(encoded), "source_rows_read": end-start,
                    "array_identity_binding_sha256": hashlib.sha256(canonical(array_identity)).hexdigest(),
                    "slice_sha256": {kind: hashlib.sha256(value).hexdigest() for kind, value in raw.items()},
                    "read_counters_before": source_reads_before, "read_counters_after": budget.counters(),
                    "whole_array_hash_recomputed": False,
                    "complete_provenance_authentication_is_driver_obligation": True}
        return packet, evidence
    except BaseException:
        budget.failed = True
        raise
    finally:
        close_errors = []
        for fd in handles.values():
            try:
                os.close(fd)
            except BaseException as problem:
                close_errors.append(problem)
        try:
            os.close(directory)
        except BaseException as problem:
            close_errors.append(problem)
        if close_errors:
            budget.failed = True
            raise DeliveryRefusal("source descriptor close failed; packet refused") from close_errors[0]


class PairedCaseDelivery:
    """Trusted host object. Expose only explicit arm methods across isolation.

    Python object privacy is not a sandbox. Both methods share one authenticated
    packet/hash/disclosure; each participant requires a fresh external case
    context, no retained prior case answers, and no access to evaluator files.
    """
    def __init__(self, packet, projection, *, viewer):
        require(type(projection) is dict and projection.get("schema") ==
                "dosei_host_slice_projection_receipt_v1" and
                projection.get("case_id") == packet.get("case_id"), "matched host projection required")
        self._packet = copy.deepcopy(packet)
        self._raw = canonical(self._packet)
        digest = hashlib.sha256(self._raw).hexdigest()
        require(projection.get("observation_sha256") == digest, "materialized packet hash differs")
        identity = projection.get("array_identity_binding_sha256")
        require(type(identity) is str and HASH.fullmatch(identity), "accepted array identity binding required")
        self._profile = {"schema": "dosei_renderer_source_profile_v1",
                         "source_proof_sha256": SOURCE_PROOF,
                         "source_cohort_sha256": SOURCE_COHORT,
                         "array_identity_binding_sha256": identity,
                         "case_id": self._packet["case_id"], "observation_sha256": digest,
                         "source_quality_values": [[0, 1, 16], [0, 1, 16]],
                         "display_policy": DISCLOSURE["display_policy"]}
        self._viewer = viewer.TraceViewer(self._packet, self._profile)
        self._binding = {"case_id": self._packet["case_id"], "observation_sha256": digest}

    def public_binding(self):
        return dict(self._binding)

    def disclosure(self):
        return copy.deepcopy(DISCLOSURE)

    def viewer_action(self, command):
        # Renderer receipt remains server-side; plot contains no private identity.
        png, internal_receipt = self._viewer.action(command)
        require(internal_receipt["observation_sha256"] == self._binding["observation_sha256"],
                "viewer changed matched observation")
        return png

    def code_observation(self):
        # Canonical immutable bytes are the same observation hashed for viewer.
        return self._raw
