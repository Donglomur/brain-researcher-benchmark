"""Generated public geometry and protocol controls; no authentic arrays or fits."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parent
CONTRACT_PATH = HERE.parent / "registered-runtime" / "io_contract.py"
CONTRACT_SHA256 = "6498192c2621cb6bb904e11d1c8b17addf172a1c89021adbb0245f4ab89ee849"
spec = importlib.util.spec_from_file_location("neural019_viewer", HERE / "viewer.py")
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)


def generated():
    # Full required shapes in memory. A shared per-trial backing array keeps the
    # fixture small; production Session takes independent immutable copies.
    page = np.zeros((140, 137), dtype=np.uint16)
    page[0, 0], page[139, 136] = 3, 65535
    groups = np.arange(1340, dtype=np.int64) % 28
    velocity = np.zeros((1340, 140, 2), dtype=np.float64)
    velocity[-1, -1] = [-0.125, 0.0625]
    return {
        "train_counts": np.broadcast_to(page, (1340, 140, 137)),
        "assessment_counts": np.broadcast_to(page, (126, 140, 137)),
        "train_velocity": velocity,
        "train_trial_ids": np.asarray([f"generated-training-{i}" for i in range(1340)]),
        "assessment_trial_ids": np.asarray([f"generated-assessment-{i}" for i in range(126)]),
        "neural_unit_ids": np.asarray([f"generated-unit-{i}" for i in range(137)]),
        "train_group_ids": groups, "train_cv_fold_ids": groups % 4,
        "neural_left_edges_ms": np.arange(-250, 450, 5),
        "velocity_left_edges_ms": np.arange(-150, 550, 5),
        "velocity_axes": np.asarray(["x", "y"]), "velocity_units": np.asarray("m/s"),
        "panel_fingerprint": np.asarray("a" * 64),
    }


def request(session, value):
    return session.dispatch(viewer.encoded(value))


def view(role="assessment", trial=125, **changes):
    result = {"action": "view", "role": role, "trial": trial,
              "unit_start": 136, "unit_stop": 137, "bin_start": 139, "bin_stop": 140}
    result.update(changes)
    return result


def answer(trial=0):
    return {"action": "answer", "trial": trial,
            "velocity": [[float(trial) - 63.5, -float(b) / 8] for b in range(140)]}


class ViewerControls(unittest.TestCase):
    def setUp(self):
        self.public = generated()

    def session(self, **kwargs):
        return viewer.Session(self.public, max_actions=kwargs.get("max_actions", 1024))

    def test_exact_full_geometry_and_private_fields_rejected(self):
        for changes in ({"assessment_velocity": np.zeros((126, 140, 2))},
                        {"assessment_counts": self.public["assessment_counts"][:-1]},
                        {"train_counts": self.public["train_counts"][:, :, :-1]}):
            with self.subTest(fields=list(changes)):
                with self.assertRaises(ValueError):
                    viewer.Session(dict(self.public, **changes), max_actions=1024)

    def test_clock_units_and_whole_group_fold_constraints(self):
        bad_fold = self.public["train_cv_fold_ids"].copy()
        bad_fold[0] = 1
        for key, value in (("neural_left_edges_ms", np.arange(-245, 455, 5)),
                           ("velocity_units", np.asarray("cm/s")),
                           ("train_cv_fold_ids", bad_fold)):
            with self.subTest(field=key), self.assertRaises(ValueError):
                viewer.Session(dict(self.public, **{key: value}), max_actions=1024)

    def test_last_unit_last_bin_keeps_exact_count_and_neural_clock(self):
        session = self.session()
        out = request(session, view())
        self.assertIn('data-bin="139" data-unit="136">65535</text>', out["svg"])
        self.assertIn('>445</text>', out["svg"])
        self.assertEqual((out["unit_range"], out["bin_range"]), ([136, 137], [139, 140]))
        self.assertNotIn("-0.125", out["svg"])
        self.assertNotIn("velocity", {k for k in out if k != "svg"})

    def test_all_calibration_trials_available_and_distinct_velocity_clock(self):
        out = request(self.session(), view(role="calibration", trial=1339))
        self.assertIn('data-calibration-bin="139">545 | -0.125 | 0.0625</text>', out["svg"])
        self.assertIn("measured calibration", out["svg"])
        self.assertIn("training fold", out["svg"])

    def test_full_crop_all_counts_present_without_downsampling(self):
        out = request(self.session(), view(trial=0, unit_start=0, unit_stop=16, bin_start=0, bin_stop=20))
        self.assertEqual(out["svg"].count('data-unit="'), 16 * 20)
        self.assertIn('data-bin="0" data-unit="0">3</text>', out["svg"])
        self.assertLessEqual(len(out["svg"].encode()), 131072)

    def test_forbidden_operations_and_out_of_range_crop_refused(self):
        session = self.session()
        bad = [dict(view(), role="private"), dict(view(), path="/gold"),
               dict(view(), trial=True), dict(view(), unit_stop=138),
               dict(view(), unit_start=0, unit_stop=17),
               dict(view(), bin_start=0, bin_stop=21), {"action": "python", "code": "pass"}]
        for value in bad:
            with self.subTest(request=value), self.assertRaises(ValueError):
                request(session, value)
        self.assertEqual(session.receipt()["actions"], len(bad))
        self.assertEqual(session.receipt()["answered"], 0)

    def test_partial_nonfinite_bool_and_duplicate_answers_refused(self):
        session = self.session()
        partial = answer(); partial["velocity"].pop()
        boolean = answer(); boolean["velocity"][0][0] = True
        wrong_trial = answer(126)
        for value in (partial, boolean, wrong_trial):
            with self.assertRaises(ValueError):
                request(session, value)
        with self.assertRaises(ValueError):
            session.dispatch(b'{"action":"answer","trial":0,"velocity":NaN}')
        self.assertEqual(session.receipt()["answered"], 0)
        request(session, answer())
        with self.assertRaises(ValueError):
            request(session, answer())
        self.assertEqual(session.receipt()["answered"], 1)

    def test_complete_collection_exports_original_six_field_contract(self):
        session = self.session()
        for i in reversed(range(126)):
            request(session, answer(i))
        closed = request(session, {"action": "finish"})
        self.assertEqual(closed["velocity_values"], 35280)
        output = session.submission()
        self.assertEqual(set(output), {"velocity", "trial_ids", "velocity_left_edges_ms",
                                      "velocity_axes", "velocity_units", "panel_fingerprint"})
        self.assertEqual(output["velocity"].shape, (126, 140, 2))
        self.assertEqual(output["velocity"][125, 139].tolist(), [61.5, -17.375])
        self.assertTrue(np.array_equal(output["trial_ids"], self.public["assessment_trial_ids"]))
        self.assertTrue(np.array_equal(output["velocity_left_edges_ms"], np.arange(-150, 550, 5)))
        self.assertEqual(output["velocity_units"].item(), "m/s")
        self.assertFalse(session.receipt()["public_packet_authenticated"])
        self.assertFalse(session.receipt()["native_understanding_measured"])

    def test_incomplete_collection_cannot_finish_or_export(self):
        session = self.session()
        request(session, answer(0))
        with self.assertRaises(ValueError):
            request(session, {"action": "finish"})
        with self.assertRaises(ValueError):
            session.submission()
        self.assertFalse(session.receipt()["closed"])

    def test_existing_public_submission_contract_accepts_complete_export(self):
        body = CONTRACT_PATH.read_bytes()
        self.assertEqual(hashlib.sha256(body).hexdigest(), CONTRACT_SHA256)
        spec = importlib.util.spec_from_file_location("unchanged_neural019_contract", CONTRACT_PATH)
        contract = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(contract)
        session = self.session()
        for i in reversed(range(126)):
            request(session, answer(i))
        request(session, {"action": "finish"})
        prediction, receipt = contract.validate_candidate(session.submission(), contract.public_contract(self.public))
        self.assertEqual(receipt["status"], "public_submission_valid")
        self.assertEqual((receipt["cases"], receipt["bins"], receipt["target_loader_invocations"]), (126, 140, 0))
        self.assertEqual(prediction[125, 139].tolist(), [61.5, -17.375])

    def test_input_and_export_are_owned_copies(self):
        session = self.session()
        self.public["train_velocity"][-1, -1] = [123, 456]
        out = request(session, view(role="calibration", trial=1339))
        self.assertIn("545 | -0.125 | 0.0625", out["svg"])
        for i in range(126):
            request(session, answer(i))
        request(session, {"action": "finish"})
        exported = session.submission(); exported["velocity"][0, 0, 0] = 999
        self.assertEqual(session.submission()["velocity"][0, 0, 0], -63.5)
        for value in (view(), answer(0), {"action": "finish"}):
            with self.assertRaises(ValueError):
                request(session, value)

    def test_failed_actions_consume_declared_budget(self):
        session = self.session(max_actions=127)
        with self.assertRaises(ValueError):
            request(session, {"action": "unknown"})
        for i in range(126):
            request(session, answer(i))
        with self.assertRaises(ValueError):
            request(session, {"action": "finish"})
        self.assertEqual(session.receipt()["actions"], 127)
        self.assertFalse(session.receipt()["closed"])

    def test_request_duplicate_keys_nonfinite_and_oversize_refused(self):
        session = self.session()
        for raw in (b'{"action":"view","action":"finish"}', b'{"action":NaN}',
                    b"x" * 32769, b"[1]", b"\xff"):
            with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                session.dispatch(raw)
        self.assertEqual(session.receipt()["actions"], 5)

    def test_utf16_and_utf32_are_refused_even_when_valid_json(self):
        session = self.session()
        text = viewer.encoded(view()).decode("utf-8")
        for encoding in ("utf-16", "utf-32"):
            with self.subTest(encoding=encoding), self.assertRaises(ValueError):
                session.dispatch(text.encode(encoding))
        self.assertEqual(session.receipt()["actions"], 2)
        self.assertTrue(all(row["status"] == "rejected" for row in session.events()))
        self.assertEqual(session.dispatch(text.encode("utf-8"))["kind"], "svg")

    def test_transcript_hash_chain_is_recomputable_and_copy_safe(self):
        session = self.session()
        request(session, view())
        request(session, answer())
        previous = "0" * 64
        events = session.events()
        for i, event in enumerate(events):
            observed = event.pop("sha256")
            self.assertEqual((event["sequence"], event["previous_sha256"]), (i, previous))
            canonical = (json.dumps(event, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
            self.assertEqual(observed, hashlib.sha256(canonical).hexdigest())
            previous = observed
        self.assertEqual(previous, session.receipt()["event_chain_sha256"])
        self.assertIn("sha256", session.events()[0])

    def test_wrong_or_linked_packet_refused_before_numpy_load(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch).resolve()
            source = root / "public.npz"; source.write_bytes(b"bad")
            linked = root / "linked.npz"; linked.symlink_to(source)
            for path in (source, linked):
                with self.subTest(path=path.name), patch.object(np, "load") as loader:
                    with self.assertRaises(ValueError):
                        viewer.load_public(path, max_actions=1024)
                    loader.assert_not_called()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--io-contract", type=Path, default=CONTRACT_PATH)
    arguments, remainder = parser.parse_known_args()
    CONTRACT_PATH = arguments.io_contract
    unittest.main(argv=[__file__, *remainder], verbosity=2)
