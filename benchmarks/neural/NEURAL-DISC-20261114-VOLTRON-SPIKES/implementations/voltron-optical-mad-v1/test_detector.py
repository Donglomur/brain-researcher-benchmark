"""Generated complete-roster controls; no released optical/electrical data."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("voltron_mad_controls", Path(__file__).with_name("detector.py"))
D = importlib.util.module_from_spec(spec)
spec.loader.exec_module(D)


def fixture():
    cells = ["c" + str(i) for i in range(12)]
    public = {"schema": "voltron-native-frame-public/v1", "task_id": D.TASK,
              "profile": D.S.PROFILE, "release_manifest_sha256": "0" * 64,
              "cells": cells, "expected_subjects": 6, "movies": {}}
    optical = {"schema": "voltron-prepared-optical-traces/v1", "task_id": D.TASK,
               "public_sha256": "0" * 64, "preparation_sha256": "1" * 64, "movies": {}}
    for i in range(34):
        mid = "m" + str(i)
        public["movies"][mid] = {"cell_id": cells[i % 12], "fold_id": "f" + str(i % 12 // 2),
            "nominal_optical_rate_hz": 400 if i % 2 else 1000,
            "start_time": 0, "end_time": [1, 20],
            "frame_times": [[j, 1000] for j in (0, 1, 3, 4, 9, 10)],
            "input_disposition": "ready", "optical_valid_intervals": [[0, [1, 20]]],
            "cores": [{"core_id": mid + "a", "start_frame": 0, "end_frame": 3},
                      {"core_id": mid + "b", "start_frame": 3, "end_frame": 6}]}
        optical["movies"][mid] = {"samples": [0, 5, 0, 4, 0, 0],
            "amplitude_unit": "delta_f_over_f", "indicator_polarity": 1,
            "exposure_seconds": [1, 2000]}
    calibration = {"schema": "voltron-optical-mad-calibration/v1", "task_id": D.TASK,
                   "public_sha256": "0" * 64, "folds": {}}
    for i in range(6):
        calibration["folds"]["f" + str(i)] = {
            "training_cells": [c for j, c in enumerate(cells) if j // 2 != i],
            "fit_sha256": "2" * 64, "amplitude_unit": "delta_f_over_f",
            "indicator_polarity": 1, "center": 0, "mad": 1,
            "threshold_mads": 3, "refractory_seconds": [3, 1000]}
    bind(public, optical, calibration)
    return public, optical, calibration


def bind(public, optical, calibration):
    optical["public_sha256"] = calibration["public_sha256"] = D.S.identity(public)


def selected(result, mid="m0"):
    return result["role"]["cores"][mid + "a"] + result["role"]["cores"][mid + "b"]


class DetectorControls(unittest.TestCase):
    def test_complete_role_enters_existing_scorer_without_private_access(self):
        public, optical, calibration = fixture()
        result = D.produce(public, optical, calibration)
        self.assertEqual((result["movie_count"], result["frame_count"], result["event_count"]), (34, 204, 68))
        self.assertEqual(len(result["role"]["cores"]), 68)
        predictions = {"schema": "voltron-native-frame-predictions/v1", "task_id": D.TASK,
                       "public_sha256": D.S.identity(public),
                       "roles": {role: copy.deepcopy(result["role"]) for role in D.S.ROLES}}
        captured, _ = D.S.capture_predictions(predictions, D.S.public_contract(public))
        self.assertEqual(captured["optical_mad"]["m0"], (1, 3))
        self.assertFalse(result["scientific_qualified"])
        self.assertFalse(result["calibration_fitted"])
        self.assertFalse(result["physical_clock_authenticity_established"])

    def test_exact_refractory_boundary_and_nonuniform_clock(self):
        public, optical, calibration = fixture()
        # Peaks at native1ms and4ms: equality is admitted, regardless of nominal rate.
        self.assertEqual(selected(D.produce(public, optical, calibration)), [1, 3])
        calibration["folds"]["f0"]["refractory_seconds"] = [3001, 1000000]
        self.assertEqual(selected(D.produce(public, optical, calibration)), [1])
        public["movies"]["m0"]["nominal_optical_rate_hz"] = 400
        bind(public, optical, calibration)
        self.assertEqual(selected(D.produce(public, optical, calibration)), [1])

    def test_detection_is_whole_movie_before_core_assignment(self):
        public, optical, calibration = fixture()
        optical["movies"]["m0"]["samples"] = [0, 0, 4, 5, 0, 0]
        result = D.produce(public, optical, calibration)
        self.assertEqual(selected(result), [3])
        self.assertEqual(result["role"]["cores"]["m0a"], [])
        self.assertEqual(result["role"]["cores"]["m0b"], [3])

    def test_flat_maximum_is_earliest_original_frame(self):
        public, optical, calibration = fixture()
        optical["movies"]["m0"]["samples"] = [0, 0, 5, 5, 0, 0]
        self.assertEqual(selected(D.produce(public, optical, calibration)), [2])

    def test_positive_validity_gap_resets_refractory_without_intermediate_frame(self):
        public, optical, calibration = fixture()
        public["movies"]["m0"]["optical_valid_intervals"] = [[0, [7, 2000]], [[15, 4000], [1, 20]]]
        calibration["folds"]["f0"]["refractory_seconds"] = [1, 10]
        bind(public, optical, calibration)
        self.assertEqual(selected(D.produce(public, optical, calibration)), [1, 3])

    def test_invalid_values_do_not_set_scale_or_form_peaks(self):
        public, optical, calibration = fixture()
        public["movies"]["m0"]["optical_valid_intervals"] = [[0, [3, 1000]], [[4, 1000], [1, 20]]]
        optical["movies"]["m0"]["samples"][2] = 1000000000
        bind(public, optical, calibration)
        self.assertEqual(selected(D.produce(public, optical, calibration)), [1, 3])

    def test_query_drift_does_not_refit_center_or_mad(self):
        public, optical, calibration = fixture()
        optical["movies"]["m0"]["samples"] = [0] * 6
        self.assertEqual(selected(D.produce(public, optical, calibration)), [])
        optical["movies"]["m0"]["samples"] = [100] * 6
        # Frozen center0/MAD1 makes this plateau supra-threshold; no query recentering.
        self.assertEqual(selected(D.produce(public, optical, calibration)), [0])
        self.assertEqual(calibration["folds"]["f0"]["center"], 0)
        self.assertEqual(calibration["folds"]["f0"]["mad"], 1)

    def test_explicit_negative_polarity_and_nonzero_center(self):
        public, optical, calibration = fixture()
        for trace in optical["movies"].values():
            trace["samples"] = [10 - value for value in trace["samples"]]
            trace["indicator_polarity"] = -1
        for row in calibration["folds"].values():
            row.update(center=10, indicator_polarity=-1)
        self.assertEqual(selected(D.produce(public, optical, calibration)), [1, 3])

    def test_failed_extraction_stays_in_complete_output_with_empty_cores(self):
        public, optical, calibration = fixture()
        public["movies"]["m0"].update(input_disposition="optical_extraction_failed", optical_valid_intervals=[])
        optical["movies"]["m0"]["samples"] = [None] * 6
        bind(public, optical, calibration)
        result = D.produce(public, optical, calibration)
        self.assertEqual(selected(result), [])
        self.assertEqual(result["movie_count"], 34)
        self.assertEqual(result["frame_count"], 204)
        self.assertEqual(len(result["role"]["cores"]), 68)

    def test_zero_mad_and_invalid_explicit_parameters_refused(self):
        public, optical, calibration = fixture()
        for key, value in (("mad", 0), ("mad", -1), ("mad", float("nan")),
                           ("center", True), ("threshold_mads", 0),
                           ("refractory_seconds", [-1, 1000])):
            changed = copy.deepcopy(calibration)
            changed["folds"]["f0"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(D.CalibrationError):
                D.produce(public, optical, changed)

    def test_calibration_must_exclude_query_cells_and_cover_training_roster(self):
        public, optical, calibration = fixture()
        for mutation in (lambda row: row["training_cells"].append("c0"),
                         lambda row: row["training_cells"].pop(),
                         lambda row: row["training_cells"].append("c2"),
                         lambda row: row.update(fit_sha256="not-a-hash")):
            changed = copy.deepcopy(calibration)
            mutation(changed["folds"]["f0"])
            with self.assertRaises(D.CalibrationError):
                D.produce(public, optical, changed)
        del calibration["folds"]["f5"]
        with self.assertRaises(D.CalibrationError):
            D.produce(public, optical, calibration)

    def test_mixed_units_or_polarity_cannot_use_pooled_calibration(self):
        public, optical, calibration = fixture()
        for key, value in (("amplitude_unit", "raw_fluorescence"), ("indicator_polarity", -1)):
            changed = copy.deepcopy(optical)
            changed["movies"]["m33"][key] = value
            with self.subTest(key=key), self.assertRaises(D.CalibrationError):
                D.produce(public, changed, calibration)

    def test_event_ceiling_refuses_instead_of_truncating(self):
        public, optical, calibration = fixture()
        old = D.S.MAX_EVENTS
        try:
            D.S.MAX_EVENTS = 1
            with self.assertRaisesRegex(D.CalibrationError, "never truncate"):
                D.produce(public, optical, calibration)
        finally:
            D.S.MAX_EVENTS = old

    def test_cli_writes_once_and_rejects_duplicate_json(self):
        public, optical, calibration = fixture()
        with tempfile.TemporaryDirectory(prefix="voltron-generated-") as temp:
            base = Path(temp)
            argv = []
            for flag, value in (("public", public), ("optical", optical), ("calibration", calibration)):
                path = base / (flag + ".json")
                path.write_text(json.dumps(value))
                argv.extend(["--" + flag, str(path)])
            out = base / "predictions.json"
            argv.extend(["--output", str(out)])
            D.main(argv)
            self.assertEqual(json.loads(out.read_text())["event_count"], 68)
            with self.assertRaises(FileExistsError):
                D.main(argv)
            duplicate = base / "duplicate.json"
            duplicate.write_text('{"a":1,"a":2}')
            with self.assertRaisesRegex(ValueError, "duplicate"):
                D._read_json(duplicate)


if __name__ == "__main__":
    unittest.main(verbosity=1)
