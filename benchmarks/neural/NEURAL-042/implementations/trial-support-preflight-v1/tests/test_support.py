import copy
import hashlib
import importlib.util
import itertools
import json
import os
from pathlib import Path
import random
import unittest

HERE = Path(__file__).resolve()
spec = importlib.util.spec_from_file_location("neural042_support", HERE.parents[1] / "support.py")
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
ROSTER = Path(os.environ.get("NEURAL042_SOURCE_ROSTER", str(
    HERE.parents[2] / "programme-source/implementation-v1/preparation/SOURCE_ASSETS.json")))
RAW = ROSTER.read_bytes()
ASSETS = support.source_roster(RAW)


def metadata():
    return {"schema": "neural042_original_trial_metadata_v1",
            "source_roster_sha256": support.ROSTER_SHA256,
            "sessions": [{"asset_id": a["asset_id"], "source_sha256": a["sha256"],
                          "subject_id": a["subject_id"],
                          "loads": [1 if i % 2 else 3 for i in range(140)],
                          "correct": [1] * 140, "probe": [0] * 140}
                         for a in ASSETS.values()]}


def exhaustive_matching(trials, comparison):
    if comparison == support.COMPARISONS[0]:
        left = [t for t in trials if t[1:3] == (3, 1)]
        right = [t for t in trials if t[1:3] == (1, 1)]
    else:
        load = 1 if comparison == support.COMPARISONS[1] else 3
        left = [t for t in trials if t[1:3] == (load, 1)]
        right = [t for t in trials if t[1:3] == (load, 0)]

    def search(i, used):
        if i == len(left):
            return 0
        best = search(i + 1, used)
        a = left[i]
        for j, b in enumerate(right):
            if j not in used and a[0] // 35 == b[0] // 35 and a[3] == b[3]:
                best = max(best, 1 + search(i + 1, used | {j}))
        return best
    return search(0, set())


class SupportTests(unittest.TestCase):
    def test_frozen_metadata_descriptor_is_saved(self):
        raw = json.dumps(metadata(), separators=(",", ":")).encode()
        expected = hashlib.sha256(raw).hexdigest()
        report = support.audit_frozen(raw, RAW, expected)
        saved = json.loads(json.dumps(report))
        self.assertEqual(saved["metadata_input"], {"bytes": len(raw), "sha256": expected})
        self.assertNotIn("path", saved["metadata_input"])
        with self.assertRaisesRegex(ValueError, "metadata identity mismatch"):
            support.audit_frozen(raw + b" ", RAW, expected)

    def test_complete_cohort_retained_and_all_correct_is_not_accuracy_support(self):
        report = support.audit(metadata(), RAW)
        self.assertEqual(len(report["sessions"]), 44)
        self.assertEqual(report["summary"]["source_people"], 36)
        self.assertEqual(report["summary"]["sessions_not_ruled_out"], {"load": 44, "correctness": 0})
        self.assertTrue(report["summary"]["primary_ruled_out_by_supplied_label_bounds"])
        self.assertIsNone(report["summary"]["actual_reference_support"])

    def test_twenty_errors_in_one_load_cannot_support_both_loads(self):
        value = metadata()
        for row in value["sessions"]:
            for i in range(1, 40, 2):
                row["correct"][i] = 0
        report = support.audit(value, RAW)
        self.assertEqual(report["summary"]["people_not_ruled_out"]["correctness"], 0)

    def test_errors_isolated_by_probe_cannot_be_matched(self):
        value = metadata()
        for row in value["sessions"]:
            for i in range(20):
                row["correct"][i] = 0
                row["probe"][i] = 1
        report = support.audit(value, RAW)
        for row in report["sessions"]:
            self.assertEqual(row["maximum_count_only_pairs"][support.COMPARISONS[1]], 0)
            self.assertEqual(row["maximum_count_only_pairs"][support.COMPARISONS[2]], 0)

    def test_exact_ten_pair_floor_is_necessary_not_sufficient(self):
        value = metadata()
        for row in value["sessions"]:
            for block in range(4):
                for j in range(5):
                    row["correct"][35 * block + j] = 0
        report = support.audit(value, RAW)
        self.assertEqual(report["summary"]["people_not_ruled_out"]["correctness"], 36)
        self.assertEqual(report["summary"]["scientific_qualification"], "not_established")
        for row in report["sessions"]:
            self.assertEqual([row["maximum_count_only_pairs"][x] for x in support.COMPARISONS[1:]], [10, 10])
        value["sessions"][0]["correct"][0] = 1
        changed = support.audit(value, RAW)
        first = next(x for x in changed["sessions"] if x["asset_id"] == value["sessions"][0]["asset_id"])
        self.assertFalse(first["endpoint_not_ruled_out"]["correctness"])

    def test_session_rows_are_not_pooled_to_create_support(self):
        value = metadata()
        for row in value["sessions"]:
            row["correct"][0:18] = [0] * 18
        report = support.audit(value, RAW)
        self.assertEqual(report["summary"]["people_not_ruled_out"]["correctness"], 0)

    def test_count_bound_matches_independent_exhaustive_matching(self):
        rng = random.Random(42001)
        for _ in range(180):
            rows = rng.sample(range(140), 7)
            trials = [(r, rng.choice((1, 3)), rng.randrange(2), rng.randrange(2)) for r in rows]
            counts, _ = support._bounds(trials)
            for comparison in support.COMPARISONS:
                self.assertEqual(counts[comparison], exhaustive_matching(trials, comparison))

    def test_artifact_vertex_removal_never_increases_any_bound(self):
        trials = [(i, 1 if i % 2 else 3, (i // 2) % 2, i // 20 % 2) for i in range(140)]
        original, _ = support._bounds(trials)
        for removed in ((0,), tuple(range(15)), tuple(range(0, 140, 2)), tuple(range(140))):
            smaller, _ = support._bounds([t for t in trials if t[0] not in removed])
            for key in original:
                self.assertLessEqual(smaller[key], original[key])

    def test_source_and_session_identity_fail_closed(self):
        for mutation in (lambda m: m["sessions"].pop(),
                         lambda m: m["sessions"].__setitem__(0, copy.deepcopy(m["sessions"][1])),
                         lambda m: m["sessions"][0].__setitem__("source_sha256", "0" * 64),
                         lambda m: m["sessions"][0].__setitem__("subject_id", "invented")):
            value = metadata(); mutation(value)
            with self.assertRaises(ValueError):
                support.audit(value, RAW)
        with self.assertRaises(ValueError):
            support.audit(metadata(), RAW + b"\n")

    def test_original_order_and_literal_integer_codes_are_required(self):
        for field, bad in (("loads", True), ("correct", 0.0), ("probe", 2)):
            value = metadata(); value["sessions"][0][field][0] = bad
            with self.assertRaises(ValueError):
                support.audit(value, RAW)
        value = metadata(); value["sessions"][0]["correct"].pop()
        with self.assertRaises(ValueError):
            support.audit(value, RAW)

    def test_duplicate_json_and_nonfinite_constants_rejected(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.assertRaises(ValueError):
                support.strict_json(raw)


if __name__ == "__main__":
    unittest.main()
