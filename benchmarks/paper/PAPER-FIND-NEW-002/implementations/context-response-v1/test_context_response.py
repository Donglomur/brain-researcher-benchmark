"""Generated arithmetic/support controls; no authentic recordings or fits."""
import copy
import json
import unittest

import numpy as np

from context_response import reconstruct_responses, CONDITIONS, RESPONSE_NAMES


def fixture():
    experiments = {}
    for i, n in enumerate((9, 13, 10), 1):
        # Use sparse, nonconsecutive ordered cell selections so a hidden crop or
        # sorting of source IDs changes the expected result.
        ids = list(range(2 * n - 1, 0, -2))
        arrays = {key: np.zeros((2 * n + 1, 200), dtype=np.float64) for key in CONDITIONS}
        for cell in range(2 * n + 1):
            arrays["visF1"][cell, 125:128] = 100 + cell
            arrays["vis1OptoF1"][cell, 125:128] = [100 + cell + 2 * i, 100 + cell + 2 * i + 3,
                                                 100 + cell + 2 * i + 6]
            arrays["visF2"][cell, 125:128] = 40 + cell
            arrays["vis2OptoF1"][cell, 125:128] = 40 + cell + i
            arrays["optoF1"][cell, 125:128] = cell
        experiments[f"expt{i}"] = {"conditions": arrays, "stimulated_cell_indices": ids}
    revision = {key: np.zeros((108, 200), dtype=np.float64) for key in RESPONSE_NAMES}
    for key, value in zip(RESPONSE_NAMES, (11.0, 7.0, 5.0)):
        revision[key][:, 123:126] = value
        revision[key][:, 126:128] = 1000  # catches mistaken transfer of old window
    return experiments, revision


class ContextResponseTests(unittest.TestCase):
    def test_full_roster_provenance_and_source_arithmetic(self):
        original, revision = fixture()
        result = reconstruct_responses(original, revision)
        self.assertEqual(result["source_namespace_counts"], {"expt1": 9, "expt2": 13, "expt3": 10, "revision": 108})
        self.assertEqual(len(result["rows"]), 140)
        self.assertEqual(result["rows"][0]["row_id"], "expt1:cell:17")
        self.assertEqual(result["rows"][0]["responses"], {"matched": 5.0, "unmatched": 1.0, "opto_only": 17.0})
        self.assertEqual(result["rows"][9]["row_id"], "expt2:cell:25")
        self.assertEqual(result["rows"][32]["responses"], {"matched": 11.0, "unmatched": 7.0, "opto_only": 5.0})
        self.assertEqual(result["rows"][-1]["row_id"], "revision:row:107")
        self.assertEqual(result["rows"][31]["frame_window"], [125, 128])
        self.assertEqual(result["rows"][32]["frame_window"], [123, 126])

    def test_pooling_is_source_cell_weighting_not_equal_namespace_weighting(self):
        result = reconstruct_responses(*fixture())
        expected = (9 * 5 + 13 * 7 + 10 * 9 + 108 * 11) / 140
        self.assertAlmostEqual(result["pooled_cell_means"]["matched"], expected)
        self.assertNotEqual(result["pooled_cell_means"]["matched"], (5 + 7 + 9 + 11) / 4)

    def test_original_baseline_subtraction_does_not_touch_revision(self):
        original, revision = fixture()
        original["expt1"]["conditions"]["visF1"] += 3
        result = reconstruct_responses(original, revision)
        self.assertEqual(result["rows"][0]["responses"]["matched"], 2.0)
        self.assertEqual(result["rows"][32]["responses"]["matched"], 11.0)

    def test_nonfinite_source_arithmetic_preserved_as_undefined_without_dropping(self):
        original, revision = fixture()
        original["expt1"]["conditions"]["vis1OptoF1"][17, 126] = np.nan
        revision["opto_only"][107, 124] = np.inf
        result = reconstruct_responses(original, revision)
        self.assertEqual(len(result["rows"]), 140)
        self.assertEqual(result["nonfinite_response_count"], 2)
        self.assertIsNone(result["rows"][0]["responses"]["matched"])
        self.assertIsNone(result["pooled_cell_means"]["matched"])
        self.assertEqual(result["source_namespace_means"]["expt2"]["matched"], 7)
        self.assertIsNone(result["pooled_cell_means"]["opto_only"])
        json.dumps(result, allow_nan=False)

    def test_nonfinite_unselected_rows_or_frames_are_not_new_exclusions(self):
        original, revision = fixture()
        original["expt1"]["conditions"]["vis1OptoF1"][0, :] = np.nan
        original["expt1"]["conditions"]["vis1OptoF1"][17, 1] = np.inf
        result = reconstruct_responses(original, revision)
        self.assertEqual(result["nonfinite_response_count"], 0)

    def test_missing_experiment_or_condition_refused(self):
        original, revision = fixture()
        del original["expt3"]
        with self.assertRaises(ValueError): reconstruct_responses(original, revision)
        original, revision = fixture()
        del original["expt1"]["conditions"]["optoF1"]
        with self.assertRaises(ValueError): reconstruct_responses(original, revision)

    def test_duplicate_wrong_count_out_of_bounds_and_noninteger_selections_refused(self):
        for replacement in ([1] * 9, [1] * 8, [100] + list(range(1, 9)),
                            [True] + list(range(1, 9)), [1.0] + list(range(2, 10))):
            original, revision = fixture()
            original["expt1"]["stimulated_cell_indices"] = replacement
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                reconstruct_responses(original, revision)

    def test_revision_subset_and_misaligned_condition_refused(self):
        original, revision = fixture()
        revision["matched"] = revision["matched"][:107]
        with self.assertRaises(ValueError): reconstruct_responses(original, revision)
        original, revision = fixture()
        original["expt2"]["conditions"]["visF2"] = np.zeros((27, 127))
        with self.assertRaises(ValueError): reconstruct_responses(original, revision)

    def test_object_or_complex_inputs_refused_without_deserialization(self):
        for dtype in (object, complex, bool, int):
            original, revision = fixture()
            revision["matched"] = np.zeros((108, 200), dtype=dtype)
            with self.subTest(dtype=dtype), self.assertRaises(ValueError):
                reconstruct_responses(original, revision)

    def test_inputs_unchanged_and_no_scientific_success_claim(self):
        original, revision = fixture()
        before = copy.deepcopy((original, revision))
        result = reconstruct_responses(original, revision)
        for name in original:
            for key in CONDITIONS:
                np.testing.assert_array_equal(original[name]["conditions"][key], before[0][name]["conditions"][key])
        for key in RESPONSE_NAMES:
            np.testing.assert_array_equal(revision[key], before[1][key])
        for flag in ("biological_independent_units_verified", "physical_response_window_verified",
                     "original_data_authenticated_by_this_function", "complete_primary_reproduction_established",
                     "paper_improvement_established"):
            self.assertIs(result[flag], False)
        self.assertIsNone(result["revision_namespace_is_one_independent_experiment"])


if __name__ == "__main__":
    unittest.main()
