"""Generated complete-panel controls; no authentic DUNL data or model runs."""
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paired_events as p


def vector(indices):
    values = [0] * 576
    for index in indices:
        values[index] = 1
    return values


def panel(predictions=(), target=None):
    h = p.endpoint()
    target = h.SCHEDULE if target is None else target
    owner = {"profile": h.PROFILE, "channel_ids": [f"allocation_{i}" for i in range(11)],
             "trial_ids": {s: [f"{s}_{i}" for i in range(n)] for s, n in h.SPLITS.items()},
             "target_codes": {s: [[vector(target)] for _ in range(n)] for s, n in h.SPLITS.items()}}
    candidate = {"profile": h.PROFILE, "context_id": h.context_id(owner),
                 "channel_ids": owner["channel_ids"].copy(),
                 "trial_ids": copy.deepcopy(owner["trial_ids"]),
                 "codes": {s: [[[vector(predictions)] for _ in range(11)] for _ in range(n)]
                           for s, n in h.SPLITS.items()}}
    return owner, candidate


class PairedEventControls(unittest.TestCase):
    def test_complete_schedule_vs_empty_preserves_both_splits_and_coordinates(self):
        owner, candidate = panel(p.endpoint().SCHEDULE)
        _, reference = panel()
        report = p.compare(owner, candidate, reference, mode="standard")
        self.assertEqual(set(report["splits"]), {"train", "test"})
        for split, count in (("train", 330), ("test", 220)):
            row = report["splits"][split]
            self.assertEqual(row["matched_rows"], count)
            self.assertEqual(row["candidate"]["missed_event_fraction"], 0)
            self.assertEqual(row["candidate"]["false_event_fraction"], 0)
            self.assertEqual(row["reference"]["missed_event_fraction"], 1)
            self.assertEqual(row["reference"]["false_event_fraction"], 1)
            self.assertEqual(row["public_schedule"]["false_event_fraction"], 0)
            self.assertEqual(row["delta"]["missed_event_fraction"]["exact"], [-1, 1])
            self.assertEqual(row["delta"]["false_event_fraction"]["exact"], [-1, 1])
        self.assertIsNone(report["scalarized_score"])
        self.assertFalse(report["scientific_qualification"])
        self.assertFalse(report["same_task_improvement_established"])
        self.assertNotIn("overall", report)

    def test_clipping_after_mean_retains_a_false_event_tradeoff(self):
        owner, candidate = panel(target=(10,))
        _, reference = panel((10,), target=(10,))
        for split, trials in candidate["codes"].items():
            for trial in trials[:len(trials) // 2]:
                for channel in trial:
                    channel[0] = vector((9, 10, 11))
        report = p.compare(owner, candidate, reference, mode="standard")
        for row in report["splits"].values():
            self.assertEqual(row["candidate"]["mean_hit_exact"], [3, 2])
            self.assertEqual(row["reference"]["mean_hit_exact"], [1, 1])
            self.assertEqual(row["delta"]["missed_event_fraction"]["exact"], [0, 1])
            self.assertEqual(row["delta"]["false_event_fraction"]["exact"], [1, 2])

    def test_common_group_mode_changes_support_before_aggregation(self):
        owner, candidate = panel()
        _, reference = panel(p.endpoint().SCHEDULE)
        for trials in candidate["codes"].values():
            for trial in trials:
                trial[0][0] = vector(p.endpoint().SCHEDULE)
        standard = p.compare(owner, candidate, reference, mode="standard")
        grouped = p.compare(owner, candidate, reference, mode="group")
        for split in ("train", "test"):
            self.assertEqual(standard["splits"][split]["delta"]["missed_event_fraction"]["exact"], [10, 11])
            self.assertEqual(standard["splits"][split]["delta"]["false_event_fraction"]["exact"], [10, 11])
            self.assertEqual(grouped["splits"][split]["delta"]["missed_event_fraction"]["exact"], [0, 1])
            self.assertEqual(grouped["splits"][split]["delta"]["false_event_fraction"]["exact"], [0, 1])

    def test_incomplete_or_reordered_reference_does_not_yield_comparison(self):
        for mutate in (
                lambda x: x["codes"]["test"].pop(),
                lambda x: x["codes"]["train"][0].pop(),
                lambda x: x["codes"]["test"][0][0][0].pop(),
                lambda x: x["trial_ids"]["test"].reverse(),
                lambda x: x["channel_ids"].reverse()):
            owner, candidate = panel()
            reference = copy.deepcopy(candidate)
            mutate(reference)
            with self.assertRaises(p.endpoint().InputError):
                p.compare(owner, candidate, reference, mode="standard")

    def test_same_context_cannot_conceal_changed_target_content(self):
        owner, candidate = panel(p.endpoint().SCHEDULE)
        _, reference = panel()
        first = p.compare(owner, candidate, reference, mode="standard")
        owner["target_codes"]["test"][0][0][100] = 0
        second = p.compare(owner, candidate, reference, mode="standard")
        self.assertEqual(first["context_id"], second["context_id"])
        self.assertNotEqual(first["content_sha256"]["owner"], second["content_sha256"]["owner"])
        self.assertEqual(first["content_sha256"]["candidate"], second["content_sha256"]["candidate"])
        self.assertNotEqual(first["splits"]["test"]["ordered_row_counts_sha256"]["candidate"],
                            second["splits"]["test"]["ordered_row_counts_sha256"]["candidate"])

    def test_swapping_arms_negates_each_exact_coordinate(self):
        owner, candidate = panel((100, 101, 50))
        _, reference = panel((100,))
        forward = p.compare(owner, candidate, reference, mode="standard")
        backward = p.compare(owner, reference, candidate, mode="standard")
        for split in ("train", "test"):
            for coordinate in ("missed_event_fraction", "false_event_fraction", "mean_hit_before_clip"):
                a = Fraction(*forward["splits"][split]["delta"][coordinate]["exact"])
                b = Fraction(*backward["splits"][split]["delta"][coordinate]["exact"])
                self.assertEqual(a, -b)

    def test_cli_binds_captured_files_and_keeps_output_exclusive(self):
        owner, candidate = panel((100,))
        _, reference = panel()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bodies = {"owner": p.canonical(owner), "candidate": p.canonical(candidate),
                      "reference": p.canonical(reference)}
            for name, raw in bodies.items():
                (root / f"{name}.json").write_bytes(raw)
            output = root / "report.json"
            args = ["--owner", str(root / "owner.json"), "--owner-sha256", "0" * 64,
                    "--candidate", str(root / "candidate.json"),
                    "--reference", str(root / "reference.json"), "--mode", "standard",
                    "--output", str(output)]
            self.assertEqual(p.main(args), 2)
            self.assertFalse(output.exists())
            args[3] = hashlib.sha256(bodies["owner"]).hexdigest()
            self.assertEqual(p.main(args), 0)
            raw_result = output.read_bytes()
            result = json.loads(raw_result)
            self.assertEqual(result["input_file_sha256"],
                             {k: hashlib.sha256(v).hexdigest() for k, v in bodies.items()})
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertEqual(p.main(args), 2)
            self.assertEqual(output.read_bytes(), raw_result)

    def test_changed_endpoint_is_refused(self):
        p.endpoint.cache_clear()
        try:
            with mock.patch.object(p, "ENDPOINT_SHA256", "0" * 64):
                with self.assertRaises(p.Refusal):
                    p.endpoint()
        finally:
            p.endpoint.cache_clear()


if __name__ == "__main__":
    unittest.main()
