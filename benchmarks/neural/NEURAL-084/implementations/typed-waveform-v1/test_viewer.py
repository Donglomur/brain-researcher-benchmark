"""Generated software controls, with no OpenBMI recordings or model runs."""
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("neural084_waveform_viewer", HERE / "viewer.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
SOURCE_ROOT = Path(os.environ.get("NEURAL084_SOURCE_IMPLEMENTATIONS", str(HERE.parent)))
NS = {"s": "http://www.w3.org/2000/svg"}
CHANNELS = ("P7", "P3", "Pz", "P4", "P8", "PO9", "PO10", "O1", "Oz", "O2")


def metadata(held=1):
    rows = []
    for person in range(1, 55):
        if person == held:
            continue
        for session in (1, 2):
            for phase in ("train", "test"):
                for label in (1, 2, 3, 4):
                    for _ in range(25):
                        rows.append({"id": f"{100000 + len(rows):064x}", "label": label,
                                     "person": person, "session": session, "phase": phase})
    desc = lambda path: {"path": path, "bytes": 1, "sha256": "f" * 64}
    fold = {"schema": "neural084_fold_v1", "generation": "generated-software-fixture-only",
            "fold": f"fold{held:03d}", "ids": [f"{i:064x}" for i in range(400)],
            "classes": [1, 2, 3, 4], "training": desc("training.npy"),
            "queries": desc("queries.npy"), "training_metadata": desc("training.json")}
    return fold, {"schema": "neural084_training_v1", "rows": rows}


def epoch(index=0):
    # Deterministic integers, not invented physiological observations.
    return [[(sample % 17) - 8 + channel for sample in range(400)] for channel in range(10)]


class ViewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fold, cls.training = metadata()

    def make(self, *, fold=None, training=None, training_provider=epoch, query_provider=epoch):
        return v.FoldViewer(fold or self.fold, training or self.training,
                            training_provider, query_provider, source_root=SOURCE_ROOT)

    def call(self, viewer, action, **fields):
        return json.loads(viewer.handle(json.dumps({"action": action, **fields}).encode()))

    def begin(self, viewer):
        return self.call(viewer, "begin_queries")["id"]

    def view(self, viewer, identity, **extra):
        fields = {"id": identity, "channels": list(CHANNELS), "start": 0, "stop": 400}
        fields.update(extra)
        return self.call(viewer, "view", **fields)

    def test_complete_trace_geometry_and_no_query_metadata(self):
        viewer = self.make()
        identity = self.begin(viewer)
        result = self.view(viewer, identity)
        self.assertEqual(set(result), {"stage", "id", "kind", "svg", "channels", "start", "stop"})
        root = ET.fromstring(result["svg"])
        paths = root.findall("s:polyline", NS)
        self.assertEqual([x.attrib["data-channel"] for x in paths], list(CHANNELS))
        self.assertEqual([len(x.attrib["points"].split()) for x in paths], [400] * 10)
        # Independent geometry from known generated values: global max is17.
        first = [float(x) for x in paths[0].attrib["points"].split()[0].split(",")]
        last = [float(x) for x in paths[0].attrib["points"].split()[-1].split(",")]
        self.assertEqual(first[0], 112)
        self.assertEqual(last[0], 980)
        self.assertAlmostEqual(first[1], 119 + 34 * 8 / 17, places=8)
        self.assertIn("0.0045 to 3.9945 s", result["svg"])
        self.assertNotIn("label", result)

    def test_crop_preserves_samples_and_full_epoch_scale(self):
        viewer = self.make()
        identity = self.begin(viewer)
        full = ET.fromstring(self.view(viewer, identity)["svg"]).findall("s:polyline", NS)
        crop = self.view(viewer, identity, channels=["Oz"], start=388, stop=400)
        path = ET.fromstring(crop["svg"]).find("s:polyline", NS)
        cropped = path.attrib["points"].split()
        original = full[8].attrib["points"].split()[388:400]
        for cropped_point, original_point in zip(cropped, original):
            self.assertAlmostEqual(float(cropped_point.split(",")[1]),
                                   float(original_point.split(",")[1]) - 86 * 8, places=8)
        self.assertEqual(len(cropped), 12)
        self.assertIn("3.8845 to 3.9945 s", crop["svg"])

    def test_all_training_rows_accessible_then_retired(self):
        requested = []
        viewer = self.make(training_provider=lambda i: requested.append(i) or epoch())
        for index in (0, 21199):
            result = self.call(viewer, "training", index=index, channels=["P7"], start=0, stop=2)
            self.assertEqual(result["row"], self.training["rows"][index])
        self.assertEqual(requested, [0, 21199])
        self.begin(viewer)
        with self.assertRaisesRegex(ValueError, "retired"):
            self.call(viewer, "training", index=0, channels=["P7"], start=0, stop=2)
        self.assertIsNone(viewer._training)
        self.assertIsNone(viewer._training_epoch)

    def test_complete_400_output_accepted_by_existing_contract(self):
        viewer = self.make(query_provider=lambda i: self.fail("answers need not invoke a numerical decoder"))
        current = self.begin(viewer)
        for i, identity in enumerate(self.fold["ids"]):
            self.assertEqual(current, identity)
            response = self.call(viewer, "answer", id=identity, scores=[-2.5, 0, 4.25, 1])
            self.assertEqual(response["answered"], i + 1)
            current = response.get("next_id")
        raw = viewer.handle(b'{"action":"finish"}')
        existing = viewer._contracts.prediction(raw, self.fold)
        self.assertEqual(len(existing["predictions"]), 400)
        self.assertEqual(existing["predictions"][-1]["scores"], [-2.5, 0, 4.25, 1])
        self.assertLess(len(raw), 262144)
        with self.assertRaisesRegex(ValueError, "closed"):
            viewer.handle(b'{"action":"finish"}')

    def test_incomplete_and_duplicate_answer_refused(self):
        viewer = self.make()
        first = self.begin(viewer)
        with self.assertRaisesRegex(ValueError, "400"):
            self.call(viewer, "finish")
        self.call(viewer, "answer", id=first, scores=[0, 0, 0, 0])
        with self.assertRaisesRegex(ValueError, "first-final"):
            self.call(viewer, "answer", id=first, scores=[1, 0, 0, 0])
        self.assertEqual(viewer._query_index, 1)
        self.assertEqual(viewer._answers[0]["scores"], [0, 0, 0, 0])

    def test_query_before_training_transition_and_future_query_refused(self):
        viewer = self.make()
        with self.assertRaisesRegex(ValueError, "unanswered"):
            self.view(viewer, self.fold["ids"][0])
        self.begin(viewer)
        with self.assertRaisesRegex(ValueError, "current opaque"):
            self.view(viewer, self.fold["ids"][1])
        with self.assertRaisesRegex(ValueError, "one training"):
            self.begin(viewer)

    def test_strict_request_and_channel_window_rejections(self):
        viewer = self.make()
        identity = self.begin(viewer)
        bad = [b'{"action":"information","action":"finish"}',
               b'{"action":"information","code":"print(1)"}',
               b'{"action":"read_file","path":"/private/gold.json"}',
               b' ' * 4097]
        for raw in bad:
            with self.subTest(raw=raw[:60]), self.assertRaises(ValueError):
                viewer.handle(raw)
        for fields in ({"channels": ["Oz", "P7"]}, {"channels": ["P7", "P7"]},
                       {"channels": ["EOG"]}, {"start": True}, {"stop": 401},
                       {"start": 399, "stop": 400}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.view(viewer, identity, **fields)

    def test_nonfinite_bool_scores_and_epoch_rejected(self):
        viewer = self.make()
        identity = self.begin(viewer)
        for scores in ([True, 0, 0, 0], [1, 2, 3], [math.inf, 0, 0, 0]):
            with self.subTest(scores=scores), self.assertRaises(ValueError):
                self.call(viewer, "answer", id=identity, scores=scores)
        for bad_sample in (True, float("nan"), float("inf"), v.FLOAT32_MAX * 2):
            bad = epoch(); bad[0][0] = bad_sample
            candidate = self.make(query_provider=lambda _: bad)
            with self.subTest(sample=str(bad_sample)), self.assertRaises(ValueError):
                self.view(candidate, self.begin(candidate))

    def test_provider_snapshot_and_training_consistency(self):
        original = epoch()
        calls = []
        viewer = self.make(query_provider=lambda index: calls.append(index) or original,
                           training_provider=lambda _: original)
        self.call(viewer, "training", index=0, channels=["P7"], start=0, stop=2)
        original[0][0] += 1
        with self.assertRaisesRegex(ValueError, "changed"):
            self.call(viewer, "training", index=0, channels=["P7"], start=0, stop=2)
        identity = self.begin(viewer)
        first = self.view(viewer, identity)
        original[0][0] += 100
        second = self.view(viewer, identity)
        self.assertEqual(first, second)
        self.assertEqual(calls, [0])

    def test_fold_and_training_support_malformed_before_provider_access(self):
        bad_training = copy.deepcopy(self.training)
        bad_training["rows"][0]["person"] = 1
        with self.assertRaises(ValueError):
            self.make(training=bad_training, training_provider=lambda _: self.fail("must validate metadata first"))
        for mutate in (lambda f: f["ids"].pop(), lambda f: f["ids"].reverse(),
                       lambda f: f.update(classes=[1, 2, 3, True]),
                       lambda f: f.update(gold={"path": "gold.json"}),
                       lambda f: f.update(fold="fold055")):
            fold = copy.deepcopy(self.fold); mutate(fold)
            with self.subTest(fold_keys=list(fold)), self.assertRaises(ValueError):
                self.make(fold=fold)

    def test_declared_budget_is_per_epoch_and_zero_epoch_has_finite_geometry(self):
        viewer = self.make(query_provider=lambda _: [[0] * 400 for _ in range(10)])
        identity = self.begin(viewer)
        for _ in range(128):
            result = self.view(viewer, identity, channels=["P7"], start=0, stop=2)
        with self.assertRaisesRegex(ValueError, "budget"):
            self.view(viewer, identity, channels=["P7"], start=0, stop=2)
        self.assertNotIn("nan", result["svg"].lower())
        self.assertNotIn("inf", result["svg"].lower())
        following = self.call(viewer, "answer", id=identity, scores=[0, 0, 0, 0])["next_id"]
        self.view(viewer, following, channels=["P7"], start=0, stop=2)

    def test_last_held_person_information_matches_public_contract(self):
        fold, training = metadata(54)
        viewer = self.make(fold=fold, training=training)
        info = self.call(viewer, "information")
        self.assertEqual(info["fold"], "fold054")
        self.assertEqual(info["frequencies_hz"], [60 / n for n in (5, 7, 9, 11)])
        self.assertEqual(info["directions"], ["up", "left", "right", "down"])
        self.assertEqual(info["training_rows"], 21200)
        self.assertEqual(info["physical_amplitude_unit"], "unverified")


if __name__ == "__main__":
    unittest.main()
