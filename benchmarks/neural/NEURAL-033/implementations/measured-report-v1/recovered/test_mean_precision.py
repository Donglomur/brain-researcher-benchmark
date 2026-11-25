"""Generated complete-report underflow controls, with no fits or source data."""
import copy
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("neural033_mean_under_test", Path(__file__).with_name("score.py"))
score = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(score)
TINY = float.fromhex("0x0.0000000000001p-1022")


def complete_report():
    group = dict(row_ids=["r0", "r1", "r2"], mice=["m0", "m1"], n_rows=3, n_mice=2,
                 effective_mice=2.0, rank=3, coefficients=dict(intercept=0.0, activity_rank=0.0, baseline_rank=0.0),
                 status="defined", reason=None)
    contrast = dict(estimate=0.0, jackknife_se=0.0, deletion_min=0.0, deletion_max=0.0, uncertainty_status="defined")
    panels = {}
    for name in ("all", "balanced"):
        panels[name] = dict(groups={g: copy.deepcopy(group) for g in score.GROUPS},
            matched_bin_mass={} if name == "all" else {g: [0.0] * 9 for g in ("apical", "basal")},
            contrasts={c: copy.deepcopy(contrast) for c in score.CONTRASTS},
            delete_one_mouse={m: {c: 0.0 for c in score.CONTRASTS} for m in ("m0", "m1")})
    expected = dict(excluded=[], eligible_row_ids=["r0", "r1", "r2"], panels=panels)
    packet = dict(schema_version=1, task_id="NEURAL-033", contract_sha256="c" * 64,
                  input_sha256="d" * 64, analysis=copy.deepcopy(expected))
    identity = dict(row_ids=["r0", "r1", "r2"], mouse_ids=["m0", "m1"])
    return packet, identity, expected


class MeanPrecisionControls(unittest.TestCase):
    def test_complete_positive_contrast_errors_cannot_receive_zero_grade(self):
        packet, identity, expected = complete_report()
        for panel in packet["analysis"]["panels"].values():
            for contrast in panel["contrasts"].values():
                contrast["estimate"] = TINY
        result, code = score.grade_bytes(score.io.encode(packet), identity, "c" * 64, "d" * 64,
                                        lambda: copy.deepcopy(expected))
        self.assertEqual(code, 0)
        self.assertEqual(result["defined_contrasts"], 6)
        self.assertEqual(result["structural_mismatch_count"], 0)
        self.assertEqual(result["availability_mismatches"], [])
        self.assertEqual(result["primary_normalized_contrast_mae"], TINY)
        self.assertEqual(result["panel_normalized_contrast_mae"], {"all": TINY, "balanced": TINY})

    def test_empty_and_exact_zero_means_preserved(self):
        self.assertIsNone(score.finite_mean([]))
        self.assertEqual(score.finite_mean([0.0, 0.0]), 0.0)
        packet, identity, expected = complete_report()
        result = score.evaluate(packet, identity, "c" * 64, "d" * 64, lambda: expected)
        self.assertEqual(result["primary_normalized_contrast_mae"], 0.0)

    def test_large_finite_mean_stays_representable(self):
        maximum = float.fromhex("0x1.fffffffffffffp+1023")
        self.assertEqual(score.finite_mean([maximum, maximum, maximum]), maximum)


if __name__ == "__main__":
    unittest.main(verbosity=2)
