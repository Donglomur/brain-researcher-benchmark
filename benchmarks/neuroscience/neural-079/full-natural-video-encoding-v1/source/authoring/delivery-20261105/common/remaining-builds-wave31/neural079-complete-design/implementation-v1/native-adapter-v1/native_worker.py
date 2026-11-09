"""Future native22 process worker. Not invoked by source-phase controls.

The only scientific execution entry is runpy.run_path of an exact authenticated
catalog script. Native inputs include original held responses, privately. No
callback can supply a finished scientific result. The external supervisor owns
namespace/process/cgroup/clock/stream/inventory admission and observation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import stat
import sys
import traceback

from native_adapter import (CAP_KEYS, WORKSPACE, NativeError, admitted_json,
                            admit_execution, canonical, checked_pin,
                            expected_shape, fields, job_spec, native_jobs, pin,
                            positive, relative_path, require, resolve_dimensions,
                            select_value)


def regular_bytes(path, cap, expected=None):
    """Bound before reading; reject symlinks, nonregular files and changed extent."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_size <= cap, "extent", "selected regular source/request exceeds its admitted extent")
        chunks, remaining = [], before.st_size
        while remaining:
            chunk = os.read(fd, min(remaining, 1024*1024))
            require(chunk, "read", "unexpected source EOF")
            chunks.append(chunk);remaining -= len(chunk)
        require(not os.read(fd, 1), "read", "source grew beyond admitted extent")
        after = os.fstat(fd)
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "read", "selected source changed while reading")
        raw = b"".join(chunks)
        if expected is not None: require(pin(raw) == expected, "source_join", "selected source/request pin mismatch")
        return raw
    finally:
        os.close(fd)


class CaptureWriter:
    def __init__(self, output, caps):
        self.output, self.caps, self.reserved = Path(output), caps, 0
        require(self.output == Path("/output") and self.output.is_dir(), "output", "fixed supervisor-owned /output required")

    def reserve(self, count):
        require(type(count) is int and 0 <= count <= self.caps["artifact_bytes"] and self.reserved+count <= self.caps["capture_bytes"], "extent", "prospective native capture bytes exceed selected caps")
        self.reserved += count

    def write(self, relative, chunks, count):
        relative_path(relative);self.reserve(count)
        destination = self.output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        total, digest = 0, hashlib.sha256()
        with destination.open("xb") as stream:
            for chunk in chunks:
                require(type(chunk) is bytes and total+len(chunk) <= count, "write", "capture exceeded preflight extent")
                stream.write(chunk);digest.update(chunk);total += len(chunk)
            require(total == count, "write", "capture did not cover the complete preflight extent")
        return {"path": relative, "pin": {"bytes": total, "sha256": digest.hexdigest()}}


def safe_numeric_array(value, expected, cap):
    import numpy as np
    if type(value) in (bool, int, float) or isinstance(value, np.generic):
        require(not (type(value) is int and not -(2**63) <= value < 2**63), "numeric_schema", "native integer scalar exceeds explicit int64 storage")
        value = np.asarray(value)
    require(isinstance(value, np.ndarray) and value.dtype.kind in "biuf" and value.dtype.itemsize in (1, 2, 4, 8), "numeric_schema", "numeric non-object native array/scalar required")
    require(value.dtype.kind != "f" or value.dtype.itemsize in (4, 8), "numeric_schema", "binary32/binary64 native floating array required")
    require(list(value.shape) == expected and value.size <= cap, "support", "source-produced native quantity does not cover its exact complete shape")
    return value


