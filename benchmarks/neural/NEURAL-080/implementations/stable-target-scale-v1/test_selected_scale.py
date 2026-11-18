"""Generated integration controls; no EEG, model fit, or native qualification."""
from decimal import Decimal, localcontext
import ast
import hashlib
import json
from pathlib import Path
import sys
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
PROGRAMME = HERE.parent / "neural-080" / "full-generalization"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PROGRAMME / "source"))
import legacy_rounded_scale
from generalization import models


class Owner:
    def __init__(self):
        self.bytes = 0

    def reserve(self, name, amount):
        if name != "retained_bytes" or type(amount) is not int or amount < 0:
            raise AssertionError("Unexpected logical reservation")
        self.bytes += amount


def example():
    values = np.array([0.1, np.nextafter(0.1, np.inf)], dtype=np.float64)
    return np.broadcast_to(values[:, None], (2, 127 * 150)).copy(), np.array([0.5, 0.5])


class Tests(unittest.TestCase):
    def test_selected_model_kernel_matches_independent_exact_moment(self):
        raw, weights = example()
        before = raw.copy()
        with localcontext() as context:
            context.prec = 150
            a, b = (Decimal(float(value)) for value in raw[:, 0])
            exact_sigma = float((b - a) / 2)
        scale, standardized = models.fit_target_scale(raw, weights, Owner())
        self.assertIs(type(scale), models.TargetScale)
        np.testing.assert_array_equal(scale.sigma, np.full(127 * 150, exact_sigma))
        np.testing.assert_array_equal(standardized * scale.sigma + scale.mean, raw)
        np.testing.assert_array_equal(raw, before)
        self.assertFalse(scale.mean.flags.writeable)
        self.assertFalse(scale.sigma.flags.writeable)

    def test_protected_reconstruction_accepts_matching_complete_capture(self):
        raw, weights = example()
        scale, _ = models.fit_target_scale(raw, weights, Owner())
        capture = {}

        class Writer:
            def array(self, name, values):
                capture[name] = values.copy()
                return {"path": name}

        models.capture_target_scale(scale, Writer(), "generated")
        owner = Owner()
        answer = models.verify_captured_target_scale(
            raw, weights, capture["generated.target_mean.npy"],
            capture["generated.target_sigma.npy"], owner)
        self.assertIsNone(answer)
        self.assertGreater(owner.bytes, raw.nbytes)

    def test_predecessor_sigma_is_rejected_instead_of_silently_rescored(self):
        raw, weights = example()
        old, _ = legacy_rounded_scale.fit_target_scale(raw, weights, Owner())
        with self.assertRaisesRegex(ValueError, "exact selected outer TRAIN-only transform"):
            models.verify_captured_target_scale(
                raw, weights, old.mean.reshape(127, 150), old.sigma.reshape(127, 150), Owner())

    def test_one_corrupt_or_incomplete_capture_refuses_whole_scale(self):
        raw, weights = example()
        scale, _ = models.fit_target_scale(raw, weights, Owner())
        mean, sigma = scale.mean.reshape(127, 150), scale.sigma.reshape(127, 150)
        variants = [sigma[:, :-1], sigma.astype(np.float32), sigma.tolist()]
        for value in (np.nan, np.inf, 0.0, np.nextafter(float(sigma[0, 0]), np.inf)):
            bad = sigma.copy()
            bad[81, 121] = value
            variants.append(bad)
        for bad in variants:
            with self.subTest(kind=type(bad).__name__, shape=getattr(bad, "shape", None)):
                with self.assertRaises(ValueError):
                    models.verify_captured_target_scale(raw, weights, mean, bad, Owner())

    def test_actual_reference_and_scorer_routes_share_selected_kernel(self):
        reference = ast.parse((PROGRAMME / "source/generalization/reference.py").read_text())
        outer = next(n for n in reference.body if isinstance(n, ast.FunctionDef) and n.name == "run_outer")
        calls = [n for n in ast.walk(outer) if isinstance(n, ast.Call) and
                 isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and
                 n.func.value.id == "models" and n.func.attr == "fit_target_scale"]
        self.assertEqual(len(calls), 2, "Both inner and outer reference scales must use the shared kernel")
        scoring = ast.parse((PROGRAMME / "source/generalization/scoring.py").read_text())
        compare = next(n for n in scoring.body if isinstance(n, ast.FunctionDef) and n.name == "compare")
        imports = [n for n in ast.walk(compare) if isinstance(n, ast.ImportFrom) and n.module == "models"]
        self.assertEqual(sum(a.name == "verify_captured_target_scale" for n in imports for a in n.names), 1)
        calls = [n for n in ast.walk(compare) if isinstance(n, ast.Call) and
                 isinstance(n.func, ast.Name) and n.func.id == "verify_captured_target_scale"]
        self.assertEqual(len(calls), 1)
        self.assertEqual([ast.unparse(n) for n in calls[0].args],
                         ["raw_targets", "weights", "mean", "sigma", "owner"])

    def test_changed_source_pins_and_api_positions_are_consistent(self):
        manifest = json.loads((PROGRAMME / "SOURCE_MANIFEST.json").read_text())
        api = json.loads((PROGRAMME / "SOURCE_API.json").read_text())
        resolution = json.loads((PROGRAMME / "INSTALLED_SOURCE_RESOLUTION.json").read_text())
        self.assertFalse(manifest["qualification"])
        self.assertFalse(resolution["scientific_qualification"])
        self.assertEqual(manifest["source_file_count"], 58)
        self.assertEqual(manifest["source_bytes"], sum(r["bytes"] for r in manifest["source_files"]))
        for path in ("source/generalization/models.py", "source/generalization/scoring.py"):
            body = (PROGRAMME / path).read_bytes()
            row = next(r for r in manifest["source_files"] if r["path"] == path)
            installed = next(r for r in resolution["files"] if r["installed_relative"] == path)
            for descriptor in (row, installed):
                self.assertEqual(descriptor["bytes"], len(body))
                self.assertEqual(descriptor["sha256"], hashlib.sha256(body).hexdigest())
            definitions = api["all_actual_definitions"][path]
            for node in ast.parse(body).body:
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    self.assertEqual(definitions[node.name]["line"], node.lineno)
                    self.assertEqual(definitions[node.name]["end_line"], node.end_lineno)
        for name, descriptor in (("SOURCE_MANIFEST.json", api["source_manifest"]),
                                 ("SOURCE_MANIFEST.json", resolution["source_manifest"]),
                                 ("SOURCE_API.json", resolution["source_api"])):
            body = (PROGRAMME / name).read_bytes()
            self.assertEqual(descriptor["bytes"], len(body))
            self.assertEqual(descriptor["sha256"], hashlib.sha256(body).hexdigest())


if __name__ == "__main__":
    unittest.main()
