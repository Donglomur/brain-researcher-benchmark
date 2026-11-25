"""Generated paired software controls; no authentic neural observations."""
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import paired_conditions as e


def fixture():
    public = {"schema_version": 1, "task_id": e.v1.TASK_ID, "protocol_sha256": "a" * 64,
              "heldout_families": ["natural_scenes", "natural_movie_one"],
              "state_prior_seconds": 1, "training": [], "query": []}
    targets, roster = [], []
    for sid, mouse, counts in (("s1", "m1", [1, 3]), ("s2", "m2", [2, 4, 2])):
        presentation_ids = ["p" + str(i) for i in range(len(counts) + 1)]
        for i, pid in enumerate(presentation_ids):
            row = {"key": [sid, "u", pid], "mouse_id": mouse,
                   "family": "drifting_gratings" if i == 0 else
                             "natural_scenes" if i == 1 else "natural_movie_one",
                   "condition_id": "c" + str(i), "start_time": i * 10,
                   "stop_time": i * 10 + 1, "exposure_seconds": 1,
                   "stimulus": {}, "running_speed": None, "running_coverage": 0,
                   "pupil_area": None, "pupil_coverage": 0}
            if i == 0:
                row["count"] = 2
                public["training"].append(row)
            else:
                public["query"].append(row)
                targets.append({"key": row["key"], "count": counts[i - 1]})
        roster.append({"session_id": sid, "mouse_id": mouse, "unit_ids": ["u"],
                       "presentation_ids": presentation_ids, "source_file_sha256": "b" * 64,
                       "source_file_bytes": 123, "presentation_table_sha256": "c" * 64})
    private = {"schema_version": 1, "task_id": e.v1.TASK_ID,
               "public_sha256": e.v1.digest(public), "targets": targets,
               "exclusions": [], "source_roster": roster}
    return public, private


def submission(public, condition, rate):
    return {"schema_version": "neural091-paired-submission/v1", "task_id": e.v1.TASK_ID,
            "condition": condition, "public_sha256": e.v1.digest(public),
            "predictions": [{"key": row["key"], "rate_hz": rate} for row in public["query"]]}


def comparison(public, private, restricted_rate=1, program_rate=2):
    return e.compare(public, private,
                     submission(public, "restricted_observation", restricted_rate),
                     submission(public, "frozen_program", program_rate), 17, 100)


def numeric_range_fixture():
    """Complete two-mouse/one-held-family generated packet, not biological data."""
    public, private = fixture()
    public["heldout_families"] = ["natural_scenes"]
    public["query"] = [row for row in public["query"] if row["family"] == "natural_scenes"]
    for row in public["training"]:
        row["count"] = 1
    keys = {tuple(row["key"]) for row in public["query"]}
    private["targets"] = [{"key": row["key"], "count": 1} for row in private["targets"]
                          if tuple(row["key"]) in keys]
    for row in private["source_roster"]:
        row["presentation_ids"] = ["p0", "p1"]
    private["public_sha256"] = e.v1.digest(public)
    return public, private


