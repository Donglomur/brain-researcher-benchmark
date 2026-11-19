"""Six finite changed-path controls; importing this file performs no tests.

An exact selected generated plan and an externally admitted CI/control envelope are required. All HDF bodies are
invented and remain in memory. No child process, Docker request, provider call,
original data, kernel test, or automatic retry is part of this runner.
"""
import argparse
import contextlib
import copy
import hashlib
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import time
import types
from unittest import mock

SOURCE_KEYS = {"adapter", "inventory", "exporter", "worker", "fixture", "controller", "controller_graph", "range", "manifest", "pipeline",
               "owner", "owner_io", "owner_scoring", "preparation", "algorithm", "native"}
LIMITS = {
    "per_fixture_extent_bytes": 131072,
    "per_fixture_hdf_write_bytes": 1048576,
    "all_fixture_hdf_write_bytes": 5242880,
    "in_memory_inventory_bytes": 4194304,
    "saved_artifact_bytes": 524288,
    "result_bytes": 65536,
    "plan_artifact_bytes": 65536,
    "source_read_bytes": 4194304,
    "interpreter_read_bytes": 67108865,
    "outer_pool_log_cap_bytes": 1048576
}
HEX = "[0-9a-f]{64}"
MOCKED_GRAPH_CASES = ("admission_before_start", "unknown_custody_stops_dispatch", "incomplete_session_held",
                      "recovery_exact_identity", "settlement_evidence_refused")


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False, ensure_ascii=False) + "\n").encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def raises(call, phrase=None):
    try:
        call()
    except Exception as exc:
        if phrase:
            require(phrase in str(exc), "wrong refusal category: " + type(exc).__name__)
        return type(exc).__name__
    raise AssertionError("required refusal did not occur")


