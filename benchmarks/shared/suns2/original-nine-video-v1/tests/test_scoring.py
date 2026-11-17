"""Generated geometry/arithmetic controls. No authentic SUNS2 payloads."""
from fractions import Fraction
import itertools
import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from suns2_benchmark import scoring as s
from suns2_benchmark.constants import VIDEO_IDS, MAX_INSTANCES

def masks(pixel_sets):
    out = np.zeros((50, 50, len(pixel_sets)), dtype=bool)
    for k, pixels in enumerate(pixel_sets):
        for x, y in pixels:
            out[x, y, k] = True
    return out

def panel(mask):
    return {video: mask.copy() for video in VIDEO_IDS}

def ratio(obj):
    return Fraction(int(obj["numerator"]), int(obj["denominator"]))

def brute_cardinality(edges):
    def visit(row, used):
        if row == len(edges):
            return 0
        best = visit(row + 1, used)
        for col, allowed in enumerate(edges[row]):
            if allowed and col not in used:
                best = max(best, 1 + visit(row + 1, used | {col}))
        return best
    return visit(0, set())

class PanelControls(unittest.TestCase):
    def test_complete_support_identity_and_json_safety(self):
        gt = panel(masks([{(0, 0)}, {(1, 1)}]))
        before = {v: a.tobytes() for v, a in gt.items()}
        result = s.score_panel(gt, gt, gt)
        self.assertEqual(result["video_ids"], list(VIDEO_IDS))
        self.assertEqual(result["status"], "scored_complete_panel")
        self.assertEqual(len(result["cases"]), 9)
        self.assertEqual(result["original_summary"]["author_mean_float"], 1)
        self.assertEqual(ratio(result["descriptive_outcome"]["original_mean_delta_exact"]), 0)
        self.assertFalse(result["descriptive_outcome"]["same_panel_geometry_improvement"])
        self.assertFalse(result["qualification"]["prediction_generation_reproduced"])
        json.dumps(result, allow_nan=False)
        self.assertEqual(before, {v: a.tobytes() for v, a in gt.items()})

    def test_geometry_improvement_requires_both_positive_metrics(self):
        gt = panel(masks([{(0, 0)}, {(1, 1)}]))
        author = panel(masks([{(0, 0)}, {(3, 3)}]))
        candidate = panel(masks([{(0, 0)}, {(1, 1)}]))
        result = s.score_panel(gt, author, candidate)
        out = result["descriptive_outcome"]
        self.assertTrue(out["same_panel_geometry_improvement"])
        self.assertEqual(ratio(out["original_mean_delta_exact"]), Fraction(1, 2))
        self.assertEqual(ratio(out["audit_mean_delta_exact"]), Fraction(1, 2))
        self.assertEqual(out["geometry_changed_video_ids"], list(VIDEO_IDS))

    def test_permutation_only_original_gain_cannot_qualify(self):
        pixels = [(0, i) for i in range(4)]
        gt = panel(masks([pixels[:2], pixels[:1], pixels]))
        author_masks = masks([pixels[:2], pixels, pixels[2:]])
        result = s.score_panel(gt, panel(author_masks), panel(author_masks[:, :, [1, 0, 2]]))
        out = result["descriptive_outcome"]
        self.assertGreater(ratio(out["original_mean_delta_exact"]), 0)
        self.assertEqual(ratio(out["audit_mean_delta_exact"]), 0)
        self.assertFalse(out["criteria"]["changed_unordered_prediction_geometry"])
        self.assertFalse(out["same_panel_geometry_improvement"])

    def test_duplicate_only_removal_is_not_geometry_improvement(self):
        one = {(0, 0)}
        result = s.score_panel(panel(masks([one])), panel(masks([one, one])), panel(masks([one])))
        out = result["descriptive_outcome"]
        self.assertEqual(ratio(out["original_mean_delta_exact"]), Fraction(1, 3))
        self.assertEqual(ratio(out["audit_mean_delta_exact"]), 0)
        self.assertFalse(out["same_panel_geometry_improvement"])
        self.assertEqual(result["cases"][0]["declared_order_invariant_audit"]["author"]["duplicate_prediction_instances_removed_for_audit_only"], 1)

    def test_duplicate_assisted_new_geometry_gain_rejected(self):
        a, b, c, d = (0, 0), (0, 1), (0, 2), (0, 3)
        common = {a, b, c}
        result = s.score_panel(panel(masks([{a, b}, {b, c}])), panel(masks([common])), panel(masks([common, common, {d}])))
        out = result["descriptive_outcome"]
        self.assertEqual(ratio(out["original_mean_delta_exact"]), Fraction(2, 15))
        self.assertEqual(ratio(out["audit_mean_delta_exact"]), Fraction(-1, 6))
        self.assertTrue(out["criteria"]["changed_unordered_prediction_geometry"])
        self.assertFalse(out["same_panel_geometry_improvement"])

    def test_all_GT_instances_are_preserved_in_audit(self):
        one = {(0, 0)}
        result = s.score_panel(panel(masks([one, one])), panel(masks([one])), panel(masks([one])))
        audit = result["cases"][0]["declared_order_invariant_audit"]["author"]
        self.assertEqual(audit["ground_truth_instances"], 2)
        self.assertEqual(audit["unique_prediction_instances"], 1)
        self.assertEqual(ratio(audit["f1_exact"]), Fraction(2, 3))

    def test_nonempty_zero_match_preserves_undefined_original(self):
        gt = panel(masks([{(0, 0)}]))
        candidate = panel(masks([{(0, 0)}]))
        candidate[VIDEO_IDS[0]] = masks([{(1, 1)}])
        result = s.score_panel(gt, gt, candidate)
        self.assertEqual(result["status"], "scored_with_undefined_original")
        self.assertIsNone(result["original_summary"]["candidate_mean_float"])
        self.assertIsNone(result["descriptive_outcome"]["original_mean_delta_exact"])
        self.assertEqual(result["original_summary"]["undefined_candidate_videos"], [VIDEO_IDS[0]])
        self.assertEqual(ratio(result["descriptive_outcome"]["audit_mean_delta_exact"]), Fraction(-1, 9))
        self.assertFalse(result["descriptive_outcome"]["same_panel_geometry_improvement"])
        json.dumps(result, allow_nan=False)

    def test_empty_prediction_preserves_literal_helper_zero(self):
        gt = panel(masks([{(0, 0)}]))
        result = s.score_panel(gt, gt, panel(masks([])))
        original = result["cases"][0]["original"]["candidate"]
        self.assertEqual(original["f1"], 0)
        self.assertEqual(original["recall"], 0)
        self.assertEqual(original["precision"], 0)
        self.assertEqual(original["status"], "literal_helper_empty_prediction_zero")
        self.assertEqual(original["full_native_producer_empty_path_parity"], "untested")
        self.assertEqual(result["declared_audit_summary"]["candidate_mean_float"], 0)

    def test_asymmetric_original_MAT_column_row_axes_preserved(self):
        # Movie[t, row=7, col=13] must map to original MAT[col=13,row=7,n].
        original_mat = panel(masks([{(13, 7)}]))
        transposed_candidate = panel(masks([{(7, 13)}]))
        exact = s.score_panel(original_mat, original_mat, original_mat)
        swapped = s.score_panel(original_mat, original_mat, transposed_candidate)
        self.assertEqual(exact["original_summary"]["candidate_mean_float"], 1)
        self.assertIsNone(swapped["original_summary"]["candidate_mean_float"])
        self.assertEqual(swapped["declared_audit_summary"]["candidate_mean_float"], 0)
        self.assertFalse(swapped["descriptive_outcome"]["same_panel_geometry_improvement"])

    def test_missing_extra_and_malformed_cases_rejected(self):
        good = panel(masks([{(0, 0)}]))
        bad_cases = []
        missing = dict(good); missing.pop(VIDEO_IDS[0]); bad_cases.append(missing)
        extra = dict(good); extra["not_a_video"] = masks([{(0, 0)}]); bad_cases.append(extra)
        for value in [np.ones((49, 50, 1)), np.zeros((50, 50, 1)), np.full((50, 50, 1), np.nan),
                      np.full((50, 50, 1), 0.5), np.ones((50, 50, 1), dtype=complex),
                      np.ones((50, 50, MAX_INSTANCES + 1), dtype=bool), np.ones((50, 50, 1), dtype=object)]:
            malformed = dict(good); malformed[VIDEO_IDS[0]] = value; bad_cases.append(malformed)
        for bad in bad_cases:
            with self.subTest(keys=list(bad)[:2]), self.assertRaises(s.ScoringError):
                s.score_panel(good, good, bad)
        empty_gt = dict(good); empty_gt[VIDEO_IDS[0]] = masks([])
        with self.assertRaises(s.ScoringError):
            s.score_panel(empty_gt, good, good)

    def test_array_subclass_is_not_executed(self):
        class Injected(np.ndarray):
            def __array_ufunc__(self, *args, **kwargs):
                raise AssertionError("must not dispatch participant subclass")
        good = panel(masks([{(0, 0)}]))
        bad = dict(good); bad[VIDEO_IDS[0]] = good[VIDEO_IDS[0]].view(Injected)
        with self.assertRaises(s.ScoringError):
            s.score_panel(good, good, bad)

    def test_bounded_deadline_rejects_before_partial_result(self):
        good = panel(masks([{(0, 0)}]))
        with patch.object(s, "SCORE_TIMEOUT_SECONDS", -1), self.assertRaises(s.ScoringError):
            s.score_panel(good, good, good)

