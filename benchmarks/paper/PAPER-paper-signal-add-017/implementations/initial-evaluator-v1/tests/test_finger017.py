import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import finger017 as f


def fixture(subjects=("S01",)):
    protocol = {"schema_version": 1, "task_id": f.TASK, "classes": [1, 4], "condition": "MI",
                "evaluation_session": 1, "subjects": list(subjects),
                "calibration_policy": "prospective_equal_run_subset", "calibration_runs_per_family": 1,
                "runs": []}
    recordings = {}
    for subject in subjects:
        for session, stage, nc, role in ((0, "Offline", 3, "train"), (1, "Base", 3, "calibration"),
                                        (1, "Base", 2, "calibration"), (1, "Finetune", 2, "test")):
            rid = f"{subject}/{session}/{stage}/{nc}/R01"
            labels = [1, 4] if nc == 2 else [1, 2, 4]
            row = {"id": rid, "source_member": rid + ".mat", "subject": subject, "condition": "MI",
                   "session": session, "run_number": 1, "nclass": nc, "stage": stage, "role": role,
                   "expected_class_counts": {str(c): 1 for c in labels}}
            protocol["runs"].append(row)
            signals, events = [], []
            time = np.arange(f.WINDOW) / f.FS
            spatial = np.linspace(-1, 1, 128)[:, None]
            for i, c in enumerate(labels):
                freq = {1: 10, 2: 18, 4: 25}[c]
                common_offset = (int(subject[1:]) * 1000 + session * 100 +
                                 {"Offline": 0, "Base": 10, "Finetune": 20}[stage] + nc) * .01
                signals.append(spatial * np.sin(2 * np.pi * freq * time) +
                               2 * np.sin(2 * np.pi * 3 * time) + common_offset)
                events.extend([{"type": "Target", "sample": i * f.WINDOW + 1, "value": c},
                               {"type": "TrialEnd", "sample": (i + 1) * f.WINDOW + 1, "value": 0}])
            recordings[rid] = {"data": np.concatenate(signals, axis=1), "fsample": 1024, "events": events,
                               "prediction": [4] * len(labels), "prob_1": [0] * len(labels)}
    return protocol, recordings


def metric_fixture(subject_labels, windows_per_trial=1, classes=(1, 4)):
    trials, windows = [], []
    for subject, labels in subject_labels.items():
        for i, label in enumerate(labels):
            tid = f"{subject}/run/trial{i}"
            ids = [f"{tid}/window{j}" for j in range(windows_per_trial)]
            trials.append({"id": tid, "subject": subject, "run_id": f"{subject}/run", "label": label,
                           "role": "test", "window_ids": ids})
            windows.extend({"id": wid, "role": "test"} for wid in ids)
    return {"protocol": {"subjects": list(subject_labels), "classes": list(classes)},
            "trials": trials, "windows": windows}


