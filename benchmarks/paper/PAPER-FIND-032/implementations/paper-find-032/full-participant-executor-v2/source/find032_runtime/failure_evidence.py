"""Private, bounded original evidence for failed FIND032 Docker commands.

Import is inert. persist is a future explicitly budgeted file-publication leaf;
it does not read inputs, launch commands, retry science, or issue qualification.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time
import types


MAX_FAILURES = 7
MAX_SECONDARY = 16
METADATA_CAP = 131072
MAX_CAP = 8388608
_EXCEPTION_CAP = 640


class EvidenceError(ValueError):
    pass


def _need(value, reason):
    if not value:
        raise EvidenceError(reason)


def _encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def _type(value):
    """Read type descriptors directly; never invoke an object's formatter."""
    cls = type(value)
    module = type.__dict__["__module__"].__get__(cls, type)
    name = type.__dict__["__qualname__"].__get__(cls, type)
    bounded = lambda item: (type(item) is str and len(item) <= 64 and
                            all(32 <= ord(character) < 127 for character in item))
    return {"module": module if bounded(module) else None,
            "qualname": name if bounded(name) else None}


def _value(value, depth=0):
    kind = type(value)
    if value is None or kind in (bool,):
        return {"exact": True, "value": value}
    if kind is int and value.bit_length() <= 256:
        return {"exact": True, "value": value}
    if kind is float and math.isfinite(value):
        return {"exact": True, "value": value}
    if kind is str and len(value) <= 96:
        return {"exact": True, "value": value}
    if kind in (tuple, list) and depth < 2 and len(value) <= 4:
        items = [_value(item, depth + 1) for item in value]
        return {"exact": all(item["exact"] for item in items),
                "sequence_type": "tuple" if kind is tuple else "list", "items": items}
    result = {"exact": False, "unresolved": "opaque_or_bounded_argument",
              "type": _type(value)}
    if kind in (bytes, bytearray, str, tuple, list):
        result["extent"] = len(value)
    return result


def _exception(error):
    """A bounded structural projection; the caller retains the actual object."""
    _need(isinstance(error, BaseException), "original-base-exception-required")
    args = BaseException.__dict__["args"].__get__(error, BaseException)
    trace = BaseException.__dict__["__traceback__"].__get__(error, BaseException)
    cause = BaseException.__dict__["__cause__"].__get__(error, BaseException)
    context = BaseException.__dict__["__context__"].__get__(error, BaseException)
    argument = _value(args)
    frames = []
    seen = set()
    truncated = False
    while trace is not None:
        if type(trace) is not types.TracebackType or id(trace) in seen or len(frames) >= 4:
            truncated = True
            break
        seen.add(id(trace))
        code = trace.tb_frame.f_code
        filename, name = code.co_filename, code.co_name
        valid = type(filename) is str and len(filename) <= 256 and type(name) is str and len(name) <= 96
        frames.append({"filename": filename if valid else None,
                       "function": name if valid else None,
                       "line": trace.tb_lineno, "first_line": code.co_firstlineno,
                       "unresolved": None if valid else "source_descriptor_extent"})
        trace = trace.tb_next
    result = {"type": _type(error), "args": argument, "traceback": frames,
              "traceback_truncated": truncated,
              "linked_exception_objects_not_serialized": cause is not None or context is not None,
              "identity_scope": "structural_source_descriptors_only_not_python_object_identity",
              "source_files_opened": False}
    unresolved = (not argument["exact"] or truncated or any(row["unresolved"] for row in frames)
                  or cause is not None or context is not None or
                  any(value is None for value in result["type"].values()))
    if len(_encoded(result)) > _EXCEPTION_CAP:
        result = {"type": _type(error), "args": {"exact": False, "unresolved": "exception_metadata_extent"},
                  "traceback": frames[:1], "traceback_truncated": True,
                  "identity_scope": "bounded_structural_projection_not_python_object_identity",
                  "source_files_opened": False}
        unresolved = True
    result["unresolved"] = bool(unresolved)
    if len(_encoded(result)) > _EXCEPTION_CAP:
        result["traceback"] = []
        result["traceback_truncated"] = True
        result["unresolved"] = True
    return result


def describe_original_errors(errors):
    """Fixed task bound: one body plus six retirements, with no object formatting.

    The caller keeps the actual objects. These bounded structural observations
    also cover parse/identity errors after an otherwise successful CLI command.
    Frame locals and arbitrary Python objects are explicitly not serialized.
    """
    _need(type(errors) in (tuple, list) and len(errors) <= 8,
          "bounded_original_body_and_retirement_errors")
    rows = [_exception(error) for error in errors]
    return {"errors": rows, "original_error_count": len(errors),
            "structurally_complete": not any(row["unresolved"] for row in rows),
            "frame_locals_serialized": False,
            "python_object_identity_survives_exit": False}


