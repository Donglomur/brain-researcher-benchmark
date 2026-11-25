"""Generated complete-answer controls for representable MAE extremes."""
import math
import sys
import unittest

import score as SCORER
from test_support import generated_metadata
from test_trajectory import generated_arrays
from trajectory import build_reference


class ScoreMeanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        metadata = generated_metadata()
        cls.reference = build_reference(metadata, generated_arrays(metadata))
        cls.supported = sum(cell["supported"] for cell in cls.reference["cells"])
        assert cls.supported > 0 and len(cls.reference["cells"]) == 48

    def report(self, error):
        answer = SCORER.expected_answer(self.reference)
        for cell in answer["cells"]:
            if cell["support_status"] == "supported":
                for field in SCORER.NUMERIC_FIELDS:
                    cell[field] = [error] * 4
        return SCORER.grade(self.reference, answer)

    def test_complete_positive_subnormal_errors_remain_positive(self):
        for error in (math.ulp(0.0), 7 * math.ulp(0.0), sys.float_info.min):
            with self.subTest(error=error):
                result = self.report(error)
                self.assertEqual(result["numeric_status"], "complete")
                for metric in result["numeric_errors"].values():
                    self.assertEqual(metric["mean_absolute_error_hz"], error)
                    self.assertEqual(metric["max_absolute_error_hz"], error)
                    self.assertEqual(metric["scored_values"], self.supported * 4)

    def test_finite_largest_errors_have_finite_mean(self):
        result = self.report(sys.float_info.max)
        for metric in result["numeric_errors"].values():
            self.assertEqual(metric["mean_absolute_error_hz"], sys.float_info.max)

    def test_normal_errors_preserve_existing_reduction(self):
        result = self.report(1.25)
        previous = math.fsum(1.25 / (self.supported * 4)
                             for _ in range(self.supported * 4))
        for metric in result["numeric_errors"].values():
            self.assertEqual(metric["mean_absolute_error_hz"], previous)
        self.assertFalse(result["support_error_cells"])
        self.assertFalse(result["count_error_cells"])
        self.assertIsNone(result["binary_win"])

    def test_correct_complete_answer_remains_zero(self):
        result = self.report(0.0)
        for metric in result["numeric_errors"].values():
            self.assertEqual(metric["mean_absolute_error_hz"], 0.0)
        self.assertTrue(result["uncertainty_qualification_correct"])
        self.assertTrue(result["interpretation_scope_correct"])


if __name__ == "__main__":
    unittest.main()
