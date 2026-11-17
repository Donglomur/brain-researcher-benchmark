"""Generated numerical controls only; no authentic observations or model calls."""
import ast
import collections
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import torch
from scipy.stats import pearsonr

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("behavior_truth", HERE / "behavior_truth.py")
truth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(truth)
RUNTIME = SimpleNamespace(np=np, torch=torch, pearsonr=pearsonr)
HISTORICAL = "released_computational_path_10ms"
PROTECTED = "protected_support_source_amended_10ms"
CASE = "lateral--joint_speed_gaze--neuroformer--100"


def row(index):
    return {"id": "generated-row-" + str(index), "recording": "generated-recording",
            "end_tick": index * 5, "recording_ticks": 1300}


def fixture(root, *, column=False, condition=HISTORICAL, count=205):
    def descriptor(path):
        body = (root / path).read_bytes()
        return {"path": path, "bytes": len(body), "sha256": truth.digest(body)}
    (root / "study.json").write_text('{"generated_control":true}')
    (root / "provenance.json").write_text('{"generated_control":true}')
    assets = {}
    for i, mode in enumerate(truth.MODES):
        path = {"speed": "behavior_speed_dt_0.05.npy", "phi": "phi_dt_0.05.npy", "th": "th_dt_0.05.npy"}[mode]
        # Nonlinear, nonperiodic deterministic values distinguish index shifts.
        values = (np.arange(260, dtype=np.float64) + .123456789) ** (1 + i / 3)
        if column:
            values = values[:, None]
        np.save(root / path, values, allow_pickle=False)
        assets[mode] = {**descriptor(path), "dtype": "<f8", "shape": list(values.shape)}
    start = 20 if condition == PROTECTED else 0
    evaluation = [row(i) for i in range(start, start + count)]
    support = {"train": [row(250 if condition == HISTORICAL else 0)],
               "selection": copy.deepcopy(evaluation) if condition == HISTORICAL else [row(5)],
               "evaluation": evaluation}
    return {"schema": "neuroformer_behavior_truth_v1", "study": descriptor("study.json"),
            "recordings": {"generated-recording": {"cohort": "lateral", "recording_ticks": 1300,
                "assets": assets, "provenance": descriptor("provenance.json")}},
            "cells": [{"case_id": CASE, "condition": condition, "support": support}],
            "limits": {"max_input_bytes": 100000, "max_file_bytes": 20000, "max_rows": 1000, "max_values": 1000}}


def independent_original_targets(loaded, root, request):
    """Run original __getitem__ with inert neural leaves and real behavior arrays.

    This checks the real caller's current-window and target slicing choices, not
    merely another call to the new target issuer. Neural leaves are unused for
    the behavioral expected values and do not represent a neural observation.
    """
    body = loaded.bodies["source/public/official_code/neuroformer/data_utils.py"]
    ns, owner = truth._extractor(body, RUNTIME)
    tree = ast.parse(body)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "NFDataloader")
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__getitem__")
    ns["collections"] = collections
    ns["create_nested_defaultdict"] = lambda: collections.defaultdict(lambda: collections.defaultdict(dict))
    exec(compile(ast.Module(body=[method], type_ignores=[]), "original_getitem", "exec"), ns)
    rows = request["cells"][0]["support"]["evaluation"]
    owner.dataset = "lateral"
    owner.t = np.array([r["end_tick"] * .01 for r in rows])
    owner.calc_intervals = lambda interval: ns["calc_intervals"](owner, interval)
    owner.get_behavior = lambda *args, **kwargs: ns["get_behavior"](owner, *args, **kwargs)
    owner.get_interval = lambda *args: ([0, 1, 2], [0, 1, 2], 0)
    owner.id_block_size = owner.id_prev_block_size = 2
    owner.frames = None
    owner.modalities = {"behavior": {"variables": {
        mode: {"window": .05, "dt": .05, "objective": "regression", "predict": True,
               "data": np.load(root / desc["path"], allow_pickle=False)}
        for mode, desc in request["recordings"]["generated-recording"]["assets"].items()}}}
    values = {mode: [] for mode in truth.MODES}
    for index in range(len(rows)):
        x, y = ns["__getitem__"](owner, index)
        for mode in values:
            values[mode].append(float(y["modalities"]["behavior"][mode]["value"].reshape(-1)[0]))
    return values


