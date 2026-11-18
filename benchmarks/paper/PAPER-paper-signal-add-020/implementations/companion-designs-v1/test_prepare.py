"""Generated controls: source-row support and actual design arithmetic, no data fits."""
from __future__ import annotations

import copy
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("erp_companion_prepare", Path(__file__).with_name("prepare.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture():
    rows = []
    for index in range(1, 7):
        rows.append({
            "source_row": str(index), "sub": "A" if index <= 3 else "B",
            "trialGlobal": str(index), "epe_valence_s": "1.0", "choice_num": str(index % 2),
            "trialLocal": str((index - 1) % 5 + 1), "abs_rpe_s": "2.25",
            "abs_epe_valence_s": "3.25", "abs_epe_arousal_s": "4.25",
            "FRN_N2_offer_s": "-0.25", "P2_offer_s": "0.50", "P2_base_offer_s": "0.75",
            "P3a_offer_s": "1.25", "P3a_base_offer_s": "-1.50",
            "P3b_offer_s": "2.50", "P3b_base_offer_s": "-2.75",
        })
    return rows


class CompanionDesignTests(unittest.TestCase):
    def test_exact_eight_unconditional_and_three_choice_parameterizations(self):
        models = m.build_designs(fixture())
        self.assertEqual(len(models), 11)
        self.assertEqual(sum("unconditional" in name for name in models), 8)
        self.assertNotIn("P3b_unconditional_3", models)
        frn = models["FRN_unconditional_1"]
        self.assertEqual(frn["rows"][0]["x"], [1.0, 2.25, 0.5, 0.75])
        self.assertEqual(frn["rows"][0]["random_block"], [1.0, 0.5, 0.75])
        p3a = models["P3a_unconditional_3"]
        self.assertEqual(p3a["rows"][0]["x"], [1.0, 4.25, -1.5])
        self.assertEqual(p3a["rows"][0]["random_block"], [1.0, -1.5])

    def test_model_specific_masks_not_conditional_intersection(self):
        rows = fixture()
        rows[0]["abs_epe_arousal_s"] = "NA"
        rows[1]["P2_base_offer_s"] = "NA"
        rows[2]["P3a_base_offer_s"] = "NA"
        rows[3]["choice_num"] = "NA"
        models = m.build_designs(rows)
        ids = lambda name: [r["source"]["source_row"] for r in models[name]["rows"]]
        self.assertEqual(ids("FRN_unconditional_1"), ["1", "3", "4", "5", "6"])
        self.assertEqual(ids("FRN_unconditional_3"), ["3", "4", "5", "6"])
        self.assertEqual(ids("P3a_unconditional_1"), ["1", "2", "4", "5", "6"])
        self.assertEqual(ids("choice_original"), ["1", "2", "3", "5", "6"])
        self.assertEqual(ids("P3b_unconditional_1"), ["1", "2", "3", "4", "5", "6"])

    def test_first_valence_filter_precedes_model_finite_validation(self):
        rows = fixture()
        rows[0]["epe_valence_s"] = "NA"
        rows[0]["P2_offer_s"] = "inf"
        models = m.build_designs(rows)
        self.assertTrue(all(model["excluded_missing_valence_pe"] == 1 for model in models.values()))
        self.assertTrue(all(model["rows"][0]["source"]["source_row"] == "2" for model in models.values()))
        rows[0]["epe_valence_s"] = "0"
        with self.assertRaises(m.PreparationError):
            m.build_designs(rows)

    def test_round_centering_preserves_linear_predictor_and_source_values(self):
        models = m.build_designs(fixture())
        original = models["choice_original"]
        beta = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1]
        for name, center in [("choice_round1", 1), ("choice_round5", 5)]:
            shifted = beta.copy()
            shifted[0] += center * beta[2]
            for main, interaction in [(1, 6), (3, 7), (4, 8), (5, 9)]:
                shifted[main] += center * beta[interaction]
            for left, right in zip(original["rows"], models[name]["rows"]):
                self.assertEqual(left["source"], right["source"])
                self.assertEqual(left["random_block"], right["random_block"])
                a = sum(b * x for b, x in zip(beta, left["x"]))
                b = sum(c * x for c, x in zip(shifted, right["x"]))
                self.assertAlmostEqual(a, b)

    def test_order_identity_cohort_and_schema_fail_closed(self):
        for mutation in ("order", "duplicate", "schema", "typed", "empty"):
            rows = fixture()
            if mutation == "order": rows.reverse()
            if mutation == "duplicate": rows[1]["trialGlobal"] = rows[0]["trialGlobal"]
            if mutation == "schema": del rows[0]["P3b_base_offer_s"]
            if mutation == "typed": rows[0]["abs_rpe_s"] = 2.0
            if mutation == "empty": rows = []
            with self.subTest(mutation=mutation), self.assertRaises(m.PreparationError):
                m.build_designs(rows)

    def test_choice_invalid_binary_round_and_nonfinite_product_rejected(self):
        for column, value in [("choice_num", "0.5"), ("trialLocal", "0"),
                              ("trialLocal", "2.5"), ("P3b_offer_s", "1e308")]:
            rows = fixture()
            rows[4][column] = value
            with self.subTest(column=column, value=value), self.assertRaises(m.PreparationError):
                m.build_designs(rows)

    def test_empty_required_model_rejected_not_dropped(self):
        rows = fixture()
        for row in rows: row["abs_epe_arousal_s"] = "NA"
        with self.assertRaises(m.PreparationError):
            m.build_designs(rows)

    def test_export_full_support_hashes_and_existing_output_preserved(self):
        models = m.build_designs(fixture())
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp).resolve() / "fresh"
            report = m.export_designs(models, output, {"sources": []})
            self.assertEqual(len(list(output.iterdir())), 34)
            self.assertEqual(report["qualification"], "input_designs_only_no_fit_or_score")
            for name, model in report["models"].items():
                for artifact in model["outputs"]:
                    body = (output / artifact["name"]).read_bytes()
                    self.assertEqual(len(body), artifact["bytes"])
                    self.assertEqual(hashlib.sha256(body).hexdigest(), artifact["sha256"])
                    self.assertEqual(len(list(csv.reader(body.decode().splitlines()))) - 1, 6)
            before = (output / "receipt.json").read_bytes()
            with self.assertRaises(m.PreparationError):
                m.export_designs(models, output, {"sources": []})
            self.assertEqual((output / "receipt.json").read_bytes(), before)
            broken = dict(models)
            del broken["choice_round5"]
            with self.assertRaises(m.PreparationError):
                m.export_designs(broken, Path(temp).resolve() / "missing", {})


if __name__ == "__main__":
    unittest.main(verbosity=1)
