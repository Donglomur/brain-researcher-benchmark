"""Generated software controls only; no authentic spikes or model outputs."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import historical_events as h


def vector(indices):
    values = [0] * h.CODE_SAMPLES
    for index in indices:
        values[index] = 1
    return values


def panel():
    owner = {"profile": h.PROFILE, "channel_ids": [f"allocated_{i}" for i in range(11)],
             "trial_ids": {s: [f"{s}_{i}" for i in range(n)] for s, n in h.SPLITS.items()},
             "target_codes": {s: [[vector(h.SCHEDULE)] for _ in range(n)]
                              for s, n in h.SPLITS.items()}}
    submission = {"profile": h.PROFILE, "context_id": h.context_id(owner),
                  "channel_ids": list(owner["channel_ids"]),
                  "trial_ids": copy.deepcopy(owner["trial_ids"]),
                  "codes": {s: [[[vector(())] for _ in range(11)] for _ in range(n)]
                            for s, n in h.SPLITS.items()}}
    return owner, submission


class EventControls(unittest.TestCase):
    def test_multiple_predictions_are_not_one_to_one_recall(self):
        row = h.row_counts({10}, {9, 10, 11})
        self.assertEqual(row, {"target_count": 1, "prediction_count": 3,
                               "neighborhood_hit_count": 3, "outside_neighborhood_count": 0})
        self.assertEqual(h.aggregate([row])["mean_hit_before_clip"], 3)

    def test_clipping_follows_row_mean(self):
        result = h.aggregate([h.row_counts({10}, {9, 10, 11}), h.row_counts({10}, set())])
        self.assertEqual(result["mean_hit_exact"], [3, 2])
        self.assertEqual(result["missed_event_fraction"], 0)
        self.assertEqual(result["false_event_fraction"], .5)

    def test_overlapping_neighborhoods_count_prediction_once(self):
        self.assertEqual(h.row_counts({10, 12}, {11})["neighborhood_hit_count"], 1)

    def test_tolerance_is_inclusive_two_bins(self):
        self.assertEqual(h.row_counts({10}, {7, 8, 12, 13}),
                         {"target_count": 1, "prediction_count": 4,
                          "neighborhood_hit_count": 2, "outside_neighborhood_count": 2})

    def test_empty_denominators_follow_source_nan_policy(self):
        for prediction in (set(), {5}):
            result = h.aggregate([h.row_counts(set(), prediction)])
            self.assertEqual((result["missed_event_fraction"], result["false_event_fraction"]), (1, 1))

    def test_average_is_not_pooled_events(self):
        result = h.aggregate([h.row_counts({10}, {10}), h.row_counts({30}, {1, 2, 3})])
        self.assertEqual(result["false_event_fraction"], .5)  # pooled false would be .75

    def test_all_550_rows_and_both_splits_survive(self):
        owner, submission = panel()
        report = h.evaluate(owner, submission, mode="standard")
        self.assertEqual(set(report["splits"]), {"train", "test"})
        for split, count in (("train", 330), ("test", 220)):
            scores = report["splits"][split]
            self.assertEqual(scores["candidate"]["rows"], count)
            self.assertEqual(scores["candidate"]["missed_event_fraction"], 1)
            self.assertEqual(scores["candidate"]["false_event_fraction"], 1)
            self.assertEqual(scores["public_schedule"]["missed_event_fraction"], 0)
            self.assertEqual(scores["public_schedule"]["false_event_fraction"], 0)
            self.assertEqual(scores["candidate_rows"][-1]["channel_id"], "allocated_10")
        self.assertNotIn("overall", report)

    def test_standard_vs_group_caller_changes_support_before_repetition(self):
        owner, submission = panel()
        for split in h.SPLITS:
            for trial in submission["codes"][split]:
                trial[0][0][100] = 2.5
        standard = h.evaluate(owner, submission, mode="standard")["splits"]["test"]["candidate"]
        group = h.evaluate(owner, submission, mode="group")["splits"]["test"]["candidate"]
        self.assertEqual(standard["mean_hit_exact"], [1, 176])
        self.assertEqual(standard["mean_false_exact"], [10, 11])
        self.assertEqual(group["mean_hit_exact"], [1, 16])
        self.assertEqual(group["mean_false_exact"], [0, 1])

    def test_missing_channel_trial_or_kernel_is_rejected(self):
        for alteration in (lambda s: s["codes"]["train"][0].pop(),
                           lambda s: s["codes"]["test"].pop(),
                           lambda s: s["codes"]["train"][0][0].append(vector(()))):
            owner, submission = panel()
            alteration(submission)
            with self.assertRaises(h.InputError):
                h.evaluate(owner, submission, mode="standard")

    def test_ordered_identities_are_enforced(self):
        owner, submission = panel()
        submission["channel_ids"].reverse()
        with self.assertRaises(h.InputError):
            h.evaluate(owner, submission, mode="standard")
        owner, submission = panel()
        owner["trial_ids"]["test"][0] = owner["trial_ids"]["train"][0]
        with self.assertRaises(h.InputError):
            h.evaluate(owner, submission, mode="standard")

    def test_nonnegative_finite_domain_and_full_bins(self):
        for bad in (-1, True, float("inf"), float("nan"), "1"):
            code = vector(())
            code[0] = bad
            with self.assertRaises(h.InputError):
                h.positive_support(code)
        with self.assertRaises(h.InputError):
            h.positive_support([0] * 575)

    def test_public_context_excludes_targets(self):
        owner, _ = panel()
        before = h.context_id(owner)
        owner["target_codes"]["test"][0][0][100] = 0
        self.assertEqual(h.context_id(owner), before)
        owner["channel_ids"][0] = "new_identity"
        self.assertNotEqual(h.context_id(owner), before)

    def test_operator_digest_cli_and_exclusive_private_output(self):
        owner, submission = panel()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            raw = json.dumps(owner).encode()
            (tmp / "owner.json").write_bytes(raw)
            (tmp / "submission.json").write_text(json.dumps(submission))
            args = ["--owner", str(tmp / "owner.json"), "--owner-sha256", "0" * 64,
                    "--submission", str(tmp / "submission.json"), "--mode", "standard",
                    "--output", str(tmp / "score.json")]
            self.assertEqual(h.main(args), 2)
            self.assertFalse((tmp / "score.json").exists())
            args[3] = hashlib.sha256(raw).hexdigest()
            self.assertEqual(h.main(args), 0)
            self.assertEqual((tmp / "score.json").stat().st_mode & 0o777, 0o600)
            original = (tmp / "score.json").read_bytes()
            self.assertEqual(h.main(args), 2)
            self.assertEqual((tmp / "score.json").read_bytes(), original)

    def test_duplicate_json_and_symlink_inputs_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.json"
            path.write_text('{"a":1,"a":2}')
            with self.assertRaises(h.InputError):
                h.read_json(path)
            alias = Path(tmp) / "alias.json"
            alias.symlink_to(path)
            with self.assertRaises(OSError):
                h.read_json(alias)


if __name__ == "__main__":
    unittest.main()
