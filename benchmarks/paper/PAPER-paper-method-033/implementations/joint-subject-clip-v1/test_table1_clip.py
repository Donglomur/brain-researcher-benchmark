"""Generated feature math and input-contract controls; no images, models or labels."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parent
COUNTS = {"source_reads": 0, "generated_writes": 0, "generated_payload_reads": 0}
EVAL_SHA = "bde3c051c6f1c3be47c7075986ba2854a16561ff8702b3cbbf412edfcdf5c180"


def read_source(path):
    body = path.read_bytes()
    COUNTS["source_reads"] += len(body)
    return body


def captured_module(path):
    body = read_source(path)
    module = types.ModuleType("_table1_under_test")
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def author_numerical_rule():
    """Frozen original numerical tail; no author imports, models or downloads.

    Full-file SHA is above. The first private check extracted these exact
    statements from authenticated author source with AST. They are retained
    here so the public generated checks are standalone and work offline.
    """
    source = "def reference(reals, preds, all_images, return_avg):\n    r = np.corrcoef(reals, preds)\n    r = r[:len(all_images), len(all_images):]\n    congruents = np.diag(r)\n\n    success = r < congruents\n    success_cnt = np.sum(success, 0)\n\n    if return_avg:\n        perf = np.mean(success_cnt) / (len(all_images)-1)\n        return perf\n    else:\n        return success_cnt, len(all_images)-1\n"
    namespace = {"np": np}
    exec(compile(source, "<pinned-author-eval-numerical-tail>", "exec"), namespace)
    return namespace["reference"]

class MetricTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = captured_module(ROOT / "table1_clip.py")
        cls.reference = staticmethod(author_numerical_rule())

    def base(self):
        return np.array([[2, -1, -1], [-1, 2, -1], [-1, -1, 2]], dtype=np.float32)

    def test_hand_perfect(self):
        x = self.base()
        counts, score = self.m.two_way_from_features(x, x)
        np.testing.assert_array_equal(counts, [2, 2, 2])
        self.assertEqual(score, 1.0)

    def test_hand_asymmetric_column_and_strict_ties(self):
        x = self.base()
        p = np.repeat(x[:1], 3, axis=0)
        counts, score = self.m.two_way_from_features(x, p)
        # Column0's correct match beats both distractors. Other congruents equal
        # one distractor and lose to the other. A row-wise version gives zero.
        np.testing.assert_array_equal(counts, [2, 0, 0])
        self.assertEqual(score, 1 / 3)

    def test_tied_identical_gallery_scores_zero(self):
        x = np.repeat(self.base()[:1], 3, axis=0)
        counts, score = self.m.two_way_from_features(x, x)
        np.testing.assert_array_equal(counts, [0, 0, 0])
        self.assertEqual(score, 0.0)

    def test_exact_pinned_author_numerical_parity(self):
        rng = np.random.default_rng(72)
        for n, d in ((3, 5), (7, 13), (19, 768)):
            r = rng.standard_normal((n, d)).astype("float32")
            p = rng.standard_normal((n, d)).astype("float32")
            counts, score = self.m.two_way_from_features(r, p)
            ref_counts, denominator = self.reference(r, p, range(n), False)
            np.testing.assert_array_equal(counts, ref_counts)
            self.assertEqual(denominator, n - 1)
            self.assertEqual(score, float(self.reference(r, p, range(n), True)))

    def test_pearson_affine_invariance_and_joint_permutation(self):
        x = self.base()
        p = np.repeat(x[:1], 3, axis=0)
        counts, score = self.m.two_way_from_features(x, p)
        new_counts, new_score = self.m.two_way_from_features(2 * x + 8, 4 * p - 3)
        np.testing.assert_array_equal(counts, new_counts)
        self.assertEqual(score, new_score)
        order = [2, 0, 1]
        reordered, again = self.m.two_way_from_features(x[order], p[order])
        np.testing.assert_array_equal(reordered, counts[order])
        self.assertEqual(again, score)

    def test_undefined_wrong_precision_or_shape_refused(self):
        x = self.base()
        variants = [x.astype("float64"), np.zeros_like(x), x[:1]]
        nan = x.copy(); nan[0, 0] = np.nan; variants.append(nan)
        inf = x.copy(); inf[0, 0] = np.inf; variants.append(inf)
        for value in variants:
            with self.subTest(dtype=value.dtype, shape=value.shape):
                with self.assertRaises(self.m.MetricError):
                    self.m.two_way_from_features(value, value)
        with self.assertRaises(self.m.MetricError):
            self.m.two_way_from_features(x, x[:2])

    def test_source_selection_first_max_and_separate_features(self):
        sims = np.array([[.2, .7, .7, .1, 0, -.2, -.1, .3]], dtype="float64")
        np.testing.assert_array_equal(self.m.source_selected_indices(sims, np.array([1])), [1])
        with self.assertRaises(self.m.MetricError):
            self.m.source_selected_indices(sims, np.array([2]))
        with self.assertRaises(self.m.MetricError):
            self.m.source_selected_indices(sims[:, :7], np.array([1]))
        sims[0, 3] = np.nan
        with self.assertRaises(self.m.MetricError):
            self.m.source_selected_indices(sims, np.array([1]))

    def rows(self):
        ids = [f"stimulus-{i:04}" for i in range(982)]
        return [{"subject": s, "target_ids": ids.copy(),
                 "reconstruction_ids": ids.copy(), "selection_ids": ids.copy(),
                 "target_features": "target", "selected_features": "selected",
                 "selection_cosines": "cosines", "selected_candidate_indices": "indices"}
                for s in self.m.SUBJECTS]

    def test_four_subject_macro_mean_not_subset(self):
        self.assertEqual(self.m.subject_mean({"1": 0., "2": .25, "5": .5, "7": 1.}), .4375)
        for scores in ({"7": .947}, {"1": 0., "2": 0., "5": 0., "7": np.nan},
                       {"1": 0., "2": 0., "5": 0., "7": 1.01}):
            with self.assertRaises(self.m.MetricError):
                self.m.subject_mean(scores)

    def test_exact_subjects_gallery_and_pairing(self):
        self.assertEqual(set(self.m.validate_rows(self.rows())), set(self.m.SUBJECTS))
        mutations = []
        rows = self.rows(); rows[3]["subject"] = "5"; mutations.append(rows)
        rows = self.rows(); rows.pop(); mutations.append(rows)
        rows = self.rows(); rows[0]["target_ids"] = rows[0]["target_ids"][:-1]; mutations.append(rows)
        rows = self.rows(); rows[0]["target_ids"][1] = rows[0]["target_ids"][0]; mutations.append(rows)
        rows = self.rows(); rows[0]["reconstruction_ids"].reverse(); mutations.append(rows)
        rows = self.rows(); rows[0]["selection_ids"].reverse(); mutations.append(rows)
        rows = self.rows()
        for key in ("target_ids", "reconstruction_ids", "selection_ids"):
            rows[0][key][0] = "a-different-stimulus"
        mutations.append(rows)
        for rows in mutations:
            with self.assertRaises(self.m.MetricError):
                self.m.validate_rows(rows)

    def test_full_generated_982_gallery_runs_and_keeps_limits_false(self):
        # Pure generated features; no brain/image/model inputs. All subjects use
        # one matching synthetic gallery, so every correct correlation wins.
        r = np.random.default_rng(11).normal(size=(982, 768)).astype("float32")
        arrays = {"target": r, "selected": r, "cosines": np.zeros((982, 8)),
                  "indices": np.zeros(982, dtype="int64")}
        result = self.m.evaluate(self.rows(), arrays.__getitem__,
                                 max_working_bytes=128 * 1024**2)
        self.assertEqual(result["clip_two_way"], 1.)
        self.assertEqual([s["images"] for s in result["subjects"]], [982] * 4)
        self.assertFalse(result["scientific_qualification"])
        self.assertFalse(result["table2_full48_qualified"])
        self.assertEqual(result["reproduction"], "unknown")
        self.assertFalse(result["source_selection_arithmetic_reexecuted"])

    def save(self, root, value=None, raw=None):
        if raw is None:
            stream = io.BytesIO(); np.save(stream, value, allow_pickle=False); raw = stream.getvalue()
        path = root / "value.npy"; path.write_bytes(raw)
        COUNTS["generated_writes"] += len(raw)
        return {"path": "value.npy", "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest()}

    def test_reader_hash_path_budget_and_exact_extent(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix="generated-metric-") as temp:
            root = Path(temp)
            desc = self.save(root, self.base())
            reader = self.m.FileArrays(root, 4096)
            np.testing.assert_array_equal(reader(desc), self.base())
            COUNTS["generated_payload_reads"] += reader.read_bytes
            bad = dict(desc, sha256="0" * 64)
            reader = self.m.FileArrays(root, 4096)
            with self.assertRaises(self.m.MetricError):
                reader(bad)
            COUNTS["generated_payload_reads"] += reader.read_bytes
            for bad in (dict(desc, path="../value.npy"), dict(desc, path="/value.npy")):
                with self.assertRaises(self.m.MetricError):
                    self.m.FileArrays(root, 4096)(bad)
            with self.assertRaises(self.m.MetricError):
                self.m.FileArrays(root, desc["bytes"] - 1)(desc)
            stream = io.BytesIO(); np.save(stream, self.base(), allow_pickle=False)
            desc = self.save(root, raw=stream.getvalue() + b"trailing")
            reader = self.m.FileArrays(root, 4096)
            with self.assertRaises(self.m.MetricError):
                reader(desc)
            COUNTS["generated_payload_reads"] += reader.read_bytes

    def test_header_extent_bounds_before_array_allocation(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix="generated-header-") as temp:
            root = Path(temp)
            stream = io.BytesIO()
            np.lib.format.write_array_header_1_0(stream, {
                "descr": "<f4", "fortran_order": False, "shape": (10**12, 768)})
            desc = self.save(root, raw=stream.getvalue())
            reader = self.m.FileArrays(root, 4096)
            with self.assertRaisesRegex(self.m.MetricError, "header/body extent"):
                reader(desc)
            COUNTS["generated_payload_reads"] += reader.read_bytes


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(MetricTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({"tests": result.testsRun, "failures": len(result.failures),
                      "errors": len(result.errors), "costs": COUNTS,
                      "generated_only": True}, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
