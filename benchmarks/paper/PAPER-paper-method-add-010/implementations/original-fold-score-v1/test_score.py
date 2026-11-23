"""Generated software controls; no empirical samples, fitting or source execution."""
import copy
import csv
import importlib.util
import io
import math
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("original_meg_score", Path(__file__).with_name("score.py"))
score = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(score)


def support():
    measures = tuple(f"generated-{i:03}" for i in range(246))
    # Generated QC makes each measure eligible in one block. This keeps the
    # complete 246-domain x24-block x6-pair control small without fitting.
    eligibility = {
        block: {measure: None if i % 24 == j else "generated exclusion" for i, measure in enumerate(measures)}
        for j, block in enumerate(score.BLOCKS)
    }
    return measures, eligibility, score.expected_cells(measures, eligibility)


def fixture():
    rows, probabilities = [], {}
    for index, participant in enumerate(score.published_participants()):
        for label in ("face", "object"):
            identifier = f"generated-{index}-{label}"
            rows.append({"id": identifier, "participant": participant, "label": label, "fold": index % 10})
            probability = float(label == "object")
            probabilities[identifier] = 1 - probability if index % 10 == 0 else probability
    return rows, probabilities


def csv_text(cells, mutation=None):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=score.AUTHOR_COLUMNS)
    writer.writeheader()
    for index, key in enumerate(cells):
        measure, a, b, relevance, period, c0, c1 = key
        row = dict(zip(score.AUTHOR_COLUMNS, (measure, "Logistic_Regression", a, b, relevance, period, repr((c1, c0)), 0.6, 0.1, 0.7, 0.2)))
        if mutation:
            mutation(index, row)
        writer.writerow(row)
    output.seek(0)
    return output


class OriginalScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.measures, cls.eligibility, cls.cells = support()

    def test_mean_fold_accuracy_not_pooled_or_equal_person(self):
        rows, probabilities = fixture()
        result = score.score_cell(rows, probabilities, ("object", "face"))
        self.assertEqual(result["accuracy"], 0.9)
        self.assertAlmostEqual(result["accuracy_SD"], 0.3)
        self.assertEqual(result["fold_observations"], [20] * 4 + [18] * 6)
        self.assertAlmostEqual(result["pooled_accuracy_descriptive"], 84 / 94)
        self.assertNotEqual(result["accuracy"], result["pooled_accuracy_descriptive"])
        self.assertNotEqual(result["accuracy_SD"], math.sqrt(0.1))  # sample SD is wrong here

    def test_threshold_tie_and_class_orientation(self):
        rows, _ = fixture()
        result = score.score_cell(rows, {row["id"]: 0.5 for row in rows}, ("object", "face"))
        self.assertEqual(result["accuracy"], 0.5)
        # At the tie every face row is correct and every object row is wrong.
        self.assertEqual(result["fold_correct"], [n // 2 for n in result["fold_observations"]])

    def test_rejects_missing_class_even_when_all_participants_and_folds_remain(self):
        rows, probabilities = fixture()
        damaged = (
            [row for row in rows if row["label"] == "face"],
            rows[1:],  # Only one participant loses one class; both remain globally.
        )
        for truncated in damaged:
            with self.subTest(observations=len(truncated)), self.assertRaisesRegex(
                    score.ScoreError, "both stimulus classes required for every participant"):
                score.score_cell(truncated, {r["id"]: probabilities[r["id"]] for r in truncated},
                                 ("face", "object"))

    def test_repeated_rows_keep_source_observation_weighting(self):
        rows, probabilities = fixture()
        repeat = {**rows[0], "id": "generated-repeat"}
        rows.append(repeat)
        probabilities[repeat["id"]] = float(repeat["label"] == "object")
        result = score.score_cell(rows, probabilities, ("face", "object"))
        self.assertEqual(result["observations"], 189)
        self.assertEqual(result["fold_observations"], [21] + [20] * 3 + [18] * 6)
        self.assertEqual(result["fold_correct"][0], 1)
        self.assertAlmostEqual(result["accuracy"], (9 + 1 / 21) / 10)

    def test_source_fold_identities_are_supplied_not_regenerated(self):
        rows, probabilities = fixture()
        reverse = copy.deepcopy(rows)
        for row in reverse:
            row["fold"] = 9 - row["fold"]
        result = score.score_cell(reverse, probabilities, ("face", "object"))
        self.assertEqual(result["fold_accuracy"], [1] * 9 + [0])

    def test_rejects_changed_prediction_support(self):
        rows, probabilities = fixture()
        for kind in ("missing", "extra", "duplicate"):
            r, p = copy.deepcopy(rows), probabilities.copy()
            if kind == "missing":
                p.pop(r[0]["id"])
            elif kind == "extra":
                p["unknown"] = 0.5
            else:
                r.append(r[0])
            with self.subTest(kind=kind), self.assertRaises(score.ScoreError):
                score.score_cell(r, p, ("face", "object"))

    def test_rejects_missing_person_and_split_participant(self):
        rows, probabilities = fixture()
        smaller = rows[2:]
        with self.assertRaises(score.ScoreError):
            score.score_cell(smaller, {r["id"]: probabilities[r["id"]] for r in smaller}, ("face", "object"))
        rows[0]["fold"] = 1
        with self.assertRaises(score.ScoreError):
            score.score_cell(rows, probabilities, ("face", "object"))

    def test_rejects_invalid_probability_and_boolean_fold(self):
        rows, probabilities = fixture()
        for bad in (True, float("nan"), float("inf"), -0.1, 1.1, 10 ** 10000, "0.4"):
            probabilities[rows[0]["id"]] = bad
            with self.assertRaises(score.ScoreError):
                score.score_cell(rows, probabilities, ("face", "object"))
        rows[0]["fold"] = False
        with self.assertRaises(score.ScoreError):
            score.score_cell(rows, {r["id"]: 0.5 for r in rows}, ("face", "object"))

    def test_complete_qc_lattice_and_all_eligible_pairs(self):
        self.assertEqual(len(self.cells), 246 * 6)
        self.assertEqual(len({c[1:] for c in self.cells}), 144)
        all_eligible = {block: {m: None for m in self.measures} for block in score.BLOCKS}
        self.assertEqual(len(score.expected_cells(self.measures, all_eligible)), 246 * 144)
        for damaged in (self.cells[:-1], (self.cells[0],), self.cells + (self.cells[0],)):
            with self.assertRaises(score.ScoreError):
                score.read_author_matrix(csv_text(damaged), damaged)

    def test_requires_explicit_qc_for_every_block_and_measure(self):
        for damage in ("block", "measure", "reason", "domain"):
            eligibility = copy.deepcopy(self.eligibility)
            measures = self.measures
            if damage == "block":
                eligibility.pop(score.BLOCKS[-1])
            elif damage == "measure":
                eligibility[score.BLOCKS[0]].pop(measures[0])
            elif damage == "reason":
                eligibility[score.BLOCKS[0]][measures[1]] = ""
            else:
                measures = measures[:-1]
            with self.subTest(damage=damage), self.assertRaises(score.ScoreError):
                score.expected_cells(measures, eligibility)

    def test_imports_author_csv_with_ordered_dimensions(self):
        result = score.read_author_matrix(csv_text(self.cells), self.cells)
        self.assertEqual(tuple(result), self.cells)
        self.assertEqual(result[self.cells[0]], {"accuracy": 0.6, "accuracy_SD": 0.1, "AUC": 0.7, "AUC_SD": 0.2})
        self.assertEqual({key[1:3] for key in result}, set(score.ROI_PAIRS))

    def test_import_rejects_missing_duplicate_and_foreign_rows(self):
        cases = (self.cells[:-1], self.cells + (self.cells[0],), self.cells + (("unknown", *self.cells[0][1:]),))
        for cells in cases:
            with self.assertRaises(score.ScoreError):
                score.read_author_matrix(csv_text(cells), self.cells)

    def test_import_rejects_metric_substitution_nonfinite_and_wrong_family(self):
        for field, value in (("classifier", "Linear_SVM"), ("accuracy", "nan"), ("accuracy", "64.3"), ("accuracy_SD", "0.6"), ("stimulus_combo", "('face','non-face')"), ("relevance_type", "relevant_to_irrelevant")):
            def mutate(index, row):
                if index == 0:
                    row[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(score.ScoreError):
                score.read_author_matrix(csv_text(self.cells, mutate), self.cells)

    def test_import_rejects_duplicate_columns_and_ragged_rows(self):
        text = csv_text(self.cells).getvalue()
        for malformed in (text.replace("AUC_SD", "AUC", 1), text.replace("0.2\r\n", "0.2,extra\r\n", 1)):
            with self.assertRaises(score.ScoreError):
                score.read_author_matrix(io.StringIO(malformed), self.cells)

    def test_complete_scoring_and_comparison_retain_every_cell(self):
        rows, probabilities = fixture()
        def inputs():
            for cell in self.cells:
                c0, c1 = cell[-2:]
                adapted = [{**r, "label": c0 if r["label"] == "face" else c1} for r in rows]
                yield cell, adapted, probabilities
        candidate = score.score_complete_matrix(self.cells, inputs())
        reference = score.read_author_matrix(csv_text(self.cells), self.cells)
        differences = score.compare_matrices(candidate, reference)
        self.assertEqual(len(differences), len(self.cells))
        self.assertAlmostEqual(differences[self.cells[-1]]["accuracy_difference"], 0.3)
        self.assertFalse(any("win" in key for row in differences.values() for key in row))
        with self.assertRaises(score.ScoreError):
            score.score_complete_matrix(self.cells, iter(()))
        candidate.pop(self.cells[0])
        with self.assertRaises(score.ScoreError):
            score.compare_matrices(candidate, reference)


if __name__ == "__main__":
    unittest.main()