def _record(value):
    allowed = {"phase", "returncode", "error_type", "observed_retained_bytes", "seconds",
               "client_reaped", "cleanup_complete", "cleanup_before_original_cutoff",
               "owned_group_absence_observed", "leader_exited_with_group_alive",
               "group_probe_or_cleanup_error"}
    if type(value) is not dict or set(value) != allowed:
        return {"unresolved": "original_command_record_shape"}
    for key, item in value.items():
        if type(item) not in (str, int, float, bool, type(None)):
            return {"unresolved": "opaque_command_record"}
        if type(item) is str and len(item) > 256:
            return {"unresolved": "command_record_string_extent"}
        if type(item) is int and item.bit_length() > 256:
            return {"unresolved": "command_record_integer_extent"}
        if type(item) is float and not math.isfinite(item):
            return {"unresolved": "nonfinite_command_record"}
    return dict(value)


def _command(value):
    if type(value) not in (tuple, list):
        return {"unresolved": "original_command_type"}
    if len(value) <= 128 and all(type(item) is str and len(item) <= 512 for item in value):
        result = {"argv": list(value)}
        if len(_encoded(result)) <= 4096:
            return result
    return {"unresolved": "original_command_extent", "argc": len(value)}


def _tick(deadline):
    _need(time.monotonic() < deadline, "original_failure_evidence_deadline")


def _write(root, root_fd, name, body, deadline, errors):
    """One create-only output; preserve errors and independently close the FD."""
    fd = None
    written = 0
    pending = False
    local = []
    descriptor = None
    observed = None
    try:
        _tick(deadline)
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=root_fd)
        start = os.fstat(fd)
        _need(stat.S_ISREG(start.st_mode) and start.st_nlink == 1 and
              stat.S_IMODE(start.st_mode) == 0o600, "private_ordinary_failure_output")
        view = memoryview(body)
        while written < len(body):
            _tick(deadline)
            pending = True
            count = os.write(fd, view[written:written + 65536])
            pending = False
            _need(type(count) is int and 0 < count <= min(65536, len(body) - written),
                  "complete_failure_output_write")
            written += count
        _tick(deadline)
        os.fsync(fd)
        observed = os.fstat(fd)
        named = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
        _need(observed.st_ino == named.st_ino == start.st_ino and
              observed.st_dev == named.st_dev == start.st_dev and
              observed.st_size == named.st_size == len(body) and
              observed.st_nlink == named.st_nlink == 1 and
              stat.S_IMODE(observed.st_mode) == stat.S_IMODE(named.st_mode) == 0o600,
              "same_complete_failure_output")
        os.fsync(root_fd)
        _tick(deadline)
        descriptor = {"path": name, "bytes": len(body),
                      "sha256": hashlib.sha256(body).hexdigest(), "mode": 0o600}
    except BaseException as error:
        local.append(error)
        errors.append(error)
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except BaseException as error:
                local.append(error)
                errors.append(error)
    return {"name": name, "descriptor": descriptor, "bytes_written": written,
            "write_outcome_unknown": pending, "complete": descriptor is not None and not local,
            "allocated_bytes": None if observed is None else observed.st_blocks * 512,
            "publication_errors": [_exception(error) for error in local]}


