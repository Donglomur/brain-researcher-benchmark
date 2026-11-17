"""Generated software controls only: no source recordings or model execution."""

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import sys
import tempfile
import types
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("neural086_support_score", HERE / "score.py")
score = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score)


def packet():
    people = [f"person-{index:02d}" for index in range(18)]
    items = ["item-a", "item-b"]
    support = []
    base, plus = [], []
    for person in people:
        for item in items:
            for word in (0, 3):
                for label in (0, 1):
                    # Unequal repeat counts exercise the hierarchy, not an
                    # occurrence-weighted mean masquerading as an equal unit.
                    for repeat in range(1 + label + (word == 3)):
                        row = {"person": person, "item": item, "word_index": word,
                               "label": label, "repetition_ordinal": repeat,
                               "block": label * 7, "duration_seconds": 2.0,
                               "window_duration_ms": 125.0}
                        support.append(row)
                        base.append({**row, "id": f"base-{len(base)}", "p": 0.5})
                        q = 0.8 if word == 0 else 0.6
                        plus.append({**row, "id": f"plus-{len(plus)}", "p": q if label else 1 - q})
    return {"base": base, "plus": plus, "people": people, "items": items, "expected_support": support}


class PairedSupportTests(unittest.TestCase):
    def test_analytic_equal_word_class_item_person_aggregation(self):
        result = score.paired_contrast(**packet())
        expected_plus = (-math.log(0.8) - math.log(0.6)) / 2
        self.assertAlmostEqual(result["base_loss"], math.log(2))
        self.assertAlmostEqual(result["plus_loss"], expected_plus)
        self.assertAlmostEqual(result["signed_difference"], math.log(2) - expected_plus)
        self.assertEqual(result["expected_person_item_cells"], 36)
        self.assertEqual(result["expected_word_occurrences"], 288)
        self.assertEqual(result["base_balanced_accuracy"], 0.5)
        self.assertEqual(result["plus_balanced_accuracy"], 1.0)
        self.assertTrue(all(cell["paired_words"] == 2 for cell in result["paired_cell_matrix"]))
        self.assertEqual(result["uncertainty"]["resamples"], 1000)
        self.assertFalse(result["uncertainty"]["population_coverage_claim"])

    def test_rejects_different_original_words_in_same_cells(self):
        data = packet()
        for row in data["plus"]:
            if row["word_index"] == 3:
                row["word_index"] = 4
        with self.assertRaisesRegex(ValueError, "plus_census_support"):
            score.paired_contrast(**data)

    def test_rejects_repeat_substitution_even_with_same_counts(self):
        data = packet()
        data["plus"][0]["repetition_ordinal"] = 7
        with self.assertRaisesRegex(ValueError, "plus_census_support"):
            score.paired_contrast(**data)

    def test_rejects_shared_word_omission_against_frozen_census(self):
        data = packet()
        for arm in ("base", "plus"):
            data[arm] = [row for row in data[arm] if row["word_index"] != 3]
        with self.assertRaisesRegex(ValueError, "base_census_support"):
            score.paired_contrast(**data)

    def test_rejects_duplicate_and_invalid_probabilities(self):
        for probability in (True, float("nan"), float("inf"), -0.01, 1.01):
            data = packet()
            data["plus"][0]["p"] = probability
            with self.subTest(probability=probability), self.assertRaisesRegex(ValueError, "probability"):
                score.paired_contrast(**data)
        data = packet()
        data["plus"].append(copy.deepcopy(data["plus"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate_source_occurrence"):
            score.paired_contrast(**data)

    def test_rejects_unknown_people_and_duplicate_axes(self):
        data = packet()
        for arm in ("base", "plus", "expected_support"):
            data[arm][0]["person"] = "outside-panel"
        with self.assertRaisesRegex(ValueError, "extra_comparison_cell"):
            score.paired_contrast(**data)
        for axis, error in (("people", "distinct_people"), ("items", "distinct_items")):
            data = packet()
            data[axis][-1] = data[axis][0]
            with self.subTest(axis=axis), self.assertRaisesRegex(ValueError, error):
                score.paired_contrast(**data)

    def test_rejects_metadata_misbinding(self):
        data = packet()
        data["plus"][0]["window_duration_ms"] = 500.0
        with self.assertRaisesRegex(ValueError, "source_occurrence_metadata"):
            score.paired_contrast(**data)

    def test_missing_source_cell_has_null_primary_and_interval(self):
        data = packet()
        for arm in ("base", "plus", "expected_support"):
            data[arm] = [row for row in data[arm] if (row["person"], row["item"]) != ("person-00", "item-b")]
        result = score.paired_contrast(**data)
        self.assertIsNone(result["signed_difference"])
        self.assertIsNone(result["base_loss"])
        self.assertIsNone(result["uncertainty"])
        self.assertEqual(result["missing_cells"], [["person-00", "item-b"]])
        self.assertEqual(result["supported_person_item_cells"], 35)
        self.assertEqual(len(result["paired_cell_matrix"]), 35)

    def test_wholly_unavailable_context_retains_all_missing_cells(self):
        data = packet()
        for arm in ("base", "plus", "expected_support"):
            data[arm] = []
        result = score.paired_contrast(**data)
        self.assertEqual(len(result["missing_cells"]), 36)
        self.assertIsNone(result["signed_difference"])

    def test_census_requires_both_conditions_per_original_word(self):
        data = packet()
        for arm in ("base", "plus", "expected_support"):
            data[arm] = [row for row in data[arm] if not (row["person"] == "person-00" and row["item"] == "item-a" and row["word_index"] == 3 and row["label"] == 1)]
        with self.assertRaisesRegex(ValueError, "unpaired_word_census"):
            score.paired_contrast(**data)

    def test_sign_zero_and_probability_endpoints(self):
        data = packet()
        data["base"], data["plus"] = data["plus"], data["base"]
        self.assertLess(score.paired_contrast(**data)["signed_difference"], 0)
        data = packet()
        for row in data["plus"]:
            row["p"] = 0.5
        result = score.paired_contrast(**data)
        self.assertEqual(result["signed_difference"], 0.0)
        self.assertEqual(result["uncertainty"]["descriptive_crossed_resampling_interval95"], [0.0, 0.0])
        for row in data["plus"]:
            row["p"] = row["label"]
        self.assertAlmostEqual(score.paired_contrast(**data)["plus_loss"], -math.log(1 - 1e-6))

    def test_row_permutations_preserve_report_and_support_digest(self):
        data = packet()
        expected = score.paired_contrast(**data)
        for arm in ("base", "plus", "expected_support"):
            random.Random(41).shuffle(data[arm])
        self.assertEqual(score.paired_contrast(**data), expected)

    def test_existing_metric_parity_and_original_counterexample(self):
        # Load only the unchanged source arithmetic and its stdlib I/O helpers;
        # never import the campaign driver or read its protected inputs.
        root = HERE.parents[4]
        shared = root / "benchmarks/shared/zuco2/zuco2-neural085-086-complete-v1/zuco"
        self.assertEqual(hashlib.sha256((shared / "metrics.py").read_bytes()).hexdigest(),
                         "30a06338aff4cd73b724bb22576c646c36c579ed51f7417df06f8b686bfae56d")
        package_name = "_neural086_legacy_control"
        package = types.ModuleType(package_name)
        package.__path__ = [str(shared)]
        sys.modules[package_name] = package
        legacy_spec = importlib.util.spec_from_file_location(package_name + ".metrics", shared / "metrics.py")
        legacy = importlib.util.module_from_spec(legacy_spec)
        legacy_spec.loader.exec_module(legacy)
        data = packet()
        # Vary person/item effects so interval and standard errors are tested.
        for row in data["plus"]:
            probability = 0.55 + int(row["person"][-2:]) * 0.01 + (row["item"] == "item-b") * 0.04
            row["p"] = probability if row["label"] else 1 - probability
        current = score.paired_contrast(**data)
        previous = legacy.paired_contrast(data["base"], data["plus"], data["people"], data["items"])
        for field in ("base_loss", "plus_loss", "signed_difference", "base_balanced_accuracy", "plus_balanced_accuracy"):
            self.assertAlmostEqual(current[field], previous[field], places=13)
        self.assertEqual(current["uncertainty"], previous["uncertainty"])
        for row in data["plus"]:
            if row["word_index"] == 3:
                row["word_index"] = 4
        self.assertTrue(legacy.paired_contrast(data["base"], data["plus"], data["people"], data["items"])["complete_support"])
        with self.assertRaisesRegex(ValueError, "plus_census_support"):
            score.paired_contrast(**data)

    def test_cli_and_failures_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "packet.json", Path(directory) / "report.json"
            source.write_text(json.dumps(packet()))
            self.assertEqual(score.main(["--packet", str(source), "--output", str(output)]), 0)
            self.assertTrue(json.loads(output.read_text())["complete_support"])
            original = output.read_bytes()
            with self.assertRaises(FileExistsError):
                score.main(["--packet", str(source), "--output", str(output)])
            self.assertEqual(output.read_bytes(), original)
            output.unlink()
            for malformed in ('{"people": [], "people": []}', '{"x": NaN}'):
                source.write_text(malformed)
                with self.assertRaises(ValueError):
                    score.main(["--packet", str(source), "--output", str(output)])
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
