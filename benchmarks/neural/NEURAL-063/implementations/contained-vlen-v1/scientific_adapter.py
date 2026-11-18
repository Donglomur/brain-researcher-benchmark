"""NEURAL-063 contained metadata adapters; no action on import.

This is source preparation, not an authenticated container launcher. The outer
operator must authenticate the deployment and its effective controls before
issuing admission. No claim is made that a VLEN allocation itself is bounded.
The existing whole-array scientific reads run only in that admitted kill domain.
"""
import hashlib
import json
import math
import os
import posixpath
from pathlib import Path
import re
import stat
import time

SCHEMA = "neural063-portable-contained-vlen-profile-v1"
NAMES = {"plane": "plane_metadata.json", "session": "session_support.json"}
MAX_OUTPUT = {"plane": 33554432, "session": 100663296}
RUNTIME = {"aiohttp": "3.14.3", "fsspec": "2026.6.0", "h5py": "3.16.0"}
SOURCE_PINS = {
    "native": (8094, "59938e74806637cc3be504a6bcb2a550f1571d22e6d55342abdd048978389c66"),
    "algorithm": (7672, "aa5255ba1d238331cc91122b4b84ce2d90a0d23b7b19964ddb91c72953bac3c8"),
    "pipeline": (20502, "ad1e2e80dc8676af208a3fee4bd0977694fc3abf145d883fbb5b8b7a17dd8f42"),
    "range": (15515, "73d479623f9fe78f42631aeca49113748791b5737cfe7b6aec43789737ffb7e1"),
    "manifest": (7952, "36b7eb96e9d40f808035979b1f30c7e103746d20d670235d8658cda613381205"),
}
DEPLOYMENT_KEYS = {
    "image_id", "endpoint", "runtime_receipt_sha256", "mount_receipt_sha256",
    "network_receipt_sha256", "containment_receipt_sha256",
    "exporter_receipt_sha256", "delegation_receipt_sha256",
}
COST_KEYS = {
    "http_requests", "http_response_body_bytes", "http_header_reservation_bytes",
    "logical_read_bytes", "export_read_bytes", "host_write_bytes",
    "control_bytes", "closure_seconds", "worker_artifact_write_bytes", "worker_control_bytes",
    "source_setup_read_bytes",
}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def validate_endpoint(value):
    """Canonical local Unix endpoint; authority/daemon proof belongs to controller."""
    need(type(value) is str and value.startswith("unix:///")
         and len(value.encode("utf-8")) <= 4096
         and not any(c in value for c in "%?#")
         and not any(ord(c) < 33 or ord(c) == 127 for c in value),
         "canonical explicit local Unix socket endpoint")
    path = value[len("unix://"):]
    need(path != "/" and not path.startswith("//") and posixpath.normpath(path) == path,
         "absolute ordinary endpoint spelling")
    return value


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False, ensure_ascii=False) + "\n").encode("utf-8")


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def strict(body):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    def invalid(_):
        raise ValueError("nonfinite JSON")
    return json.loads(body, object_pairs_hook=pairs, parse_constant=invalid)


