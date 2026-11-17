"""Generated software controls only; no authentic features or model execution."""
from contextlib import ExitStack
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("bounded_mindeye2", HERE / "streaming.py")
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference():
    ids = [f"generated-{i}" for i in range(1000)]
    return dict(task_id=s.legacy.TASK, contract_sha256=s.CONTRACT_SHA256,
                code_revision=s.legacy.CODE_REVISION, dataset_revision=s.legacy.DATA_REVISION,
                subject=1, image_ids=ids, retrieval_pools=s.legacy.freeze_pools(ids),
                feature_space=s.FEATURE_SPACE, image_features_sha256="a" * 64,
                population_manifest_sha256="b" * 64, feature_extraction_receipt_sha256="c" * 64)


class NumericalControls(unittest.TestCase):
    def test_full_population_thirty_draws_matches_predecessor_and_reordered_memmaps(self):
        rng = np.random.RandomState(733)
        images = rng.normal(size=(1000, 31)).astype("float32")
        brain = (images * .20 + rng.normal(size=images.shape)).astype("float32")
        ids = reference()["image_ids"]
        pools = s.legacy.freeze_pools(ids)
        expected = s.legacy.score_aligned_features(ids, pools, brain, images)
        permutation = rng.permutation(1000)
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            paths = [Path(folder) / name for name in ("images.npy", "brain.npy")]
            np.save(paths[0], images)
            np.save(paths[1], brain[permutation])
            im, br = [stack.enter_context(s.mapped_npy(path, sha(path))) for path in paths]
            actual = s.score_aligned_features(ids, pools, br, im, brain_order=np.argsort(permutation),
                                              block_rows=7, feature_block=11)
            self.assertIsInstance(im, np.memmap)
            self.assertIsInstance(br, np.memmap)
        self.assertEqual(expected, actual)
        self.assertGreater(actual["image_retrieval"]["mean"], 0)
        self.assertLess(actual["image_retrieval"]["mean"], 1)
        self.assertEqual(len(actual["brain_retrieval"]["draw_values"]), 30)

    def test_independent_dense_cosines_and_bounded_temporary_shapes(self):
        rng = np.random.RandomState(21)
        a = rng.normal(size=(37, 69))
        b = rng.normal(size=(37, 69))
        original_a, original_b = a.copy(), b.copy()
        order = rng.permutation(37)
        # Independent conventional L2 normalization, without the tiled path.
        expected = (a / np.linalg.norm(a, axis=1)[:, None])[order] @ (b / np.linalg.norm(b, axis=1)[:, None]).T
        with patch.object(s, "_row_normalizers", wraps=s._row_normalizers) as rows, \
             patch.object(s, "_normalized_columns", wraps=s._normalized_columns) as cols:
            actual = s.cosine_matrix(a, b, order, block_rows=5, feature_block=7)
        np.testing.assert_allclose(actual, expected, rtol=2e-13, atol=2e-15)
        self.assertEqual(rows.call_count, 2 * 8)
        self.assertTrue(all(len(call.args[1]) <= 5 for call in rows.call_args_list))
        self.assertEqual(cols.call_count, 2 * 10)
        self.assertTrue(all(call.args[3] - call.args[2] <= 7 for call in cols.call_args_list))
        np.testing.assert_array_equal(a, original_a)
        np.testing.assert_array_equal(b, original_b)

    def test_direction_is_not_transposed(self):
        matrix = np.array([[.9, .1, .2], [.8, .7, .3], [.1, .6, .4]])
        self.assertEqual(s.retrieval_from_cosines(matrix), {"image_retrieval": 1 / 3, "brain_retrieval": 1.0})
        with self.assertRaisesRegex(ValueError, "tied maximum"):
            s.retrieval_from_cosines(np.ones((3, 3)))

    def test_extreme_scale_invariance_and_invalid_rows(self):
        a = np.array([[1., 2., 3.], [3., -4., 1.]])
        expected = s.cosine_matrix(a, a, np.arange(2), feature_block=1)
        actual = s.cosine_matrix(a * 1e300, a * 1e-300, np.arange(2), feature_block=2)
        np.testing.assert_allclose(actual, expected, rtol=2e-15, atol=2e-15)
        for invalid in (np.zeros((2, 3)), np.full((2, 3), np.nan), np.full((2, 3), np.inf)):
            with self.assertRaises(ValueError):
                s.cosine_matrix(invalid, a, np.arange(2))
        for kwargs in ({"block_rows": 33}, {"block_rows": True}, {"feature_block": 4097}, {"feature_block": 0}):
            with self.assertRaises(ValueError):
                s.cosine_matrix(a, a, np.arange(2), **kwargs)
        for order in ([0, 0], [0., 1.], [True, False]):
            with self.assertRaises(ValueError):
                s.cosine_matrix(a, a, order)

    def test_storage_and_identity_failures(self):
        ids = [str(i) for i in range(300)]
        a = np.ones((300, 2))
        pools = s.legacy.freeze_pools(ids)
        for bad_ids, bad_pools, bad_array in ((ids[:-1], pools, a),
                                              (ids, pools[:-1], a),
                                              (ids, pools, a[:-1]),
                                              (ids, pools, np.asfortranarray(a))):
            with self.assertRaises(ValueError):
                s.score_aligned_features(bad_ids, bad_pools, bad_array, a)


