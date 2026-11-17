"""Generated report controls only; no recordings, private targets or models."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location("ern_metric", Path(__file__).with_name("score.py"))
score = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(score)


def fixture(values=None, counts=None):
    """Invented complete report, following the source report's exact schema."""
    values = values or [-2.0, 0.0, 2.0, 4.0, -4.0, 1.0, -1.0, 3.0]
    counts = counts or [10, 20, 30, 40, 50, 60, 70, 80]
    rows = []
    for person, value, count in zip(score.PEOPLE, values, counts):
        strata = {key: {"error_n": 0, "correct_n": 0, "pairs_n": 0} for key in score.STRATA}
        strata[score.STRATA[0]] = {"error_n": count, "correct_n": count, "pairs_n": count}
        row = {"participant_id": person, "eligible_error_n": count, "eligible_correct_n": count,
               "matched_pairs_n": count, "pair_digest": hashlib.sha256(("fixture-" + person).encode()).hexdigest(),
               "stratum_support": strata, "status": "supported" if count >= 10 else "insufficient_matched_pairs"}
        row.update({key: 0.0 if count >= 10 else None for key in score.NUMBERS})
        if count >= 10:
            row["matched_FCz_contrast"] = value
        rows.append(row)
    supported = all(count >= 10 for count in counts)
    mean = sum(values) / 8 if supported else None
    se = math.sqrt(sum((x - mean) ** 2 for x in values) / 7) / math.sqrt(8) if supported else None
    return {"schema": "neural078_contrast_submission_v1", "protocol_sha256": score.PROTOCOL_SHA256,
            "participants": rows,
            "aggregate": {"status": "all_participants_supported" if supported else "not_all_participants_supported",
                          "matched_FCz_equal_person_mean": mean,
                          "matched_FCz_between_person_descriptive_SE": se}}


