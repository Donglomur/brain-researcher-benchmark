"""Generated public-format controls. No NWB files or private answers are read."""
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import submission


PUBLIC = Path(os.environ.get("FIND044_PUBLIC_DIR", str(Path(__file__).resolve().parents[1] / "registered-runtime")))


class PublicSubmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract, cls.schema = submission.load_public(PUBLIC)
        cls.template = submission.scaffold(cls.contract, cls.schema)

    def setUp(self):
        self.document = copy.deepcopy(self.template)

    def record(self, table, index=0, **updates):
        columns = self.document[table]["columns"]
        row = self.document[table]["rows"][index]
        for field, value in updates.items():
            row[columns.index(field)] = value

    def check(self):
        return submission.validate(self.document, self.contract, self.schema)

    def test_complete_original_identity_scaffold(self):
        result = self.check()
        self.assertEqual(result["row_counts"], {
            "session_audit": 309, "trials": 8679, "daily": 302, "mice": 38,
            "group_e": 440, "group_endpoints": 6, "comparisons": 3,
        })
        self.assertIsNone(result["scientific_score"])
        self.assertFalse(result["numerical_correctness_checked"])
        self.assertFalse(result["paper_improvement_claim"])
        self.assertEqual(len([row for row in self.contract["mice"] if row["condition"] == "60s"]), 19)
        self.assertEqual(len([row for row in self.contract["mice"] if row["condition"] == "600s"]), 19)
        self.assertTrue(any("D_" in row[0] for row in self.document["mice"]["rows"]))
        self.assertTrue(any(row["day"] == 9 for row in self.contract["sessions"]))
        self.assertTrue(all(row[1] <= 8 for row in self.document["daily"]["rows"]))
        # Split sessions keep separate assets/cues but one mouse/day daily entry.
        source_daily = [(row["mouse_id"], row["day"]) for row in self.contract["sessions"] if row["day"] <= 8]
        self.assertGreater(len(source_daily), len(set(source_daily)))
        self.assertEqual(set(map(tuple, self.document["daily"]["rows"])),
                         {(mouse, day, 0, None, None, "unresolved") for mouse, day in source_daily})

    def test_rows_can_reorder_without_changing_coverage(self):
        for table in self.schema["tables"]:
            self.document[table]["rows"].reverse()
        self.check()

    def test_cue_cutoff_and_prefix_rows_remain_in_complete_support(self):
        self.record("trials", 0, state="recording_cutoff_removed")
        self.record("trials", 1, state="prefix_removed", baseline_licks=3,
                    anticipatory_licks=1, consumption_licks=0, normalized_count=-2,
                    rate_hz=-1.6, actual_duration_s=1.25, original_ITI_s=60.0)
        self.check()
        self.document["trials"]["rows"].pop(0)
        with self.assertRaisesRegex(ValueError, "incomplete identity coverage"):
            self.check()

    def test_duplicate_mice_and_cue_ordinals_do_not_replace_missing_ones(self):
        for table in ("mice", "trials", "daily", "group_e", "comparisons"):
            with self.subTest(table=table):
                original = self.document[table]["rows"][1]
                self.document[table]["rows"][1] = copy.deepcopy(self.document[table]["rows"][0])
                with self.assertRaisesRegex(ValueError, "duplicate identity"):
                    self.check()
                self.document[table]["rows"][1] = original

    def test_full_condition_endpoint_partition(self):
        columns = self.document["group_endpoints"]["columns"]
        row = self.document["group_endpoints"]["rows"][0]
        excluded = row[columns.index("undefined_or_ineligible_mouse_statuses")]
        mouse = next(iter(excluded))
        self.record("group_endpoints", included_mouse_ids=[mouse])
        with self.assertRaisesRegex(ValueError, "partition"):
            self.check()
        del excluded[mouse]
        self.check()
        excluded["other_condition_mouse"] = "unresolved"
        with self.assertRaisesRegex(ValueError, "partition"):
            self.check()

    def test_retained_negative_counts_are_valid_but_missing_values_are_not(self):
        self.record("trials", state="retained", baseline_licks=4, anticipatory_licks=1,
                    consumption_licks=2, normalized_count=-3, rate_hz=-2.4,
                    actual_duration_s=1.25, original_ITI_s=60, retained_index=1,
                    cumulative_normalized_count=-3)
        self.check()
        self.record("trials", rate_hz=None)
        with self.assertRaisesRegex(ValueError, "rate_hz"):
            self.check()

    def test_every_status_branch_and_finite_inaccurate_answers(self):
        # Intentionally inconsistent but finite values remain scoreable: this is
        # public format validation, not a numerical correctness oracle.
        self.record("daily", status="defined", mean_rate_hz=-123.0, meets_threshold=True)
        self.record("mice", mouse_status="defined", learner_status="defined", is_learner=True,
                    g_status="defined", learned_trial=800, h_status="defined", time_to_learn_s=-20.0,
                    h_selected_rows=0, h_next_trial_present=False, k_status="defined", k_mean_rate_hz=9.0)
        self.record("group_e", status="mean_only_n1", mean_rate_hz=3.0)
        self.record("group_endpoints", status="defined", mean=0.0, sample_sd=0.0, sem=0.0)
        self.record("comparisons", welch_status="defined", difference=3.0,
                    standard_error=2.0, t=99.0, welch_df=4.0, p_two_sided=1.1,
                    F_status="source_formula_outside_probability_range", F=3.0,
                    F_source_p=1.2, F_numerator_condition="600s", F_df1=3, F_df2=4)
        self.check()
        self.record("comparisons", welch_status="zero_standard_error_undefined",
                    standard_error=0.0, t=None, welch_df=None, p_two_sided=None,
                    F_status="source_equal_variances_branch", F=1.0, F_source_p=1.0,
                    F_numerator_condition=None, F_df1=None, F_df2=None)
        self.check()
        self.record("comparisons", F_df1=3)
        with self.assertRaisesRegex(ValueError, "must be null"):
            self.check()

    def test_boolean_and_null_status_types_do_not_coerce(self):
        for field, value in (("day", True), ("retained_trials", True), ("retained_trials", -1),
                             ("status", "invented"), ("mean_rate_hz", 0.0)):
            with self.subTest(field=field):
                original = copy.deepcopy(self.document["daily"]["rows"][0])
                self.record("daily", **{field: value})
                with self.assertRaises(ValueError):
                    self.check()
                self.document["daily"]["rows"][0] = original
        self.document["schema_version"] = True
        with self.assertRaisesRegex(ValueError, "wrong header"):
            self.check()

    def test_container_columns_and_header_cannot_change(self):
        self.document["extra"] = 1
        with self.assertRaisesRegex(ValueError, "root"):
            self.check()
        del self.document["extra"]
        self.document["trials"]["columns"].reverse()
        with self.assertRaisesRegex(ValueError, "ordered columns"):
            self.check()

    def test_strict_json_parser(self):
        malformed = [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}',
                     b'{"a":1e999}', b'{"a":"\\ud800"}', b'{"a":"\xff"}',
                     b'[' * 13 + b'0' + b']' * 13,
                     b'{"a":' + b'1' * 33 + b'}',
                     b'{"a":0.' + b'1' * 129 + b'}']
        for payload in malformed:
            with self.subTest(payload=payload[:30]):
                with self.assertRaises(ValueError):
                    submission.parse_submission(payload, 2500000)
        with self.assertRaisesRegex(ValueError, "payload cap"):
            submission.parse_submission(b'{}', 1)
        encoded = json.dumps(self.template).encode()
        self.assertEqual(submission.parse_submission(encoded, 2500000), self.template)

    def test_cli_scaffold_validate_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "submission.json"
            report = Path(temp) / "preflight.json"
            prefix = ["submission.py", "--public-dir", str(PUBLIC)]
            with mock.patch("sys.argv", prefix + ["scaffold", "--output", str(output)]), \
                    mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
                self.assertEqual(submission.main(), 0)
                receipt = json.loads(stdout.getvalue())
                self.assertTrue(receipt["all_scientific_observations_unresolved"])
                self.assertLess(receipt["bytes"], 2500000)
            before = output.read_bytes()
            with mock.patch("sys.argv", prefix + ["scaffold", "--output", str(output)]), \
                    mock.patch("sys.stderr", new_callable=io.StringIO):
                self.assertEqual(submission.main(), 2)
            self.assertEqual(output.read_bytes(), before)
            with mock.patch("sys.argv", prefix + ["validate", "--submission", str(output), "--output", str(report)]):
                self.assertEqual(submission.main(), 0)
            result = json.loads(report.read_text())
            self.assertEqual(result["row_counts"]["trials"], 8679)
            self.assertEqual(result["submission_sha256"], receipt["sha256"])
            with mock.patch("sys.argv", prefix + ["validate", "--submission", str(output), "--output", str(report)]), \
                    mock.patch("sys.stderr", new_callable=io.StringIO):
                self.assertEqual(submission.main(), 2)

    def test_alternate_public_files_cannot_change_the_original_cohort(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / "PUBLIC_CONTRACT.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "pin mismatch"):
                submission.load_public(temp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
