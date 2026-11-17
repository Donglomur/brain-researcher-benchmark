import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

spec = importlib.util.spec_from_file_location("geometry", Path(__file__).resolve().parents[1] / "geometry.py")
geometry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geometry)


def fixture():
    rows = []
    for index, participant in enumerate(geometry.INCLUDED):
        # Unequal actual sensor counts distinguish participant from sensor weighting.
        distances = [0.01 + index * 0.0001, 0.02 + index * 0.0002]
        sensors = ["physical-A", "physical-B"]
        if index == 0:
            distances += [0.09]
            sensors += ["physical-C"]
        rows.append({"participant_id": participant, "age_years": 4 + index,
                     "head_circumference_source_value": 480 + 2 * index,
                     "actual": {"sensor_ids": sensors, "nearest_scalp_vertex_distances_m": distances},
                     "virtual": {"sensor_ids": ["physical-A", "physical-B"],
                                 "nearest_scalp_vertex_distances_m": [0.03 + index * 0.0003, 0.05 + index * 0.0002]}})
    return {"schema_version": 1, "task_id": geometry.TASK_ID,
            "source_revision": geometry.REVISION, "source_code_sha256": geometry.SOURCE_SHA256,
            "geometry_provenance": "Generated control only",
            "head_circumference_provenance": "Generated scalar, no MRI or physical-unit claim",
            "age_provenance": "Generated control only", "permutation_seed": 11,
            "reference_participant_id": "sub-126", "excluded_participants": list(geometry.EXCLUDED),
            "participants": rows}


class GeometryTests(unittest.TestCase):
    def test_native_channels_units_axis_and_matlab_order(self):
        channels = [{"name": "oneX", "Px": "100", "Py": "200", "Pz": "300"},
                    {"name": "oneY", "Px": "999", "Py": "999", "Pz": "999"},
                    {"name": "oneZ", "Px": "999", "Py": "999", "Pz": "999"}]
        affine = np.array([[0, -1, 0, .1], [1, 0, 0, .2], [0, 0, 1, .3], [0, 0, 0, 1]])
        ids, points = geometry.source_sensor_centers(channels, affine.reshape(-1, order="F"))
        self.assertEqual(ids, ["oneX"])
        np.testing.assert_allclose(points, [[-1.9, 1.2, 3.3]])
        np.testing.assert_allclose(geometry.source_sensor_centers(channels, affine)[1], points)

    def test_nearest_vertex_not_triangle_or_centroid(self):
        scalp = [[-1, -1, 0], [1, -1, 0], [0, 1, 0]]
        distances = geometry.nearest_vertex_distances([[0, 0, 1]], scalp)
        # Distance to the triangular face is 1; the source vertex metric is sqrt(2).
        np.testing.assert_allclose(distances, [np.sqrt(2)])

    def test_geometry_rigid_translation_invariance(self):
        sensors = np.array([[1, 2, 3], [2, 3, 4]])
        scalp = np.array([[0, 0, 0], [1, 1, 1], [2, 2, 2]])
        before = geometry.nearest_vertex_distances(sensors, scalp)
        np.testing.assert_allclose(before, geometry.nearest_vertex_distances(sensors + [7, 8, 9], scalp + [7, 8, 9]))

    def test_full_panel_mean_units_and_all_four_fits(self):
        report = geometry.evaluate(fixture())
        self.assertEqual(len(report["participants"]), 51)
        self.assertEqual(report["participants"][0]["actual_sensor_count"], 3)
        self.assertAlmostEqual(report["participants"][0]["actual_mean_mm"], 40)
        self.assertEqual(len(report["panels"]), 4)
        self.assertEqual(report["paired_slope_control"]["permutations"], 10000)
        self.assertIsNone(report["paper_reproduction_score"])
        self.assertIsNone(report["paper_improvement_score"])
        expected = .25 / 2  # virtual mean increases .25 mm per 2 source head units.
        self.assertAlmostEqual(report["panels"]["virtual_vs_head_source_value"]["slope_mm_per_predictor_unit"], expected)

    def test_paired_slope_control_hand_derived_and_strict(self):
        masks = np.array([[False, False, False], [True, True, True], [False, False, True], [True, False, False]])
        result = geometry.paired_slope_control([1, 2, 3], [0, 1, 4], [0, 0, 0], masks)
        np.testing.assert_allclose(result["null_slope_differences"], [2, -2, -2, 2])
        self.assertEqual(result["actual_minus_virtual_slope"], 2)
        self.assertEqual(result["upper_tail_fraction_strict"], 0)
        self.assertEqual(result["null_97_5_percentile_hazen"], 2)

    def test_permutation_mask_validation(self):
        with self.assertRaises(geometry.GeometryError):
            geometry.paired_slope_control([1, 2, 3], [1, 2, 3], [0, 0, 0], [[0, 1, 0]])

    def test_complete_panel_identity_and_virtual_sensor_support(self):
        for mutation in (lambda m: m["participants"].pop(),
                         lambda m: m["participants"][0].update(participant_id="sub-120"),
                         lambda m: m["participants"][0]["virtual"]["sensor_ids"].reverse(),
                         lambda m: m.update(reference_participant_id="sub-125"),
                         lambda m: m.update(excluded_participants=[])):
            manifest = fixture()
            mutation(manifest)
            with self.assertRaises(geometry.GeometryError):
                geometry.evaluate(manifest)

    def test_input_order_does_not_change_source_order_or_rng(self):
        manifest = fixture()
        report = geometry.evaluate(manifest)
        manifest["participants"].reverse()
        self.assertEqual(report, geometry.evaluate(manifest))

    def test_invalid_geometry_cannot_silently_drop_sensor(self):
        for points in ([], [[1, 2]], [[1, 2, float("nan")]]):
            with self.assertRaises(geometry.GeometryError):
                geometry.nearest_vertex_distances(points, [[0, 0, 0]])
        manifest = fixture()
        manifest["participants"][0]["actual"]["nearest_scalp_vertex_distances_m"][0] = -1
        with self.assertRaises(geometry.GeometryError):
            geometry.evaluate(manifest)

    def test_constant_distance_undefined_pearson_is_explicit(self):
        result = geometry.line_fit([1, 2, 3], [4, 4, 4])
        self.assertEqual(result["slope_mm_per_predictor_unit"], 0)
        self.assertIsNone(result["pearson_r"])
        with self.assertRaises(geometry.GeometryError):
            geometry.line_fit([1, 1, 1], [2, 3, 4])

    def test_cli_file_identity_and_strict_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / "input.json", Path(tmp) / "output.json"
            source.write_text(json.dumps(fixture()))
            with patch("sys.argv", ["geometry.py", str(source), str(output)]):
                geometry.main()
            result = json.loads(output.read_text())
            self.assertEqual(result["input_sha256"], geometry.hashlib.sha256(source.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
