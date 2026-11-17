"""Generated software controls only; contains no authentic participant values."""

import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("source_statistic", Path(__file__).with_name("source_statistic.py"))
statistic = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(statistic)


def panel():
    # Every fixture row is generated; the arithmetic totals are hand-checkable.
    return [
        {"participant_id": participant, "model": model, "log_likelihood": -participant * multiplier}
        for model, multiplier in (("active_inference", 1), ("model_free_rl", 2), ("model_based_rl", 3))
        for participant in range(1, 26)
    ]


def csv_body(rows):
    return ("participant_id,model,log_likelihood\n" + "".join(
        f"{r['participant_id']},{r['model']},{r['log_likelihood']}\n" for r in rows
    )).encode()


class SourceStatisticTests(unittest.TestCase):
    def test_exact_source_arithmetic_not_25_parameter_penalties(self):
        result = statistic.reduce_panel(panel())
        # 1+...+25 = 325. The source uses one k penalty, not 25*k.
        for model, expected in {
            "active_inference": 650 + 5 * math.log(6000),
            "model_free_rl": 1300 + 2 * math.log(6000),
            "model_based_rl": 1950 + 3 * math.log(6000),
        }.items():
            self.assertAlmostEqual(result["models"][model]["literal_source_statistic"], expected)
        self.assertFalse(result["source_statistic_is_standard_bic"])
        self.assertAlmostEqual(result["active_inference_minus_comparator"]["model_free_rl"], -650 + 3 * math.log(6000))
        self.assertNotAlmostEqual(result["models"]["active_inference"]["literal_source_statistic"], 650 + 125 * math.log(6000))
        self.assertFalse(result["input_likelihoods_authenticated"])

    def test_order_and_csv_round_trip(self):
        expected = statistic.reduce_panel(panel())
        self.assertEqual(statistic.reduce_panel(list(reversed(panel()))), expected)
        self.assertEqual(statistic.reduce_panel(statistic.read_panel(csv_body(panel()))), expected)

    def test_no_silent_subset_or_duplicate(self):
        for rows in (panel()[:-1], panel()[3:], panel() + panel()[:1], panel()[:-1] + panel()[:1]):
            with self.subTest(rows=len(rows)), self.assertRaises(ValueError):
                statistic.reduce_panel(rows)

    def test_invalid_identity_values_and_nonfinite_aggregates(self):
        changes = [
            ("participant_id", True), ("participant_id", 26), ("participant_id", "1"),
            ("model", "new_model"), ("log_likelihood", True), ("log_likelihood", 0.1),
            ("log_likelihood", None), ("log_likelihood", float("nan")),
            ("log_likelihood", float("inf")), ("log_likelihood", -float("inf")),
            ("log_likelihood", 10 ** 1000),
        ]
        for field, value in changes:
            rows = panel()
            rows[0][field] = value
            with self.subTest(field=field, value=repr(value)), self.assertRaises(ValueError):
                statistic.reduce_panel(rows)
        rows = panel()
        for row in rows:
            row["log_likelihood"] = -1e308
        with self.assertRaises(ValueError):
            statistic.reduce_panel(rows)

    def test_likelihood_origin_is_not_inferred(self):
        rows = panel()
        for row in rows:
            row["log_likelihood"] = 0
        result = statistic.reduce_panel(rows)
        self.assertAlmostEqual(result["models"]["active_inference"]["literal_source_statistic"], 5 * math.log(6000))
        self.assertFalse(result["published_numeric_baseline_authenticated"])
        self.assertEqual(result["scope"], "source_arithmetic_only")

    def test_transport_rejects_extra_columns_blank_rows_and_aliases(self):
        body = csv_body(panel())
        for malformed in (
            body.replace(b"participant_id,model", b"participant_id,participant_id", 1),
            body.replace(b"1,active_inference", b"01,active_inference", 1),
            body + b"\n", body.replace(b"-1\n", b"-1,ignored\n", 1),
            b"x" * 65537,
        ):
            with self.subTest(body=malformed[:100]), self.assertRaises(ValueError):
                statistic.read_panel(malformed)

    def test_cli_and_failure_do_not_overwrite_results(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / "input.csv", Path(directory) / "result.json"
            source.write_bytes(csv_body(panel()))
            args = ["--input", str(source), "--output", str(target)]
            statistic.main(args)
            original = target.read_bytes()
            self.assertEqual(json.loads(original)["fit_count"], 75)
            with self.assertRaises(FileExistsError):
                statistic.main(args)
            self.assertEqual(target.read_bytes(), original)
            target.unlink()
            source.write_bytes(csv_body(panel()[:-1]))
            with self.assertRaises(ValueError):
                statistic.main(args)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
