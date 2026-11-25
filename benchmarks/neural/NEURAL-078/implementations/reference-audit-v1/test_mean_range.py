"""Generated complete-packet arithmetic controls; no recordings or gold."""
import importlib.util
import math
from pathlib import Path
import unittest


_spec = importlib.util.spec_from_file_location(
    "neural078_audit_mean_fixture", Path(__file__).with_name("test_audit.py"))
fixture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fixture)
audit, core = fixture.audit, fixture.core


class MeanRangeTests(unittest.TestCase):
    def test_complete_eight_person_audit_preserves_subnormal_contrast(self):
        value = math.ulp(0.0)
        report, comparison = audit.audit_packets(
            ((person, fixture.packet(person, value)) for person in audit.PEOPLE), core)
        self.assertEqual(comparison["checked_fields"], 195)
        self.assertEqual(len(report["participants"]), 8)
        for row in report["participants"]:
            self.assertEqual(row["matched_pairs_n"], 12)
            self.assertEqual(row["matched_FCz_contrast"], value)
            self.assertEqual(row["unmatched_FCz_contrast"], value)
        self.assertEqual(report["aggregate"][audit.AGGREGATES[0]], value)

    def test_representable_small_large_and_cancelling_means(self):
        smallest = math.ulp(0.0)
        largest = float.fromhex("0x1.fffffffffffffp+1023")
        for value in (smallest, -smallest, largest, -largest):
            with self.subTest(value=value):
                self.assertEqual(audit.mean([value] * 103), value)
        self.assertEqual(audit.mean([largest, largest, -largest, -largest]), 0)

    def test_nonrepresentable_nonzero_mean_is_not_false_zero(self):
        with self.assertRaisesRegex(ValueError, "representable arithmetic"):
            audit.mean([math.ulp(0.0), 0.0])
        self.assertEqual(audit.mean([0.0] * 103), 0)

    def test_normal_complete_panel_keeps_declared_analytic_values(self):
        values = [-2, -1, 0, 1, 2, 3, 4, 5]
        report, comparison = audit.audit_packets(
            ((p, fixture.packet(p, v)) for p, v in zip(audit.PEOPLE, values)), core)
        self.assertEqual(comparison["checked_fields"], 195)
        self.assertEqual(report["aggregate"][audit.AGGREGATES[0]], 1.5)
        self.assertAlmostEqual(report["aggregate"][audit.AGGREGATES[1]], math.sqrt(0.75))
        for row, value in zip(report["participants"], values):
            self.assertEqual(row["matched_FCz_contrast"], value)
            self.assertEqual(row["unmatched_FCz_contrast"], value)
            self.assertEqual(row["matched_HEOG_contrast"], 2)
            self.assertEqual(row["matched_VEOG_contrast"], -3)
            self.assertEqual(row["matched_preresponse_FCz_placebo"], -4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
