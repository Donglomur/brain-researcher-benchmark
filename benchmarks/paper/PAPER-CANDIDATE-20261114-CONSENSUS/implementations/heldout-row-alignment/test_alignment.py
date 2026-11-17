"""Generated controls and optional exact-upstream source integration; no native run."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("align_sources", HERE / "align_sources.py")
alignment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(alignment)


class GeneratedControls(unittest.TestCase):
    def test_changed_predecessor_is_refused_before_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            successor = root / "heldout-row-alignment"
            previous = root / "held-neuron"
            successor.mkdir()
            previous.mkdir()
            shutil.copyfile(HERE / "align_sources.py", successor / "align_sources.py")
            original = (HERE.parent / "held-neuron" / "correct_sources.py").read_bytes()
            (previous / "correct_sources.py").write_bytes(original + b"\nraise RuntimeError('must not execute')\n")
            result = subprocess.run([
                sys.executable, "-I", "-S", "-B", str(successor / "align_sources.py"),
                "--fit-source", "absent", "--analyze-source", "absent", "--analysis-source", "absent",
                "--output", str(root / "output")], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2)
            self.assertIn("exact reviewed held-neuron predecessor required", result.stderr)
            self.assertNotIn("must not execute", result.stderr)
            self.assertFalse((root / "output").exists())

    def test_counterexample_and_all_companion_rows(self):
        # Distinct occurrence tokens include repeated source trial identities.
        # These are invented values, not an asserted authentic axis geometry.
        source_ids = [19, 4, 19, 7]
        occurrences = ["a", "b", "c", "d"]
        reverse = [3, 2, 1, 0]  # Actual source comparator b-a uses positions.
        indexed_ids = [source_ids[k] for k in reverse]
        self.assertEqual(indexed_ids, [7, 19, 4, 19])
        self.assertNotEqual(indexed_ids, sorted(source_ids))
        old_time_rows = [[k, k + 10] for k in range(4)]
        indexed_totals = [sum(old_time_rows[k]) for k in reverse]
        self.assertNotEqual([sum(row) for row in old_time_rows], indexed_totals)
        # Interpret only the four simple indexed-let statements emitted by the
        # source insertion. This checks transformation intent, not Owl execution.
        assignments = re.findall(rb"let (\w+) = Arr.get_fancy \[ L argsorted_ids \] (\w+) in",
                                 alignment.INSERTION)
        self.assertEqual(len(assignments), 4)
        state = {
            "ll_neuron_time": old_time_rows,
            "pred_var_os": [("o", key) for key in occurrences],
            "pred_var_us": [("u", key) for key in occurrences],
            "pred_zs": [("z", key) for key in occurrences],
        }
        for lhs, rhs in assignments:
            lhs, rhs = lhs.decode(), rhs.decode()
            state[lhs] = [state[rhs][k] for k in reverse]
        self.assertEqual([sum(row) for row in state["ll_neuron_time"]], indexed_totals)
        for field, label in (("pred_var_os", "o"), ("pred_var_us", "u"), ("pred_zs", "z")):
            self.assertEqual(state[field], [(label, key) for key in ["d", "c", "b", "a"]])

    def test_partial_consumer_set_is_refused(self):
        for originals in ({}, {"fit": b""}, {"fit": b"", "analyze": b"", "analysis": b"", "extra": b""}):
            with self.subTest(consumers=list(originals)), self.assertRaisesRegex(ValueError, "complete three-consumer"):
                alignment.render(originals)

    def test_wrong_sources_refused_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "source"
            with self.assertRaisesRegex(ValueError, "exact original identity"):
                alignment.materialize({role: b"invented wrong source" for role in
                                       ("fit", "analyze", "analysis")}, destination)
            self.assertFalse(destination.exists())


class OwnerSourceIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        names = {role: "CONSENSUS_" + role.upper() + "_SOURCE"
                 for role in ("fit", "analyze", "analysis")}
        supplied = {role: os.environ.get(name) for role, name in names.items()}
        if not any(supplied.values()):
            raise unittest.SkipTest("exact external upstream sources not supplied; no native qualification")
        if not all(supplied.values()):
            raise ValueError("supply all three CONSENSUS_*_SOURCE variables")
        cls.paths = supplied
        cls.predecessor = alignment.load_predecessor()
        cls.originals = {role: cls.predecessor.read_original(path) for role, path in supplied.items()}

    def test_exact_composition_and_unchanged_score_path(self):
        earlier, _ = self.predecessor.render(self.originals)
        outputs, report = alignment.render(self.originals)
        self.assertEqual(outputs["lib/analysis.ml"], earlier["lib/analysis.ml"])
        for row in report["row_alignment_insertions"]:
            before, after = earlier[row["path"]], outputs[row["path"]]
            offset = row["predecessor_insertion_offset"]
            self.assertEqual(after[:offset] + after[offset + len(alignment.INSERTION):], before)
            # Reordering ll_time before summing it would double-permute LL totals.
            prefix = after[:offset]
            self.assertGreater(prefix.rfind(b"Arr.get_fancy [ L argsorted_ids ] num_time"),
                               prefix.rfind(b"let ll_neuron = Arr.sum ~axis:1 ll_neuron_time"))
            self.assertTrue(after[offset + len(alignment.INSERTION):].startswith(b"          ( ll_neuron_time\n"))
            self.assertEqual(after.count(alignment.INSERTION), 1)
        self.assertFalse(report["historical_parity"])
        self.assertFalse(report["scientific_qualification"])

    def test_every_original_is_authenticated(self):
        for role in self.originals:
            bad = dict(self.originals)
            raw = bytearray(bad[role])
            raw[-1] ^= 1
            bad[role] = bytes(raw)
            with self.subTest(role=role), self.assertRaisesRegex(ValueError, "exact original identity"):
                alignment.render(bad)

    def test_materialize_and_refuse_existing_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "successor"
            report = alignment.materialize(self.originals, destination)
            outputs, _ = alignment.render(self.originals)
            for path, raw in outputs.items():
                self.assertEqual((destination / path).read_bytes(), raw)
            self.assertEqual(json.loads((destination / "ROW_ALIGNMENT_REPORT.json").read_text()), report)
            with self.assertRaises(FileExistsError):
                alignment.materialize(self.originals, destination)

    def test_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "source"
            argv = [sys.executable, "-I", "-S", "-B", str(HERE / "align_sources.py")]
            for role, path in self.paths.items():
                argv.extend(["--" + role + "-source", path])
            result = subprocess.run(argv + ["--output", str(destination)], capture_output=True,
                                    text=True, timeout=10, check=True)
            self.assertEqual(json.loads(result.stdout)["row_alignment_entrypoints"], 2)
            self.assertTrue((destination / "ROW_ALIGNMENT_REPORT.json").is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
