"""Small generated controls; optional exact pinned-author source differential."""
import argparse
import ast
import copy
import hashlib
import io
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np
import scipy
from scipy.io import savemat

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import source_preparation as p

AUTHOR_SOURCE = None
MEMBER = "S01/OfflineImagery/S01_OfflineImagery_R01.mat"


def fixture(repeats=2):
    rng = np.random.default_rng(17)
    labels = [1, 2, 3, 4, 4, 3, 2, 1]
    lengths = [1024, 1280, 1152, 1536, 1280, 1024, 1152, 1408]
    labels, lengths = labels[:4 * repeats], lengths[:4 * repeats]
    data = rng.normal(size=(128, sum(lengths)))
    events, offset = [], 0
    for label, length in zip(labels, lengths):
        events += [{"type": "Target", "sample": float(offset + 1), "value": float(label)},
                   {"type": "TrialEnd", "sample": float(offset + length + 1), "value": 0.0}]
        offset += length
    return data, events, {str(c): repeats for c in (1, 2, 3, 4)}


def trials():
    data, events, counts = fixture()
    return p.extract_trials(data, 1024.0, events, p.parse_member(MEMBER), counts)


def write_mat(path, *, outputs=1, repeats=2):
    data, events, _ = fixture(repeats=repeats)
    array = np.empty((1, len(events)), dtype=[("type", "O"), ("sample", "O"), ("value", "O")])
    for i, event in enumerate(events):
        array[0, i] = (event["type"], event["sample"], event["value"])
    savemat(path, {"eeg": {"data": data, "fsample": 1024.0, "nChans": 128.0,
                          "nSamples": float(data.shape[1]), "prediction": outputs,
                          "prob_thumb": outputs, "prob_pinky": outputs}, "event": array})
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PreparationTests(unittest.TestCase):
    def test_original_middle_finger_is_counted_then_excluded(self):
        raw = trials()
        self.assertEqual([t.source_label for t in raw], [1, 2, 3, 4, 4, 3, 2, 1])
        result = p.prepare_training(raw, [1, 4], [2, 0, 3, 1], subject="S01", condition="MI",
                                    session=1, model_type="Orig")
        self.assertEqual(result["excluded_source_class_counts"], {"2": 2, "3": 2})
        self.assertEqual(len(result["training"]["trial_ids"]), 3)
        self.assertEqual(len(result["validation"]["trial_ids"]), 1)
        self.assertEqual(result["training"]["eeg"].shape[1:], (128, 100, 1))
        self.assertEqual(set(result["training"]["labels_zero_based"]), {0, 1})
        self.assertFalse(set(result["training"]["trial_ids"]) & set(result["validation"]["trial_ids"]))

    def test_independent_sample_boundary_car_and_offset_order(self):
        raw = trials()
        data, _, _ = fixture()
        self.assertEqual(raw[1].start_sample_zero_based, 1024)
        self.assertEqual(raw[1].end_sample_exclusive, 2304)
        np.testing.assert_allclose(raw[1].eeg[:, 0], data[:, 1024] - data[:, 1024].mean())
        packet = p.segment_trials([raw[0], raw[1]], [1, 2, 4])
        self.assertEqual([w["offset_samples"] for w in packet["windows"]], [0, 0, 128, 256])
        self.assertEqual([w["trial_id"] for w in packet["windows"]], [raw[0].id, raw[1].id, raw[1].id, raw[1].id])
        np.testing.assert_allclose(packet["eeg"].mean(axis=2), 0, atol=1e-12)
        np.testing.assert_allclose(packet["eeg"].std(axis=2), 1, atol=1e-12)

    def test_frozen_split_validation_uses_original_sorted_indices(self):
        result = p.prepare_training(trials(), [1, 2, 4], [4, 1, 5, 2, 3, 0], subject="S01",
                                    condition="MI", session=1, model_type="Orig")
        selected = [t for t in trials() if t.source_label != 3]
        self.assertEqual(result["validation"]["trial_ids"], [selected[0].id, selected[3].id])
        for permutation in ([0] * 6, [0, 1, 2], [0, 1, 2, 3, 4, True]):
            with self.assertRaisesRegex(ValueError, "permutation"):
                p.prepare_training(trials(), [1, 2, 4], permutation, subject="S01",
                                   condition="MI", session=1, model_type="Orig")

    def test_raw_class_roster_and_event_failures_are_not_silent(self):
        data, events, counts = fixture()
        for modify in (lambda e: e.pop(), lambda e: e[0].update(value=5),
                       lambda e: e[0].update(sample=1.5), lambda e: e[1].update(sample=500),
                       lambda e: e[1].update(type="Target")):
            bad = copy.deepcopy(events)
            modify(bad)
            with self.assertRaises(ValueError):
                p.extract_trials(data, 1024, bad, p.parse_member(MEMBER), counts)
        with self.assertRaisesRegex(ValueError, "middle finger"):
            p.extract_trials(data, 1024, events, p.parse_member(MEMBER), {"1": 2, "2": 2, "4": 2})
        data[0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "finite"):
            p.extract_trials(data, 1024, events, p.parse_member(MEMBER), counts)
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            p.source_transform(np.zeros((1, 128, 1024)))

    def test_identity_chronology_and_calibration_routes(self):
        for member in ("../" + MEMBER, MEMBER.replace("S01_", "S02_"),
                       "S07/OnlineImagery_Sess05_3class_Base/S07_OnlineImagery_Sess05_3class_Base_R01.mat"):
            with self.assertRaises(ValueError):
                p.parse_member(member)
        raw = trials()
        with self.assertRaisesRegex(ValueError, "participant"):
            p.prepare_training(raw, [1, 4], [0, 1, 2, 3], subject="S02", condition="MI", session=1, model_type="Orig")
        with self.assertRaisesRegex(ValueError, "order"):
            p.prepare_training(raw[::-1], [1, 4], [0, 1, 2, 3], subject="S01", condition="MI", session=1, model_type="Orig")
        with self.assertRaisesRegex(ValueError, "Base"):
            p.prepare_training(raw, [1, 4], [0, 1, 2, 3], subject="S01", condition="MI", session=1, model_type="Finetune")

    def test_safe_mat_structure_content_pin_and_online_output_invariance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "original.mat"
            sha = write_mat(path)
            first = p.read_mat(path, MEMBER, sha, {str(c): 2 for c in (1, 2, 3, 4)})
            sha2 = write_mat(path, outputs=98765)
            second = p.read_mat(path, MEMBER, sha2, {str(c): 2 for c in (1, 2, 3, 4)})
            for before, after in zip(first, second):
                np.testing.assert_array_equal(before.eeg, after.eeg)
                self.assertEqual(before.source_label, after.source_label)
            with self.assertRaisesRegex(ValueError, "checksum"):
                p.read_mat(path, MEMBER, "0" * 64, {str(c): 2 for c in (1, 2, 3, 4)})