class MetricTests(unittest.TestCase):
    def test_equal_person_error_cannot_cancel_or_weight_by_pairs(self):
        gold = fixture()
        candidate = fixture([-1, -2, 2, 8, -5, 1.5, -1.5, 1])
        result = score.compare(candidate, gold)
        self.assertEqual(result["primary"]["value"], 1.375)
        self.assertEqual(result["aggregate_absolute_errors"]["matched_FCz_equal_person_mean"], 0)
        self.assertEqual(result["supported_subset_sign_agreement"], 7 / 8)
        self.assertEqual(result["primary"]["unit"], "native_EEGLAB_amplitude")
        self.assertEqual(result["fixed_zero_contrast_baseline"]["participant_macro_mae"], 17 / 8)

    def test_exact_null_and_reversed_effects_are_valid(self):
        for values in ([0] * 8, [2] * 8, [-2] * 8):
            report = fixture(values)
            result = score.compare(report, report)
            self.assertEqual(result["primary"]["value"], 0)
            self.assertTrue(result["sign_is_diagnostic_only"])

    def test_participant_row_order_is_not_weight_or_identity(self):
        gold = fixture()
        candidate = copy.deepcopy(gold)
        candidate["participants"].reverse()
        result = score.compare(candidate, gold)
        self.assertEqual(result["primary"]["value"], 0)
        self.assertEqual([r["participant_id"] for r in result["participants"]], list(score.PEOPLE))

    def test_unsupported_reference_never_replaced_by_subset_primary(self):
        gold = fixture(counts=[9, 20, 30, 40, 50, 60, 70, 80])
        candidate = copy.deepcopy(gold)
        candidate["participants"][1]["matched_FCz_contrast"] = 7.0
        result = score.compare(candidate, gold)
        self.assertIsNone(result["primary"]["value"])
        self.assertEqual(result["primary"]["supported_participants"], 7)
        self.assertEqual(result["unsupported_participants"], ["sub-001"])
        self.assertEqual(result["numeric_field_diagnostics"]["matched_FCz_contrast"]["supported_subset_mae"], 1.0)
        self.assertIsNone(result["aggregate_absolute_errors"]["matched_FCz_equal_person_mean"])
        self.assertIsNone(result["fixed_zero_contrast_baseline"]["participant_macro_mae"])

    def test_no_supported_reference_returns_no_numeric_result(self):
        report = fixture(counts=[0] * 8)
        result = score.compare(report, report)
        self.assertIsNone(result["primary"]["value"])
        self.assertIsNone(result["supported_subset_sign_agreement"])
        self.assertTrue(all(v["supported_subset_mae"] is None for v in result["numeric_field_diagnostics"].values()))

    def test_support_cannot_be_changed_to_drop_hard_person(self):
        gold = fixture()
        candidate = fixture(counts=[9, 20, 30, 40, 50, 60, 70, 80])
        with self.assertRaisesRegex(ValueError, "Support identity differs"):
            score.compare(candidate, gold)

    def test_digest_and_stratum_commitments_must_match(self):
        gold = fixture()
        for edit in ("digest", "strata", "count"):
            candidate = copy.deepcopy(gold)
            row = candidate["participants"][0]
            if edit == "digest":
                row["pair_digest"] = "f" * 64
            elif edit == "strata":
                row["stratum_support"][score.STRATA[1]] = row["stratum_support"][score.STRATA[0]]
                row["stratum_support"][score.STRATA[0]] = {"error_n": 0, "correct_n": 0, "pairs_n": 0}
            else:
                row["eligible_error_n"] += 1
                row["stratum_support"][score.STRATA[0]]["error_n"] += 1
            with self.subTest(edit=edit), self.assertRaisesRegex(ValueError, "Support identity differs"):
                score.compare(candidate, gold)

    def test_all_numeric_diagnostics_stay_in_source_units(self):
        gold = fixture()
        candidate = copy.deepcopy(gold)
        for row in candidate["participants"]:
            for index, key in enumerate(score.NUMBERS):
                row[key] += index + 1
        for index, key in enumerate(score.AGGREGATE_NUMBERS):
            candidate["aggregate"][key] += index + 10
        result = score.compare(candidate, gold)
        for index, key in enumerate(score.NUMBERS):
            self.assertEqual(result["numeric_field_diagnostics"][key]["supported_subset_mae"], index + 1)
            self.assertEqual(result["numeric_field_diagnostics"][key]["unit"], "ms" if index < 2 else score.AMPLITUDE_UNIT)
        for index, key in enumerate(score.AGGREGATE_NUMBERS):
            self.assertEqual(result["aggregate_absolute_errors"][key], index + 10)
        self.assertEqual(len(result["participants"]) * len(score.NUMBERS) + len(score.AGGREGATE_NUMBERS), 58)

    def test_invalid_complete_schema_and_nonfinite_values_refused(self):
        mutations = [lambda d: d["participants"].pop(),
                     lambda d: d["participants"].__setitem__(1, copy.deepcopy(d["participants"][0])),
                     lambda d: d["participants"][0].__setitem__("matched_FCz_contrast", float("nan")),
                     lambda d: d["participants"][0].__setitem__("matched_FCz_contrast", True),
                     lambda d: d["participants"][0].__setitem__("matched_FCz_contrast", None),
                     lambda d: d["participants"][0].__setitem__("eligible_error_n", True),
                     lambda d: d["aggregate"].__setitem__("matched_FCz_between_person_descriptive_SE", -1),
                     lambda d: d.__setitem__("protocol_sha256", "0" * 64),
                     lambda d: d.__setitem__("extra", 0)]
        for mutation in mutations:
            report = fixture()
            mutation(report)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                score.validate_report(report)

    def test_supported_threshold_exactly_ten(self):
        report = fixture(counts=[10] * 8)
        self.assertEqual(score.compare(report, report)["primary"]["supported_participants"], 8)
        report = fixture(counts=[9] * 8)
        report["participants"][0]["matched_FCz_contrast"] = 0
        with self.assertRaises(ValueError):
            score.validate_report(report)

    def test_extreme_error_refused_instead_of_infinity(self):
        gold = fixture()
        candidate = copy.deepcopy(gold)
        gold["participants"][0]["matched_FCz_contrast"] = -1e308
        candidate["participants"][0]["matched_FCz_contrast"] = 1e308
        with self.assertRaisesRegex(ValueError, "arithmetic range"):
            score.compare(candidate, gold)

    def test_subnormal_mean_refused_instead_of_false_zero_error(self):
        gold = fixture([0] * 8)
        candidate = copy.deepcopy(gold)
        candidate["participants"][0]["matched_FCz_contrast"] = math.ulp(0.0)
        with self.assertRaisesRegex(ValueError, "arithmetic range"):
            score.compare(candidate, gold)

    def test_large_finite_errors_do_not_overflow_mean_sum(self):
        gold = fixture([0] * 8)
        candidate = copy.deepcopy(gold)
        for row in candidate["participants"]:
            row["matched_FCz_contrast"] = 1e308
        self.assertEqual(score.compare(candidate, gold)["primary"]["value"], 1e308)