def validate_profile(profile, *, require_selected=True):
    need(set(profile) == {"schema", "selected", "runtime_qualified", "deployment",
         "global_caps", "unit_caps", "plane_range_limits", "session_input_bytes",
         "output_caps", "terminal_inventory_bytes", "runtime_versions", "unit_seconds", "isolation_limits"}, "exact N063 profile")
    need(profile["schema"] == SCHEMA and type(profile["selected"]) is bool
         and type(profile["runtime_qualified"]) is bool, "typed profile state")
    need(profile["runtime_versions"] == RUNTIME and profile["output_caps"] == MAX_OUTPUT,
         "fixed runtime/output schema")
    need(set(profile["deployment"]) == DEPLOYMENT_KEYS, "exact deployment fields")
    need(profile["isolation_limits"] == {"memory_bytes": 1879048192, "memory_swap_bytes": 1879048192,
         "pids": 32, "nofile": [1024, 1024], "tmpfs_bytes": 134217728, "cpu_threads": 1},
         "fixed prospective contained-worker resource contract")
    need(set(profile["unit_seconds"]) == {"plane", "session"}, "two bounded worker durations")
    need(set(profile["unit_caps"]) == {"plane", "session"}, "two unit kinds only")
    for caps in [profile["global_caps"], *profile["unit_caps"].values()]:
        need(set(caps) == COST_KEYS, "complete resource envelope")
        for value in caps.values():
            need(value is None or type(value) is int and value >= 0, "finite cap or unresolved")
    need(profile["terminal_inventory_bytes"] is None or
         type(profile["terminal_inventory_bytes"]) is int and
         profile["terminal_inventory_bytes"] >= 9377792, "protected full-inventory reserve")
    if not require_selected:
        need(profile["selected"] is False and profile["runtime_qualified"] is False,
             "preparation cannot select execution")
        return {"launchable": False, "deployment_unresolved": True}
    need(profile["selected"] is True and profile["runtime_qualified"] is True,
         "inactive source-preparation profile")
    dep = profile["deployment"]
    need(type(dep["image_id"]) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", dep["image_id"]),
         "unresolved image identity")
    need(all(type(v) is str and re.fullmatch(r"[0-9a-f]{64}", v)
             for k, v in dep.items() if k not in ("image_id", "endpoint")), "unresolved deployment/delegation")
    validate_endpoint(dep["endpoint"])
    for caps in [profile["global_caps"], *profile["unit_caps"].values()]:
        need(all(type(v) is int and v >= 0 for v in caps.values()), "unresolved resource envelope")
    need(all(type(v) is int and 0 < v <= 1800 for v in profile["unit_seconds"].values()),
         "finite contained-worker durations")
    need(type(profile["session_input_bytes"]) is int and profile["session_input_bytes"] > 0,
         "unresolved complete-session input cap")
    need(type(profile["terminal_inventory_bytes"]) is int, "unresolved terminal reserve")
    need(type(profile["plane_range_limits"]) is dict, "unresolved fixed range limits")
    for kind, cap in profile["unit_caps"].items():
        need(cap["export_read_bytes"] >= 2 * MAX_OUTPUT[kind] + 8194
             and cap["host_write_bytes"] >= MAX_OUTPUT[kind] + cap["control_bytes"]
             and cap["control_bytes"] >= 131072 and cap["closure_seconds"] >= 2
             and cap["worker_artifact_write_bytes"] >= MAX_OUTPUT[kind]
             and cap["worker_control_bytes"] >= 16384 and cap["source_setup_read_bytes"] >= 67108864 + 257,
             "whole output/failure/closure reservation before launch")
    need(profile["unit_caps"]["session"]["logical_read_bytes"] >= profile["session_input_bytes"] + 1936,
         "all session input bytes and one EOF probe per original plane reserved")
    need(all(profile["unit_caps"]["session"][k] == 0 for k in
             ("http_requests", "http_response_body_bytes", "http_header_reservation_bytes")),
         "session has no provider route")
    return {"launchable": True, "deployment_unresolved": False}


def admitted(profile, admission, kind, identity):
    """Cross-bind outer-verified receipts; this is not a kernel-control verifier."""
    validate_profile(profile)
    need(set(admission) == {"schema", "kind", "identity", "profile_sha256", "reservation_sha256",
         "container_id", "deployment_sha256", "effective_controls_sha256", "container_deadline_monotonic",
         "host_deadline_receipt_sha256", "clock_domain", "selection_sha256", "assets_sha256",
         "completed_inventory_sha256", "plane_inputs_sha256"},
         "exact contained admission")
    need(admission["schema"] == "neural063-contained-admission-v1"
         and admission["kind"] == kind and admission["identity"] == identity
         and admission["profile_sha256"] == sha(profile)
         and admission["deployment_sha256"] == sha(profile["deployment"]), "admission cross-binding")
    need(all(type(admission[k]) is str and re.fullmatch(r"[0-9a-f]{64}", admission[k])
             for k in ("reservation_sha256", "container_id", "effective_controls_sha256", "host_deadline_receipt_sha256",
                       "selection_sha256", "assets_sha256", "completed_inventory_sha256", "plane_inputs_sha256")),
         "unresolved owned containment/reservation")
    end = admission["container_deadline_monotonic"]
    need(admission["clock_domain"] == "linux_container_monotonic"
         and type(end) in (int, float) and math.isfinite(end)
         and 0 < end - time.monotonic() <= profile["unit_seconds"][kind], "finite container-local deadline")
    return end