def persist(directory, failures, byte_cap, deadline):
    """Publish only failed raw streams and bounded structural original evidence.

    Returns raw objects separately from its JSON-safe summary; publication never
    replaces the original command exception. No cleanup/retry/qualification is
    inferred from a successful evidence write. byte_cap covers prospective total
    allocation, including metadata and filesystem rounding, not raw bytes alone.
    """
    original = tuple(failures) if type(failures) in (tuple, list) and len(failures) <= MAX_FAILURES else ()
    errors = []
    products = []
    structures = []
    metadata = None
    root_fd = None
    parent_fd = None
    reserve = None
    raw_total = 0
    allocated = None
    unresolved = []
    try:
        _need(type(failures) in (tuple, list) and 0 < len(failures) <= MAX_FAILURES,
              "one_to_seven_original_failures")
        _need(type(byte_cap) is int and METADATA_CAP < byte_cap <= MAX_CAP,
              "fixed_selected_failure_evidence_cap")
        _need(type(deadline) in (int, float) and math.isfinite(deadline),
              "finite_original_failure_evidence_deadline")
        _tick(deadline)
        root = Path(directory)
        _need(root.is_absolute() and len(root.parts) <= 64 and ".." not in root.parts,
              "absolute_bounded_failure_directory")
        _need(not root.exists() and not root.is_symlink(), "fresh_failure_directory")
        for parent in root.parents:
            _need(not parent.is_symlink(), "unlinked_failure_directory_ancestry")
        _need(root.parent.is_dir(), "existing_owned_failure_parent")
        expected = {"exception", "rawstdout", "rawstderr", "record", "secondary_exceptions",
                    "command", "original_result", "wait_returns", "eof"}
        for index, failure in enumerate(original):
            _need(type(failure) is dict and set(failure) == expected, "exact_original_failure_record")
            for key in ("rawstdout", "rawstderr"):
                _need(type(failure[key]) in (bytes, bytearray), "original_raw_stream_bytes")
                raw_total += len(failure[key])
                _need(raw_total <= byte_cap - METADATA_CAP, "full_failed_raw_byte_reservation")
            second = failure["secondary_exceptions"]
            _need(type(second) is tuple and len(second) <= MAX_SECONDARY, "bounded_original_cleanup_failures")
            _need(type(failure["wait_returns"]) is tuple and len(failure["wait_returns"]) <= 2 and
                  all(type(code) is int and -(1 << 31) <= code < (1 << 31)
                      for code in failure["wait_returns"]), "original_wait_result_extent")
            _need(type(failure["eof"]) is dict and set(failure["eof"]) == {"out", "err"} and
                  all(type(value) is bool for value in failure["eof"].values()), "original_stream_eof")
            value = failure["original_result"]
            _need(value is None or type(value) is bytes and value == failure["rawstdout"],
                  "original_failed_command_return_is_stdout")
            first = _exception(failure["exception"])
            secondary = [_exception(error) for error in second]
            record = _record(failure["record"])
            command = _command(failure["command"])
            row = {"failure_index": index, "original_exception": first,
                   "secondary_exceptions": secondary, "command": command, "record": record,
                   "original_result_returned_before_cleanup_failure": value is not None,
                   "original_result_is_exact_stdout": value is not None,
                   "original_wait_returns": list(failure["wait_returns"]),
                   "original_eof": dict(failure["eof"]),
                   "raw_streams_are_observed_prefixes": not all(failure["eof"].values()),
                   "python_object_identity_survives_exit": False}
            if (first["unresolved"] or any(item["unresolved"] for item in secondary) or
                    "unresolved" in record or "unresolved" in command):
                unresolved.append(index)
            structures.append(row)
        _tick(deadline)
        block = os.statvfs(root.parent).f_frsize
        _need(type(block) is int and 0 < block <= byte_cap, "actual_failure_filesystem_rounding")
        rounding = lambda size: max(1, (size + block - 1) // block) * block
        # Reserve a further block for the new entry in the existing parent.
        reserve = 2 * block + rounding(METADATA_CAP) + sum(
            rounding(len(row[key])) for row in original for key in ("rawstdout", "rawstderr"))
        _need(reserve <= byte_cap, "complete_failure_allocation_reservation")
        _tick(deadline)
        parent_fd = os.open(root.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        root.mkdir(mode=0o700)
        os.fsync(parent_fd)
        root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        root_stat = os.fstat(root_fd)
        _need(stat.S_IMODE(root_stat.st_mode) == 0o700, "private_failure_directory")
        for index, failure in enumerate(original):
            for suffix, key in (("stdout", "rawstdout"), ("stderr", "rawstderr")):
                name = "command-" + format(index, "02d") + "." + suffix
                products.append(_write(root, root_fd, name, failure[key], deadline, errors))
        body = {"schema": "find032_original_command_failures_v1", "task_id": "PAPER-FIND-032",
                "failures": structures, "raw_products": products, "raw_bytes": raw_total,
                "allocation_reservation_bytes": reserve, "allocation_rounding_bytes": block,
                "parent_directory_entry_growth_reserved_bytes": block,
                "metadata_cap_bytes": METADATA_CAP, "retention_cap_bytes": byte_cap,
                "unresolved_failure_indices": unresolved, "scientific_success": False,
                "original_python_objects_retained_only_in_live_parent": True,
                "publication_errors_before_metadata": [_exception(error) for error in errors]}
        raw = _encoded(body)
        _need(len(raw) <= METADATA_CAP, "complete_structural_evidence_extent")
        metadata = _write(root, root_fd, "EVIDENCE.json", raw, deadline, errors)
        all_products = products + [metadata]
        if all(row["allocated_bytes"] is not None for row in all_products):
            allocated = os.fstat(root_fd).st_blocks * 512 + sum(row["allocated_bytes"] for row in all_products)
            _need(allocated <= byte_cap, "actual_complete_failure_allocation")
        _tick(deadline)
    except BaseException as error:
        errors.append(error)
    finally:
        if root_fd is not None:
            try:
                os.close(root_fd)
            except BaseException as error:
                errors.append(error)
        if parent_fd is not None:
            try:
                os.close(parent_fd)
            except BaseException as error:
                errors.append(error)
    published = metadata is not None and metadata["complete"] and all(row["complete"] for row in products)
    summary = {"schema": "find032_failure_evidence_result_v1", "raw_bytes": raw_total,
               "allocation_reservation_bytes": reserve, "observed_allocated_bytes": allocated,
               "raw_products": products, "metadata": metadata,
               "publications_complete": bool(published and not errors),
               "complete": bool(published and not errors and not unresolved),
               "unresolved_failure_indices": unresolved,
               "publication_errors": [_exception(error) for error in errors],
               "scientific_success": False, "python_object_identity_survives_exit": False}
    return {"summary": summary, "original_failures": original,
            "publication_errors": tuple(errors)}
