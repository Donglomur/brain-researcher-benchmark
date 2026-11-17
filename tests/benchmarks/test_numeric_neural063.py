"""Generated controls for NEURAL063 FIT means; no scientific source data reads."""

from fractions import Fraction
import hashlib
import importlib
import json
import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "benchmarks/neural/NEURAL-063/implementations/neural-063/complete-omission-v1"
CLOSURE = ROOT / "benchmarks/integrity/current-closures/numeric-neural063/SOURCE.json"
TINY = math.ulp(0.0)


def load_arithmetic():
    """Import only the inspected pure arithmetic closure, without namespace leaks."""
    names = lambda name: name in ("owner", "references") or name.startswith(("owner.", "references."))
    saved = {name: module for name, module in sys.modules.items() if names(name)}
    old_path = list(sys.path)
    try:
        for name in saved:
            del sys.modules[name]
        sys.path.insert(0, str(PACKAGE))
        return tuple(importlib.import_module(name) for name in
                     ("references.controls", "owner.scoring", "references.schema"))
    finally:
        sys.path[:] = old_path
        for name in list(sys.modules):
            if names(name):
                del sys.modules[name]
        sys.modules.update(saved)


def row(i, split, values):
    prefix = f"invented-{split}-{i:03d}"
    return {
        "id": prefix, "mouse": prefix + "-m", "session": prefix + "-s",
        "experiment": prefix + "-e", "split": split,
        "previous": [{"image": "invented-a", "omitted": False,
                      "start_relative_seconds": t} for t in (-2.25, -1.5, -0.75)],
        "context": {"cre_line": "invented", "targeted_structure": "invented",
                    "imaging_depth": 100, "image_set": "invented",
                    "passive": False, "experience_level": "Familiar", "session_number": 1},
        "history": [0.0] * 12, "target": list(values),
    }