def numeric_chunks(array, dtype, block_bytes, diagnostics):
    """C-order bytes in bounded nditer buffers; never flatten-copy a full matrix."""
    import numpy as np
    require(block_bytes >= dtype.itemsize, "extent", "numeric block cap must hold one complete scalar")
    elements = max(1, block_bytes // dtype.itemsize)
    iterator = np.nditer(array, flags=["external_loop", "buffered", "zerosize_ok"],
                         op_flags=["readonly"], op_dtypes=[dtype], casting="equiv",
                         order="C", buffersize=elements)
    with iterator:
        for chunk in iterator:
            # A contiguous iterator operand can be a larger zero-copy view.
            # Explicit slicing also bounds masks and serialized byte copies.
            for start in range(0, chunk.size, elements):
                part = chunk[start:start+elements]
                if dtype.kind == "f":
                    diagnostics["nan_count"] += int(np.count_nonzero(np.isnan(part)))
                    diagnostics["positive_infinity_count"] += int(np.count_nonzero(np.isposinf(part)))
                    diagnostics["negative_infinity_count"] += int(np.count_nonzero(np.isneginf(part)))
                yield part.tobytes(order="C")


def bounded_metadata(value, max_bytes):
    # Selected source metadata is limited to nodes, video paths, shape tuples,
    # device, channel names and indices. No arbitrary object serialization.
    count = 0
    def inspect(item, depth=0):
        nonlocal count
        count += 1
        require(count <= 8192 and depth <= 8, "extent", "native metadata item/nesting cap")
        if type(item) is str: require(len(item.encode("utf-8")) <= 8192, "extent", "native metadata string cap")
        elif type(item) in (list, tuple):
            require(len(item) <= 4096, "extent", "native metadata sequence cap")
            for child in item: inspect(child, depth+1)
        elif type(item) is dict:
            require(len(item) <= 4096, "extent", "native metadata mapping cap")
            for key, child in item.items(): inspect(key, depth+1);inspect(child, depth+1)
    inspect(value)
    raw = canonical(admitted_json(value))
    require(len(raw) <= max_bytes, "extent", "native JSON capture extent")
    return raw


def capture_quantity(namespace, quantity, dimensions, admission, writer):
    import numpy as np
    value = select_value(namespace, quantity["selector"])
    record = {"id": quantity["id"], "status": "captured", "source_pin": quantity["source_pin"],
              "selector_pin": quantity["selector_pin"], "units": admission["units"],
              "units_evidence": admission["units_evidence"], "support_evidence": admission["support_evidence"],
              "encoding": quantity["encoding"]}
    if quantity["encoding"] == "json":
        raw = bounded_metadata(value, writer.caps["artifact_bytes"])
        record.update(writer.write("quantities/"+quantity["id"]+".json", (raw,), len(raw)))
        record.update({"dtype": None, "shape": None, "nonfinite": None})
    else:
        shape = expected_shape(quantity, dimensions)
        array = safe_numeric_array(value, shape, writer.caps["capture_elements"])
        dtype = array.dtype.newbyteorder("<")
        size = array.size*dtype.itemsize
        require(size <= writer.caps["artifact_bytes"], "extent", "complete numeric quantity exceeds capture extent before buffer allocation")
        diagnostics = {"nan_count": 0, "positive_infinity_count": 0, "negative_infinity_count": 0}
        record.update(writer.write("quantities/"+quantity["id"]+".bin", numeric_chunks(array, dtype, writer.caps["block_bytes"], diagnostics), size))
        record.update({"dtype": dtype.str, "shape": shape, "order": "C", "nonfinite": diagnostics})
    return record


def file_chunks(path, expected_size, block_bytes):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_size == expected_size, "file", "original native output extent changed")
        left = expected_size
        while left:
            chunk = os.read(fd, min(left, block_bytes))
            require(chunk, "file", "original native output ended early")
            left -= len(chunk);yield chunk
        require(not os.read(fd, 1), "file", "original native output has unadmitted tail")
        after = os.fstat(fd)
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "file", "original native output changed while capturing")
    finally:
        os.close(fd)


