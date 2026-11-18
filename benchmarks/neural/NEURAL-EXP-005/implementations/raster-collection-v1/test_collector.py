"""Generated complete-schedule controls; no authentic EEG or model execution."""

from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import collector as c


KEY = b"invented-phase2-fixture-private-key-0123456"


def fixture():
    ids = ["eeg" + str(i) for i in range(1, 80)]
    folds = c.protocol.fold_map(ids, "phase2-fixture")
    desc = {"schema": c.protocol.DESCRIPTION_SCHEMA, "assessment_id": "phase2-invented",
        "protocol_id": c.protocol.PROTOCOL, "source_version": c.protocol.SOURCE_VERSION,
        "fold_seed": "phase2-fixture", "representation_sha256": "a" * 64,
        "detector_sha256": "b" * 64, "source_admission_sha256": "c" * 64,
        "montage": list(c.protocol.MONTAGE),
        "development_by_fold": {str(f): [next(r for r in ids if folds[r] != f)] for f in range(5)},
        "recordings": []}
    for rid in ids:
        duration = 31 if rid == "eeg1" else 30
        desc["recordings"].append({"recording_id": rid, "eeg_sha256": "d" * 64,
            "sample_rate": {"num": 1, "den": 1}, "sample_count": duration,
            "sample_zero_annotation_second": 0, "units": "uV",
            "labels": [[1] * duration, [0] * duration, [0] * duration],
            "quality_flags": [False] * duration})
    def reader(rid, start, stop):
        return [[n + col / 100 for col in range(18)] for n in range(start, stop)]
    reference = c.protocol.prepare_reference(desc, reader, KEY)
    schedule = c.freeze_reference(reference)
    selectors = [(rid, second) for rid in reference.record_ids()
                 for second in range(29, 31 if rid == "eeg1" else 30)]
    packets = [c.protocol.packet(reference, rid, second, reader) for rid, second in selectors]
    return reference, schedule, c.protocol.digest(schedule), packets


def answer(session, probability=0.25):
    binding = session.act({"action": "describe"})["binding"]
    return session.act({"action": "answer", "case_id": binding["case_id"],
                        "input_sha256": binding["input_sha256"], "probability": probability})


def completed(schedule, digest, packets):
    owner = c.Collector(schedule, expected_schedule_sha256=digest)
    for packet in packets:
        session = owner.open_case(packet)
        answer(session)
        owner.commit_current()
    return owner, owner.finish()