class Neural063WeightedMean(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.controls, cls.scoring, cls.schema = load_arithmetic()

    def panel(self, values):
        rows = [row(i, "fit", values(i)) for i in range(73)]
        return self.admit(rows, "fit")

    def admit(self, rows, split, require_target=True):
        return self.schema.admit_rows(
            {"schema": "neural063_rows_v2", "split": split, "rows": rows},
            split, require_target=require_target)

    def oracle(self, rows):
        weights, _ = self.scoring.hierarchy(rows, 73)
        return [float(sum((Fraction(weights[r["id"]]) * Fraction(float(r["target"][k]))
                           for r in rows), Fraction())) for k in range(3)]

    def test_complete_subnormal_fit_and_query_control(self):
        values = [5e-323, 1e-322, 1.5e-322]
        fit = self.panel(lambda i: values)
        model = self.controls.fit_mean(fit)
        self.assertEqual(model["values"], values)
        owner_query = self.admit([row(i, "query", values) for i in range(19)], "query")
        public_query = self.admit([{k: v for k, v in r.items() if k != "target"}
                                   for r in owner_query], "query", require_target=False)
        predictions = self.controls.direct(public_query, model)["fit_mean"]
        self.assertEqual([r["id"] for r in predictions], [r["id"] for r in owner_query])
        score = self.scoring.absolute({r["id"]: r["values"] for r in predictions},
                                      owner_query, self.scoring.training_scale(fit), 19)
        self.assertEqual(score["primary"], {"value": 0.0, "status": "finite"})
        self.assertEqual((score["mice"], score["events"]), (19, 19))

    def test_smallest_signed_subnormal_constant(self):
        for sign in (-1, 1):
            rows = self.panel(lambda i: [sign * TINY] * 3)
            self.assertEqual(self.controls.fit_mean(rows)["values"], [sign * TINY] * 3)

    def test_extreme_cancellation_retains_representable_residual(self):
        values = [sys.float_info.max, -sys.float_info.max, 73 * TINY] + [0.0] * 70
        rows = self.panel(lambda i: [values[i], -values[i], values[i]])
        expected = [TINY, -TINY, TINY]
        self.assertEqual(self.oracle(rows), expected)
        self.assertEqual(self.controls.fit_mean(rows)["values"], expected)
        self.assertEqual(self.controls.fit_mean(list(reversed(rows)))["values"], expected)

    def test_exact_cancellation_and_zero_are_zero(self):
        for values in ([0.0] * 73, [sys.float_info.max, -sys.float_info.max] + [0.0] * 71):
            rows = self.panel(lambda i: [values[i]] * 3)
            self.assertEqual(self.controls.fit_mean(rows)["values"], [0.0] * 3)

    def test_nonzero_unrepresentable_mean_is_refused(self):
        rows = self.panel(lambda i: [TINY if i == 0 else 0.0] * 3)
        with self.assertRaisesRegex(self.scoring.ContractError, "nonzero FIT mean control underflows"):
            self.controls.fit_mean(rows)

    def test_maximum_finite_constant_stays_finite(self):
        rows = self.panel(lambda i: [sys.float_info.max, -sys.float_info.max, 0.0])
        self.assertEqual(self.controls.fit_mean(rows)["values"], self.oracle(rows))
        self.assertTrue(all(math.isfinite(v) for v in self.controls.fit_mean(rows)["values"]))

    def test_ordinary_and_unbalanced_hierarchy_match_independent_oracle(self):
        rows = self.panel(lambda i: [i - 36, (i % 7) / 8, -i / 16])
        # Two sessions for mouse 0; the second has two experiments and three
        # events. Mouse/session/experiment/event weights must all be retained.
        for j in range(3):
            extra = row(0, "fit", [10 + j, -20 - j, 30 + j])
            extra.update(id=f"invented-fit-000-extra-{j}", session="invented-extra-session",
                         experiment=f"invented-extra-experiment-{min(j, 1)}")
            rows.append(extra)
        rows.sort(key=lambda r: r["id"])
        self.admit(rows, "fit")
        model = self.controls.fit_mean(rows)
        self.assertEqual(model["values"], self.oracle(rows))
        weights, _ = self.scoring.hierarchy(rows, 73)
        self.assertEqual(model["weights_sha256"],
                         self.schema.object_hash([[r["id"], weights[r["id"]]] for r in rows]))
        self.assertEqual(model["fit_ids_sha256"], self.schema.object_hash([r["id"] for r in rows]))
        self.assertEqual(model["fit_mice"], 73)

    def test_full_fit_population_and_split_still_required(self):
        rows = self.panel(lambda i: [1, 2, 3])
        with self.assertRaisesRegex(self.scoring.ContractError, "complete fixed mouse panel"):
            self.controls.fit_mean(rows[:-1])
        rows[0]["split"] = "query"
        with self.assertRaisesRegex(self.scoring.ContractError, "FIT-only"):
            self.controls.fit_mean(rows)

    def test_invalid_target_types_shapes_and_nonfinite_values_are_refused(self):
        for bad in (True, "1", None, math.inf, math.nan, 10 ** 1000):
            rows = self.panel(lambda i: [1, 2, 3])
            rows[0]["target"][0] = bad
            with self.subTest(bad_type=type(bad).__name__):
                with self.assertRaises(self.scoring.ContractError):
                    self.controls.fit_mean(rows)
        rows = self.panel(lambda i: [1, 2, 3])
        rows[0]["target"] = [1, 2]
        with self.assertRaisesRegex(self.scoring.ContractError, "three target bins"):
            self.controls.fit_mean(rows)

    def test_current_descriptor_pins_repair_and_preserves_native_hold(self):
        descriptor = json.loads(CLOSURE.read_text())
        for pin in (descriptor["canonical_task"], *descriptor["historical_descriptors"],
                    *descriptor["arithmetic_source_files"], descriptor["regression_test"]):
            body = (ROOT / pin["path"]).read_bytes()
            self.assertEqual((len(body), hashlib.sha256(body).hexdigest()),
                             (pin["bytes"], pin["sha256"]))
        self.assertFalse(descriptor["native_manifest_selection"])
        self.assertFalse(descriptor["runtime_scientific_qualification"])
        historical = json.loads((PACKAGE / "SOURCE_MANIFEST.json").read_text())
        old = next(p for p in historical["files"] if p["path"] == "references/controls.py")
        repair = next(p for p in descriptor["arithmetic_source_files"]
                      if p["path"].endswith("/references/controls.py"))
        self.assertEqual({k: old[k] for k in ("bytes", "sha256")}, repair["predecessor"])
        self.assertNotEqual(old["sha256"], repair["sha256"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
