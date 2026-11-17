"""Invented interface/mathematical controls only; no physiological observations."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import score


def encoded(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()


def fixture():
    # Deliberately unequal blocks/repetitions, invented opaque identities and targets.
    patients = ["invented-person-" + str(i) for i in range(5)]
    cases, targets, rows = [], [], []
    for i, patient in enumerate(patients):
        for b in range(i + 1):
            name = "invented-case-" + str(i) + "-" + str(b)
            cases.append({"case_id": name, "patient": patient, "session": "invented-session",
                          "site_block": "invented-site-" + str(b), "VTC_contact": "invented-contact",
                          "repetitions": 3 + i * 9, "packet_sha256": "1" * 64,
                          "coverage": "ready", "coverage_reason": ""})
            targets.append({"case_id": name, "class_index": 0})
            prob = .1 * (i + 1)
            rows.append({"case_id": name, "probabilities": [prob] + [(1 - prob) / 3] * 3})
    t = {"schema": "ccep-targets-v1", "task_id": score.TASK, "rows": targets}
    p = {"schema": "ccep-operator-policy-v1", "task_id": score.TASK,
         "contract_sha256": score.CONTRACT, "release": "ds004457:1.0.2",
         "class_order": list(score.CLASSES), "patients": patients,
         "folds": [{"held_patient": x, "training_patients": [y for y in patients if x != y]}
                   for x in patients], "cases": cases,
         "numeric_policy": {"log_base": "natural", "loss_floor": 1e-12,
                            "sum_tolerance": 1e-12, "tie_break": "first_class_in_frozen_order",
                            "calibration_bins": 10},
         "provenance": {k: "2" * 64 for k in ("source_census_sha256", "anatomical_mapping_sha256",
                                              "packet_manifest_sha256", "exposure_audit_sha256")},
         "targets_sha256": hashlib.sha256(encoded(t)).hexdigest(),
         "scope_assertion": "all_five_patients_all_VTC_contacts_all_site_blocks_all_repetitions"}
    s = {"schema": "ccep-predictions-v1", "task_id": score.TASK, "policy_sha256": "",
         "class_order": list(score.CLASSES), "condition": "original_full_scope", "rows": rows}
    return p, s, t


class Controls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.p, self.s, self.t = fixture()

    def tearDown(self):
        self.temp.cleanup()

    def write(self):
        self.p["targets_sha256"] = hashlib.sha256(encoded(self.t)).hexdigest()
        phash = hashlib.sha256(encoded(self.p)).hexdigest()
        self.s["policy_sha256"] = phash
        for name, value in (("policy", self.p), ("submission", self.s), ("targets", self.t)):
            (self.root / (name + ".json")).write_bytes(encoded(value))
        return phash

    def run_score(self):
        phash = self.write()
        return score.score_files(self.root / "policy.json", phash,
                                 self.root / "submission.json", self.root / "targets.json")

    def test_equal_person_not_blocks_or_pulses(self):
        r = self.run_score()
        expected = sum(-math.log(.1 * (i + 1)) for i in range(5)) / 5
        pooled = sum((i + 1) * -math.log(.1 * (i + 1)) for i in range(5)) / 15
        self.assertAlmostEqual(r["primary_patient_macro_log_loss"], expected)
        self.assertGreater(abs(expected - pooled), .1)
        self.assertEqual([x["blocks"] for x in r["patient_folds"]], [1, 2, 3, 4, 5])
        self.assertFalse(r["scientifically_qualified"])

    def test_uniform_prediction_known_loss(self):
        for row in self.s["rows"]:
            row["probabilities"] = [.25] * 4
        r = self.run_score()
        self.assertAlmostEqual(r["primary_patient_macro_log_loss"], math.log(4))
        self.assertEqual(r["patient_folds"][0]["confusion_true_by_predicted"][0][0], 1)

    def test_zero_probability_floor_is_operator_bound(self):
        for row in self.s["rows"]:
            row["probabilities"] = [0, 1, 0, 0]
        self.p["numeric_policy"]["loss_floor"] = 1e-7
        r = self.run_score()
        self.assertAlmostEqual(r["primary_patient_macro_log_loss"], -math.log(1e-7))
        self.assertEqual(r["patient_folds"][0]["recall_by_class"], [0, None, None, None])

    def test_missing_training_class_is_reported_not_discarded(self):
        self.t["rows"][0]["class_index"] = 3
        r = self.run_score()
        self.assertIn("other_mixed", r["patient_folds"][0]["unsupported_training_classes"])
        self.assertNotIn("other_mixed", r["patient_folds"][1]["unsupported_training_classes"])
        self.assertEqual(len(r["patient_folds"]), 5)
        self.assertIsNone(r["patient_folds"][0]["macro_recall_all_four_classes"])

    def test_all_class_recall_confusion_and_calibration(self):
        # Existing invented five-block patient: targets 0,1,2,3,0 with perfect predictions.
        for row in self.t["rows"][-5:]:
            row["class_index"] = self.t["rows"][-5:].index(row) % 4
        for target, prediction in zip(self.t["rows"], self.s["rows"]):
            prediction["probabilities"] = [int(k == target["class_index"]) for k in range(4)]
        r = self.run_score()
        self.assertEqual(r["primary_patient_macro_log_loss"], 0)
        f = r["patient_folds"][-1]
        self.assertEqual(f["recall_by_class"], [1, 1, 1, 1])
        self.assertEqual(f["macro_recall_all_four_classes"], 1)
        for k, support in enumerate(f["held_class_support"]):
            bins = f["calibration_by_class_and_fixed_bin"][k]
            self.assertEqual(sum(b["count"] for b in bins), 5)
            self.assertEqual(bins[-1]["count"], support)
            self.assertEqual(bins[-1]["observed_fraction"], 1)

    def test_shuffled_rows_do_not_change_metric(self):
        a = self.run_score()
        self.s["rows"].reverse(); self.t["rows"].reverse(); self.p["cases"].reverse()
        b = self.run_score()
        self.assertEqual(a["primary_patient_macro_log_loss"], b["primary_patient_macro_log_loss"])
        self.assertEqual(a["patient_folds"], b["patient_folds"])

    def test_complete_artifact_admission_precedes_any_target_open(self):
        changes = [lambda s: s["rows"].pop(),
                   lambda s: s["rows"].append(copy.deepcopy(s["rows"][0])),
                   lambda s: s["rows"][-1].update(case_id=s["rows"][0]["case_id"]),
                   lambda s: s["rows"][-1].update(case_id="invented-unknown"),
                   lambda s: s["rows"][-1].update(probabilities=[.5] * 4),
                   lambda s: s.update(class_order=list(reversed(score.CLASSES))),
                   lambda s: s.update(condition="paired_null"),
                   lambda s: s["rows"][-1].update(target=0)]
        for change in changes:
            with self.subTest(change=change):
                self.p, self.s, self.t = fixture(); change(self.s); phash = self.write()
                calls = []
                original = score.read_document
                def observe(path, expected=None):
                    calls.append(Path(path).name)
                    return original(path, expected)
                with patch.object(score, "read_document", side_effect=observe):
                    with self.assertRaises(score.Invalid):
                        score.score_files(self.root / "policy.json", phash,
                                          self.root / "submission.json", self.root / "targets.json")
                self.assertNotIn("targets.json", calls)

    def test_unresolved_census_not_available_case_score(self):
        self.p["cases"][-1].update(coverage="unsupported_anatomy", coverage_reason="invented ambiguity")
        phash = self.write(); (self.root / "targets.json").unlink()
        r = score.score_files(self.root / "policy.json", phash,
                              self.root / "submission.json", self.root / "targets.json")
        self.assertEqual(r["status"], "construction_unestablished")
        self.assertIsNone(r["primary_patient_macro_log_loss"])
        self.assertFalse(r["targets_opened"])
        self.assertEqual(r["blocks"], 15)

    def test_untrusted_policy_changes_and_target_pin_rejected(self):
        phash = self.write()
        self.p["numeric_policy"]["loss_floor"] = .01
        (self.root / "policy.json").write_bytes(encoded(self.p))
        with self.assertRaises(score.Invalid):
            score.score_files(self.root / "policy.json", phash,
                              self.root / "submission.json", self.root / "targets.json")
        phash = self.write()
        (self.root / "targets.json").write_bytes(b"{}")
        with self.assertRaises(score.Invalid):
            score.score_files(self.root / "policy.json", phash,
                              self.root / "submission.json", self.root / "targets.json")

    def test_policy_shrink_leak_and_duplicate_barriers(self):
        changes = [lambda p: p["patients"].pop(), lambda p: p["class_order"].pop(),
                   lambda p: p["folds"][0]["training_patients"].append(p["patients"][0]),
                   lambda p: p["folds"].__setitem__(4, copy.deepcopy(p["folds"][0])),
                   lambda p: p["cases"].__setitem__(14, copy.deepcopy(p["cases"][0])),
                   lambda p: p["cases"][0].update(repetitions=True),
                   lambda p: p["cases"][0].update(patient="unknown"),
                   lambda p: p["numeric_policy"].update(loss_floor=0),
                   lambda p: p["numeric_policy"].update(sum_tolerance=.1),
                   lambda p: p["provenance"].update(anatomical_mapping_sha256="unverified")]
        for change in changes:
            with self.subTest(change=change):
                self.p, self.s, self.t = fixture(); change(self.p)
                with self.assertRaises(score.Invalid): self.run_score()

    def test_invalid_probability_types_and_bounds(self):
        for bad in [True, "0.2", -1e-30, 1.00000000001, {}, 10**1000]:
            with self.subTest(bad=type(bad).__name__):
                self.p, self.s, self.t = fixture(); self.s["rows"][-1]["probabilities"][0] = bad
                with self.assertRaises(score.Invalid): self.run_score()

    def test_json_duplicate_nonfinite_and_symlink_barriers(self):
        path = self.root / "bad.json"
        for data in [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'\xff']:
            path.write_bytes(data)
            with self.assertRaises(score.Invalid): score.read_document(path)
        link = self.root / "link.json"; link.symlink_to(path)
        with self.assertRaises(score.Invalid): score.read_document(link)

    def test_target_domain_and_ids(self):
        for bad in [True, -1, 4, 1.5, "1"]:
            self.p, self.s, self.t = fixture(); self.t["rows"][-1]["class_index"] = bad
            with self.assertRaises(score.Invalid): self.run_score()
        self.p, self.s, self.t = fixture(); self.t["rows"][-1]["case_id"] = self.t["rows"][0]["case_id"]
        with self.assertRaises(score.Invalid): self.run_score()

    def test_api_requires_external_policy_hash_before_any_read(self):
        for bad in [None, "", True, "not-a-hash"]:
            with patch.object(score, "read_document", side_effect=AssertionError("unexpected read")):
                with self.assertRaises(score.Invalid):
                    score.score_files("unused", bad, "unused", "unused")

    def test_fifo_is_rejected_without_blocking(self):
        fifo = self.root / "fifo.json"
        os.mkfifo(fifo)
        with patch.object(score.os, "open", side_effect=AssertionError("FIFO must fail pre-open")):
            with self.assertRaises(score.Invalid): score.read_document(fifo)
        phash = self.write()
        argv = [sys.executable, "-I", "-B", str(Path(score.__file__).resolve()),
                "--policy", str(self.root / "policy.json"), "--expected-policy-sha256", phash,
                "--submission", str(fifo), "--targets", str(self.root / "targets.json")]
        result = subprocess.run(argv, capture_output=True, text=True, timeout=3, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "invalid_or_incomplete")

    def test_cli_real_api_parity_and_generic_refusal(self):
        phash = self.write()
        argv = [sys.executable, "-I", "-B", str(Path(score.__file__).resolve()),
                "--policy", str(self.root / "policy.json"), "--expected-policy-sha256", phash,
                "--submission", str(self.root / "submission.json"), "--targets", str(self.root / "targets.json")]
        result = subprocess.run(argv, capture_output=True, text=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), self.run_score())
        self.s["rows"].pop(); (self.root / "submission.json").write_bytes(encoded(self.s))
        result = subprocess.run(argv, capture_output=True, text=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "invalid_or_incomplete")
        self.assertNotIn(str(self.root), result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