class TruthControls(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="neuroformer-generated-truth-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_original_getitem_parity_all_modes_and_empty_first_slice(self):
        request = fixture(self.root)
        with truth.sources() as loaded:
            packets, receipt = truth._issue(request, loaded, self.root, RUNTIME)
            expected = independent_original_targets(loaded, self.root, request)
        self.assertEqual(packets[0]["values"], expected)
        self.assertEqual(expected["speed"][0], 0.0)
        self.assertEqual(len(receipt["extraction"][0]["empty_source_slices_retained"]), 3)
        raw = np.load(self.root / "behavior_speed_dt_0.05.npy")
        self.assertEqual(expected["speed"][1], float(np.float32(raw[0])))
        self.assertNotEqual(expected["speed"][1], float(raw[0]))

    def test_column_stream_source_failure_not_silently_flattened(self):
        request = fixture(self.root, column=True, count=2)
        with truth.sources() as loaded:
            with self.assertRaises(AssertionError):
                truth._issue(request, loaded, self.root, RUNTIME)
            with self.assertRaises(AssertionError):
                independent_original_targets(loaded, self.root, request)

    def test_column_stream_after_boundary_matches_original(self):
        request = fixture(self.root, column=True, condition=PROTECTED, count=4)
        with truth.sources() as loaded:
            packets, _ = truth._issue(request, loaded, self.root, RUNTIME)
            self.assertEqual(packets[0]["values"], independent_original_targets(loaded, self.root, request))

    def test_historical_first200_and_protected_full_support_unchanged(self):
        for condition in (HISTORICAL, PROTECTED):
            with self.subTest(condition=condition):
                request = fixture(self.root, condition=condition)
                with truth.sources() as loaded:
                    packets, _ = truth._issue(request, loaded, self.root, RUNTIME)
                original = copy.deepcopy(packets)
                for mode in truth.MODES:
                    packets[0]["values"][mode][-5:] = [-1e6] * 5
                report = truth.grade(packets, request, self.root, runtime=RUNTIME)
                n = 200 if condition == HISTORICAL else 205
                for mode in truth.MODES:
                    measured = report["rows"][0]["values"][mode]
                    expected = pearsonr(packets[0]["values"][mode][:n], original[0]["values"][mode][:n]).statistic
                    self.assertEqual(measured["n"], n)
                    self.assertEqual(measured["total_admitted_support"], 205)
                    self.assertAlmostEqual(measured["pearson_r"], expected)
                self.assertFalse(report["scientifically_qualified"])
                self.assertFalse(report["truth_issuance"]["target_values_returned"])

    def test_invalid_prediction_precedes_runtime_and_target_access(self):
        request = fixture(self.root, count=2)
        packets = [{"cell_id": CASE + "::" + HISTORICAL,
                    "row_ids": ["generated-row-0", "generated-row-1"],
                    "values": {m: [0.0, float("nan")] for m in truth.MODES}}]
        with patch.object(truth, "_native_runtime", side_effect=AssertionError("runtime opened")):
            with self.assertRaisesRegex(ValueError, "finite scalar"):
                truth.grade(packets, request, self.root / "missing-root")

    def test_all_cells_freeze_before_target_access(self):
        request = fixture(self.root, count=2)
        second = copy.deepcopy(request["cells"][0])
        second["case_id"] = "lateral--speed_regression--neuroformer--100"
        request["cells"].append(second)
        packets = [{"cell_id": CASE + "::" + HISTORICAL,
                    "row_ids": ["generated-row-0", "generated-row-1"],
                    "values": {m: [0.0, 1.0] for m in truth.MODES}},
                   {"cell_id": second["case_id"] + "::" + HISTORICAL,
                    "row_ids": ["wrong-row", "generated-row-1"], "values": {"speed": [0.0, 1.0]}}]
        with patch.object(truth, "_native_runtime", side_effect=AssertionError("runtime opened")):
            with self.assertRaisesRegex(ValueError, "ordered candidate"):
                truth.grade(packets, request, self.root / "missing-root")

    def test_changed_asset_hash_and_recording_extent_fail(self):
        request = fixture(self.root, count=2)
        desc = request["recordings"]["generated-recording"]["assets"]["speed"]
        (self.root / desc["path"]).write_bytes(b"x" * desc["bytes"])
        with truth.sources() as loaded:
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                truth._issue(request, loaded, self.root, RUNTIME)
            request["recordings"]["generated-recording"]["recording_ticks"] = 1295
            with self.assertRaisesRegex(ValueError, "complete original scalar stream"):
                truth.admit_request(request, loaded)

    def test_wrong_cohort_context_overlap_and_cell_rejected(self):
        request = fixture(self.root, condition=PROTECTED, count=2)
        with truth.sources() as loaded:
            for mutation, error in (("cohort", "cohort and full"), ("overlap", "contexts overlap"), ("cell", "native continuous")):
                bad = copy.deepcopy(request)
                if mutation == "cohort":
                    bad["recordings"]["generated-recording"]["cohort"] = "medial"
                elif mutation == "overlap":
                    bad["cells"][0]["support"]["selection"] = [row(19)]
                else:
                    bad["cells"][0]["case_id"] = "lateral--speed_classification--neuroformer--100"
                with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, error):
                    truth.admit_request(bad, loaded)


if __name__ == "__main__":
    unittest.main(verbosity=2)