class SourceBridgeTests(unittest.TestCase):
    def test_raw_boundary_car_and_independent_window_counts(self):
        p, raw = fixture()
        run = p["runs"][0]
        run["expected_class_counts"] = {"1": 1, "2": 1, "4": 1}
        length = 3 * 1024
        eeg = np.arange(128)[:, None] + np.arange(3 * length)[None, :] * .01
        events = []
        for i, label in enumerate([1, 2, 4]):
            events.extend([{"type": "Target", "sample": i * length + 1, "value": label},
                           {"type": "TrialEnd", "sample": (i + 1) * length + 1}])
        trials = f.extract_trials(eeg, 1024, events, run)
        self.assertEqual(trials[0]["start"], 0)
        self.assertEqual(trials[0]["end"], length)
        np.testing.assert_allclose(trials[0]["data"][:, 0], np.arange(128) - 63.5)
        self.assertEqual(len(range(0, trials[0]["data"].shape[1] - 1024 + 1, 128)), 17)
        events[-1]["sample"] += 2048
        eeg = np.pad(eeg, ((0, 0), (0, 2048)))
        trials = f.extract_trials(eeg, 1024, events, run)
        self.assertEqual(len(range(0, trials[-1]["data"].shape[1] - 1024 + 1, 128)), 33)

    def test_exact_source_calibration_routes_and_grouping(self):
        p, raw = fixture()
        prepared = f.prepare(p, raw)
        self.assertEqual(prepared["binary_excluded_index_trials"], 2)
        self.assertEqual(len(prepared["trials"]), 8)
        for t in prepared["trials"]:
            self.assertTrue(all(w.startswith(t["id"]) for w in t["window_ids"]))
        bad = copy.deepcopy(p)
        bad["runs"] = [r for r in bad["runs"] if not (r["role"] == "calibration" and r["nclass"] == 2)]
        with self.assertRaisesRegex(ValueError, "calibration coverage"):
            f.validate_protocol(bad)
        bad = copy.deepcopy(p)
        bad["calibration_policy"] = "source_folder_selection"
        with self.assertRaisesRegex(ValueError, "all eight"):
            f.validate_protocol(bad)
        complete = copy.deepcopy(p)
        complete["calibration_policy"] = "source_folder_selection"
        complete["calibration_runs_per_family"] = 8
        for r in p["runs"]:
            if r["role"] == "calibration":
                for n in range(2, 9):
                    extra = copy.deepcopy(r)
                    extra.update(id=r["id"][:-2] + f"{n:02}",
                                 source_member=r["source_member"][:-6] + f"{n:02}.mat", run_number=n)
                    complete["runs"].append(extra)
        f.validate_protocol(complete)

    def test_temporal_role_and_identity_adversaries(self):
        p, _ = fixture()
        for field, value, message in (("session", 1, "offline/session"), ("condition", "ME", "mismatch")):
            bad = copy.deepcopy(p)
            bad["runs"][0][field] = value
            with self.assertRaisesRegex(ValueError, message):
                f.validate_protocol(bad)
        bad = copy.deepcopy(p)
        duplicate = copy.deepcopy(bad["runs"][0])
        duplicate["id"], duplicate["source_member"] = "new-alias", "new-alias.mat"
        bad["runs"].append(duplicate)
        with self.assertRaisesRegex(ValueError, "original run reused"):
            f.validate_protocol(bad)
        bad = copy.deepcopy(p)
        bad["runs"][0]["stage"] = "Finetune"
        bad["runs"][0]["session"] = 1
        with self.assertRaisesRegex(ValueError, "prior sessions"):
            f.validate_protocol(bad)

    def test_missing_event_family_is_rejected_before_recording_load(self):
        p, _ = fixture(("S07",))
        p["evaluation_session"] = 5
        for r in p["runs"]:
            if r["session"]:
                r["session"] = 5
        with self.assertRaisesRegex(ValueError, "known unusable"):
            f.validate_protocol(p)

    def test_malformed_events_and_raw_admission(self):
        p, raw = fixture()
        run = p["runs"][0]
        r = raw[run["id"]]
        for modify in (lambda a: a["events"].pop(), lambda a: a["events"].pop(1),
                       lambda a: a.update(fsample=100), lambda a: a["events"][0].update(sample=0),
                       lambda a: a["events"][0].update(value=3),
                       lambda a: a["data"].__setitem__((0, 0), np.nan)):
            bad = copy.deepcopy(r)
            modify(bad)
            with self.assertRaises(ValueError):
                f.extract_trials(bad["data"], bad["fsample"], bad["events"], run)

    def test_public_packet_excludes_targets_events_online_outputs(self):
        p, raw = fixture()
        prepared = f.prepare(p, raw)
        packet = f.public_packet(prepared, "test")
        self.assertEqual(set(packet), {"schema_version", "task_id", "classes", "role", "windows", "eeg"})
        serialized = json.dumps({k: v for k, v in packet.items() if k != "eeg"})
        for key in ("target", "labels", "events", "prediction", "prob_"):
            self.assertNotIn(key, serialized)
        packet["eeg"][0, 0, 0] = 999
        self.assertNotEqual(prepared["eeg"][-1, 0, 0], 999)
        self.assertIn("labels", f.public_packet(prepared, "train"))

    def test_numeric_run_alias_rejected_despite_new_metadata(self):
        p, raw = fixture()
        calibration = next(r for r in p["runs"] if r["role"] == "calibration" and r["nclass"] == 2)
        test = next(r for r in p["runs"] if r["role"] == "test")
        raw[test["id"]]["data"] = raw[calibration["id"]]["data"].copy()
        with self.assertRaisesRegex(ValueError, "duplicated numeric EEG"):
            f.prepare(p, raw)