class MappedInputControls(unittest.TestCase):
    def test_same_file_readonly_mapping_hash_and_complete_payload(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "array.npy"
            original = np.arange(48, dtype="float32").reshape(4, 3, 4)
            np.save(path, original)
            with s.mapped_npy(path, sha(path)) as result:
                self.assertIsInstance(result, np.memmap)
                self.assertFalse(result.flags.writeable)
                np.testing.assert_array_equal(result, original)
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                with s.mapped_npy(path, "0" * 64):
                    pass
            with path.open("ab") as file:
                file.write(b"extra payload")
            with self.assertRaisesRegex(ValueError, "trailing payload"):
                with s.mapped_npy(path, sha(path)):
                    pass

    def test_object_complex_fortran_and_mutation_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "array.npy"
            for x in (np.ones((3, 4), dtype=complex), np.array([[object()]], dtype=object),
                      np.asfortranarray(np.ones((3, 4)))):
                np.save(path, x)
                with self.assertRaises(ValueError):
                    with s.mapped_npy(path, sha(path)):
                        pass
            np.save(path, np.ones((3, 4)))
            with self.assertRaisesRegex(ValueError, "changed during scoring"):
                with s.mapped_npy(path, sha(path)):
                    with path.open("ab") as file:
                        file.write(b"mutation")

    def test_current_contract_and_native_width_admission(self):
        ref = reference()
        self.assertEqual(len(s.validate_reference(ref)), 1000)
        for key, value in (("subject", 3), ("subject", True),
                           ("contract_sha256", s.legacy.CONTRACT_SHA256),
                           ("code_revision", "wrong"), ("feature_space", "image labels")):
            bad = copy.deepcopy(ref)
            bad[key] = value
            with self.assertRaises(ValueError):
                s.validate_reference(bad)
        candidate = dict(reference_manifest_digest=s.legacy.digest(ref), image_ids=ref["image_ids"],
                         subject=1, feature_space=s.FEATURE_SPACE, brain_features_sha256="d" * 64,
                         checkpoint_sha256="e" * 64, exposure_ledger_sha256="f" * 64)
        with self.assertRaisesRegex(ValueError, r"256\*1664"):
            s.evaluate(ref, candidate, np.ones((1000, 8)), np.ones((1000, 8)))
        candidate["image_ids"] = candidate["image_ids"][::-1][:-1] + ["impostor"]
        with self.assertRaisesRegex(ValueError, "population"):
            s.evaluate(ref, candidate, np.ones((1000, 8)), np.ones((1000, 8)))

    def test_cli_rejects_untrusted_reference_before_array_access(self):
        with tempfile.TemporaryDirectory() as folder:
            ref = Path(folder) / "reference.json"
            ref.write_text(json.dumps(reference()))
            proc = subprocess.run([sys.executable, "-I", "-B", str(HERE / "streaming.py"),
                "--reference", str(ref), "--reference-sha256", "0" * 64,
                "--candidate", "absent", "--image-features", "absent", "--brain-features", "absent"],
                capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("trusted reference SHA-256 mismatch", proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
