"""Generated software controls only; no source observations or model calls."""
import csv
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("figure4d_scorer", Path(__file__).with_name("scorer.py"))
scorer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scorer)

CONDITIONS = tuple(str(i) for i in range(9))
OPTIONS = {"context_labels": ("A", "B"), "condition_labels": CONDITIONS,
           "condition_column": "Conditional", "aggregation": "conditional"}


def generated_rows():
    # One high-occupancy position is entirely right; all other positions wrong.
    # Independent count oracle: 8/16 observations correct, 1/9 groups correct.
    for rep in range(100):
        for condition in CONDITIONS:
            for i in range(8 if condition == "0" else 1):
                real = "A" if i % 2 else "B"
                yield {"Real_label": real,
                       "Pred_label": real if condition == "0" else ("B" if real == "A" else "A"),
                       "Conditional": condition, "Boot_rep": str(rep)}


class PredictionScoringTests(unittest.TestCase):
    def test_condition_mean_differs_from_observation_pool(self):
        result = scorer.score_rows(generated_rows(), **OPTIONS)
        self.assertEqual(result["selected_rows"], 1600)
        for rep in result["repetitions"]:
            self.assertAlmostEqual(rep["exact_match_accuracy"], 1 / 9)
            self.assertAlmostEqual(rep["normalized_absolute_error"], 8 / 9)
            self.assertEqual(rep["pooled_observation_diagnostic"]["exact_match_accuracy"], 0.5)
        self.assertAlmostEqual(result["repeat_summary"]["exact_match_accuracy"], 1 / 9)
        self.assertFalse(result["pairing_verified"])

    def test_global_source_accuracy_uses_all_observations(self):
        options = {**OPTIONS, "aggregation": "global"}
        result = scorer.score_rows(generated_rows(), **options)
        self.assertEqual(result["repeat_summary"]["exact_match_accuracy"], 0.5)
        self.assertEqual(result["repeat_summary"]["normalized_absolute_error"], 0.5)

    def test_binary_metric_is_label_encoding_invariant(self):
        rows = list(generated_rows())
        for row in rows:
            for key in ("Real_label", "Pred_label"):
                row[key] = {"A": "17", "B": "42"}[row[key]]
        result = scorer.score_rows(rows, **{**OPTIONS, "context_labels": ("17", "42")})
        self.assertAlmostEqual(result["repeat_summary"]["normalized_absolute_error"], 8 / 9)

    def test_bootstrap_multiplicity_is_retained(self):
        rows = list(generated_rows())
        rows += [dict(row) for row in rows if row["Conditional"] == "1"]
        result = scorer.score_rows(rows, **OPTIONS)
        self.assertEqual(result["selected_rows"], 1700)
        self.assertEqual(result["repetitions"][0]["conditions"][1]["count"], 2)
        self.assertAlmostEqual(result["repeat_summary"]["exact_match_accuracy"], 1 / 9)
        self.assertAlmostEqual(result["repetitions"][0]["pooled_observation_diagnostic"]["exact_match_accuracy"], 8 / 17)

    def test_missing_condition_is_undefined_never_dropped(self):
        rows = [row for row in generated_rows() if not (row["Conditional"] == "8" and row["Boot_rep"] == "4")]
        result = scorer.score_rows(rows, **OPTIONS)
        self.assertEqual(result["repetitions"][4]["missing_conditions"], ["8"])
        self.assertIsNone(result["repetitions"][4]["exact_match_accuracy"])
        self.assertIsNone(result["repeat_summary"]["exact_match_accuracy"])
        self.assertIsNotNone(result["repetitions"][3]["exact_match_accuracy"])

    def test_full_repetition_cannot_be_omitted(self):
        with self.assertRaisesRegex(scorer.ScoreError, "missing complete bootstrap repetition 99"):
            scorer.score_rows((row for row in generated_rows() if row["Boot_rep"] != "99"), **OPTIONS)

    def test_bad_export_rows_rejected(self):
        corruptions = [{"Real_label": ""}, {"Pred_label": "nan"}, {"Pred_label": "C"},
                       {"Conditional": "outside"}, {"Boot_rep": "0.0"}, {"Boot_rep": "100"},
                       {"Boot_rep": "-1"}, {"Pred_label": None}]
        for change in corruptions:
            with self.subTest(change=change), self.assertRaises(scorer.ScoreError):
                rows = list(generated_rows())
                rows[0].update(change)
                scorer.score_rows(rows, **OPTIONS)

    def test_malformed_csv_headers_and_padding_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prediction.csv"
            for body in ("Real_label,Real_label,Pred_label,Conditional,Boot_rep\nA,A,A,0,0\n",
                         "Real_label,Pred_label,Conditional,Boot_rep\nA,A,0,0,extra\n",
                         "Real_label,Pred_label,Conditional,Boot_rep\n,,,\n"):
                path.write_text(body)
                with self.subTest(body=body), self.assertRaises(scorer.ScoreError):
                    scorer.score_csv(path, **OPTIONS)

    def test_explicit_selector_does_not_mix_feature_counts_or_arms(self):
        rows = []
        for row in generated_rows():
            rows.extend([{**row, "PC": "3", "Decoder": "cond"},
                         {**row, "PC": "1", "Decoder": "cond", "Pred_label": row["Real_label"]},
                         {**row, "PC": "3", "Decoder": "single", "Pred_label": row["Real_label"]}])
        result = scorer.score_rows(rows, **OPTIONS, selectors={"PC": "3", "Decoder": "cond"})
        self.assertEqual(result["selected_rows"], 1600)
        self.assertEqual(result["selector_excluded_rows"], 3200)
        self.assertAlmostEqual(result["repeat_summary"]["exact_match_accuracy"], 1 / 9)
        for field in ("Pred_label", "Real_label", "Boot_rep", "Conditional"):
            with self.assertRaisesRegex(scorer.ScoreError, "selectors cannot narrow"):
                scorer.score_rows(rows, **OPTIONS, selectors={field: "0"})

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaisesRegex(scorer.ScoreError, "duplicate JSON key"):
            json.loads('{"schema":"a","schema":"b"}', object_pairs_hook=scorer._unique_object)

    def test_full_panel_and_required_source_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = {"schema": "hierarchy-figure4d-export-panel/v1", "context_labels": ["A", "B"],
                        "condition_labels": list(CONDITIONS), "sessions": []}
            # All 25 sessions use invented exports, never native observations.
            body = io.StringIO(newline="")
            fields = ["Real_label", "Pred_label", "Conditional", "Boot_rep", "Decoder"]
            writer = csv.DictWriter(body, fieldnames=fields)
            writer.writeheader()
            for arm in scorer.ARMS:
                for row in generated_rows():
                    writer.writerow({**row, "Decoder": arm})
            for animal, dates in scorer.ROSTER.items():
                for date in dates:
                    path = Path(directory) / f"{animal}_{date}.csv"
                    path.write_text(body.getvalue())
                    manifest["sessions"].append({"animal": animal, "date": date, "exports": {
                        arm: {"path": path.name, "condition_column": "Conditional", "selectors": {"Decoder": arm}}
                        for arm in scorer.ARMS}})
            result = scorer.score_panel(manifest, directory)
            self.assertEqual(result["session_count"], 25)
            self.assertEqual(result["animal_count"], 5)
            self.assertEqual(len(result["sessions"]), 25)
            self.assertIsNone(result["cross_session_aggregate"])
            self.assertIsNone(result["biological_uncertainty"])
            self.assertFalse(result["paired_source_draws_verified"])
            self.assertEqual(result["sessions"][0]["arms"]["global"]["repeat_summary"]["exact_match_accuracy"], 0.5)
            json.dumps(result, allow_nan=False)
            with self.assertRaisesRegex(scorer.ScoreError, "all 25"):
                scorer.score_panel({**manifest, "sessions": manifest["sessions"][:-1]}, directory)
            manifest["sessions"][0]["exports"].pop("conditional_position_shuffle")
            with self.assertRaisesRegex(scorer.ScoreError, "shuffle controls required"):
                scorer.score_panel(manifest, directory)


if __name__ == "__main__":
    unittest.main(verbosity=2)
