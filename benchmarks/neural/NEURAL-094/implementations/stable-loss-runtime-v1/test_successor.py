"""Source-composition controls only; no scientific observations or native runner."""
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import compose


HERE = Path(__file__).resolve().parent
TASK = Path(os.environ.get("NEURAL094_TASK_ROOT", HERE.parents[1]))
BASE = TASK / "implementations/regional-comparison/complete_regional"


def module_from_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RootBoundaryTests(unittest.TestCase):
    def test_dotdot_alias_cannot_hide_a_nested_destination(self):
        scratch = HERE.parent / "test-scratch"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            base, overlay = root / "base", root / "overlay"
            for parent in (base, overlay):
                (parent / "child").mkdir(parents=True)
                (parent / "output").mkdir()
            for aliased in (base, overlay):
                source = base / "child" / ".." if aliased == base else base
                replacement = overlay / "child" / ".." if aliased == overlay else overlay
                target = aliased / "output"
                with self.subTest(aliased=aliased.name), mock.patch.object(compose, "read") as reader:
                    with self.assertRaisesRegex(compose.Refusal, "Three disjoint roots"):
                        compose.materialize(source, replacement, target, compose.RECIPE_PIN,
                                            compose.Budget(600000, 400000, 30))
                    reader.assert_not_called()
                    self.assertEqual(list(target.iterdir()), [])
        scratch.rmdir()


class SuccessorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recipe = (HERE / "RECIPE.json").read_bytes()
        cls.plan = compose.recipe(cls.recipe, compose.RECIPE_PIN)
        manifest = (BASE / "SOURCE_MANIFEST.json").read_bytes()
        cls.before = {"SOURCE_MANIFEST.json": manifest}
        cls.before.update({name: (BASE / name).read_bytes()
                           for name in json.loads(manifest)["files"]})
        cls.overlay = {r["path"]: (HERE / r["overlay_path"]).read_bytes()
                       for r in cls.plan["changes"]}

    def composed(self):
        return compose.compose(self.before, self.overlay, self.recipe, compose.RECIPE_PIN)

    def test_exact_closed_source_and_loader_select_stable_scorer(self):
        result = self.composed()
        self.assertEqual(len(result), 35)
        self.assertEqual(compose.pin(result[compose.SCORE]), compose.SCORER_PIN)
        source = json.loads(result["SOURCE_MANIFEST.json"])
        runtime = json.loads(result["RUNTIME_INVENTORY.json"])
        numerical = json.loads(result[compose.NUMERICAL])
        selected = next(r for r in runtime["files"] if r["path"] == compose.SCORE)
        self.assertEqual({k: selected[k] for k in ("bytes", "sha256")}, compose.SCORER_PIN)
        self.assertEqual(source["files"][compose.SCORE], compose.SCORER_PIN)
        self.assertEqual({k: numerical["score_adapter"][k] for k in ("bytes", "sha256")}, compose.SCORER_PIN)
        self.assertEqual(numerical["score_adapter"]["path"], "score_adapter.py")
        self.assertEqual(source["scientific_scope"], compose.SCOPE)
        self.assertFalse(source["execution_authority"])
        self.assertFalse(source["scientific_qualification"])

    def test_only_one_executable_body_changes(self):
        result = self.composed()
        python = [n for n in result if n.endswith(".py")]
        self.assertEqual(len(python), 28)
        self.assertEqual([n for n in python if result[n] != self.before[n]], [compose.SCORE])
        self.assertEqual(result["source/regional_grading.py"], self.before["source/regional_grading.py"])
        self.assertEqual(result["source/regional_sources.py"], self.before["source/regional_sources.py"])

    def test_selected_executable_preserves_small_signed_effect_and_undefined_values(self):
        namespace = {}
        exec(compile(self.composed()[compose.SCORE], "<selected-stable-source>", "exec"), namespace)
        stable_mean = namespace["_stable_mean"]
        self.assertGreater(stable_mean([2.0, 2**-53, -2.0]), 0.0)
        self.assertLess(stable_mean([-2.0, -(2**-53), 2.0]), 0.0)
        self.assertEqual(stable_mean([math.inf, 1.0]), math.inf)
        self.assertTrue(math.isnan(stable_mean([math.inf, -math.inf])))
        self.assertTrue(math.isnan(stable_mean([math.nan, 1.0])))

    def test_tampered_unchanged_dependency_is_refused(self):
        bad = dict(self.before)
        bad["source/regional_grading.py"] += b"\n"
        with self.assertRaises(compose.Refusal):
            compose.compose(bad, self.overlay, self.recipe, compose.RECIPE_PIN)

    def test_missing_or_added_predecessor_source_is_refused(self):
        for bad in (dict(self.before, unexpected=b"x"),
                    {n: b for n, b in self.before.items() if n != "source/regional_scope.py"}):
            with self.assertRaises(compose.Refusal):
                compose.compose(bad, self.overlay, self.recipe, compose.RECIPE_PIN)

    def test_old_scorer_or_stale_nested_manifest_is_refused(self):
        for name in (compose.SCORE, compose.NUMERICAL, "RUNTIME_INVENTORY.json", "DEPENDENCIES.json"):
            bad = dict(self.overlay)
            bad[name] = self.before[name]
            with self.assertRaises(compose.Refusal):
                compose.compose(self.before, bad, self.recipe, compose.RECIPE_PIN)

    def test_unselected_recipe_cannot_authorize_own_replacements(self):
        bad = copy.deepcopy(self.plan)
        bad["readiness_promoted"] = True
        body = json.dumps(bad).encode()
        with self.assertRaises(compose.Refusal):
            compose.compose(self.before, self.overlay, body, compose.pin(body))
        with self.assertRaises(compose.Refusal):
            compose.compose(self.before, self.overlay, self.recipe,
                            {"bytes": len(self.recipe), "sha256": "0" * 64})

    def test_missing_extra_or_corrupt_overlay_is_refused(self):
        for bad in ({n: b for n, b in self.overlay.items() if n != compose.SCORE},
                    dict(self.overlay, unselected=b"x"),
                    dict(self.overlay, **{compose.SCORE: self.overlay[compose.SCORE] + b"\n"})):
            with self.assertRaises(compose.Refusal):
                compose.compose(self.before, bad, self.recipe, compose.RECIPE_PIN)

    def test_write_preflight_and_existing_destination_refuse_before_output(self):
        scratch = HERE.parent / "test-scratch"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            target = Path(temporary)
            with self.assertRaisesRegex(compose.Refusal, "write allowance"):
                compose.materialize(BASE, HERE, target, compose.RECIPE_PIN,
                                    compose.Budget(600000, 1, 30))
            self.assertEqual(list(target.iterdir()), [])
            # Directory evidence is enough: no file or neural payload is written.
            (target / "old").mkdir()
            with self.assertRaisesRegex(compose.Refusal, "Fresh empty"):
                compose.materialize(BASE, HERE, target, compose.RECIPE_PIN,
                                    compose.Budget(600000, 400000, 30))
        scratch.rmdir()

    def test_materialized_successor_passes_unchanged_source_inspector(self):
        scratch = HERE.parent / "test-scratch"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            target = Path(temporary)
            result = compose.materialize(BASE, HERE, target, compose.RECIPE_PIN,
                                         compose.Budget(600000, 400000, 30))
            self.assertEqual(result["source_files"], 35)
            self.assertFalse(result["execution_authority"])
            inspector = module_from_file("n094_successor_source_inspector", target / "operator.py")
            report = json.loads(inspector.inspect(target, result["source_manifest"],
                                                 budget=inspector.Budget(500000, 4096, 30)))
            self.assertEqual(report["source_members"], 29)
            self.assertEqual(report["package_members"], 35)
            self.assertFalse(report["benchmark_modules_imported"])
            self.assertFalse(report["authentic_inputs_opened"])
            self.assertEqual(compose.pin((BASE / "SOURCE_MANIFEST.json").read_bytes()), compose.BASE_PIN)
            self.assertEqual(compose.pin((target / compose.SCORE).read_bytes()), compose.SCORER_PIN)
            print("source_only_materialized_bytes=" + str(result["logical_write_reservation_bytes"]))
        scratch.rmdir()


if __name__ == "__main__":
    unittest.main(verbosity=2)
