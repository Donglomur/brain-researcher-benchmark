"""New DPAD numerical regressions; generated algebraic inputs only."""
from fractions import Fraction
import importlib.util
import math
import sys
import unittest

import paired as p


def exact_cc(x, y):
    """Independent exact-rational centered products; round only the final square root."""
    a, b = list(map(Fraction, x)), list(map(Fraction, y))
    am, bm = sum(a) / len(a), sum(b) / len(b)
    a, b = [v - am for v in a], [v - bm for v in b]
    aa, bb = sum(v * v for v in a), sum(v * v for v in b)
    if aa == 0 or bb == 0:
        return None
    ab = sum(u * v for u, v in zip(a, b))
    return (1 if ab >= 0 else -1) * math.sqrt(float(ab * ab / (aa * bb)))


def rows(values, columns=1):
    return [[v] * columns for v in values]


def full_fixture():
    """Full declared grid, with exact affine signals instead of neural recordings."""
    e = p.e
    protocol = {
        "task_id": e.TASK_ID, "profile": "historical_symmetric",
        "reference_kind": "generated_engineering_control",
        "sessions": list(e.SESSIONS), "dimensions": list(e.DIMENSIONS),
        "folds": [1, 2, 3, 4, 5], "filter_past_support_samples": 0,
        "filter_future_support_samples": 0, "purge_samples": 0,
        "neural_lag_samples": 1, "held_behavior_used": False,
        "session_sample_counts": {s: 15 for s in e.SESSIONS},
        "animal_ids": {s: "indy" for s in e.SESSIONS},
    }
    layout = {s: {"neural": [{"id": f"unit-{i}", "unit": "generated"} for i in range(77)],
                  "behavior": [{"id": name, "unit": "generated"} for name in p.BEHAVIOR]}
              for s in e.SESSIONS}
    training = {"protocol": protocol, "channel_layout": layout, "cases": []}
    candidate_training = {"protocol": protocol, "channel_layout": layout,
                          "candidate_id": "generated-affine", "code_sha256": "a" * 64,
                          "cases": []}
    for session, fold in sorted(p.FOLDS):
        held = e.held_ids(protocol, session, fold)
        allowed = [i for i in range(15) if i not in held]
        common = {"session_id": session, "fold": fold,
                  "fit_sample_ids": allowed, "selection_sample_ids": allowed}
        dimensions, candidate_dimensions = {}, {}
        for dimension in e.DIMENSIONS:
            score = .8 if dimension == 4 else .4
            metrics = {"training_neural_cc": score, "training_behavior_cc": score,
                       "inner_neural_cc": [.5, .5], "inner_behavior_cc": [.5, .5]}
            dimensions[str(dimension)] = {name: metrics for name in e.ARCHITECTURES}
            candidate_dimensions[str(dimension)] = {
                "training_neural_cc": score, "training_behavior_cc": score,
                "configuration_sha256": e.digest({"dimension": dimension})}
        training["cases"].append({**common, "dimensions": dimensions})
        candidate_training["cases"].append({**common, "dimensions": candidate_dimensions})
    author_plan = e.select(training)
    candidate_plan = p.select_candidate(candidate_training)
    targets = {"protocol": protocol, "channel_layout": layout, "cases": []}
    author = {"protocol": protocol, "channel_layout": layout,
              "selection_plan_sha256": e.digest(author_plan), "cases": []}
    candidate = {"protocol": protocol, "channel_layout": layout,
                 "candidate_id": candidate_training["candidate_id"], "code_sha256": "a" * 64,
                 "selection_plan_sha256": e.digest(candidate_plan), "cases": []}
    anchor = float(3 * 2**52)
    signal = [anchor, anchor + 2, anchor + 4]
    plan_rows = {(r["session_id"], r["fold"]): r for r in author_plan["cases"]}
    for session, fold in sorted(p.FOLDS):
        common = {"session_id": session, "fold": fold,
                  "sample_ids": e.held_ids(protocol, session, fold),
                  "neural_channel_ids": [c["id"] for c in layout[session]["neural"]],
                  "behavior_channel_ids": list(p.BEHAVIOR)}
        targets["cases"].append({**common, "neural": rows(signal, 77), "behavior": rows(signal, 4)})
        for dimension in e.DIMENSIONS:
            candidate["cases"].append({**common, "dimension": dimension,
                "configuration_sha256": e.digest({"dimension": dimension}),
                "neural": rows([1.0, 0.0, -1.0], 77), "behavior": rows([1.0, 0.0, -1.0], 4)})
            for method in e.METHODS:
                author["cases"].append({**common, "dimension": dimension, "method": method,
                    "architecture": plan_rows[(session, fold)]["methods"][method]["architectures"][str(dimension)],
                    "neural": rows([-1.0, 0.0, 1.0], 77), "behavior": rows([-1.0, 0.0, 1.0], 4)})
    return training, targets, author, candidate_plan, candidate