class CollectorControls(unittest.TestCase):
    def test_freeze_projects_exact_existing_order_without_label_or_sample_access(self):
        reference, schedule, _, _ = fixture()
        class NoGoldAccess:
            reference_sha256 = reference.reference_sha256
            def record_ids(self): return reference.record_ids()
            def case_rows(self): return reference.case_rows()
            @property
            def document(self): raise AssertionError("private labels accessed")
            def record(self, _rid): raise AssertionError("private labels accessed")
        projected = c.freeze_reference(NoGoldAccess())
        self.assertEqual(projected, schedule)
        self.assertEqual(projected["bindings"], list(reference.case_rows()))
        self.assertEqual((projected["infants"], projected["case_count"]), (79, 80))
        self.assertEqual({r["fold"] for r in projected["bindings"]}, set(range(5)))
        self.assertTrue(all(set(r) == c.BINDING_FIELDS for r in projected["bindings"]))

    def test_complete_rows_feed_unchanged_scorer_with_original_infant_estimand(self):
        reference, schedule, digest, packets = fixture()
        _, export = completed(schedule, digest, packets)
        protected = c.protocol.digest(export)
        rows = c.admit_collection(schedule, export, expected_schedule_sha256=digest,
                                  expected_collection_sha256=protected)
        self.assertEqual(export["source_reference_sha256"], reference.reference_sha256)
        evaluator_path = Path(__file__).resolve().parent.parent / "complete-support-evaluator/evaluate.py"
        spec = importlib.util.spec_from_file_location("_phase2_existing_evaluator", evaluator_path)
        evaluator = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"protocol": c.protocol}):
            spec.loader.exec_module(evaluator)
        report = evaluator.evaluate(reference, rows)
        self.assertEqual((report["n_infants"], report["n_cases"]), (79, 80))
        self.assertAlmostEqual(report["primary_soft_vote_brier"], 1 / 144, places=13)
        self.assertEqual([r["case_id"] for r in rows], [r["case_id"] for r in schedule["bindings"]])

    def test_no_partial_export_active_skip_or_unanswered_commit(self):
        _, schedule, digest, packets = fixture()
        owner = c.Collector(schedule, expected_schedule_sha256=digest)
        with self.assertRaises(c.CollectionError): owner.finish()
        with self.assertRaises(c.CollectionError): owner.commit_current()
        session = owner.open_case(packets[0])
        with self.assertRaises(c.CollectionError): owner.open_case(packets[1])
        with self.assertRaises(c.viewer.ViewError): owner.commit_current()
        with self.assertRaises(c.CollectionError): owner.finish()
        answer(session)
        owner.commit_current()
        with self.assertRaises(c.CollectionError): owner.finish()
        with self.assertRaises(c.CollectionError): owner.commit_current()

    def test_wrong_next_duplicate_and_changed_packets_are_refused(self):
        _, schedule, digest, packets = fixture()
        owner = c.Collector(schedule, expected_schedule_sha256=digest)
        with self.assertRaises(c.viewer.ViewError): owner.open_case(packets[1])
        changed = deepcopy(packets[0]); changed["samples"][0][0] += 1
        with self.assertRaises(c.viewer.ViewError): owner.open_case(changed)
        session = owner.open_case(packets[0]); answer(session); owner.commit_current()
        with self.assertRaises(c.viewer.ViewError): owner.open_case(packets[0])
        owner.open_case(packets[1])

    def test_current_receipt_exposes_no_roster_labels_future_or_scores(self):
        _, schedule, digest, packets = fixture()
        owner = c.Collector(schedule, expected_schedule_sha256=digest)
        session = owner.open_case(packets[0])
        public = session.act({"action": "describe"})
        answer(session)
        receipt = owner.commit_current()
        self.assertEqual(set(receipt), {"schema", "case_id", "input_sha256", "row_sha256"})
        self.assertEqual(receipt["case_id"], schedule["bindings"][0]["case_id"])
        self.assertNotIn(schedule["bindings"][1]["case_id"], str((public, receipt)))
        self.assertNotIn("source_reference_sha256", public)
        self.assertNotIn("rows", public)

    def test_schedule_and_answer_aliases_cannot_mutate_owned_collection(self):
        _, schedule, digest, packets = fixture()
        owner = c.Collector(schedule, expected_schedule_sha256=digest)
        schedule["bindings"][0]["case_id"] = "0" * 64
        session = owner.open_case(packets[0])
        answer(session)
        row = session.finish(); row["probability"] = 0.9
        receipt = owner.commit_current(); receipt["case_id"] = "0" * 64
        self.assertEqual(owner._rows[0]["probability"], 0.25)
        self.assertEqual(owner._rows[0]["case_id"], packets[0]["case_id"])

    def test_frozen_schedule_rejects_missing_duplicate_mixed_or_uncommitted_rows(self):
        _, schedule, digest, _ = fixture()
        for defect in ("drop", "duplicate", "mixed", "fold_bool", "extra_label"):
            changed = deepcopy(schedule)
            if defect == "drop": changed["bindings"].pop()
            elif defect == "duplicate": changed["bindings"][1] = changed["bindings"][0]
            elif defect == "mixed": changed["bindings"][0]["assessment_id"] = "other"
            elif defect == "fold_bool": changed["bindings"][0]["fold"] = True
            else: changed["bindings"][0]["labels"] = [1, 0, 0]
            with self.subTest(defect=defect), self.assertRaises(c.CollectionError):
                c.Collector(changed, expected_schedule_sha256=digest)
            # Except mere prefix omission, independently reject malformed
            # self-consistent schedules even under a different alleged pin.
            if defect != "drop":
                with self.assertRaises(c.CollectionError):
                    c.Collector(changed, expected_schedule_sha256=c.protocol.digest(changed))

    def test_complete_export_is_single_assignment_and_finalized_sessions_stay_closed(self):
        _, schedule, digest, packets = fixture()
        owner = c.Collector(schedule, expected_schedule_sha256=digest)
        old = None
        for packet in packets:
            session = owner.open_case(packet); answer(session); owner.commit_current()
            if old is None: old = session
        with self.assertRaises(c.CollectionError): owner.open_case(packets[0])
        export = owner.finish()
        with self.assertRaises(c.CollectionError): owner.finish()
        with self.assertRaises(c.CollectionError): owner.commit_current()
        with self.assertRaises(c.viewer.ViewError): old.act({"action": "describe"})
        export["rows"][0]["probability"] = 0.9
        self.assertEqual(owner._rows[0]["probability"], 0.25)

    def test_readback_rejects_tampering_even_if_untrusted_row_hash_is_recomputed(self):
        _, schedule, digest, packets = fixture()
        _, original = completed(schedule, digest, packets)
        final_digest = c.protocol.digest(original)
        for defect in ("missing", "extra", "reordered", "probability", "reference", "mode", "fold_bool"):
            altered = deepcopy(original)
            if defect == "missing": altered["rows"].pop()
            elif defect == "extra": altered["rows"].append(altered["rows"][0])
            elif defect == "reordered": altered["rows"].reverse()
            elif defect == "probability": altered["rows"][0]["probability"] = 0.99
            elif defect == "reference": altered["source_reference_sha256"] = "0" * 64
            elif defect == "mode": altered["mode"] = "direct_numeric"
            else: altered["rows"][0]["fold"] = True
            altered["rows_sha256"] = c.protocol.digest(altered["rows"])
            with self.subTest(defect=defect), self.assertRaises(c.CollectionError):
                c.admit_collection(schedule, altered, expected_schedule_sha256=digest,
                                   expected_collection_sha256=final_digest)
            if defect != "probability":
                with self.assertRaises(c.CollectionError):
                    c.admit_collection(schedule, altered, expected_schedule_sha256=digest,
                                       expected_collection_sha256=c.protocol.digest(altered))

    def test_invalid_probabilities_or_extra_labels_never_enter_complete_rows(self):
        _, schedule, digest, packets = fixture()
        _, original = completed(schedule, digest, packets)
        for value in (True, -0.1, 1.1):
            bad = deepcopy(original); bad["rows"][0]["probability"] = value
            bad["rows_sha256"] = c.protocol.digest(bad["rows"])
            with self.assertRaises(c.CollectionError):
                c.admit_collection(schedule, bad, expected_schedule_sha256=digest,
                                   expected_collection_sha256=c.protocol.digest(bad))
        bad = deepcopy(original); bad["rows"][0]["labels"] = [1, 0, 0]
        bad["rows_sha256"] = c.protocol.digest(bad["rows"])
        with self.assertRaises(c.CollectionError):
            c.admit_collection(schedule, bad, expected_schedule_sha256=digest,
                               expected_collection_sha256=c.protocol.digest(bad))


if __name__ == "__main__":
    unittest.main(verbosity=2)
