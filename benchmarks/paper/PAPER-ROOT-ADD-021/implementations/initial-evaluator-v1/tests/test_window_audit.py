"""Generated lineage controls, not source-paper reproduction evidence."""
import importlib.util
import math
from pathlib import Path
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("window_audit_evaluator", ROOT / "evaluator.py")
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def row(pid="p1", region="Postcentral_gyrus", time=0, paf=8, tau=25, fit0=0, age=8):
    return dict(ID=pid, age=age, region=region, time=time, fit0=fit0,
                PAF=paf, PAA=.3, INT=tau, offset=-1, knee=1, exp=2)


class WindowAuditTests(unittest.TestCase):
    def test_mask_refill_support_is_metric_specific_and_never_cascades(self):
        rows = [row(time=0, paf=4, tau=float("nan")),
                row(time=1, paf=6, tau=20, fit0=.2),
                row(time=2, paf=float("nan"), tau=30),
                row(time=3, paf=10, tau=40)]
        report = e.analyze(rows, ["p1"])
        audit = report["parameter_window_audit"]
        at_one = audit[1]
        self.assertFalse(at_one["fit0_pass"])
        self.assertEqual(at_one["raw_parameters"]["PAF"], 6)
        self.assertTrue(math.isnan(at_one["PAF"]["post_qc"]))
        self.assertTrue(at_one["PAF"]["filled_after_masking"])
        self.assertEqual([c["key"][2] for c in at_one["PAF"]["contributors"]], [0, 3])
        self.assertEqual([c["key"][2] for c in at_one["INT"]["contributors"]], [2, 3])
        self.assertEqual([k[2] for k in at_one["smoothing_window_keys"]], [0, 1, 2, 3])
        # Independent two-point result; source 1 is excluded despite its refill.
        expected = (4 * math.exp(-.5) + 10 * math.exp(-2)) / (math.exp(-.5) + math.exp(-2))
        self.assertAlmostEqual(at_one["PAF"]["smoothed"], expected)
        for entry in audit:
            for metric in e.METRICS:
                self.assertNotIn(1, [c["key"][2] for c in entry[metric]["contributors"]])

    def test_edges_and_all_missing_windows_are_retained(self):
        rows = [row(time=i, paf=float("nan"), tau=float("nan")) for i in range(7)]
        audit = e.analyze(rows, ["p1"])["parameter_window_audit"]
        self.assertEqual(len(audit), 7)
        self.assertEqual([k[2] for k in audit[0]["smoothing_window_keys"]], [0, 1, 2])
        self.assertEqual([k[2] for k in audit[-1]["smoothing_window_keys"]], [4, 5, 6])
        self.assertEqual(len(audit[3]["smoothing_window_keys"]), 5)
        for entry in audit:
            for metric in e.METRICS:
                self.assertEqual(entry[metric]["contributors"], [])
                self.assertTrue(math.isnan(entry[metric]["smoothed"]))
                self.assertFalse(entry[metric]["filled_after_masking"])
        serialized = e.json_safe(audit)
        self.assertIsNone(serialized[0]["PAF"]["smoothed"])

    def test_complete_variable_coverage_reconstructs_every_source_summary(self):
        rows = []
        roster = [f"generated_{i:02d}" for i in range(13)]
        regions = list(e.REGIONS)
        for i, pid in enumerate(roster):
            for j in range(1 + i % 6):
                for t in range(1 + (i + j) % 5):
                    rows.append(row(pid, regions[j], t * .25, 5 + .1*i + .3*j + .05*t,
                                    20 + .4*i + .6*j + .2*t, .2 if t == 1 else 0, 4+i))
        report = e.analyze(list(reversed(rows)), roster)
        audit = report["parameter_window_audit"]
        self.assertEqual(len(audit), len(rows))
        self.assertEqual({r["ID"] for r in audit}, set(roster))
        source = {(r["ID"], r["region"], r["time"]): r for r in rows}
        for entry in audit:
            key = (entry["ID"], entry["region"], entry["time"])
            self.assertEqual(entry["raw_parameters"], {k: source[key][k] for k in ("fit0", "PAF", "PAA", "INT", "offset", "knee", "exp")})
            for metric in e.METRICS:
                contributors = entry[metric]["contributors"]
                self.assertTrue(all(c["key"][:2] == list(key[:2]) for c in contributors))
                if contributors:
                    self.assertAlmostEqual(sum(c["normalized_weight"] for c in contributors), 1)
                    reconstructed = sum(source[tuple(c["key"])][metric]*c["normalized_weight"] for c in contributors)
                    self.assertAlmostEqual(reconstructed, entry[metric]["smoothed"])
        families = [("participant_region", ("ID", "region", "ctx")),
                    ("participant_context_pooled_time_rows", ("ID", "ctx")),
                    ("participant_omnibus_pooled_time_rows", ("ID",))]
        for family, fields in families:
            for summary in report[family]:
                matching = [r for r in audit if all(r[f] == summary[f] for f in fields)]
                self.assertEqual(len(matching), summary["rows"])
                for metric in e.METRICS:
                    values = [r[metric]["smoothed"] for r in matching if math.isfinite(r[metric]["smoothed"])]
                    self.assertEqual(len(values), summary[metric + "_n"])
                    self.assertAlmostEqual(sum(values)/len(values), summary[metric])
                    self.assertAlmostEqual(float(np.percentile(values, 25)), summary[metric + "_q25"])
                    self.assertAlmostEqual(float(np.percentile(values, 75)), summary[metric + "_q75"])
        self.assertEqual(e.json_safe(report), e.json_safe(e.analyze(rows, roster)))
        self.assertFalse(report["scientifically_qualified"])


if __name__ == "__main__":
    unittest.main()