class ReadBudget:
    def __init__(self):
        self.bytes = 0
        self.interpreter_bytes = 0

    def pinned(self, ref, cap=131072, *, interpreter=False, retain=True):
        require(type(ref) is dict and set(ref) == {"path", "bytes", "sha256"}, "exact source descriptor")
        require(type(ref["bytes"]) is int and 0 < ref["bytes"] <= cap
                and type(ref["sha256"]) is str and re.fullmatch(HEX, ref["sha256"]), "bounded source identity")
        if interpreter:
            self.interpreter_bytes += ref["bytes"] + 1
            require(self.interpreter_bytes <= LIMITS["interpreter_read_bytes"], "prospective interpreter read cap")
        else:
            self.bytes += ref["bytes"] + 1
            require(self.bytes <= LIMITS["source_read_bytes"], "prospective source read cap")
        path = Path(ref["path"])
        require(path.is_absolute() and all(not p.is_symlink() for p in (path, *path.parents)), "ordinary source path")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_size == ref["bytes"], "exact source extent")
            body, digest, remaining = bytearray(), hashlib.sha256(), before.st_size
            while remaining:
                piece = os.read(fd, min(65536, remaining))
                require(piece, "complete source read")
                digest.update(piece)
                if retain:
                    body.extend(piece)
                remaining -= len(piece)
            after = os.fstat(fd)
            require(not os.read(fd, 1) and (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                    == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "stable source bytes")
        finally:
            os.close(fd)
        require(digest.hexdigest() == ref["sha256"], "source pin mismatch")
        return bytes(body) if retain else None


IMMUTABLE_PINS = {
    "owner": {
        "bytes": 80,
        "sha256": "d857d613efdca2fad6b20a106349516a410e2837b5f4bff6b6d2db592ba58658"
    },
    "owner_io": {
        "bytes": 10152,
        "sha256": "8e29aa60a95b8433361bda241ee60e25db40c0884547c7bc55d5015c4741ad4e"
    },
    "owner_scoring": {
        "bytes": 12817,
        "sha256": "e85413e3af2b63c919fbfc93fffdb6fc0e37af9d038f693df99da980b04dc0dc"
    },
    "preparation": {
        "bytes": 82,
        "sha256": "a852591a1dea52c60ea4a6cacb06b150e49397ac9189d2120e8dc7c4f9241d95"
    },
    "algorithm": {
        "bytes": 7672,
        "sha256": "aa5255ba1d238331cc91122b4b84ce2d90a0d23b7b19964ddb91c72953bac3c8"
    },
    "native": {
        "bytes": 8094,
        "sha256": "59938e74806637cc3be504a6bcb2a550f1571d22e6d55342abdd048978389c66"
    },
    "range": {
        "bytes": 15515,
        "sha256": "73d479623f9fe78f42631aeca49113748791b5737cfe7b6aec43789737ffb7e1"
    },
    "manifest": {
        "bytes": 7952,
        "sha256": "36b7eb96e9d40f808035979b1f30c7e103746d20d670235d8658cda613381205"
    },
    "pipeline": {
        "bytes": 20502,
        "sha256": "ad1e2e80dc8676af208a3fee4bd0977694fc3abf145d883fbb5b8b7a17dd8f42"
    }
}


def validate_source_identities(plan):
    require(set(plan["sources"]) == SOURCE_KEYS, "exact changed control source closure")
    for key, expected in IMMUTABLE_PINS.items():
        ref = plan["sources"][key]
        require({field: ref[field] for field in ("bytes", "sha256")} == expected,
                "immutable scientific source identity differs before imports")


def load_sources(plan, bodies):
    names = [("owner", "owner"), ("owner_io", "owner.io"), ("owner_scoring", "owner.scoring"),
             ("preparation", "preparation"), ("algorithm", "preparation.algorithm"),
             ("native", "preparation.native"), ("range", "range_io"), ("manifest", "manifest"),
             ("pipeline", "pipeline"), ("adapter", "generated_n063_adapter"),
             ("inventory", "generated_n063_inventory"), ("exporter", "generated_n063_exporter"),
             ("worker", "generated_n063_worker"), ("fixture", "generated_n063_fixture"),
             ("controller", "generated_n063_controller"),
             ("controller_graph", "generated_n063_controller_graph")]
    require(not any(name in sys.modules for _, name in names), "fresh source module namespace")
    result = {}
    for key, name in names:
        module = types.ModuleType(name)
        module.__file__ = plan["sources"][key]["path"]
        module.__package__ = name if key in ("owner", "preparation") else name.rpartition(".")[0]
        if key in ("owner", "preparation"):
            module.__path__ = []
        sys.modules[name] = module
        exec(compile(bodies[key], module.__file__, "exec"), module.__dict__)
        result[key] = module
    return types.SimpleNamespace(**result)


class ArtifactGuard:
    """Independent failure-inclusive file-write cap for this future campaign."""
    def __init__(self, root):
        self.root = root
        self.requested = LIMITS["plan_artifact_bytes"]
        self.paths = {}
        self.open = os.open
        self.write = os.write
        self.close = os.close

    def guarded_open(self, path, flags, mode=0o777, *, dir_fd=None):
        writing = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        if writing:
            require(dir_fd is None, "no relative-dir artifact writes")
            p = Path(path)
            require(p.is_absolute() and self.root in p.parents and not p.is_symlink(), "generated output scope")
        fd = self.open(path, flags, mode, dir_fd=dir_fd)
        if writing:
            self.paths[fd] = str(path)
        return fd

    def guarded_write(self, fd, body):
        if fd in self.paths:
            self.requested += len(body)
            require(self.requested <= LIMITS["saved_artifact_bytes"] - LIMITS["result_bytes"],
                    "independent generated file-write ceiling")
        return self.write(fd, body)

    def guarded_close(self, fd):
        try:
            return self.close(fd)
        finally:
            self.paths.pop(fd, None)


def profile_for(a):
    # Invented admission data for pure controls; never a real runtime release.
    unit = {key: 268435456 for key in a.COST_KEYS}
    unit.update(http_requests=64, http_response_body_bytes=8388608,
                http_header_reservation_bytes=2097152, logical_read_bytes=16777216,
                control_bytes=131072, closure_seconds=2)
    session = dict(unit)
    session.update(http_requests=0, http_response_body_bytes=0, http_header_reservation_bytes=0)
    return {"schema": a.SCHEMA, "selected": True, "runtime_qualified": True,
            "deployment": {key: ("unix:///invented/docker.sock" if key == "endpoint" else
                ("sha256:" if key == "image_id" else "") + "a" * 64) for key in a.DEPLOYMENT_KEYS},
            "global_caps": {key: 2 ** 40 for key in a.COST_KEYS},
            "unit_caps": {"plane": unit, "session": session},
            "plane_range_limits": {"max_requests": 64, "response_body_bytes": 8388608,
                "logical_read_bytes": 16777216, "record_bytes": 32768, "block_bytes": 32768,
                "cache_blocks": 4, "read_operation_bytes": 1048576, "hdf5_cache_bytes": 1048576,
                "seconds": 30, "request_seconds": 2},
            "session_input_bytes": 2097152, "output_caps": dict(a.MAX_OUTPUT),
            "terminal_inventory_bytes": 9377792, "runtime_versions": dict(a.RUNTIME),
            "unit_seconds": {"plane": 30, "session": 30},
            "isolation_limits": {"memory_bytes": 1879048192, "memory_swap_bytes": 1879048192,
                "pids": 32, "nofile": [1024, 1024], "tmpfs_bytes": 134217728, "cpu_threads": 1}}


def admission_for(a, profile, kind, identity, assets, refs):
    return {"schema": "neural063-contained-admission-v1", "kind": kind, "identity": identity,
            "profile_sha256": a.sha(profile), "deployment_sha256": a.sha(profile["deployment"]),
            "reservation_sha256": "b" * 64, "container_id": "c" * 64,
            "effective_controls_sha256": "d" * 64, "host_deadline_receipt_sha256": "e" * 64,
            "container_deadline_monotonic": time.monotonic() + 20,
            "clock_domain": "linux_container_monotonic", "selection_sha256": "f" * 64,
            "assets_sha256": digest(assets), "completed_inventory_sha256": "1" * 64,
            "plane_inputs_sha256": a.sha(refs)}


def invented_assets(m):
    rows = []
    for index in range(1936):
        session = 1000 + index % 703
        mouse = 1 + (session - 1000) % 107
        rows.append({"experiment": str(10000 + index), "session": str(session), "mouse": str(mouse),
                     "split": "fit" if mouse <= 73 else "validation" if mouse <= 88 else "query"})
    value = {"schema": "neural063_versioned_range_assets_v1", "selection_sha256": m.SELECTION["sha256"],
             "source_counts": {"experiments": 1936, "sessions": 703, "mice": 107, "rois": 133066},
             "mouse_splits": {"fit": 73, "validation": 15, "query": 19},
             "full_object_BLAKE2b_verified": False, "assets": rows}
    body = canonical(value)
    identity = {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    return body, identity


class Controls:
    def __init__(self, modules, root, h5py, numpy):
        self.m, self.root, self.h5py, self.numpy = modules, root, h5py, numpy
        self.profile = profile_for(modules.adapter)
        self.fixtures = {}
        self.fixture_receipts = []
        self.captured = {}
        self.details = {}
        self.memory_budget = {"used": 0, "limit": LIMITS["in_memory_inventory_bytes"]}
        self.graph_attempted, self.graph_result = False, None

    def build_fixtures(self):
        total = 0
        for variant in self.m.fixture.VARIANTS:
            body, receipt = self.m.fixture.build(variant, h5py=self.h5py, numpy=self.numpy)
            require(len(body) <= LIMITS["per_fixture_extent_bytes"], "invented extent bound")
            require(receipt["requested_hdf_write_bytes"] <= LIMITS["per_fixture_hdf_write_bytes"], "invented write bound")
            total += receipt["requested_hdf_write_bytes"]
            require(total <= LIMITS["all_fixture_hdf_write_bytes"], "five-fixture write bound")
            self.fixtures[variant] = body
            self.fixture_receipts.append(receipt)

    def rows_assets(self):
        rows, assets = [], {}
        for eid in ("101", "102"):
            row = self.m.fixture.row(eid)
            row.update(version_id="invented-version", blake2b_512="0" * 128,
                url="https://visual-behavior-ophys-data.s3.us-west-2.amazonaws.com/visual-behavior-ophys/behavior_ophys_experiments/behavior_ophys_experiment_" + eid + ".nwb")
            rows.append(row)
            assets[eid] = self.m.range.Asset(eid, row["url"] + "?versionId=invented-version",
                row["version_id"], '"invented-etag"', len(self.fixtures["mixed512"]), row["blake2b_512"])
        return rows, assets

    def capture_publish(self, folder, name, value, cap, *args, **kwargs):
        body = canonical(value)
        require(len(body) <= min(cap, 262144), "small complete invented publication")
        self.captured[name] = copy.deepcopy(value)
        ref = {"name": name, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
        usage = {"bytes_requested": len(body), "bytes_confirmed": len(body), "write_calls": 1,
                 "exclusive_append_only": True, "same_fd_path": True, "fsync": True,
                 "complete": True, "sha256": ref["sha256"]}
        return ref, usage

    @contextlib.contextmanager
    def prohibit_signal_values(self):
        h5 = self.h5py
        calls = []
        original_getitem, original_array, original_direct = h5.Dataset.__getitem__, h5.Dataset.__array__, h5.Dataset.read_direct
        def check(ds):
            require(ds.name != "/processing/ophys/dff/traces/data", "dF/F value read forbidden")
        def getitem(ds, key, *args, **kwargs):
            check(ds)
            if ds.name.endswith("/image_name"):
                calls.append(repr(key))
            return original_getitem(ds, key, *args, **kwargs)
        def array(ds, *args, **kwargs):
            check(ds)
            return original_array(ds, *args, **kwargs)
        def direct(ds, *args, **kwargs):
            check(ds)
            return original_direct(ds, *args, **kwargs)
        with mock.patch.object(h5.Dataset, "__getitem__", getitem), mock.patch.object(h5.Dataset, "__array__", array), mock.patch.object(h5.Dataset, "read_direct", direct):
            yield calls

    def local_plane(self, variant, row, asset):
        with self.h5py.File(io.BytesIO(self.fixtures[variant]), "r") as file:
            fields = self.m.pipeline.field_layouts(file, self.m.native)
            data, info = self.m.native.neural_metadata(file, row)
            records = self.m.native.presentations(file)
            layout = self.m.pipeline.layout(data)
        value = {"schema": "neural063_range_native_metadata_v1", "experiment": row["ophys_experiment_id"],
            "mouse": row["mouse_id"], "session": row["ophys_session_id"], "split": row["split"],
            "asset_sha256": self.m.pipeline.digest(vars(asset)), "neural_metadata": info,
            "presentations": records, "presentation_sha256": self.m.pipeline.digest(records),
            "layout": layout, "response_projection_performed": False, "full_object_BLAKE2b_verified": False}
        return value, {"experiment": row["ophys_experiment_id"], "asset_sha256": value["asset_sha256"], "fields": fields}

    def adapter_plane(self, variant, row, asset, layout):
        @contextlib.contextmanager
        def opened(*args):
            with self.h5py.File(io.BytesIO(self.fixtures[variant]), "r") as file:
                yield file
        budget = self.m.range.Budget(self.m.range.Limits(**self.profile["plane_range_limits"]))
        deps = types.SimpleNamespace(range=self.m.range, native=self.m.native, pipeline=self.m.pipeline)
        admission = admission_for(self.m.adapter, self.profile, "plane", row["ophys_experiment_id"], {}, [])
        with mock.patch.object(self.m.range, "open_versioned", opened), mock.patch.object(self.m.adapter, "publish_worker", self.capture_publish):
            return self.m.adapter.decode_plane(asset, row, layout, deps=deps, ranges=budget,
                runtime=self.profile["runtime_versions"], profile=self.profile, admission=admission)

    def session(self, rows, assets, planes, refs=None, profile=None):
        profile = self.profile if profile is None else profile
        refs = refs if refs is not None else [{"experiment": row["ophys_experiment_id"],
            "path": "/inputs/planes/" + row["ophys_experiment_id"] + ".json",
            "bytes": len(canonical(planes[row["ophys_experiment_id"]])),
            "sha256": hashlib.sha256(canonical(planes[row["ophys_experiment_id"]])).hexdigest()} for row in rows]
        manifest_value = {"invented_assets": sorted(assets)}
        manifest = types.SimpleNamespace(full_scope=lambda _: rows,
            validate_assets=lambda *_: assets, SELECTION_SHA256="f" * 64)
        deps = types.SimpleNamespace(manifest=manifest, pipeline=self.m.pipeline, algorithm=self.m.algorithm)
        admission = admission_for(self.m.adapter, profile, "session", "501", manifest_value, refs)
        with mock.patch.object(self.m.adapter, "read_plane_input", lambda ref, cap: copy.deepcopy(planes[ref["experiment"]])), mock.patch.object(self.m.adapter, "publish_worker", self.capture_publish):
            return self.m.adapter.derive_complete_session({}, manifest_value, "501", refs,
                deps=deps, profile=profile, admission=admission)

    def test_01_admission(self):
        a, w = self.m.adapter, self.m.worker
        # These pure refusal branches prove ordering; the selected positive
        # descriptor/library checks already ran in this same invocation.
        changed_runtime = copy.deepcopy(self.plan["runtime"])
        changed_runtime["python"]["path"] = str(self.root / "different-python")
        raises(lambda: validate_interpreter(changed_runtime), "interpreter before imports")
        changed_source = copy.deepcopy(self.plan)
        changed_source["sources"]["native"]["sha256"] = "0" * 64
        raises(lambda: validate_source_identities(changed_source), "before imports")
        wrong_versions = copy.deepcopy(self.plan["runtime"])
        wrong_versions["distributions"]["numpy"] = "0.0.0"
        raises(lambda: observe_imports(self.imported, wrong_versions), "imported library version")
        wrong_origin = copy.deepcopy(self.plan["runtime"])
        wrong_origin["package_roots"]["numpy"] = str(self.root)
        raises(lambda: observe_imports(self.imported, wrong_origin), "selected package origin")
        self.details["portable_runtime_guards"] = {"interpreter_mismatch": True,
            "immutable_source_mismatch": True, "imported_version_mismatch": True,
            "imported_origin_mismatch": True, "negative_controls_are_pure": True}
        for identity, distributions in PROFILE_PACKAGES.items():
            declaration = {"schema": "neural063-portable-generated-runtime-v1",
                "sys_platform": identity[0], "machine": identity[1],
                "python_release": identity[2], "distributions": dict(distributions)}
            require(selected_distributions(declaration) == distributions,
                    "complete supported profile accepted")
            other = next(value for key, value in PROFILE_PACKAGES.items() if key != identity)
            swapped = copy.deepcopy(declaration)
            swapped["distributions"] = dict(other)
            raises(lambda: selected_distributions(swapped), "unsupported complete")
            hybrid = copy.deepcopy(declaration)
            hybrid["distributions"]["idna"] = other["idna"]
            raises(lambda: selected_distributions(hybrid), "unsupported complete")
            wrong_version = copy.deepcopy(declaration)
            wrong_version["distributions"]["numpy"] = "0.0.0"
            raises(lambda: selected_distributions(wrong_version), "unsupported complete")
            for field, replacement in (("sys_platform", "freebsd"),
                    ("machine", "unsupported-machine"), ("python_release", "3.11.0")):
                wrong_identity = copy.deepcopy(declaration)
                wrong_identity[field] = replacement
                raises(lambda: selected_distributions(wrong_identity), "unsupported complete")
        self.details["complete_runtime_profile_guards"] = {
            "accepted_complete_profiles": len(PROFILE_PACKAGES),
            "hybrid_refused": True, "opposite_profile_map_refused": True,
            "package_version_refused": True,
            "platform_refused": True, "machine_refused": True,
            "python_release_refused": True, "pure_declaration_controls": True}
        member = {"invented_shape_only": True}
        require(w.unwrap_selection({"original_selection": member}) is member, "exact authenticated wrapper member")
        raises(lambda: w.unwrap_selection({}))
        inactive = copy.deepcopy(self.profile)
        inactive.update(selected=False, runtime_qualified=False)
        inactive["deployment"] = {key: None for key in a.DEPLOYMENT_KEYS}
        require(a.validate_profile(inactive, require_selected=False)["launchable"] is False, "inactive fixture state")
        raises(lambda: a.validate_profile(inactive), "inactive")
        for invalid_endpoint in ("tcp://localhost:2375", "unix://host/socket", "unix:///a/../socket"):
            bad_endpoint = copy.deepcopy(self.profile)
            bad_endpoint["deployment"]["endpoint"] = invalid_endpoint
            raises(lambda: a.validate_profile(bad_endpoint), "endpoint")
        missing = copy.deepcopy(self.profile)
        missing["deployment"]["image_id"] = None
        raises(lambda: a.validate_profile(missing), "unresolved")
        for kind, field, below in (("plane", "source_setup_read_bytes", 67108864),
                                   ("session", "export_read_bytes", 2 * a.MAX_OUTPUT["session"] + 8193)):
            under_reserved = copy.deepcopy(self.profile)
            under_reserved["unit_caps"][kind][field] = below
            raises(lambda: a.validate_profile(under_reserved), "reservation")
        admission = admission_for(a, self.profile, "plane", "101", {}, [])
        admission["container_deadline_monotonic"] = float("inf")
        raises(lambda: a.admitted(self.profile, admission, "plane", "101"), "deadline")
        admission["container_deadline_monotonic"] = time.monotonic() + 10
        admission["clock_domain"] = "host_monotonic"
        raises(lambda: a.admitted(self.profile, admission, "plane", "101"), "deadline")
        sources = {"range/range_io.py": {"path": "/operator/range/range_io.py", "bytes": w.RANGE["range_io.py"][0], "sha256": "0" * 64}}
        for prefix, values in (("original/", w.ORIGINAL), ("range/", w.RANGE)):
            for name, (size, sha) in values.items():
                sources.setdefault(prefix + name, {"path": "/operator/" + prefix + name, "bytes": size, "sha256": sha})
        for name in ("scientific_adapter.py", "worker.py"):
            sources[name] = {"path": "/operator/" + name, "bytes": 1, "sha256": "0" * 64}
        with mock.patch.object(w, "read_pinned", side_effect=AssertionError("source read before changed pin refusal")):
            raises(lambda: w.load_sources({"sources": sources}), "source pin")
        controller = self.m.controller
        inactive_operation = {key: None for key in ("schema", "selected", "runtime_qualified", "native", "runtime",
            "deployment", "sources", "host_inventory", "profile", "inputs", "layout_bank", "output_root", "limits",
            "startup_envelope", "authority_policy_sha256", "helpers")}
        inactive_operation.update(schema="neural063-portable-contained-controller-v1", selected=False, runtime_qualified=False)
        require(controller.validate_operation(inactive_operation, require_selected=False) == {"launchable": False},
                "inactive controller proposal accepted only as preparation")
        raises(lambda: controller.validate_operation(inactive_operation), "unselected")
        invented = types.SimpleNamespace(root=Path("/invented/authority/authority-declaration"),
            spent={key: 0 for key in controller.COUNTERS})
        operation = self.m.controller_graph.operation(controller, None,
            copy.deepcopy(self.profile), invented, "authority-declaration")
        operation["sources"]["controller.py"] = copy.deepcopy(self.plan["sources"]["controller"])
        policy = self.m.controller_graph.authority_fixture(controller, operation)
        declarations_only = {"declarations_valid": True, "authority_proven": False}
        require(controller.validate_operation(operation) == declarations_only
                and controller.validate_authority(policy, operation) == declarations_only,
                "well-bound invented declarations never prove live authority")
        bad_policy = copy.deepcopy(policy)
        bad_policy["native_controller"]["sha256"] = "0" * 64
        raises(lambda: controller.validate_authority(bad_policy, operation), "code anchor")
        bad_endpoint_policy = copy.deepcopy(policy)
        bad_endpoint_policy["endpoint"] = "unix:///invented/other.sock"
        raises(lambda: controller.validate_authority(bad_endpoint_policy, operation), "allowlist")
        for field in ("runtime", "helpers"):
            changed = copy.deepcopy(operation)
            if field == "runtime":
                changed[field]["docker"]["sha256"] = "0" * 64
            else:
                changed[field]["bank"]["sha256"] = "0" * 64
            raises(lambda: controller.validate_authority(policy, changed), "allowlist")
        changed = copy.deepcopy(operation)
        changed["native"]["ledger"] = "/invented/foreign-ledger"
        raises(lambda: controller.validate_authority(policy, changed), "native authority")
        escaped = copy.deepcopy(operation)
        escaped["output_root"] = str(self.root / "outside-declared-namespace")
        raises(lambda: controller.validate_authority(policy, escaped), "namespace")
        authority_path = Path("/invented/authority/policy.json")
        command = controller.fixed_outer_command(operation, Path("/invented/authority/operation.json"), "1" * 64,
                                                  authority_path, "2" * 64)
        require(command[command.index("--authority") + 1] == str(authority_path)
                and command[command.index("--authority-sha256") + 1] == "2" * 64,
                "fixed outer argv binds independently supplied authority")
        # The approved payload excludes only the native protocol's own pointer,
        # avoiding a digest cycle without dropping any deployment/science field.
        authority_ref = {"path": str(authority_path), "bytes": 1, "sha256": "2" * 64}
        operation_path = Path("/invented/authority/operation.json")
        payload = copy.deepcopy(operation)
        payload["native"].pop("protocol")
        protocol = {"schema": "neural063-portable-native-protocol-v1",
            "authority": authority_ref, "mode": "host", "operation_path": str(operation_path),
            "operation_payload": payload}
        protocol_args = {"operation_path": operation_path, "authority_descriptor": authority_ref,
                         "mode": "host"}
        expected_binding = {"approved_payload_equal": True, "authority_proven": False}
        require(controller.validate_native_protocol(protocol, operation, **protocol_args) == expected_binding,
                "complete cycle-free payload declaration still does not prove authority")
        changed_payload = copy.deepcopy(operation)
        changed_payload["runtime"]["docker"]["sha256"] = "0" * 64
        raises(lambda: controller.validate_native_protocol(protocol, changed_payload, **protocol_args),
               "approved complete operation payload")
        changed_authority = dict(authority_ref, sha256="3" * 64)
        raises(lambda: controller.validate_native_protocol(protocol, operation,
            operation_path=operation_path, authority_descriptor=changed_authority, mode="host"), "approved independent authority")
        raises(lambda: controller.validate_native_protocol(protocol, operation,
            operation_path=operation_path, authority_descriptor=authority_ref, mode="recover"), "approved fixed controller entry")
        raises(lambda: controller.validate_native_protocol(protocol, operation,
            operation_path=Path("/invented/authority/other-operation.json"), authority_descriptor=authority_ref,
            mode="host"), "approved independent authority")
        protocol_pointer_only = copy.deepcopy(operation)
        protocol_pointer_only["native"]["protocol"] = {
            "path": str(self.root / "approved-protocol.json"), "bytes": 1, "sha256": "4" * 64}
        require(controller.validate_native_protocol(protocol, protocol_pointer_only, **protocol_args)
                == expected_binding, "only the documented self-pointer is excluded")
        recovery_path = Path("/invented/authority/recovery.json")
        recovery = {"schema": "neural063-portable-contained-recovery-v1", "selected": True,
            "runtime_qualified": True, "authority_policy_sha256": operation["authority_policy_sha256"],
            "original_operation": {"path": str(operation_path), "bytes": 1, "sha256": "5" * 64},
            "native": {**copy.deepcopy(operation["native"]), "id": "invented-recovery"},
            "kind": "plane", "identity": "101",
            "output_root": operation["output_root"] + "/recovery-invented-recovery",
            "envelope": copy.deepcopy(operation["startup_envelope"])}
        for field in ("startup", "reservation", "create_intent", "created", "prior_group_closure"):
            recovery[field] = {"path": "/invented/authority/" + field + ".json", "bytes": 1, "sha256": "6" * 64}
        recovery_payload = copy.deepcopy(recovery)
        recovery_payload["native"].pop("protocol")
        recovery_protocol = {"schema": "neural063-portable-native-protocol-v1",
            "authority": authority_ref, "mode": "recover", "operation_path": str(recovery_path),
            "operation_payload": recovery_payload}
        recovery_args = {"operation_path": recovery_path, "authority_descriptor": authority_ref, "mode": "recover"}
        require(controller.validate_native_protocol(recovery_protocol, recovery, **recovery_args)
                == expected_binding, "complete actual recovery document shape is bound")
        for mutation in ("kind", "identity", "custody", "envelope"):
            different = copy.deepcopy(recovery)
            if mutation == "kind":
                different["kind"] = "session"
            elif mutation == "identity":
                different["identity"] = "102"
            elif mutation == "custody":
                different["create_intent"]["sha256"] = "7" * 64
            else:
                different["envelope"]["host_write_bytes"] += 1
            raises(lambda: controller.validate_native_protocol(recovery_protocol, different, **recovery_args),
                   "approved complete operation payload")
        self.details["portable_native_protocol"] = {"complete_payload_binding": True,
            "changed_payload_authority_mode_path_refused": True,
            "only_native_protocol_pointer_omitted": True,
            "recovery_kind_identity_custody_envelope_refused": True, "actual_native_gate_executed": False}
        self.details["portable_authority_declarations"] = {"well_bound_but_authority_unproven": True,
            "native_code_anchor_refusal": True, "endpoint_refusal": True,
            "helper_runtime_refusal": True, "ledger_refusal": True, "output_namespace_refusal": True,
            "actual_native_admission_executed": False}
        self.details["admission"] = {"provider_calls": 0, "changed_source_before_read": True, "kernel_proof": False}
        graph_root = self.root / "controller-graphs"
        graph_root.mkdir(mode=0o700)
        self.graph_attempted = True
        self.graph_result = self.m.controller_graph.run_cases(controller, self.m.inventory, a, self.m.exporter,
            profile_factory=profile_for, assets_factory=invented_assets, evidence_root=graph_root,
            artifact_guard=self.guard, memory_budget=self.memory_budget)
        self.details["controller_graph_fake_engine"] = self.graph_result
        require([case["name"] for case in self.graph_result["cases"]] == list(MOCKED_GRAPH_CASES),
                "exact five selected fake-engine graph cases")
        require(self.graph_result["passed"] == 5 and self.graph_result["failed"] == 0
                and all(self.graph_result[k] == 0 for k in ("actual_processes", "signals", "provider_requests")),
                "five fake-engine graph cases pass without real side effects")

    def test_02_real_hdf_parity(self):
        self.build_fixtures()
        rows, assets = self.rows_assets()
        planes = {}
        with self.prohibit_signal_values() as calls:
            for row in rows:
                eid = row["ophys_experiment_id"]
                native, layout = self.local_plane("mixed512", row, assets[eid])
                self.adapter_plane("mixed512", row, assets[eid], layout)
                require(self.captured["plane_metadata.json"] == native, "complete generated metadata equality")
                field = layout["fields"]["intervals/presentation/image_name"]
                require(field["contains_variable_length_or_reference"] is True
                        and field["heap_payload_bytes"] is None and field["full_logical_array_bytes"] is None,
                        "VLEN uncertainty preserved")
                require(len(native["presentations"]) == 11
                        and all(len(v["image"].encode()) == 512 for v in native["presentations"]), "all512-byte names")
                planes[eid] = native
            expected_schedule, expected_supports = self.m.pipeline.derive_session(rows, planes, self.m.algorithm)
            self.session(rows, assets, planes)
            got = self.captured["session_support.json"]
            require(got["schedule"] == expected_schedule and got["supports"] == expected_supports,
                    "complete generated schedule/support equality")
            require(all(len(v["supported_events"]) == 2 and all(len(e["spans"]) == 15 for e in v["supported_events"])
                        for v in got["supports"].values()), "both events/all15 bins for both planes")
            require(len(calls) >= 4 and all(v == "slice(None, None, None)" for v in calls), "full VLEN selection preserved")
        self.details["parity"] = {"invented_planes": 2, "events_per_plane": 2, "bins_per_event": 15,
            "all_metadata_roi_schedule_support_fields_equal": True, "dff_values_read": False,
            "provider_transport_qualified": False, "complete_cohort_executed": False}

    def test_03_scientific_refusals(self):
        rows, assets = self.rows_assets()
        with self.prohibit_signal_values():
            for variant in ("ascii513", "unicode513"):
                raises(lambda: self.local_plane(variant, rows[0], assets["101"]), "invalid image name")
                with self.h5py.File(io.BytesIO(self.fixtures[variant]), "r") as file:
                    layout = {"experiment": "101", "asset_sha256": self.m.pipeline.digest(vars(assets["101"])),
                              "fields": self.m.pipeline.field_layouts(file, self.m.native)}
                self.captured.pop("plane_metadata.json", None)
                raises(lambda: self.adapter_plane(variant, rows[0], assets["101"], layout), "invalid image name")
                require("plane_metadata.json" not in self.captured, "invalid label never published")
            left, _ = self.local_plane("mixed512", rows[0], assets["101"])
            right, _ = self.local_plane("consensus_mismatch", rows[1], assets["102"])
            raises(lambda: self.session(rows, assets, {"101": left, "102": right}), "consensus")
            planes = {r["ophys_experiment_id"]: self.local_plane("zero_omissions", r, assets[r["ophys_experiment_id"]])[0] for r in rows}
            result = self.session(rows, assets, planes)
            require(result["zero_eligible_events"] is True, "legitimate zero event result")
            got = self.captured["session_support.json"]
            require(got["schedule"]["original_omissions"] == 0 and got["schedule"]["scheduled"] == 0,
                    "original zero omission schedule")
        self.details["scientific_refusals"] = {"invalid_utf8_byte_lengths": [513, 513],
            "consensus_refused": True, "zero_omissions_distinct_from_failure": True}

    def test_04_session_identity(self):
        rows, assets = self.rows_assets()
        planes = {r["ophys_experiment_id"]: self.local_plane("mixed512", r, assets[r["ophys_experiment_id"]])[0] for r in rows}
        refs = [{"experiment": r["ophys_experiment_id"], "path": "/inputs/planes/" + r["ophys_experiment_id"] + ".json",
                 "bytes": len(canonical(planes[r["ophys_experiment_id"]])), "sha256": digest(planes[r["ophys_experiment_id"]])} for r in rows]
        raises(lambda: self.session(rows, assets, planes, refs=refs[:1]), "every original session plane")
        for key, value in (("asset_sha256", "0" * 64), ("full_object_BLAKE2b_verified", True)):
            changed = copy.deepcopy(planes)
            changed["102"][key] = value
            raises(lambda: self.session(rows, assets, changed), "asset/custody")
        limited = copy.deepcopy(self.profile)
        limited["session_input_bytes"] = 1
        raises(lambda: self.session(rows, assets, planes, profile=limited), "input")
        self.details["session_identity"] = {"matching_subset_refused": True, "wrong_asset_refused": True,
            "false_full_object_custody_refused": True, "input_limit_before_decode": True}

    def test_05_inventory(self):
        m, a = self.m.inventory, self.m.adapter
        body, identity = invented_assets(m)
        startup_envelope = {key: 0 for key in m.COUNTERS}
        startup_envelope.update(host_write_bytes=8192, control_bytes=8192, source_setup_read_bytes=67108864)
        memory_bytes, snapshots = [0], {}
        real_publish = m.exclusive_bytes
        def memory_inventory(path, data):
            if Path(path).name in ("INITIAL.json", "FINAL.json"):
                memory_bytes[0] += len(data)
                self.memory_budget["used"] += len(data)
                require(self.memory_budget["used"] <= self.memory_budget["limit"], "shared graph/inventory memory sink cap")
                snapshots[str(path)] = data
                return {"name": Path(path).name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            return real_publish(path, data)
        def construct(name, profile):
            root = self.root / name
            startup = m.reserve_startup(profile, root, "9" * 64, startup_envelope, a.validate_profile)
            return m.Inventory(body, assets_identity=identity, profile=profile,
                               validate_profile=a.validate_profile, root=root, owner_sha256="9" * 64, startup=startup)
        with mock.patch.object(m, "ASSETS_IDENTITY", identity), mock.patch.object(m, "exclusive_bytes", memory_inventory):
            inv = construct("inventory-complete-map", self.profile)
            require(len(inv.planes) == 1936 and len(inv.sessions) == 703, "entire invented host identity inventory")
            with mock.patch.object(m, "strict", side_effect=AssertionError("unexpected host scientific decode")):
                raises(lambda: m.Inventory(body + b"!", assets_identity=identity, profile=self.profile,
                    validate_profile=a.validate_profile, root=inv.root, owner_sha256="9" * 64, startup={}), "ASSETS")
                raises(lambda: inv.session_custody("1000"), "reserve")
                raises(lambda: inv.reserve("session", "1000"), "every original plane")
                reservation = inv.reserve("plane", "10000")
                payload = b"\x00\xffopaque"
                artifact = {"name": "plane_metadata.json", "bytes": len(payload),
                            "sha256": hashlib.sha256(payload).hexdigest()}
                lease = inv.claim_export("plane", "10000", expected=artifact, container_id="c" * 64,
                    producer_receipt_sha256="d" * 64, ownership_receipt_sha256="e" * 64,
                    host_deadline_monotonic=time.monotonic() + 20)
                require(lease["export_read_bytes"] == reservation["envelope"]["export_read_bytes"]
                        - self.profile["output_caps"]["plane"] - 1, "host capture disjoint from container export reads")
                raises(lambda: inv.claim_export("plane", "10000", expected=artifact, container_id="c" * 64,
                    producer_receipt_sha256="d" * 64, ownership_receipt_sha256="e" * 64,
                    host_deadline_monotonic=time.monotonic() + 20), "one copyout")
                # This is a generated receipt-join test, not real producer/custody evidence.
                writer = {"bytes_requested": len(payload) + 5, "bytes_confirmed": len(payload), "write_calls": 2,
                          "exclusive_append_only": True, "same_fd_path": True, "fsync": True, "complete": True,
                          "sha256": artifact["sha256"]}
                copyout = {"verified": True, "identity": "10000", "artifact": artifact,
                    "container_id": lease["container_id"], "reservation_sha256": reservation["reservation_sha256"],
                    "write_usage": dict(writer), "confirmed_written_bytes": len(payload),
                    "requested_write_bytes": len(payload) + 5, "read_bytes": len(payload)}
                closure = {"kind": "plane", "identity": "10000", "reservation_sha256": reservation["reservation_sha256"],
                    "container_id": lease["container_id"], "producer_receipt_sha256": "d" * 64,
                    "ownership_receipt_sha256": "e" * 64, "export_receipt_sha256": digest(copyout),
                    "artifact": artifact, "proofs": {key: True for key in ("producer_complete", "producer_zero_exit",
                        "oom_absent", "timeout_absent", "copyout_verified", "streams_eof", "cli_reaped",
                        "ownership_verified", "container_absence_verified")}}
                receipt = {"schema": "neural063_unit_success_settlement_v1", "kind": "plane", "identity": "10000",
                    "reservation_sha256": reservation["reservation_sha256"], "container_id": lease["container_id"],
                    "output": artifact, "worker_output": dict(writer), "copyout": copyout,
                    "range": {"failed": False, "request_unresolved": False, "requests_admitted": 0,
                        "records_count": 0, "range_receipt_bytes_reserved": 0,
                        "complete_response_body_bytes_observed": 0, "response_body_bytes_reserved_including_failures": 0,
                        "range_records_sha256": digest([]), "logical_bytes_requested": 0},
                    "session_input_bytes_read_including_EOF_probes": 0, "source_setup_read_bytes": 1,
                    "controller_requested_write_bytes": 0, "controller_control_bytes": 0,
                    "unmeasured_residuals_stay_reserved": True,
                    "receipt_hashes": {"ready": "d" * 64, "configuration": "1" * 64, "exit": "2" * 64,
                        "absence": "3" * 64, "copyout": digest(copyout)}}
                before = dict(inv.spent)
                altered = copy.deepcopy(receipt)
                altered["worker_output"]["complete"] = False
                raises(lambda: inv.finish_unit("plane", "10000", artifact=artifact, closure=closure,
                    copyout_result=copyout, settlement_receipt=altered), "append-only")
                require(inv.spent == before and inv.active == ("plane", "10000"), "refusal never releases reservation")
                wrong_closure = dict(closure, reservation_sha256="0" * 64)
                raises(lambda: inv.finish_unit("plane", "10000", artifact=artifact, closure=wrong_closure,
                    copyout_result=copyout, settlement_receipt=receipt), "same owned")
                inv.finish_unit("plane", "10000", artifact=artifact, closure=closure,
                                copyout_result=copyout, settlement_receipt=receipt)
                cap = reservation["envelope"]
                require(inv.spent["worker_artifact_write_bytes"] == before["worker_artifact_write_bytes"]
                        - cap["worker_artifact_write_bytes"] + len(payload) + 5, "requested successful worker bytes settled")
                require(inv.spent["host_write_bytes"] == before["host_write_bytes"] - cap["host_write_bytes"]
                        + len(payload) + 5 + cap["control_bytes"], "requested host bytes plus control residual")
                require(inv.spent["source_setup_read_bytes"] == before["source_setup_read_bytes"],
                        "unmeasured bootstrap and readiness setup remains fully reserved")
                require(inv.spent["export_read_bytes"] == before["export_read_bytes"] - cap["export_read_bytes"]
                        + copyout["read_bytes"] + artifact["bytes"] + 1, "host and container export reads both charged")
                settled = strict_json((inv.root / "plane-10000-settlement.json").read_bytes())
                require(settled["evidence"]["worker_output"]["bytes_requested"] > len(payload)
                        and "plane-10000" in inv.settlements, "requested evidence retained and durable settlement precedes release")
                second = inv.reserve("plane", "10001")
                failed_lease = inv.claim_export("plane", "10001", expected=artifact, container_id="c" * 64,
                    producer_receipt_sha256="d" * 64, ownership_receipt_sha256="e" * 64,
                    host_deadline_monotonic=time.monotonic() + 20)
                partial = {"identity": "10001", "reservation_sha256": second["reservation_sha256"],
                    "container_id": "c" * 64, "verified": False, "partial_path": failed_lease["output_path"],
                    "retained_extent_bytes": 2, "write_uncertain": True, "confirmed_prefix_sha256": hashlib.sha256(payload[:2]).hexdigest(),
                    "error": "invented interrupted binary export"}
                path = Path(failed_lease["output_path"])
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                try:
                    require(os.write(fd, payload[:2]) == 2, "tiny uncertain-partial fixture")
                finally:
                    os.close(fd)
                before_failure = dict(inv.spent)
                inv.finish_unit("plane", "10001", failure="export_failed", copyout_result=partial,
                    closure={"kind": "plane", "identity": "10001", "container_absence_verified": False})
                require(inv.spent == before_failure, "failure retains every initially reserved counter")
                saved_failure = strict_json((inv.root / "plane-10001-result.json").read_bytes())
                require(saved_failure["copyout_result"] == partial and saved_failure["closure"]["container_absence_verified"] is False,
                        "partial/unknown failure custody retained")
                inv.finalize()
            final = strict_json(snapshots[str(inv.root / "FINAL.json")])
            require(len(final["planes"]) == 1936 and len(final["sessions"]) == 703
                    and final["metadata_support_complete"] is False and final["benchmark_ready"] is False,
                    "partial work never completes full cohort")
            require(final["planes"]["10000"]["state"] == "complete" and final["planes"]["10001"]["state"] == "failed"
                    and final["sessions"]["1001"]["state"] == "held", "completed/failed/held dispositions retained")
            limited = copy.deepcopy(self.profile)
            limited["global_caps"]["http_requests"] = limited["unit_caps"]["plane"]["http_requests"] - 1
            exhausted = construct("inventory-budget-exhausted", limited)
            raises(lambda: exhausted.reserve("plane", "10000"), "exhausted before dispatch")
            require(not exhausted.reservations and exhausted.active is None, "budget refusal before dispatch")
            exhausted.finalize()
            last = strict_json(snapshots[str(exhausted.root / "FINAL.json")])
            require(len(last["planes"]) == 1936 and len(last["sessions"]) == 703
                    and not last["metadata_support_complete"], "budget failure preserves full inventory")
        self.details["inventory"] = {"invented_planes": 1936, "invented_sessions": 703,
            "snapshot_memory_bytes": memory_bytes[0], "durable_small_records": True,
            "full_snapshots_saved": False, "opaque_scientific_decode_calls": 0,
            "failure_full_reservations_retained": True, "unequal_requested_confirmed_evidence": True,
            "success_requested_byte_settlement_with_residuals": True, "source_setup_full_reserved": True,
            "export_host_and_container_reads_charged": True, "kernel_or_full_cohort_proof": False}

    def binary_mode(self, mode, guard):
        e = self.m.exporter
        payload = b"\x00\xffN063\n\x80"
        expected = {"name": "plane_metadata.json", "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest()}
        identity = str(80000 + self.binary_modes.index(mode))
        folder = self.root / ("plane-" + identity)
        folder.mkdir(mode=0o700)
        lease = {"kind": "plane", "identity": identity, "container_id": "c" * 64,
            "output_path": str(folder / expected["name"]), "host_deadline_monotonic": time.monotonic() + 10,
            "clock_domain": "host_monotonic", "closure_seconds": 2,
            "export_read_bytes": len(payload) + 8193, "host_write_bytes": len(payload) + 4096,
            "reservation_sha256": "d" * 64, "producer_receipt_sha256": "e" * 64,
            "ownership_receipt_sha256": "f" * 64, "image_id": "sha256:" + "a" * 64,
            "single_export_attempt": True}
        deployment = {"docker": {"path": "/invented/runtime/docker", "resolved_path": "/invented/runtime/docker",
                "bytes": 1, "sha256": "a" * 64},
            "endpoint": "unix:///invented/docker.sock", "python_in_image": "/usr/bin/python3", "exporter_in_image": e.EXPORT_PATH,
            "image_id": lease["image_id"], "runtime_receipt_sha256": "b" * 64,
            "exporter_receipt_sha256": "b" * 64, "delegation_receipt_sha256": "b" * 64,
            "stop_helper_sha256": e.STOP_HELPER_SHA256}
        streams, writers, calls = [], [], []
        class FakeProc:
            returncode = None
            def wait(self, timeout=None):
                self.returncode = 1 if mode == "nonzero" else 0
                return self.returncode
        proc = FakeProc()
        original_write = guard.write
        for name in ("stdout", "stderr"):
            read_fd, write_fd = os.pipe()
            stream = os.fdopen(read_fd, "rb", buffering=0)
            streams.append(stream)
            setattr(proc, name, stream)
            content = payload if name == "stdout" else (b"diagnostic" if mode == "stderr" else b"")
            if name == "stdout":
                if mode == "short":
                    content = payload[:-1]
                elif mode == "corrupt":
                    content = b"X" + payload[1:]
                elif mode == "oversized":
                    content += b"!"
            if content:
                require(original_write(write_fd, content) == len(content), "finite invented pipe write")
            if mode == "held_open":
                writers.append(write_fd)
            else:
                os.close(write_fd)
        def popen(command, **kwargs):
            require(command == e.export_command(deployment, lease["container_id"], expected), "fixed export command")
            require(kwargs["close_fds"] is True and kwargs["start_new_session"] is False, "same-group export seam")
            calls.append("Popen")
            return proc
        def stop(handle):
            require(handle is proc, "only exact fake leader")
            calls.append("cleanup")
            if mode == "cleanup_permission":
                raise PermissionError("invented permission refusal")
            proc.wait()
            return {"leader_reaped": True, "whole_group_cleanup_delegated_to_watchdog": True}
        real_selector = e.selectors.DefaultSelector
        class CloseFailure:
            def __init__(self):
                self.inner = real_selector()
            def __getattr__(self, name):
                return getattr(self.inner, name)
            def close(self):
                self.inner.close()
                raise OSError("invented selector-close failure")
        uncertain_used = [False]
        def uncertain_write(fd, body):
            if guard.paths.get(fd) == lease["output_path"] and not uncertain_used[0]:
                uncertain_used[0] = True
                guard.requested += len(body)
                require(guard.requested <= LIMITS["saved_artifact_bytes"] - LIMITS["result_bytes"],
                        "uncertain write request charged before attempt")
                original_write(fd, body[:2])
                raise OSError("invented uncertain write after two bytes")
            return guard.guarded_write(fd, body)
        clock = [time.monotonic()]
        def advancing_clock():
            clock[0] += 0.25
            return clock[0]
        result = None
        try:
            with contextlib.ExitStack() as stack:
                stack.enter_context(mock.patch.object(e.subprocess, "Popen", popen))
                if mode == "uncertain_write":
                    stack.enter_context(mock.patch.object(os, "write", uncertain_write))
                if mode == "selector_close":
                    stack.enter_context(mock.patch.object(e.selectors, "DefaultSelector", CloseFailure))
                if mode == "held_open":
                    stack.enter_context(mock.patch.object(e.time, "monotonic", advancing_clock))
                result = e.copyout(lease, expected, deployment=deployment, stop_cli_leader=stop)
            require(calls == ["Popen", "cleanup"], "one fake export and one exact cleanup attempt")
            require(all(stream.closed for stream in streams), "all fake streams closed")
            require(result["container_absence_verified"] is False, "no mocked container absence claim")
            if mode == "exact":
                require(result["verified"] is True and result["artifact"] == expected, "binary-safe complete copyout")
                require(Path(lease["output_path"]).read_bytes() == payload, "opaque byte exactness")
                with mock.patch.object(e.subprocess, "Popen", side_effect=AssertionError("duplicate export dispatch")):
                    duplicate = e.copyout(lease, expected, deployment=deployment, stop_cli_leader=stop)
                    require(duplicate["verified"] is False and duplicate["attempt_marker_created"] is False
                            and "FileExistsError" in duplicate["error"], "one-use marker refuses duplicate before dispatch")
            else:
                require(result["verified"] is False and result["artifact"] is None and result["error"],
                        "observed failure is never certified")
                if mode == "uncertain_write":
                    require(result["write_uncertain"] is True and result["retained_extent_bytes"] == 2,
                            "uncertain partial extent retained")
                if mode == "cleanup_permission":
                    require("PermissionError" in result["error"], "permission refusal retained")
            return {"mode": mode, "verified": result["verified"], "read_bytes": result["read_bytes"],
                    "retained_extent_bytes": result.get("retained_extent_bytes"), "error": result["error"],
                    "fake_processes": 1, "actual_processes": 0, "signals": 0,
                    "cleanup_attempts": calls.count("cleanup")}
        finally:
            for fd in writers:
                os.close(fd)
            for stream in streams:
                if not stream.closed:
                    stream.close()

    binary_modes = ("exact", "short", "corrupt", "oversized", "stderr", "nonzero", "held_open",
                    "uncertain_write", "selector_close", "cleanup_permission")

    def test_06_binary_copyout(self):
        self.details["binary_copyout"] = [self.binary_mode(mode, self.guard) for mode in self.binary_modes]

METHODS = ("test_01_admission", "test_02_real_hdf_parity", "test_03_scientific_refusals",
           "test_04_session_identity", "test_05_inventory", "test_06_binary_copyout")
PLAN_KEYS = {"schema", "selected", "generated_only", "authentic_provider_requests", "docker_allowed",
             "network_allowed", "original_array_reads", "kernel_tests", "model_runs", "controller_graph_executed",
             "recovery_graph_executed", "evidence_root",
             "runner", "plan_builder", "ci_entry", "construction", "sources", "runtime", "limits", "methods", "binary_modes", "planned_mocked_controller_graph_cases"}


def strict_json(body):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, "duplicate JSON key")
            value[key] = item
        return value
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def prepare_plan(path, expected_sha):
    require(re.fullmatch(HEX, expected_sha), "reviewed raw plan SHA256")
    require(path.is_absolute() and path.is_file() and not path.is_symlink()
            and path.stat().st_size <= 65536 and all(not p.is_symlink() for p in path.parents), "bounded ordinary plan")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= 65536, "bounded plan extent")
        requested = before.st_size + 1
        body = bytearray()
        while len(body) < before.st_size:
            block = os.read(fd, min(65536, before.st_size - len(body)))
            require(block, "complete plan input")
            body.extend(block)
        after, named = os.fstat(fd), path.lstat()
        stamp = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        require(not os.read(fd, 1) and stamp(before) == stamp(after) == stamp(named), "stable same-FD plan")
    finally:
        os.close(fd)
    require(hashlib.sha256(body).hexdigest() == expected_sha, "exact reviewed plan bytes")
    plan = strict_json(body)
    require(type(plan) is dict and set(plan) == PLAN_KEYS and plan["schema"] == "neural063-portable-contained-generated-controls-v1",
            "exact generated control plan")
    require(plan["selected"] is True and plan["generated_only"] is True, "unselected source-only plan")
    require(all(plan[k] is False for k in ("authentic_provider_requests", "docker_allowed", "network_allowed",
            "original_array_reads", "kernel_tests", "model_runs", "controller_graph_executed",
            "recovery_graph_executed")), "generated source control boundary")
    require(plan["limits"] == LIMITS and plan["methods"] == list(METHODS)
            and plan["binary_modes"] == list(Controls.binary_modes)
            and plan["planned_mocked_controller_graph_cases"] == list(MOCKED_GRAPH_CASES), "fixed finite control campaign")
    construction = plan["construction"]
    require(type(construction) is dict and set(construction) == {
        "source_read_bytes_reserved", "interpreter_read_bytes_reserved",
        "plan_requested_write_reservation_bytes", "metadata_startup_read_bytes_measured",
        "entry_source_read_reservation_bytes"}, "bounded declared plan construction")
    require(type(construction["source_read_bytes_reserved"]) is int
            and 0 <= construction["source_read_bytes_reserved"] <= LIMITS["source_read_bytes"]
            and type(construction["interpreter_read_bytes_reserved"]) is int
            and 0 <= construction["interpreter_read_bytes_reserved"] <= LIMITS["interpreter_read_bytes"]
            and construction["plan_requested_write_reservation_bytes"] == LIMITS["plan_artifact_bytes"]
            and construction["entry_source_read_reservation_bytes"] == 163842
            and construction["metadata_startup_read_bytes_measured"] is False,
            "finite declared construction reservations")
    root = Path(plan["evidence_root"])
    require(root.is_absolute() and str(root) == os.path.normpath(str(root))
            and not root.exists() and not root.is_symlink() and root.parent.is_dir()
            and all(not p.is_symlink() for p in root.parents), "fresh ordinary generated evidence root")
    return plan, root, requested


PACKAGES = {
    "aiohappyeyeballs": "2.6.1",
    "aiohttp": "3.14.3",
    "aiosignal": "1.4.0",
    "attrs": "25.4.0",
    "frozenlist": "1.8.0",
    "fsspec": "2026.6.0",
    "h5py": "3.16.0",
    "idna": "3.11",
    "multidict": "6.7.0",
    "numpy": "2.4.6",
    "propcache": "0.4.1",
    "typing-extensions": "4.15.0",
    "yarl": "1.22.0"
}
LOCAL_PACKAGES = {
    "aiohappyeyeballs": "2.7.1",
    "aiohttp": "3.14.3",
    "aiosignal": "1.4.0",
    "attrs": "26.1.0",
    "frozenlist": "1.8.0",
    "fsspec": "2026.6.0",
    "h5py": "3.16.0",
    "idna": "3.18",
    "multidict": "6.9.0",
    "numpy": "2.4.6",
    "propcache": "0.5.4",
    "typing-extensions": "4.15.0",
    "yarl": "1.25.1"
}
PROFILE_PACKAGES = {
    ("darwin", "arm64", "3.11.6"): LOCAL_PACKAGES,
    ("linux", "x86_64", "3.11.18"): PACKAGES,
}


def selected_distributions(profile):
    """Select one complete declared profile; callers also bind the actual host."""
    fields = ("sys_platform", "machine", "python_release")
    if (type(profile) is not dict or set(profile) !=
            {"schema", "python_release", "sys_platform", "machine", "distributions"}
            or profile["schema"] != "neural063-portable-generated-runtime-v1"
            or any(type(profile[field]) is not str for field in fields)):
        raise ValueError("exact complete generated runtime profile required")
    expected = PROFILE_PACKAGES.get(tuple(profile[field] for field in fields))
    if (expected is None or type(profile["distributions"]) is not dict
            or profile["distributions"] != expected):
        raise ValueError("unsupported complete generated runtime profile")
    return dict(expected)


INSTALLED_SOURCES = {
    "aiohttp/client.py": {
        "bytes": 64597,
        "sha256": "a5467752c13ae51bf5731a8e3997d5f8b44ab1c0c54b11a906e878ff3cc31701"
    },
    "aiohttp/client_reqrep.py": {
        "bytes": 54704,
        "sha256": "456c97cee222d0d11335eb8d00331b58f19dfa6c5ca552ec550334379f36a54f"
    },
    "fsspec/implementations/http.py": {
        "bytes": 30894,
        "sha256": "d6e5b0c6594e8cf7bc9900f9e08ac261024753561a01787f703997064f80a10f"
    },
    "fsspec/caching.py": {
        "bytes": 34024,
        "sha256": "6099bb4a3413c4e8326af2af004d02493fc64749a99c48e7208582744d506cb9"
    },
    "fsspec/spec.py": {
        "bytes": 78097,
        "sha256": "ec6f041509f780c48c3fa3f168580cf557fddc384573ffb50018af73fd3af5fa"
    },
    "h5py/_hl/files.py": {
        "bytes": 25154,
        "sha256": "926856d56326dbbf8cd6a698169c05e8d6f54932d40dc9989351b308e0358d36"
    }
}


def validate_interpreter(runtime):
    require(type(runtime) is dict and set(runtime) == {"python", "profile", "python_release",
            "sys_platform", "machine", "distributions", "package_roots", "installed_sources"},
            "exact selected portable runtime declaration")
    require(sys.version_info[:2] == (3, 11) and sys.version.split()[0] == runtime["python_release"]
            and sys.platform == runtime["sys_platform"] and os.uname().machine == runtime["machine"],
            "selected Python release and host identity")
    require(Path(sys.executable).resolve(strict=True) == Path(runtime["python"]["path"]),
            "same selected interpreter before imports")


def verify_runtime(plan, budget):
    runtime = plan["runtime"]
    validate_interpreter(runtime)
    budget.pinned(runtime["python"], cap=67108864, interpreter=True, retain=False)
    profile = strict_json(budget.pinned(runtime["profile"], cap=65536))
    expected = selected_distributions(profile)
    require(profile == {"schema": "neural063-portable-generated-runtime-v1",
            "python_release": runtime["python_release"], "sys_platform": runtime["sys_platform"],
            "machine": runtime["machine"], "distributions": runtime["distributions"]},
            "exact selected runtime profile")
    require(runtime["distributions"] == expected, "exact selected complete distribution profile")
    observed = {name: importlib.metadata.version(name) for name in expected}
    require(observed == expected, "installed distribution metadata versions")
    roots = runtime["package_roots"]
    require(type(roots) is dict and set(roots) == {"numpy", "h5py", "fsspec", "aiohttp"},
            "four selected imported package origins")
    for name, value in roots.items():
        require(type(value) is str and len(value.encode()) <= 2048 and Path(value).is_absolute()
                and str(Path(value).resolve(strict=True)) == value, "selected resolved package origin")
    installed = runtime["installed_sources"]
    require(type(installed) is dict and set(installed) == set(INSTALLED_SOURCES),
            "maintained installed Python source closure")
    for relative, expected in INSTALLED_SOURCES.items():
        ref = installed[relative]
        package, suffix = relative.split("/", 1)
        require({key: ref[key] for key in ("bytes", "sha256")} == expected
                and Path(ref["path"]) == Path(roots[package]) / suffix,
                "maintained installed source identity")
        budget.pinned(ref, retain=False)
    return observed


def observe_imports(modules, runtime):
    """Observe actual imports in this invocation, distinct from metadata pins."""
    observed = {}
    for name, module in modules.items():
        version = getattr(module, "__version__", None)
        require(version == runtime["distributions"][name], "imported library version agrees with declaration")
        origin = Path(module.__file__).resolve(strict=True)
        require(origin.is_relative_to(Path(runtime["package_roots"][name])),
                "imported module from selected package origin")
        observed[name] = {"version": version, "resolved_file": str(origin)}
    return observed


def publish_result(root, result, guard):
    body = canonical(result)
    require(len(body) <= LIMITS["result_bytes"], "reserved final result capacity")
    require(guard.requested + len(body) <= LIMITS["saved_artifact_bytes"], "complete application saved-write ceiling")
    path = root / "RESULT.json"
    fd = guard.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    requested = 0
    try:
        offset = 0
        while offset < len(body):
            piece = memoryview(body)[offset:]
            requested += len(piece)
            require(guard.requested + requested <= LIMITS["saved_artifact_bytes"], "final failure-inclusive write ceiling")
            count = guard.write(fd, piece)
            require(count > 0, "complete final result")
            offset += count
        os.fsync(fd)
        os.fchmod(fd, 0o444)
    finally:
        guard.close(fd)
    return {"path": str(path), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
            "requested_write_bytes": requested}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--plan-sha256", required=True)
    args = parser.parse_args(argv)
    plan, root, plan_read_requested = prepare_plan(args.plan, args.plan_sha256)
    root.mkdir(mode=0o700)
    budget, guard = ReadBudget(), ArtifactGuard(root)
    result = {"schema": "neural063-portable-contained-generated-result-v1", "plan_sha256": args.plan_sha256,
              "generated_only": True, "actual_processes": 0, "signals": 0, "provider_requests": 0,
              "plan_read_requested_bytes": plan_read_requested,
              "kernel_tests": False, "original_array_reads": False, "benchmark_ready": False,
              "controller_graph_executed": False, "recovery_graph_executed": False,
              "actual_container_lifecycle": False, "actual_recovery": False,
              "methods": [], "details": {}, "fixture_receipts": [], "scope_limitations": [
                  "Fake export processes do not qualify Docker, signals, kernel memory, descendants or container cleanup.",
                  "Generated two-plane parity is not full-cohort scientific completion.",
                  "Whole inventories retained in a bounded memory sink are not durable whole-inventory publication proof.",
                  "Query privacy and mixed ClockUnsupported session outcomes are unexercised.",
                  "Metadata and imported version/origin checks do not authenticate complete wheels or native binaries.",
                  "Controller and recovery graph evidence uses only a deterministic fake engine; real lifecycle remains unexecuted.",
                  "Outer pool log has its separate 1048576-byte cap; runtime startup I/O is unmeasured."]}
    controls = None
    failure = None
    bootstrap_importing = True
    result["bootstrap_metadata_process_refusals"] = 0

    def deny_process_launch(*args, **kwargs):
        command = args[0] if args else kwargs.get("args")
        exact_metadata_command = (len(args) <= 1 and type(command) is list
            and len(command) == 2 and all(type(item) is str for item in command)
            and command == ["uname", "-p"] and kwargs.get("shell", False) is False
            and kwargs.get("executable") is None)
        if bootstrap_importing and exact_metadata_command:
            result["bootstrap_metadata_process_refusals"] += 1
            # Still no process: let platform's existing OSError fallback handle
            # unavailable processor metadata, without fabricating a value.
            raise PermissionError(1, "bootstrap metadata subprocess forbidden")
        raise AssertionError("actual process launch forbidden")

    try:
        budget.pinned(plan["runner"], retain=False)
        require(Path(plan["runner"]["path"]) == Path(__file__).resolve(strict=True), "exact selected runner path")
        budget.pinned(plan["plan_builder"], retain=False)
        budget.pinned(plan["ci_entry"], retain=False)
        validate_source_identities(plan)
        source_bodies = {key: budget.pinned(ref) for key, ref in plan["sources"].items()}
        result["distribution_metadata_versions"] = verify_runtime(plan, budget)
        with (
            mock.patch.object(subprocess, "Popen", side_effect=deny_process_launch),
            mock.patch.object(os, "kill", side_effect=AssertionError("real signals forbidden")),
            mock.patch.object(os, "killpg", side_effect=AssertionError("real group signals forbidden")),
            mock.patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden")),
            mock.patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")),
        ):
            import h5py
            import numpy
            import fsspec
            import aiohttp
            result["imported_modules"] = observe_imports(
                {"numpy": numpy, "h5py": h5py, "fsspec": fsspec, "aiohttp": aiohttp}, plan["runtime"])
            bootstrap_importing = False
            modules = load_sources(plan, source_bodies)
            source_bodies.clear()
            controls = Controls(modules, root, h5py, numpy)
            controls.guard = guard
            controls.plan = plan
            controls.imported = {"numpy": numpy, "h5py": h5py, "fsspec": fsspec, "aiohttp": aiohttp}
            with mock.patch.object(os, "open", guard.guarded_open),                  mock.patch.object(os, "write", guard.guarded_write),                  mock.patch.object(os, "close", guard.guarded_close):
                for name in METHODS:
                    started = time.monotonic()
                    item = {"method": name, "passed": False}
                    try:
                        getattr(controls, name)()
                        item["passed"] = True
                    except Exception as exc:
                        item["error"] = type(exc).__name__ + ": " + str(exc)[:500]
                    item["seconds"] = round(time.monotonic() - started, 6)
                    result["methods"].append(item)
    except BaseException as exc:
        failure = type(exc).__name__ + ": " + str(exc)[:500]
    result["admission_or_campaign_error"] = failure
    if controls is not None:
        result["details"] = controls.details
        result["fixture_receipts"] = controls.fixture_receipts
        result["controller_graph_fake_engine"] = {"planned": list(MOCKED_GRAPH_CASES),
            "attempted": controls.graph_attempted, "evidence": controls.graph_result}
        recovery = next((case for case in (controls.graph_result or {}).get("cases", [])
                         if case.get("name") == "recovery_exact_identity"), None)
        result["recovery_mocked"] = {"planned": True, "evidence": recovery}
        result["shared_fake_file_memory_bytes"] = controls.memory_budget["used"]
    result["source_read_bytes_reserved"] = budget.bytes
    result["interpreter_read_bytes_reserved"] = budget.interpreter_bytes
    result["declared_plan_construction"] = plan["construction"]
    result["plan_write_reservation_charged"] = LIMITS["plan_artifact_bytes"]
    result["saved_artifact_requested_bytes_before_result"] = guard.requested
    result["passed"] = sum(item["passed"] for item in result["methods"])
    result["failed"] = sum(not item["passed"] for item in result["methods"])
    result["unattempted"] = len(METHODS) - len(result["methods"])
    result["success"] = failure is None and result["passed"] == len(METHODS)
    ref = publish_result(root, result, guard)
    if result["success"]:
        print(json.dumps({"controls": list(METHODS)}, sort_keys=True))
    else:
        print(json.dumps({"error": "generated controls failed", "passed": result["passed"],
                          "failed": result["failed"], "unattempted": result["unattempted"]}, sort_keys=True))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