class CLITests(unittest.TestCase):
    def test_duplicate_nonfinite_oversized_json_refused(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b" " * 65537):
            with self.subTest(raw=raw[:50]), self.assertRaises(ValueError):
                score.parse_json(raw)

    def test_invalid_submission_is_rejected_before_gold_read(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            submission = root / "candidate.json"
            submission.write_text("{}")
            gold = root / "NEVER_OPEN.json"
            original = score.read_bytes
            opened = []
            def observed(path):
                opened.append(path)
                return original(path)
            with mock.patch.object(score, "read_bytes", side_effect=observed), contextlib.redirect_stderr(io.StringIO()):
                code = score.main(["--submission", str(submission), "--gold", str(gold),
                                   "--gold-sha256", "0" * 64, "--output", str(root / "score.json")])
            self.assertEqual(code, 2)
            self.assertEqual(opened, [submission])

    def test_complete_cli_identity_output_and_wrong_gold_refusal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            body = (json.dumps(fixture()) + "\n").encode()
            candidate, gold, output = [root / name for name in ("candidate.json", "gold.json", "score.json")]
            candidate.write_bytes(body)
            gold.write_bytes(body)
            args = ["--submission", str(candidate), "--gold", str(gold), "--gold-sha256",
                    hashlib.sha256(body).hexdigest(), "--output", str(output)]
            self.assertEqual(score.main(args), 0)
            result = json.loads(output.read_text())
            self.assertEqual(result["primary"]["value"], 0)
            self.assertEqual(result["submission_sha256"], hashlib.sha256(body).hexdigest())
            self.assertEqual(result["reference_sha256"], hashlib.sha256(body).hexdigest())
            before = output.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(score.main(args), 2)
            self.assertEqual(output.read_bytes(), before)
            args[-1] = str(root / "wrong-reference-score.json")
            args[5] = "0" * 64
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(score.main(args), 2)
            self.assertFalse(Path(args[-1]).exists())

    def test_nonregular_and_symlink_inputs_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "report.json"
            target.write_text("{}")
            link = root / "link.json"
            link.symlink_to(target)
            for path in (root, link):
                with self.subTest(path=path), self.assertRaises((OSError, ValueError)):
                    score.read_bytes(path)

    @unittest.skipUnless(hasattr(os, "mkfifo") and hasattr(os, "O_NONBLOCK"), "POSIX FIFO control")
    def test_fifo_refused_without_waiting_for_writer(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "pipe"
            os.mkfifo(path)
            with self.assertRaisesRegex(ValueError, "regular file"):
                score.read_bytes(path)


if __name__ == "__main__":
    unittest.main()
