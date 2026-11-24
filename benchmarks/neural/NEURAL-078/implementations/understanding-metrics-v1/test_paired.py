"""Generated full-report paired controls; no EEG, private targets or models."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

paired = load("neural078_paired_tests", HERE / "paired.py")
fixture = load("neural078_original_test_fixture", HERE / "test_score.py").fixture


class PairedTests(unittest.TestCase):
    def test_complete_equal_person_pairing_preserves_both_metrics(self):
        gold = fixture([0] * 8)
        first = fixture([8, 0, 0, 0, 0, 0, 0, 0])
        second = fixture([0, 0, 0, 0, 0, 0, 0, 16])
        result = paired.compare_pair(first, second, gold)
        self.assertEqual(result["condition_scores"]["first"], paired.metric.compare(first, gold))
        self.assertEqual(result["condition_scores"]["second"], paired.metric.compare(second, gold))
        self.assertEqual(result["paired_primary"]["value"], -1)
        self.assertEqual([r["first_minus_second_absolute_error"] for r in result["participants"]],
                         [8, 0, 0, 0, 0, 0, 0, -16])
        self.assertEqual(result["paired_primary"]["negative_favors"], "first")
        self.assertEqual(result["paired_primary"]["unit"], "native_EEGLAB_amplitude")

    def test_permutation_swap_and_identity(self):
        gold, first, second = fixture(), fixture([1] * 8), fixture([-1] * 8)
        result = paired.compare_pair(first, second, gold)
        first["participants"].reverse()
        second["participants"] = second["participants"][3:] + second["participants"][:3]
        self.assertEqual(result, paired.compare_pair(first, second, gold))
        self.assertEqual(result["paired_primary"]["value"],
                         -paired.compare_pair(second, first, gold)["paired_primary"]["value"])
        self.assertEqual(paired.compare_pair(first, first, gold)["paired_primary"]["value"], 0)

    def test_pairwise_calculation_precedes_rounding_of_report_means(self):
        gold = fixture([0] * 8)
        first, second = fixture([1e16 + 2] + [1e16] * 7), fixture([1e16] * 8)
        result = paired.compare_pair(first, second, gold)
        self.assertEqual(result["condition_scores"]["first"]["primary"]["value"], 1e16)
        self.assertEqual(result["condition_scores"]["second"]["primary"]["value"], 1e16)
        self.assertEqual(result["paired_primary"]["value"], 0.25)

    def test_missing_reference_support_keeps_complete_primary_null(self):
        gold = fixture(counts=[9, 20, 30, 40, 50, 60, 70, 80])
        first, second = copy.deepcopy(gold), copy.deepcopy(gold)
        first["participants"][1]["matched_FCz_contrast"] += 7
        result = paired.compare_pair(first, second, gold)
        self.assertIsNone(result["paired_primary"]["value"])
        self.assertEqual(result["supported_subset_mean_error_difference_diagnostic"], 1)
        self.assertEqual(result["unsupported_participants"], ["sub-001"])
        self.assertIsNone(result["participants"][0]["first_minus_second_absolute_error"])
        empty = fixture(counts=[0] * 8)
        result = paired.compare_pair(empty, empty, empty)
        self.assertIsNone(result["paired_primary"]["value"])
        self.assertIsNone(result["supported_subset_mean_error_difference_diagnostic"])

    def test_same_candidate_support_must_also_match_reference(self):
        gold, first = fixture(), fixture()
        first["participants"][0]["pair_digest"] = "e" * 64
        with self.assertRaisesRegex(ValueError, "Support identity differs"):
            paired.compare_pair(first, first, gold)

    def test_incomplete_reports_and_different_strata_or_digest_refused(self):
        gold = fixture()
        edits = []
        missing = copy.deepcopy(gold)
        missing["participants"].pop()
        edits.append(missing)
        digest = copy.deepcopy(gold)
        digest["participants"][0]["pair_digest"] = "f" * 64
        edits.append(digest)
        strata = copy.deepcopy(gold)
        support = strata["participants"][0]["stratum_support"]
        a, b = paired.metric.STRATA[:2]
        support[a], support[b] = support[b], support[a]
        edits.append(strata)
        for changed in edits:
            with self.subTest(changed=changed["participants"][0]["pair_digest"]), self.assertRaises(ValueError):
                paired.compare_pair(gold, changed, gold)


class PairedCLITests(unittest.TestCase):
    def run_cli(self, root, first, second, gold, expected, bad_pin=False):
        paths = [root / name for name in ("first.json", "second.json", "reference.json", "result.json")]
        for path, report in zip(paths, (first, second, gold)):
            path.write_text(json.dumps(report))
        gold_pin = hashlib.sha256(paths[2].read_bytes()).hexdigest()
        opened = []
        reader = paired.metric.read_bytes
        def observed(path):
            opened.append(path)
            return reader(path)
        args = ["--first", str(paths[0]), "--second", str(paths[1]), "--gold", str(paths[2]),
                "--gold-sha256", "0" * 64 if bad_pin else gold_pin, "--output", str(paths[3])]
        with mock.patch.object(paired.metric, "read_bytes", side_effect=observed), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(paired.main(args), expected)
        return paths, opened, args

    def test_invalid_second_and_support_mismatch_never_open_reference(self):
        cases = [{}]
        changed = fixture()
        changed["participants"][0]["pair_digest"] = "a" * 64
        cases.append(changed)
        for second in cases:
            with self.subTest(second=second.get("schema")), tempfile.TemporaryDirectory() as folder:
                paths, opened, _ = self.run_cli(Path(folder), fixture(), second, fixture(), 2)
                self.assertEqual(opened, paths[:2])
                self.assertFalse(paths[3].exists())

    def test_one_reference_read_byte_identity_and_fresh_output(self):
        with tempfile.TemporaryDirectory() as folder:
            paths, opened, args = self.run_cli(Path(folder), fixture([1] * 8), fixture([2] * 8), fixture(), 0)
            self.assertEqual(opened, paths[:3])
            result = json.loads(paths[3].read_text())
            self.assertEqual(result["input_sha256"], {
                key: hashlib.sha256(path.read_bytes()).hexdigest()
                for key, path in zip(("first", "second", "reference"), paths[:3])})
            self.assertEqual(result["paired_primary"]["required_participants"], 8)
            before = paths[3].read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(paired.main(args), 2)
            self.assertEqual(paths[3].read_bytes(), before)

    def test_reference_pin_failure_publishes_no_output(self):
        with tempfile.TemporaryDirectory() as folder:
            paths, opened, _ = self.run_cli(Path(folder), fixture(), fixture(), fixture(), 2, bad_pin=True)
            self.assertEqual(opened, paths[:3])
            self.assertFalse(paths[3].exists())


if __name__ == "__main__":
    unittest.main()
