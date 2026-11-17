"""Complete prediction commitments and trusted, source-native CV evaluation.

These functions are operator primitives, not a participant filesystem sandbox.
The delivery coordinator must isolate candidate state and prevent full-data
observations or other folds from reaching an unfinished CV context. A sealed
panel commits every prediction before this module opens any protected target.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import stat

RECORD_SCHEMA = "temporal026-candidate-prediction/v1"
MANIFEST_SCHEMA = "temporal026-candidate-panel/v1"
MAX_RECORD_BYTES = 16 * 1024**2
MAX_MANIFEST_BYTES = 2 * 1024**2
MAX_TOTAL_BYTES = 1024**3
MAX_JOBS = 2054
SAMPLES = 819
FAILURES = {"candidate_execution_failed", "candidate_declined", "candidate_output_invalid"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"


def parse(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def _hex(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _context(protocol):
    plan, manifest = protocol.plan, protocol.manifest
    require(_hex(protocol.protocol_sha256) and _hex(protocol.method_sha256), "frozen procedure/protocol identities required")
    require(protocol.condition in {"paper_data", "paper_data_author_code"}, "explicit information condition required")
    protocol.source.producer.validate_plan(plan, protocol.plan_sha256, manifest, protocol.source.replay)
    jobs = plan["jobs"]
    require(len(jobs) == MAX_JOBS and plan["scalings"] == ["none", "S"], "complete two-slot 2054-coordinate panel required")
    require(sum(j["mode"] == "cv" for j in jobs) == 1896 and sum(j["mode"] == "full" for j in jobs) == 158,
            "complete original CV/full support required")
    return {"plan": plan, "jobs": jobs, "by_id": {j["id"]: j for j in jobs},
            "positions": {j["id"]: i for i, j in enumerate(jobs)},
            "items": {item["electrode_id"]: item for item in manifest["electrodes"]}}


def _job_info(context, job_id):
    require(type(job_id) is str and job_id in context["by_id"], "foreign source coordinate")
    job = context["by_id"][job_id]
    item = context["items"][job["electrode_id"]]
    allocation = item["folds"][job["fold"]] if job["mode"] == "cv" else None
    indices = allocation["test_rows"] if allocation else list(range(72))
    return {"job": job, "source_data_sha256": item["source_data_sha256"],
            "prediction_rows": indices, "prediction_identities": [item["rows"][i] for i in indices],
            "column_branch": job["response_columns"]}


def _base(protocol, context, job_id):
    info = _job_info(context, job_id)
    return {"schema": RECORD_SCHEMA, "protocol_sha256": protocol.protocol_sha256,
            "plan_sha256": protocol.plan_sha256, "method_sha256": protocol.method_sha256,
            "condition": protocol.condition, "job_id": job_id,
            **{k: info[k] for k in ("source_data_sha256", "prediction_rows", "prediction_identities", "column_branch")}}


def _traces(value, rows):
    require(type(value) is list and len(value) == rows, "complete prediction row support required")
    for trace in value:
        require(type(trace) is list and len(trace) == SAMPLES, "each prediction must have exactly 819 samples")
        def finite(x):
            if type(x) not in (int, float):
                return False
            try:
                return math.isfinite(x)
            except OverflowError:
                return False
        require(all(finite(x) for x in trace), "finite numeric predictions required; booleans refused")


def validate_record(record, protocol, context, job_id):
    expected = _base(protocol, context, job_id)
    require(type(record) is dict, "candidate record must be an object")
    require(all(k in record and encoded(record[k]) == encoded(value) for k, value in expected.items()),
            "prediction identity/branch/method binding mismatch")
    if record.get("status") == "submitted":
        require(set(record) == set(expected) | {"status", "predictions"}, "prediction-only record fields required")
        _traces(record["predictions"], len(expected["prediction_rows"]))
    else:
        require(record.get("status") == "failed" and set(record) == set(expected) | {"status", "failure"},
                "candidate status must be submitted or explicit failed")
        failure = record["failure"]
        require(type(failure) is dict and set(failure) == {"type", "message"} and type(failure["type"]) is str and failure["type"] in FAILURES,
                "typed candidate failure required")
        require(type(failure["message"]) is str and 0 < len(failure["message"]) <= 2048,
                "bounded nonempty failure message required")
    return record


def _directory(directory):
    path = Path(directory).absolute()
    require(path.resolve(strict=True) == path, "ordinary canonical output directory required")
    return os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)


def _filename(index):
    return "prediction-%04d.json" % index


def _inventory(fd):
    """At most 2055 metadata entries; no source or prediction body reads."""
    result = {}
    with os.scandir(fd) as entries:
        for entry in entries:
            name = entry.name
            require(len(result) < MAX_JOBS + 1, "too many submission directory entries")
            require(name == "MANIFEST.json" or
                    (name.startswith("prediction-") and len(name) == len("prediction-0000.json") and
                     name[11:15].isascii() and name[11:15].isdigit() and name.endswith(".json") and int(name[11:15]) < MAX_JOBS),
                    "unexpected submission directory entry")
            item = entry.stat(follow_symlinks=False)
            require(stat.S_ISREG(item.st_mode) and item.st_nlink == 1, "ordinary single-link submission members required")
            result[name] = item.st_size
    require(sum(result.values()) <= MAX_TOTAL_BYTES + MAX_MANIFEST_BYTES, "submission byte cap exceeded")
    return result


def _read(fd, pin, cap):
    require(type(pin) is dict and set(pin) == {"path", "bytes", "sha256"} and
            type(pin["path"]) is str and "/" not in pin["path"] and "\\" not in pin["path"] and
            pin["path"] not in {"", ".", ".."} and type(pin["bytes"]) is int and
            0 < pin["bytes"] <= cap and _hex(pin["sha256"]), "bounded canonical member pin required")
    child = os.open(pin["path"], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    with os.fdopen(child, "rb") as handle:
        before = os.fstat(handle.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == pin["bytes"],
                "submission member extent/type/link mismatch")
        raw = handle.read(pin["bytes"] + 1)
        after = os.fstat(handle.fileno())
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    require(identity(before) == identity(after) and len(raw) == pin["bytes"] and
            hashlib.sha256(raw).hexdigest() == pin["sha256"], "submission member changed or hash differs")
    return raw


def _write(fd, name, raw):
    child = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
    with os.fdopen(child, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
        os.fchmod(handle.fileno(), 0o444)
    os.fsync(fd)
    return {"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _record_bytes(protocol, context, job_id, *, predictions=None, failure=None):
    require((predictions is None) != (failure is None), "exactly one predictions or failure outcome required")
    record = _base(protocol, context, job_id)
    record.update(status="submitted", predictions=predictions) if predictions is not None else record.update(status="failed", failure=failure)
    validate_record(record, protocol, context, job_id)
    raw = encoded(record)
    require(len(raw) <= MAX_RECORD_BYTES, "prediction record exceeds byte cap")
    return raw


def _write_record(directory, protocol, context, job_id, *, predictions=None, failure=None):
    raw = _record_bytes(protocol, context, job_id, predictions=predictions, failure=failure)
    fd = _directory(directory)
    try:
        inventory = _inventory(fd)
        require("MANIFEST.json" not in inventory, "sealed panel cannot accept further predictions")
        require(sum(inventory.values()) + len(raw) <= MAX_TOTAL_BYTES, "cumulative submission byte cap exceeded")
        return _write(fd, _filename(context["positions"][job_id]), raw)
    finally:
        os.close(fd)


class Writer:
    """One trusted writer owns a validated panel context; no resume or sandbox."""

    def __init__(self, directory, protocol):
        self._directory = directory
        self._protocol = protocol
        self._context = _context(protocol)
        self._binding = (protocol.protocol_sha256, protocol.plan_sha256,
                         protocol.method_sha256, protocol.condition)
        self._committed = set()
        self._charged_bytes = 0
        self._failed = False
        fd = _directory(directory)
        try:
            require(not _inventory(fd), "new writer requires an empty prediction directory")
            st = os.fstat(fd)
            self._directory_identity = (st.st_dev, st.st_ino)
        finally:
            os.close(fd)

    def write(self, job_id, *, predictions=None, failure=None):
        protocol = self._protocol
        require((protocol.protocol_sha256, protocol.plan_sha256, protocol.method_sha256,
                 protocol.condition) == self._binding, "writer protocol identity changed")
        expected = _job_info(self._context, job_id)
        current = protocol.job_info(job_id)
        require(all(k in current and encoded(current[k]) == encoded(v) for k, v in expected.items()),
                "writer coordinate metadata changed")
        require(not self._failed, "failed writer cannot resume")
        require(job_id not in self._committed, "duplicate candidate coordinate")
        raw = _record_bytes(protocol, self._context, job_id, predictions=predictions, failure=failure)
        require(self._charged_bytes + len(raw) <= MAX_TOTAL_BYTES, "cumulative writer byte cap exceeded")
        fd = _directory(self._directory)
        try:
            st = os.fstat(fd)
            require((st.st_dev, st.st_ino) == self._directory_identity, "writer directory identity changed")
            try:
                os.stat("MANIFEST.json", dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise ValueError("sealed panel cannot accept further predictions")
            # Charge the full attempted write before it starts. Failures remain
            # terminal and partial/removed bytes never restore this allowance.
            self._charged_bytes += len(raw)
            try:
                result = _write(fd, _filename(self._context["positions"][job_id]), raw)
            except BaseException:
                self._failed = True
                raise
            self._committed.add(job_id)
            return result
        finally:
            os.close(fd)

    @property
    def accounting(self):
        return {"attempted_record_bytes": self._charged_bytes, "committed_records": len(self._committed),
                "failed_write_preserved": self._failed,
                "scope": "single trusted writer cumulative record bytes; final manifest and external costs separate"}


def write_record(directory, protocol, job_id, *, predictions=None, failure=None):
    """Single-record convenience; a complete delivery should reuse one Writer."""
    return _write_record(directory, protocol, _context(protocol), job_id,
                         predictions=predictions, failure=failure)


def _manifest_base(protocol, context, records, counts):
    return {"schema": MANIFEST_SCHEMA, "protocol_sha256": protocol.protocol_sha256,
            "plan_sha256": protocol.plan_sha256, "method_sha256": protocol.method_sha256,
            "condition": protocol.condition, "source_branch": context["plan"]["cv_column_branch"],
            "records": records, "counts": counts, "scientific_qualification": False}


def seal(directory, protocol):
    """Commit complete canonical support before target access; failure records remain."""
    context = _context(protocol)
    fd = _directory(directory)
    try:
        inventory = _inventory(fd)
        expected = {_filename(i) for i in range(MAX_JOBS)}
        require(set(inventory) == expected, "all 2054 prediction records and no extras required before sealing")
        records, counts = [], {"submitted": 0, "failed": 0, "cv": 1896, "full": 158}
        for i, job in enumerate(context["jobs"]):
            name = _filename(i)
            size = inventory[name]
            require(0 < size <= MAX_RECORD_BYTES, "bounded prediction extent required")
            child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            with os.fdopen(child, "rb") as handle:
                before = os.fstat(handle.fileno())
                require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == size,
                        "prediction identity changed before sealing")
                raw = handle.read(size + 1)
                after = os.fstat(handle.fileno())
            require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                    (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) and len(raw) == size,
                    "prediction changed during sealing")
            record = validate_record(parse(raw), protocol, context, job["id"])
            counts[record["status"]] += 1
            records.append({"job_id": job["id"], "status": record["status"],
                            "file": {"path": name, "bytes": size, "sha256": hashlib.sha256(raw).hexdigest()}})
        require(sum(row["file"]["bytes"] for row in records) <= MAX_TOTAL_BYTES, "complete prediction byte cap exceeded")
        raw = encoded(_manifest_base(protocol, context, records, counts))
        require(len(raw) <= MAX_MANIFEST_BYTES, "panel manifest exceeds byte cap")
        return _write(fd, "MANIFEST.json", raw)
    finally:
        os.close(fd)


def _load_panel(fd, protocol, context, expected_manifest_sha256):
    require(_hex(expected_manifest_sha256), "externally frozen complete manifest hash required")
    inventory = _inventory(fd)
    require(set(inventory) == {_filename(i) for i in range(MAX_JOBS)} | {"MANIFEST.json"}, "complete sealed directory required")
    manifest_pin = {"path": "MANIFEST.json", "bytes": inventory["MANIFEST.json"], "sha256": expected_manifest_sha256}
    manifest = parse(_read(fd, manifest_pin, MAX_MANIFEST_BYTES))
    require(type(manifest) is dict and type(manifest.get("records")) is list and len(manifest["records"]) == MAX_JOBS,
            "complete sealed record roster required")
    counts = {"submitted": 0, "failed": 0, "cv": 1896, "full": 158}
    total = 0
    for i, (entry, job) in enumerate(zip(manifest["records"], context["jobs"])):
        require(type(entry) is dict and set(entry) == {"job_id", "status", "file"} and entry["job_id"] == job["id"],
                "canonical complete job order required")
        pin = entry["file"]
        require(type(pin) is dict and pin.get("path") == _filename(i), "canonical prediction path required")
        require(type(pin.get("bytes")) is int and pin["bytes"] == inventory[pin["path"]], "prediction inventory extent differs")
        total += pin["bytes"]
        require(total <= MAX_TOTAL_BYTES, "complete prediction byte cap exceeded")
        record = validate_record(parse(_read(fd, pin, MAX_RECORD_BYTES)), protocol, context, job["id"])
        require(record["status"] == entry["status"], "record status differs from frozen manifest")
        counts[record["status"]] += 1
    require(encoded(manifest) == encoded(_manifest_base(protocol, context, manifest["records"], counts)),
            "manifest bindings/counts/fields differ")
    return manifest


def _reduce(protocol, context, compact, bootstrap_seed):
    """Candidate-named reduction matching source condition→fold→electrode rules."""
    import numpy as np
    require(type(bootstrap_seed) is int and 0 <= bootstrap_seed < 2**32, "prospective bootstrap seed required")
    require(set(compact) == set(context["by_id"]), "complete scored support required")
    failures = [{"job": name, "status": row["status"]} for name, row in compact.items() if row["status"] != "submitted"]
    electrodes = []
    for electrode in protocol.source.replay.cohort():
        for scaling in context["plan"]["scalings"]:
            names = [electrode["id"] + "/DN-" + scaling + "/fold%02d" % fold for fold in range(12)]
            values = [compact[name]["fold_r2"] for name in names]
            valid = all(type(v) in (int, float) and math.isfinite(v) for v in values) and all(compact[name]["status"] == "submitted" for name in names)
            electrodes.append({**electrode, "scaling": scaling, "fold_r2": values,
                               "r2": float(np.round(np.mean(values), 4)) if valid else None})
    rng = np.random.RandomState(bootstrap_seed)
    regional = []
    for region in ("V1-V3", "VOTC", "LOTC"):
        for scaling in context["plan"]["scalings"]:
            rows = [row for row in electrodes if row["varea"] == region and row["scaling"] == scaling]
            values = [row["r2"] for row in rows]
            item = {"region": region, "scaling": scaling, "electrodes": [row["id"] for row in rows],
                    "participants": sorted({row["subject"] for row in rows}), "status": "undefined_incomplete_or_nonfinite"}
            if not failures and all(value is not None for value in values):
                a = np.asarray(values)
                draws = rng.choice(len(a), size=(1000, len(a)), replace=True)
                medians = np.median(a[draws], axis=1)
                item.update(status="finite_descriptive", median=float(np.median(medians)),
                            interval68=np.nanpercentile(medians, [16, 84]).tolist())
            regional.append(item)
    return {"failures": failures, "electrode_cv": electrodes, "figure3_regional_cv": regional,
            "bootstrap": {"seed": bootstrap_seed, "resamples": 1000,
                          "unit": "electrodes descriptively resampled within region; not independent participants",
                          "historical_rng_recovered": False}}


def evaluate(directory, protocol, expected_manifest_sha256, input_root, bootstrap_seed):
    """Authenticate the entire committed panel before any protected target read.

    Prediction bytes are rechecked against that commitment during scoring. The
    caller owns this directory and the protected input root; filesystem isolation
    and candidate-process isolation are separate, unqualified runtime obligations.
    """
    import numpy as np
    context = _context(protocol)
    require(type(bootstrap_seed) is int and 0 <= bootstrap_seed < 2**32, "prospective bootstrap seed required")
    fd = _directory(directory)
    try:
        manifest = _load_panel(fd, protocol, context, expected_manifest_sha256)
        # No targets() call occurs above this line, including for full-data jobs.
        compact, cells = {}, []
        for entry, job in zip(manifest["records"], context["jobs"]):
            record = validate_record(parse(_read(fd, entry["file"], MAX_RECORD_BYTES)), protocol, context, job["id"])
            info = _job_info(context, job["id"])
            row = {"job_id": job["id"], "status": record["status"], "fold_r2": None}
            if record["status"] == "submitted" and job["mode"] == "cv":
                target = protocol.targets(input_root, job["id"])
                require(type(target) is dict and all(k in target and encoded(target[k]) == encoded(info[k]) for k in
                        ("source_data_sha256", "prediction_rows", "prediction_identities", "column_branch")),
                        "protected target source/row/branch binding mismatch")
                _traces(target.get("observations"), 6)
                values = [protocol.source.producer.native_r2(a, b) for a, b in zip(target["observations"], record["predictions"])]
                rounded = np.round([value["value"] for value in values], 3).tolist() if all(value["status"] == "finite" for value in values) else None
                score = float(np.round(np.mean(rounded), 4)) if rounded is not None else None
                row.update(condition_r2=values, rounded_condition_r2=rounded, fold_r2=score)
                cells.append(row)
            elif record["status"] == "failed":
                row["failure"] = record["failure"]
                if job["mode"] == "cv":
                    cells.append(row)
            compact[job["id"]] = row
        reduced = _reduce(protocol, context, compact, bootstrap_seed)
        return {"schema": "temporal026-candidate-source-metric-results/v1",
                "protocol_sha256": protocol.protocol_sha256, "plan_sha256": protocol.plan_sha256,
                "method_sha256": protocol.method_sha256, "condition": protocol.condition,
                "source_branch": context["plan"]["cv_column_branch"],
                "manifest_sha256": expected_manifest_sha256, "complete_job_count": len(compact),
                "candidate_status_counts": manifest["counts"], "cv_cells": cells, **reduced,
                "full_fit_jobs": [job["id"] for job in context["jobs"] if job["mode"] == "full"],
                "full_fit_warning": "Full-data predictions are retained exposed response outputs; no DN fit/components or biological companion reproduction is asserted.",
                "comparison_slots": "DN-none/S are original source coordinate labels, not claims about candidate architecture; repeated method identities are not new trials.",
                "scientific_qualification": False}
    finally:
        os.close(fd)
