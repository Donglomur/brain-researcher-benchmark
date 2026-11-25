"""Generated full-panel regression for a fixed-neural contrast; no real data."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("neural026_fixed_neural_score", HERE / "score.py")
score = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score)


class FixedNeuralContrast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.temp.name).resolve() / "candidate"
        cls.folder.mkdir()
        cls.api = score.backend()
        cls.design = {"schema": "neural026_design_v1", "cases": []}
        manifest = {"schema": score.NEW_SCHEMA, "cases": []}
        cls.targets = {}
        for mouse in cls.api.p.MICE:
            for area in cls.api.p.AREAS:
                for fold in range(5):
                    cid = f"{mouse}_{area}_fold{fold}"
                    query = [i for i in range(1, 21) if (i - 1) % 5 == fold]
                    cls.design["cases"].append({"case_id": cid, "mouse": mouse,
                        "area": area, "fold": fold, "query_id": query,
                        "train_id": [i for i in range(1, 21) if i not in query],
                        "matched_counts": {"1": 10, "2": 10}})
                    ids = np.asarray(query, dtype=np.int64)
                    y = np.broadcast_to(ids[:, None, None], (4, 51, 24)).astype(np.float64)
                    cls.targets[cid] = {"trial_id": ids, "y": y}
                    path = cls.folder / (cid + ".npz")
                    np.savez_compressed(path, trial_id=ids, neural=y + .5)
                    raw = path.read_bytes()
                    manifest["cases"].append({"case_id": cid, "file": path.name,
                        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        (cls.folder / "submission.json").write_text(json.dumps(manifest))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def evaluate(self, *, nuisance_offset, fixed_neural_offset):
        def private(cid):
            target = self.targets[cid]
            y = target["y"]
            return target, {"trial_id": target["trial_id"],
                "nuisance": y + nuisance_offset,
                "neural": y + fixed_neural_offset, "shifted": y + 2.}
        result = score.evaluate(self.folder, self.design, private)
        self.assertEqual(result["complete_cases"], 50)
        self.assertEqual(result["independent_mice"], 5)
        self.assertEqual(len(result["biological_effects"]), 10)
        self.assertFalse(result["scientific_qualification"])
        self.assertFalse(result["neural_dependence_established"])
        return result

    def assert_contrast(self, result, expected):
        # Every joint contains each integer1..20 equally often, hence variance
        # (20**2 - 1)/12 =33.25. Errors are constant and independently known.
        for row in result["biological_effects"]:
            values = row["candidate_minus_fixed_neural_incremental_ev"]
            self.assertEqual(len(values), 24)
            np.testing.assert_allclose(values, expected, rtol=1e-14, atol=0.)

    def test_large_nuisance_preserves_real_positive_fixed_neural_difference(self):
        result = self.evaluate(nuisance_offset=1e10, fixed_neural_offset=1.)
        self.assert_contrast(result, .75 / 33.25)
        self.assertAlmostEqual(result["primary_value"] / 1e20, 1. / 33.25)

    def test_large_nuisance_preserves_negative_fixed_neural_difference(self):
        result = self.evaluate(nuisance_offset=1e10, fixed_neural_offset=.25)
        self.assert_contrast(result, -.1875 / 33.25)

    def test_identical_fixed_neural_error_has_zero_difference(self):
        result = self.evaluate(nuisance_offset=1e10, fixed_neural_offset=.5)
        self.assert_contrast(result, 0.)

    def test_ordinary_scale_contrast_and_primary_are_preserved(self):
        result = self.evaluate(nuisance_offset=3., fixed_neural_offset=1.)
        self.assert_contrast(result, .75 / 33.25)
        self.assertAlmostEqual(result["primary_value"], 8.75 / 33.25)
        for row in result["biological_effects"]:
            np.testing.assert_allclose(row["joint_incremental_ev"], 8.75 / 33.25)
            np.testing.assert_allclose(row["fixed_neural_joint_incremental_ev"], 8. / 33.25)


if __name__ == "__main__":
    unittest.main()
