"""Generated numerical controls; never reads EEG, weights or genuine targets."""
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
import warnings

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("endpoints", HERE / "endpoints.py")
ep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ep)
np = ep.np


def source_oracles(path):
    """Execute authenticated arithmetic tails only, excluding all model loops."""
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != "56646f96447384920216d84aa1189b4a96c2e16ced3b927a360e6bcc19711ad3":
        raise ValueError("pinned official evaluator differs")
    tree = ast.parse(body)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Evaluator")
    result = {}
    for kind, suffix in (("multiclass", "multiclass"), ("binary", "binaryclass"), ("regression", "regression")):
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "get_metrics_for_" + suffix)
        start = next(i for i, node in enumerate(method.body)
                     if isinstance(node, ast.Assign) and ast.unparse(node) == "truths = np.array(truths)")
        fn = ast.parse("def oracle(truths, preds, scores=None):\n    pass\n").body[0]
        fn.body = method.body[start:]
        module = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
        scope = vars(ep).copy()
        exec(compile(module, "<authenticated CBraMod metric tail>", "exec"), scope)
        result[kind] = scope["oracle"]
    return result


class Endpoints(unittest.TestCase):
    oracle = None

    def test_primary_dataset_dispatch_matches_preserved_source_panel(self):
        path = HERE.parent / "cbramod-paired-program/science/runtime/source/benchmark/public/PANEL.json"
        body = path.read_bytes()
        self.assertEqual(hashlib.sha256(body).hexdigest(),
                         "1f7348f79f62175e3292f4cfdbd613a785f222ebf038dd3ddadce09f438e06eb")
        expected = {r["id"]: (r["task"], r["classes"])
                    for r in json.loads(body)["primary_downstream_datasets"]}
        self.assertEqual(ep.DATASETS, expected)

    def test_preserved_scorer_counterexamples(self):
        path = HERE.parent / "cbramod-paired-program/science/runtime/source/benchmark/private/metrics.py"
        body = path.read_bytes()
        self.assertEqual(hashlib.sha256(body).hexdigest(),
                         "f593aa424fe8a3a0ae76bcb827c5a2f05667d01573276bb14c934616114abb49")
        old = {}
        exec(compile(body, "<preserved numerical source>", "exec"), old)
        self.assertIsNone(old["classify"]([0, 0, 1, 1], np.eye(6)[[0, 2, 1, 1]], 6)["balanced_accuracy"])
        self.assertIsNone(old["regress"]([2., 2., 2.], [2., 2., 2.])["r2"])

    def compare(self, kind, dataset, y, out):
        actual = ep.score(dataset, y, out)
        truth = np.asarray(y).reshape(-1).tolist()
        scores = np.asarray(out)
        if kind == "multiclass":
            pred = scores.reshape(-1, ep.DATASETS[dataset][1]).argmax(-1).tolist()
            names = ("balanced_accuracy", "cohen_kappa", "weighted_f1")
        elif kind == "binary":
            pred = (scores[:, 0] > .5).astype(int).tolist()
            names = ("balanced_accuracy", "auc_pr", "auroc")
        else:
            pred = scores[:, 0].tolist()
            names = ("pearson", "r2", "rmse")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            expected = self.oracle[kind](truth, pred, scores.tolist())
        for name, value in zip(names, expected[:3]):
            if np.isfinite(value):
                self.assertAlmostEqual(actual["metrics"][name], value, places=13)
            else:
                self.assertIsNone(actual["metrics"][name])
                self.assertIn(name, actual["undefined_metrics"])
        return actual

    def test_all_twelve_dispatch_against_author_arithmetic(self):
        for dataset, (kind, classes) in ep.DATASETS.items():
            with self.subTest(dataset=dataset):
                if kind == "multiclass":
                    y = np.arange(40) % classes
                    out = np.eye(classes)[(y + (np.arange(40) % 7 == 0)) % classes]
                    if dataset == "ISRUC":
                        y, out = y.reshape(2, 20), out.reshape(2, 20, classes)
                elif kind == "binary":
                    y, out = np.array([0, 1, 0, 1, 1, 0]), np.array([[.5], [.5], [.9], [.9], [.2], [.1]])
                else:
                    y, out = np.array([.1, .7, .4, .9]), np.array([[.2], [.6], [.3], [.8]])
                self.compare(kind, dataset, y, out)

    def test_missing_class_balanced_accuracy_is_not_none(self):
        # Six-class TUEV ontology, only target classes 0/1 in this software fixture.
        out = np.eye(6)[[0, 2, 1, 1]]
        result = self.compare("multiclass", "TUEV", [0, 0, 1, 1], out)
        self.assertEqual(result["metrics"]["balanced_accuracy"], .75)
        self.assertEqual(result["confusion_labels"], [0, 1, 2])
        self.assertEqual(result["target_class_support"], [2, 2, 0, 0, 0, 0])

    def test_binary_ties_and_trapezoidal_pr_not_average_precision(self):
        result = self.compare("binary", "TUAB", [0, 1], np.array([[.5], [.5]]))
        self.assertEqual(result["confusion"], [[1, 0], [1, 0]])
        self.assertEqual(result["metrics"]["auc_pr"], .75)
        self.assertEqual(result["metrics"]["auroc"], .5)

    def test_constant_regression_preserves_sklearn_r2(self):
        for prediction, expected in (([2., 2., 2.], 1.), ([1., 1., 1.], 0.)):
            result = self.compare("regression", "SEED-VIG", [2., 2., 2.], np.array(prediction)[:, None])
            self.assertEqual(result["metrics"]["r2"], expected)
            self.assertIsNone(result["metrics"]["pearson"])

    def test_perfect_single_class_kappa_remains_undefined(self):
        result = self.compare("multiclass", "PhysioNet-MI", [0, 0], np.eye(4)[[0, 0]])
        self.assertEqual(result["metrics"]["balanced_accuracy"], 1.)
        self.assertIsNone(result["metrics"]["cohen_kappa"])

    def test_regression_promotes_float32_like_author_tolist(self):
        self.compare("regression", "SEED-VIG", np.array([1e8, 1e8 + 8, 1e8 + 16], dtype="f4"),
                     np.array([[1e8 + 8], [1e8 + 8], [1e8 + 24]], dtype="f4"))

    def test_isruc_context_and_bad_outputs_refused(self):
        bad = [("ISRUC", np.zeros(20), np.zeros((20, 5))),
               ("ISRUC", np.zeros((1, 19)), np.zeros((1, 19, 5))),
               ("TUAB", [0, 1], [[-1.], [1.]]),
               ("TUAB", [0, 0], [[.2], [.3]]),
               ("SEED-VIG", [1., 2.], [[1.], [np.nan]]),
               ("TUEV", [0, 6], np.zeros((2, 6))),
               ("FACED", [0, 1], np.zeros((2, 8))),
               ("SEED-VIG", [1., 2.], [1., 2.])]
        for dataset, y, out in bad:
            with self.subTest(dataset=dataset), self.assertRaises(ValueError):
                ep.score(dataset, y, out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-evaluator", required=True, type=Path)
    args = parser.parse_args()
    Endpoints.oracle = source_oracles(args.official_evaluator)
    unittest.main(argv=[sys.argv[0]], verbosity=2)
