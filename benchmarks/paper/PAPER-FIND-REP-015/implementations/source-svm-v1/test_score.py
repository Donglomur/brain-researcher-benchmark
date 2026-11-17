"""Generated controls only; no source trial data, labels, or model execution."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("cerebellar_svm_score", Path(__file__).with_name("score.py"))
score = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score)


def packets(region="DCN"):
    reference = {"schema": "cerebellar-source-test-v1", "region": region, "units": []}
    candidate = {"schema": "cerebellar-decisions-v1", "region": region, "units": []}
    author = copy.deepcopy(candidate)
    for uid in range(1, score.REGION_UNITS[region] + 1):
        # Four or eight rows: different trial counts make pooling distinguishable.
        labels = [1, 1, 0, 0] * (2 if uid == 1 else 1)
        reference["units"].append({"unit_id": uid, "trials": [
            {"trial_id": str(i), "reward": y} for i, y in enumerate(labels)]})
        candidate["units"].append({"unit_id": uid, "trials": [
            {"trial_id": str(i), "decision": y} for i, y in enumerate(labels)]})
        author["units"].append({"unit_id": uid, "trials": [
            {"trial_id": str(i), "decision": (i % 2)} for i in range(len(labels))]})
    return reference, candidate, author


class SourceMetricsTests(unittest.TestCase):
    def test_complete_source_regions_and_paired_metrics(self):
        for region, count in (("DCN", 1006), ("VTA", 22)):
            report = score.score_pair(*packets(region))
            self.assertEqual(report["unit_count"], count)
            self.assertEqual(report["candidate"], dict.fromkeys(score.METRICS, 1.0))
            self.assertEqual(report["author"], dict.fromkeys(score.METRICS, 0.5))
            self.assertEqual(report["improvement_delta"], dict.fromkeys(score.METRICS, 0.5))
            self.assertEqual(report["reproduction_mean_absolute_metric_error"], dict.fromkeys(score.METRICS, 0.5))

    def test_source_means_units_instead_of_trials(self):
        reference, candidate, author = packets()
        for trial in candidate["units"][0]["trials"]:
            trial["decision"] = 1 - trial["decision"]
        report = score.score_pair(reference, candidate, author)
        self.assertAlmostEqual(report["candidate"]["accuracy"], 1005 / 1006)
        self.assertNotAlmostEqual(report["candidate"]["accuracy"], 4020 / 4028)

    def test_reproduction_error_does_not_cancel(self):
        reference, candidate, author = packets("VTA")
        for trial in candidate["units"][0]["trials"]:
            trial["decision"] = 1 - trial["decision"]
        report = score.score_pair(reference, candidate, author)
        self.assertEqual(report["reproduction_mean_absolute_metric_error"]["accuracy"], 0.5)
        self.assertAlmostEqual(report["improvement_delta"]["accuracy"], 10 / 22)

    def test_reordered_records_align_by_identity(self):
        reference, candidate, author = packets("VTA")
        original = score.score_pair(reference, candidate, author)
        candidate["units"].reverse()
        for unit in candidate["units"]:
            unit["trials"].reverse()
        self.assertEqual(original, score.score_pair(reference, candidate, author))

    def test_missing_unit_is_rejected(self):
        reference, candidate, author = packets()
        candidate["units"].pop()
        with self.assertRaisesRegex(ValueError, "Complete original"):
            score.score_pair(reference, candidate, author)

    def test_same_count_wrong_trial_identity_is_rejected(self):
        reference, candidate, author = packets("VTA")
        author["units"][-1]["trials"][-1]["trial_id"] = "wrong-source-trial"
        with self.assertRaisesRegex(ValueError, "test IDs must match"):
            score.score_pair(reference, candidate, author)

    def test_duplicate_trials_and_units_are_rejected(self):
        for mutate in (lambda c: c["units"].append(copy.deepcopy(c["units"][0])),
                       lambda c: c["units"][0]["trials"].append(copy.deepcopy(c["units"][0]["trials"][0]))):
            reference, candidate, author = packets("VTA")
            mutate(candidate)
            with self.assertRaises(ValueError):
                score.score_pair(reference, candidate, author)

    def test_no_region_pooling(self):
        reference, candidate, author = packets("DCN")
        candidate["region"] = "VTA"
        with self.assertRaisesRegex(ValueError, "source region"):
            score.score_pair(reference, candidate, author)

    def test_unknown_zero_division_policy_is_explicit(self):
        reference, candidate, author = packets("VTA")
        for trial in candidate["units"][0]["trials"]:
            trial["decision"] = 0
        report = score.score_pair(reference, candidate, author)
        self.assertIsNone(report["candidate"]["precision"])
        self.assertIsNone(report["improvement_delta"]["precision"])
        self.assertEqual(report["units"][0]["candidate"]["sensitivity"], 0.0)
        self.assertEqual(report["units"][0]["candidate"]["f1"], 0.0)

    def test_nonbinary_and_boolean_values_rejected(self):
        for value in (True, 1.0, "1", -1, 2):
            reference, candidate, author = packets("VTA")
            candidate["units"][0]["trials"][0]["decision"] = value
            with self.assertRaisesRegex(ValueError, "integer 0 or 1"):
                score.score_pair(reference, candidate, author)


if __name__ == "__main__":
    unittest.main()
