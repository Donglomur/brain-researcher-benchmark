import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "initial-evaluator-v1"))
import endpoint_vector as v
from make_control import build


def rows_for(bits):
    queries = [("0", "person"), ("1", "car"), ("1", "dog"), ("1", "bottle")]
    return [{"image_id": i, "category": c, "iou": bit} for (i, c), bit in zip(queries, bits)]


def fixture():
    rows = {role: {subject: rows_for([0, 0, 0, 0]) for subject in v.SUBJECTS}
            for role in v.g.ROLES}
    for subject, bits in zip(v.SUBJECTS, ([1, 0, 0, 0], [0, 1, 1, 1], [1, 1, 1, 1], [0, 0, 0, 0])):
        rows["candidate"][subject] = rows_for(bits)
    return rows


class EndpointVectorTests(unittest.TestCase):
    def test_hand_computed_query_weights_and_twelve_contrast_family(self):
        result = v.compare_vectors(fixture(), ["0", "1"], draws=0)
        self.assertEqual(result["scores_percent"]["candidate"], {"S1": 25, "S2": 75, "S5": 100, "S7": 0})
        self.assertEqual(result["query_count_per_subject"], 4)
        self.assertEqual(result["bootstrap"]["family_size"], 12)
        self.assertEqual(result["bootstrap"]["status"], "not_requested")
        self.assertEqual(result["published_umbrae_v2_percent"], {"S1": 18.93, "S2": 18.27, "S5": 18.19, "S7": 16.74})
        self.assertIsNone(result["bootstrap"]["radius_percentage_points"])

    def test_independent_exhaustive_two_image_bootstrap(self):
        # Four equally probable ordered resamples. Because image1 has 3 queries,
        # S1 accuracies are 100,25,25,0 and S2 are 0,75,75,100. Max deviations
        # across the whole family are 75,0,0,25. Nearest-rank q(.75) is 25.
        with patch.object(v.random, "Random") as rng:
            rng.return_value.choices.side_effect = [["0", "0"], ["0", "1"], ["1", "0"], ["1", "1"]]
            result = v.compare_vectors(fixture(), ["0", "1"], draws=4, confidence=.75)
            self.assertEqual(rng.return_value.choices.call_count, 4)
        self.assertEqual(result["bootstrap"]["radius_percentage_points"], 25)
        expected = {"S1": [0, 50], "S2": [50, 100], "S5": [75, 100], "S7": [-25, 25]}
        for role in v.COMPARATORS:
            for subject, interval in expected.items():
                self.assertEqual(result["candidate_contrasts"][role][subject]["simultaneous_interval_percentage_points"], interval)

    def test_positive_pooled_delta_cannot_hide_losing_subject(self):
        rows = fixture()
        for role in v.COMPARATORS:
            for subject in v.SUBJECTS:
                rows[role][subject] = rows_for([1, 1, 0, 0])
        for subject in ("S1", "S2", "S5"):
            rows["candidate"][subject] = rows_for([1, 1, 1, 1])
        result = v.compare_vectors(rows, ["0", "1"], draws=0)
        deltas = result["candidate_contrasts"]["official_baseline"]
        self.assertEqual([deltas[s]["candidate_minus_comparator_percentage_points"] for s in v.SUBJECTS], [50, 50, 50, -50])
        self.assertNotIn("pooled", result)
        self.assertTrue(result["decision"].startswith("not_admitted"))

    def test_strict_threshold_and_arm_pairing(self):
        rows = fixture()
        rows["candidate"]["S1"][0]["iou"] = .5
        rows["neural_free"]["S2"] = copy.deepcopy(rows["candidate"]["S2"])
        result = v.compare_vectors(rows, ["0", "1"], draws=0)
        self.assertEqual(result["scores_percent"]["candidate"]["S1"], 0)
        self.assertEqual(result["candidate_contrasts"]["neural_free"]["S2"]["candidate_minus_comparator_percentage_points"], 0)
        self.assertEqual(result["candidate_contrasts"]["official_baseline"]["S2"]["candidate_minus_comparator_percentage_points"], 75)

    def test_empty_image_resample_never_silently_conditioned_away(self):
        with patch.object(v.random, "Random") as rng:
            rng.return_value.choices.side_effect = [["0", "1", "2"], ["2", "2", "2"]]
            result = v.compare_vectors(fixture(), ["0", "1", "2"], draws=2)
        self.assertEqual(result["empty_query_image_count"], 1)
        self.assertEqual(result["bootstrap"]["undefined_zero_query_draws"], 1)
        self.assertEqual(result["bootstrap"]["defined_draws"], 1)
        self.assertEqual(result["bootstrap"]["status"], "undefined_zero_query_resamples")
        self.assertIsNone(result["bootstrap"]["radius_percentage_points"])
        for contrast in result["candidate_contrasts"].values():
            for value in contrast.values():
                self.assertIsNone(value["simultaneous_interval_percentage_points"])

    def test_order_invariance_and_identical_arm_zero_band(self):
        rows = fixture()
        expected = v.compare_vectors(rows, ["0", "1"], draws=20, seed=4)
        reversed_rows = {role: {subject: list(reversed(value)) for subject, value in reversed(list(subjects.items()))}
                         for role, subjects in reversed(list(rows.items()))}
        self.assertEqual(v.compare_vectors(reversed_rows, ["1", "0"], draws=20, seed=4), expected)
        for role in v.COMPARATORS:
            rows[role] = copy.deepcopy(rows["candidate"])
        result = v.compare_vectors(rows, ["0", "1"], draws=20)
        self.assertEqual(result["bootstrap"]["radius_percentage_points"], 0)
        for role in v.COMPARATORS:
            self.assertEqual(result["candidate_contrasts"][role]["S1"]["simultaneous_interval_percentage_points"], [0, 0])

    def test_all_subjects_arms_query_identity_and_multiplicity_required(self):
        mutations = [
            lambda r: r.pop("shuffled_neural"),
            lambda r: r["candidate"].pop("S7"),
            lambda r: r["official_baseline"]["S2"].pop(),
            lambda r: r["neural_free"]["S5"].append(copy.deepcopy(r["neural_free"]["S5"][0])),
            lambda r: r["candidate"]["S1"][0].update(category="cat"),
            lambda r: r["shuffled_neural"]["S7"][0].update(image_id="99"),
        ]
        for mutate in mutations:
            rows = fixture()
            mutate(rows)
            with self.assertRaises(v.g.ContractError):
                v.compare_vectors(rows, ["0", "1"], draws=0)
        with self.assertRaises(v.g.ContractError):
            v.compare_vectors(fixture(), ["0", "0", "1"], draws=0)

    def test_invalid_numbers_and_resampling_parameters_reject(self):
        for invalid in (True, None, float("nan"), float("inf"), -0.1, 1.1, 10**1000):
            rows = fixture()
            rows["candidate"]["S1"][0]["iou"] = invalid
            with self.assertRaises(v.g.ContractError):
                v.compare_vectors(rows, ["0", "1"], draws=0)
        for kwargs in ({"draws": True}, {"draws": -1}, {"draws": 10001}, {"seed": False},
                       {"confidence": 1}, {"confidence": 0}, {"confidence": float("nan")}):
            with self.assertRaises(v.g.ContractError):
                v.compare_vectors(fixture(), ["0", "1"], **kwargs)

    def test_real_file_path_keeps_original_semantics_and_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "fixture"
            contract = build(root)
            result = v.evaluate(contract, root / "annotations.json", root / "image_order.json", draws=0)
            self.assertNotIn("paired_comparisons", result)
            self.assertEqual(result["endpoint_vector"]["scores_percent"]["candidate"], dict.fromkeys(v.SUBJECTS, 75))
            self.assertEqual(result["scores"]["candidate"]["S1"]["All"]["mean_iou"], .875)
            self.assertEqual(result["endpoint_vector"]["candidate_contrasts"]["official_baseline"]["S7"]["candidate_minus_comparator_percentage_points"], 50)
            self.assertFalse(result["authentic_reference_run"])
            self.assertEqual(result["qualification"], "unknown")
            obj = json.loads(contract.read_text())
            del obj["runs"]["neural_free"]
            contract.write_text(json.dumps(obj))
            with self.assertRaises(v.g.ContractError):
                v.evaluate(contract, root / "annotations.json", root / "image_order.json", draws=0)

    def test_cli_produces_vector_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "fixture"
            contract = build(root)
            output = root / "result.json"
            command = [sys.executable, "-I", "-B", str(HERE / "endpoint_vector.py"),
                       "--contract", str(contract), "--annotations", str(root / "annotations.json"),
                       "--image-order", str(root / "image_order.json"), "--output", str(output), "--draws", "0"]
            first = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(first.returncode, 0, first.stderr)
            original = output.read_bytes()
            self.assertEqual(json.loads(original)["endpoint_vector"]["subject_order"], list(v.SUBJECTS))
            second = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(second.returncode, 2)
            self.assertEqual(output.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
