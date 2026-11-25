"""Generated software controls only; no biological data or author fit."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("rastermap_figure1_scorer", ROOT / "scorer.py")
scorer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = scorer
SPEC.loader.exec_module(scorer)


def generated_truth(counts=(12, 12, 12, 12, 24)):
    return np.concatenate([k + np.linspace(.01, .99, n) for k, n in enumerate(counts)])


class FixedPairs:
    def choice(self, n, size, replace):
        assert size == 2 and replace is False
        return np.array([0, n - 1])


class MetricTests(unittest.TestCase):
    def test_correct_order_and_reversal(self):
        truth = generated_truth()
        for emb in (truth, -truth):
            scores, counts = scorer.source_benchmarks(truth, [emb], np.random.RandomState(71))
            np.testing.assert_array_equal(scores[0, 0], np.zeros(5))
            np.testing.assert_array_equal(scores[1, 0], np.ones(5))
            self.assertTrue((counts > 0).all())

    def test_contamination_preserves_unusual_upper_exclusion(self):
        # Module 0 endpoints at positions 0 and 6. Slice [1:5] has two outsiders;
        # the conventional interior [1:6] has three. Exact source result is 1/2.
        truth = np.array([.1, 1.1, .2, .3, 1.2, 1.3, .4, 1.4])
        value, count = scorer.embedding_contamination(truth, np.arange(8), FixedPairs())
        self.assertEqual(value[0], .5)
        self.assertEqual(count[0], 40)

    def test_qualifying_rule_and_no_redraw(self):
        truth = np.array([.1, .2, .3, 1.1, 1.2, 1.3])
        score, count = scorer.embedding_contamination(truth, np.arange(6), FixedPairs())
        self.assertTrue(np.isnan(score).all())
        np.testing.assert_array_equal(count, [0, 0])

    def test_interleaving_breaks_continuity_but_not_within_module_order(self):
        truth = generated_truth((12,) * 5)
        embedded = np.tile(np.arange(12), 5) * 5 + np.repeat(np.arange(5), 12)
        scores, _ = scorer.source_benchmarks(truth, [embedded], np.random.RandomState(2))
        np.testing.assert_array_equal(scores[1, 0], np.ones(5))
        self.assertTrue((scores[0, 0] > .7).all())

    def test_invalid_embeddings_and_ground_truth_rejected(self):
        truth = generated_truth()
        for emb in (np.zeros((len(truth), 2)), truth[:-1], truth.astype(complex), np.full(len(truth), np.nan)):
            with self.assertRaises(ValueError):
                scorer.source_benchmarks(truth, [emb], np.random.RandomState(2))
        with self.assertRaises(ValueError):
            scorer.source_benchmarks(truth, [truth], np.random.default_rng(2))
        with self.assertRaises(ValueError):
            scorer.validate_original_population(truth)
        scorer.validate_original_population(generated_truth(scorer.MODULE_COUNTS))

    def test_sem_uses_simulation_units_and_percentages(self):
        scores = np.broadcast_to(np.arange(10)[:, None, None, None] / 10, (10, 2, 3, 5)).copy()
        report = scorer.summarize_panel(scores, range(10))
        np.testing.assert_allclose(report["mean_percent"], 45)
        np.testing.assert_allclose(report["sem_percent"], np.std(np.arange(0, 100, 10), ddof=1) / np.sqrt(10))
        for ids in (range(9), [0] * 10, reversed(range(10)), [False] + list(range(1, 10))):
            with self.assertRaises(ValueError):
                scorer.summarize_panel(scores, ids)
        scores[0, 0, 0, 0] = np.nan
        with self.assertRaises(ValueError):
            scorer.summarize_panel(scores, range(10))


class PacketTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)

    def packet(self, name, **arrays):
        path = self.path / name
        np.savez(path, **arrays)
        return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def request(self):
        gt = generated_truth(scorer.MODULE_COUNTS)
        ids = np.arange(6000)
        target = self.packet("target.npz", xi_all=gt, neuron_id=ids)
        author = self.packet("author.npz", embedding=gt, neuron_id=ids)
        candidate = self.packet("candidate.npz", embedding=-gt, neuron_id=ids)
        return {"schema": "rastermap-figure1-score/v1", "method_names": ["source_rastermap", "candidate"],
                "realizations": [{"id": i, "metric_seed": 91 + i, "activity_sha256": f"{i:064x}",
                                  "target": target, "embeddings": {"source_rastermap": author, "candidate": candidate}}
                                 for i in range(10)]}

    def test_authentication_order_identity_and_unexpected_keys(self):
        ids = np.arange(6000)
        packet = self.packet("valid.npz", embedding=np.zeros(6000), neuron_id=ids)
        scorer._load_artifact(packet, {"embedding", "neuron_id"})
        with self.assertRaises(ValueError):
            scorer._load_artifact(dict(packet, sha256="0" * 64), {"embedding", "neuron_id"})
        for name, badids in (("duplicate", np.zeros(6000, dtype=int)), ("reversed", ids[::-1]), ("floats", ids.astype(float))):
            invalid = self.packet(name + ".npz", embedding=np.zeros(6000), neuron_id=badids)
            with self.assertRaises(ValueError):
                scorer._load_artifact(invalid, {"embedding", "neuron_id"})
        invalid = self.packet("leak.npz", embedding=np.zeros(6000), neuron_id=ids, xi_all=np.zeros(6000))
        with self.assertRaises(ValueError):
            scorer._load_artifact(invalid, {"embedding", "neuron_id"})

    def test_complete_roster_preflight_before_scoring(self):
        request = self.request()
        request["realizations"][-1]["embeddings"].pop("candidate")
        with mock.patch.object(scorer, "source_benchmarks") as metric:
            with self.assertRaises(ValueError):
                scorer.evaluate_request(request)
            metric.assert_not_called()

    def test_generated_transport_and_paired_directions(self):
        # This checks packet transport/aggregation only. Source numerical parity
        # is separately exercised on small generated fixtures without mocks.
        request = self.request()
        calls = []

        def generated_metric(truth, embeddings, rng):
            calls.append(rng.get_state()[1].copy())
            candidate = embeddings[0][0] < 0
            scores = np.array([[[.2] * 5, [.8] * 5], [[.7] * 5, [.33] * 5]])
            if candidate:
                scores[0, 0] -= .1
                scores[1, 0] += .05
            return scores, np.full((2, 5), 12)

        with mock.patch.object(scorer, "source_benchmarks", side_effect=generated_metric):
            result = scorer.evaluate_request(request)
        self.assertEqual(len(calls), 20)
        for i in range(0, 20, 2):
            np.testing.assert_array_equal(calls[i], calls[i+1])
        diff = np.asarray(result["paired_favorable_mean_percentage_points"])
        np.testing.assert_allclose(diff[0], 10)
        np.testing.assert_allclose(diff[1], 5)
        self.assertFalse(result["published_score_reproduced"])
        self.assertFalse(result["paper_improvement_established"])
        encoded = json.dumps(result, default=lambda a: a.tolist(), allow_nan=False)
        self.assertNotIn(str(self.path), encoded)


class AllocationAdmissionTests(unittest.TestCase):
    """Generated headers only; oversized claimed arrays are never allocated."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "packet.npz"

    def packet(self, embedding_body):
        import io
        import zipfile
        ids = io.BytesIO()
        np.save(ids, np.arange(6000, dtype="<i4"), allow_pickle=False)
        with zipfile.ZipFile(self.path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("neuron_id.npy", ids.getvalue())
            archive.writestr("embedding.npy", embedding_body)
        return {"path": str(self.path), "sha256": hashlib.sha256(self.path.read_bytes()).hexdigest()}

    def test_invalid_geometry_and_extent_refused_before_numpy_materialization(self):
        import io
        for shape in ((2**40,), (5999,), (6000,)):
            with self.subTest(shape=shape):
                body = io.BytesIO()
                np.lib.format.write_array_header_1_0(body,
                    {"descr": "<f8", "fortran_order": False, "shape": shape})
                packet = self.packet(body.getvalue())  # Header only: never allocate its declared shape.
                with mock.patch.object(scorer.np, "load", side_effect=AssertionError("unvalidated materialization")) as load:
                    with self.assertRaises(ValueError):
                        scorer._load_artifact(packet, {"embedding", "neuron_id"})
                    load.assert_not_called()

    def test_valid_column_vector_and_integer_ids_preserved(self):
        import io
        values = np.zeros((6000, 1), dtype=">f4")
        body = io.BytesIO(); np.save(body, values, allow_pickle=False)
        result = scorer._load_artifact(self.packet(body.getvalue()), {"embedding", "neuron_id"})
        np.testing.assert_array_equal(result["embedding"], values)
        self.assertEqual(result["embedding"].dtype, values.dtype)
        np.testing.assert_array_equal(result["neuron_id"], np.arange(6000))

    def test_compressed_input_read_is_bounded_on_consumed_stream(self):
        import io
        stream = io.BytesIO(b"x" * (1024 * 1024 + 1))
        path = mock.MagicMock(); path.is_absolute.return_value = True
        path.open.return_value.__enter__.return_value = stream
        with mock.patch.object(scorer, "Path", return_value=path):
            with self.assertRaisesRegex(ValueError, "exceeds 1 MiB"):
                scorer._load_artifact({"path": "/operator/packet.npz", "sha256": "0" * 64},
                                      {"embedding", "neuron_id"})
        self.assertEqual(stream.tell(), 1024 * 1024 + 1)
        path.read_bytes.assert_not_called()


if __name__ == "__main__":
    unittest.main()
