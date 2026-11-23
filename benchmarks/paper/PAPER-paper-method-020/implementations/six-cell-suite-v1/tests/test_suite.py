"""Generated counterexamples for a six-cell declared-trace join; no neural data."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest


_spec = importlib.util.spec_from_file_location("neurona_suite_tested", Path(__file__).resolve().parents[1] / "suite.py")
s = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s)


def fixture():
    vocabulary = ["yes", "no", "ride", "on", "_is"]
    specs = [
        ("q0", "yes", {"kind": "bool", "value": 1}, "yes"),
        ("q1", "ride", {"kind": "vocab", "value": [0, 0, 1, 0, 0]}, "ride"),
        ("q2", "on", {"kind": "vocab", "value": [0, 0, 1, 0, 0]}, "ride"),
        ("q3", "no", {"kind": "bool", "value": 1}, "yes"),
        ("q4", "_is", {"kind": "vocab", "value": [0, 0, 0, 0, 1]}, "_is"),
    ]
    queries = [{"id": q, "answer": a, "query_sha256": s.source.digest(q),
                "domain_functions": s.source.BUILTINS + ["cat"]} for q, a, _, _ in specs]
    manifest = {"schema": s.source.SCHEMA, "engineering_fixture": True,
                "source_code_revision": s.source.legacy.CODE_REVISION,
                "data_revision": s.source.legacy.DATA_REVISION,
                "training_manifest_sha256": "a" * 64,
                "train_domain_functions": s.source.BUILTINS + ["cat"],
                "records": [{"path": "CSI1/test/4804.npy", "source_sha256": "b" * 64, "queries": queries[:2]},
                            {"path": "CSI1/test/4805.npy", "source_sha256": "c" * 64, "queries": queries[2:]}]}
    suite = {"schema": s.SCHEMA, "comparison_plan_sha256": "e" * 64,
             "control_design": s.ABLATION_DESIGN, "cells": []}
    for access in s.ACCESS:
        for condition in s.CONDITIONS:
            run = {"manifest_sha256": s.source.digest(manifest), "train_hop": "all",
                   "checkpoint_sha256": "d" * 64, "selection_policy": "declared_frozen_selection",
                   "access_condition": access, "neural_condition": condition,
                   "vocabulary_sha256": s.source.digest(vocabulary),
                   "training_monitor": [{"id": q, "outcome": "returned", "execution": deepcopy(e)} for q, _, e, _ in specs],
                   "posthoc": [{"id": q, "outcome": "returned", "pred_answer": p} for q, _, _, p in specs]}
            declarations = {"common_inputs_sha256": "1" * 64, "resource_budget_sha256": "2" * 64,
                            "author_code_sha256": None if access == "paper_data" else "3" * 64,
                            "candidate_code_sha256": "4" * 64, "training_run_sha256": "5" * 64}
            suite["cells"].append({"run": run, "declarations": declarations})
    return manifest, suite, vocabulary


class SixCellSuiteTests(unittest.TestCase):
    def test_all_six_cells_recomputed_without_averaging_or_qualification(self):
        result = s.score_suite(*fixture())
        self.assertEqual(result["declared_cell_count"], 6)
        self.assertEqual(set(result["cells"]), set(s.ACCESS))
        for access in s.ACCESS:
            for condition in s.CONDITIONS:
                score = result["cells"][access][condition]
                self.assertEqual((score["posthoc"]["Overall"]["correct"], score["posthoc"]["Overall"]["queries"]), (3, 5))
                self.assertEqual(score["posthoc"]["Action"]["accuracy"], 1)
                self.assertEqual(score["posthoc"]["Position"]["accuracy"], 0)
                self.assertEqual(score["posthoc"]["T/F"]["accuracy"], 0.5)
                self.assertEqual(score["posthoc"]["Thing"]["queries"], 1)
        for key in ("execution_verified", "resource_equality_verified", "information_boundary_verified",
                    "native_query_population_authenticated", "separately_trained_text_only_present",
                    "full_benchmark_panel_complete", "reproduction_established", "improvement_established",
                    "current_sota_established"):
            self.assertIs(result[key], False)
        self.assertNotIn("overall_accuracy", result)

    def test_missing_duplicate_unknown_and_extra_cells_rejected(self):
        for mutation in ("missing", "duplicate", "unknown", "extra"):
            manifest, suite, vocabulary = fixture()
            if mutation == "missing":
                suite["cells"].pop()
            elif mutation == "duplicate":
                suite["cells"][-1] = deepcopy(suite["cells"][0])
            elif mutation == "unknown":
                suite["cells"][0]["run"]["neural_condition"] = "retrained_text_only"
            else:
                suite["cells"].append(deepcopy(suite["cells"][0]))
            with self.subTest(mutation=mutation), self.assertRaises(s.ContractError):
                s.score_suite(manifest, suite, vocabulary)

    def test_declared_input_budget_and_code_access_mismatch_rejected(self):
        for field in ("common_inputs_sha256", "resource_budget_sha256", "author_code_sha256"):
            manifest, suite, vocabulary = fixture()
            suite["cells"][0]["declarations"][field] = "9" * 64
            with self.subTest(field=field), self.assertRaises(s.ContractError):
                s.score_suite(manifest, suite, vocabulary)
        manifest, suite, vocabulary = fixture()
        suite["cells"][3]["declarations"]["author_code_sha256"] = None
        with self.assertRaises(s.ContractError):
            s.score_suite(manifest, suite, vocabulary)

    def test_inference_ablation_cannot_silently_retrain_or_change_selection(self):
        for location, field in (("declarations", "candidate_code_sha256"), ("declarations", "training_run_sha256"),
                                ("run", "checkpoint_sha256"), ("run", "selection_policy")):
            manifest, suite, vocabulary = fixture()
            suite["cells"][1][location][field] = "f" * 64
            with self.subTest(field=field), self.assertRaises(s.ContractError):
                s.score_suite(manifest, suite, vocabulary)

    def test_dropped_error_retained_and_no_false_neural_advantage(self):
        manifest, suite, vocabulary = fixture()
        # The neural cell drops an erroneous posthoc execution:3/4 versus3/5 is not a paired gain.
        suite["cells"][0]["run"]["posthoc"][2].update(outcome="raised", pred_answer=None)
        result = s.score_suite(manifest, suite, vocabulary)
        contrast = result["within_access_contrasts"]["paper_data"]["neural_minus_no_neural"]["posthoc"]["Overall"]
        self.assertEqual(result["cells"]["paper_data"]["neural"]["posthoc"]["Overall"]["accuracy"], 0.75)
        self.assertFalse(contrast["same_included_queries"])
        self.assertEqual(contrast["left_only_ids"], ["q2"])
        self.assertIsNone(contrast["right_minus_left"])
        self.assertEqual(len(result["cells"]["paper_data"]["neural"]["ledger"]), 5)

    def test_matched_delta_has_correct_direction_and_category_panel(self):
        manifest, suite, vocabulary = fixture()
        suite["cells"][0]["run"]["posthoc"][2]["pred_answer"] = "on"
        result = s.score_suite(manifest, suite, vocabulary)
        contrast = result["within_access_contrasts"]["paper_data"]["neural_minus_no_neural"]["posthoc"]
        self.assertAlmostEqual(contrast["Overall"]["right_minus_left"], 0.2)
        self.assertEqual(contrast["Position"]["right_minus_left"], 1)
        self.assertEqual(contrast["Action"]["right_minus_left"], 0)
        across = result["author_code_arm_minus_paper_data_arm"]["neural"]["posthoc"]["Overall"]
        self.assertAlmostEqual(across["right_minus_left"], -0.2)

    def test_aborted_monitor_never_becomes_completed_suite_metric(self):
        manifest, suite, vocabulary = fixture()
        rows = suite["cells"][0]["run"]["training_monitor"]
        rows[1].update(outcome="raised", execution=None)
        for row in rows[2:]:
            row.update(outcome="not_called", execution=None)
        result = s.score_suite(manifest, suite, vocabulary)
        contrast = result["within_access_contrasts"]["paper_data"]["neural_minus_shuffled_neural"]["training_monitor"]
        self.assertFalse(contrast["both_passes_completed"])
        self.assertIsNone(contrast["right_minus_left"])
        self.assertFalse(result["cells"]["paper_data"]["neural"]["training_monitor"]["completed"])

    def test_source_manifest_and_vocabulary_bindings_apply_to_every_cell(self):
        for field in ("manifest_sha256", "vocabulary_sha256"):
            manifest, suite, vocabulary = fixture()
            suite["cells"][5]["run"][field] = "0" * 64
            with self.subTest(field=field), self.assertRaises(s.ContractError):
                s.score_suite(manifest, suite, vocabulary)

    def test_candidate_reference_compare_corresponding_cells_not_access_mix(self):
        manifest, reference, vocabulary = fixture()
        candidate = deepcopy(reference)
        candidate["cells"][0]["run"]["posthoc"][2]["pred_answer"] = "on"
        result = s.compare_suites(manifest, reference, candidate, vocabulary)
        comparisons = result["candidate_minus_reference_by_cell"]
        self.assertAlmostEqual(comparisons["paper_data"]["neural"]["posthoc"]["Overall"]["right_minus_left"], 0.2)
        self.assertEqual(comparisons["paper_data_author_code"]["neural"]["posthoc"]["Overall"]["right_minus_left"], 0)
        self.assertFalse(result["improvement_established"])

    def test_candidate_reference_protocol_and_common_resources_must_match(self):
        for field in ("comparison_plan_sha256", "common_inputs_sha256", "resource_budget_sha256", "author_code_sha256"):
            manifest, reference, vocabulary = fixture()
            candidate = deepcopy(reference)
            if field == "comparison_plan_sha256":
                candidate[field] = "9" * 64
            else:
                for cell in candidate["cells"]:
                    if field != "author_code_sha256" or cell["run"]["access_condition"] == "paper_data_author_code":
                        cell["declarations"][field] = "9" * 64
            with self.subTest(field=field), self.assertRaises(s.ContractError):
                s.compare_suites(manifest, reference, candidate, vocabulary)

    def test_candidate_denominator_difference_is_not_improvement(self):
        manifest, reference, vocabulary = fixture()
        candidate = deepcopy(reference)
        candidate["cells"][3]["run"]["posthoc"][3].update(outcome="raised", pred_answer=None)
        report = s.compare_suites(manifest, reference, candidate, vocabulary)
        contrast = report["candidate_minus_reference_by_cell"]["paper_data_author_code"]["neural"]["posthoc"]["Overall"]
        self.assertEqual(contrast["left_only_ids"], ["q3"])
        self.assertIsNone(contrast["right_minus_left"])

    def test_same_nonempty_surviving_ids_do_not_define_source_overall(self):
        manifest, suite, vocabulary = fixture()
        for cell in suite["cells"]:
            for row in cell["run"]["posthoc"]:
                if row["id"] in {"q0", "q3"}:
                    row.update(outcome="raised", pred_answer=None)
        result = s.score_suite(manifest, suite, vocabulary)
        contrast = result["within_access_contrasts"]["paper_data"]["neural_minus_no_neural"]["posthoc"]
        self.assertTrue(contrast["Overall"]["same_included_queries"])
        self.assertFalse(contrast["Overall"]["both_scores_available"])
        self.assertIsNone(contrast["Overall"]["right_minus_left"])
        self.assertEqual(contrast["Action"]["right_minus_left"], 0)
        for access in s.ACCESS:
            for condition in s.CONDITIONS:
                overall = result["cells"][access][condition]["posthoc"]["Overall"]
                self.assertIsNone(overall["accuracy"])
                self.assertEqual(overall["pooled_accuracy_diagnostic"], 2 / 3)

    def test_missing_candidate_vocabulary_withholds_source_comparison(self):
        manifest, reference, vocabulary = fixture()
        candidate = deepcopy(reference)
        for row in candidate["cells"][0]["run"]["posthoc"]:
            if row["id"] in {"q1", "q2", "q4"}:
                row.update(outcome="raised", pred_answer=None)
        result = s.compare_suites(manifest, reference, candidate, vocabulary)
        contrast = result["candidate_minus_reference_by_cell"]["paper_data"]["neural"]["posthoc"]
        self.assertFalse(contrast["Overall"]["both_scores_available"])
        self.assertIsNone(contrast["Overall"]["right_minus_left"])
        self.assertEqual(contrast["T/F"]["right_minus_left"], 0)
        self.assertEqual(contrast["Overall"]["left_only_ids"], ["q1", "q2", "q4"])

    def test_unknown_claim_fields_and_control_design_are_refused(self):
        for mutation in ("claim", "declaration", "design"):
            manifest, suite, vocabulary = fixture()
            if mutation == "claim":
                suite["execution_verified"] = True
            elif mutation == "declaration":
                suite["cells"][0]["declarations"]["resource_equality_verified"] = True
            else:
                suite["control_design"] = "separately_retrained_text_only"
            with self.subTest(mutation=mutation), self.assertRaises(s.ContractError):
                s.score_suite(manifest, suite, vocabulary)


if __name__ == "__main__":
    unittest.main()
