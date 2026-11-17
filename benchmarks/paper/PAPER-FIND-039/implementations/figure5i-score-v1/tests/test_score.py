"""Generated software controls only; none of these are empirical predictions."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / "score.py"
SPEC = importlib.util.spec_from_file_location("figure5i_score", PATH)
score = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(score)


def fixture():
    reference = {
        "schema": "figure5i-reference/v1", "task_id": score.TASK,
        "source_revision": score.SOURCE_REVISION, "condition": "spatial_cells_both_maps",
        "cohort_receipt_sha256": "1" * 64, "preprocessing_receipt_sha256": "2" * 64,
        "split_receipt_sha256": "3" * 64, "sessions": [],
    }
    for age, count in (("young", 34), ("aged", 27)):
        for index in range(count):
            # Deliberately uneven folds: 21 observations -> 3,2,...,2.
            observations = [f"o{n}" for n in range(21)]
            folds, start = [], 0
            for repeat, length in enumerate([3] + [2] * 9):
                test = observations[start:start + length]
                train = [obs for obs in observations if obs not in test][:18]
                folds.append({"repeat": repeat, "test_observation_ids": test,
                              "train_observation_ids": train, "target_radians": [0.0] * length})
                start += length
            reference["sessions"].append({
                "mouse_id": f"{age}_mouse{index // 3}", "session_id": f"session{index}",
                "age_group": age, "spatial_cell_ids": [f"c{n}" for n in range(11)],
                "optimal_k": 2, "source_onemap": False,
                "downsampled_observation_ids": observations, "folds": folds,
            })
    packet = {"schema": "figure5i-predictions/v1", "reference_sha256": score.reference_digest(reference),
              "sessions": []}
    for session in reference["sessions"]:
        packet["sessions"].append({"mouse_id": session["mouse_id"], "session_id": session["session_id"],
                                   "folds": [{"repeat": fold["repeat"],
                                              "test_observation_ids": fold["test_observation_ids"].copy(),
                                              "predicted_radians": [0.0] * len(fold["test_observation_ids"])}
                                             for fold in session["folds"]]})
    return reference, packet


class ScoreTests(unittest.TestCase):
    def test_geometry_and_wrap(self):
        self.assertAlmostEqual(score.cosine_score([0.0], [0.0]), 1)
        self.assertAlmostEqual(score.cosine_score([0.0], [math.pi]), -1)
        self.assertAlmostEqual(score.cosine_score([0.0], [math.pi / 2]), 0)
        self.assertAlmostEqual(score.cosine_score([-math.pi + .2], [math.pi + .2]), 1)

    def test_rejects_missing_or_nonfinite_observations(self):
        for target, predicted in (([], []), ([0], []), ([0], [float("nan")]),
                                  ([0], [float("inf")]), ([True], [0]), ([0], ["0"]),
                                  ([0, 1], [0])):
            with self.subTest(target=target, predicted=predicted), self.assertRaises(ValueError):
                score.cosine_score(target, predicted)

    def test_mean_of_folds_not_pooled_observations(self):
        reference, candidate = fixture()
        author, shuffle = copy.deepcopy(candidate), copy.deepcopy(candidate)
        for session in candidate["sessions"]:
            session["folds"][0]["predicted_radians"] = [math.pi] * 3
        result = score.score_panel(reference, candidate, author, shuffle)
        # Independent count oracle: nine +1 fold scores, one -1 score => 0.8.
        self.assertAlmostEqual(result["age_strata"]["young"]["session_mean"]["candidate"], .8)
        self.assertNotAlmostEqual(.8, (18 - 3) / 21)
        self.assertAlmostEqual(result["age_strata"]["aged"]["candidate_minus_author"], -.2)

    def test_session_weighting_and_strata_are_preserved(self):
        reference, author = fixture()
        candidate = copy.deepcopy(author)
        for fold in candidate["sessions"][0]["folds"]:
            fold["predicted_radians"] = [math.pi] * len(fold["predicted_radians"])
        result = score.score_panel(reference, candidate, author, author)
        self.assertAlmostEqual(result["age_strata"]["young"]["candidate_minus_author"], -2 / 34)
        self.assertEqual(result["age_strata"]["aged"]["candidate_minus_author"], 0)
        self.assertNotIn("pooled", result)

    def test_exact_cohort_and_eligibility(self):
        reference, _ = fixture()
        for change in (lambda r: r["sessions"].pop(),
                       lambda r: r["sessions"][0].update(optimal_k=3),
                       lambda r: r["sessions"][0].update(spatial_cell_ids=[f"c{i}" for i in range(10)]),
                       lambda r: r["sessions"][0].update(age_group="middle")):
            altered = copy.deepcopy(reference)
            change(altered)
            with self.assertRaises(ValueError):
                score.validate_reference(altered)

    def test_rejects_train_test_overlap_and_non_source_partition(self):
        reference, _ = fixture()
        for change in (lambda s: s["folds"][0]["train_observation_ids"].__setitem__(0, "o0"),
                       lambda s: s["folds"][0]["test_observation_ids"].reverse(),
                       lambda s: s["folds"][0]["train_observation_ids"].pop(),
                       lambda s: s["folds"][0].update(repeat=True)):
            altered = copy.deepcopy(reference)
            change(altered["sessions"][0])
            with self.assertRaises(ValueError):
                score.validate_reference(altered)

    def test_source_non_single_map_declaration_required(self):
        reference, _ = fixture()
        for value in (True, None, 0, "False"):
            altered = copy.deepcopy(reference)
            altered["sessions"][0]["source_onemap"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                score.validate_reference(altered)
        del reference["sessions"][0]["source_onemap"]
        with self.assertRaises(ValueError):
            score.validate_reference(reference)

    def test_predictions_bind_every_observation_and_all_folds(self):
        reference, packet = fixture()
        for change in (lambda p: p["sessions"].pop(),
                       lambda p: p["sessions"].append(p["sessions"][0]),
                       lambda p: p["sessions"][0]["folds"].pop(),
                       lambda p: p["sessions"][0]["folds"][0]["test_observation_ids"].reverse(),
                       lambda p: p["sessions"][0]["folds"][0]["predicted_radians"].pop(),
                       lambda p: p.update(reference_sha256="0" * 64)):
            altered = copy.deepcopy(packet)
            change(altered)
            with self.assertRaises(ValueError):
                score.score_panel(reference, altered, packet, packet)

    def test_rebound_targets_invalidate_predictions(self):
        reference, packet = fixture()
        reference["sessions"][0]["folds"][0]["target_radians"][0] = .1
        with self.assertRaises(ValueError):
            score.score_panel(reference, packet, packet, packet)

    def test_all_arms_checked_and_order_independent(self):
        reference, packet = fixture()
        reordered = copy.deepcopy(packet)
        reordered["sessions"].reverse()
        for session in reordered["sessions"]:
            session["folds"].reverse()
        self.assertEqual(score.score_panel(reference, reordered, packet, packet),
                         score.score_panel(reference, packet, packet, packet))
        for arm in (1, 2):
            packets = [copy.deepcopy(packet) for _ in range(3)]
            packets[arm]["sessions"].pop()
            with self.assertRaises(ValueError):
                score.score_panel(reference, *packets)

    def test_cli_and_duplicate_keys(self):
        reference, packet = fixture()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ref, pred, out = root / "reference.json", root / "prediction.json", root / "report.json"
            ref.write_text(json.dumps(reference))
            pred.write_text(json.dumps(packet))
            command = [sys.executable, "-B", str(PATH), str(ref), str(pred), str(pred), str(pred), str(out)]
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(len(json.loads(out.read_text())["sessions"]), 61)
            ref.write_text('{"sessions": [], "sessions": []}')
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)


if __name__ == "__main__":
    unittest.main()
