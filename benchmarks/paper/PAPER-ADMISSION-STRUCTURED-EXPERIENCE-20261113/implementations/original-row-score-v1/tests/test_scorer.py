"""Generated controls only; no authentic recordings, targets or model executions."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("original_scorer", Path(__file__).parents[1] / "scorer.py")
scorer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scorer)


def panel():
    # Non-sorted labels, unequal context counts, and query folds without all contexts.
    trials = (42, 3, 100, 8, 9, 10, 11, 12, 13, 14, 15, 16)
    sessions = []
    for group in scorer.SESSIONS.values():
        for sid in group:
            rows = []
            for ordinal, trial in enumerate(trials):
                context = "LS" if ordinal < 6 else "SL" if ordinal < 9 else "SS"
                for time_bin in range(40):
                    rows.append({"trial": trial, "type": context, "result": "correct", "time_bin": time_bin})
            sessions.append({"session_id": sid, "feature_sha256": "1" * 64, "rows": rows})
    return {"schema": "structured-original-index/v1", "source_commit": scorer.SOURCE_COMMIT,
            "evidence_kind": "generated_engineering_control", "sessions": sessions}


def prediction_artifact(owner_index, shift=2, include_all=False):
    # Independently enumerated np.array_split positions for the 12 original trials.
    fold_by_trial = dict(zip((42, 3, 100, 8, 9, 10, 11, 12, 13, 14, 15, 16),
                            (0, 0, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9)))
    sessions = []
    for session in owner_index["sessions"]:
        rows = []
        for row in session["rows"]:
            values = {source: (row["time_bin"] + (shift if source == row["type"] else 2 * shift)) % 40
                      for source in scorer.CONTEXTS}
            if include_all:
                values["all"] = (row["time_bin"] + 20) % 40
            rows.append(dict(row, split=fold_by_trial[row["trial"]], predictions=values))
        sessions.append({"session_id": session["session_id"], "rows": rows})
    return {"schema": "structured-original-predictions/v1", "owner_index_sha256": scorer.digest(owner_index),
            "run_receipt_sha256": "2" * 64, "sessions": sessions}


class OriginalEndpointTests(unittest.TestCase):
    def setUp(self):
        self.index = panel()
        self.pred = prediction_artifact(self.index)

    def test_circular_formula_all_classes_against_three_physical_images(self):
        for actual in range(40):
            for predicted in range(40):
                expected = min((predicted / 2 - actual / 2 + offset) ** 2 for offset in (-20, 0, 20))
                self.assertEqual(scorer.circular_error(predicted, actual), expected)
        self.assertEqual(scorer.circular_error(39, 0), 0.25)
        self.assertEqual(scorer.circular_error(20, 0), 100)

    def test_original_full_panel_and_sparse_query_contexts(self):
        result = scorer.score(self.index, self.pred)
        self.assertEqual(len(result["context_pair_mse_seconds2"]), 13)
        self.assertEqual(sum(len(row) for table in result["context_pair_mse_seconds2"].values()
                             for row in table.values()), 117)
        for table in result["context_pair_mse_seconds2"].values():
            for source, row in table.items():
                for test, value in row.items():
                    self.assertEqual(value, 1 if source == test else 4)
        first = result["sessions"][0]
        self.assertEqual(first["context_row_counts"], {"LS": 240, "SL": 120, "SS": 120})
        self.assertEqual(first["within_mse_seconds2"], 1)
        self.assertEqual(first["across_mse_seconds2"], 4)
        self.assertEqual(first["absolute_biological_gap_seconds2"], 3)
        self.assertIsNone(result["paper_win"])
        self.assertNotIn("loss", result)

    def test_all_context_model_is_reported_separately(self):
        pred = prediction_artifact(self.index, include_all=True)
        result = scorer.score(self.index, pred)
        self.assertEqual(result["context_pair_mse_seconds2"], scorer.score(self.index, self.pred)["context_pair_mse_seconds2"])
        self.assertEqual(result["sessions"][0]["all_context_decoder_diagnostic_seconds2"],
                         {"LS": 100, "SL": 100, "SS": 100})
        del pred["sessions"][0]["rows"][0]["predictions"]["all"]
        with self.assertRaises(scorer.ScoreError):
            scorer.score(self.index, pred)

    def test_original_reduction_weights_rows_not_trial_means(self):
        # An additional source result group for one trial remains in the native index.
        # It contributes 40 rows to the LS context, not a half-weighted trial mean.
        extra = [dict(row, result="second_recorded_result") for row in self.index["sessions"][0]["rows"][:40]]
        self.index["sessions"][0]["rows"].extend(extra)
        pred = prediction_artifact(self.index, shift=0)
        for row in pred["sessions"][0]["rows"][-40:]:
            row["predictions"]["LS"] = (row["time_bin"] + 6) % 40
        result = scorer.score(self.index, pred)
        sid = self.index["sessions"][0]["session_id"]
        self.assertAlmostEqual(result["context_pair_mse_seconds2"][sid]["LS"]["LS"], 9 / 7)
        self.assertNotAlmostEqual(result["context_pair_mse_seconds2"][sid]["LS"]["LS"], 4.5 / 6)

    def test_context_pairs_are_equally_weighted_after_row_reduction(self):
        for row in self.pred["sessions"][0]["rows"]:
            for source in scorer.CONTEXTS:
                row["predictions"][source] = (row["time_bin"] + (6 if row["type"] == "LS" else 0)) % 40
        first = scorer.score(self.index, self.pred)["sessions"][0]
        self.assertEqual(first["within_mse_seconds2"], 3)
        self.assertEqual(first["across_mse_seconds2"], 3)
        self.assertNotEqual(first["within_mse_seconds2"], 4.5)  # Pooled context rows.

    def test_prediction_order_does_not_change_score(self):
        reversed_pred = copy.deepcopy(self.pred)
        reversed_pred["sessions"].reverse()
        for session in reversed_pred["sessions"]:
            session["rows"].reverse()
        actual = scorer.score(self.index, reversed_pred)
        expected = scorer.score(self.index, self.pred)
        self.assertEqual(actual["context_pair_mse_seconds2"], expected["context_pair_mse_seconds2"])

    def test_changed_source_order_cannot_reuse_original_split(self):
        rows = self.index["sessions"][0]["rows"]
        rows[:120] = rows[80:120] + rows[40:80] + rows[:40]
        self.pred["owner_index_sha256"] = scorer.digest(self.index)
        with self.assertRaisesRegex(scorer.ScoreError, "ordered ten folds"):
            scorer.score(self.index, self.pred)

    def test_missing_duplicate_wrong_fold_and_class_refuse(self):
        for mutation in ("missing", "duplicate", "split", "bool", "float", "context"):
            pred = copy.deepcopy(self.pred)
            rows = pred["sessions"][0]["rows"]
            if mutation == "missing":
                rows.pop()
            elif mutation == "duplicate":
                rows.append(copy.deepcopy(rows[0]))
            elif mutation == "split":
                rows[0]["split"] = 1
            elif mutation == "context":
                rows[0]["type"] = "LL"
            else:
                rows[0]["predictions"]["LS"] = True if mutation == "bool" else 2.0
            with self.subTest(mutation=mutation), self.assertRaises(scorer.ScoreError):
                scorer.score(self.index, pred)

    def test_full_session_and_feature_binding_required(self):
        self.pred["sessions"].pop()
        with self.assertRaises(scorer.ScoreError):
            scorer.score(self.index, self.pred)
        self.pred = prediction_artifact(self.index)
        self.index["sessions"][0]["feature_sha256"] = "3" * 64
        with self.assertRaisesRegex(scorer.ScoreError, "different original"):
            scorer.score(self.index, self.pred)
        self.index["sessions"][0]["rows"].pop()
        with self.assertRaisesRegex(scorer.ScoreError, "forty bins"):
            scorer.validate_index(self.index)

    def test_comparison_keeps_every_original_cell_without_significance(self):
        baseline = prediction_artifact(self.index, shift=4)
        compared = scorer.compare(self.index, self.pred, baseline)
        for matrix in compared["baseline_minus_candidate_seconds2"].values():
            for source, row in matrix.items():
                for test, delta in row.items():
                    self.assertEqual(delta, 3 if source == test else 12)
        self.assertIsNone(compared["paper_win"])
        self.assertNotIn("p_value", compared)

    def test_native_export_preserves_index_order_columns_and_scalars(self):
        # Small protocol objects exercise the export path; this is not pandas parity.
        class Index:
            def __init__(self, names, values):
                self.names, self.values = names, values

            def tolist(self):
                return self.values

        class Scalar:
            def __init__(self, value):
                self.value = value

            def item(self):
                return self.value

        class Frame:
            index = Index(("split", "trial", "type", "result", "time_bin"),
                          [(Scalar(0), Scalar(42), "LS", "correct", Scalar(0))])
            columns = ["all", "SS", "SL", "LS"]

            def itertuples(self, *, index, name):
                return iter([(Scalar(20), Scalar(6), Scalar(4), Scalar(2))])

        index = Index(scorer.INDEX_FIELDS, [(Scalar(42), "LS", "correct", Scalar(0))])
        self.assertEqual(scorer.export_index_rows(index), [self.index["sessions"][0]["rows"][0]])
        rows = scorer.export_prediction_rows(Frame())
        self.assertEqual(rows, [{"split": 0, "trial": 42, "type": "LS", "result": "correct",
                                 "time_bin": 0, "predictions": {"all": 20, "SS": 6, "SL": 4, "LS": 2}}])
        index.names = ("trial", "result", "type", "time_bin")
        with self.assertRaises(scorer.ScoreError):
            scorer.export_index_rows(index)

    def test_json_and_exclusive_private_cli_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index_path, pred_path, output = [root / name for name in ("index.json", "pred.json", "score.json")]
            index_path.write_text(json.dumps(self.index))
            pred_path.write_text(json.dumps(self.pred))
            scorer.main([str(index_path), str(pred_path), str(output)])
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertEqual(scorer.load(output)["qualification"], "row_scoring_component_only")
            with self.assertRaises(FileExistsError):
                scorer.main([str(index_path), str(pred_path), str(output)])
            for invalid in ('{"x":1,"x":2}', '{"x":NaN}'):
                pred_path.write_text(invalid)
                with self.assertRaises(scorer.ScoreError):
                    scorer.load(pred_path)


if __name__ == "__main__":
    unittest.main()
