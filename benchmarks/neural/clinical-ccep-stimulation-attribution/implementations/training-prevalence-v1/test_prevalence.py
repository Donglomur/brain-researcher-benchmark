"""Generated mathematical and isolation controls, never clinical observations."""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("ccep_prevalence", HERE / "prevalence.py")
R = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)


def fixture():
    patients = ["generated-p" + str(i) for i in range(5)]
    cases, labels = [], []
    # Patient-level fractions: (1,0,0,0), (0,1,0,0), (0,0,1,0),
    # (1/2,1/2,0,0), (0,0,0,1); unequal blocks and repetitions.
    per_patient = [[0], [1, 1], [2, 2, 2], [0, 0, 1, 1], [3] * 5]
    for i, (patient, classes) in enumerate(zip(patients, per_patient)):
        for j, target in enumerate(classes):
            name = "generated-c" + str(i) + "-" + str(j)
            cases.append({"case_id": name, "patient": patient, "session": "generated-session",
                          "site_block": "generated-site" + str(j), "VTC_contact": "generated-contact",
                          "repetitions": (i + 1) * 11, "packet_sha256": "1" * 64,
                          "coverage": "ready", "coverage_reason": ""})
            labels.append({"case_id": name, "class_index": target})
    targets = {"schema": "ccep-targets-v1", "task_id": R.P.TASK, "rows": labels}
    policy = {"schema": "ccep-operator-policy-v1", "task_id": R.P.TASK,
              "contract_sha256": R.P.CONTRACT, "release": "ds004457:1.0.2",
              "class_order": list(R.P.CLASSES), "patients": patients,
              "folds": [{"held_patient": p, "training_patients": [q for q in patients if q != p]}
                        for p in patients], "cases": cases,
              "numeric_policy": {"log_base": "natural", "loss_floor": 1e-12,
                                 "sum_tolerance": 1e-12, "tie_break": "first_class_in_frozen_order",
                                 "calibration_bins": 10},
              "provenance": {k: "2" * 64 for k in ("source_census_sha256", "anatomical_mapping_sha256",
                                                   "packet_manifest_sha256", "exposure_audit_sha256")},
              "targets_sha256": hashlib.sha256(R.encoded(targets)).hexdigest(),
              "scope_assertion": "all_five_patients_all_VTC_contacts_all_site_blocks_all_repetitions"}
    return policy, targets


