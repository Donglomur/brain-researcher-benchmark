"""Generated software controls only. No authentic source observations or trials."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

import numpy as np


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROOT = Path(__file__).resolve().parents[1]
ev = load("neural040_v2_controls", ROOT / "evaluator.py")
controls = load("neural040_v1_controls", ROOT.parent / "initial-evaluator-v1/tests/test_evaluator.py")


class FixedFitControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol, cls.features, cls.training, cls.targets = controls.fixture()
        cls.training_meta = controls.target_meta(cls.protocol, "train")
        cls.target_meta = controls.target_meta(cls.protocol, "evaluation")
        cls.predictions, cls.metadata = ev.base.encode(
            cls.protocol, cls.features, cls.training, cls.training_meta)
        cls.reference_score = ev.base.score(cls.protocol, cls.predictions, cls.targets,
                                            cls.metadata, cls.target_meta)
        cls.claims = [{"family": family, "mean_delta_r": contrast["mean_delta_r"]}
                      for family, contrast in cls.reference_score["contrasts"].items()]

    def evaluate(self, predictions=None, claims=None, loader=None, features=None):
        return ev.score_fixed_fit(
            self.protocol, self.features if features is None else features,
            self.training, self.training_meta,
            self.predictions if predictions is None else predictions, self.metadata,
            self.claims if claims is None else claims,
            loader if loader is not None else lambda: (self.targets, self.target_meta))

    def test_retains_exact_estimator_and_complete_signed_claims(self):
        loader = Mock(return_value=(self.targets, self.target_meta))
        result = self.evaluate(claims=list(reversed(self.claims)), loader=loader)
        loader.assert_called_once_with()
        self.assertEqual(result["contrasts"], self.reference_score["contrasts"])
        self.assertEqual(result["people"], self.reference_score["people"])
        self.assertEqual([c["family"] for c in result["claims"]], list(ev.base.FAMILIES))
        self.assertTrue(result["all_numerical_claims_verified"])
        self.assertFalse(result["scientific_qualification"])
        self.assertFalse(result["native_reference_reproduced"])

    def test_forged_ablation_is_rejected_before_private_access(self):
        # This remains shape-, parcel- and protocol-valid for the predecessor.
        forged = dict(self.predictions)
        for key in forged:
            if key.startswith("no_audio__"):
                forged[key] = -forged[key]
        original = ev.base.score(self.protocol, forged, self.targets, self.metadata, self.target_meta)
        self.assertNotEqual(original["contrasts"]["audio"], self.reference_score["contrasts"]["audio"])
        loader = Mock(side_effect=AssertionError("private targets read too early"))
        with self.assertRaisesRegex(ev.ContractError, "fixed-fit prediction mismatch"):
            self.evaluate(predictions=forged, loader=loader)
        loader.assert_not_called()

    def test_missing_extra_and_swapped_arm_arrays_are_rejected(self):
        first, second = list(self.predictions)[:2]
        variants = []
        missing = dict(self.predictions)
        missing.pop(first)
        variants.append(missing)
        variants.append(dict(self.predictions, extra=self.predictions[first]))
        swapped = dict(self.predictions)
        swapped[first], swapped[second] = swapped[second], swapped[first]
        variants.append(swapped)
        for predictions in variants:
            loader = Mock(side_effect=AssertionError("target access"))
            with self.subTest(keys=list(predictions)[:2]), self.assertRaises(ev.ContractError):
                self.evaluate(predictions=predictions, loader=loader)
            loader.assert_not_called()

    def test_complete_claim_schema_rejects_omissions_duplicates_and_nonfinite(self):
        bad = [None, [], self.claims[:2], self.claims + self.claims[:1],
               [self.claims[0]] * 3]
        for value in (True, float("nan"), float("inf"), "0"):
            altered = copy.deepcopy(self.claims)
            altered[0]["mean_delta_r"] = value
            bad.append(altered)
        for value in ([], "other"):
            altered = copy.deepcopy(self.claims)
            altered[0]["family"] = value
            bad.append(altered)
        for claims in bad:
            with self.subTest(claims=claims), self.assertRaises(ev.ContractError):
                ev.complete_claims(claims)

    def test_wrong_complete_claims_are_false_not_a_larger_effect_reward(self):
        claims = copy.deepcopy(self.claims)
        claims[0]["mean_delta_r"] += .1
        result = self.evaluate(claims=claims)
        self.assertEqual([claim["verified"] for claim in result["claims"]], [False, True, True])
        self.assertFalse(result["all_numerical_claims_verified"])

    def test_scoring_uses_recomputed_arrays_even_when_roundoff_is_admitted(self):
        changed = {key: value + 1e-13 for key, value in self.predictions.items()}
        result = self.evaluate(predictions=changed)
        self.assertEqual(result["contrasts"], self.reference_score["contrasts"])
        self.assertGreater(max(result["fixed_fit_verification"][
            "maximum_absolute_deviation_by_prediction"].values()), 0)

    def test_changed_reference_features_cannot_reuse_old_predictions(self):
        features = copy.deepcopy(self.features)
        segment = ev.base.selected_segments(self.protocol, split="evaluation")[0]
        features[segment["feature_keys"]["audio"]] += 100
        loader = Mock(side_effect=AssertionError("target access"))
        with self.assertRaisesRegex(ev.ContractError, "fixed-fit prediction mismatch"):
            self.evaluate(features=features, loader=loader)
        loader.assert_not_called()

    def test_cli_validates_real_artifacts_and_keeps_private_load_after_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            files = {key: directory / (key + suffix) for key, suffix in (
                ("protocol", ".json"), ("features", ".npz"), ("claims", ".json"),
                ("training-targets", ".npz"), ("training-target-metadata", ".json"),
                ("predictions", ".npz"), ("prediction-metadata", ".json"),
                ("private-targets", ".npz"), ("private-target-metadata", ".json"),
                ("output", ".json"))}
            for key, value in (("protocol", self.protocol), ("claims", self.claims)):
                ev.base.write_json(files[key], value)
            np.savez(files["features"], **self.features)
            np.savez(files["predictions"], **self.predictions)
            for prefix, arrays, metadata in (("training", self.training, self.training_meta),
                                              ("private", self.targets, self.target_meta)):
                np.savez(files[prefix + "-targets"], **arrays)
                ev.base.write_json(files[prefix + "-target-metadata"],
                    dict(metadata, npz_sha256=ev.base.sha256(files[prefix + "-targets"])))
            metadata = dict(self.metadata, artifact_sha256={
                "predictions": ev.base.sha256(files["predictions"])})
            ev.base.write_json(files["prediction-metadata"], metadata)
            argv = [arg for key, value in files.items() for arg in ("--" + key, str(value))]
            ev.main(argv)
            result = json.loads(files["output"].read_text())
            self.assertEqual(result["contrasts"], self.reference_score["contrasts"])
            self.assertIn("private_targets", result["artifact_sha256"])
            with self.assertRaises(FileExistsError):
                ev.main(argv)
            forged = dict(self.predictions)
            key = next(key for key in forged if key.startswith("no_audio__"))
            forged[key] = -forged[key]
            np.savez(files["predictions"], **forged)
            # Even a self-consistent rehash cannot authenticate a changed fit.
            metadata["artifact_sha256"]["predictions"] = ev.base.sha256(files["predictions"])
            ev.base.write_json(files["prediction-metadata"], metadata)
            files["private-targets"].unlink()
            files["private-target-metadata"].unlink()
            with self.assertRaisesRegex(ev.ContractError, "fixed-fit prediction mismatch"):
                ev.main(argv)


if __name__ == "__main__":
    unittest.main()