def publish_worker(folder, name, value, cap, write_limit):
    """Serialization may OOM inside containment; it never runs on the host."""
    need(name in NAMES.values(), "two fixed scientific outputs only")
    root = Path(folder)
    need(root == Path("/output") and root.is_dir() and not root.is_symlink(), "owned output tmpfs")
    body = canonical(value)
    need(0 < len(body) <= cap, "serialized scientific output cap")
    path = root / name
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        offset = requested = calls = 0
        while offset < len(body):
            piece = memoryview(body)[offset:offset + 65536]
            need(requested + len(piece) <= write_limit, "worker requested-write budget before write")
            requested += len(piece)
            calls += 1
            count = os.write(fd, piece)
            need(count > 0, "complete worker output write")
            offset += count
        os.fsync(fd)
        os.fchmod(fd, 0o444)
        st = os.fstat(fd)
        need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size == len(body)
             and (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns) ==
                 tuple(getattr(path.lstat(), k) for k in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")),
             "immutable same-FD/named-path worker output")
        parent_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        os.close(fd)
    digest = hashlib.sha256(body).hexdigest()
    return ({"name": name, "bytes": len(body), "sha256": digest},
            {"bytes_requested": requested, "bytes_confirmed": offset, "write_calls": calls,
             "exclusive_append_only": True, "same_fd_path": True, "fsync": True,
             "complete": True, "sha256": digest})


def decode_plane(asset, row, expected_layout, *, deps, ranges, runtime, profile, admission):
    """Only the original fixed-version range route; no arbitrary opener."""
    eid = row["ophys_experiment_id"]
    end = admitted(profile, admission, "plane", eid)
    asset.validate()
    need(asset.experiment == eid and asset.version_id == row["version_id"]
         and asset.provider_blake2b == row["blake2b_512"], "original plane identity")
    need(runtime == RUNTIME and vars(ranges.limits) == profile["plane_range_limits"],
         "exact declared range budget")
    cap = profile["unit_caps"]["plane"]
    need(ranges.limits.max_requests <= cap["http_requests"]
         and ranges.limits.response_body_bytes <= cap["http_response_body_bytes"]
         and ranges.limits.logical_read_bytes <= cap["logical_read_bytes"]
         and ranges.limits.max_requests * 32768 <= cap["http_header_reservation_bytes"],
         "range budget inside nonrefundable host reservation")
    need(expected_layout["experiment"] == eid
         and expected_layout["asset_sha256"] == deps.pipeline.digest(vars(asset)), "saved layout binding")
    with deps.range.open_versioned(asset, ranges, runtime) as file:
        fields = deps.pipeline.field_layouts(file, deps.native)
        need(fields == expected_layout["fields"], "same-version complete required layouts")
        dataset, info = deps.native.neural_metadata(file, row)
        records = deps.native.presentations(file)
        native_layout = deps.pipeline.layout(dataset)
    need(time.monotonic() < end, "plane complete before common deadline")
    value = {"schema": "neural063_range_native_metadata_v1", "experiment": eid,
             "mouse": row["mouse_id"], "session": row["ophys_session_id"], "split": row["split"],
             "asset_sha256": deps.pipeline.digest(vars(asset)), "neural_metadata": info,
             "presentations": records, "presentation_sha256": deps.pipeline.digest(records),
             "layout": native_layout, "response_projection_performed": False,
             "full_object_BLAKE2b_verified": False}
    output, write_usage = publish_worker("/output", NAMES["plane"], value, MAX_OUTPUT["plane"],
                                          profile["unit_caps"]["plane"]["worker_artifact_write_bytes"])
    need(time.monotonic() < end, "plane publication inside container deadline")
    custody = ranges.receipt()
    summary = {k: custody[k] for k in ("requests_admitted", "response_body_bytes_reserved_including_failures",
               "complete_response_body_bytes_observed", "logical_bytes_requested", "range_receipt_bytes_reserved", "failed")}
    summary["request_unresolved"] = custody["unresolved_request"] is not None
    summary["range_records_sha256"] = deps.pipeline.digest(custody["ranges"])
    summary["records_count"] = len(custody["ranges"])
    return {"output": output, "identity": eid,
            "source_usage": {"worker_output": write_usage, "range": summary,
                             "session_input_bytes_read_including_EOF_probes": 0},
            "vlen_allocation_bound": None, "unknown_heap_retained": True,
            "neural_values_decoded": False, "benchmark_ready": False}


