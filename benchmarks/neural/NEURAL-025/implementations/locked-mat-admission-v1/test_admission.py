#!/usr/bin/env python3
"""Independent generated MATLAB7.3-structure controls; no authentic data/models."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import h5py
import numpy as np

HERE = Path(__file__).resolve().parent
SOURCE_START_SHA256 = hashlib.sha256((HERE / "admission.py").read_bytes()).hexdigest()
SPEC = importlib.util.spec_from_file_location("tested_calcium_admission", HERE / "admission.py")
A = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = A
SPEC.loader.exec_module(A)
P = A.pipeline()
ORIGINAL = [2, 5, 9, 14, 22, 31, 44]
GRID = np.arange(-200, 801, 10, dtype=float).reshape(1, -1)
BUDGET = 6 * 1024 * 1024
WRITTEN = 0


def charge(path: Path):
    global WRITTEN
    WRITTEN += path.stat().st_size
    if WRITTEN > BUDGET:
        raise RuntimeError("Independent fixture-write budget exceeded")


def pin(path: Path):
    return {"path": path.name, "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def fixture_document(session):
    mouse = P.SESSIONS[session][0]
    date = session.split("_", 1)[1]
    kin, neu, raw = [], [], []
    for i, n in enumerate(ORIGINAL):
        valid = i < 6
        x = np.column_stack((GRID.ravel() / 10 + n, -GRID.ravel() / 20 + n * 2))
        y = n + GRID.T / 8 + np.arange(24, dtype=float).reshape(1, -1)
        kin.append({"trialNumber": n, "locked": valid, "animalID": mouse, "date": date,
                    "eventName": "liftTimeDLC", "tPts": GRID, "LR": 1 + (i % 2),
                    "jointAngles": y if valid else np.empty((0, 0))})
        neu.append({"trialNumber": n, "locked": valid, "data": x if valid else np.empty((0, 0))})
        raw.append({"trialNumber": n, "animalID": mouse, "date": date,
                    "success": True, "grabTimeC": 5., "liftRT": 100., "goodDLC": True,
                    "wrongZoneFirst": False, "movementTime": 200., "timeToContact": 300.,
                    "has_radical": True})
    raw.append(dict(raw[-1], trialNumber=56, success=False))
    return {"kinematics": kin, "neurons": neu, "R": raw,
            "M": [{"config": {"tPts": GRID, "tBase": 10., "preT": -200., "postT": 800.,
                               "smoothSD": 35., "eventName": "liftTimeDLC",
                               "datasetInfo": {"mouseName": mouse, "sessionDate": date[:8],
                                               "filename": A.primary_assets()[session]["filename"][:-4]}},
                   "jointNames": list(P.JOINT_NAMES), "ROILags": np.array([[0., 1.]]), "cycleDurMs": 40.}]}


class MatFixtureWriter:
    """Write genuine HDF5 datasets with explicit MATLAB7.3 axis/reference layout.

    This is generated serialization, not a claim that MATLAB produced the bytes.
    """
    def __init__(self, handle):
        self.h = handle
        self.refs = handle.create_group("#refs#")
        self.serial = 0

    def value(self, value):
        name = f"v{self.serial}"
        self.serial += 1
        if isinstance(value, dict):
            group = self.refs.create_group(name)
            group.attrs["MATLAB_class"] = np.bytes_("struct")
            for key, child in value.items():
                ref = self.value(child).ref
                dataset = group.create_dataset(key, shape=(1, 1), dtype=h5py.ref_dtype)
                dataset[0, 0] = ref
            return group
        if isinstance(value, str):
            native = np.frombuffer(value.encode("utf-16-le"), dtype="<u2").reshape(1, -1)
            dataset = self.refs.create_dataset(name, data=native.T)
            dataset.attrs["MATLAB_class"] = np.bytes_("char")
            return dataset
        if isinstance(value, list) and all(isinstance(x, str) for x in value):
            dataset = self.refs.create_dataset(name, shape=(len(value), 1), dtype=h5py.ref_dtype)
            dataset.attrs["MATLAB_class"] = np.bytes_("cell")
            for i, child in enumerate(value):
                dataset[i, 0] = self.value(child).ref
            return dataset
        native = np.asarray(value)
        if native.ndim == 0:
            native = native.reshape(1, 1)
        if native.dtype.kind == "b":
            dataset = self.refs.create_dataset(name, data=native.astype("u1").T)
            dataset.attrs["MATLAB_class"] = np.bytes_("logical")
        else:
            dataset = self.refs.create_dataset(name, data=native.astype("f8").T)
            dataset.attrs["MATLAB_class"] = np.bytes_("double")
        return dataset

    def struct(self, name, rows):
        group = self.h.create_group(name)
        group.attrs["MATLAB_class"] = np.bytes_("struct")
        for key in rows[0]:
            dataset = group.create_dataset(key, shape=(len(rows), 1), dtype=h5py.ref_dtype)
            for i, row in enumerate(rows):
                dataset[i, 0] = self.value(row[key]).ref
        return group


def write_mat(path, document):
    with h5py.File(path, "w", userblock_size=512) as h:
        w = MatFixtureWriter(h)
        for name, rows in document.items():
            w.struct(name, rows)
        # This intentionally inaccessible unused signal field must not be read
        # by metadata-only inspection.
        h["R"]["events"] = h5py.SoftLink("/not-present-unused-events")
    with path.open("r+b") as f:
        f.write(b"MATLAB 7.3 MAT-file, generated independent fixture".ljust(128, b" "))
    charge(path)


def make_manifest(root):
    recipe = {"target_field": "jointAngles", "feature_variant": "smoothed_deconvolved_events",
              "window_ms": [-100, 400], "grid_step_ms": 10,
              "cell_budget": 2, "pca_components": 1, "ridge_alpha": 1., "split_seed": 240926,
              "limits": {"max_total_timepoints": 4000, "max_rois_per_session": 2, "max_trials_per_session": 7}}
    entries = []
    for i, sid in enumerate(P.SESSIONS):
        path = root / (sid + ".mat")
        write_mat(path, fixture_document(sid))
        provenance = {key: hashlib.sha256((sid + key).encode()).hexdigest() for key in A.PROVENANCE}
        provenance["source_asset_sha256"] = pin(path)["sha256"]
        entries.append(dict(pin(path), session_id=sid, original_trial_numbers=ORIGINAL,
                            excluded_unlocked_trial_numbers=[44], upstream_temporal_support_ms=[-200, 900],
                            provenance=provenance))
    return {"schema": "calcium_locked_mat73_manifest_v1", "author_commit": P.AUTHOR_COMMIT,
            "recipe": recipe, "io_limits": {"max_file_bytes": 1024 * 1024,
                                            "max_decoded_elements_per_file": 40000,
                                            "max_raw_report_bytes": 100000}, "sessions": entries}


class AdmissionControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = os.environ.get("CALCIUM_CONTROL_TMP")
        cls.temp = tempfile.TemporaryDirectory(prefix="calcium-admission-controls-", dir=base)
        cls.root = Path(cls.temp.name)
        cls.manifest = make_manifest(cls.root)
        cls.sid = next(iter(P.SESSIONS))
        cls.raw_manifest = {"schema": "calcium_raw_mat73_manifest_v1", "author_commit": P.AUTHOR_COMMIT,
                            "limits": {"max_file_bytes": 1024 * 1024,
                                       "max_decoded_elements_per_file": 10000, "max_trials_per_session": 8},
                            "sessions": copy.deepcopy(cls.manifest["sessions"])}
        cls.generated_assets = {e["session_id"]: {"filename": e["path"], "bytes": e["bytes"],
                                "published_md5": hashlib.md5((cls.root / e["path"]).read_bytes()).hexdigest(),
                                "figshare_file_id": i}
                               for i, e in enumerate(cls.raw_manifest["sessions"])}
        # Only the expected metadata map is patched for the invented corpus;
        # the actual file hashing, HDF5 reader and scalar eligibility run unchanged.
        with patch.object(A, "primary_assets", return_value=cls.generated_assets):
            report = A.inspect_raw(cls.raw_manifest, cls.root)
        raw_report = cls.root / "generated-raw-inspection.json"
        raw_report.write_bytes(A.canonical(report))
        charge(raw_report)
        cls.manifest["raw_inspection"] = pin(raw_report)
        cls.normalized = A.normalize_locked(cls.manifest, cls.root)

    @classmethod
    def tearDownClass(cls):
        # The full corpus is deliberately generated once, shared read-only, and
        # removed after tests. Written-byte accounting survives in stdout.
        source_end = hashlib.sha256((HERE / "admission.py").read_bytes()).hexdigest()
        print(json.dumps({"independent_fixture_bytes_written": WRITTEN,
                          "fixture_budget_bytes": BUDGET, "authentic_arrays_read": 0,
                          "source_start_sha256": SOURCE_START_SHA256, "source_end_sha256": source_end,
                          "python": sys.version, "numpy": np.__version__, "h5py": h5py.__version__}))
        cls.temp.cleanup()
        if source_end != SOURCE_START_SHA256:
            raise RuntimeError("Production source changed during controls")

    def test_complete_original_axes_values_and_trial_ids(self):
        result = self.normalized
        self.assertEqual(len(result["dataset"]["sessions"]), 10)
        self.assertEqual(result["receipt"]["complete_mice"], 5)
        for source, normalized, receipt in zip(self.manifest["sessions"], result["dataset"]["sessions"], result["receipt"]["sessions"]):
            self.assertEqual(receipt["original_trial_numbers"], ORIGINAL)
            self.assertEqual(receipt["included_trial_numbers"], ORIGINAL[:-1])
            self.assertEqual(receipt["selected_source_rows_zero_based"], list(range(10, 61)))
            self.assertEqual(receipt["excluded_trials"], [{"original_trial_number": 44, "reason": "both_native_lock_flags_false"}])
            self.assertEqual(len(normalized["trials"]), 6)
            self.assertEqual(normalized["trials"][0]["trial_id"], source["session_id"] + ":trial-2")
            self.assertEqual(normalized["trials"][0]["neural"][0], [-8., 9.])
            self.assertEqual(normalized["trials"][0]["targets"][0], [-10.5 + i for i in range(24)])
            self.assertEqual(normalized["trials"][0]["neural_time_ms"], list(range(-100, 401, 10)))
            self.assertEqual(len(normalized["trials"][0]["targets"]), 51)
            self.assertFalse(result["receipt"]["scientific_qualification"])

    def test_normalized_output_runs_existing_complete_scorer(self):
        result = self.normalized
        data = {s["session_id"]: {t["trial_id"]: t["targets"] for t in s["trials"]} for s in result["dataset"]["sessions"]}
        predictions = {s["session_id"]: {t: data[s["session_id"]][t] for t in s["evaluation_trial_ids"]}
                       for s in result["protocol"]["sessions"]}
        score = P.score_predictions(result["dataset"], result["protocol"], predictions,
                                    expected_protocol_sha256=result["protocol_sha256"])
        self.assertEqual(score["mouse_macro_nrmse"], 0.)
        self.assertEqual(score["mouse_macro_r_squared_per_joint"], [1.] * 24)
        self.assertEqual(score["support"]["evaluation_trials"], 20)
        self.assertFalse(score["verification"]["scientific_qualification"])

    def test_context_original_lr_split_census_and_source_fields(self):
        result = self.normalized
        for context, protocol in zip(result["context"]["sessions"], result["protocol"]["sessions"]):
            self.assertEqual([t["original_trial_number"] for t in context["trials"]], ORIGINAL[:-1])
            self.assertEqual([t["reach_target"] for t in context["trials"]], ["left", "right"] * 3)
            self.assertEqual(len(protocol["training_trial_ids"]), 4)
            self.assertEqual(len(protocol["evaluation_trial_ids"]), 2)
            self.assertEqual(set(protocol["training_trial_ids"]) | set(protocol["evaluation_trial_ids"]), set(protocol["all_trial_ids"]))
            self.assertEqual(protocol["native_neural_field"], "data")
        self.assertEqual(result["protocol_sha256"], P.digest(result["protocol"]))

    def test_raw_complete_census_and_unused_signal_not_read(self):
        with patch.object(A, "primary_assets", return_value=self.generated_assets):
            result = A.inspect_raw(self.raw_manifest, self.root)
        self.assertEqual(len(result["sessions"]), 10)
        for row in result["sessions"]:
            self.assertEqual(row["selected_trial_numbers"], ORIGINAL)
            self.assertEqual(row["ordered_original_trials"][-1]["exclusion_reasons"], ["unsuccessful"])
            self.assertLess(row["decoded_elements"], 10000)
        self.assertFalse(result["clock_alignment_qualified"])

    def test_raw_exact_thresholds_nan_and_multicause(self):
        rows = fixture_document(self.sid)["R"]
        rows[0].update(grabTimeC=np.nan, liftRT=500., goodDLC=False, wrongZoneFirst=True,
                       movementTime=500., timeToContact=1000., has_radical=False)
        result = A.raw_census(rows, self.sid, P)
        self.assertEqual(result["ordered_original_trials"][0]["exclusion_reasons"],
                         ["grabTimeC_nan", "liftRT_not_below_500", "movementTime_not_below_500",
                          "timeToContact_not_below_1000", "goodDLC_false", "wrongZoneFirst_true", "has_radical_false"])
        self.assertEqual(result["selected_trial_numbers"], ORIGINAL[1:])

    def test_raw_malformed_domain_refuses_entire_census(self):
        for field, value in (("trialNumber", 0), ("trialNumber", 2**53+1), ("success", 2),
                             ("grabTimeC", np.inf), ("liftRT", -np.inf), ("animalID", "cfaVG1"),
                             ("date", "20210101")):
            with self.subTest(field=field, value=value):
                rows = fixture_document(self.sid)["R"]
                rows[0][field] = value
                with self.assertRaises((A.Refusal, ValueError)):
                    A.raw_census(rows, self.sid, P)

    def test_raw_duplicate_trials_refused(self):
        rows = fixture_document(self.sid)["R"]
        rows[1]["trialNumber"] = rows[0]["trialNumber"]
        with self.assertRaisesRegex(A.Refusal, "Duplicate"):
            A.raw_census(rows, self.sid, P)

    def test_complete_session_manifest_missing_duplicate_and_extra(self):
        for mutation in (lambda m: m["sessions"].pop(),
                         lambda m: m["sessions"].append(copy.deepcopy(m["sessions"][0])),
                         lambda m: m["sessions"][0].update(session_id="cfaVG1_20210305_153354")):
            with self.subTest(mutation=mutation):
                m = copy.deepcopy(self.manifest)
                mutation(m)
                with self.assertRaises((A.Refusal, ValueError)):
                    A.normalize_locked(m, self.root)

    def test_actual_normalize_cli_private_output_and_no_overwrite(self):
        manifest = self.root / "request.json"
        manifest.write_bytes(A.canonical(self.manifest))
        charge(manifest)
        out = self.root / "result.json"
        cmd = [sys.executable, "-B", str(HERE / "admission.py"), "normalize-locked", "--manifest", str(manifest),
               "--expected-manifest-sha256", hashlib.sha256(manifest.read_bytes()).hexdigest(),
               "--input-root", str(self.root), "--output", str(out), "--max-manifest-bytes", "100000",
               "--max-output-bytes", "2000000"]
        run = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr)
        charge(out)
        result = json.loads(out.read_bytes())
        self.assertEqual(result["normalized_input_sha256"], self.normalized["normalized_input_sha256"])
        self.assertEqual(out.stat().st_mode & 0o777, 0o600)
        first = out.read_bytes()
        repeated = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(repeated.returncode, 0)
        self.assertEqual(out.read_bytes(), first)

    def test_actual_raw_cli_refuses_counterfeit_published_source_and_bad_pin(self):
        manifest = self.root / "raw-request.json"
        manifest.write_bytes(A.canonical(self.raw_manifest))
        charge(manifest)
        out = self.root / "raw-result.json"
        cmd = [sys.executable, "-B", str(HERE / "admission.py"), "inspect-raw", "--manifest", str(manifest),
               "--expected-manifest-sha256", hashlib.sha256(manifest.read_bytes()).hexdigest(),
               "--input-root", str(self.root), "--output", str(out), "--max-manifest-bytes", "100000",
               "--max-output-bytes", "100000"]
        run = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 2, run.stderr)
        self.assertIn("published Figshare inventory", run.stderr)
        self.assertFalse(out.exists())
        cmd[cmd.index("--expected-manifest-sha256")+1] = "0" * 64
        bad = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        self.assertEqual(bad.returncode, 2)
        self.assertIn("pin mismatch", bad.stderr)

    def test_native_masks_identity_and_explicit_exclusion(self):
        for mutate in (lambda d, e: d["neurons"][0].update(locked=False),
                       lambda d, e: d["neurons"][0].update(trialNumber=99),
                       lambda d, e: d["kinematics"][0].update(trialNumber=0),
                       lambda d, e: e.update(excluded_unlocked_trial_numbers=[]),
                       lambda d, e: e.update(excluded_unlocked_trial_numbers=[2, 44])):
            with self.subTest(mutate=mutate):
                d, e = fixture_document(self.sid), copy.deepcopy(self.manifest["sessions"][0])
                mutate(d, e)
                with self.assertRaises((A.Refusal, ValueError)):
                    A.locked_session(d, e, self.manifest["recipe"], P)

    def test_grid_axes_joint_order_and_roi_width(self):
        cases = [lambda d: d["M"][0]["config"].update(tBase=20.),
                 lambda d: d["M"][0]["config"].update(smoothSD=50.),
                 lambda d: d["M"][0]["config"]["datasetInfo"].update(filename="wrong-source"),
                 lambda d: d["kinematics"][0].update(tPts=GRID + 1),
                 lambda d: d["M"][0].update(jointNames=list(reversed(P.JOINT_NAMES))),
                 lambda d: d["neurons"][0].update(data=d["neurons"][0]["data"].T),
                 lambda d: d["kinematics"][0].update(jointAngles=d["kinematics"][0]["jointAngles"].T),
                 lambda d: d["M"][0].update(ROILags=np.array([0., 1., 2.])),
                 lambda d: d["kinematics"][0].update(eventName="grabTimeC")]
        for mutate in cases:
            with self.subTest(mutate=mutate):
                d = fixture_document(self.sid)
                mutate(d)
                with self.assertRaises((A.Refusal, ValueError)):
                    A.locked_session(d, self.manifest["sessions"][0], self.manifest["recipe"], P)

    def test_nonfinite_matrices_and_bool_targets_refuse(self):
        for which, value in (("neural", np.nan), ("target", np.inf), ("target", True)):
            with self.subTest(which=which, value=value):
                d = fixture_document(self.sid)
                if which == "neural":
                    d["neurons"][0]["data"][0, 0] = value
                elif value is True:
                    d["kinematics"][0]["jointAngles"] = np.ones((101, 24), dtype=bool)
                else:
                    d["kinematics"][0]["jointAngles"][0, 0] = value
                with self.assertRaises((A.Refusal, ValueError)):
                    A.locked_session(d, self.manifest["sessions"][0], self.manifest["recipe"], P)

    def test_velocity_is_separate_and_radical_native_route_refuses(self):
        d = fixture_document(self.sid)
        for k, n in zip(d["kinematics"], d["neurons"]):
            k["jointVelocities"] = k.pop("jointAngles") * 2
        recipe = copy.deepcopy(self.manifest["recipe"])
        recipe.update(target_field="jointVelocities")
        data, _, _ = A.locked_session(d, self.manifest["sessions"][0], recipe, P)
        self.assertEqual(data["native_neural_field"], "data")
        self.assertEqual(data["trials"][0]["neural"][0], [-8., 9.])
        self.assertEqual(data["trials"][0]["targets"][0][0], -21.)
        manifest = copy.deepcopy(self.manifest)
        manifest["recipe"]["feature_variant"] = "radical"
        with self.assertRaisesRegex(A.Refusal, "RADICaL native admission held"):
            A.normalize_locked(manifest, self.root)

    def test_raw_report_complete_roster_census_source_and_roi_bindings(self):
        original = json.loads((self.root / self.manifest["raw_inspection"]["path"]).read_bytes())
        mutations = [lambda r: r.update(published_asset_checksums_matched=False),
                     lambda r: r["sessions"].pop(),
                     lambda r: r["sessions"][0].update(source_sha256="0" * 64),
                     lambda r: r["sessions"][0].update(selected_trial_numbers=ORIGINAL[:-1]),
                     lambda r: r["sessions"][0].update(roi_columns=1),
                     lambda r: r["sessions"][0].update(roilags_sha256="0" * 64)]
        path = self.root / "mutated-raw-report.json"
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                report = copy.deepcopy(original)
                mutate(report)
                path.write_bytes(A.canonical(report))
                charge(path)
                manifest = copy.deepcopy(self.manifest)
                manifest["raw_inspection"] = pin(path)
                with self.assertRaises((A.Refusal, ValueError)):
                    A.normalize_locked(manifest, self.root)

    def test_manifest_raw_receipt_digest_is_checked(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["raw_inspection"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(A.Refusal, "pin mismatch"):
            A.normalize_locked(manifest, self.root)

    def test_original_predecessor_source_pin(self):
        with patch.object(A, "PIPELINE_SHA256", "0" * 64):
            with self.assertRaisesRegex(A.Refusal, "source mismatch"):
                A.pipeline()

    def test_file_hash_size_budget_and_path_refusals(self):
        entry = self.manifest["sessions"][0]
        variants = [dict(entry, sha256="0"*64), dict(entry, bytes=entry["bytes"] + 1),
                    dict(entry, bytes=0), dict(entry, path="../outside.mat"),
                    dict(entry, path=str(self.root / entry["path"]))]
        for e in variants:
            with self.subTest(entry=e):
                with self.assertRaises((A.Refusal, OSError)):
                    A.opened_mat(self.root, e, self.manifest["io_limits"])
        with self.assertRaisesRegex(A.Refusal, "budget"):
            A.opened_mat(self.root, entry, dict(self.manifest["io_limits"], max_file_bytes=1))

    def test_symlink_and_hardlink_sources_refused(self):
        entry = self.manifest["sessions"][0]
        link = self.root / "alias.mat"
        link.symlink_to(self.root / entry["path"])
        try:
            with self.assertRaisesRegex(A.Refusal, "Symlink"):
                A.opened_mat(self.root, dict(entry, path=link.name), self.manifest["io_limits"])
        finally:
            link.unlink()
        os.link(self.root / entry["path"], link)
        try:
            with self.assertRaisesRegex(A.Refusal, "single-link"):
                A.opened_mat(self.root, entry, self.manifest["io_limits"])
        finally:
            link.unlink()

    def test_source_change_during_open_detected(self):
        entry = self.manifest["sessions"][0]
        f, before = A.opened_mat(self.root, entry, self.manifest["io_limits"])
        try:
            wrong = tuple([*before[:3], before[3] + 1, before[4]])
            with self.assertRaisesRegex(A.Refusal, "changed"):
                A.stable(f, wrong)
        finally:
            f.close()

    def test_wrong_header_and_empty_file_refused(self):
        path = self.root / "wrong.mat"
        path.write_bytes(b"not MATLAB".ljust(520, b" "))
        charge(path)
        with self.assertRaisesRegex(A.Refusal, "MATLAB7.3"):
            A.opened_mat(self.root, pin(path), self.manifest["io_limits"])
        path.write_bytes(b"")
        with self.assertRaises(A.Refusal):
            A.opened_mat(self.root, pin(path), self.manifest["io_limits"])

    def test_decoded_element_and_record_limits_prevent_reads(self):
        path = self.root / self.manifest["sessions"][0]["path"]
        with h5py.File(path, "r") as h:
            with self.assertRaisesRegex(A.Refusal, "element limit"):
                A.Mat73(h, max_elements=1, max_records=8).read("R", A.RAW_FIELDS)
            with self.assertRaisesRegex(A.Refusal, "record limit"):
                A.Mat73(h, max_elements=10000, max_records=7).read("R", A.RAW_FIELDS)

    def test_external_and_soft_hdf5_links_refused(self):
        path = self.root / "links.h5"
        with h5py.File(path, "w") as h:
            h["external"] = h5py.ExternalLink("missing.h5", "/R")
            h["soft"] = h5py.SoftLink("/missing")
            reader = A.Mat73(h, max_elements=10, max_records=1)
            for name in ("external", "soft"):
                with self.subTest(name=name), self.assertRaises(A.Refusal):
                    reader.read(name, {"x": None})
        charge(path)

    def test_external_storage_and_virtual_dataset_refused(self):
        path = self.root / "external-storage.h5"
        with h5py.File(path, "w") as h:
            external = h.create_dataset("external", shape=(1, 1), dtype="f8", external=[("missing.bin", 0, 8)])
            external.attrs["MATLAB_class"] = np.bytes_("double")
            layout = h5py.VirtualLayout(shape=(1, 1), dtype="f8")
            layout[:] = h5py.VirtualSource("missing-source.h5", "value", shape=(1, 1))
            virtual = h.create_virtual_dataset("virtual", layout)
            virtual.attrs["MATLAB_class"] = np.bytes_("double")
            reader = A.Mat73(h, max_elements=10, max_records=1)
            for node in (external, virtual):
                with self.subTest(name=node.name), self.assertRaises(A.Refusal):
                    reader._leaf(node)
        charge(path)

    def test_null_and_region_references_refused(self):
        path = self.root / "refs.h5"
        with h5py.File(path, "w") as h:
            target = h.create_dataset("target", data=np.ones((2, 2)))
            target.attrs["MATLAB_class"] = np.bytes_("double")
            for name, dtype, value in (("null", h5py.ref_dtype, h5py.Reference()),
                                       ("region", h5py.regionref_dtype, target.regionref[0:1, 0:1])):
                g = h.create_group(name)
                g.attrs["MATLAB_class"] = np.bytes_("struct")
                ds = g.create_dataset("x", shape=(1, 1), dtype=dtype)
                ds[0, 0] = value
                reader = A.Mat73(h, max_elements=20, max_records=1)
                with self.subTest(name=name), self.assertRaises(A.Refusal):
                    reader.read(name, {"x": None})
        charge(path)

    def test_manifest_duplicate_keys_nonfinite_and_size(self):
        path = self.root / "bad-json.json"
        for body in (b'{"a":1,"a":2}', b'{"a":NaN}', b'[]', b'\xff'):
            path.write_bytes(body)
            charge(path)
            with self.subTest(body=body), self.assertRaises(A.Refusal):
                A.read_json(path, hashlib.sha256(body).hexdigest(), 100)
        body = b'{"a":1}'
        path.write_bytes(body)
        charge(path)
        with self.assertRaisesRegex(A.Refusal, "bounded|limit"):
            A.read_json(path, hashlib.sha256(body).hexdigest(), 2)

    def test_large_manifest_allowance_uses_bounded_reads(self):
        path = self.root / "tiny.json"
        body = b'{"a":1}'
        path.write_bytes(body)
        charge(path)
        self.assertEqual(A.read_json(path, hashlib.sha256(body).hexdigest(), 2**62), {"a": 1})

    def test_output_budget_and_existing_output_preservation(self):
        path = self.root / "bounded-output.json"
        with self.assertRaisesRegex(A.Refusal, "limit"):
            A.write_new(path, {"abc": "def"}, 1)
        self.assertFalse(path.exists())
        path.write_bytes(b"existing")
        charge(path)
        with self.assertRaises((A.Refusal, FileExistsError)):
            A.write_new(path, {"abc": "def"}, 100)
        self.assertEqual(path.read_bytes(), b"existing")


class PathBoundaryControls(unittest.TestCase):
    """Small targeted regressions for the shared path-admission extraction."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="calcium-path-controls-",
                                              dir=os.environ.get("CALCIUM_CONTROL_TMP"))
        self.base = Path(self.temp.name)
        self.root = self.base / "inputs"
        self.root.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    @classmethod
    def tearDownClass(cls):
        end = hashlib.sha256((HERE / "admission.py").read_bytes()).hexdigest()
        print(json.dumps({"path_control_bytes_written": WRITTEN,
                          "source_start_sha256": SOURCE_START_SHA256, "source_end_sha256": end}))
        if end != SOURCE_START_SHA256:
            raise RuntimeError("Production source changed during path controls")

    def test_shared_safe_path_accepts_pinned_mat_and_json(self):
        mat = self.root / "small.mat"
        mat.write_bytes(b"MATLAB 7.3 MAT-file".ljust(512, b" ") + b"\x89HDF\r\n\x1a\n")
        charge(mat)
        f, before = A.opened_mat(self.root, pin(mat), {"max_file_bytes": 1024})
        try:
            A.stable(f, before)
        finally:
            f.close()
        doc = self.root / "small.json"
        doc.write_bytes(b'{"ok":true}')
        charge(doc)
        path = A.safe_input_path(self.root, doc.name)
        self.assertEqual(A.read_json(path, pin(doc)["sha256"], 1024), {"ok": True})

    def test_raw_report_parent_symlink_is_refused_before_read(self):
        outside = self.base / "outside"
        outside.mkdir()
        report = outside / "raw.json"
        report.write_bytes(b"{}")
        charge(report)
        (self.root / "alias").symlink_to(outside, target_is_directory=True)
        manifest = {"schema": "calcium_locked_mat73_manifest_v1", "author_commit": P.AUTHOR_COMMIT,
                    "sessions": [{"session_id": s} for s in P.SESSIONS],
                    "recipe": {"target_field": "jointAngles", "feature_variant": "smoothed_deconvolved_events"},
                    "io_limits": {"max_raw_report_bytes": 1000},
                    "raw_inspection": {"path": "alias/raw.json", "sha256": pin(report)["sha256"]}}
        with self.assertRaisesRegex(A.Refusal, "Symlink"):
            A.normalize_locked(manifest, self.root)

    def test_shared_path_refuses_final_alias_absolute_and_parent(self):
        target = self.root / "target.json"
        target.write_bytes(b"{}")
        charge(target)
        (self.root / "alias.json").symlink_to(target)
        for rel in ("alias.json", "../target.json", str(target), ""):
            with self.subTest(rel=rel), self.assertRaises(A.Refusal):
                A.safe_input_path(self.root, rel)


if __name__ == "__main__":
    unittest.main(verbosity=2)
