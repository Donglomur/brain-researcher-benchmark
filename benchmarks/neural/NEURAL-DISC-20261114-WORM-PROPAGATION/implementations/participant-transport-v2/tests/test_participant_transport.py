"""Generated transport attacks and scorer roundtrip; no biological data."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("transport", ROOT / "participant_transport.py")
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
KEY = b"generated-test-key-never-use-in-authentic-export"


def dataset():
    cases = []
    for role, worm in (("train", "animal-private-train"), ("development", "animal-private-dev"),
                       ("held", "animal-private-held-a"), ("held", "animal-private-held-b")):
        for receiver in ("R1", "R2"):
            cases.append({"case_id": worm + ":private-trial:" + receiver, "worm_id": worm,
                          "acquisition_id": worm + ":private-acquisition", "trial_id": "private-trial",
                          "source_id": "S", "receiver_id": receiver, "condition": "WT", "role": role,
                          "quality_flags": ["private-qc-generated"],
                          "stimulus_parameters": {"duration_s": .5, "power_mw": 1.2},
                          "stimulus_onset_acquisition_s": 100.125,
                          "provenance": {"asset_id": "private-source-asset", "asset_sha256": "0" * 64,
                                         "source_index": 0, "receiver_index": 1 if receiver == "R1" else 2,
                                         "stimulus_index": 0},
                          "source": {"times_s": [-10., -2., -1., 0., .3, 1.7, 30.],
                                     "values": [0., None, 1., 2., 3., 2., 0.]},
                          "receiver_pre": {"times_s": [-10., -.6], "values": [None, 1.]},
                          "target": {"times_s": [0., .3, 1.7, 30.], "values": [2., 4., 6., 8.]}})
    return {"task_id": "NEURAL-DISC-20261114-WORM-PROPAGATION", "schema_version": 1,
            "release_id": "DANDI:001075/0.240930.1859", "inventory_sha256": "a" * 64,
            "identity_audit_sha256": "b" * 64, "mask_policy_sha256": "c" * 64,
            "identity_authenticated": True, "mask_policy": "acquisition_missingness_only",
            "units": "generated-fluorescence", "horizon_s": 30, "max_interpolation_gap_s": 2.,
            "expected_case_ids": [c["case_id"] for c in cases], "cases": cases}


def answer(bundle, mode="direct_observation"):
    out = t.response_template(bundle, mode)
    for row in out["cases"]:
        row["values"] = [1.] * len(row["times_s"])
    return out


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.data = dataset()
        self.bundle, self.custody = t.build_transport(self.data, KEY)

    def test_full_roundtrip_into_unchanged_scientific_scorer(self):
        original = t.evaluator()
        direct_predictions = {"units": self.data["units"], "cases": [
            {"case_id": c["case_id"], "times_s": c["target"]["times_s"], "values": [1.] * 4}
            for c in self.data["cases"] if c["role"] == "held"]}
        expected = original.evaluate(self.data, direct_predictions, draws=100)
        for mode in t.MODES:
            predictions, receipt = t.collect_response(self.bundle, self.custody,
                                                       answer(self.bundle, mode), expected_mode=mode)
            self.assertEqual(original.evaluate(self.data, predictions, draws=100), expected)
            # (1 + 9 + 25 + 49)/4, and the train mean is exactly the target.
            self.assertEqual(expected["complete_roster_primary_mean_difference"], 21.)
            self.assertEqual(receipt["complete_cases"], 4)
            self.assertEqual(receipt["requested_samples"], 16)
            self.assertFalse(receipt["runtime_compliance_verified"])

    def test_hidden_values_masks_flags_and_private_commitment_do_not_change_public(self):
        changed = copy.deepcopy(self.data)
        for case in changed["cases"]:
            if case["role"] != "train":
                case["target"]["values"] = [None, -999., 123456., None]
            case["quality_flags"].append("response-selected-private-flag")
            case["provenance"]["asset_id"] = "private-other-asset"
        bundle, custody = t.build_transport(changed, KEY)
        self.assertEqual(bundle, self.bundle)
        self.assertEqual(custody["bundle_sha256"], self.custody["bundle_sha256"])
        self.assertNotEqual(custody["dataset_sha256"], self.custody["dataset_sha256"])
        self.assertNotIn("dataset_sha256", json.dumps(bundle))
        self.assertNotIn("private-", json.dumps(bundle))
        for role in ("development", "held"):
            for case in bundle["roles"][role]["cases"]:
                self.assertNotIn("training_response", case)
                self.assertNotIn("target", case)

    def test_aliases_preserve_grouping_and_all_allowed_measurements(self):
        for role, packet in self.bundle["roles"].items():
            originals = [case for case in self.data["cases"] if case["role"] == role]
            for source, public in zip(originals, packet["cases"]):
                for field in ("source", "receiver_pre", "source_id", "receiver_id", "condition",
                              "stimulus_parameters", "stimulus_onset_acquisition_s"):
                    self.assertEqual(source[field], public[field])
                self.assertEqual(source["target"]["times_s"], public["response_times_s"])
            self.assertEqual(packet["cases"][0]["trial_id"], packet["cases"][1]["trial_id"])
        held = self.bundle["roles"]["held"]["cases"]
        # Same local trial label in a different acquisition must not collide.
        self.assertNotEqual(held[0]["trial_id"], held[2]["trial_id"])
        self.assertNotEqual(held[0]["worm_id"], held[2]["worm_id"])
        self.assertEqual(self.bundle, t.build_transport(self.data, KEY)[0])
        self.assertNotEqual(self.bundle, t.build_transport(self.data, b"other-test-key" * 4)[0])

    def test_no_target_mask_based_response_abstention(self):
        self.data["cases"][-1]["target"]["values"] = [None] * 4
        bundle, custody = t.build_transport(self.data, KEY)
        submission = answer(bundle)
        submission["cases"][-1]["values"][0] = None
        with self.assertRaisesRegex(ValueError, "finite prediction"):
            t.collect_response(bundle, custody, submission, expected_mode="direct_observation")
        predictions, _ = t.collect_response(bundle, custody, answer(bundle), expected_mode="direct_observation")
        self.assertEqual(len(predictions["cases"]), 4)

    def test_roster_grid_units_mode_and_submission_content_attacks(self):
        mutations = [lambda s: s["cases"].pop(),
                     lambda s: s["cases"].append(copy.deepcopy(s["cases"][0])),
                     lambda s: s["cases"][0].update(case_id="original-private-case"),
                     lambda s: s["cases"][0]["times_s"].__setitem__(1, .300001),
                     lambda s: s["cases"][0]["times_s"].__setitem__(0, False),
                     lambda s: s["cases"][0]["values"].__setitem__(0, float("nan")),
                     lambda s: s["cases"][0]["values"].__setitem__(0, True),
                     lambda s: s.update(units="dF/F"),
                     lambda s: s.update(access_mode="frozen_program"),
                     lambda s: s.update(bundle_sha256="0" * 64),
                     lambda s: s.update(arbitrary_metadata="not allowed")]
        for mutation in mutations:
            submission = answer(self.bundle)
            mutation(submission)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                t.collect_response(self.bundle, self.custody, submission, expected_mode="direct_observation")

    def test_changed_bundle_custody_mapping_or_source_dataset_rejected(self):
        changed = copy.deepcopy(self.bundle)
        changed["roles"]["held"]["cases"][0]["source"]["values"][0] = 999.
        with self.assertRaisesRegex(ValueError, "frozen custody"):
            t.collect_response(changed, self.custody, answer(changed), expected_mode="direct_observation")
        custody = copy.deepcopy(self.custody)
        custody["held_mapping"][0]["times_s"][0] = .001
        with self.assertRaisesRegex(ValueError, "custody roster"):
            t.collect_response(self.bundle, custody, answer(self.bundle), expected_mode="direct_observation")
        self.data["cases"][-1]["target"]["values"][0] = 999.
        with self.assertRaisesRegex(ValueError, "dataset changed"):
            t.validate_custody_dataset(self.data, self.custody)

    def test_duplicate_json_keys_and_nonfinite_constants_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            for text in ('{"cases": [], "cases": [1]}', '{"x": NaN}', '{"x": Infinity}'):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    t.read_json(path)

    def test_cli_separates_custody_and_completes_collection_without_target_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data, key = base / "data.json", base / "key.bin"
            data.write_text(json.dumps(self.data))
            key.write_bytes(KEY)
            command = [sys.executable, "-B", str(ROOT / "participant_transport.py")]
            subprocess.run(command + ["export", str(data), str(key), str(base / "public"),
                                      str(base / "custody.json")], check=True, capture_output=True)
            self.assertEqual((base / "custody.json").stat().st_mode & 0o777, 0o600)
            self.assertEqual(len(list((base / "public").iterdir())), 5)
            bundle = t.read_json(base / "public/packet.json")
            submission = base / "answer.json"
            submission.write_text(json.dumps(answer(bundle)))
            subprocess.run(command + ["collect", str(base / "public/packet.json"), str(base / "custody.json"),
                                      str(submission), str(data), str(base / "predictions.json"),
                                      str(base / "receipt.json"), "--mode", "direct_observation"],
                           check=True, capture_output=True)
            self.assertEqual(len(t.read_json(base / "predictions.json")["cases"]), 4)
            self.assertEqual((base / "predictions.json").stat().st_mode & 0o777, 0o600)
            forbidden = subprocess.run(command + ["export", str(data), str(key), str(base / "bad-public"),
                                                  str(base / "bad-public/custody.json")], capture_output=True)
            self.assertNotEqual(forbidden.returncode, 0)
            self.assertFalse((base / "bad-public").exists())


if __name__ == "__main__":
    unittest.main()
