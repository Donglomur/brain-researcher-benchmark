"""Invented metadata/probabilities only; no neural arrays or fitted models."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import scorer as s


def manifest():
    recs = []
    for animal in ("A", "B", "C"):
        for regime, values in (("sleep", (0, 0.5, 1, 2)), ("anesthesia", (0, 1))):
            recs.append({"recording_id": animal + "-" + regime, "animal_id": animal,
                         "regime": regime, "source_sha256": "a" * 64,
                         "n_frames": 4 * len(values), "boundaries": [],
                         "epochs": [{"start": 4*i, "stop": 4*i+4, "raw_state": value}
                                    for i, value in enumerate(values)]})
    return {"schema": "calcium-state-private-manifest-v1", "task_id": s.TASK,
            "admission": {g: {"accepted": True, "evidence_sha256": "b" * 64} for g in s.GATES},
            "case_salt_hex": "c" * 64,
            "window_frames": 2, "guard_frames": 0, "recordings": recs,
            "folds": [{"fold_id": "fold-" + test, "train_animals": [train],
                       "validation_animals": [val], "test_animals": [test]}
                      for test, train, val in (("A", "B", "C"), ("B", "C", "A"), ("C", "A", "B"))]}


def predictions(m, perfect):
    cases, _ = s.validate_manifest(m)
    rows = []
    for c in cases:
        states = s.STATES[c["regime"]]
        probs = {state: float(state == c["state"]) if perfect else 1/len(states) for state in states}
        rows.append({"case_id": c["case_id"], "probabilities": probs})
    return {"schema": "calcium-state-predictions-v1", "task_id": s.TASK, "predictions": rows}


class ScorerControls(unittest.TestCase):
    def test_independently_calculated_metrics(self):
        m = manifest()
        r = s.score(m, predictions(m, True), predictions(m, False))
        self.assertEqual(r["cases"], 36)
        self.assertEqual(r["animals"], 3)
        self.assertEqual(r["candidate"]["animal_macro_balanced_accuracy"], 1)
        self.assertEqual(r["rate_reference"]["animal_macro_balanced_accuracy"], 0.375)
        self.assertEqual(r["rate_reference"]["animal_macro_balanced_log_loss_bits"], 1.5)
        self.assertEqual(r["primary_gain"], 0.625)

    def test_semantic_state_collision(self):
        self.assertEqual(s.state_label("sleep", 1), "nrem")
        self.assertEqual(s.state_label("anesthesia", 1), "anesthesia")
        self.assertEqual(s.state_label("sleep", 0.5), "quiet_wake")
        with self.assertRaises(s.Invalid):
            s.state_label("anesthesia", 0.5)

    def test_no_windows_cross_discontinuity(self):
        m = manifest()
        m["recordings"][0]["boundaries"] = [1, 3]
        cases, coverage = s.derive_cases(m["recordings"], 2, 0, m["case_salt_hex"])
        first = [c for c in cases if c["recording_id"] == "A-sleep" and c["state"] == "awake"]
        self.assertEqual([(c["start"], c["stop"]) for c in first], [(1, 3)])
        segments = coverage[0]["segments"]
        self.assertEqual(sum(x["remainder_frames"] for x in segments), 2)

    def test_guard_frame_conservation(self):
        m = manifest()
        cases, coverage = s.derive_cases(m["recordings"], 2, 1, m["case_salt_hex"])
        self.assertEqual(len(cases), 18)
        self.assertEqual(sum(x["guarded_frames"] for r in coverage for x in r["segments"]), 36)
        self.assertTrue(all(c["start"] % 4 == 1 for c in cases))

    def test_probability_regime_collision_rejected(self):
        m = manifest(); p = predictions(m, True)
        cases, _ = s.validate_manifest(m)
        ident = next(c["case_id"] for c in cases if c["regime"] == "anesthesia")
        row = next(x for x in p["predictions"] if x["case_id"] == ident)
        row["probabilities"] = {"awake": 0.5, "nrem": 0.5}
        with self.assertRaises(s.Invalid): s.score(m, p, predictions(m, False))

    def test_no_animal_leakage(self):
        m = manifest(); m["folds"][0]["train_animals"] = ["A", "B"]
        with self.assertRaises(s.Invalid): s.validate_manifest(m)

    def test_missing_outer_fold_rejected(self):
        m = manifest(); m["folds"].pop()
        with self.assertRaises(s.Invalid): s.validate_manifest(m)

    def test_complete_train_class_support(self):
        m = manifest(); m["recordings"] = [r for r in m["recordings"] if r["recording_id"] != "C-anesthesia"]
        with self.assertRaises(s.Invalid): s.validate_manifest(m)

    def test_unadmitted_originals_rejected(self):
        m = manifest(); m["admission"]["animal_identity"]["accepted"] = False
        with self.assertRaises(s.Invalid): s.validate_manifest(m)

    def test_metadata_gaps_rejected(self):
        for field, value in (("start", 1), ("stop", 5)):
            m = manifest(); m["recordings"][0]["epochs"][0][field] = value
            with self.subTest(field=field), self.assertRaises(s.Invalid): s.validate_manifest(m)

    def test_unsorted_and_duplicate_acquisition_cuts_rejected(self):
        for cuts in ([3, 2], [2, 2], [16], [0]):
            m = manifest(); m["recordings"][0]["boundaries"] = cuts
            with self.subTest(cuts=cuts), self.assertRaises(s.Invalid): s.validate_manifest(m)

    def test_unsupported_and_boolean_raw_states_rejected(self):
        for value in (-1, 3, True, float("nan")):
            m = manifest(); m["recordings"][0]["epochs"][0]["raw_state"] = value
            with self.subTest(value=value), self.assertRaises(s.Invalid): s.validate_manifest(m)

    def test_prediction_missing_duplicate_extra(self):
        m = manifest(); original = predictions(m, True)
        alterations = [original["predictions"][:-1], original["predictions"] + original["predictions"][:1],
                       original["predictions"][:-1] + original["predictions"][:1]]
        for rows in alterations:
            p = copy.deepcopy(original); p["predictions"] = rows
            with self.assertRaises(s.Invalid): s.score(m, p, predictions(m, False))

    def test_invalid_probabilities(self):
        for value in (float("nan"), float("inf"), -0.1, 1.1, True):
            m = manifest(); p = predictions(m, True)
            p["predictions"][0]["probabilities"]["awake"] = value
            with self.subTest(value=value), self.assertRaises(s.Invalid): s.score(m, p, predictions(m, False))

    def test_not_normalized(self):
        m = manifest(); p = predictions(m, True); p["predictions"][0]["probabilities"]["awake"] = 0.9
        with self.assertRaises(s.Invalid): s.score(m, p, predictions(m, False))

    def test_case_number_does_not_reweight_animal_or_state(self):
        m = manifest(); rec = m["recordings"][0]; rec["epochs"][0]["stop"] = 104
        for e in rec["epochs"][1:]: e["start"] += 100; e["stop"] += 100
        rec["n_frames"] += 100
        r = s.score(m, predictions(m, True), predictions(m, False))
        self.assertEqual(r["cases"], 86)
        self.assertEqual(r["rate_reference"]["animal_macro_balanced_accuracy"], 0.375)
        self.assertEqual(r["rate_reference"]["animal_macro_balanced_log_loss_bits"], 1.5)

    def test_json_duplicates_nonfinite_and_digest(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "input.json"
            for text in ('{"a":1,"a":2}', '{"a":NaN}'):
                p.write_text(text)
                with self.assertRaises(s.Invalid): s.load_json(p)
            p.write_text('{"a":1}')
            with self.assertRaises(s.Invalid): s.load_json(p, "0" * 64)
            self.assertEqual(s.load_json(p, hashlib.sha256(p.read_bytes()).hexdigest()), {"a": 1})

    def test_candidate_labels_rejected(self):
        m = manifest(); p = predictions(m, True)
        p["predictions"][0]["state"] = "awake"
        with self.assertRaises(s.Invalid): s.score(m, p, predictions(m, False))

    def test_opaque_id_stability_and_secret_binding(self):
        m = manifest()
        first = s.candidate_index(m)
        self.assertEqual(first, s.candidate_index(copy.deepcopy(m)))
        for row in first:
            self.assertEqual(set(row), {"case_id", "regime", "n_frames"})
            self.assertRegex(row["case_id"], r"^[0-9a-f]{64}$")
            self.assertNotIn("A-sleep", row["case_id"])
            self.assertNotIn(".0.2", row["case_id"])
        self.assertEqual([r["case_id"] for r in first], sorted(r["case_id"] for r in first))
        m["case_salt_hex"] = "d" * 64
        changed = s.candidate_index(m)
        self.assertFalse({r["case_id"] for r in first} & {r["case_id"] for r in changed})

    def test_invalid_or_missing_private_salt_rejected(self):
        for salt in ("", "c" * 63, "G" * 64, True):
            m = manifest(); m["case_salt_hex"] = salt
            with self.subTest(salt=salt), self.assertRaises(s.Invalid): s.candidate_index(m)
        m = manifest(); del m["case_salt_hex"]
        with self.assertRaises(s.Invalid): s.candidate_index(m)


if __name__ == "__main__":
    unittest.main(verbosity=2)