class Controls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.policy, self.targets = fixture()
        self.bind()

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, value):
        path = self.root / name
        body = R.encoded(value)
        path.write_bytes(body)
        return path, hashlib.sha256(body).hexdigest()

    def bind(self):
        self.path, self.ph = self.write("policy.json", self.policy)

    def labels(self, held):
        selected = {c["case_id"] for c in self.policy["cases"] if c["patient"] != held}
        return {"schema": "ccep-training-prevalence-labels-v1", "task_id": R.P.TASK,
                "policy_sha256": self.ph, "held_patient": held, "class_order": list(R.P.CLASSES),
                "rows": [copy.deepcopy(row) for row in self.targets["rows"] if row["case_id"] in selected]}

    def fit(self, held=None, labels=None):
        held = held or self.policy["patients"][-1]
        lp, lh = self.write("training.json", self.labels(held) if labels is None else labels)
        return R.fit(self.path, self.ph, held, lp, lh)

    def folds(self):
        paths, hashes = [], []
        for i, patient in enumerate(self.policy["patients"]):
            path, digest = self.write("fold" + str(i) + ".json", self.fit(patient))
            paths.append(path); hashes.append(digest)
        return paths, hashes

    def test_equal_patient_prior_has_hand_computed_values(self):
        result = self.fit()
        self.assertEqual(result["probabilities"], [.375, .375, .25, 0])
        self.assertNotEqual(result["probabilities"], [.3, .4, .3, 0])  # Pooled 10 blocks.
        self.assertEqual([sum(row["class_counts"]) for row in result["training_patient_class_counts"]],
                         [1, 2, 3, 4])

    def test_pulses_cannot_reweight_the_prior(self):
        before = self.fit()["probabilities"]
        for case in self.policy["cases"]:
            case["repetitions"] *= 17
        self.bind()
        self.assertEqual(before, self.fit()["probabilities"])

    def test_all_held_labels_can_change_without_changing_the_fit(self):
        before = self.fit()
        for row in self.targets["rows"][-5:]:
            row["class_index"] = 0
        # Policy pin represents its original owner document; no target file is read.
        self.assertEqual(before, self.fit())

    def test_held_labels_missing_labels_and_foreign_labels_rejected(self):
        held = self.policy["patients"][-1]
        for mutation in (lambda v: v["rows"].append(copy.deepcopy(self.targets["rows"][-1])),
                         lambda v: v["rows"].pop(),
                         lambda v: v["rows"][0].update(case_id="foreign"),
                         lambda v: v["rows"].__setitem__(0, copy.deepcopy(v["rows"][1])),
                         lambda v: v["rows"][0].update(class_index=True)):
            labels = self.labels(held); mutation(labels)
            with self.assertRaises(R.P.Invalid):
                self.fit(held, labels)

    def test_wrong_fold_class_order_and_policy_rejected(self):
        held = self.policy["patients"][-1]
        for key, value in (("held_patient", self.policy["patients"][0]),
                           ("class_order", list(reversed(R.P.CLASSES))),
                           ("policy_sha256", "3" * 64)):
            labels = self.labels(held); labels[key] = value
            with self.assertRaises(R.P.Invalid):
                self.fit(held, labels)

    def test_training_row_order_does_not_change_probabilities(self):
        held = self.policy["patients"][-1]
        labels = self.labels(held)
        before = self.fit(held, labels)
        labels["rows"].reverse()
        after = self.fit(held, labels)
        self.assertEqual(before["probabilities"], after["probabilities"])
        self.assertEqual(before["training_patient_class_counts"], after["training_patient_class_counts"])

    def test_unresolved_coverage_refused_before_labels_open(self):
        self.policy["cases"][-1].update(coverage="invalid_signal", coverage_reason="generated invalid")
        self.bind()
        observed = []
        original = R.P.read_document
        def observe(path, expected=None):
            observed.append(Path(path).name)
            return original(path, expected)
        with patch.object(R.P, "read_document", side_effect=observe):
            with self.assertRaises(R.P.Invalid):
                R.fit(self.path, self.ph, self.policy["patients"][-1], "never-open.json", "1" * 64)
        self.assertEqual(observed, ["policy.json"])

    def test_pins_are_mandatory_and_exact(self):
        held = self.policy["patients"][-1]
        lp, lh = self.write("training.json", self.labels(held))
        for ph, digest in (("4" * 64, lh), (self.ph, "4" * 64), (self.ph, None)):
            with self.assertRaises(R.P.Invalid):
                R.fit(self.path, ph, held, lp, digest)

    def test_assemble_exact_primary_artifact_and_score(self):
        paths, hashes = self.folds()
        result = R.assemble(self.path, self.ph, paths, hashes)
        self.assertEqual(len(result["rows"]), 15)
        sp, _ = self.write("prediction.json", result)
        tp, _ = self.write("targets.json", self.targets)
        report = R.P.score_files(self.path, self.ph, sp, tp)
        expected = (-math.log(.125) - math.log(.125) - math.log(1e-12)
                    - math.log(.25) - math.log(1e-12)) / 5
        self.assertAlmostEqual(report["primary_patient_macro_log_loss"], expected)
        self.assertEqual(len(report["patient_folds"]), 5)
        self.assertFalse(report["scientifically_qualified"])

    def test_assembly_never_opens_labels_and_is_fold_order_invariant(self):
        paths, hashes = self.folds()
        (self.root / "training.json").unlink()
        before = R.assemble(self.path, self.ph, paths, hashes)
        self.assertEqual(before, R.assemble(self.path, self.ph, paths[::-1], hashes[::-1]))

    def test_missing_duplicate_and_tuned_fold_rejected(self):
        paths, hashes = self.folds()
        with self.assertRaises(R.P.Invalid):
            R.assemble(self.path, self.ph, paths[:-1], hashes[:-1])
        with self.assertRaises(R.P.Invalid):
            R.assemble(self.path, self.ph, paths[:4] + paths[:1], hashes[:4] + hashes[:1])
        value = json.loads(paths[0].read_bytes())
        value["probabilities"] = [.25] * 4
        paths[0], hashes[0] = self.write("tuned.json", value)
        with self.assertRaises(R.P.Invalid):
            R.assemble(self.path, self.ph, paths, hashes)

    def test_forged_counts_cannot_shrink_training_support(self):
        value = self.fit()
        value["training_patient_class_counts"][0]["class_counts"] = [0, 0, 0, 0]
        with self.assertRaises(R.P.Invalid):
            R._validate_fit(value, self.policy, self.ph, R.P.validate_policy(self.policy)[1])

    def test_cli_works_isolated_and_refuses_unknown_target_argument(self):
        held = self.policy["patients"][-1]
        path, digest = self.write("training.json", self.labels(held))
        cmd = [sys.executable, "-I", "-S", "-B", str(HERE / "prevalence.py"), "fit",
               "--policy", str(self.path), "--policy-sha256", self.ph, "--held-patient", held,
               "--training-labels", str(path), "--training-labels-sha256", digest]
        run = subprocess.run(cmd, cwd=self.root, capture_output=True, check=False, timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["probabilities"], [.375, .375, .25, 0])
        refused = subprocess.run(cmd + ["--targets", "not-allowed.json"], cwd=self.root,
                                 capture_output=True, check=False, timeout=10)
        self.assertEqual(refused.returncode, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
