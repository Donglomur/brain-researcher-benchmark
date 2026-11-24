"""Generated software controls only; contains no authentic participant values."""

import importlib.util
import hashlib
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

    def test_complete_paired_differences_follow_identity_not_row_order(self):
        reference, candidate = panel(), panel()
        # Improve one participant and worsen another; retain both changes.
        candidate[0]["log_likelihood"] += 0.5
        candidate[24]["log_likelihood"] -= 2
        candidate[25]["log_likelihood"] += 1
        result = statistic.compare_panels(list(reversed(reference)), candidate[17:] + candidate[:17])
        self.assertEqual(result["paired_fit_count"], 75)
        self.assertEqual(result["scope"], "paired_source_arithmetic_only")
        for model, expected in (("active_inference", 3), ("model_free_rl", -2), ("model_based_rl", 0)):
            values = result["models"][model]
            self.assertEqual(values["candidate_minus_reference_literal_source_statistic"], expected)
            self.assertEqual(values["candidate_minus_reference_source_penalty"], 0)
            self.assertEqual([r["participant_id"] for r in values["participant_differences"]], list(range(1, 26)))
        changes = result["models"]["active_inference"]["participant_differences"]
        self.assertEqual(changes[0]["candidate_minus_reference_log_likelihood_nats"], 0.5)
        self.assertEqual(changes[-1]["candidate_minus_reference_log_likelihood_nats"], -2)
        for flag in ("same_source_models_and_likelihood_masks_authenticated", "scientific_reproduction_verified",
                     "scientific_improvement_verified", "readiness_promoted"):
            self.assertFalse(result[flag])

    def test_pairing_rejects_incomplete_or_duplicated_panel_on_either_side(self):
        malformed = [panel()[:-1], panel()[:-1] + panel()[:1],
                     [row for row in panel() if row["participant_id"] not in (2, 3)]]
        for rows in malformed:
            for left, right in ((rows, panel()), (panel(), rows)):
                with self.subTest(left=len(left), right=len(right)), self.assertRaises(ValueError):
                    statistic.compare_panels(left, right)

    def test_paired_changes_are_summed_before_rounding_cohort_totals(self):
        reference, candidate = panel(), panel()
        for rows in (reference, candidate):
            for row in rows:
                row["log_likelihood"] = -1e15
        candidate[0]["log_likelihood"] += 1
        result = statistic.compare_panels(reference, candidate)
        model = "active_inference"
        self.assertEqual(result["reference"]["models"][model]["literal_source_statistic"],
                         result["candidate"]["models"][model]["literal_source_statistic"])
        self.assertEqual(result["models"][model]["candidate_minus_reference_literal_source_statistic"], -2)

    def test_paired_cli_binds_both_inputs_and_never_publishes_partial_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            reference = Path(directory) / "reference.csv"
            candidate = Path(directory) / "candidate.csv"
            target = Path(directory) / "result.json"
            reference.write_bytes(csv_body(panel()))
            candidate.write_bytes(csv_body(list(reversed(panel()))))
            args = ["--input", str(candidate), "--reference", str(reference), "--output", str(target)]
            statistic.main(args)
            original = target.read_bytes()
            result = json.loads(original)
            self.assertEqual(result["reference_input_sha256"], hashlib.sha256(reference.read_bytes()).hexdigest())
            self.assertEqual(result["candidate_input_sha256"], hashlib.sha256(candidate.read_bytes()).hexdigest())
            self.assertEqual(result["input_sha256"], result["candidate_input_sha256"])
            with self.assertRaises(FileExistsError):
                statistic.main(args)
            self.assertEqual(target.read_bytes(), original)
            target.unlink()
            reference.write_bytes(csv_body(panel()[:-1]))
            with self.assertRaises(ValueError):
                statistic.main(args)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