def capture_native_file(member, workspace, writer):
    relative_path(member["relative_path"])
    path = workspace / member["relative_path"]
    require(path.resolve().is_relative_to(workspace.resolve()) and not path.is_symlink(), "file", "native output must be a regular owned workspace file")
    info = path.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_size <= writer.caps["artifact_bytes"], "extent", "original native file exceeds cap before read")
    result = writer.write("native_files/"+member["relative_path"], file_chunks(path, info.st_size, writer.caps["block_bytes"]), info.st_size)
    return {"id": member["id"], "status": "captured", "native_relative_path": member["relative_path"],
            "encoding": "opaque_original_bytes", "source_pin": member["source_pin"], **result}


def workspace_links(payload):
    """Private tmpfs workspace; input links never enter the output inventory."""
    root = Path(WORKSPACE);root.mkdir(mode=0o700, parents=False, exist_ok=False)
    records = []
    for link in payload["input_links"]:
        fields(link, ("native_relative_path", "mounted_path", "material_path", "input_pin"), "native input link")
        relative = relative_path(link["native_relative_path"])
        require(link["mounted_path"] == "/data/"+relative, "input_join", "exact native mount-to-workspace path join")
        checked_pin(link["input_pin"])
        source = Path(link["mounted_path"])
        observed = source.stat()
        require(stat.S_ISREG(observed.st_mode) and observed.st_size == link["input_pin"]["bytes"], "input_join", "immutable supervisor-mounted input has wrong type/extent")
        destination = root / relative
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        require(destination.parent.resolve().is_relative_to(root.resolve()), "input_join", "input link parents escape the owned workspace")
        os.symlink(link["mounted_path"], destination)
        records.append({**link, "workspace_path": str(destination), "stat_bytes": observed.st_size,
                        "body_hash_rechecked_by_worker": False,
                        "custody": "Independent supervisor material admission/immutable read-only mount; worker checks exact size and link target."})
    return root, records


def error_record(exc):
    return {"type": type(exc).__name__, "code": getattr(exc, "code", "native_exception"), "message": str(exc)}


