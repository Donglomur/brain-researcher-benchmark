"""Generated controls for result extraction; no authentic BANC rows are used."""
import csv
import io
import math
import unittest

from inspect_results import BODY_PARTS, COLUMNS, MAX_CSV_BYTES, ResultError, inspect_csv


def example_matrix():
    return [[0.1 + ((i + 1) * (j + 2) % 17) / 25 for j in range(14)] for i in range(14)]


def rows_for(matrix):
    rows = []
    for i, target in enumerate(BODY_PARTS):
        for j, source in enumerate(BODY_PARTS):
            a, b = matrix[i], matrix[j]
            denominator = math.sqrt(sum(x*x for x in a) * sum(x*x for x in b))
            cosine = sum(x*y for x, y in zip(a, b)) / denominator if denominator else 0
            rows.append([source, target, repr(cosine), repr(matrix[i][j]), "TRUE" if i == j else "FALSE"])
    return rows


def encode(rows, columns=COLUMNS):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, quoting=csv.QUOTE_NONNUMERIC, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


class SourceResultTests(unittest.TestCase):
    def setUp(self):
        self.matrix = example_matrix()
        self.rows = rows_for(self.matrix)

    def inspect(self, rows=None, metric="influence_log_minmax"):
        return inspect_csv(encode(self.rows if rows is None else rows), metric=metric)

    def test_complete_source_matrix_and_orientation(self):
        result = self.inspect()
        self.assertEqual(result["statistical_paired_matrix"], self.matrix)
        self.assertEqual(result["support_counts"], {"body_parts":14,"cells":196,"same":14,"different":182})
        self.assertEqual(result["same_body_part_values"], [self.matrix[i][i] for i in range(14)])
        self.assertEqual(result["different_body_part_values"][0], self.matrix[0][1])
        self.assertLess(result["cosine_max_absolute_residual"], 1e-12)

    def test_row_order_is_not_a_new_support_or_matrix_orientation(self):
        result = self.inspect(self.rows[::-1])
        self.assertEqual(result["statistical_paired_matrix"], self.matrix)
        self.assertEqual(result["source_cosine_matrix"], self.inspect()["source_cosine_matrix"])

    def test_display_renormalization_does_not_replace_statistical_operands(self):
        result = self.inspect()
        self.assertNotEqual(result["paired_heatmap_display_matrix"], self.matrix)
        for original, display in zip(self.matrix, result["paired_heatmap_display_matrix"]):
            self.assertEqual(min(display), 0)
            self.assertEqual(max(display), 1)
            self.assertGreater(min(original), 0)
        display_rows = rows_for(result["paired_heatmap_display_matrix"])
        # A mixed result table has display-derived cosine and original influence.
        for changed, original in zip(display_rows, self.rows):
            changed[3] = original[3]
        with self.assertRaisesRegex(ResultError, "cosine does not match"):
            self.inspect(display_rows)

    def test_nonminmax_metrics_do_not_acquire_display_rescaling(self):
        for metric in ("influence_log", "influence_norm_log"):
            result = self.inspect(metric=metric)
            self.assertEqual(result["paired_heatmap_display_matrix"], self.matrix)
            self.assertFalse(result["display_renormalized_on_paired_subset"])

    def test_zero_and_constant_rows_preserve_author_zero_vector_branch(self):
        matrix = example_matrix()
        matrix[0] = [0.0] * 14
        matrix[1] = [0.4] * 14
        result = self.inspect(rows_for(matrix))
        self.assertEqual(result["source_cosine_matrix"][0], [0.0] * 14)
        self.assertEqual(result["paired_heatmap_display_matrix"][0], [0.0] * 14)
        self.assertEqual(result["paired_heatmap_display_matrix"][1], [0.0] * 14)
        self.assertAlmostEqual(result["source_cosine_matrix"][1][1], 1)

    def test_duplicate_pair_cannot_replace_missing_pair(self):
        rows = self.rows[:]
        rows[-1] = rows[0]
        with self.assertRaisesRegex(ResultError, "duplicate"):
            self.inspect(rows)

    def test_any_missing_pair_refuses_full_support(self):
        with self.assertRaisesRegex(ResultError, "incomplete"):
            self.inspect(self.rows[:-1])

    def test_unknown_body_part_is_not_silently_intersected_away(self):
        rows = [row[:] for row in self.rows]
        rows[0][0] = "thoracic-abdominal"
        with self.assertRaisesRegex(ResultError, "support differs"):
            self.inspect(rows)

    def test_diagonal_flags_and_exact_r_booleans_are_required(self):
        for value in ("FALSE", "1", "true", ""):
            rows = [row[:] for row in self.rows]
            rows[0][4] = value
            with self.assertRaisesRegex(ResultError, "diagonal flag"):
                self.inspect(rows)

    def test_nonfinite_values_are_never_coerced_into_zero(self):
        for column in (2, 3):
            for value in ("NaN", "Inf", "-Infinity", "NA", "1e9999"):
                rows = [row[:] for row in self.rows]
                rows[0][column] = value
                with self.assertRaises(ResultError):
                    self.inspect(rows)

    def test_numeric_underflow_and_non_source_spellings_are_rejected(self):
        for column in (2, 3):
            for value in ("1e-999", "-1e-999", "1_0", "\u0661", " 0"):
                rows = [row[:] for row in self.rows]
                rows[0][column] = value
                with self.subTest(column=column, value=value), self.assertRaises(ResultError):
                    self.inspect(rows)
        matrix = [[0.0] * 14 for _ in range(14)]
        rows = rows_for(matrix)
        for row in rows:
            row[3] = "-0e-999"
        result = self.inspect(rows)
        self.assertEqual(result["statistical_paired_matrix"], matrix)

    def test_minmax_bounds_and_metric_declaration_are_closed(self):
        for value in ("-0.01", "1.01"):
            rows = [row[:] for row in self.rows]
            rows[0][3] = value
            with self.assertRaisesRegex(ResultError, "minmax"):
                self.inspect(rows)
        with self.assertRaisesRegex(ResultError, "metric"):
            self.inspect(metric="accuracy")

    def test_inconsistent_cosine_is_not_accepted_as_independent_evidence(self):
        rows = [row[:] for row in self.rows]
        rows[1][2] = "0"
        with self.assertRaisesRegex(ResultError, "cosine does not match"):
            self.inspect(rows)

    def test_closed_csv_schema_and_utf8(self):
        with self.assertRaisesRegex(ResultError, "columns"):
            inspect_csv(encode(self.rows, COLUMNS + ("p_value",)), metric="influence_log_minmax")
        with self.assertRaisesRegex(ResultError, "columns"):
            inspect_csv(encode(self.rows, (COLUMNS[0],)*5), metric="influence_log_minmax")
        with self.assertRaisesRegex(ResultError, "UTF-8"):
            inspect_csv(b"\xff", metric="influence_log_minmax")
        rows = [row[:] for row in self.rows]
        rows[0].append("unexpected")
        with self.assertRaisesRegex(ResultError, "malformed"):
            self.inspect(rows)

    def test_input_bound_and_no_producer_or_scientific_promotion(self):
        for body in (b"", b"x"*(MAX_CSV_BYTES+1), "not bytes"):
            with self.assertRaises(ResultError):
                inspect_csv(body, metric="influence_log_minmax")
        result = self.inspect()
        self.assertFalse(result["metric_and_producer_authenticated"])
        self.assertFalse(result["source_pipeline_reproduced"])
        self.assertFalse(result["primary_panel_selected"])
        self.assertIsNone(result["reproduction_outcome"])
        self.assertIsNone(result["improvement_outcome"])


if __name__ == "__main__":
    unittest.main()
