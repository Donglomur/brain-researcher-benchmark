"""Generated arithmetic, matched-information and complete-answer controls."""
import copy
from fractions import Fraction
import math
import unittest

import numpy as np

from score import expected_answer, grade
from support import validate_metadata
from test_support import generated_metadata
from trajectory import (TrajectoryError, build_reference, matched_observation,
                        quarter_summary, validate_arrays)
from view import render_cell


def generated_arrays(metadata):
    rows = metadata["trials"]
    edges = np.asarray([[float(Fraction(row["set_time"]) +
                               (Fraction(row["go_time"]) - Fraction(row["set_time"])) * k / 20)
                         for k in range(21)] for row in rows], dtype="<f8")
    return {"counts": np.zeros((204, 54, 20), dtype="<u4"),
            "phase_edges_seconds": edges, "exposure_seconds": np.diff(edges, axis=1),
            "trial_ids": np.asarray([row["trial_id"] for row in rows], dtype="<i8"),
            "unit_ids": np.asarray(metadata["unit_ids"], dtype="<i8"),
            "nlb_heldout_unit_flags": np.asarray(metadata["nlb_heldout_unit_flags"], dtype="u1")}


class TrajectoryTests(unittest.TestCase):
    def test_signed_quarters_distinguish_superseded_reversal_counterexample(self):
        forward = np.tile([2.0] * 5 + [1.0] * 5 + [-1.0] * 5 + [-2.0] * 5, (54, 1))
        reverse = -forward
        a, b = quarter_summary(forward), quarter_summary(reverse)
        self.assertEqual(a["quarter_rms_hz"], b["quarter_rms_hz"])
        self.assertEqual(float(np.mean(forward)), float(np.mean(reverse)))
        self.assertEqual(a["quarter_signed_mean_hz"], [2.0, 1.0, -1.0, -2.0])
        self.assertEqual(b["quarter_signed_mean_hz"], [-2.0, -1.0, 1.0, 2.0])

    def test_unit_cancellation_does_not_erase_rms(self):
        difference = np.vstack((np.full((27, 20), 3.0), np.full((27, 20), -3.0)))
        result = quarter_summary(difference)
        self.assertEqual(result["quarter_signed_mean_hz"], [0.0] * 4)
        self.assertEqual(result["quarter_rms_hz"], [3.0] * 4)

    def test_equal_trial_rates_and_long_minus_short_orientation(self):
        metadata = generated_metadata()
        support = validate_metadata(metadata)
        cell = next(cell for cell in support["cells"]
                    if cell["cell_id"] == "train-segment3-eye0-direction0")
        selected = cell["long_trial_indices"]
        first = metadata["trials"][selected[0]]
        first["go_time"] = first["set_time"] + 0.5
        first["observed_production_interval_seconds"] = 0.5
        arrays = generated_arrays(metadata)
        arrays["counts"][selected[0], :, :] = 1
        arrays["counts"][selected[1], :, :] = 1
        reference = build_reference(metadata, arrays)
        result = next(row for row in reference["cells"] if row["cell_id"] == cell["cell_id"])
        expected = [math.fsum(float(arrays["counts"][i, 0, t]) /
                              float(arrays["exposure_seconds"][i, t]) for i in selected) / len(selected)
                    for t in range(20)]
        np.testing.assert_allclose(result["difference_hz"][0], expected, rtol=0, atol=1e-13)
        pooled = 2.0 / math.fsum(float(arrays["exposure_seconds"][i, 0]) for i in selected)
        self.assertGreater(abs(expected[0] - pooled), 1.0)
        self.assertTrue(all(value > 0 for value in result["summary"]["quarter_signed_mean_hz"]))

    def test_complete_support_projection_withholds_answers_and_is_detached(self):
        metadata = generated_metadata()
        reference = build_reference(metadata, generated_arrays(metadata))
        observation = matched_observation(reference)
        self.assertEqual(len(observation["cells"]), 48)
        self.assertTrue(any(cell["summary"] is None for cell in reference["cells"]))
        self.assertTrue(all("summary" not in cell and "difference_hz" not in cell
                            and "long_trial_indices" not in cell for cell in observation["cells"]))
        first = next(cell for cell in observation["cells"] if cell["long_rate_hz"] is not None)
        original = next(cell for cell in reference["cells"] if cell["cell_id"] == first["cell_id"])
        first["long_rate_hz"][0][0] = 123.0
        self.assertEqual(original["long_rate_hz"][0][0], 0.0)
        self.assertIsNone(reference["complete_support_aggregate"])

    def test_generated_full_pipeline_to_viewer_and_continuous_grade(self):
        metadata = generated_metadata()
        arrays = generated_arrays(metadata)
        arrays["counts"][:] = 1
        reference = build_reference(metadata, arrays)
        observation = matched_observation(reference)
        image = render_cell(observation, observation["cells"][0]["cell_id"])
        self.assertTrue(image.startswith(b"<svg"))
        answer = expected_answer(reference)
        result = grade(reference, answer)
        self.assertEqual(result["numeric_status"], "complete")
        self.assertEqual(result["numeric_errors"]["quarter_rms_hz"]["mean_absolute_error_hz"], 0)
        self.assertTrue(result["uncertainty_qualification_correct"])
        self.assertFalse(result["support_error_cells"])
        self.assertIsNone(result["binary_win"])
        self.assertEqual(reference["prior_orientation"], "long minus short")

    def test_wrong_or_missing_scientific_answers_do_not_obtain_zero_error(self):
        metadata = generated_metadata()
        reference = build_reference(metadata, generated_arrays(metadata))
        answer = expected_answer(reference)
        supported = next(cell for cell in answer["cells"] if cell["support_status"] == "supported")
        supported["quarter_signed_mean_hz"][0] = -8.0
        result = grade(reference, answer)
        self.assertGreater(result["numeric_errors"]["quarter_signed_mean_hz"]["mean_absolute_error_hz"], 0)
        answer["uncertainty"] = {"status": "qualified", "reason_codes": []}
        answer["interpretation_scope"] = "population_generalization"
        result = grade(reference, answer)
        self.assertFalse(result["uncertainty_qualification_correct"])
        self.assertFalse(result["interpretation_scope_correct"])
        supported["support_status"] = "unsupported"
        supported["quarter_signed_mean_hz"] = supported["quarter_rms_hz"] = None
        result = grade(reference, answer)
        self.assertEqual(result["numeric_status"], "missing_supported_cell_estimates")
        self.assertTrue(all(value is None for value in result["numeric_errors"].values()))

    def test_exposure_identity_and_missing_output_refusals(self):
        metadata = generated_metadata()
        validated = validate_metadata(metadata)
        arrays = generated_arrays(metadata)
        arrays["exposure_seconds"][0, 0] *= 2
        with self.assertRaisesRegex(TrajectoryError, "exposure differs"):
            validate_arrays(validated, arrays)
        arrays = generated_arrays(metadata)
        arrays["unit_ids"] = arrays["unit_ids"][::-1].copy()
        with self.assertRaisesRegex(TrajectoryError, "unit identity"):
            validate_arrays(validated, arrays)
        reference = build_reference(metadata, generated_arrays(metadata))
        answer = expected_answer(reference)
        answer["cells"].pop()
        with self.assertRaisesRegex(TrajectoryError, "complete cell roster"):
            grade(reference, answer)

    def test_nonfinite_boolean_and_unsupported_zero_fill_refusals(self):
        metadata = generated_metadata()
        reference = build_reference(metadata, generated_arrays(metadata))
        for value in (True, float("nan"), float("inf")):
            answer = expected_answer(reference)
            cell = next(row for row in answer["cells"] if row["support_status"] == "supported")
            cell["quarter_signed_mean_hz"][0] = value
            with self.subTest(value=value), self.assertRaises(TrajectoryError):
                grade(reference, answer)
        answer = expected_answer(reference)
        cell = next(row for row in answer["cells"] if row["support_status"] == "unsupported")
        cell["quarter_rms_hz"] = [0.0] * 4
        with self.assertRaisesRegex(TrajectoryError, "must be null"):
            grade(reference, answer)


if __name__ == "__main__":
    unittest.main()
