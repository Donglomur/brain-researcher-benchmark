"""Analytic generated controls; no neural data, fitted model or study run."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("fde", Path(__file__).with_name("fde.py"))
fde = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fde)


def fixture():
    observations = []
    for i in range(5):
        observations.append({"trial_id": "generated_trial_" + str(i), "frame_id": "frame_0",
            "fold_id": i + 1, "trial_type": i + 1, "activity": 0.5,
            "npvc": {"log_joint_grid": [0.0] * 200, "log_joint_observed": math.log(0.75),
                     "log_marginal_observed": math.log(0.25)},
            "glm": {"mean": 0.5, "null_mean": 1.0}})
    unit = {"identity": {"animal_id": "generated_mouse", "session_id": "generated_session",
                        "neuron_id": "generated_neuron", "projection": "unlabeled", "epoch": "sample"},
            "activity_bounds": [0.0, 1.0], "observations": observations}
    return {"schema": "npvc-fde-operands-v1", "units": [unit]}


class Equations(unittest.TestCase):
    def test_source_rectangle_integral_not_trapezoid_or_grid_spacing(self):
        # Joint density q(r)=r on [0,2]; the paper's rectangle sum is exactly 2.
        # Use q(r)=1+r to avoid zero log density: integral sum is exactly 4.
        grid, delta = fde.source_grid([0.0, 2.0])
        self.assertEqual((grid[0], grid[-1], delta), (0.0, 2.0, 0.01))
        p = fde.npvc_point([0.0, 2.0], [math.log(1 + x) for x in grid], math.log(2), math.log(0.5))
        self.assertAlmostEqual(p["model"], math.log(0.5), places=14)
        self.assertAlmostEqual(p["saturated"], math.log(0.75), places=14)
        self.assertEqual(p["mode_activity"], 2.0)
        self.assertNotEqual(delta, grid[1] - grid[0])
        # Quadratic q(r)=1+r^2 distinguishes the rectangular sum from trapezoids.
        expected_integral = 2 + 4 * 399 / (3 * 199)
        q = fde.npvc_point([0.0, 2.0], [math.log(1 + x*x) for x in grid], 0.0, -1.0)
        self.assertAlmostEqual(q["model"], -math.log(expected_integral), places=14)

    def test_joint_rescaling_cancels_without_exponentiating_large_logs(self):
        values = [math.log(i + 1) for i in range(200)]
        a = fde.npvc_point([0.0, 2.0], values, math.log(10), -2.0)
        for scale in (-10000.0, 10000.0):
            b = fde.npvc_point([0.0, 2.0], [v + scale for v in values], math.log(10) + scale, -2.0)
            for k in ("model", "null", "saturated"):
                self.assertAlmostEqual(a[k], b[k], places=10)

    def test_density_coordinate_change_preserves_fde(self):
        # y'=10y changes every conditional/marginal log density by -log(10).
        logs = [math.log(i + 1) for i in range(200)]
        a = fde.npvc_point([0.0, 2.0], logs, math.log(20), -2.0)
        scale = math.log(10)
        b = fde.npvc_point([0.0, 20.0], [v - scale for v in logs], math.log(20) - scale, -2.0 - scale)
        self.assertAlmostEqual(fde.fraction_deviance_explained([a])["fde"],
                               fde.fraction_deviance_explained([b])["fde"], places=13)

    def test_glm_matches_independent_poisson_deviance(self):
        ys, mus, nulls = [0.0, 0.4, 3.0, 8.0], [0.2, 0.7, 2.0, 7.0], [2.0] * 4
        points = [fde.glm_point(y, mu, null) for y, mu, null in zip(ys, mus, nulls)]
        def deviance(predictions):
            return 2 * sum((y * math.log(y / mu) if y else 0) - y + mu for y, mu in zip(ys, predictions))
        expected = 1 - deviance(mus) / deviance(nulls)
        self.assertAlmostEqual(fde.fraction_deviance_explained(points)["fde"], expected, places=13)
        self.assertEqual(fde.glm_point(0.0, 0.0, 1.0)["saturated"], 0.0)
        with self.assertRaisesRegex(fde.Invalid, "no pseudocount"):
            fde.glm_point(0.5, 0.0, 1.0)

    def test_ratio_after_sum_not_average_of_fold_fractions(self):
        points = [{"model": 0.0, "null": -1.0, "saturated": 0.0},
                  {"model": -9.0, "null": -9.0, "saturated": 0.0}]
        self.assertEqual(fde.fraction_deviance_explained(points)["fde"], 0.1)
        self.assertNotEqual(fde.fraction_deviance_explained(points)["fde"], 0.5)

    def test_zero_negative_and_above_one_are_never_silently_omitted(self):
        for point, expected, state in [({"model": 0.0, "null": 0.0, "saturated": 0.0}, None, "zero"),
                ({"model": -2.0, "null": -1.0, "saturated": 0.0}, -1.0, "positive"),
                ({"model": 1.0, "null": -1.0, "saturated": 0.0}, 2.0, "positive"),
                ({"model": 0.0, "null": 1.0, "saturated": 0.0}, 1.0, "negative")]:
            result = fde.fraction_deviance_explained([point])
            self.assertEqual((result["fde"], result["denominator_state"], result["observations"]), (expected, state, 1))

    def test_distinct_source_normalizers_and_tied_mode_audit(self):
        result = fde.score(fixture())["units"][0]
        self.assertAlmostEqual(result["npvc"]["fde"], math.log(3) / math.log(4))
        self.assertAlmostEqual(result["glm"]["fde"], 1.0)
        self.assertNotEqual(result["npvc"]["denominator"], result["glm"]["denominator"])
        self.assertEqual(result["npvc_predictions"][0]["mode_tie_count"], 200)
        self.assertEqual(result["npvc_predictions"][0]["mode_activity"], 0.0)
        self.assertEqual([f["fold_id"] for f in result["folds"]], [1, 2, 3, 4, 5])

    def test_identity_duplicate_and_numeric_boundary_refusals(self):
        document = fixture()
        document["units"][0]["observations"].append(copy.deepcopy(document["units"][0]["observations"][0]))
        with self.assertRaisesRegex(fde.Invalid, "duplicate trial/frame"):
            fde.score(document)
        document = fixture(); document["units"].append(copy.deepcopy(document["units"][0]))
        with self.assertRaisesRegex(fde.Invalid, "duplicate unit"):
            fde.score(document)
        for field, value in (("fold_id", True), ("trial_type", 9), ("activity", float("nan")), ("activity", 2.0)):
            document = fixture(); document["units"][0]["observations"][0][field] = value
            with self.assertRaises(fde.Invalid): fde.score(document)
        for bounds, values in (([0.0, 0.0], [0.0] * 200), ([0.0, 1.0], [0.0] * 199),
                              ([0.0, 1.0], [float("inf")] * 200)):
            with self.assertRaises(fde.Invalid): fde.npvc_point(bounds, values, 0.0, 0.0)

    def test_same_cell_epoch_metadata_must_agree(self):
        for change in ({"animal_id": "different_animal"}, {"projection": "different_projection"}):
            document = fixture(); second = copy.deepcopy(document["units"][0])
            second["identity"].update(epoch="delay", **change); document["units"].append(second)
            with self.assertRaises(fde.Invalid): fde.score(document)
        document = fixture(); second = copy.deepcopy(document["units"][0])
        second["identity"]["epoch"] = "delay"; second["activity_bounds"] = [0.0, 2.0]
        document["units"].append(second)
        with self.assertRaisesRegex(fde.Invalid, "bounds changed"): fde.score(document)

    def test_relocated_cli_and_no_overwrite_or_partial_invalid_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "fde.py"; source.write_bytes(Path(fde.__file__).read_bytes())
            inp = root / "input.json"; inp.write_text(json.dumps(fixture()))
            out = root / "output.json"
            command = [sys.executable, "-I", "-S", "-B", str(source), "--input", str(inp), "--output", str(out)]
            result = subprocess.run(command, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            previous = out.read_bytes()
            self.assertEqual(len(json.loads(previous)["units"]), 1)
            self.assertEqual(subprocess.run(command, capture_output=True, timeout=10).returncode, 2)
            self.assertEqual(out.read_bytes(), previous)
            out.unlink(); inp.write_text('{"schema":"npvc-fde-operands-v1","schema":"duplicate"}')
            result = subprocess.run(command, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
