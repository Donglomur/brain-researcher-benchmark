"""Generated-only operator controls; never use authentic packet/label bodies."""
import copy
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

import numpy as np

COMPONENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COMPONENT))
import pair


class PairControls(unittest.TestCase):
    """One shared generated fixture; originals are restored after each mutation."""
    written = 0

    @classmethod
    def put(cls, path, body):
        path.write_bytes(body)
        cls.written += len(body)
        return pair.pin(body)

    @classmethod
    def npz(cls, **values):
        buffer = io.BytesIO()
        np.savez(buffer, **values)
        return buffer.getvalue()

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="n077-pair-generated-")
        cls.root = Path(cls.temp.name).resolve()
        cls.transport, cls.comparator, cls.bodies, cls.bindings = pair.sources()
        cls.ids = {case: [case + "-" + format(i, "024x") for i in range(200)] for case in pair.CASES}
        allids = sum(cls.ids.values(), [])
        cls.comparator.ROSTER_SHA256 = hashlib.sha256(
            (json.dumps(allids, separators=(",", ":")) + "\n").encode()).hexdigest()
        cls.original = cls.npz(trial_ids=np.array(allids, dtype="<U48"),
                               target_probability=np.full(400, 0.5, dtype=np.float64))
        cls.a, cls.b = cls.root / "a.npz", cls.root / "b.npz"
        cls.prediction_pin = cls.put(cls.a, cls.original)
        cls.put(cls.b, cls.original)
        cls.receipt_pin = pair.pin(b"generated-receipt\n")
        cls.assets = pair.decode(cls.bodies["registered-runtime/assets.json"])
        cls.targets = {}
        for case in pair.CASES:
            path = cls.root / (case + ".npz")
            body = cls.npz(trial_ids=np.array(cls.ids[case]), labels=np.array([1] * 40 + [0] * 160, dtype=np.int8),
                           case_id=np.array(case))
            cls.assets["private"]["targets"][case] = cls.put(path, body)
            cls.targets[case] = str(path)
        rows = [{"person_id": case, "n": 200, "n_target": 40, "n_non_target": 160,
                 "balanced_accuracy": 0.5, "log_loss": math.log(2)} for case in pair.CASES]
        scores = {"arms": {arm: {"per_person": rows, "participant_macro_balanced_accuracy": 0.5,
                                "participant_macro_log_loss": math.log(2)} for arm in
                           ("prior", "eeg", "eog_site", "gross_amplitude", "behavioral_history", "eeg_history")}}
        cls.reference = {"status": "erp_reference_scored_and_audited", "all_public_validated_before_targets": True,
                         "target_loader_invocations": 2, "independent_arithmetic":
                         {"status": "passed", "checks": 391, "comparison_defined": True}, "scores": scores}
        cls.commit = {"status": "predictions_frozen_before_private_grade", "producer_removed_and_absent": True,
                      "source_freeze_sha256": cls.assets["reference_freeze"],
                      "files": {case + ".npz": {"sha256": cls.assets["verification_references"][case]["sha256"]}
                                for case in pair.CASES}}
        cls.commit["files"]["diagnostics.json"] = {"sha256": "0" * 64}
        cls.gradepath, cls.commitpath = cls.root / "grade.json", cls.root / "commit.json"
        cls.assets["private"]["reference_grade"] = cls.put(cls.gradepath, pair.encode(cls.reference))
        cls.assets["private"]["reference_commit"] = cls.put(cls.commitpath, pair.encode(cls.commit))
        cls.locations = cls.root / "locations.json"
        cls.put(cls.locations, pair.encode({"schema": "neural077_pair_private_locations_v1", "targets": cls.targets,
                                           "reference_grade": str(cls.gradepath), "reference_commit": str(cls.commitpath)}))

    @classmethod
    def tearDownClass(cls):
        print("GENERATED_PAIR_FIXTURE_BYTES_CREATED=" + str(cls.written))
        cls.temp.cleanup()

    def setUp(self):
        self.accounting = {"both_public_validated_before_private": False, "private_reference_attempts": 0,
                           "target_loader_attempts": 0, "temporary_submission_bytes_created": 0}

    def evaluate(self, assets=None, a=None, b=None):
        bodies = dict(self.bodies)
        bodies["registered-runtime/assets.json"] = pair.encode(assets or self.assets)
        arms = ((self.a, self.prediction_pin, self.receipt_pin), (self.b, self.prediction_pin, self.receipt_pin))
        if a is not None:
            arms = (a, arms[1])
        if b is not None:
            arms = (arms[0], b)
        try:
            return pair.protected_compare(self.comparator, bodies, arms, self.ids, self.locations, self.accounting)
        finally:
            type(self).written += self.accounting["temporary_submission_bytes_created"]

    def test_complete_400_fixed_controls_reuse_canonical_metrics(self):
        report = self.evaluate()
        self.assertEqual(report["trial_count"], 400)
        self.assertEqual(report["a_minus_b"]["participant_macro_balanced_accuracy"], 0)
        self.assertEqual(report["a_minus_b"]["participant_macro_log_loss"], 0)
        self.assertEqual(report["a"]["canonical_score"]["candidate"]["participant_macro_balanced_accuracy"], .5)
        self.assertEqual(self.accounting["private_reference_attempts"], 2)
        self.assertEqual(self.accounting["target_loader_attempts"], 2)
        self.assertTrue(self.accounting["both_public_validated_before_private"])
        self.assertEqual(len(report["a"]["canonical_score"]["candidate_minus_reference"]), 6)

    def test_invalid_second_submission_never_opens_private_locations(self):
        invalid = self.root / "invalid.npz"
        expected = self.put(invalid, self.npz(trial_ids=np.array(sum(self.ids.values(), [])),
                                             target_probability=np.zeros(399, dtype=np.float64)))
        actual_read = pair.read
        def guard(path, *args, **kwargs):
            self.assertNotEqual(Path(path), self.locations, "Private path file opened before public admission")
            return actual_read(path, *args, **kwargs)
        with mock.patch.object(pair, "read", side_effect=guard), self.assertRaises(ValueError):
            self.evaluate(b=(invalid, expected, self.receipt_pin))
        self.assertFalse(self.accounting["both_public_validated_before_private"])
        self.assertEqual(self.accounting["private_reference_attempts"], 0)
        self.assertEqual(self.accounting["target_loader_attempts"], 0)

    def test_reference_lineage_refusal_precedes_target_attempts(self):
        assets = copy.deepcopy(self.assets)
        changed = copy.deepcopy(self.commit)
        changed["producer_removed_and_absent"] = False
        path = self.root / "badcommit.json"
        assets["private"]["reference_commit"] = self.put(path, pair.encode(changed))
        actual_read = pair.read
        def replace(pathname, *args, **kwargs):
            return actual_read(path if Path(pathname) == self.commitpath else pathname, *args, **kwargs)
        with mock.patch.object(pair, "read", side_effect=replace), self.assertRaisesRegex(ValueError, "Stopped fixed reference"):
            self.evaluate(assets=assets)
        self.assertEqual(self.accounting["private_reference_attempts"], 2)
        self.assertEqual(self.accounting["target_loader_attempts"], 0)

    def test_target_pin_failure_records_attempt_before_authentication(self):
        assets = copy.deepcopy(self.assets)
        assets["private"]["targets"][pair.CASES[0]]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Input identity changed"):
            self.evaluate(assets=assets)
        self.assertEqual(self.accounting["target_loader_attempts"], 1)

    def test_float_labels_are_not_coerced(self):
        assets = copy.deepcopy(self.assets)
        case = pair.CASES[0]
        path = self.root / "floatlabels.npz"
        assets["private"]["targets"][case] = self.put(path, self.npz(
            trial_ids=np.array(self.ids[case]), labels=np.array([1.] * 40 + [0.] * 160), case_id=np.array(case)))
        actual_read = pair.read
        def replace(pathname, *args, **kwargs):
            return actual_read(path if str(pathname) == self.targets[case] else pathname, *args, **kwargs)
        with mock.patch.object(pair, "read", side_effect=replace), self.assertRaisesRegex(ValueError, "binary private label"):
            self.evaluate(assets=assets)
        self.assertEqual(self.accounting["target_loader_attempts"], 1)

    def test_current_complete_source_pins_and_reject_drift(self):
        self.assertEqual(len(self.bindings), 11)
        actual_read = pair.read
        def changed(path, cap=1048576, expected=None):
            if str(path).endswith("registered-runtime/metrics.py"):
                raise ValueError("Input identity changed")
            return actual_read(path, cap, expected)
        with mock.patch.object(pair, "read", side_effect=changed), self.assertRaises(ValueError):
            pair.sources()

    def test_condition_and_closure_reject_richer_feature_arm(self):
        collection = {"schema": "neural077_waveform_transport_collection_v1", "condition": pair.CONDITIONS[1],
                      "status": "complete_unscored_transport_collection", "queries": 400,
                      "configuration": {"sandbox": "macos"}, "local_transcript_replayed": True,
                      "private_target_reads": 0, "scoring_performed": False}
        pair._closed(collection, pair.CONDITIONS[1])
        for key, value in (("condition", "ordinary_feature_programme"), ("queries", 399),
                           ("local_transcript_replayed", False)):
            changed = copy.deepcopy(collection)
            changed[key] = value
            with self.assertRaises(ValueError):
                pair._closed(changed, pair.CONDITIONS[1])


