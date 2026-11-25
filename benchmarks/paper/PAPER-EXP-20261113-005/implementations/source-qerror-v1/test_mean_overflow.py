"""Generated complete-population controls; no authentic source measurements."""
from fractions import Fraction
import importlib.util
import math
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location("qerror_mean_control", Path(__file__).with_name("qerror.py"))
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


def complete_packet(pfc_value=0., other_value=0.):
    """Invented values with every declared unit, recording and panel count."""
    units = []
    for i in range(19186):
        pfc = i < 10413
        record = i % 99
        units.append({"unit_id": f"unit-{i}", "recording_id": f"record-{record}",
                      "animal_id": f"animal-{record // 3}",
                      "region": "MOs1" if pfc else "MOp1", "area": "MOs" if pfc else "MOp",
                      "features": [pfc_value if pfc else other_value, 0., 0.]})
    return {"schema": "pfc-source-qerror-packet/v1", "task_id": "PAPER-EXP-20261113-005",
            "source_run": "runC00dMP3_brain", "feature_names": ["B_mean", "M_mean", "rate_mean"],
            "feature_space": "author-loader-output-before-standardization",
            "reference_mean": [0., 0., 0.], "reference_std": [1., 1., 1.],
            "feature_weights": [1., 1., 1.],
            "source_map": {"topology": "hex", "kshape": [1, 2],
                           "prototypes": [[0., 0., 0.], [other_value, 0., 0.]]},
            "units": units, "panel_counts": {"ED2c": {"MOs": 10413},
                                             "ED2d": {"PFC": 10413, "MO": 8773}}}


class MeanOverflowControls(unittest.TestCase):
    def test_complete_panel_finite_candidate_mean_survives_sum_overflow(self):
        packet = complete_packet()
        candidate = {"topology": "hex", "kshape": [1, 2], "prototypes": [[1e308, 0., 0.]] * 2}
        result = q.score(packet, candidate)
        self.assertEqual(result["n_units"], 19186)
        self.assertEqual(result["diagnostic_all_unit_mean"], {"source": 0., "candidate": 1e308})
        for regions in result["panels"].values():
            for region in regions.values():
                self.assertEqual(region["candidate"]["median"], 1e308)
                self.assertEqual(region["candidate_minus_source_median"], 1e308)
        self.assertIsNone(result["paper_win"])

    def test_complete_unequal_groups_match_exact_mean(self):
        packet = complete_packet(other_value=1e308)
        candidate = {"topology": "hex", "kshape": [1, 2], "prototypes": [[1e308, 0., 0.]] * 2}
        result = q.score(packet, candidate)
        exact = float(Fraction(1e308) * Fraction(10413, 19186))
        actual = result["diagnostic_all_unit_mean"]["candidate"]
        self.assertLessEqual(abs(actual - exact), math.ulp(exact))
        self.assertEqual(result["panels"]["ED2d"]["PFC"]["candidate"]["median"], 1e308)
        self.assertEqual(result["panels"]["ED2d"]["MO"]["candidate"]["median"], 0.)

    def test_ordinary_complete_population_retains_original_mean(self):
        packet = complete_packet(pfc_value=3., other_value=7.)
        candidate = {"topology": "hex", "kshape": [1, 2], "prototypes": [[1., 0., 0.]] * 2}
        result = q.score(packet, candidate)
        expected = math.fsum([2.] * 10413 + [6.] * 8773) / 19186
        self.assertEqual(result["diagnostic_all_unit_mean"]["candidate"], expected)


if __name__ == "__main__":
    unittest.main()
