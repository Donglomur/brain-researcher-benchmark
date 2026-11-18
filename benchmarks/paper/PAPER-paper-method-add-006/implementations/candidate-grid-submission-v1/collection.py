"""Freeze and authenticate the complete original population-geometry grid.

This trusted operator utility receives already-produced outputs. It does not
run participant code or establish training, delivery, phase isolation, or a
scientific improvement. In particular, every readout must be frozen before an
external delivery system releases full target latents for covariance analysis.
The file collector alone cannot attest that earlier information boundary.

No reference callback is called until the whole submitted grid, every payload,
and its externally retained COMPLETE hash have passed authentication. Evaluation
results are an operator-only iterator; publishing feedback and allowing further
attempts are separate policies. The operator must exclude concurrent writers.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat

from deps import G, R, P, K

EXPECTED_COUNTS = {"glm": 13824, "geometry": 64000}
LINE_CAP = 4096
CLOSURE_CAP = 8192
FAILURE_CAP = 2048
TASK_ID = "PAPER-paper-method-add-006"


def need(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def _sha(value, name):
    need(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value),
         name + " requires a lowercase SHA256")
    return value


def full_plan():
    """Exact original source order; no public partial-grid option exists."""
    for job in G.job_plan():
        yield {"family": "glm", "id": job["id"], "job": job}
    for job in R.geometry_plan():
        yield {"family": "geometry", "id": P.geometry_id(job), "job": job}


def plan_fingerprint():
    h, counts = hashlib.sha256(), dict.fromkeys(EXPECTED_COUNTS, 0)
    for coordinate in full_plan():
        need(coordinate["family"] in counts, "unknown plan family")
        counts[coordinate["family"]] += 1
        h.update(canonical(coordinate) + b"\n")
    need(counts == EXPECTED_COUNTS, "original complete grid census differs")
    return {"sha256": h.hexdigest(), "counts": counts}


def make_binding(*, method_sha256, operator_input_sha256, information_condition):
    """Bind code identity, operator input manifest and both complete grids.

    The method hash is declared provenance, not proof of execution. Input
    manifest authenticity and participant custody remain operator obligations.
    """
    need(information_condition in ("paper_data", "paper_data_author_code"),
         "unknown paper information condition")
    return {"schema": "population_candidate_collection_binding_v1",
            "task_id": TASK_ID, "source_revision": K.SOURCE_REVISION,
            "method_sha256": _sha(method_sha256, "method identity"),
            "operator_input_sha256": _sha(operator_input_sha256, "operator input identity"),
            "information_condition": information_condition,
            "plan": plan_fingerprint(),
            "upstream_phase_isolation_attested": False}


def _binding(binding):
    need(isinstance(binding, dict), "operator collection binding required")
    expected = make_binding(method_sha256=binding.get("method_sha256"),
                            operator_input_sha256=binding.get("operator_input_sha256"),
                            information_condition=binding.get("information_condition"))
    need(binding == expected, "operator collection binding differs")


def _limits(max_result_bytes, max_total_bytes):
    need(type(max_result_bytes) is int and max_result_bytes > 0
         and type(max_total_bytes) is int and max_total_bytes > CLOSURE_CAP + LINE_CAP
         and max_result_bytes <= max_total_bytes, "explicit positive result/total byte limits required")


def _directory(path):
    path = Path(path).absolute()
    need(path == path.resolve(strict=True), "directory path contains a symlink or noncanonical component")
    need(stat.S_ISDIR(path.lstat().st_mode), "ordinary directory required")
    return path


def _entries(path, expected):
    """Stop at the first unexpected/extra entry without an unbounded listing."""
    seen = set()
    with os.scandir(path) as entries:
        for entry in entries:
            need(entry.name in expected and entry.name not in seen,
                 "directory has missing or extra entries")
            seen.add(entry.name)
    need(seen == expected, "directory has missing or extra entries")


def _read(path, cap):
    """Bounded ordinary single-link file read with stable opened identity."""
    st = path.lstat()
    need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and 0 <= st.st_size <= cap,
         "ordinary bounded single-link file required")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    try:
        before = os.fstat(fd)
        need((before.st_dev, before.st_ino) == (st.st_dev, st.st_ino), "file identity changed before open")
        with os.fdopen(fd, "rb", closefd=False) as f:
            raw = f.read(cap + 1)
        after = os.fstat(fd)
        need(len(raw) == before.st_size <= cap and
             (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
              before.st_ctime_ns, before.st_nlink) ==
             (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
              after.st_ctime_ns, after.st_nlink), "file changed during bounded read")
        return raw
    finally:
        os.close(fd)


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite JSON literal")))


def _candidate(candidate, coordinate, binding):
    need(isinstance(candidate, dict) and candidate.get("job_id") == coordinate["id"],
         "candidate job identity differs")
    need(candidate.get("method_sha256") == binding["method_sha256"],
         "candidate method identity differs")


def _record_binding(binding, coordinate):
    return {"schema": "population_candidate_coordinate_binding_v1",
            "collection": binding, "coordinate": coordinate}


def _write_exclusive(path, raw):
    with path.open("xb") as f:
        f.write(raw)


def freeze_submission(root, records, binding, *, max_result_bytes, max_total_bytes):
    """Create one complete sealed submission; all failed partial files remain.

    Byte limits cover cumulative logical output, including final receipts. They
    do not cover filesystem allocation, input objects, interpreter memory or
    physical I/O. On a failed numeric save, its whole allowance is conservatively
    charged because the inherited writer does not expose partial-write counters.
    """
    _limits(max_result_bytes, max_total_bytes)
    _binding(binding)
    root = Path(root).absolute()
    _directory(root.parent)
    need(root == root.parent / root.name and not root.exists() and not root.is_symlink(),
         "fresh ordinary submission destination required")
    root.mkdir(mode=0o700)
    (root / "records").mkdir(mode=0o700)
    charged, count, manifest_bytes = 0, 0, 0
    manifest_hash = hashlib.sha256()
    values = iter(records)
    sentinel = object()
    try:
        with (root / "RECORDS.jsonl").open("xb") as manifest:
            for index, coordinate in enumerate(full_plan()):
                item = next(values, sentinel)
                need(item is not sentinel, "incomplete candidate grid")
                need(isinstance(item, dict) and set(item) == {"family", "id", "candidate"}
                     and item["family"] == coordinate["family"] and item["id"] == coordinate["id"],
                     "candidate grid order, identity, duplicate or support mismatch")
                _candidate(item["candidate"], coordinate, binding)
                allowance = min(max_result_bytes, max_total_bytes - charged - CLOSURE_CAP - LINE_CAP)
                need(allowance > 0, "cumulative submission output ceiling exhausted")
                destination = root / "records" / f"{index:06d}"
                try:
                    pin = P.save_result(destination, item["candidate"],
                                        _record_binding(binding, coordinate), max_bytes=allowance)
                except BaseException:
                    charged += allowance
                    raise
                charged += pin["bytes"]
                descriptor = {"index": index, "family": coordinate["family"], "id": coordinate["id"],
                              "job_sha256": digest(canonical(coordinate["job"])),
                              "path": f"records/{index:06d}", "pin": pin}
                line = canonical(descriptor) + b"\n"
                need(len(line) <= LINE_CAP, "descriptor line ceiling exceeded")
                charged += len(line)  # Precharge writes, including an interrupted/partial write.
                need(charged + CLOSURE_CAP <= max_total_bytes, "cumulative output ceiling exceeded")
                manifest.write(line)
                manifest_hash.update(line)
                manifest_bytes += len(line)
                count += 1
            need(next(values, sentinel) is sentinel, "extra candidate grid coordinate")
        need(count == sum(EXPECTED_COUNTS.values()), "complete original job count differs")
        complete = {"schema": "population_candidate_collection_complete_v1", "binding": binding,
                    "records": count, "record_stream": {"path": "RECORDS.jsonl", "bytes": manifest_bytes,
                                                          "sha256": manifest_hash.hexdigest()},
                    "cumulative_logical_write_bytes": charged, "qualification": False,
                    "phase_isolation_attested": False}
        while True:
            raw = canonical(complete) + b"\n"
            total = charged + len(raw)
            if complete["cumulative_logical_write_bytes"] == total:
                break
            complete["cumulative_logical_write_bytes"] = total
        need(len(raw) <= CLOSURE_CAP - FAILURE_CAP and total + FAILURE_CAP <= max_total_bytes,
             "completion and potential failure receipts exceed ceiling")
        charged += len(raw)  # Retain the entire attempted write if write/close fails.
        _write_exclusive(root / "COMPLETE.json", raw)
        return {"complete_sha256": digest(raw), "complete_bytes": len(raw),
                "records": count, "cumulative_logical_write_bytes": total,
                "qualification": False, "phase_isolation_attested": False}
    except BaseException as exc:
        failure = canonical({"schema": "population_candidate_collection_failure_v1",
                             "completed_records": count, "charged_before_failure_receipt": charged,
                             "error": type(exc).__name__ + ": " + str(exc)[:512],
                             "status": "incomplete", "retry": False,
                             "partial_files_retained_and_not_refunded": True}) + b"\n"
        if len(failure) <= FAILURE_CAP and charged + len(failure) <= max_total_bytes:
            try:
                _write_exclusive(root / "FAILURE.json", failure)
            except OSError:
                pass  # Missing failure evidence never makes this a complete run.
        raise


def _seal(root, binding, expected_complete_sha256, max_total_bytes):
    root = _directory(root)
    _entries(root, {"records", "RECORDS.jsonl", "COMPLETE.json"})
    _directory(root / "records")
    raw = _read(root / "COMPLETE.json", CLOSURE_CAP)
    need(digest(raw) == _sha(expected_complete_sha256, "externally retained freeze identity"),
         "COMPLETE differs from externally retained freeze identity")
    value = _json(raw)
    need(set(value) == {"schema", "binding", "records", "record_stream", "cumulative_logical_write_bytes",
                        "qualification", "phase_isolation_attested"}
         and value["schema"] == "population_candidate_collection_complete_v1"
         and value["binding"] == binding and value["records"] == sum(EXPECTED_COUNTS.values())
         and value["qualification"] is False and value["phase_isolation_attested"] is False,
         "complete submission identity/counts differ")
    stream = value["record_stream"]
    need(set(stream) == {"path", "bytes", "sha256"} and stream["path"] == "RECORDS.jsonl"
         and type(stream["bytes"]) is int and 0 < stream["bytes"] <= max_total_bytes
         and type(value["cumulative_logical_write_bytes"]) is int
         and 0 < value["cumulative_logical_write_bytes"] <= max_total_bytes,
         "record stream or total-byte bound differs")
    _sha(stream["sha256"], "record stream identity")
    return root, value, len(raw)


def _descriptors(root, seal, max_total_bytes):
    """Bound each JSONL line; authenticate complete stream on iterator exhaustion."""
    path = root / "RECORDS.jsonl"
    st = path.lstat()
    need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1
         and st.st_size == seal["record_stream"]["bytes"] <= max_total_bytes,
         "ordinary manifest size differs")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    h, size = hashlib.sha256(), 0
    try:
        before = os.fstat(fd)
        need((before.st_dev, before.st_ino) == (st.st_dev, st.st_ino), "manifest changed before open")
        with os.fdopen(fd, "rb", closefd=False) as f:
            for index, coordinate in enumerate(full_plan()):
                line = f.readline(LINE_CAP + 1)
                need(0 < len(line) <= LINE_CAP and line.endswith(b"\n"), "missing, torn or oversized manifest line")
                size += len(line)
                need(size <= seal["record_stream"]["bytes"], "manifest exceeds frozen size")
                h.update(line)
                value = _json(line)
                need(set(value) == {"index", "family", "id", "job_sha256", "path", "pin"}
                     and type(value["index"]) is int and value["index"] == index
                     and value["family"] == coordinate["family"]
                     and value["id"] == coordinate["id"]
                     and value["job_sha256"] == digest(canonical(coordinate["job"]))
                     and value["path"] == f"records/{index:06d}", "manifest coordinate/order differs")
                pin = value["pin"]
                need(set(pin) == {"path", "bytes", "record_sha256", "array_sha256"}
                     and pin["path"] == f"{index:06d}" and type(pin["bytes"]) is int and pin["bytes"] > 0,
                     "numeric artifact descriptor differs")
                _sha(pin["record_sha256"], "record hash")
                _sha(pin["array_sha256"], "array hash")
                yield coordinate, value
            need(f.read(1) == b"", "extra manifest coordinate or trailing bytes")
        after = os.fstat(fd)
        need((before.st_size, before.st_mtime_ns, before.st_ctime_ns, before.st_nlink) ==
             (after.st_size, after.st_mtime_ns, after.st_ctime_ns, after.st_nlink),
             "manifest changed during scan")
        need(size == seal["record_stream"]["bytes"] and h.hexdigest() == seal["record_stream"]["sha256"],
             "manifest does not match complete frozen stream")
    finally:
        os.close(fd)


def _load_candidate(root, coordinate, descriptor, binding, max_result_bytes):
    path = _directory(root / descriptor["path"])
    _entries(path, {"arrays.npz", "record.json"})
    pin = descriptor["pin"]
    record = _read(path / "record.json", max_result_bytes)
    arrays = _read(path / "arrays.npz", max_result_bytes)
    need(len(record) + len(arrays) == pin["bytes"] <= max_result_bytes
         and digest(record) == pin["record_sha256"] and digest(arrays) == pin["array_sha256"],
         "numeric artifact differs from frozen descriptor")
    del record, arrays
    candidate = P.load_result(path, _record_binding(binding, coordinate), max_bytes=max_result_bytes)
    _candidate(candidate, coordinate, binding)
    return candidate


def verify_submission(root, binding, *, expected_complete_sha256, max_result_bytes, max_total_bytes):
    """Authenticate all 77,824 payloads before returning a verified seal."""
    _limits(max_result_bytes, max_total_bytes)
    _binding(binding)
    root, seal, closure_bytes = _seal(root, binding, expected_complete_sha256, max_total_bytes)
    count, artifact_bytes = 0, 0
    for coordinate, descriptor in _descriptors(root, seal, max_total_bytes):
        _load_candidate(root, coordinate, descriptor, binding, max_result_bytes)
        count += 1
        artifact_bytes += descriptor["pin"]["bytes"]
        need(artifact_bytes + seal["record_stream"]["bytes"] + closure_bytes <= max_total_bytes,
             "complete artifact byte census exceeds ceiling")
    # Bound extra-directory enumeration, rather than materializing an unbounded list.
    seen = 0
    for child in (root / "records").iterdir():
        seen += 1
        need(seen <= count and re.fullmatch(r"[0-9]{6}", child.name)
             and int(child.name) < count and child.is_dir() and not child.is_symlink(),
             "extra or malformed coordinate directory")
    total = artifact_bytes + seal["record_stream"]["bytes"] + closure_bytes
    need(seen == count == seal["records"] and total == seal["cumulative_logical_write_bytes"],
         "complete artifact census/total differs")
    return seal


def evaluate_submission(root, binding, reference_loader, evaluators, *,
                        expected_complete_sha256, max_result_bytes, max_total_bytes):
    """Yield evaluator-derived records after whole-grid authentication.

    The first ``next`` performs the complete verification, then reads references.
    Callers must consume the iterator completely and retain failures. No output
    is labelled a completed evaluation here, and these are not participant APIs.
    Caller isolation must prevent concurrent source/target/output mutations.
    """
    need(callable(reference_loader) and isinstance(evaluators, dict)
         and set(evaluators) == set(EXPECTED_COUNTS)
         and all(callable(v) for v in evaluators.values()), "operator reference loader and both evaluators required")
    seal = verify_submission(root, binding, expected_complete_sha256=expected_complete_sha256,
                             max_result_bytes=max_result_bytes, max_total_bytes=max_total_bytes)
    root = _directory(root)
    for coordinate, descriptor in _descriptors(root, seal, max_total_bytes):
        candidate = _load_candidate(root, coordinate, descriptor, binding, max_result_bytes)
        reference = reference_loader(coordinate["family"], coordinate["job"])
        result = evaluators[coordinate["family"]](reference, candidate)
        yield {"family": coordinate["family"], "id": coordinate["id"],
               "job": coordinate["job"], "result": result,
               "submission_complete_sha256": expected_complete_sha256}