class StablePearson(unittest.TestCase):
    def test_near_offset_exact_dyadic_oracle_and_predecessor_failure(self):
        anchor = float(3 * 2**52)
        x = [anchor, anchor + 2, anchor + 4]
        y = [-1.0, 0.0, 1.0]
        spec = importlib.util.spec_from_file_location("dpad_unchanged_numeric_control", p.LEGACY)
        old = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(old)
        # Exact normalized predecessor deviations are [-1, 0, 1/2].
        self.assertAlmostEqual(old.channel_cc(rows(x), rows(y))["mean_cc"], 3 / math.sqrt(10), places=14)
        self.assertEqual(exact_cc(x, y), 1.0)
        self.assertAlmostEqual(p.channel_cc(rows(x), rows(y))["mean_cc"], 1.0, places=14)
        self.assertAlmostEqual(p.channel_cc(rows(x), rows([-v for v in y]))["mean_cc"], -1.0, places=14)
        nonaffine_x = [anchor + 2 * i for i in range(4)]
        nonaffine_y = [0.0, 2.0, 1.0, 3.0]
        self.assertAlmostEqual(p.channel_cc(rows(nonaffine_x), rows(nonaffine_y))["mean_cc"],
                               exact_cc(nonaffine_x, nonaffine_y), places=14)

    def test_extremes_subnormals_and_channel_mean(self):
        tiny = math.ulp(0.0)
        vectors = [([-sys.float_info.max, 0.0, sys.float_info.max], [-1.0, 0.0, 1.0]),
                   ([tiny, 2 * tiny, 3 * tiny], [-1.0, 0.0, 1.0]),
                   ([-3 * tiny, -2 * tiny, -tiny], [-1.0, 0.0, 1.0])]
        for x, y in vectors:
            with self.subTest(x=x):
                self.assertAlmostEqual(p.channel_cc(rows(x), rows(y))["mean_cc"], exact_cc(x, y), places=14)
        x = [[-100.0, -1.0], [-100.0, 1.0], [100.0, -1.0], [100.0, 1.0]]
        result = p.channel_cc(x, [[a, -b] for a, b in x])
        self.assertAlmostEqual(result["mean_cc"], 0.0, places=14)
        self.assertEqual(result["undefined_channels"], [])

    def test_undefined_and_invalid_inputs_preserve_strict_admission(self):
        result = p.channel_cc([[1.0, 0.0], [1.0, 1.0]], [[0.0, 0.0], [1.0, 1.0]])
        self.assertIsNone(result["mean_cc"])
        self.assertEqual(result["undefined_channels"], [0])
        self.assertEqual(result["sample_count"], 2)
        for invalid in ([[True], [1.0]], [[float("nan")], [1.0]], [[float("inf")], [1.0]],
                        [[None], [1.0]], [[0.0], [1.0, 2.0]]):
            with self.subTest(invalid=invalid), self.assertRaises(p.e.ContractError):
                p.channel_cc([[0.0], [1.0]], invalid)

    def test_full_grid_both_paths_and_metric_lineage(self):
        training, targets, author, plan, candidate = full_fixture()
        reference = p.freeze_reference(training, targets, author)
        result = p.compare(targets, reference, plan, candidate, p.e.digest(reference), p.e.digest(plan))
        self.assertIs(p.e.channel_cc, p.channel_cc)
        self.assertEqual(reference["numerical_policy"], p.NUMERICAL_POLICY)
        self.assertEqual(reference["source_grid_results"]["numerical_policy"], p.NUMERICAL_POLICY)
        self.assertEqual(result["numerical_policy"], p.NUMERICAL_POLICY)
        self.assertEqual(len(reference["source_grid_results"]["all_grid_scores"]), 1960)
        self.assertEqual(len(result["candidate_grid_scores"]), 280)
        self.assertEqual(len(result["paired_fold_deltas"]), 245)
        for row in reference["source_grid_results"]["all_grid_scores"]:
            self.assertAlmostEqual(row["neural"]["mean_cc"], 1.0, places=14)
            self.assertAlmostEqual(row["behavior"]["mean_cc"], 1.0, places=14)
        for row in result["paired_fold_deltas"]:
            self.assertAlmostEqual(row["neural_cc_delta"], -2.0, places=14)
            self.assertAlmostEqual(row["behavior_cc_delta"], -2.0, places=14)
        self.assertEqual(result["scientific_reproduction"], "not_assessed")
        self.assertEqual(result["scientific_improvement"], "not_assessed")
        for field, value in (("schema", "dpad-author-reference-v2"), ("numerical_policy", "wrong")):
            invalid = dict(reference, **{field: value})
            with self.subTest(field=field), self.assertRaisesRegex(p.e.ContractError, "reference lineage"):
                p.compare(targets, invalid, plan, candidate, p.e.digest(invalid), p.e.digest(plan))
        invalid_plan = dict(plan, schema="dpad-candidate-plan-v2")
        with self.assertRaisesRegex(p.e.ContractError, "candidate plan"):
            p.compare(targets, reference, invalid_plan, candidate, p.e.digest(reference), p.e.digest(invalid_plan))


if __name__ == "__main__":
    unittest.main()
