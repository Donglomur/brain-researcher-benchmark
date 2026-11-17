"""Generated engineering controls; none are authentic Siena signal results."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import siena_evaluator as se
import reference


def manifest(patients=("PN01",), role="train", references=True, n=2000, fs=10):
    rows = []
    for rid, source in se.inventory().items():
        if source["patient_id"] in patients:
            row = dict(source, sample_rate=fs, n_samples=n, channels=["FP1", "FP2"])
            if references:
                row["reference_events"] = [[100, 120]]
            rows.append(row)
    return dict(schema_version=1, task_id=se.TASK_ID, role=role, patients=list(patients), recordings=rows)


def signals(m):
    result = {}
    for row in m["recordings"]:
        t = np.arange(row["n_samples"]) / row["sample_rate"]
        envelope = 1 + 5 * ((t >= 100) & (t < 120))
        result[row["recording_id"]] = np.column_stack((np.sin(t * 2) * envelope, np.cos(t * 3) * envelope))
    return result


class MetricsTests(unittest.TestCase):
    def test_independently_derived_controls(self):
        controls = json.loads(Path(__file__).with_name("independent_controls.json").read_text())["controls"]
        names = {"n_ref": "reference_events", "tp": "true_positives", "fp": "false_alarms", "f1": "event_f1"}
        for case in controls:
            with self.subTest(case=case["name"]):
                actual = se.event_score(case["reference_events"], case["hypothesis_events"], case["duration_seconds"])
                for key, expected in case["expected_independently_derived"].items():
                    observed = actual[names.get(key, key)]
                    if expected is None:
                        self.assertIsNone(observed)
                    else:
                        self.assertAlmostEqual(observed, expected)

    def test_patient_macro_not_recording_or_event_pool(self):
        m = manifest(("PN01", "PN11"), role="test", n=36000)
        m["recordings"][1]["reference_events"] = [[i, i + 10] for i in range(100, 1900, 200)]
        predictions = {r["recording_id"]: np.zeros(r["n_samples"]) for r in m["recordings"]}
        predictions[m["recordings"][0]["recording_id"]][1000:1100] = 1
        output = se.score_manifest(m, predictions, .5)
        self.assertAlmostEqual(output["patient_macro_event_f1"], .5)
        self.assertAlmostEqual(output["patient_macro_sensitivity"], .5)

    def test_subtick_alarm_is_false_alarm_as_native(self):
        score = se.event_score([], [[1.01, 1.02]], 10)
        self.assertEqual(score["false_alarms"], 1)

    def test_invalid_events_and_vectors(self):
        for event in [[[-1, 1]], [[1, 1]], [[0, 11]], [[1, 5], [4, 7]], [[5, 7], [1, 2]], [[0, float("nan")]]]:
            with self.subTest(event=event), self.assertRaises(ValueError):
                se.event_score(event, [], 10)
        for vector in [[], [[0, 1]], [0, float("inf")], [True, False], ["0", "1"]]:
            with self.subTest(vector=vector), self.assertRaises(ValueError):
                se.scores_to_events(vector, 10, .5)

    def test_boundary_events(self):
        self.assertEqual(se.scores_to_events([1, 1, 0, 1], 2, .5), [(0, 1), (1.5, 2)])
        self.assertEqual(se.scores_to_events([1, 1], 2, .5), [(0, 1)])
        self.assertEqual(se.scores_to_events([0, 0], 2, .5), [])

    def test_paired_patient_uncertainty(self):
        a = {"patients": {"PN01": {"event_f1": .8}, "PN11": {"event_f1": .6}}}
        b = {"patients": {"PN01": {"event_f1": .3}, "PN11": {"event_f1": .1}}}
        result = se.paired_bootstrap(a, b, draws=100, seed=7)
        self.assertAlmostEqual(result["difference"], .5)
        np.testing.assert_allclose(result["percentile_95_interval"], [.5, .5])
        self.assertEqual(result, se.paired_bootstrap(a, b, draws=100, seed=7))


class ManifestTests(unittest.TestCase):
    def test_full_patient_inventory(self):
        m = manifest(("PN00",))
        self.assertEqual(len(se.validate_manifest(m, "train", True)), 5)
        m["recordings"].pop()
        with self.assertRaisesRegex(ValueError, "missing complete"):
            se.validate_manifest(m, "train", True)

    def test_identity_and_leakage(self):
        changes = [("recording_id", "PN99/fake.edf"), ("patient_id", "PN11"),
                   ("source_sha256", "0" * 64), ("channels", ["FP1", "EKG"]),
                   ("channels", ["FP1", "MK"]), ("channels", ["FP1", "FP1"]),
                   ("n_samples", 1), ("sample_rate", float("nan"))]
        for key, value in changes:
            m = manifest()
            m["recordings"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                se.validate_manifest(m, "train", True)
        m = manifest()
        m["recordings"].append(copy.deepcopy(m["recordings"][0]))
        with self.assertRaises(ValueError):
            se.validate_manifest(m, "train", True)
        with self.assertRaisesRegex(ValueError, "exposed reference"):
            se.validate_manifest(manifest(role="test"), "test", False)

    def test_complete_scores_and_nonfinite(self):
        m = manifest(role="test")
        rid = m["recordings"][0]["recording_id"]
        for predictions in [{}, {rid: np.zeros(1999)}, {rid: np.full(2000, np.nan)}, {rid: np.zeros(2000), "extra": []}]:
            with self.assertRaises(ValueError):
                se.score_manifest(m, predictions, .5)

    def test_constant_scores_retained_as_controls(self):
        m = manifest(role="test")
        rid = m["recordings"][0]["recording_id"]
        score = se.score_manifest(m, {rid: np.zeros(2000)}, .5)
        self.assertTrue(score["recordings"][0]["constant_scores"])
        self.assertEqual(score["patient_macro_event_f1"], 0)


class AnnotationTests(unittest.TestCase):
    def test_source_correction(self):
        text = "File name: PN00-3.edf\nRegistration start time: 18.15.44\nSeizure start time: 18.28.29\nSeizure end time: 19.29.29"
        result = se.parse_siena_annotations(text, "PN00/PN00-3.edf", 2489)
        self.assertEqual(result["events"], [(765, 825)])
        self.assertEqual(len(result["corrections"]), 1)
        with self.assertRaises(ValueError):
            se.parse_siena_annotations(text, "PN00/PN00-3.edf", 800)

    def test_midnight_pn01_alias_and_two_events(self):
        text = "File name: PN01.edf\nRegistration start time: 23.59.00\nStart time: 23:59:10\nEnd time: 23.59.20\nStart time: 00.00.10\nEnd time: 00.00.20"
        self.assertEqual(se.parse_siena_annotations(text, "PN01/PN01-1.edf", 100)["events"], [(10, 20), (70, 80)])

    def test_pn12_repeated_registration(self):
        text = "File name: PN12-1.2.edf\nRegistration start time: 10.00.00\nSeizure start time: 10.00.10\nSeizure end time: 10.00.20\nFile name: PN12-1.2.edf\nSeizure start time: 10.01.10\nSeizure end time: 10.01.20"
        self.assertEqual(se.parse_siena_annotations(text, "PN12/PN12-1.2.edf", 100)["events"], [(10, 20), (70, 80)])

    def test_missing_does_not_mean_background(self):
        with self.assertRaises(ValueError):
            se.parse_siena_annotations("no events here", "PN01/PN01-1.edf", 100)

    def test_ambiguous_clocks_follow_pinned_final_clock(self):
        self.assertEqual(se._clock("Seizure end time: 11.41.04 oppure 11.40.43"), 42043)
        self.assertEqual(se._clock("Seizure start time: 15.43.53 clinico 15.43.59 elettrico"), 56639)


class ReferenceTests(unittest.TestCase):
    def test_complete_train_predict_score(self):
        train = manifest()
        test_public = manifest(("PN11",), "test", False)
        test_private = manifest(("PN11",), "test", True)
        artifact = reference.fit(train, signals(train))
        predicted = reference.predict(test_public, signals(test_public), artifact)
        result = se.evaluate(test_private, predicted, artifact)
        self.assertEqual(result["scientific_qualification"], "unknown")
        self.assertEqual(len(result["recordings"][0]["raw_prediction_events"]), 1)
        self.assertEqual(len(next(iter(predicted.values()))), 2000)
        self.assertEqual(artifact, reference.fit(train, signals(train)))

    def test_causal_signal_transform(self):
        x = np.arange(80, dtype=float).reshape(40, 2)
        y = x.copy()
        y[20:] *= 100
        a = reference._line_length(x, 10, [1, 1])
        b = reference._line_length(y, 10, [1, 1])
        np.testing.assert_array_equal(a[:20], b[:20])

    def test_timing_only_and_paired_comparison(self):
        train = manifest()
        public = manifest(("PN11", "PN07"), "test", False)
        private = manifest(("PN11", "PN07"), "test", True)
        neural = reference.fit(train, signals(train))
        timing = reference.fit(train, None, "timing_only_v1")
        neural_scores = reference.predict(public, signals(public), neural)
        timing_scores = reference.predict(public, None, timing)
        report = se.evaluate(private, neural_scores, neural, (timing_scores, timing))
        self.assertEqual(report["paired_comparison"]["status"], "descriptive_public_development")
        other_train = copy.deepcopy(train)
        other_train["recordings"][0]["reference_events"] = [[100, 130]]
        other_timing = reference.fit(other_train, None, "timing_only_v1")
        with self.assertRaisesRegex(ValueError, "identical training"):
            se.evaluate(private, neural_scores, neural, (timing_scores, other_timing))
        with self.assertRaises(ValueError):
            reference.predict(public, signals(public), timing)

    def test_training_patient_labels_channels_and_frozen_tamper(self):
        train = manifest()
        artifact = reference.fit(train, signals(train))
        with self.assertRaisesRegex(ValueError, "leakage"):
            reference.predict(manifest(role="test", references=False), signals(train), artifact)
        public = manifest(("PN11",), "test", False)
        private = manifest(("PN11",), "test", True)
        with self.assertRaisesRegex(ValueError, "exposed reference"):
            reference.predict(private, signals(private), artifact)
        public["recordings"][0]["channels"].reverse()
        with self.assertRaisesRegex(ValueError, "channel order"):
            reference.predict(public, signals(public), artifact)
        tampered = copy.deepcopy(artifact)
        tampered["threshold"] += 1
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            se.validate_frozen(tampered)

    def test_cli_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            train, public, private = manifest(), manifest(("PN11",), "test", False), manifest(("PN11",), "test", True)
            for name, obj in [("train", train), ("public", public), ("private", private)]:
                (root / (name + ".json")).write_text(json.dumps(obj))
                np.savez(root / (name + ".npz"), **signals(obj))
            artifact, predicted, report = str(root / "frozen.json"), str(root / "predicted.npz"), str(root / "report.json")
            reference.main(["fit", str(root / "train.json"), artifact, "--signals", str(root / "train.npz")])
            reference.main(["predict", str(root / "public.json"), predicted, "--signals", str(root / "public.npz"), "--artifact", artifact])
            se.main(["evaluate", str(root / "private.json"), predicted, artifact, report])
            self.assertEqual(json.loads(Path(report).read_text())["task_id"], se.TASK_ID)


if __name__ == "__main__":
    unittest.main()