def run_worker(request_path, output, caps):
    for key in CAP_KEYS: positive(caps[key], key)
    raw = regular_bytes(request_path, caps["request_bytes"])
    request = json.loads(raw)
    fields(request, ("schema", "context", "work_id", "job", "program_pin", "execution", "input_links", "dependencies", "view_evidence", "program_evidence", "transductive_disclosure"), "native worker request")
    require(request["schema"] == "n079_native_worker_request_v1", "schema", "native worker request schema")
    job = request["job"]
    matches = [r for r in native_jobs() if r["id"] == job.get("id")]
    require(len(matches) == 1 and job == job_spec(matches[0], job.get("variant")), "source_join", "exact source-owned job and selector roster required")
    execution = request["execution"];admit_execution(execution, job)
    require(execution["caps"] == caps and dict(os.environ) == execution["environment"], "environment_join", "actual worker environment and CLI caps must equal independent selection")
    require(sys.executable == execution["interpreter"], "runtime", "actual interpreter path differs from selected runtime")
    interpreter_bytes = regular_bytes(execution["interpreter"], caps["source_bytes"], execution["interpreter_pin"])
    script = job["argv"][0]
    source = regular_bytes(script, caps["source_bytes"], job["source"]["pin"])
    writer = CaptureWriter(output, caps)
    source_snapshot = writer.write("source/"+job["source"]["id"]+".py", (source,), len(source))
    literal_snapshot = None
    if "literal_original" in job["source"]:
        original = job["source"]["literal_original"]
        original_bytes = regular_bytes("/source/author/"+original["author_relative_path"], caps["source_bytes"], original["pin"])
        literal_snapshot = writer.write("source/literal_original_visual_features.py", (original_bytes,), len(original_bytes))
    index = {"schema": "n079_native_capture_index_v1", "job_id": job["id"], "variant": job["variant"],
             "context": request["context"], "work_id": request["work_id"], "request_pin": pin(raw),
             "program_pin": request["program_pin"], "source_pin": pin(source), "source_snapshot": source_snapshot,
             "literal_original_source_snapshot": literal_snapshot,
             "interpreter_pin": pin(interpreter_bytes), "argv": job["argv"], "environment_pin": pin(canonical(execution["environment"])),
             "python_path": execution["python_path"], "independent_execution_evidence": execution["evidence"],
             "dependencies": request["dependencies"], "transductive_disclosure": request["transductive_disclosure"],
             "quantities": [], "native_files": [], "failures": [], "capture_complete": False,
             "native_execution": {"status": "not_started"}, "workspace": {"root": WORKSPACE, "private_tmpfs_required": True},
             "prospective_grading_blocked_by_numeric_mismatch": False,
             "qualification": "Producer capture only; external observer/source/quantity/reference/tolerance admission remains necessary."}
    namespace = None
    try:
        workspace, links = workspace_links(request)
        index["workspace"].update({"links": links, "link_count": len(links), "link_metadata_bytes": len(canonical(links)),
                                   "private_tmp_result_extents": "Original native allocations/files require independent full-work admission and observation; not bounded by this capture writer."})
        sys.argv = list(job["argv"])
        sys.path[:] = list(execution["python_path"])
        os.chdir(workspace)
        # This is the sole native execution primitive. No callback, rewritten
        # scientific function or supplied finished result can replace it.
        namespace = runpy.run_path(script, run_name="__main__")
        index["native_execution"] = {"status": "returned", "original_script_exception": None}
        if job["kind"] == "visual_features":
            expected_device = "cpu" if job["variant"] == "literal_cpu" else "cuda"
            require(namespace.get("device") == expected_device, "device_join", "actual selected-device branch differs from declared literal/corrected variant")
    except (Exception, SystemExit) as exc:
        index["native_execution"] = {"status": "failed", "original_script_exception": error_record(exc)}
        index["failures"].append({"phase": "native_execution", **error_record(exc)})
        traceback.print_exc()
    dimensions = None
    if namespace is not None:
        try: dimensions = resolve_dimensions(namespace, job)
        except Exception as exc: index["failures"].append({"phase": "source_dimensions", **error_record(exc)})
    index["dimensions"] = dimensions
    for quantity in job["quantities"]:
        try:
            require(namespace is not None and dimensions is not None, "missing_quantity", "original execution/dimension state did not expose required quantity")
            index["quantities"].append(capture_quantity(namespace, quantity, dimensions, execution["quantity_admissions"][quantity["id"]], writer))
        except Exception as exc:
            index["quantities"].append({"id": quantity["id"], "status": "missing", "source_pin": quantity["source_pin"], "selector_pin": quantity["selector_pin"], "failure": error_record(exc)})
            index["failures"].append({"phase": "quantity_capture", "quantity_id": quantity["id"], **error_record(exc)})
    for member in job["native_files"]:
        try:
            index["native_files"].append(capture_native_file(member, Path(WORKSPACE), writer))
        except Exception as exc:
            index["native_files"].append({"id": member["id"], "status": "missing", "native_relative_path": member["relative_path"], "failure": error_record(exc)})
            index["failures"].append({"phase": "original_file_capture", "file_id": member["id"], **error_record(exc)})
    index["capture_complete"] = index["native_execution"]["status"] == "returned" and not index["failures"]
    index["capture_reserved_bytes_before_index"] = writer.reserved
    index["original_files_are_opaque"] = True
    index["nonfinite_native_values_retained"] = True
    encoded = canonical(index)
    require(len(encoded) <= caps["index_bytes"], "extent", "full failure/capture index exceeds selected cap; external full streams remain evidence")
    writer.write("CAPTURE_INDEX.json", (encoded,), len(encoded))
    # Worker closure is distinct from original-script success. A natural0
    # delivers a complete failure index too; the consumer inspects both states.
    return index


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--output", required=True)
    for key in CAP_KEYS: parser.add_argument("--"+key.replace("_", "-"), type=int, required=True)
    args = parser.parse_args()
    require(args.request == "/request/request.json" and args.output == "/output", "path", "fixed worker request/output paths required")
    run_worker(args.request, args.output, {key: getattr(args, key) for key in CAP_KEYS})


if __name__ == "__main__":
    main()
