"""Source application and invented projection controls; no OCaml execution."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("consensus_source_correction", HERE / "correct_sources.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def emitted_map(branch, n, i):
    """Read the exact tiny emitted integer-map shape, then model its arithmetic.

    This checks the replacement expression, not installed Base/Owl semantics or
    OCaml parsing. An OCaml compilation/native parity test remains outstanding.
    """
    text = re.sub(r"\s+", " ", branch.decode())
    expected = "List.init Int.(n_neurons - 1) ~f:(fun j -> if Int.(j < i) then j else Int.(j + 1))"
    if text.count(expected) != 1 or "if Int.(n_neurons < 2 || i < 0 || i >= n_neurons)" not in text:
        raise ValueError("unexpected emitted integer map")
    if type(n) is not int or type(i) is not int or n < 2 or i < 0 or i >= n:
        raise ValueError("invalid population/index")
    return [j if j < i else j + 1 for j in range(n - 1)]


def select_columns(rows, indices):
    return [[row[i] for i in indices] for row in rows]


class Projection(unittest.TestCase):
    def test_all_other_indices_first_interior_last(self):
        for n in range(2, 65):
            for target in range(n):
                expected = list(range(n)); expected.remove(target)
                for source in (c.WRAPPER_BRANCH, c.ANALYSIS_BRANCH):
                    observed = emitted_map(source, n, target)
                    self.assertEqual(observed, expected)
                    self.assertEqual(len(set(observed)), n - 1)
                    self.assertNotIn(target, observed)
        for n, i in ((1, 0), (0, 0), (3, -1), (3, 3)):
            with self.assertRaises(ValueError):
                emitted_map(c.ANALYSIS_BRANCH, n, i)

    def test_original_interior_counterexample(self):
        # Conditional on explicit-index L semantics, the original expression
        # selects [0,3,4,6] for n7/held3: includes3 and omits1,2,5.
        old = [0, 3, 4, 6]
        fixed = emitted_map(c.ANALYSIS_BRANCH, 7, 3)
        self.assertIn(3, old)
        self.assertEqual(fixed, [0, 1, 2, 4, 5, 6])
        original = [[10 * time + neuron for neuron in range(7)] for time in range(4)]
        changed = copy.deepcopy(original)
        for row in changed: row[3] += 10000
        self.assertNotEqual(select_columns(original, old), select_columns(changed, old))
        self.assertEqual(select_columns(original, fixed), select_columns(changed, fixed))
        self.assertNotEqual(select_columns(original, [3]), select_columns(changed, [3]))

    def test_noninterference_and_aligned_parameters_complete_declared_scope(self):
        # Seven animals and all three folds, with unequal LM/V1 sizes. Every
        # target, including region-boundary targets, is tested; no246 forced.
        animals = ("MPV17_FB_5", "MPV18_FB_5", "MPV31_FF_5", "MPV33_FF_5", "MPV34_FF_5", "VL63_FF_5", "VL66_FB_5")
        count = 0
        for a, animal in enumerate(animals):
            lm, v1 = 2 + a % 3, 3 + a % 2
            n = lm + v1
            for fold in range(3):
                data = [[100 * a + 10 * fold + 3 * t + j for j in range(n)] for t in range(6)]
                parameters = {"c": [[j, j + 1, j + 2] for j in range(n)],
                              "c_mask": [[1, j % 2, 1] for j in range(n)],
                              "bias": [2 * j for j in range(n)], "gain": [j + 1 for j in range(n)],
                              "scales": [2, 3, 5, 7]}
                for target in range(n):
                    observed = emitted_map(c.WRAPPER_BRANCH, n, target)
                    analysis = emitted_map(c.ANALYSIS_BRANCH, n, target)
                    self.assertEqual(observed, analysis)
                    altered = copy.deepcopy(data)
                    for row in altered: row[target] += 1000
                    self.assertEqual(select_columns(data, analysis), select_columns(altered, analysis))
                    for name in ("c", "c_mask", "bias", "gain"):
                        expected = copy.deepcopy(parameters[name]); expected.pop(target)
                        self.assertEqual([parameters[name][j] for j in observed], expected)
                    self.assertEqual(parameters["scales"], [2, 3, 5, 7])
                    observation = select_columns(data, analysis)
                    observation[0][0] += 1000
                    self.assertNotEqual(observation, select_columns(data, analysis))
                    self.assertEqual(data[0][target], 100 * a + 10 * fold + target)
                    count += 1
        self.assertEqual(count, 132)


class OwnerSourceIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = os.environ.get("CONSENSUS_SOURCE_ROOT")
        if root is None:
            raise unittest.SkipTest("owner-supplied pinned upstream sources absent; integration not verified")
        root = Path(root).resolve()
        declared = json.loads((HERE / "SOURCE_INPUTS.json").read_bytes())
        cls.bindings = {"sources": {role: {"original_path": str(root / row["destination"])}
                                   for role, row in declared["source_roles"].items()}}
        cls.originals = {role: c.read_original(row["original_path"])
                         for role, row in cls.bindings["sources"].items()}

    def test_complete_exact_application_and_unchanged_consumers(self):
        outputs, report = c.render(self.originals)
        self.assertEqual(len(outputs), 3)
        self.assertFalse(report["native_compilation_or_execution"])
        for role, (path, _, _, start, end, _) in c.SOURCES.items():
            new = c.ANALYSIS_BRANCH if role == "analysis" else c.WRAPPER_BRANCH
            self.assertEqual(outputs[path], self.originals[role][:start] + new + self.originals[role][end:])
            self.assertEqual(outputs[path].count(b"L observed_indices"), 1)
            self.assertNotIn(b"L (List.concat [ [ 0; i ]; [ i + 1; -1 ] ])", outputs[path])
            if role == "analysis":
                self.assertEqual(outputs[path].split(b"  let simulate_laser\n", 1)[1],
                                 self.originals[role].split(b"  let simulate_laser\n", 1)[1])
                self.assertEqual(outputs[path].count(b"AD.Maths.get_fancy slice_train (G.L.extract_output (Data.o dat))"), 2)
            if role != "analysis":
                # C, c_mask, bias and gain all continue to use the same slice;
                # four latent-population scales remain unchanged, not neuronwise.
                for token in (b"transpose (AD.Maths.get_fancy slice AD.Maths.(transpose c))",
                              b"transpose (AD.Maths.get_fancy slice AD.Maths.(transpose block_c))",
                              b"AD.Maths.get_fancy slice bias", b"AD.Maths.get_fancy slice gain",
                              b"scales = pinned scales"):
                    self.assertIn(token, outputs[path])

    def test_all_inputs_admitted_before_output_and_no_silent_repatch(self):
        with tempfile.TemporaryDirectory() as td:
            for role in c.SOURCES:
                changed = dict(self.originals)
                changed[role] += b"\n"
                dest = Path(td) / role
                with self.assertRaisesRegex(ValueError, "exact original identity"):
                    c.materialize(changed, dest)
                self.assertFalse(dest.exists())
            changed = dict(self.originals); changed.pop("analysis")
            with self.assertRaisesRegex(ValueError, "complete three"):
                c.render(changed)
            outputs, _ = c.render(self.originals)
            already = {role: outputs[row[0]] for role, row in c.SOURCES.items()}
            with self.assertRaisesRegex(ValueError, "exact original identity"):
                c.render(already)

    def test_real_cli_source_materialization_and_stale_refusal(self):
        with tempfile.TemporaryDirectory(prefix="consensus corrected source ") as td:
            out = Path(td) / "corrected"
            command = [sys.executable, "-I", "-S", "-B", str(HERE / "correct_sources.py")]
            for role in ("fit", "analyze", "analysis"):
                command.extend(["--" + role + "-source", self.bindings["sources"][role]["original_path"]])
            command.extend(["--output", str(out)])
            result = subprocess.run(command, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            expected, report = c.render(self.originals)
            self.assertEqual(json.loads((out / "CORRECTION_REPORT.json").read_bytes()), report)
            self.assertEqual({p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()},
                             set(expected) | {"CORRECTION_REPORT.json"})
            for path, raw in expected.items(): self.assertEqual((out / path).read_bytes(), raw)
            before = (out / "CORRECTION_REPORT.json").read_bytes()
            result = subprocess.run(command, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 2)
            self.assertEqual((out / "CORRECTION_REPORT.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
