import copy
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
import warnings

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("matched_reference", HERE / "reference.py")
ref = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ref)


def packet(arm="neural", *, zero=False):
    width = len(ref.delivery.FEATURES[arm])
    demos = [] if zero else [{"label": label, "values": [float(label)] * width}
                             for label in (0, 2, 0, 2)]
    return {"schema": ref.delivery.SCHEMA, "task_id": "NEURAL-027",
            "requested_access_mode": "direct_observation", "observation_condition": arm,
            "demonstration_condition": "zero_demonstrations" if zero else "fixed_training_demonstrations",
            "classes_in_probability_order": [0, 2], "feature_order": ref.delivery.FEATURES[arm],
            "instructions": ref.delivery.INSTRUCTIONS, "demonstrations": demos,
            "items": [{"item_id": f"{i:064x}", "values": [value] * width}
                      for i, value in enumerate((0.9, 1.1), 1)]}


class MatchedReferenceTests(unittest.TestCase):
    def test_numerical_gaussian_oracle(self):
        result = ref.predict(packet())
        expected = 1 / (1 + math.exp(-8))
        self.assertAlmostEqual(result[0]["probabilities"][0], expected, places=14)
        self.assertAlmostEqual(result[1]["probabilities"][1], expected, places=14)

    def test_equal_mouse_class_weights_match_original_recipe(self):
        p = packet()
        p["demonstrations"] = [{"label": c, "values": [v, v + 0.2, v - 0.1, 2*v]}
                                for c, v in ((0, 0.1), (2, 1.9), (0, 0.3), (2, 2.4))]
        original = [{"item_id": str(i), "mname": "mouse-A" if i < 2 else "mouse-B",
                     "phase": "before", "label": r["label"], "neural": r["values"]}
                    for i, r in enumerate(p["demonstrations"])]
        queries = [{"item_id": r["item_id"], "neural": r["values"], "context": []}
                   for r in p["items"]]
        expected = ref.base.Reference([0, 2], "neural").fit(original).predict(queries)
        self.assertEqual(ref.predict(p), expected)

    def test_query_population_does_not_fit_reference(self):
        p = packet()
        before = ref.predict(p)
        p["items"].append({"item_id": "f" * 64, "values": [100000.0] * 4})
        self.assertEqual(ref.predict(p)[:2], before)
        p["items"].reverse()
        by_id = {r["item_id"]: r["probabilities"] for r in ref.predict(p)}
        self.assertEqual([by_id[r["item_id"]] for r in before],
                         [r["probabilities"] for r in before])

    def test_no_other_arm_features_enter_neural_fit(self):
        p = {arm: packet(arm) for arm in ref.delivery.FEATURES}
        a, _ = ref.predict_pair(p)
        p["movement_position"]["demonstrations"][0]["values"] = [800.0, -20.0]
        p["movement_position"]["items"][0]["values"] = [70.0, -100.0]
        b, _ = ref.predict_pair(p)
        self.assertEqual(a["neural"], b["neural"])
        self.assertNotEqual(a["movement_position"], b["movement_position"])

    def test_zero_demonstrations_are_explicit_uniform_recipe(self):
        p = {arm: packet(arm, zero=True) for arm in ref.delivery.FEATURES}
        rows, report = ref.predict_pair(p)
        self.assertEqual(report["recipe"], "uniform_probabilities")
        self.assertEqual(report["demonstrations_per_condition"], 0)
        self.assertTrue(all(row["probabilities"] == [0.5, 0.5]
                            for arm in rows.values() for row in arm))

    def test_incomplete_or_unbalanced_demonstrations_rejected(self):
        p = packet()
        p["demonstrations"].pop()
        with self.assertRaisesRegex(ValueError, "all classes equally"):
            ref.predict(p)
        p["demonstrations"] = [r for r in p["demonstrations"] if r["label"] == 0]
        with self.assertRaisesRegex(ValueError, "all classes equally"):
            ref.predict(p)

    def test_pair_requires_same_cases_and_exposure(self):
        good = {arm: packet(arm) for arm in ref.delivery.FEATURES}
        for mutation, expected in (("case", "query identities"), ("label", "demonstration targets"),
                                   ("zero", "exposure condition")):
            p = copy.deepcopy(good)
            if mutation == "case":
                p["movement_position"]["items"][0]["item_id"] = "e" * 64
            elif mutation == "label":
                p["movement_position"]["demonstrations"].reverse()
            else:
                p["movement_position"] = packet("movement_position", zero=True)
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, expected):
                ref.predict_pair(p)

    def test_target_or_identity_injection_rejected(self):
        p = packet()
        p["items"][0]["label"] = 0
        with self.assertRaisesRegex(ValueError, "fields mismatch"):
            ref.predict(p)

    def test_finite_inputs_that_overflow_recipe_fail_closed(self):
        for where in ("demonstrations", "items"):
            p = packet()
            p[where][0]["values"] = [1e308] * 4
            with self.subTest(where=where), warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                with self.assertRaisesRegex(ValueError, "nonfinite|invalid probabilities"):
                    ref.predict(p)
        p = packet()
        p["private_binding"] = {"target": 0}
        with self.assertRaisesRegex(ValueError, "fields mismatch"):
            ref.predict(p)

    def test_cli_complete_outputs_and_frozen_binding_compatible(self):
        public = {arm: packet(arm) for arm in ref.delivery.FEATURES}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            incoming, output = root / "public", root / "responses"
            incoming.mkdir()
            for arm, value in public.items():
                (incoming / (arm + ".json")).write_text(json.dumps(value))
            ref.main(["--public-dir", str(incoming), "--output-dir", str(output)])
            rows = {arm: json.loads((output / (arm + "-responses.json")).read_text())
                    for arm in public}
            report = json.loads((output / "reference.json").read_text())
            self.assertEqual(report["public_sha256"], {arm: ref.delivery.digest(value)
                                                      for arm, value in public.items()})
            expected = [{"item_id": r["item_id"], "label": c, "mname": "generated-mouse", "phase": "generated-phase"}
                        for r, c in zip(public["neural"]["items"], (0, 2))]
            private = {"schema": ref.delivery.SCHEMA, "task_id": "NEURAL-027",
                       "predecessor_sha256": ref.delivery.BASE_SHA256,
                       "classes_in_probability_order": [0, 2], "expected": expected,
                       "public_sha256": report["public_sha256"]}
            scores = ref.delivery.collect(public, private, rows, bootstrap_draws=100)
            self.assertEqual(scores["neural"]["by_phase"]["generated-phase"]["n_mice"], 1)
            self.assertFalse(scores["access_enforcement_verified"])
            with self.assertRaisesRegex(ValueError, "must be new"):
                ref.main(["--public-dir", str(incoming), "--output-dir", str(output)])
            with self.assertRaisesRegex(ValueError, "disjoint"):
                ref.main(["--public-dir", str(incoming), "--output-dir", str(incoming / "child")])


if __name__ == "__main__":
    unittest.main()