class PinnedAuthorDifferential(unittest.TestCase):
    def test_original_mat_loader_segmentation_split_and_filtering(self):
        if not AUTHOR_SOURCE:
            self.skipTest("pass --author-source for frozen-source differential")
        source = Path(AUTHOR_SOURCE).read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(), "53dbd4f587673b562d3558fbf5f85307e0e78ed45a64a298c10d24ad8149a223")
        # Execute original non-model helpers and the literal train_models prefix
        # ending immediately before the first EEGNet/model-related assignment.
        tree = ast.parse(source)
        functions = []
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in (
                    "segment_data", "filter_and_relabel", "load_and_filter_data", "train_models"):
                if node.name == "train_models":
                    cut = next(i for i, stmt in enumerate(node.body) if isinstance(stmt, ast.Assign)
                               and ast.unparse(stmt.targets[0]) == "(kernels, chans, samples)")
                    node.body = node.body[:cut] + [ast.parse("return X_train, X_validate, Y_train, Y_validate").body[0]]
                functions.append(node)
        scope = {"np": np, "scipy": scipy, "resample": scipy.signal.resample, "os": os,
                 "K": types.SimpleNamespace(set_image_data_format=lambda _: None)}
        exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])),
                     "pinned-author-pre-model-prefix", "exec"), scope)
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "run.mat"
            sha = write_mat(file, repeats=1)
            raw = p.read_mat(file, MEMBER, sha, {str(c): 1 for c in (1, 2, 3, 4)})
            for classes, permutation in (([1, 4], [1, 0]), ([1, 2, 4], [2, 0, 1])):
                params = {"nclass": len(classes), "maxtriallen": 5, "windowlen": 1,
                          "downsrate": 100, "bandpass_filt": [4, 40]}
                with patch("sys.stdout", io.StringIO()):
                    original, labels, params = scope["load_and_filter_data"]([directory], params)
                    with patch.object(np.random, "permutation", return_value=np.array(permutation)):
                        xtrain, xval, ytrain, yval = scope["train_models"](original, labels, "unused", params)
                actual = p.prepare_training(raw, classes, permutation, subject="S01", condition="MI",
                                            session=1, model_type="Orig")
                for role, x, y in (("training", xtrain, ytrain), ("validation", xval, yval)):
                    np.testing.assert_allclose(actual[role]["eeg"][..., 0], x, rtol=1e-12, atol=1e-12)
                    np.testing.assert_array_equal(actual[role]["labels_zero_based"], y - 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--author-source")
    args, remaining = parser.parse_known_args()
    AUTHOR_SOURCE = args.author_source
    print(f"Python {sys.version.split()[0]}; NumPy {np.__version__}; SciPy {scipy.__version__}")
    unittest.main(argv=[sys.argv[0]] + remaining)