class PairedControls(unittest.TestCase):
    def test_hand_calculated_mouse_macro_is_not_spike_pooled(self):
        public, private = fixture()
        result = comparison(public, private)
        expected = ((1 - 2 / (4 * math.log(2))) + (1 - 3 / (8 * math.log(2)))) / 2
        paired = result["paired_overall"]
        self.assertAlmostEqual(paired["mouse_macro_difference_bits_per_spike"], expected)
        self.assertNotAlmostEqual(expected, 1 - 5 / (12 * math.log(2)))
        self.assertEqual(paired["mouse_count"], 2)
        self.assertEqual(paired["uncertainty"]["limits"],
                         [paired["mice"][0]["difference_bits_per_spike"],
                          paired["mice"][1]["difference_bits_per_spike"]])
        self.assertEqual(result["query_observations"], 5)
        self.assertFalse(result["actual_information_access_verified"])
        self.assertFalse(result["access_conditions_enforced"])
        self.assertFalse(result["research_qualified"])
        for condition, rate in (("restricted_observation", 1), ("frozen_program", 2)):
            expected_score = e.roster.score(public, private, submission(public, condition, rate)["predictions"], 17, 100)
            self.assertEqual(result["condition_scores"][condition], expected_score)
        for family, paired_family in result["paired_stimulus_families"].items():
            a = result["condition_scores"]["restricted_observation"]["stimulus_families"][family]
            b = result["condition_scores"]["frozen_program"]["stimulus_families"][family]
            self.assertAlmostEqual(paired_family["mouse_macro_difference_bits_per_spike"],
                                   b["mouse_macro_bits_per_spike"] - a["mouse_macro_bits_per_spike"])

    def test_finite_full_packet_mean_and_bootstrap_survive_sum_overflow(self):
        public, private = numeric_range_fixture()
        result = comparison(public, private, 1.0, 9e307)
        expected = -9e307 / math.log(2)
        programme = result["condition_scores"]["frozen_program"]
        self.assertEqual(programme["overall"]["status"], "finite")
        self.assertEqual(programme["overall"]["mouse_macro_bits_per_spike"], expected)
        self.assertEqual(programme["uncertainty"]["limits"], [expected, expected])
        self.assertEqual(result["paired_overall"]["mouse_macro_difference_bits_per_spike"], expected)
        self.assertEqual(result["paired_overall"]["uncertainty"]["limits"], [expected, expected])
        self.assertEqual(programme["declared_roster_coverage"]["query_observations"], 2)
        json.dumps(result, allow_nan=False)

    def test_finite_per_mouse_likelihood_ratio_survives_gain_sum_overflow(self):
        public, private = fixture()
        result = comparison(public, private, 2.0, 9e307)
        programme = result["condition_scores"]["frozen_program"]["overall"]
        expected = [-9e307 * (2 / (4 * math.log(2))),
                    -9e307 * (3 / (8 * math.log(2)))]
        self.assertEqual(programme["status"], "finite")
        for row, value in zip(programme["mice"], expected):
            self.assertTrue(math.isclose(row["bits_per_spike"], value, rel_tol=1e-15))
        self.assertTrue(math.isfinite(programme["mouse_macro_bits_per_spike"]))
        json.dumps(result, allow_nan=False)

    def test_opposed_finite_differences_have_finite_paired_quantiles(self):
        public, private = numeric_range_fixture()
        restricted = submission(public, "restricted_observation", 1.0)
        programme = submission(public, "frozen_program", 1.0)
        restricted["predictions"][0]["rate_hz"] = 9e307
        programme["predictions"][1]["rate_hz"] = 9e307
        paired = e.compare(public, private, restricted, programme, 0, 2)["paired_overall"]
        expected = (9e307 / math.log(2)) * 0.95
        self.assertEqual(paired["status"], "finite")
        self.assertEqual(paired["mouse_macro_difference_bits_per_spike"], 0.0)
        lower, upper = paired["uncertainty"]["limits"]
        self.assertTrue(math.isclose(lower, -expected, rel_tol=1e-15))
        self.assertTrue(math.isclose(upper, expected, rel_tol=1e-15))
        self.assertTrue(math.isfinite(lower) and math.isfinite(upper))

    def test_identical_predictions_and_reordered_rows_have_zero_paired_interval(self):
        public, private = fixture()
        restricted = submission(public, "restricted_observation", 2)
        program = submission(public, "frozen_program", 2)
        program["predictions"].reverse()
        result = e.compare(public, private, restricted, program, 2, 20)
        self.assertEqual(result["paired_overall"]["mouse_macro_difference_bits_per_spike"], 0)
        self.assertEqual(result["paired_overall"]["uncertainty"]["limits"], [0, 0])

    def test_both_complete_submissions_admitted_before_protected_access(self):
        public, _ = fixture()
        class Unreadable(dict):
            def __getitem__(self, key):
                raise AssertionError("protected access occurred")
        for condition_index in (0, 1):
            for mutate in (lambda s: s["predictions"].pop(),
                           lambda s: s["predictions"].append(copy.deepcopy(s["predictions"][0])),
                           lambda s: s["predictions"][0].update(rate_hz=-1),
                           lambda s: s["predictions"][0].update(rate_hz=True),
                           lambda s: s["predictions"][0].update(rate_hz=float("nan")),
                           lambda s: s.update(public_sha256="0" * 64),
                           lambda s: s.update(condition="tool_assisted"),
                           lambda s: s.update(extra="forbidden")):
                pair = [submission(public, condition, 2) for condition in e.CONDITIONS]
                mutate(pair[condition_index])
                with self.assertRaises(ValueError):
                    e.compare(public, Unreadable(), *pair)

    def test_equal_query_keys_with_different_calibration_do_not_match(self):
        public, private = fixture()
        changed = copy.deepcopy(public)
        changed["training"][0]["count"] = 7
        with self.assertRaisesRegex(ValueError, "identical public"):
            e.compare(public, private, submission(public, "restricted_observation", 2),
                      submission(changed, "frozen_program", 2))

    def test_declared_roster_omission_still_rejected(self):
        public, private = fixture()
        removed = public["query"].pop()
        private["targets"] = [r for r in private["targets"] if r["key"] != removed["key"]]
        private["public_sha256"] = e.v1.digest(public)
        with self.assertRaisesRegex(ValueError, "unaccounted"):
            comparison(public, private)

    def test_zero_rate_infinities_and_indeterminate_difference_are_explicit(self):
        public, private = fixture()
        for restricted, program, status in ((0, 2, "positive_infinity"),
                                            (2, 0, "negative_infinity"),
                                            (0, 0, "undefined")):
            result = comparison(public, private, restricted, program)
            paired = result["paired_overall"]
            self.assertEqual(paired["status"], status)
            self.assertIsNone(paired["mouse_macro_difference_bits_per_spike"])
            self.assertIsNone(paired["uncertainty"]["limits"])
            json.dumps(result, allow_nan=False)

    def test_opposite_infinities_across_mice_are_not_silently_dropped(self):
        public, private = fixture()
        restricted, program = (submission(public, c, 2) for c in e.CONDITIONS)
        restricted["predictions"][0]["rate_hz"] = 0
        program["predictions"][-1]["rate_hz"] = 0
        result = e.compare(public, private, restricted, program, 0, 20)["paired_overall"]
        self.assertEqual(result["status"], "undefined")
        self.assertEqual({row["status"] for row in result["mice"]},
                         {"negative_infinity", "positive_infinity"})
        self.assertEqual(result["mouse_count"], 2)
        self.assertIsNone(result["uncertainty"]["limits"])

    def test_original_undefined_endpoints_remain_undefined(self):
        for zero_training in (False, True):
            public, private = fixture()
            if zero_training:
                public["training"][0]["count"] = 0
                private["public_sha256"] = e.v1.digest(public)
            else:
                for row in private["targets"]:
                    if row["key"][0] == "s1":
                        row["count"] = 0
            result = comparison(public, private)["paired_overall"]
            self.assertEqual(result["status"], "undefined")
            self.assertEqual(result["mice"][0]["reason"], "original_endpoint_undefined")
            self.assertIsNone(result["uncertainty"]["limits"])
            self.assertEqual(result["mouse_count"], 2)

    def test_single_mouse_has_no_bootstrap_interval(self):
        public, private = fixture()
        for split in ("training", "query"):
            public[split] = [r for r in public[split] if r["mouse_id"] == "m1"]
        private["targets"] = [r for r in private["targets"] if r["key"][0] == "s1"]
        private["source_roster"] = private["source_roster"][:1]
        private["public_sha256"] = e.v1.digest(public)
        result = comparison(public, private)["paired_overall"]
        self.assertEqual(result["mouse_count"], 1)
        self.assertIsNone(result["uncertainty"]["limits"])

    def test_cli_admission_before_private_file_read_and_success(self):
        public, private = fixture()
        with tempfile.TemporaryDirectory(dir=os.environ.get("NEURAL091_TEST_TMPDIR")) as directory:
            root = Path(directory)
            restricted = submission(public, "restricted_observation", 1)
            for name, value in (("public", public), ("restricted", restricted),
                                ("program", submission(public, "frozen_program", 2))):
                e.v1.write_json(root / (name + ".json"), value)
            command = [sys.executable, "-I", "-B", str(Path(e.__file__))]
            for name in ("public", "private", "restricted", "program", "output"):
                command += ["--" + name, str(root / (name + ".json"))]
            restricted["predictions"].pop()
            e.v1.write_json(root / "restricted.json", restricted)
            result = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("exactly cover", result.stderr)
            self.assertNotIn("FileNotFoundError", result.stderr)
            self.assertFalse((root / "output.json").exists())
            e.v1.write_json(root / "restricted.json", submission(public, "restricted_observation", 1))
            e.v1.write_json(root / "private.json", private)
            result = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = e.v1.read_json(root / "output.json")
            self.assertEqual(output["paired_overall"]["status"], "finite")


if __name__ == "__main__":
    unittest.main()
