"""Generated controls for representable Brier losses near binary64 underflow."""
import math
from fractions import Fraction
import unittest

import scorer
from test_scorer import invented_intake


class BrierSubnormalControls(unittest.TestCase):
    def test_complete_roster_retains_representable_tiny_brier(self):
        intake = invented_intake()
        tiny = 1e-162
        expected = float(7 * Fraction(tiny) ** 2)
        self.assertGreater(expected, 0.0)
        predictions = []
        for record in intake["records"]:
            for trial in record["trials"][8:]:
                probabilities = [tiny] * 8
                probabilities[trial["direction"]] = 1.0
                predictions.append({"query_id": trial["query_id"], "probabilities": probabilities})
        report = scorer.evaluate(intake, predictions, condition="program_B")
        self.assertEqual(report["queries"], 20238)
        self.assertEqual(report["primary"], 1.0)
        self.assertEqual(report["overall"]["equal_animal_mean"]["brier"], expected)
        self.assertTrue(all(row["brier"] == expected for row in report["sessions"]))

    def test_tiny_brier_matches_exact_binary_operands(self):
        queries = [{"query_id": str(i), "direction": i} for i in range(8)]
        for tiny in (0.0, math.ulp(0.0), 1e-162, 2e-162, 1e-160):
            values = {}
            for i in range(8):
                probabilities = [tiny] * 8
                probabilities[i] = 1.0
                values[str(i)] = probabilities
            report = scorer.session_score(queries, values, False)
            self.assertEqual(report["brier"], float(7 * Fraction(tiny) ** 2))
            self.assertEqual(report["balanced_accuracy"], 1.0)

    def test_ordinary_and_invalid_losses_keep_declared_values(self):
        queries = [{"query_id": str(i), "direction": i} for i in range(8)]
        uniform = {str(i): [0.125] * 8 for i in range(8)}
        report = scorer.session_score(queries, uniform, False)
        self.assertEqual(report["brier"], 0.875)
        self.assertEqual(report["balanced_accuracy"], 0.125)
        invalid = scorer.session_score(queries, {}, True)
        self.assertEqual(invalid["brier"], 2.0)
        self.assertEqual(invalid["invalid_by_class"], [1] * 8)


if __name__ == "__main__":
    unittest.main()
