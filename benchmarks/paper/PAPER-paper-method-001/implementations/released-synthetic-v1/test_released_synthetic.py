"""Small generated software controls; no author estimator or complete panel run."""
import ast
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("released_synthetic", HERE / "released_synthetic.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def scalar(value):
    return {"value": value, "nonfinite": None}


def fixture():
    # Invented software-control scalars, never a paper baseline or prediction.
    return [{"case": row, "recipe": module.RECIPE,
             "environment": {"numpy": np.__version__, "opt_einsum": "software-control"},
             "status": "returned", "error_kind": None,
             "values": {key: scalar(float(row["seed"] ** 2 + 3 * i))
                        for i, key in enumerate(module.ESTIMATORS)}}
            for row in module.cases()]


class ReleasedSyntheticTests(unittest.TestCase):
    def test_source_authentication_and_grid(self):
        source = (HERE / "upstream/synthetic.py").read_bytes()
        manifest = json.loads((HERE / "SOURCE.json").read_text())
        self.assertEqual(hashlib.sha256(source).hexdigest(), manifest["recovered_source"]["sha256"])
        self.assertEqual(hashlib.sha1(b"blob " + str(len(source)).encode() + b"\0" + source).hexdigest(),
                         manifest["recovered_source"]["git_blob_sha1"])
        original = ast.parse(source)
        main = next(node for node in original.body if isinstance(node, ast.FunctionDef) and node.name == "main")
        source_grids = {node.targets[0].id: ast.literal_eval(node.value)
                        for node in main.body if isinstance(node, ast.Assign) and
                        isinstance(node.targets[0], ast.Name) and node.targets[0].id in ("P_vals", "Q_vals")}
        self.assertEqual(source_grids, {"P_vals": list(module.SIZES), "Q_vals": list(module.SIZES)})
        rows = module.cases()
        self.assertEqual(len(rows), 400)
        self.assertEqual(len({row["case_id"] for row in rows}), 400)
        self.assertEqual(len({(row["P"], row["Q"], row["seed"]) for row in rows}), 380)
        for dependency, digest in manifest["estimator_dependencies"].items():
            path = HERE.parent / "dimensionality-programme/programme/scientific-runtime/finite_science/literal_author" / dependency
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)

    def test_observation_against_exact_upstream_generator(self):
        original = ast.parse((HERE / "upstream/synthetic.py").read_text())
        make = next(node for node in original.body if isinstance(node, ast.FunctionDef) and node.name == "_make_Phi")
        scope = {"np": np}
        exec(compile(ast.Module(body=[make], type_ignores=[]), "upstream-generator-only", "exec"), scope)
        for case in (module.cases()[0], module.cases()[19], module.cases()[200]):
            expected = scope["_make_Phi"](case["P"], case["Q"], 50, np.sqrt(0.2), np.random.default_rng(case["seed"]))
            np.testing.assert_array_equal(module.observation(case), expected)
        # The two source panels reuse this observation, so cannot be counted as
        # two independent simulation worlds.
        p_case = next(row for row in module.cases() if row["case_id"] == "P/07/00")
        q_case = next(row for row in module.cases() if row["case_id"] == "Q/05/00")
        np.testing.assert_array_equal(module.observation(p_case), module.observation(q_case))

    def test_complete_order_independent_source_reductions(self):
        result = module.summarize(list(reversed(fixture())))
        self.assertEqual((result["planned_draw_slots"], result["retained_draw_slots"], result["planned_estimates"]),
                         (400, 400, 1600))
        values = [float(seed ** 2) for seed in range(20)]
        mean = math.fsum(values) / 20
        sem = math.sqrt(math.fsum((value - mean) ** 2 for value in values) / 19 / 20)
        first = result["panels"][0]["estimates"]["naive"]
        self.assertEqual(first["mean"], scalar(mean))
        self.assertAlmostEqual(first["sem"]["value"], sem, places=12)
        self.assertEqual(first["counts"]["finite"], 20)
        self.assertEqual(first["counts"]["nonpositive_finite"], 1)

    def test_nonfinite_source_mean_is_not_nan_skipped(self):
        rows = fixture()
        rows[0]["values"]["naive"] = {"value": None, "nonfinite": "nan"}
        rows[1]["values"]["row"] = {"value": None, "nonfinite": "inf"}
        summary = module.summarize(rows)["panels"][0]["estimates"]
        self.assertEqual(summary["naive"]["mean"], {"value": None, "nonfinite": "nan"})
        self.assertEqual(summary["naive"]["counts"]["nan"], 1)
        self.assertEqual(summary["row"]["mean"], {"value": None, "nonfinite": "inf"})
        self.assertEqual(summary["row"]["counts"]["positive_infinity"], 1)

    def test_arithmetic_failure_keeps_denominator(self):
        rows = fixture()
        rows[4].update(status="arithmetic_failure", values=None, error_kind="OverflowError")
        result = module.summarize(rows)
        first = result["panels"][0]
        self.assertEqual(first["planned_draws"], 20)
        self.assertEqual(first["failed_seeds"], [4])
        self.assertIsNone(first["estimates"]["both"]["mean"])
        self.assertEqual(first["estimates"]["both"]["counts"]["finite"], 19)
        self.assertIsNotNone(result["panels"][1]["estimates"]["both"]["mean"])

    def test_rejects_invalid_roster_and_disposition(self):
        baseline = fixture()
        changes = []
        changes.append(baseline[:-1])
        duplicate = copy.deepcopy(baseline)
        duplicate[-1] = copy.deepcopy(duplicate[0])
        changes.append(duplicate)
        for key, value in (("P", 4), ("seed", False), ("extra", "untrusted")):
            changed = copy.deepcopy(baseline)
            changed[0]["case"][key] = value
            changes.append(changed)
        changed = copy.deepcopy(baseline)
        changed[0]["environment"]["numpy"] = "other-version"
        changes.append(changed)
        changed = copy.deepcopy(baseline)
        changed[0]["values"]["both"] = {"value": 1.0, "nonfinite": "nan"}
        changes.append(changed)
        for rows in changes:
            with self.assertRaises(ValueError):
                module.summarize(rows)

    def test_author_adapter_calls_only_single_observation(self):
        calls = []
        def fake_estimator(*args, **kwargs):
            calls.append((args, kwargs))
            return dict.fromkeys(module.ESTIMATORS, 2.0)
        fake_dependency = types.ModuleType("opt_einsum")
        fake_dependency.__version__ = "software-control"
        with patch.dict(sys.modules, {"opt_einsum": fake_dependency}), \
                patch.object(module, "_author_estimator", return_value=fake_estimator):
            result = module.author_case(module.cases()[0])
        self.assertEqual(result["status"], "returned")
        self.assertEqual(len(calls[0][0]), 1)
        self.assertEqual(calls[0][1], {"return_all": True})
        with patch.dict(sys.modules, {"opt_einsum": fake_dependency}), \
                patch.object(module, "_author_estimator", return_value=lambda *_args, **_kwargs: 1 / 0):
            result = module.author_case(module.cases()[0])
        self.assertEqual(result["status"], "arithmetic_failure")
        self.assertEqual(result["error_kind"], "ZeroDivisionError")
        self.assertIsNone(result["values"])

    @unittest.skipUnless(importlib.util.find_spec("opt_einsum") is not None,
                         "opt_einsum unavailable; real author import unverified")
    def test_author_dependency_loader_without_estimation(self):
        estimator = module._author_estimator()
        self.assertTrue(callable(estimator))
        self.assertEqual(estimator.__module__, "_released_synthetic_author_f18de358.estimators")
        self.assertIs(estimator, module._author_estimator())

    def test_missing_dependency_is_not_an_estimator_failure(self):
        with patch.dict(sys.modules, {"opt_einsum": None}):
            with self.assertRaises(ModuleNotFoundError):
                module.author_case(module.cases()[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
