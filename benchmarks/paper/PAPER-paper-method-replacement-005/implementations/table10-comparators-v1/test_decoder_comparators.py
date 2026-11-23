"""Generated controls for the original decoder incidence; no native execution."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("decoder_comparators", HERE / "decoder_comparators.py")
panel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panel)
IMPLEMENTATIONS = HERE.parent


class DecoderComparatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge, directory = panel.load_bridge(IMPLEMENTATIONS)
        cls.evaluator = cls.bridge.load_evaluator(directory)
        spec = importlib.util.spec_from_file_location("neds_bridge_controls",
            IMPLEMENTATIONS / "native-output-bridge-v1" / "test_native_output_bridge.py")
        fixture_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture_module)
        cls.bundle, cls.paired = fixture_module.fixture(cls.evaluator)
        roster = cls.evaluator.load_roster()
        records = []
        for session in cls.bundle["sessions"]:
            if session["eid"] not in roster["heldout_eids"]:
                continue
            for method in panel.METHODS:
                predictions = {field: copy.deepcopy(session["test"][field]) for field in panel.FIELDS}
                # Independently known choice accuracy: 0, 1/3, 1 for RRR/NDT2/POYO+.
                predictions["choice"] = {"RRR": [1, -1, 1], "NDT2": [-1, -1, 1],
                                         "POYO+": [-1, 1, -1]}[method]
                row = cls.evaluator.make_receipt(session, method, predictions,
                    method + "-source-resource-declaration", roster["training_eids"])
                row["packet_sha256"] = {"decode_all": row["packet_sha256"]["decode_all"]}
                records.append(row)
        cls.export = {"schema": "neds-table10-decoder-export/v1", "source_commit": cls.bridge.COMMIT,
                      "evidence_kind": "generated_engineering", "records": records}

    def score(self, export=None, bundle=None):
        return panel.score_comparators(self.bundle if bundle is None else bundle,
            self.export if export is None else export, implementations=IMPLEMENTATIONS)

    def test_exact_source_incidence_and_independent_metric_values(self):
        result = self.score()
        self.assertEqual(result["coverage"], {"required_operator_sessions": 84, "heldout_sessions": 10,
            "comparator_records": 30, "decoding_cells": 120, "encoding_cells": 0})
        for method, accuracy in (("RRR", 0), ("NDT2", 1 / 3), ("POYO+", 1)):
            actual = result["session_macro"][method]
            self.assertEqual(set(actual), set(panel.ENDPOINTS))
            self.assertAlmostEqual(actual["choice:accuracy"], accuracy)
            self.assertEqual(actual["block:accuracy"], 1)
            self.assertEqual(actual["wheel:r2"], 1)
            self.assertEqual(actual["whisker:r2"], 1)
        self.assertEqual(result["scientific_qualification"], "unknown")
        self.assertFalse(result["readiness_promoted"])

    def test_combined_path_keeps_84_sessions_and_nine_endpoints(self):
        report = panel.evaluate_panel(self.bundle, self.paired, self.export,
            ["source_method", "candidate"], implementations=IMPLEMENTATIONS, draws=8)
        evaluation = report["paired_nine_endpoint_evaluation"]["evaluation"]
        self.assertEqual(len(evaluation["session_results"]), 84)
        for row in evaluation["session_results"]:
            for method in evaluation["methods"]:
                self.assertEqual(len(row["scores"][method]["endpoints"]), 9)
        difference = report["paired_minus_comparator_session_macro"]
        self.assertEqual(difference["candidate"]["RRR"]["choice:accuracy"], 1)
        self.assertEqual(difference["source_method"]["POYO+"]["choice:accuracy"], -1)
        self.assertAlmostEqual(difference["candidate"]["NDT2"]["choice:accuracy"], 2 / 3)
        self.assertEqual(report["joint_superiority"], "not_assessed")

    def test_missing_duplicate_unknown_and_wrong_cohort_fail(self):
        for mutation in ("missing", "duplicate", "unknown", "training"):
            bad = copy.deepcopy(self.export)
            if mutation == "missing": bad["records"].pop()
            if mutation == "duplicate": bad["records"][1] = copy.deepcopy(bad["records"][0])
            if mutation == "unknown": bad["records"][0]["method"] = "convenient-baseline"
            if mutation == "training": bad["records"][0]["eid"] = self.evaluator.load_roster()["training_eids"][0]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.score(bad)

    def test_operator_full_cohort_still_required(self):
        bad = dict(self.bundle, sessions=self.bundle["sessions"][74:])
        with self.assertRaisesRegex(ValueError, "complete 74"):
            self.score(bundle=bad)

    def test_no_encoding_fabrication_missing_targets_or_last_batch(self):
        for mutation in ("encoding", "missing_behavior", "last_batch", "bad_bins"):
            bad = copy.deepcopy(self.export)
            pred = bad["records"][0]["predictions"]
            if mutation == "encoding": pred["spike"] = [[[1]]]
            if mutation == "missing_behavior": del pred["block"]
            if mutation == "last_batch": pred["choice"].pop()
            if mutation == "bad_bins": pred["wheel"][0].pop()
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.score(bad)

    def test_ordered_trial_unit_fit_validation_and_packet_binding(self):
        for field in ("trial_ids", "unit_ids", "fit_trial_ids", "validation_trial_ids", "packet_sha256"):
            bad = copy.deepcopy(self.export)
            if field == "packet_sha256": bad["records"][0][field]["decode_all"] = "0" * 64
            else: bad["records"][0][field].reverse()
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.score(bad)

    def test_all_pretraining_sessions_required(self):
        for mutation in ("missing", "duplicate", "heldout"):
            bad = copy.deepcopy(self.export)
            eids = bad["records"][0]["pretrained_eids"]
            if mutation == "missing": eids.pop()
            if mutation == "duplicate": eids[0] = eids[1]
            if mutation == "heldout": eids[0] = bad["records"][0]["eid"]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.score(bad)

    def test_raw_labels_numeric_types_and_nonfinite(self):
        for value in (0, True, "-1", float("inf")):
            bad = copy.deepcopy(self.export)
            bad["records"][0]["predictions"]["choice"][0] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.score(bad)

    def test_negative_r2_retained_and_no_test_baseline_selection(self):
        bad = copy.deepcopy(self.export)
        for row in bad["records"]:
            if row["method"] == "RRR":
                row["predictions"]["wheel"] = [[100 for _ in x] for x in row["predictions"]["wheel"]]
        result = self.score(bad)
        self.assertLess(result["session_macro"]["RRR"]["wheel:r2"], 0)
        self.assertEqual(set(result["session_macro"]), set(panel.METHODS))

    def test_order_invariant_and_no_mutation(self):
        original = json.dumps(self.export, sort_keys=True)
        expected = self.score()
        self.assertEqual(original, json.dumps(self.export, sort_keys=True))
        changed = dict(self.export, records=list(reversed(self.export["records"])))
        actual = self.score(changed)
        self.assertEqual(actual["session_results"], expected["session_results"])
        self.assertNotEqual(actual["export_sha256"], expected["export_sha256"])

    def test_evidence_and_source_commit_bound(self):
        for key, value in (("evidence_kind", "authentic"), ("source_commit", "0" * 40)):
            bad = dict(self.export, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.score(bad)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--implementations", type=Path, default=IMPLEMENTATIONS)
    args, rest = parser.parse_known_args()
    IMPLEMENTATIONS = args.implementations
    unittest.main(argv=[__file__, *rest])
