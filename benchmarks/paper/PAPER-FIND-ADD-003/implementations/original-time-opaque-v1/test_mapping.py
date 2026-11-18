"""Generated metadata controls only; no authentic neural data or model runs."""
import copy
from pathlib import Path
import tempfile
import unittest

from mapping import Collector, IdentityPlan, RESPONSE_SCHEMA, content_hash, load_reference

SCORE = load_reference()
SECRET = bytes(range(32))  # Reproducible generated control, NEVER a study secret.


def roster(full=False, empty=False):
    sessions = []
    for animal in SCORE.ANIMALS:
        for day in SCORE.DAYS:
            delays = ([2.5, 5.0] * 70 if full else [0.0] * 140)
            if not empty and not full:
                delays[2], delays[91] = 2.5, 5.0
            if empty:
                delays = [0.0] * 140
            sessions.append({"animal": animal, "day": day,
                             "condition_codes": [11] * 140,
                             "recorded_delay_seconds": delays})
    return {"schema": "h_original_time_roster_v1", "input_sha256": SCORE.SOURCE_SHA256,
            "sessions": sessions}


def response(plan, fid, reverse=False):
    private = plan.operator_binding(fid)
    rows = [{"query_id": row["query_id"],
             "predicted_bin": 8 - row["actual_bin"] if reverse else row["actual_bin"]}
            for row in private["queries"]]
    return {"schema": RESPONSE_SCHEMA, "fold_id": fid,
            "packet_sha256": content_hash(plan.public_fold(fid)), "predictions": list(reversed(rows))}


