"""Concrete future reference sandbox worker; never run during source construction.

Parent authenticates this source, engine, request, image, readonly mounts and
original host clock. Parent precreates fixed empty writable output-file mounts
inside readonly /output and independently observes natural process closure.
"""
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import stat
import sys
import time
import types

REQUEST = Path("/input/REQUEST.json")
ENGINE = Path("/trusted/reference_engine.py")
MODEL = Path("/model/model.pkl")
OUTPUT = Path("/output")
PIN_KEYS = {"bytes", "sha256"}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def finite(x):
    try:
        return type(x) in (int, float) and math.isfinite(x)
    except OverflowError:
        return False


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def pin_shape(p):
    need(type(p) is dict and set(p) == PIN_KEYS and type(p["bytes"]) is int and p["bytes"] > 0
         and type(p["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", p["sha256"]), "Exact nonempty byte/SHA256 descriptor")


def pairs(items):
    result = {}
    for k, v in items:
        need(k not in result, "Duplicate JSON member")
        result[k] = v
    return result


def decode(raw):
    text = raw.decode("utf-8")
    depth, quoted, escaped = 0, False, False
    for c in text:
        if quoted:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                quoted = False
        elif c == '"':
            quoted = True
        elif c in "[{":
            depth += 1
            need(depth <= 64, "JSON nesting limit")
        elif c in "]}":
            depth -= 1
    return json.loads(text, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON literal")))


def encoded(obj):
    return json.dumps(obj, separators=(",", ":"), allow_nan=False).encode("utf-8")


def stamp(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


class Work:
    def __init__(self, request, local_origin):
        clock = request["clock"]
        self.host_origin = clock["original_origin"]
        self.host_deadline = clock["phase_deadline"]
        self.local_origin = local_origin
        self.local_cap = clock["local_duration_cap"]
        self.limit = request["limits"]["output_bytes"]
        self.request = request
        self.read_hashed_bytes = 0
        self.decoded_array_bytes = 0
        self.reserved_write_bytes = 0
        self.completed_write_bytes = 0
        self.outputs = {}
        self.stamps = {}
        self.journal = []
        self.status = "entered"
        self.error_type = None
        self.local_tick()
        names = ["WORK.json", "model.pkl", "SELECTION.json"] if request["kind"] == "fit" else ["WORK.json", "PREDICTIONS.json"]
        for name in names:
            st = (OUTPUT / name).lstat()
            need(stat.S_ISREG(st.st_mode) and st.st_size == 0, "Known precreated zero-size output files required")
            self.stamps[name] = stamp(st)

    def local_tick(self):
        # Container/host monotonic clocks may differ. This is only a local
        # elapsed guard; the independent HOST observer owns absolute deadlines.
        elapsed = time.monotonic() - self.local_origin
        need(0 <= elapsed < self.local_cap, "Supplementary local elapsed cap exceeded")
        return elapsed

    def reserve_write(self, count):
        self.local_tick()
        need(type(count) is int and count >= 0 and self.reserved_write_bytes + count <= self.limit,
             "Aggregate logical output-write ceiling exceeded")
        self.reserved_write_bytes += count

    def write(self, name, chunks, file_cap):
        self.local_tick()
        need(name in self.stamps and type(file_cap) is int and file_cap > 0, "Fixed owned output and cap")
        path = OUTPUT / name
        before = path.lstat()
        need(stamp(before) == self.stamps[name], "Precreated output changed outside worker custody")
        fd = os.open(path, os.O_WRONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        total, digest = 0, hashlib.sha256()
        try:
            need(stamp(os.fstat(fd)) == self.stamps[name], "Output inode changed on open")
            os.ftruncate(fd, 0)
            for chunk in chunks:
                need(type(chunk) in (bytes, bytearray), "Output byte chunks only")
                need(total + len(chunk) <= file_cap, "Selected per-file output cap exceeded")
                self.reserve_write(len(chunk))
                view = memoryview(chunk)
                while view:
                    n = os.write(fd, view)
                    need(n > 0, "Output write made no progress")
                    self.completed_write_bytes += n
                    view = view[n:]
                digest.update(chunk)
                total += len(chunk)
            os.fsync(fd)
            after = os.fstat(fd)
            need(after.st_size == total and (before.st_dev, before.st_ino) == (after.st_dev, after.st_ino),
                 "Owned fixed output extent/inode")
            self.stamps[name] = stamp(after)
            value = {"bytes": total, "sha256": digest.hexdigest()}
            self.outputs[name] = value
            self.local_tick()
            return value
        finally:
            os.close(fd)

    def json_write(self, name, value):
        return self.write(name, [encoded(value)], self.request["limits"]["output_bytes"])

    def report(self, engine=None):
        if engine is None:
            disposition = {"expected": 16 if self.request["kind"] == "fit" else 3,
                           "entered": 0, "completed": 0, "entered_failed": 0,
                           "entered_incomplete": 0, "unentered": 16 if self.request["kind"] == "fit" else 3,
                           "last": None}
        else:
            disposition = engine.work_disposition(self.journal, 16 if self.request["kind"] == "fit" else 3)
        return {"schema": "neural060-reference-work-v1", "kind": self.request["kind"],
            "role": self.request["role"], "session_ordinal": self.request["session_ordinal"],
            "session_id": self.request["session_id"], "status": self.status,
            "error_type": self.error_type, "journal": self.journal, "disposition": disposition,
            "clock": {"original_host_origin": self.host_origin, "original_host_deadline": self.host_deadline,
                      "local_elapsed_seconds": time.monotonic() - self.local_origin, "local_duration_cap": self.local_cap,
                      "host_absolute_cutoff_verified_by_worker": False},
            "read_hashed_bytes": self.read_hashed_bytes, "decoded_array_bytes": self.decoded_array_bytes,
            "logical_write_bytes_reserved_before_this_record": self.reserved_write_bytes,
            "logical_write_bytes_completed_before_this_record": self.completed_write_bytes,
            "this_record_publication_is_additional": True,
            "native_physical_io_and_peak_memory": None,
            "outputs_before_work_publication": {k: v for k, v in self.outputs.items() if k != "WORK.json"},
            "source_or_runtime_qualification_created": False, "reference_competence_qualified": False}


def raw_capture(path, limit, expected=None, work=None):
    if work is not None:
        work.local_tick()
    if expected is not None:
        pin_shape(expected)
        need(expected["bytes"] <= limit, "Selected input descriptor exceeds cap")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= limit, "Bounded ordinary input")
        chunks, length = [], 0
        while True:
            block = os.read(fd, min(1 << 20, limit + 1 - length))
            if not block:
                break
            chunks.append(block)
            length += len(block)
            need(length <= limit, "Input body exceeds cap")
        raw = b"".join(chunks)
        after = os.fstat(fd)
        need(stamp(before) == stamp(after) and len(raw) == before.st_size, "Input unchanged during capture")
        if expected is not None:
            need(pin(raw) == expected, "Exact selected input bytes")
        if work is not None:
            work.read_hashed_bytes += len(raw)
            work.local_tick()
        return raw
    finally:
        os.close(fd)


def request_admission(value):
    need(type(value) is dict and value.get("kind") in ("fit", "infer"), "Exact reference request kind")
    keys = {"schema", "task_id", "kind", "role", "session_ordinal", "session_id", "unit_count", "unit_axis_sha256",
            "engine_source", "environment", "limits", "clock", "files"}
    if value["kind"] == "infer":
        keys.add("model")
    need(set(value) == keys and value["schema"] == "neural060-reference-request-v1"
         and value["task_id"] == "NEURAL-060", "Exact reference request envelope")
    need(value["role"] in ("nuisance", "joint") and type(value["session_ordinal"]) is int
         and 1 <= value["session_ordinal"] <= 29 and type(value["session_id"]) is str
         and re.fullmatch(r"[0-9a-f]{32}", value["session_id"]), "Exact role/session request identity")
    units = value["unit_count"]
    need(type(units) is int and (units == 0 if value["role"] == "nuisance" else units > 0), "Role-specific unit geometry")
    axis = value["unit_axis_sha256"]
    need(axis is None if value["role"] == "nuisance" else type(axis) is str and re.fullmatch(r"[0-9a-f]{64}", axis),
         "Original native axis identity or no nuisance neural metadata")
    pin_shape(value["engine_source"])
    need(value["engine_source"]["bytes"] <= 131072, "Bounded captured trusted engine source")
    env = value["environment"]
    need(type(env) is dict and set(env) == {"python", "numpy", "scikit_learn", "h5py"}
         and all(type(v) is str and 0 < len(v) < 100 for v in env.values()), "Exact qualified environment versions")
    limits = value["limits"]
    need(type(limits) is dict and set(limits) == {"context_bytes", "counts_bytes", "model_bytes", "output_bytes", "arrays_bytes"}
         and all(type(v) is int and v > 0 for v in limits.values()), "Selected complete workload bounds")
    clock = value["clock"]
    need(type(clock) is dict and set(clock) == {"original_origin", "phase_deadline", "local_duration_cap"}
         and all(finite(x) for x in clock.values()) and 0 <= clock["original_origin"] < clock["phase_deadline"]
         and 0 < clock["local_duration_cap"] <= clock["phase_deadline"] - clock["original_origin"],
         "Inherited host provenance and supplementary local duration")
    splits = ("train", "val") if value["kind"] == "fit" else ("test",)
    want = {s + "/context.json" for s in splits}
    if value["role"] == "joint":
        want |= {s + "/neural.h5" for s in splits}
    need(type(value["files"]) is dict and set(value["files"]) == want, "Exact role/phase readonly files; no arm flag")
    for p in value["files"].values():
        pin_shape(p)
    if value["kind"] == "infer":
        pin_shape(value["model"])
    return value


def environment_admission(expected):
    actual = {"python": platform.python_version(), "numpy": importlib.metadata.version("numpy"),
              "scikit_learn": importlib.metadata.version("scikit-learn"), "h5py": importlib.metadata.version("h5py")}
    need(actual == expected, "Exact prequalified numerical environment required")
    return actual


def capture_engine(request, work):
    raw = raw_capture(ENGINE, 131072, request["engine_source"], work)
    module = types.ModuleType("neural060_reference_engine")
    module.__file__ = str(ENGINE)
    exec(compile(raw, str(ENGINE), "exec"), module.__dict__)
    need(module.DESIGN_SHA256 == "206992a77c2470587fec83c84b2b4362c753b0d9f697a1e7d1923e5d5a82a471",
         "Exact reviewed reference design")
    return module


def context(request, split, engine, work):
    name = split + "/context.json"
    raw = raw_capture(Path("/input") / name, request["limits"]["context_bytes"], request["files"][name], work)
    envelope = decode(raw)
    need(type(envelope) is dict and set(envelope) == {"schema", "split", "session_id", "rows", "unit_count", "unit_axis_sha256"}
         and envelope["schema"] == "neural060_context_v2" and envelope["split"] == split
         and envelope["session_id"] == request["session_id"]
         and type(envelope["unit_count"]) is int and envelope["unit_count"] == request["unit_count"]
         and envelope["unit_axis_sha256"] == request["unit_axis_sha256"],
         "Exact staged context envelope")
    meta = engine.row_metadata(envelope["rows"], split != "test", request["session_id"])
    return envelope["rows"], meta


def count_attributes(values, request, split):
    attrs = {k: v.decode("utf-8") if isinstance(v, bytes) else str(v) for k, v in values.items()}
    need(attrs == {"schema": "neural060_counts_v2", "session_id": request["session_id"],
                   "split": split, "unit_axis_sha256": request["unit_axis_sha256"]},
         "Exact preparation count attributes; no condition/replay flag")


def counts(request, split, expected_ids, work):
    if request["role"] == "nuisance":
        return None
    import h5py
    import numpy as np
    name = split + "/neural.h5"
    path, expected = Path("/input") / name, request["files"][name]
    limit = request["limits"]["counts_bytes"]
    need(expected["bytes"] <= limit, "Full original count stream within selected file cap")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_size == expected["bytes"], "Original count-stream descriptor")
        digest, length = hashlib.sha256(), 0
        with os.fdopen(fd, "rb", closefd=False) as stream:
            while True:
                work.local_tick()
                block = stream.read(1 << 20)
                if not block:
                    break
                digest.update(block)
                length += len(block)
                need(length <= limit, "Count file changed beyond cap")
            need({"bytes": length, "sha256": digest.hexdigest()} == expected, "Exact full count-stream content")
            work.read_hashed_bytes += length
            stream.seek(0)
            with h5py.File(stream, "r") as handle:
                count_attributes(handle.attrs, request, split)
                need(set(handle.keys()) == {"case_ids", "counts"}, "Only original case IDs and counts")
                for key in ("case_ids", "counts"):
                    need(isinstance(handle.get(key, getlink=True), h5py.HardLink)
                         and isinstance(handle[key], h5py.Dataset)
                         and not handle[key].is_virtual and not handle[key].external,
                         "No external, virtual or soft-linked count payload")
                ids, values = handle["case_ids"], handle["counts"]
                need(ids.shape == (len(expected_ids),) and ids.dtype.kind == "S" and ids.dtype.itemsize == 32,
                     "Full ordered32-byte case-ID axis")
                need(values.shape == (len(expected_ids), 50, request["unit_count"])
                     and values.dtype.kind == "u" and values.dtype.itemsize == 4, "All native units and50 count bins")
                bytes_decoded = int(values.size) * 4 + len(expected_ids) * 32
                need(bytes_decoded <= request["limits"]["arrays_bytes"], "Declared whole count-array allocation cap")
                decoded_ids = [x.decode("ascii") for x in ids[()].tolist()]
                need(decoded_ids == expected_ids, "Exact context/count case order")
                array = np.asarray(values[()])
                work.decoded_array_bytes += bytes_decoded
        need(stamp(os.fstat(fd)) == stamp(before), "Count stream unchanged during decode")
        work.local_tick()
        return array
    finally:
        os.close(fd)


class PickleSink:
    """Streaming serializer sink over the fixed mounted output inode."""
    def __init__(self, work, cap):
        self.work, self.cap = work, cap
        path = OUTPUT / "model.pkl"
        need(stamp(path.lstat()) == work.stamps["model.pkl"], "Unchanged empty model output")
        self.fd = os.open(path, os.O_WRONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        need(stamp(os.fstat(self.fd)) == work.stamps["model.pkl"], "Exact model output inode")
        os.ftruncate(self.fd, 0)
        self.total, self.digest = 0, hashlib.sha256()

    def write(self, value):
        raw = bytes(value)
        need(self.total + len(raw) <= self.cap, "Selected serialized-model cap")
        self.work.reserve_write(len(raw))
        view = memoryview(raw)
        while view:
            n = os.write(self.fd, view)
            need(n > 0, "Model write made no progress")
            self.work.completed_write_bytes += n
            view = view[n:]
        self.total += len(raw)
        self.digest.update(raw)
        return len(raw)

    def finish(self):
        os.fsync(self.fd)
        st = os.fstat(self.fd)
        need(st.st_size == self.total, "Complete model serialization extent")
        self.work.stamps["model.pkl"] = stamp(st)
        value = {"bytes": self.total, "sha256": self.digest.hexdigest()}
        self.work.outputs["model.pkl"] = value
        return value

    def close(self):
        os.close(self.fd)


def run(request, request_pin, work):
    environment = environment_admission(request["environment"])
    engine = capture_engine(request, work)
    work.json_write("WORK.json", work.report(engine))
    if request["kind"] == "fit":
        train, train_meta = context(request, "train", engine, work)
        val, val_meta = context(request, "val", engine, work)
        train_counts = counts(request, "train", train_meta["case_ids"], work)
        val_counts = counts(request, "val", val_meta["case_ids"], work)

        def progress(journal):
            need(journal is work.journal, "Trusted reference journal identity")
            work.json_write("WORK.json", work.report(engine))

        bundle, selection = engine.fit_session(request["role"], request["session_ordinal"],
            train, val, train_counts, val_counts, work.journal, progress)
        work.local_tick()
        # Only this isolated worker serializes or later loads this model.
        import pickle
        sink = PickleSink(work, request["limits"]["model_bytes"])
        try:
            wrapper = {"schema": "neural060-reference-model-v1", "engine_source": request["engine_source"],
                       "environment": environment, "unit_axis_sha256": request["unit_axis_sha256"], "bundle": bundle}
            pickle.dump(wrapper, sink, protocol=5)
            model_pin = sink.finish()
        finally:
            sink.close()
        work.json_write("SELECTION.json", {"schema": "neural060-reference-selection-file-v1",
            "request": request_pin, "engine_source": request["engine_source"], "model": model_pin,
            "environment": environment, "selection": selection})
    else:
        rows, meta = context(request, "test", engine, work)
        array = counts(request, "test", meta["case_ids"], work)
        raw = raw_capture(MODEL, request["limits"]["model_bytes"], request["model"], work)
        import pickle
        wrapper = pickle.loads(raw)
        del raw
        need(type(wrapper) is dict and set(wrapper) == {"schema", "engine_source", "environment", "unit_axis_sha256", "bundle"}
             and wrapper["schema"] == "neural060-reference-model-v1"
             and wrapper["engine_source"] == request["engine_source"] and wrapper["environment"] == environment
             and wrapper["unit_axis_sha256"] == request["unit_axis_sha256"], "Same source/environment/native unit-axis model seal")
        bundle = wrapper["bundle"]
        engine.bundle_metadata(bundle)
        need(bundle["role"] == request["role"] and bundle["session_ordinal"] == request["session_ordinal"]
             and bundle["session_id"] == request["session_id"] and bundle["unit_count"] == request["unit_count"],
             "Readonly model belongs to this exact role/session/all-unit view")
        # One concrete engine call predicts all three families. Entered states
        # are written first; individual progress is added by engine below.
        def progress(journal):
            need(journal is work.journal, "Trusted prediction journal identity")
            work.json_write("WORK.json", work.report(engine))
        predictions, inference = engine.predict_session(bundle, rows, array, work.journal, progress)
        families = {f: [{"case_id": case, "prediction": values} for case, values in zip(meta["case_ids"], predictions[f])]
                    for f in engine.FAMILIES}
        work.json_write("PREDICTIONS.json", {"schema": "neural060-reference-predictions-file-v1",
            "request": request_pin, "engine_source": request["engine_source"], "model": request["model"],
            "environment": environment, "inference": inference, "families": families})
    work.status = "completed"
    work.json_write("WORK.json", work.report(engine))
    work.local_tick()


def main():
    local_origin = time.monotonic()
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    args = parser.parse_args()
    need(args.request == str(REQUEST), "Fixed root-authenticated request path only")
    work = None
    try:
        raw = raw_capture(REQUEST, 262144)
        request = request_admission(decode(raw))
        work = Work(request, local_origin)
        work.read_hashed_bytes += len(raw)
        run(request, pin(raw), work)
    except BaseException as error:
        if work is not None:
            work.status, work.error_type = "failed", type(error).__name__
            # A timeout/write-cap/failure may prevent this final record. Prior
            # durable entered states remain; parent must not infer success.
            try:
                completed = sum(r.get("status") == "completed" for r in work.journal)
                failed = sum(r.get("status") == "failed" for r in work.journal)
                incomplete = sum(r.get("status") == "entered" for r in work.journal)
                report = work.report()
                report["journal"] = work.journal
                report["disposition"] = {"expected": 16 if request["kind"] == "fit" else 3,
                    "entered": len(work.journal), "completed": completed, "entered_failed": failed,
                    "entered_incomplete": incomplete,
                    "unentered": (16 if request["kind"] == "fit" else 3) - len(work.journal),
                    "last": None if not work.journal else work.journal[-1]}
                work.json_write("WORK.json", report)
            except BaseException:
                pass
        print(json.dumps({"schema": "neural060-reference-worker-failure-v1", "error_type": type(error).__name__,
                          "detail": str(error)[:512], "success": False}), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
