"""Generated controls only; no authentic arrays, programme runtime, or score."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parent


def module(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + "_program.py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


MEAN = module("training_mean")
RIDGE = module("layer4_ridge")


def fixture_roster():
    def pin(path):
        return {"path": path, "bytes": 128, "sha256": "0" * 64}
    return {
        "schema": "boldmoments-public-roster-v1",
        "subjects": list(MEAN.SUBJECTS),
        "train_video_ids": [f"vid{i:04d}" for i in range(1, 1001)],
        "query_video_ids": [f"vid{i:04d}" for i in range(1001, 1103)],
        "training_repeats": 3,
        "query_repeats": 10,
        "features": {"layer4": {s: pin(f"public/input/features/{s}_layer4.npy") for s in ("train", "test")}},
        "cases": [{"id": key, "subject": key.split("/")[0], "roi": key.split("/")[1], "voxels": voxels,
                   "coordinates": [[j, 0, 0] for j in range(voxels)],
                   "training": pin("public/input/training/" + key.replace("/", "_") + ".npy")}
                  for key, voxels in MEAN.CASES],
    }


def encoded(roster):
    raw = json.dumps(roster, separators=(",", ":")).encode()
    digest = hashlib.sha256(raw).hexdigest()
    return raw, digest, {"bytes": len(raw), "sha256": digest}


class ProgrammeControls(unittest.TestCase):
    def test_both_exact_candidate_interfaces_accept_existing_volume(self):
        roster = fixture_roster()
        raw, digest, pin = encoded(roster)
        for program in (MEAN, RIDGE):
            with self.subTest(method=program.BASELINE_METHOD), tempfile.TemporaryDirectory() as base:
                root = Path(base)
                public = root / "public"
                output = root / "output"
                public.mkdir()
                output.mkdir()
                result = {"status": "predictions_written", "cases": 80}
                with mock.patch.object(program, "ROSTER_PIN", pin), \
                     mock.patch.object(program, "capture_relative", return_value=(raw, digest)) as capture, \
                     mock.patch.object(program, "produce", return_value=result) as produce, \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(program.main(["--public-root", str(public), "--output-dir", str(output)]), result)
                self.assertEqual(capture.call_args.args[1], "input/ROSTER.json")
                self.assertEqual(produce.call_args.args[2]["cases"], roster["cases"])

    def test_method_cannot_be_selected_by_runtime_argument(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            MEAN.main(["--public-root", "/public", "--output-dir", "/output", "--method", "layer4_ridge"])

    def test_roster_pin_failure_precedes_json_deserialization(self):
        contract = types.SimpleNamespace(strict_json=mock.Mock(side_effect=AssertionError("must not parse")))
        with self.assertRaisesRegex(ValueError, "frozen public roster"):
            MEAN.admit_roster(b"{}", "0" * 64, contract)
        contract.strict_json.assert_not_called()

    def test_full_roster_rejects_missing_reordered_duplicate_and_wrong_coordinate_extent(self):
        contract, _ = MEAN.dependencies()
        changes = [
            lambda r: r["cases"].pop(),
            lambda r: r["cases"].reverse(),
            lambda r: r["cases"].__setitem__(-1, copy.deepcopy(r["cases"][0])),
            lambda r: r["cases"][-1].__setitem__("voxels", r["cases"][-1]["voxels"] - 1),
            lambda r: r["query_video_ids"].reverse(),
            lambda r: r.__setitem__("training_repeats", True),
        ]
        for change in changes:
            roster = fixture_roster()
            change(roster)
            raw, digest, pin = encoded(roster)
            with mock.patch.object(MEAN, "ROSTER_PIN", pin), self.assertRaises(ValueError):
                MEAN.admit_roster(raw, digest, contract)

    def test_embedded_source_tamper_is_rejected(self):
        with mock.patch.object(MEAN, "READOUT_SOURCE", MEAN.READOUT_SOURCE + "\n"), \
             self.assertRaisesRegex(ValueError, "embedded source changed"):
            MEAN.dependencies()

    def test_training_mean_uses_exact_constant_safe_original_arithmetic(self):
        _, readout = MEAN.dependencies()
        y = np.full((1000, 2), 0.1)
        y[:, 1] = np.arange(1000, dtype=np.float64)
        np.testing.assert_array_equal(readout.constant_safe_mean(y), np.array([0.1, 499.5]))

    def test_ridge_original_recipe_uses_training_statistics_and_fixed_lambda(self):
        _, readout = RIDGE.dependencies()
        x = np.zeros((1000, 100), dtype=np.float64)
        x[:, 0] = np.tile([-1.0, 1.0], 500)
        q = np.zeros((102, 100), dtype=np.float64)
        q[:, 0] = np.tile([-1.0, 1.0], 51)
        q[:, 1] = 1e10  # A training-constant column must stay ignored at query.
        y = (2.0 + 3.0 * x[:, 0])[:, None]
        out = readout.fixed_ridge_readout(x, q, y)
        expected = 2.0 + 3.0 * (1000.0 / 1001.0) * q[:, 0]
        np.testing.assert_allclose(out["prediction"][:, 0], expected, rtol=0, atol=1e-12)
        self.assertEqual(out["ridge_lambda"], 1.0)
        self.assertFalse(out["intercept_penalized"])
        self.assertEqual(out["support"]["constant_training_features"], 99)

    def test_full_mean_programme_emits_eighty_native_shapes_then_submission(self):
        roster = fixture_roster()
        written, loaded = [], []
        contract, _ = MEAN.dependencies()

        def load(_fd, pin, shape, _contract):
            loaded.append(pin["path"])
            self.assertTrue(pin["path"].startswith("public/input/training/"))
            return np.broadcast_to(np.full((1, shape[1]), 0.1), shape)

        def write(_fd, name, raw):
            written.append((name, len(raw), hashlib.sha256(raw).hexdigest()))
            if name == "submission.json":
                submission = json.loads(raw)
                self.assertEqual([r["id"] for r in submission["predictions"]], [c[0] for c in MEAN.CASES])
                self.assertEqual(len(written), 81)
                self.assertEqual([r["sha256"] for r in submission["predictions"]], [r[2] for r in written[:-1]])
            else:
                key, voxels = MEAN.CASES[len(written) - 1]
                self.assertEqual(name, key.replace("/", "_") + ".npy")
                a = contract.parse_npy(raw, (102, voxels))
                self.assertTrue(bool(np.all(a == 0.1)))

        # Real capture/serialization/full iteration; arithmetic was tested above.
        arithmetic = types.SimpleNamespace(constant_safe_mean=lambda a, axis: a[0].copy())
        with mock.patch.object(MEAN.os, "listdir", return_value=[]), \
             mock.patch.object(MEAN, "load_array", side_effect=load), \
             mock.patch.object(MEAN, "write_exclusive", side_effect=write):
            out = MEAN.produce(10, 11, roster, "a" * 64, contract, arithmetic)
        self.assertEqual(len(loaded), 80)
        self.assertEqual(len(set(loaded)), 80)
        self.assertEqual(out["cases"], 80)
        self.assertLess(sum(r[1] for r in written), MEAN.MAX_OUTPUT_BYTES)

    def test_ridge_route_has_one_fixed_feature_pair_and_all_eighty_training_panels(self):
        roster = fixture_roster()
        seen, calls, writes = [], [], []

        def load(_fd, pin, shape, _contract):
            seen.append((pin["path"], shape))
            return np.broadcast_to(np.zeros((1, shape[1])), shape)

        def ridge(x, q, y):
            calls.append((x.shape, q.shape, y.shape))
            return {"prediction": np.zeros((102, y.shape[1]))}

        with mock.patch.object(RIDGE.os, "listdir", return_value=[]), \
             mock.patch.object(RIDGE, "load_array", side_effect=load), \
             mock.patch.object(RIDGE, "write_exclusive", side_effect=lambda _fd, name, raw: writes.append(name)):
            RIDGE.produce(10, 11, roster, "a" * 64, None, types.SimpleNamespace(fixed_ridge_readout=ridge))
        self.assertEqual(seen[:2], [("public/input/features/train_layer4.npy", (1000, 100)),
                                  ("public/input/features/test_layer4.npy", (102, 100))])
        self.assertEqual(len(seen), 82)
        self.assertEqual(len(calls), 80)
        self.assertEqual(writes[-1], "submission.json")

    def test_partial_failure_preserves_outputs_without_final_submission(self):
        writes = []
        calls = 0

        def load(_fd, _pin, shape, _contract):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ValueError("next frozen input failed authentication")
            return np.broadcast_to(np.zeros((1, shape[1])), shape)

        with mock.patch.object(MEAN.os, "listdir", return_value=[]), \
             mock.patch.object(MEAN, "load_array", side_effect=load), \
             mock.patch.object(MEAN, "write_exclusive", side_effect=lambda _fd, name, raw: writes.append(name)), \
             self.assertRaisesRegex(ValueError, "failed authentication"):
            MEAN.produce(10, 11, fixture_roster(), "a" * 64, None,
                         types.SimpleNamespace(constant_safe_mean=lambda a, axis: a[0]))
        self.assertEqual(writes, [MEAN.CASES[0][0].replace("/", "_") + ".npy"])

    def test_nonempty_output_refused_before_input_array_load(self):
        with mock.patch.object(MEAN.os, "listdir", return_value=["old.npy"]), \
             mock.patch.object(MEAN, "load_array") as load, \
             self.assertRaisesRegex(ValueError, "start empty"):
            MEAN.produce(10, 11, fixture_roster(), "a" * 64, None, None)
        load.assert_not_called()

    def test_capture_rejects_directory_and_leaf_symlinks(self):
        contract, _ = MEAN.dependencies()
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            actual = root / "actual"
            actual.mkdir()
            (actual / "file").write_bytes(b"safe")
            (root / "alias").symlink_to(actual, target_is_directory=True)
            (root / "leaf").symlink_to(actual / "file")
            fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                for path in ("alias/file", "leaf"):
                    with self.assertRaises(OSError):
                        MEAN.capture_relative(fd, path, 100, contract)
                raw, _ = MEAN.capture_relative(fd, "actual/file", 100, contract)
                self.assertEqual(raw, b"safe")
            finally:
                os.close(fd)

    def test_input_pin_mismatch_precedes_numeric_parser_and_private_path_refused(self):
        contract = types.SimpleNamespace(parse_npy=mock.Mock(side_effect=AssertionError("no parse")))
        pin = {"path": "public/input/training/x.npy", "bytes": 3, "sha256": "0" * 64}
        with mock.patch.object(MEAN, "capture_relative", return_value=(b"abc", "1" * 64)), \
             self.assertRaisesRegex(ValueError, "frozen descriptor"):
            MEAN.load_array(10, pin, (1000, 1), contract)
        contract.parse_npy.assert_not_called()
        pin["path"] = "private/targets/x.npy"
        with mock.patch.object(MEAN, "capture_relative") as capture, \
             self.assertRaisesRegex(ValueError, "public input only"):
            MEAN.load_array(10, pin, (1000, 1), contract)
        capture.assert_not_called()

    def test_writer_never_replaces_or_follows_an_existing_leaf(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                MEAN.write_exclusive(fd, "prediction.npy", b"first")
                with self.assertRaises(FileExistsError):
                    MEAN.write_exclusive(fd, "prediction.npy", b"second")
                self.assertEqual((root / "prediction.npy").read_bytes(), b"first")
            finally:
                os.close(fd)

    def test_nonfinite_or_incomplete_prediction_cannot_be_serialized(self):
        for array in (np.full((102, 1), np.nan), np.zeros((101, 1)), np.zeros((102, 1), dtype=object)):
            with self.assertRaises(ValueError):
                MEAN.serialize_prediction(array, (102, 1))


if __name__ == "__main__":
    unittest.main()
