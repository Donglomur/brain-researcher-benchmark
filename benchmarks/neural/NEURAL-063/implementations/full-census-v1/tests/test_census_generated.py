"""One selected generated-only campaign for new N063 census paths.

No original object, network address, dataset selection, or model is consumed.
Third-party/source imports happen only in main after exact prospective pins pass.
"""
import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import sys
from types import SimpleNamespace
import unittest
from unittest import mock


MAX_GENERATED_WRITES = 458_752
TERMINAL_GENERATED_RESERVE = 98_304
MAX_FIXTURE = 131_072
WRITTEN = 0
EVIDENCE = {}
ROOT = CORE = DEPS = H5 = NP = FIXTURE = WRAPPER = PLAN = BUILDER = None


def charge(count, *, terminal=False):
    global WRITTEN
    cap = MAX_GENERATED_WRITES if terminal else MAX_GENERATED_WRITES - TERMINAL_GENERATED_RESERVE
    if type(count) is not int or count < 0 or WRITTEN + count > cap:
        raise RuntimeError("generated cumulative application artifact ceiling reached")
    WRITTEN += count


def publish(path, body, *, terminal=False):
    charge(len(body), terminal=terminal)
    with path.open("xb") as stream:
        stream.write(body)
    path.chmod(0o400)
    return {"path": str(path), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def profile(stage="layouts"):
    return {"stage": stage, "runtime_versions": dict(CORE.RUNTIME), "reject_unknown_vlen": True,
            "max_interval_groups": 4, "max_group_fields": 8, "max_name_bytes": 512,
            "max_presentation_tables": 1, "max_metadata_elements": 10000,
            "max_fixed_metadata_bytes": 1024 * 1024, "max_numeric_chunk_bytes": 1024 * 1024,
            "max_plane_memory_estimate_bytes": 64 * 1024 * 1024,
            "max_session_memory_estimate_bytes": 256 * 1024 * 1024,
            "max_presentation_records": 64, "max_supported_events": 64,
            "max_chunk_coordinates": 2048, "max_chunk_index_bytes": 8 * 1024 * 1024,
            "max_support_artifact_bytes": 1024 * 1024, "max_json_nodes": 200000,
            "max_json_depth": 32, "max_json_string_chars": 4096,
            "artifact_bytes": 16 * 1024 * 1024,
            "total_artifact_reservation_bytes": 256 * 1024 * 1024,
            "disposition_bytes": 8192 + 4096 * 1936 + 2048 * 703}


def row(eid="101", sid="501", mouse="1"):
    return {"ophys_experiment_id": eid, "ophys_session_id": sid, "mouse_id": mouse,
            "split": "fit", "rois": [{"cell_roi_id": "10", "cell_specimen_id": "100"}],
            "context": {"cre_line": "invented", "targeted_structure": "VISp", "imaging_depth": 100,
                        "image_set": "A", "passive": False, "experience_level": "Familiar", "session_number": 1}}


def make_store(name, write_limit=512 * 1024 * 1024):
    target = ROOT / name
    target.mkdir()
    class GeneratedMeter(DEPS.io.ByteMeter):
        def write(self, amount):
            charge(amount)  # failure-inclusive before original meter/open
            return super().write(amount)
    return DEPS.io.ArtifactStore(target, GeneratedMeter(512 * 1024 * 1024, write_limit))


@contextmanager
def no_neural_values():
    original_getitem = H5.Dataset.__getitem__
    blocked = {"/" + CORE.DATA, "/controls/contiguous", "/controls/unallocated", "/controls/unallocated_contiguous"}
    counts = {"attempts": 0}
    def guarded(ds, key, *args, **kwargs):
        if ds.name in blocked:
            counts["attempts"] += 1
            raise AssertionError("census attempted invented dF/F value access")
        return original_getitem(ds, key, *args, **kwargs)
    def reject_array(*args, **kwargs):
        counts["attempts"] += 1
        raise AssertionError("census attempted dataset array/read_direct conversion")
    with mock.patch.object(H5.Dataset, "__getitem__", guarded), \
         mock.patch.object(H5.Dataset, "__array__", reject_array), \
         mock.patch.object(H5.Dataset, "read_direct", reject_array):
        yield counts


def invented_fixture():
    buffer = io.BytesIO()
    with H5.File(buffer, "w") as file:
        table = file.create_group(CORE.TABLE.rstrip("/"))
        table.create_dataset("id", data=NP.array([10, 11, 12, 13], dtype="int64"))
        table.create_dataset("cell_specimen_id", data=NP.array([100, 101, 102, 103], dtype="int64"))
        table.create_dataset("valid_roi", data=NP.array([True, False, False, False], dtype="bool"))
        trace = file.create_group(CORE.TRACE.rstrip("/"))
        values = NP.arange(161 * 4, dtype="float32").reshape(161, 4) / 100
        data = trace.create_dataset("data", data=values, chunks=(10, 2), compression="gzip", compression_opts=1)
        data.attrs["unit"] = "NA"
        clock = trace.create_dataset("timestamps", data=NP.arange(161, dtype="float64") / 20, chunks=(32,))
        clock.attrs["unit"] = "seconds"
        roi = trace.create_dataset("rois", data=NP.arange(4, dtype="int64"))
        roi.attrs["neurodata_type"] = "DynamicTableRegion"
        roi.attrs["table"] = table.ref
        presentations = file.create_group("intervals/presentation")
        presentations.create_dataset("id", data=NP.arange(11, dtype="int64"))
        presentations.create_dataset("start_time", data=NP.arange(11, dtype="float64") * .75)
        omissions = NP.zeros(11, dtype="bool"); omissions[[4, 8]] = True
        presentations.create_dataset("omitted", data=omissions)
        presentations.create_dataset("image_name", data=NP.array([b"image"] * 11, dtype="S8"))
        controls = file.create_group("controls")
        controls.create_dataset("contiguous", data=NP.arange(80, dtype="float32").reshape(20, 4))
        controls.create_dataset("unallocated", shape=(20, 4), chunks=(5, 2), dtype="float32", fillvalue=1.25)
        controls.create_dataset("unallocated_contiguous", shape=(20, 4), dtype="float32", fillvalue=2.5)
        controls.create_dataset("vlen_names", data=["image"] * 11, dtype=H5.string_dtype("utf-8"))
    body = buffer.getvalue()
    if len(body) > MAX_FIXTURE:
        raise RuntimeError("invented fixture exceeds prospective byte cap")
    ref = publish(ROOT / "invented_fixture.nwb", body)
    ref["blake2b"] = hashlib.blake2b(body).hexdigest()
    EVIDENCE["fixture"] = ref
    return Path(ref["path"])


class CensusControls(unittest.TestCase):
    def test_01_unchanged_support_and_all_column_chunk_metadata(self):
        p = profile("metadata_support")
        with no_neural_values() as guard, H5.File(FIXTURE, "r") as file:
            structure = CORE.structure_admission(file, DEPS.native, p)
            fields = DEPS.pipeline.field_layouts(file, DEPS.native)
            admitted = CORE.admit_layout(fields, p)
            data, info = DEPS.native.neural_metadata(file, row())
            records = DEPS.native.presentations(file)
            plane = {"experiment": "101", "session": "501", "mouse": "1", "split": "fit",
                     "neural_metadata": info, "presentations": records,
                     "presentation_sha256": DEPS.pipeline.digest(records)}
            session, supports = DEPS.pipeline.derive_session([row()], {"101": plane}, DEPS.alg)
            supported = supports["101"]
            self.assertEqual(supported["supported"], 2)
            self.assertEqual(supported["original_omissions"], 2)
            spans = [span for event in supported["supported_events"] for span in event["spans"]]
            self.assertEqual(len(spans), 30)
            result = CORE.chunk_census(data, spans, profile=p, extent_bytes=FIXTURE.stat().st_size, block_bytes=128)
            self.assertEqual(info["columns"], [0])
            expected = {(tr * 10, cr * 2) for left, right in spans
                        for tr in range(left // 10, (right - 1) // 10 + 1) for cr in range(2)}
            actual = {tuple(e["coordinate"]) for e in result["entries"]}
            self.assertEqual(actual, expected)
            self.assertTrue(any(e["coordinate"][1] == 2 for e in result["entries"]))
            self.assertGreater(result["coordinate_touches_before_union"], len(actual))
            by_index = {tuple(info.chunk_offset): info for info in
                        (data.id.get_chunk_info(j) for j in range(data.id.get_num_chunks()))}
            for entry in result["entries"]:
                expected_info = by_index[tuple(entry["coordinate"])]
                self.assertEqual((entry["byte_offset"], entry["stored_bytes"], entry["filter_mask"]),
                                 (expected_info.byte_offset, expected_info.size, expected_info.filter_mask))
            self.assertFalse(result["dff_values_decoded"])
            self.assertFalse(result["is_actual_transfer_upper_bound"])
            self.assertFalse(result["full_object_BLAKE2b_verified"])
            self.assertEqual(guard["attempts"], 0)
            estimate = CORE.session_admission([row()], {"101": admitted}, p)
            EVIDENCE["positive"] = {"presentation_tables": structure["presentation_tables"],
                "native_metadata_columns": info["columns"], "supported_events": 2, "all_original_bins": 30,
                "unique_chunk_coordinates": len(actual), "original_chunk_touches": result["coordinate_touches_before_union"],
                "allocated_stored_bytes": result["stored_chunk_bytes_sum"],
                "stored_bytes_with_repeated_accesses": result["stored_bytes_counting_repeated_slice_accesses"],
                "invalid_ROI_only_column_chunk_included": True, "by_index_and_coordinate_metadata_equal": True,
                "dff_value_access_attempts": guard["attempts"], "allocation_admission": admitted,
                "session_admission": estimate, "unchanged_schedule": session["selected"]}

    def test_02_contiguous_unallocated_empty_and_invalid_storage(self):
        p = profile("chunks")
        with no_neural_values() as guard, H5.File(FIXTURE, "r") as file:
            outcomes = {}
            for name in ("contiguous", "unallocated", "unallocated_contiguous"):
                ds = file["controls/" + name]
                result = CORE.chunk_census(ds, [[0, 5], [5, 10]], profile=p,
                                           extent_bytes=FIXTURE.stat().st_size, block_bytes=128)
                outcomes[name] = {"layout": result["layout"], "entries": len(result["entries"]),
                                  "stored_bytes": result["stored_chunk_bytes_sum"]}
                if name != "contiguous":
                    self.assertTrue(all(e["disposition"] == "unallocated_fill" for e in result["entries"]))
                    self.assertEqual(result["stored_chunk_bytes_sum"], 0)
                    self.assertFalse(result["fill_value_decoded"])
            empty = CORE.chunk_census(file[CORE.DATA], [], profile=p,
                                       extent_bytes=FIXTURE.stat().st_size, block_bytes=128)
            self.assertEqual(empty["entries"], [])
            self.assertEqual(empty["unique_payload_cache_bytes"], 0)
            compact = SimpleNamespace(shape=(20, 4), dtype=NP.dtype("float32"), chunks=None,
                                      id=SimpleNamespace(get_offset=lambda: None, get_storage_size=lambda: 320))
            with self.assertRaisesRegex(CORE.CensusError, "non-addressable"):
                CORE.chunk_census(compact, [[0, 5]], profile=p, extent_bytes=1000, block_bytes=128)
            fake = SimpleNamespace(shape=(20, 4), dtype=NP.dtype("float32"), chunks=(5, 2),
                    id=SimpleNamespace(get_chunk_info_by_coord=lambda c:
                       SimpleNamespace(chunk_offset=c, byte_offset=9999, size=100, filter_mask=0)))
            with self.assertRaisesRegex(CORE.CensusError, "outside"):
                CORE.chunk_census(fake, [[0, 5]], profile=p, extent_bytes=1000, block_bytes=128)
            self.assertEqual(guard["attempts"], 0)
            EVIDENCE["storage_cases"] = {"actual_hdf5": outcomes, "zero_supported_intervals": True,
                "compact_nonaddressable_refused": True, "outside_original_extent_refused": True,
                "dff_value_access_attempts": guard["attempts"]}

    def test_03_preallocation_refusals_before_arrays_and_serialization(self):
        p = profile("metadata_support")
        with no_neural_values() as guard, H5.File(FIXTURE, "r") as file:
            fields = DEPS.pipeline.field_layouts(file, DEPS.native)
            vlen = dict(fields)
            vlen["intervals/presentation/image_name"] = DEPS.pipeline.layout(file["controls/vlen_names"])
            with mock.patch.object(H5.Dataset, "asstr", side_effect=AssertionError("VLEN decoding forbidden")) as asstr:
                with self.assertRaisesRegex(CORE.CensusError, "unknown VLEN"):
                    CORE.admit_layout(vlen, p)
                self.assertEqual(asstr.call_count, 0)
            failures = []
            for key in ("max_fixed_metadata_bytes", "max_metadata_elements", "max_numeric_chunk_bytes",
                        "max_plane_memory_estimate_bytes", "artifact_bytes", "max_support_artifact_bytes"):
                small = dict(p); small[key] = 1
                with self.assertRaises(CORE.CensusError):
                    CORE.admit_layout(fields, small)
                failures.append(key)
            admission = CORE.admit_layout(fields, p)
            small = dict(p); small["max_session_memory_estimate_bytes"] = 1
            with self.assertRaisesRegex(CORE.CensusError, "session"):
                CORE.session_admission([row()], {"101": admission}, small)
            calls = []
            fake = SimpleNamespace(shape=(161, 4), dtype=NP.dtype("float32"), chunks=(10, 2),
                                   id=SimpleNamespace(get_chunk_info_by_coord=lambda c: calls.append(c)))
            small = dict(p); small["max_chunk_coordinates"] = 1
            with self.assertRaisesRegex(CORE.CensusError, "before enumeration"):
                CORE.chunk_census(fake, [[0, 100]], profile=small, extent_bytes=1000, block_bytes=128)
            self.assertEqual(calls, [])
            small = dict(p); small["max_json_nodes"] = 1
            with self.assertRaisesRegex(CORE.CensusError, "node/depth"):
                CORE.json_upper({"x": [1]}, small)
            self.assertEqual(guard["attempts"], 0)
            EVIDENCE["preallocation_refusals"] = {"vlen_decode_calls": 0, "fixed_caps": failures,
                "session_refused": True, "chunk_query_calls_before_refusal": 0, "JSON_nodes_refused": True,
                "dff_value_access_attempts": 0}

    def test_04_full_inventory_failure_and_pre_admission_distinction(self):
        p = profile("layouts")
        store = make_store("full_inventory_failure", p["total_artifact_reservation_bytes"])
        budget = DEPS.range.Budget(DEPS.range.Limits(32, 131072, 1048576, 16384, 4096, 4, 65536, 65536, 60, 5))
        with self.assertRaises(Exception):
            CORE.run_census({}, {}, deps=DEPS, store=store, ranges=budget, profile=p)
        self.assertIsNone(store.census_report)
        self.assertFalse(store.census_complete)
        self.assertEqual(store.meter.write_bytes, 0)
        project = dict(p); project["stage"] = "project"
        with self.assertRaisesRegex(CORE.CensusError, "forbidden"):
            CORE.run_census({}, {}, deps=DEPS, store=store, ranges=budget, profile=project)
        # Test-only dependency injections model a full-sized GENERATED inventory.
        # Production full_scope/validate_assets and literal counts are unchanged.
        rows = [row(str(10000 + i), str(20000 + i % 703), str(1 + (i % 703) % 107)) for i in range(1936)]
        assets = {r["ophys_experiment_id"]: SimpleNamespace(experiment=r["ophys_experiment_id"],
                  url="generated-only-no-network", version_id="invented", etag='"generated"',
                  extent_bytes=FIXTURE.stat().st_size, provider_blake2b="0" * 128) for r in rows}
        calls = []
        @contextmanager
        def generated_open(asset, ranges, versions):
            calls.append(asset.experiment)
            if len(calls) == 2:
                raise CORE.CensusError("injected second-plane transport failure")
            with H5.File(FIXTURE, "r") as file:
                yield file
        proxy = SimpleNamespace(**vars(DEPS.range)); proxy.open_versioned = generated_open
        injected = SimpleNamespace(**vars(DEPS)); injected.range = proxy
        with mock.patch.object(DEPS.pipeline, "full_scope", return_value=rows), \
             mock.patch.object(DEPS.pipeline, "validate_assets", return_value=assets), no_neural_values():
            ref = CORE.run_census({"generated": True}, {"generated": True}, deps=injected,
                                  store=store, ranges=budget, profile=p)
        report = store.read_json(ref, roles={"census_dispositions"}, cap=p["disposition_bytes"])
        self.assertEqual(len(report["planes"]), 1936)
        self.assertEqual(len(report["sessions"]), 703)
        counts = {state: sum(r["status"] == state for r in report["planes"])
                  for state in ("complete", "failed", "unattempted")}
        self.assertEqual(counts, {"complete": 1, "failed": 1, "unattempted": 1934})
        self.assertEqual(sum(s["status"] == "held" for s in report["sessions"]), 703)
        self.assertEqual(len(calls), 2)
        self.assertFalse(report["complete"])
        self.assertIsNone(report["bank"])
        self.assertFalse(store.census_complete)
        self.assertEqual(store.census_report, ref)
        self.assertEqual(len(report["planes"][0]["artifacts"]), 1)
        self.assertEqual(budget.requests, 0)
        self.assertEqual(store.meter.write_limit, p["total_artifact_reservation_bytes"] + p["disposition_bytes"])
        EVIDENCE["full_sized_generated_inventory"] = {"report": ref, "planes": 1936, "sessions": 703,
            "counts": counts, "held_sessions": 703, "open_calls": 2, "actual_network_requests": 0,
            "production_full_scope_rejected_invalid_input_before_report": True,
            "production_projection_stage_refused": True, "cohort_complete": False,
            "dependency_injection_scope": "generated control only; no original lineage or cohort qualification"}

    def test_05_writer_failure_charges_and_reserved_final_report(self):
        p = profile()
        p["total_artifact_reservation_bytes"] = 4096
        p["disposition_bytes"] = 8192
        store = make_store("writer_failure", 4096)
        writer = CORE.Writer(DEPS, store, p)
        writer.reserve(4096)
        existing = store.write("occupied.json", b"{}\n", role="generated_existing", visibility="operator", producer="generated")
        before = store.meter.write_bytes
        with self.assertRaises(FileExistsError):
            writer.write("occupied", {"x": 1}, "generated_failure")
        self.assertGreater(store.meter.write_bytes, before)
        self.assertEqual(writer.used, store.meter.write_bytes - before)
        self.assertEqual(store.census_artifacts, [])
        self.assertEqual(Path(existing.path).read_bytes(), b"{}\n")
        with mock.patch.object(DEPS.range, "canonical", side_effect=AssertionError("serialization must not occur")) as encode:
            with self.assertRaisesRegex(CORE.CensusError, "artifact admission"):
                writer.write("too_large", {"x": "large"}, "generated_refusal", cap=1)
            self.assertEqual(encode.call_count, 0)
        ref = writer.write("final", {"complete": False, "reason": "generated failed attempt retained"},
                           "census_dispositions", p["disposition_bytes"], final=True)
        self.assertEqual(store.meter.write_limit, 4096 + 8192)
        self.assertEqual(store.census_report, ref)
        with self.assertRaisesRegex(CORE.CensusError, "exactly once"):
            writer.write("second_final", {"complete": False}, "census_dispositions", 8192, final=True)
        EVIDENCE["writer"] = {"failed_attempt_charged_bytes": writer.used,
            "existing_file_unchanged": True, "failed_descriptor_not_certified": True,
            "oversize_pre_serialization_calls": 0, "disposition_reserve_opened_once": True,
            "wrapper_receipt_reserve_untouched": True, "final": ref}

    def test_06_wrapper_unselected_cost_and_reserve_guards(self):
        proposals = [json.loads(Path(p).read_bytes()) for p in PLAN["operation_profiles"]]
        with mock.patch.object(WRAPPER, "load_sources", side_effect=AssertionError("dependency loading forbidden")) as load:
            bounds = []
            for proposal in proposals:
                CORE.validate_profile(proposal["core"])
                result = WRAPPER.validate_operation_profile(proposal, require_selected=False)
                self.assertFalse(result["guaranteed_complete_census_budget"])
                self.assertFalse(result["hard_RAM_certificate"])
                self.assertEqual(result["disposition_reserved_bytes"], 9_377_792)
                with self.assertRaisesRegex(ValueError, "selected"):
                    WRAPPER.validate_operation_profile(proposal)
                bounds.append({"stage": proposal["stage"], "conservative_global_bytes": result["conservative_global_bytes"]})
            base = proposals[0]
            project = json.loads(json.dumps(base)); project["stage"] = project["core"]["stage"] = "project"
            with self.assertRaisesRegex(ValueError, "forbidden"):
                WRAPPER.validate_operation_profile(project, require_selected=False)
            bad_cost = json.loads(json.dumps(base)); bad_cost["conservative_global_bytes"] += 1
            with self.assertRaisesRegex(ValueError, "planning total"):
                WRAPPER.validate_operation_profile(bad_cost, require_selected=False)
            small = json.loads(json.dumps(base)); small["core"]["disposition_bytes"] = 2_350_592
            with self.assertRaisesRegex(ValueError, "inventory"):
                WRAPPER.validate_operation_profile(small, require_selected=False)
            receipt = json.loads(json.dumps(base)); receipt["receipt_bytes"] = 1
            with self.assertRaisesRegex(ValueError, "final receipt"):
                WRAPPER.validate_operation_profile(receipt, require_selected=False)
            self.assertEqual(load.call_count, 0)
        future = ROOT / "helper_future_output"
        arguments = [PLAN["core_source"], PLAN["wrapper_source"], PLAN["range_source"],
                     PLAN["original_root"], PLAN["operation_profiles"], future, PLAN["worker_source"]]
        generated = BUILDER.build_plan(*arguments)
        self.assertEqual(generated["source_files"], PLAN["source_files"])
        for key in ("core_source", "wrapper_source", "range_source", "original_root", "operation_profiles",
                    "worker_source", "plan_builder_source"):
            self.assertEqual(generated[key], PLAN[key])
        self.assertEqual(generated["evidence_root"], str(future))
        self.assertFalse(future.exists())
        self.assertTrue(generated["generated_only"])
        for key in ("authentic_execution_selected", "authentic_provider_requests", "original_array_reads",
                    "model_runs", "network_allowed"):
            self.assertIs(generated[key], False)
        self.assertEqual(generated["limits"]["application_artifact_bytes"], MAX_GENERATED_WRITES)
        self.assertEqual(generated["limits"]["terminal_generated_reserve_bytes"], TERMINAL_GENERATED_RESERVE)
        existing = list(arguments); existing[5] = ROOT
        with self.assertRaisesRegex(ValueError, "fresh"):
            BUILDER.build_plan(*existing)
        wrong_worker = list(arguments); wrong_worker[6] = str(Path(PLAN["core_source"]) / "census.py")
        with self.assertRaisesRegex(ValueError, "names"):
            BUILDER.build_plan(*wrong_worker)
        wrong_range = list(arguments); wrong_range[2] = PLAN["core_source"]
        with self.assertRaises((ValueError, FileNotFoundError)):
            BUILDER.build_plan(*wrong_range)
        EVIDENCE["wrapper_guards"] = {"proposals": bounds, "selected_false_refused": True,
            "project_refused": True, "cost_mismatch_refused": True, "old_small_D_refused": True,
            "small_R_refused": True, "dependency_load_calls": 0,
            "authentic_CLI_executed": False, "import_had_no_scientific_dependencies": PLAN["wrapper_import_was_clean"],
            "builder_return_only_exact_source_pins": True, "builder_future_output_not_created": True,
            "builder_existing_output_wrong_worker_wrong_closure_refused": True,
            "builder_import_had_no_scientific_dependencies": PLAN["builder_import_was_clean"]}


class LimitedText:
    def __init__(self, cap):
        self.cap, self.parts, self.bytes = cap, [], 0
    def write(self, value):
        body = value.encode("utf-8", "replace")
        keep = body[:max(0, self.cap - self.bytes)]
        self.parts.append(keep)
        self.bytes += len(keep)
        return len(value)
    def flush(self):
        pass
    def text(self):
        return b"".join(self.parts).decode("utf-8", "replace")


def load_source(name, path):
    if (path.parent / "__pycache__").exists():
        raise RuntimeError("source bytecode cache forbidden")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


def main():
    global ROOT, CORE, DEPS, H5, NP, FIXTURE, WRAPPER, PLAN, BUILDER
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--plan-sha256", required=True)
    args = parser.parse_args()
    body = Path(args.plan).read_bytes()
    if len(body) > 65536 or hashlib.sha256(body).hexdigest() != args.plan_sha256:
        raise RuntimeError("exact prospective plan required")
    plan = PLAN = json.loads(body)
    for descriptor in plan["source_files"]:
        path = Path(descriptor["path"])
        data = path.read_bytes()
        if len(data) != descriptor["bytes"] or hashlib.sha256(data).hexdigest() != descriptor["sha256"]:
            raise RuntimeError("source/runtime pin changed: " + path.name)
    ROOT = Path(plan["evidence_root"])
    ROOT.mkdir()
    names = ("census", "manifest", "pipeline", "range_io", "owner", "preparation", "h5py", "numpy")
    if any(n in sys.modules for n in names):
        raise RuntimeError("fresh generated source namespace required")
    WRAPPER = load_source("census_wrapper_generated", Path(plan["wrapper_source"]))
    if any(n in sys.modules for n in names):
        raise RuntimeError("wrapper import executed scientific dependencies")
    plan["wrapper_import_was_clean"] = True
    BUILDER = load_source("census_plan_builder_generated", Path(plan["plan_builder_source"]))
    if any(n in sys.modules for n in names):
        raise RuntimeError("plan-builder import executed scientific dependencies")
    plan["builder_import_was_clean"] = True
    range_root = Path(plan["range_source"])
    source_root = Path(plan["core_source"])
    load_source("range_io", range_root / "range_io.py")
    load_source("manifest", range_root / "manifest.py")
    pipeline = load_source("pipeline", range_root / "pipeline.py")
    pins = json.loads((range_root / "ORIGINAL_SOURCES.json").read_bytes())["files"]
    native, alg, owner_io = pipeline.load_original(plan["original_root"], pins)
    CORE = load_source("census", source_root / "census.py")
    DEPS = SimpleNamespace(range=sys.modules["range_io"], pipeline=pipeline, native=native, alg=alg, io=owner_io)
    def no_network(*args, **kwargs):
        raise AssertionError("all network connections forbidden in generated census controls")
    limited = LimitedText(32768)
    result = None
    try:
        with mock.patch.object(socket.socket, "connect", no_network), \
             mock.patch.object(socket.socket, "connect_ex", no_network):
            import h5py
            import numpy
            from importlib.metadata import version
            H5, NP = h5py, numpy
            if version("h5py") != "3.16.0":
                raise RuntimeError("pinned generated h5py version changed")
            FIXTURE = invented_fixture()
            result = unittest.TextTestRunner(stream=limited, verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(CensusControls))
    finally:
        log = limited.text().encode()
        if len(log) > 32768:
            raise RuntimeError("bounded unittest transcript violated")
        log_ref = publish(ROOT / "controls.log", log, terminal=True)
        report = {"schema": "neural063-census-generated-result-v1", "generated_only": True,
                  "success": bool(result is not None and result.wasSuccessful()),
                  "methods": 0 if result is None else result.testsRun,
                  "failures": None if result is None else len(result.failures),
                  "errors": None if result is None else len(result.errors), "evidence": EVIDENCE,
                  "application_artifact_bytes_before_result": WRITTEN, "application_artifact_ceiling": MAX_GENERATED_WRITES,
                  "network_requests": 0, "original_array_reads": 0, "dff_projection_performed": False,
                  "authenticated_cohort_qualification": False, "controls_log": log_ref,
                  "cleanup": "All invented HDF5 handles and BytesIO fixture writers use completed context managers; no child/server/service loop created."}
        payload = (json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
        if len(payload) > 65536:
            raise RuntimeError("generated result cap exceeded")
        publish(ROOT / "RESULT.json", payload, terminal=True)
        print(json.dumps({"success": report["success"], "methods": report["methods"],
                          "failures": report["failures"], "errors": report["errors"],
                          "application_artifact_bytes": WRITTEN, "result": str(ROOT / "RESULT.json")}))
    return 0 if result is not None and result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