class MetricTests(unittest.TestCase):
    def test_paper_majority_differs_from_mean_probability(self):
        prep = metric_fixture({"S01": [1]}, windows_per_trial=3)
        rows = [[.51, .49], [.51, .49], [.01, .99]]
        pred = {w["id"]: row for w, row in zip(prep["windows"], rows)}
        result = f.score(prep, pred)
        self.assertEqual(result["subject_macro_accuracy"], 1)
        self.assertGreater(np.mean(rows, axis=0)[1], .5)
        self.assertIsNone(result["subject_macro_balanced_accuracy"])

    def test_independent_confusion_and_fixed_classes(self):
        prep = metric_fixture({"S01": [1, 1, 1, 1, 2, 2, 4, 4]}, classes=(1, 2, 4))
        decisions = [1, 1, 1, 2, 1, 2, 2, 4]
        pred = {w["id"]: np.eye(3)[[1, 2, 4].index(c)].tolist()
                for w, c in zip(prep["windows"], decisions)}
        result = f.score(prep, pred)
        self.assertEqual(result["subject_macro_accuracy"], 5 / 8)
        self.assertAlmostEqual(result["subject_macro_balanced_accuracy"], 7 / 12)
        self.assertEqual(result["subjects"]["S01"]["confusion_true_by_predicted"], [[3, 1, 0], [1, 1, 0], [0, 1, 1]])
        np.testing.assert_allclose(result["subjects"]["S01"]["class_precision"], [.75, 1 / 3, 1])

    def test_participant_weight_and_paired_cluster_bootstrap(self):
        prep = metric_fixture({"S01": [1] * 10, "S02": [1]})
        base_decisions = [1] * 9 + [4] + [4]
        adapted_decisions = [1] * 10 + [4]
        make = lambda ds: {w["id"]: ([1., 0.] if c == 1 else [0., 1.]) for w, c in zip(prep["windows"], ds)}
        baseline, adapted = f.score(prep, make(base_decisions)), f.score(prep, make(adapted_decisions))
        self.assertAlmostEqual(baseline["subject_macro_accuracy"], .45)
        comparison = f.paired_comparison(baseline, adapted, replicates=100)
        self.assertAlmostEqual(comparison["delta_subject_macro_accuracy"], .05)
        np.testing.assert_allclose(comparison["paired_subject_bootstrap_95_percentile"], [0, .1])

    def test_vote_ties_roster_simplex_and_nan(self):
        prep = metric_fixture({"S01": [4]}, windows_per_trial=2)
        valid = {w["id"]: p for w, p in zip(prep["windows"], [[1, 0], [0, 1]])}
        scored = f.score(prep, valid)
        self.assertEqual(scored["trials"][0]["prediction"], 1)
        self.assertTrue(scored["trials"][0]["tie"])
        for bad in ({}, {**valid, "extra": [1, 0]},
                    {k: [np.nan, 0] for k in valid}, {k: [.1, .1] for k in valid},
                    {k: [-.1, 1.1] for k in valid}):
            with self.assertRaises(ValueError):
                f.score(prep, bad)