def read_plane_input(ref, cap):
    need(set(ref) == {"experiment", "path", "bytes", "sha256"}, "exact plane input descriptor")
    need(type(ref["bytes"]) is int and 0 < ref["bytes"] <= cap
         and re.fullmatch(r"[0-9a-f]{64}", ref["sha256"]), "bounded plane input")
    path = Path(ref["path"])
    need(path.is_absolute() and path.parent == Path("/inputs/planes")
         and path.name == ref["experiment"] + ".json"
         and all(not p.is_symlink() for p in (path, *path.parents)), "fixed readonly plane input")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == ref["bytes"],
             "exact regular plane input")
        body = bytearray()
        while len(body) < ref["bytes"]:
            piece = os.read(fd, min(65536, ref["bytes"] - len(body)))
            need(piece, "complete plane input")
            body.extend(piece)
        need(not os.read(fd, 1) and stamp(before) == stamp(os.fstat(fd)), "stable complete plane input")
    finally:
        os.close(fd)
    need(hashlib.sha256(body).hexdigest() == ref["sha256"], "plane input hash")
    return strict(body)


def derive_complete_session(selection, assets_manifest, session_id, plane_inputs, *, deps, profile, admission):
    rows = [row for row in deps.manifest.full_scope(selection)
            if row["ophys_session_id"] == session_id]
    need(rows, "one existing complete original session")
    assets = deps.manifest.validate_assets(assets_manifest, selection)
    sid = session_id
    end = admitted(profile, admission, "session", sid)
    need(admission["selection_sha256"] == deps.manifest.SELECTION_SHA256
         and admission["assets_sha256"] == deps.pipeline.digest(assets_manifest)
         and admission["plane_inputs_sha256"] == sha(plane_inputs),
         "complete inventory and original input cross-binding")
    expected = {r["ophys_experiment_id"] for r in rows}
    need(len(plane_inputs) == len(expected) and {r["experiment"] for r in plane_inputs} == expected,
         "every original session plane required, never caller-selected subset")
    input_bytes = sum(r["bytes"] for r in plane_inputs)
    need(input_bytes <= profile["session_input_bytes"]
         and input_bytes + len(plane_inputs) <= profile["unit_caps"]["session"]["logical_read_bytes"],
         "complete input and EOF reservation before any JSON decoding")
    planes = {}
    for ref in plane_inputs:
        need(time.monotonic() < end, "session input container-local deadline")
        value = read_plane_input(ref, MAX_OUTPUT["plane"])
        need(value["schema"] == "neural063_range_native_metadata_v1"
             and value["experiment"] == ref["experiment"]
             and value["asset_sha256"] == deps.pipeline.digest(vars(assets[ref["experiment"]]))
             and value["response_projection_performed"] is False
             and value["full_object_BLAKE2b_verified"] is False, "original plane asset/custody schema")
        planes[ref["experiment"]] = value
    schedule, supports = deps.pipeline.derive_session(rows, planes, deps.algorithm)
    need(time.monotonic() < end, "complete session scientific derivation deadline")
    envelope = {"schema": "neural063_contained_session_envelope_v1", "session": sid,
                "schedule": schedule, "supports": supports, "plane_inputs": plane_inputs,
                "completed_inventory_sha256": admission["completed_inventory_sha256"],
                "selection_sha256": admission["selection_sha256"], "assets_sha256": admission["assets_sha256"],
                "response_projection_performed": False, "benchmark_ready": False}
    output, write_usage = publish_worker("/output", NAMES["session"], envelope, MAX_OUTPUT["session"],
                                          profile["unit_caps"]["session"]["worker_artifact_write_bytes"])
    need(time.monotonic() < end, "session publication inside container deadline")
    return {"output": output, "identity": sid, "complete_plane_count": len(planes),
            "source_usage": {"worker_output": write_usage, "range": None,
                             "session_input_bytes_read_including_EOF_probes": input_bytes + len(plane_inputs)},
            "zero_eligible_events": all(s["supported"] == 0 for s in supports.values()),
            "session_json_allocation_bound": None, "benchmark_ready": False}
