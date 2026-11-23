"""Generated numerical/identity controls; no author data or native runtime."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("likelihood_terms", HERE / "likelihood_terms.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def fixture():
    return {"schema": "consensus_supplied_likelihood_terms_v1",
            "units": "expected_spikes_per_bin", "bin_width_seconds": 0.005,
            "records": [{
                "key": {"animal_id": "generated_animal", "fold_id": 0,
                        "model_variant": "constrained", "condition_id": "generated_condition",
                        "target_neuron_id": "generated_neuron", "source_trial_index": 7,
                        "occurrence_index": 0},
                "time_bin_ids": [100, 101, 102], "target_counts": [0, 1, 2],
                "model_expected_counts": [0.5, 1.0, 2.0], "psth_expected_counts": [1., 1., 1.],
                "reported_model_ll_terms": None, "reported_psth_ll_terms": None}]}


class LikelihoodTerms(unittest.TestCase):
    def test_literal_terms_and_totals(self):
        output = module.calculate(fixture())
        row = output["records"][0]
        self.assertEqual(row["model_ll_terms"], [-0.5, -1., 2 * math.log(2) - 2])
        self.assertEqual(row["psth_ll_terms"], [-1., -1., -1.])
        self.assertAlmostEqual(row["residual_ll_sum"], 2 * math.log(2) - 0.5)
        self.assertEqual((row["num_spikes"], row["num_time_bins"]), (3, 3))
        self.assertIsNone(output["paper_figure2b_score"])
        self.assertFalse(output["scientific_qualification"])

    def test_factorials_cancel_only_on_shared_observations(self):
        document = fixture()
        source = document["records"][0]
        row = module.calculate(document)["records"][0]
        def full_logpmf(means):
            return sum(y * math.log(mu) - mu - math.lgamma(y + 1)
                       for y, mu in zip(source["target_counts"], means))
        self.assertAlmostEqual(row["residual_ll_sum"],
                               full_logpmf(source["model_expected_counts"]) -
                               full_logpmf(source["psth_expected_counts"]))
        self.assertAlmostEqual(row["model_ll_sum"] - full_logpmf(source["model_expected_counts"]),
                               math.log(2))

    def test_expected_counts_are_not_scaled_again(self):
        document = fixture()
        document["records"][0]["target_counts"] = [0, 0, 0]
        document["records"][0]["model_expected_counts"] = [1, 1, 1]
        output = module.calculate(document)
        self.assertEqual(output["records"][0]["model_ll_sum"], -3)
        self.assertFalse(output["expected_counts_scaled_again"])
        for field, wrong in (("units", "spikes_per_second"), ("bin_width_seconds", 1),
                             ("bin_width_seconds", True)):
            bad = copy.deepcopy(document); bad[field] = wrong
            with self.subTest(field=field, value=wrong), self.assertRaises(ValueError):
                module.calculate(bad)

    def test_repeated_source_trial_occurrences_stay_distinct(self):
        document = fixture()
        second = copy.deepcopy(document["records"][0])
        second["key"]["occurrence_index"] = 1
        second["target_counts"] = [1, 0, 2]
        document["records"].append(second)
        output = module.calculate(document)
        self.assertEqual([r["key"] for r in output["records"]], [r["key"] for r in document["records"]])
        self.assertEqual([r["key"]["source_trial_index"] for r in output["records"]], [7, 7])
        self.assertNotEqual(output["records"][0]["model_ll_sum"], output["records"][1]["model_ll_sum"])
        self.assertFalse(output["full_panel_coverage_verified"])

    def test_duplicate_keys_and_changed_time_support_are_refused(self):
        document = fixture(); document["records"].append(copy.deepcopy(document["records"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate occurrence"):
            module.calculate(document)
        for bins in ([100, 102, 101], [100, 100, 102], [100, 101], [True, 101, 102]):
            document = fixture(); document["records"][0]["time_bin_ids"] = bins
            with self.subTest(bins=bins), self.assertRaises(ValueError):
                module.calculate(document)

    def test_nonpositive_or_nonfinite_expectations_have_no_smoothing(self):
        for field in ("model_expected_counts", "psth_expected_counts"):
            for bad in (0, -1, float("nan"), float("inf"), True, "1"):
                document = fixture(); document["records"][0][field][0] = bad
                with self.subTest(field=field, value=repr(bad)), self.assertRaises(ValueError):
                    module.calculate(document)

    def test_observation_domain_is_checked_before_rounding(self):
        for bad in (-1, 1.5, True, 2**53 + 1, float("nan"), float("inf"), "1"):
            document = fixture(); document["records"][0]["target_counts"][0] = bad
            with self.subTest(value=repr(bad)), self.assertRaises(ValueError):
                module.calculate(document)

    def test_reported_disagreement_is_descriptive_without_a_threshold(self):
        document = fixture(); row = document["records"][0]
        row["reported_model_ll_terms"] = [-0.25, -1, 2 * math.log(2) - 2]
        row["reported_psth_ll_terms"] = [-1., -1., -1.]
        result = module.calculate(document)["records"][0]
        comparison = result["reported_model_comparison"]
        self.assertEqual(comparison["reported_minus_calculated"], [0.25, 0., 0.])
        self.assertEqual(comparison["max_abs_difference"], 0.25)
        self.assertFalse(comparison["exact_float_equal"])
        self.assertIsNone(comparison["acceptance_tolerance"])
        self.assertTrue(result["reported_psth_comparison"]["exact_float_equal"])

    def test_missing_extra_or_misaligned_values_are_refused(self):
        for field in ("target_counts", "model_expected_counts", "psth_expected_counts",
                      "reported_model_ll_terms", "reported_psth_ll_terms"):
            for value in ([], [1], [1] * 4):
                document = fixture(); document["records"][0][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    module.calculate(document)
        document = fixture(); document["records"][0]["unexpected"] = 1
        with self.assertRaises(ValueError):
            module.calculate(document)

    def test_nonfinite_sums_and_reported_terms_are_refused(self):
        document = fixture(); document["records"][0]["model_expected_counts"] = [1e308] * 3
        with self.assertRaisesRegex(ValueError, "nonfinite LL sum"):
            module.calculate(document)
        document = fixture(); document["records"][0]["reported_model_ll_terms"] = [float("nan"), 0, 0]
        with self.assertRaises(ValueError):
            module.calculate(document)

    def test_parser_rejects_duplicate_fields_and_nonfinite_constants(self):
        for raw in (b'{"schema":1,"schema":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                module.parse_input(raw)

    def test_cli_returns_all_or_no_output(self):
        command = [sys.executable, "-I", "-S", "-B", str(HERE / "likelihood_terms.py")]
        document = fixture()
        result = subprocess.run(command, input=json.dumps(document).encode(), capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["record_count"], 1)
        second = copy.deepcopy(document["records"][0]); second["key"]["occurrence_index"] = 1
        second["psth_expected_counts"][-1] = 0
        document["records"].append(second)
        result = subprocess.run(command, input=json.dumps(document).encode(), capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"native zero-rate policy unresolved", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