class ReferenceTests(unittest.TestCase):
    def test_equal_trial_weight_and_no_test_scaling(self):
        model = f.Centroid().fit(np.array([[0.], [0.], [10.], [20.]]), [1, 1, 1, 4], ["a", "a", "b", "c"], [1, 4])
        np.testing.assert_allclose(model.mean, [10.])
        mean, scale = model.mean.copy(), model.scale.copy()
        model.predict([[1e6]])
        np.testing.assert_equal(model.mean, mean)
        np.testing.assert_equal(model.scale, scale)
        np.testing.assert_allclose(model.prior, [2 / 3, 1 / 3])

    def test_complete_reference_and_controls(self):
        p, raw = fixture()
        prep = f.prepare(p, raw)
        result = f.run_reference(prep)
        self.assertEqual(result["baseline"]["subject_macro_accuracy"], 1.)
        self.assertEqual(result["calibration_augmented"]["subject_macro_accuracy"], 1.)
        self.assertEqual(result["controls"]["no_neural"]["subject_macro_accuracy"], .5)
        self.assertEqual(result["scientific_qualification"], "unknown")
        self.assertIsNone(result["paired_comparison"]["paired_subject_bootstrap_95_percentile"])
        self.assertEqual(set(result["controls"]), {"no_neural", "within_session_label_permutation", "run_trial_alignment_shift"})
        json.dumps(result, allow_nan=False)

    def test_complete_ternary_reference_and_source_route(self):
        p, raw = fixture()
        p["classes"] = [1, 2, 4]
        removed = next(r for r in p["runs"] if r["role"] == "calibration" and r["nclass"] == 2)
        p["runs"].remove(removed)
        raw.pop(removed["id"])
        train = next(r for r in p["runs"] if r["role"] == "train")
        test = next(r for r in p["runs"] if r["role"] == "test")
        test["nclass"] = 3
        test["expected_class_counts"] = {"1": 1, "2": 1, "4": 1}
        raw[test["id"]] = copy.deepcopy(raw[train["id"]])
        raw[test["id"]]["data"] += 1
        prepared = f.prepare(p, raw)
        self.assertEqual(prepared["binary_excluded_index_trials"], 0)
        result = f.score(prepared, f.reference_predictions(prepared))
        self.assertEqual(result["subject_macro_accuracy"], 1)
        self.assertEqual(result["subjects"]["S01"]["class_support"], [1, 1, 1])

    def test_heldout_target_mutation_does_not_change_predictions(self):
        p, raw = fixture()
        before = f.prepare(p, raw)
        for run in p["runs"]:
            if run["role"] == "test":
                for event in raw[run["id"]]["events"]:
                    if event["type"] == "Target":
                        event["value"] = {1: 4, 4: 1}[event["value"]]
        after = f.prepare(p, raw)
        self.assertEqual(f.reference_predictions(before), f.reference_predictions(after))

    def test_safe_export_cli_reference_score_packets_and_hash(self):
        p, raw = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for i, run in enumerate(p["runs"]):
                source = raw[run["id"]]
                path = root / f"run{i}.npz"
                np.savez(path, data=source["data"], fsample=1024, prediction=np.ones(2))
                run.update(eeg_npz=path.name, eeg_npz_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), events=source["events"])
            protocol = root / "protocol.json"
            protocol.write_text(json.dumps(p))
            f.main(["reference", str(protocol), str(root / "report.json")])
            result = json.loads((root / "report.json").read_text())
            self.assertEqual(result["baseline"]["subject_macro_accuracy"], 1)
            f.main(["packets", str(protocol), str(root / "packets")])
            self.assertNotIn("labels", json.loads((root / "packets/test.json").read_text()))
            prepared = f.prepare(p, f.load_recordings(p, root))
            predictions = root / "predictions.json"
            predictions.write_text(json.dumps(f.reference_predictions(prepared)))
            f.main(["score", str(protocol), str(root / "score.json"), "--predictions", str(predictions)])
            wid = next(iter(f.reference_predictions(prepared)))
            predictions.write_text('{"' + wid + '":[1,0],"' + wid + '":[0,1]}')
            with self.assertRaisesRegex(ValueError, "duplicate prediction"):
                f.main(["score", str(protocol), str(root / "bad.json"), "--predictions", str(predictions)])
            bad = copy.deepcopy(p)
            bad["runs"][-1]["eeg_npz"] = bad["runs"][-2]["eeg_npz"]
            bad["runs"][-1]["eeg_npz_sha256"] = bad["runs"][-2]["eeg_npz_sha256"]
            with self.assertRaisesRegex(ValueError, "path reused"):
                f.load_recordings(bad, root)
            alias = root / "alias.npz"
            alias.write_bytes((root / bad["runs"][-2]["eeg_npz"]).read_bytes())
            bad["runs"][-1]["eeg_npz"] = alias.name
            with self.assertRaisesRegex(ValueError, "bytes reused"):
                f.load_recordings(bad, root)
            p["runs"][0]["eeg_npz_sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                f.load_recordings(p, root)


if __name__ == "__main__":
    unittest.main()