class MappingTests(unittest.TestCase):
    def test_full_44_by_140_support_and_all_176_panels(self):
        source = roster(full=True)
        plan = IdentityPlan(source, SECRET)
        self.assertEqual(len(plan.operator_fold_ids()), 44 * 140 * 2)
        collector = Collector(plan)
        for fid in plan.operator_fold_ids():
            collector.submit(fid, response(plan, fid, reverse=True))
        result = collector.finish()
        scored = SCORE.score_run(source, result)
        self.assertEqual(scored["finite_panel_count"], 176)
        self.assertTrue(scored["complete_prediction_support"])
        for panel in scored["panels"]:
            self.assertEqual(panel["trial_count"], 70)
            self.assertAlmostEqual(panel["pearson_r"], -1.0)
            self.assertEqual(panel["confusion_predicted_by_actual"],
                             [[float(r + c == 6) for c in range(7)] for r in range(7)])

    def test_public_keys_hide_source_fields_and_permute_actual_bins(self):
        plan = IdentityPlan(roster(), SECRET)
        observed_orders = set()
        for fid in plan.operator_fold_ids():
            public = plan.public_fold(fid)
            self.assertEqual(set(public), {"schema", "fold_id", "queries"})
            self.assertTrue(all(set(row) == {"query_id"} for row in public["queries"]))
            self.assertEqual(len(public["queries"]), 7)
            observed_orders.add(tuple(x["actual_bin"] for x in plan.operator_binding(fid)["queries"]))
        self.assertGreater(len(observed_orders), 1)
        self.assertNotEqual(observed_orders, {tuple(range(1, 8))})

    def test_fresh_secret_changes_identity_not_support(self):
        one = IdentityPlan(roster(), SECRET)
        two = IdentityPlan(roster(), bytes(reversed(SECRET)))
        self.assertEqual(len(one.operator_fold_ids()), len(two.operator_fold_ids()))
        self.assertTrue(set(one.operator_fold_ids()).isdisjoint(two.operator_fold_ids()))
        self.assertEqual(one.operator_fold_ids(), IdentityPlan(roster(), SECRET).operator_fold_ids())

    def test_masks_retain_source_trial_indices_and_exact_delay(self):
        source = roster()
        source["sessions"][0]["recorded_delay_seconds"][3] = 2.50000000001
        source["sessions"][0]["recorded_delay_seconds"][4] = 5.00000000001
        plan = IdentityPlan(source, SECRET)
        document = Collector(plan).finish()
        for panel in document["panels"]:
            self.assertEqual([row["trial_index"] for row in panel["trials"]],
                             [2] if panel["cue"] == "short" else [91])

    def test_incomplete_and_failed_folds_are_not_dropped(self):
        source = roster()
        plan = IdentityPlan(source, SECRET)
        collector = Collector(plan)
        first, second, *_ = plan.operator_fold_ids()
        collector.submit(first, response(plan, first))
        collector.fail(second, "Owned execution timed out")
        document = collector.finish()
        rows = [r for p in document["panels"] for r in p["trials"]]
        self.assertEqual(len(rows), 176)
        self.assertEqual(sum(r["status"] == "finite" for r in rows), 1)
        self.assertEqual(sum(r["status"] == "failed" for r in rows), 1)
        self.assertEqual(sum(r["status"] == "unstarted" for r in rows), 174)
        self.assertFalse(SCORE.score_run(source, document)["complete_prediction_support"])

    def test_malformed_response_consumes_first_final_attempt(self):
        mutations = [
            lambda doc: doc.update(packet_sha256="0" * 64),
            lambda doc: doc.update(extra="source timing"),
            lambda doc: doc["predictions"].pop(),
            lambda doc: doc["predictions"][0].update(predicted_bin=True),
            lambda doc: doc["predictions"][0].update(predicted_bin=8),
            lambda doc: doc["predictions"][0].update(query_id="q_" + "0" * 64),
            lambda doc: doc["predictions"].__setitem__(0, dict(doc["predictions"][1])),
        ]
        plan = IdentityPlan(roster(), SECRET)
        fid = plan.operator_fold_ids()[0]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                collector = Collector(plan)
                bad = response(plan, fid)
                mutate(bad)
                with self.assertRaises(ValueError):
                    collector.submit(fid, bad)
                with self.assertRaises(ValueError):
                    collector.submit(fid, response(plan, fid))
                self.assertEqual(sum(r["status"] == "failed" for p in collector.finish()["panels"]
                                     for r in p["trials"]), 1)

    def test_cross_fold_response_is_rejected(self):
        plan = IdentityPlan(roster(), SECRET)
        first, second, *_ = plan.operator_fold_ids()
        collector = Collector(plan)
        bad = response(plan, second)
        with self.assertRaises(ValueError):
            collector.submit(first, bad)
        with self.assertRaises(ValueError):
            collector.submit(first, response(plan, first))

    def test_finalization_and_copies_preserve_sealed_values(self):
        source = roster()
        plan = IdentityPlan(source, SECRET)
        source["sessions"].clear()
        fid = plan.operator_fold_ids()[0]
        collector = Collector(plan)
        doc = response(plan, fid)
        collector.submit(fid, doc)
        doc["predictions"].clear()
        result = collector.finish()
        expected = copy.deepcopy(result)
        result["panels"].clear()
        self.assertEqual(collector.finish(), expected)
        with self.assertRaises(ValueError):
            collector.fail(plan.operator_fold_ids()[1], "Late failure")

    def test_empty_source_cues_keep_undefined_panels(self):
        source = roster(empty=True)
        plan = IdentityPlan(source, SECRET)
        self.assertEqual(plan.operator_fold_ids(), ())
        result = SCORE.score_run(source, Collector(plan).finish())
        self.assertEqual(len(result["panels"]), 176)
        self.assertTrue(result["complete_prediction_support"])
        self.assertTrue(all(p["status"] == "source_undefined" for p in result["panels"]))

    def test_unsupported_roster_and_secret_rejected(self):
        source = roster()
        source["sessions"].pop()
        with self.assertRaises(ValueError):
            IdentityPlan(source, SECRET)
        with self.assertRaises(ValueError):
            IdentityPlan(roster(), b"short")

    def test_changed_scorer_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "score.py"
            path.write_text("raise AssertionError('must never execute')\n")
            with self.assertRaisesRegex(ValueError, "identity changed"):
                load_reference(path)


if __name__ == "__main__":
    unittest.main()