class AuditControls(unittest.TestCase):
    def test_integer_half_threshold_and_zero_totalization(self):
        gt = panel(masks([{(0, 0), (0, 1)}]))
        half = panel(masks([{(0, 0)}]))
        result = s.score_panel(gt, half, half)
        self.assertEqual(result["cases"][0]["declared_order_invariant_audit"]["author"]["matches"], 1)
        gt = panel(masks([{(0, 0), (0, 1), (0, 2)}]))
        result = s.score_panel(gt, half, half)
        self.assertEqual(result["cases"][0]["declared_order_invariant_audit"]["author"]["f1"], 0)
        self.assertIsNone(result["cases"][0]["original"]["author"]["f1"])

    def test_all_three_by_three_graphs_against_independent_enumeration(self):
        deadline = time.monotonic() + 15
        for bits in range(512):
            edges = np.array([(bits >> i) & 1 for i in range(9)], dtype=bool).reshape(3, 3)
            self.assertEqual(s._maximum_cardinality(edges, deadline), brute_cardinality(edges))
        for shape in [(0, 4), (4, 0), (2, 4), (4, 2)]:
            edges = np.ones(shape, dtype=bool)
            self.assertEqual(s._maximum_cardinality(edges, deadline), min(shape))

    def test_audit_invariant_to_every_three_instance_permutation(self):
        pixels = [(0, i) for i in range(4)]
        gt = panel(masks([pixels[:2], pixels[:1], pixels]))
        pred = masks([pixels[:2], pixels, pixels[2:]])
        for permutation in itertools.permutations(range(3)):
            result = s.score_panel(gt, panel(pred), panel(pred[:, :, permutation]))
            self.assertEqual(result["declared_audit_summary"]["candidate_mean_float"], 1)
            self.assertEqual(ratio(result["descriptive_outcome"]["audit_mean_delta_exact"]), 0)
            self.assertFalse(result["descriptive_outcome"]["same_panel_geometry_improvement"])

    def test_count_rationals_prevent_floating_only_gain(self):
        selected = None
        # Find a small realizable equal-F1 count pair whose source floating
        # arithmetic differs. This is generated arithmetic, not data tuning.
        for g in range(2, 65):
            for p in range(1, 65):
                a_recall, a_precision = 1 / g, 1 / p
                c_recall, c_precision = 2 / g, 2 / (g + 2 * p)
                a_f1 = 2 * a_recall * a_precision / (a_recall + a_precision)
                c_f1 = 2 * c_recall * c_precision / (c_recall + c_precision)
                if float(np.mean([c_f1] * 9)) > float(np.mean([a_f1] * 9)):
                    selected = g, p
                    break
            if selected:
                break
        self.assertIsNotNone(selected)
        g, p = selected
        true_pixels = [{(i // 50, i % 50)} for i in range(g)]
        false_pixels = [{(25 + i // 50, i % 50)} for i in range(g + 2 * p)]
        author = masks(true_pixels[:1] + false_pixels[:p - 1])
        candidate = masks(true_pixels[:2] + false_pixels[:g + 2 * p - 2])
        result = s.score_panel(panel(masks(true_pixels)), panel(author), panel(candidate))
        self.assertGreater(result["original_summary"]["candidate_minus_author_mean_float"], 0)
        self.assertEqual(ratio(result["descriptive_outcome"]["original_mean_delta_exact"]), 0)
        self.assertFalse(result["descriptive_outcome"]["criteria"]["positive_original_mean_delta_exact"])
        self.assertFalse(result["descriptive_outcome"]["same_panel_geometry_improvement"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