class OrchestrationControls(unittest.TestCase):
    """Generated transport double tests wiring; it cannot qualify the sandbox."""
    def test_run_admit_tamper_and_failed_collection(self):
        with tempfile.TemporaryDirectory(prefix="n077-pair-wire-") as raw:
            root = Path(raw).resolve()
            source = root / "participant"
            source.mkdir()
            (source / "main.py").write_bytes(b"def main():\n    return 0\n")
            (source / "config.json").write_bytes(b"{}\n")
            declaration = {"schema": "neural077_python_bundle_v1", "entry_module": "main",
                           "modules": ["main.py"], "config": "config.json"}
            frozen = pair.bundle.capture(source, declaration)
            frozen_file = root / "frozen.json"
            frozen_file.write_bytes(pair.encode(frozen))
            calls = []
            transport, comparator, bodies, bindings = pair.sources()
            submission_body = b"generated delegation fixture; canonical NPZ controls are separate\n"
            def campaign(delivery, condition, output, client, python, sandbox, limits):
                self.assertEqual(sandbox, "macos")
                self.assertEqual(condition, pair.CONDITIONS[1])
                self.assertEqual(Path(client).read_bytes(), pair.bundle.verify(frozen))
                output.mkdir()
                calls.append("campaign_closed")
                return {"successful": 400, "failed_or_not_started": 0}
            def collect(delivery, condition, campaign_dir, output):
                self.assertEqual(calls[-1], "campaign_closed")
                output.mkdir()
                (output / "submission.npz").write_bytes(submission_body)
                collection = {"schema": "neural077_waveform_transport_collection_v1", "condition": condition,
                              "status": "complete_unscored_transport_collection", "queries": 400,
                              "configuration": {"sandbox": "macos", "client": pair.pin(pair.bundle.verify(frozen))},
                              "local_transcript_replayed": True, "private_target_reads": 0,
                              "scoring_performed": False, "submission": pair.pin(submission_body)}
                (output / "TRANSPORT_COMPLETE.json").write_bytes(pair.encode(collection))
                calls.append("collection_closed")
                return collection
            double = types.SimpleNamespace(run_campaign=campaign, collect=collect)
            with mock.patch.object(pair, "sources", return_value=(double, comparator, bodies, bindings)):
                receipt = pair.run_arm(root / "unused-public", pair.CONDITIONS[1], frozen_file,
                                       root / "arm", sys.executable, transport.Limits())
                self.assertEqual(calls, ["campaign_closed", "collection_closed"])
                descriptor = pair._arm_descriptor(root / "arm")
                admitted = pair._admit_arm(descriptor, pair.CONDITIONS[1], bindings, pair.operator_identity())
                self.assertEqual(admitted[1], pair.pin(submission_body))
                with self.assertRaisesRegex(ValueError, "Closed operator-authenticated"):
                    pair._admit_arm(descriptor, pair.CONDITIONS[0], bindings, pair.operator_identity())
                client = root / "arm/CLIENT.py"
                client.chmod(0o600)
                original = client.read_bytes()
                client.write_bytes(b"# changed\n" + original)
                with self.assertRaisesRegex(ValueError, "Input identity changed"):
                    pair._admit_arm(descriptor, pair.CONDITIONS[1], bindings, pair.operator_identity())
                with mock.patch.object(double, "collect", side_effect=ValueError("generated incomplete collection")):
                    with self.assertRaisesRegex(ValueError, "generated incomplete"):
                        pair.run_arm(root / "unused-public", pair.CONDITIONS[1], frozen_file,
                                     root / "failed", sys.executable, transport.Limits())
                self.assertFalse((root / "failed/ARM.json").exists())
                self.assertEqual(pair.decode((root / "failed/FAILED.json").read_bytes())["status"], "failed_unscoreable")
            # Include the replaced launcher in cumulative writes, not just retained bytes.
            written = sum(p.stat().st_size for p in root.rglob("*") if p.is_file()) + len(original)
            print("GENERATED_ORCHESTRATION_BYTES_CREATED=" + str(written))

    def test_control_driver_closes_programme_before_dispatch_and_stops_on_failure(self):
        import control_validation
        with tempfile.TemporaryDirectory(prefix="n077-control-wire-") as raw:
            root = Path(raw).resolve()
            source = root / "source"
            source.mkdir()
            (source / "main.py").write_bytes(pair.sources()[2]["waveform-transport-v1/scripted_client.py"])
            (source / "config.json").write_bytes(b"{}\n")
            frozen = pair.bundle.capture(source, {"schema": "neural077_python_bundle_v1", "entry_module": "main",
                                                  "modules": ["main.py"], "config": "config.json"})
            body = pair.encode(frozen)
            frozen_file = root / "frozen.json"
            frozen_file.write_bytes(body)
            calls = []
            def run(*args):
                calls.append("all_programme_outputs_closed")
                return {"status": "closed_unscored_arm"}
            def dispatch(*args):
                self.assertEqual(calls, ["all_programme_outputs_closed"])
                calls.append("grade_dispatched")
                grade = Path(args[5]) / "grade"
                grade.mkdir(parents=True)
                report = {"trial_count": 400, "private_loader_invocations": 2,
                          "a": {"canonical_score": {"candidate": {"participant_macro_balanced_accuracy": .5}}},
                          "b": {"canonical_score": {"candidate": {"participant_macro_balanced_accuracy": .5}}},
                          "a_minus_b": {"participant_macro_balanced_accuracy": 0, "participant_macro_log_loss": 0},
                          "accounting": {"temporary_submission_bytes_created": 322160}}
                (grade / "RESULT.json").write_bytes(pair.encode(report))
                return {"status": "paired_evaluation_closed"}
            with mock.patch.object(control_validation.platform, "system", return_value="Darwin"), \
                 mock.patch.object(pair, "run_arm", side_effect=run), \
                 mock.patch.object(pair, "dispatch_grade", side_effect=dispatch) as grade:
                result = control_validation.validate(root / "public-unused", frozen_file, pair.pin(body)["sha256"],
                                                     sys.executable, root / "legacy-unused", root / "private-unused",
                                                     root / "success")
                self.assertEqual(result["new_programme_queries"], 400)
                self.assertFalse(result["old_no_tools_proof_replayed"])
                with mock.patch.object(pair, "run_arm", side_effect=ValueError("incomplete programme")):
                    with self.assertRaisesRegex(ValueError, "incomplete programme"):
                        control_validation.validate(root / "public-unused", frozen_file, pair.pin(body)["sha256"],
                                                    sys.executable, root / "legacy-unused", root / "private-unused",
                                                    root / "failure")
                self.assertEqual(grade.call_count, 1)
                self.assertTrue((root / "failure/FAILED.json").exists())
            print("GENERATED_DRIVER_BYTES_CREATED=" + str(sum(p.stat().st_size for p in root.rglob("*") if p.is_file())))


if __name__ == "__main__":
    unittest.main()
