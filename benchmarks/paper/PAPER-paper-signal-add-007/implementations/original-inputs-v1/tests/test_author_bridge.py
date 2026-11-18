"""Generated controls of the real author bridge; no author model or data run."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import sys
import types
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import author_bridge as bridge
import predictions
from source import InputError


def binding():
    return {"schema": "icnet-author-probability-bridge-binding/v1",
            "author_revision": bridge.AUTHOR_REVISION,
            "author_functions_sha256": bridge.AUTHOR_FUNCTIONS_SHA256,
            "checkpoint_sha256": "a" * 64,
            "context_alignment_evidence_sha256": "b" * 64,
            "measurement_time_mapping_evidence_sha256": "c" * 64}


def request():
    audio = np.full(bridge.AUDIO_SAMPLES, 0.25, dtype=np.float32)
    cfs = np.full(bridge.UNITS, 900.0, dtype=np.float64)
    cfs[0] = -np.inf
    audio.flags.writeable = False
    cfs.flags.writeable = False
    return {"animal": 3, "sound": "music", "trial": 1, "audio_pa": audio,
            "fs_audio": bridge.FS_AUDIO, "fs_neural": bridge.FS_NEURAL,
            "time_bins": bridge.TIME_BINS, "measurement_time_seconds": 7200.0,
            "characteristic_frequencies_hz": cfs,
            "unit_ids": tuple(f"animal_3:original_column_{i}" for i in range(bridge.UNITS)),
            "maximum_block_bins": 1024}


class FakeBranch:
    def __init__(self):
        self.calls = []
        values = np.zeros((1, 1, bridge.UNITS, bridge.COUNT_CLASSES), dtype=np.float32)
        values[0, 0, np.arange(bridge.UNITS), np.arange(bridge.UNITS) % 5] = 1
        self.result = np.broadcast_to(values, (1, bridge.TIME_BINS, bridge.UNITS, 5))

    def predict(self, inputs, *, verbose):
        self.calls.append((inputs, verbose))
        return self.result


class BridgeControls(unittest.TestCase):
    def setUp(self):
        self.raw = FakeBranch()
        self.factory_calls = []
        self.context_calls = []
        self.model = types.SimpleNamespace(
            input=["audio", [f"time{i}" for i in range(9)]],
            layers=[types.SimpleNamespace(output=f"decoder{i}") for i in range(9)])
        self.previous = np.full(2048, -0.5, dtype=np.float32)
        self.context_mutator = lambda value: value

        def provider(identity):
            self.context_calls.append(identity)
            result = {"identity": dict(identity), "left_context_pa": self.previous,
                      "samples_sha256": hashlib.sha256(self.previous.astype("<f4").tobytes()).hexdigest(),
                      "alignment_evidence_sha256": "b" * 64}
            return self.context_mutator(result)

        def factory(inputs, output):
            self.factory_calls.append((inputs, output))
            return self.raw

        self.predict = bridge.AuthorProbabilityBridge(self.model, provider, binding(), branch_factory=factory)

    def test_full_original_support_original_columns_and_existing_probability_conversion(self):
        req = request()
        rows = list(self.predict(req))
        self.assertEqual(len(rows), 23)
        self.assertEqual(sum(row["probabilities"].shape[0] for row in rows), 22784)
        self.assertEqual([row["start_bin"] for row in rows], list(range(0, 22784, 1024)))
        self.assertTrue(all(row["column_indices"] == list(range(512)) for row in rows))
        self.assertEqual(self.factory_calls, [(["audio", "time2"], "decoder2")])
        draws, means = predictions.convert_block(rows[0]["probabilities"][:2],
                                                  rows[0]["column_indices"], np.random.default_rng(1))
        expected = np.broadcast_to(np.arange(512) % 5, (2, 512))
        np.testing.assert_array_equal(draws, expected)
        np.testing.assert_array_equal(means, expected)
        waveform, clock = self.raw.calls[0][0]
        self.assertEqual(waveform.shape, (1, 729088 + 2048, 1))
        np.testing.assert_allclose(waveform[0, :2048, 0], -0.02)
        np.testing.assert_allclose(waveform[0, 2048:, 0], 0.01)
        self.assertTrue(np.all(req["audio_pa"] == 0.25))
        self.assertTrue(np.all(self.previous == -0.5))
        self.assertEqual(clock.shape, (1, 22784, 1))
        self.assertAlmostEqual(float(clock[0, 0, 0]), 7200 / 36000, places=7)
        self.assertAlmostEqual(float(clock[0, -1, 0]),
                               (7200 + 22783 / bridge.FS_NEURAL) / 36000, places=7)

    def test_trial_specific_seconds_and_context_requests_are_not_reused(self):
        req = request()
        list(self.predict(req))
        later = dict(req, trial=2, measurement_time_seconds=10800.0)
        list(self.predict(later))
        self.assertEqual(len(self.context_calls), 2)
        self.assertEqual([x["trial"] for x in self.context_calls], [1, 2])
        self.assertEqual(len(self.factory_calls), 1)
        first, second = [row[0][1][0, 0, 0] for row in self.raw.calls]
        self.assertAlmostEqual(float(second - first), 0.1, places=7)

    def test_missing_or_mismatched_context_fails_before_model(self):
        for mutator in (
            lambda x: None,
            lambda x: dict(x, identity=dict(x["identity"], trial=2)),
            lambda x: dict(x, alignment_evidence_sha256="d" * 64),
            lambda x: dict(x, samples_sha256="0" * 64),
            lambda x: dict(x, left_context_pa=np.zeros(2047, dtype=np.float32)),
            lambda x: dict(x, left_context_pa=np.full(2048, np.nan, dtype=np.float32)),
        ):
            with self.subTest(mutator=mutator):
                self.context_mutator = mutator
                with self.assertRaises(InputError):
                    list(self.predict(request()))
        self.assertEqual(self.factory_calls, [])
        self.assertEqual(self.raw.calls, [])

    def test_binding_is_mandatory_and_source_specific(self):
        for key, value in (("author_revision", "0" * 40), ("checkpoint_sha256", None),
                           ("measurement_time_mapping_evidence_sha256", "")):
            with self.subTest(key=key):
                b = binding()
                b[key] = value
                with self.assertRaises(InputError):
                    bridge.AuthorProbabilityBridge(self.model, lambda x: x, b)
        with self.assertRaises(InputError):
            bridge.AuthorProbabilityBridge(self.model, None, binding())

    def test_foreign_or_partial_request_fails_before_context(self):
        for key, value in (("animal", 1), ("trial", True), ("time_bins", 1),
                           ("measurement_time_seconds", float("inf")),
                           ("unit_ids", tuple(reversed(request()["unit_ids"]))),
                           ("maximum_block_bins", 1025)):
            with self.subTest(key=key):
                r = request()
                r[key] = value
                with self.assertRaises(InputError):
                    list(self.predict(r))
        self.assertEqual(self.context_calls, [])

    def test_wrong_model_layout_and_sample_only_output_are_refused(self):
        self.model.input[1] = ["one"]
        with self.assertRaises(InputError):
            list(self.predict(request()))
        self.model.input[1] = [f"time{i}" for i in range(9)]
        self.raw.result = np.zeros((1, 22784, 512), dtype=np.int8)
        with self.assertRaises(InputError):
            list(self.predict(request()))

    def test_invalid_distribution_is_rejected_by_existing_stream_boundary(self):
        self.raw.result = np.broadcast_to(np.array([2, 0, 0, 0, 0], dtype=np.float32),
                                         (1, 22784, 512, 5))
        row = next(self.predict(request()))
        with self.assertRaises(InputError):
            predictions.convert_block(row["probabilities"], row["column_indices"], np.random.default_rng(1))


if __name__ == "__main__":
    unittest.main()
