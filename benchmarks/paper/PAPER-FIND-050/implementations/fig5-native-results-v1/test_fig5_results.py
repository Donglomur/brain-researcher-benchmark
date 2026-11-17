"""Generated numeric/file controls only; no real data or native kernels."""
import ast
import copy
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("fig5_results", HERE / "fig5_results.py")
results = importlib.util.module_from_spec(spec)
spec.loader.exec_module(results)


def npy(shape, values, dtype="<f8", version=1, fortran=False):
    # Independent file fixture encoder uses the documented NPY layout.
    header = repr({"descr": dtype, "fortran_order": fortran, "shape": shape}).encode()
    prefix = b"\x93NUMPY" + bytes((version, 0))
    prefix_size = 10 if version == 1 else 12
    header += b" " * ((-prefix_size - len(header) - 1) % 64) + b"\n"
    prefix += len(header).to_bytes(2 if version == 1 else 4, "little")
    fmt = {"<f8": "<d", ">f8": ">d", "<i4": "<i", ">i4": ">i"}.get(dtype, "<d")
    return prefix + header + b"".join(struct.pack(fmt, value) for value in values)


def archive(steps, values, shuffled=None, **overrides):
    members = {"acc.npy": npy((20, 50, 3), values),
               "acc_shuff.npy": npy((20, 50, 3), values if shuffled is None else shuffled),
               "wm_isi.npy": npy((50,), steps, "<i4")}
    members.update(overrides)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        for name, body in members.items():
            handle.writestr(name, body)
    return stream.getvalue()


class NativeResultsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        # The replicate coordinate, not the 50 correlated lag points, varies.
        self.values = [rep / 20 for rep in range(20) for lag in range(50) for family in range(3)]

    def prepare(self, role="notebook_producer", overrides=None):
        selected = {"schema": "fig5-archive-selection/v1", "artifact_role": role, "files": []}
        for index, name in enumerate(results.filenames(role)):
            stop = 4500 if index == 2 else 1500
            # Independent arithmetic oracle (positive rational truncation).
            steps = [60 + ((stop - 60) * lag) // 50 for lag in range(50)]
            body = archive(steps, self.values)
            if overrides and index in overrides:
                body = overrides[index](steps, self.values[:])
            (self.root / name).write_bytes(body)
            selected["files"].append({"name": name, "bytes": len(body),
                                      "sha256": hashlib.sha256(body).hexdigest()})
        return selected

    def test_complete_original_curve_support_and_population_sd(self):
        report = results.summarize(self.root, self.prepare())
        self.assertEqual(len(report["curves"]), 360)
        self.assertEqual(sum(len(row["accuracy"]) for row in report["curves"]), 18000)
        self.assertEqual(len(report["summaries"]), 18)
        self.assertEqual(report["missing_accuracy_cells"], 0)
        for row in report["summaries"]:
            self.assertEqual(row["finite_replicates"], [20] * 50)
            self.assertEqual(row["mean_accuracy"], [.475] * 50)
            for sd in row["population_sd"]:
                # Variance of uniform integers 0..19 divided by 20².
                self.assertAlmostEqual(sd, math.sqrt(399 / 12) / 20)
        self.assertEqual(report["panels"][0]["delay_seconds"][-1], 2.942)
        self.assertEqual(report["panels"][2]["delay_seconds"][-1], 8.822)
        self.assertEqual(report["panels"][2]["notebook_examples_per_fold"], 300)
        self.assertIn("paper equivalence unresolved", report["qualification"])
        json.dumps(report, allow_nan=False)

    def test_axes_modes_and_replica_identity_are_preserved(self):
        fixed = [rep / 100 + lag / 1000 + family / 10
                 for rep in range(20) for lag in range(50) for family in range(3)]
        selected = self.prepare(overrides={1: lambda steps, _: archive(steps, fixed, [0.] * 3000)})
        report = results.summarize(self.root, selected)
        row = next(row for row in report["curves"] if row["panel"] == "F5e"
                   and row["mode"] == "fixed_lag" and row["family"] == "echo_state"
                   and row["replicate_index"] == 13)
        self.assertAlmostEqual(row["accuracy"][17], .347)
        row = next(row for row in report["curves"] if row["panel"] == "F5e"
                   and row["mode"] == "time_independent")
        self.assertEqual(row["accuracy"], [0.] * 50)

    def test_nan_propagates_with_full_failure_coordinates(self):
        def broken(steps, values):
            values[(7 * 50 + 11) * 3 + 2] = float("nan")
            return archive(steps, values, [0.] * 3000)
        report = results.summarize(self.root, self.prepare(overrides={2: broken}))
        self.assertEqual(report["numerical_completeness"], "required_unscorable")
        self.assertEqual(report["missing_accuracy_cells"], 1)
        self.assertEqual(report["failed_curve_cells"][0]["delay_indices"], [11])
        row = next(row for row in report["summaries"] if row["panel"] == "F5f"
                   and row["mode"] == "fixed_lag" and row["family"] == "echo_state")
        self.assertIsNone(row["mean_accuracy"][11])
        self.assertIsNone(row["population_sd"][11])
        self.assertEqual(row["finite_replicates"][11], 19)
        self.assertEqual(row["finite_replicates"][12], 20)
        self.assertEqual(len(report["curves"]), 360)
        json.dumps(report, allow_nan=False)

    def test_roles_do_not_alias_or_claim_historical_provenance(self):
        selection = self.prepare("notebook_renderer")
        report = results.summarize(self.root, selection)
        self.assertEqual(report["panels"][0]["source_archive"], "acc_multi2.npz")
        self.assertIn("unresolved lineage", report["limits"][0])
        selection["artifact_role"] = "notebook_producer"
        with self.assertRaises(results.ResultError):
            results.summarize(self.root, selection)

    def test_missing_duplicate_or_unpinned_panels_refused(self):
        selection = self.prepare()
        for changed in (selection["files"][:-1], selection["files"][:2] + selection["files"][:1]):
            bad = copy.deepcopy(selection)
            bad["files"] = changed
            with self.assertRaises(results.ResultError):
                results.summarize(self.root, bad)
        selection["files"][0]["sha256"] = "0" * 64
        with self.assertRaises(results.ResultError):
            results.summarize(self.root, selection)

    def test_wrong_grid_shape_dtype_and_extra_members_refused(self):
        changes = [lambda s, v: archive([n * 2 for n in s], v),
                   lambda s, v: archive(s, v, **{"acc.npy": npy((50, 20, 3), v)}),
                   lambda s, v: archive(s, v, **{"acc.npy": npy((20, 50, 3), v, "|O")} ),
                   lambda s, v: archive(s, v, **{"extra.npy": b"unselected"}),
                   lambda s, v: archive(s, v, **{"acc.npy": npy((20, 50, 3), v, fortran=True)}),
                   lambda s, v: archive(s, v, **{"acc.npy": npy((20, 50, 3), v) + b"extra"})]
        for change in changes:
            with self.subTest(change=change):
                with self.assertRaises(results.ResultError):
                    results.summarize(self.root, self.prepare(overrides={0: change}))

    def test_non_accuracy_values_refused(self):
        for bad in (-.001, 1.001, math.inf, -math.inf):
            def change(steps, values):
                values[5] = bad
                return archive(steps, values)
            with self.subTest(bad=bad), self.assertRaises(results.ResultError):
                results.summarize(self.root, self.prepare(overrides={0: change}))

    def test_big_endian_and_npy_versions(self):
        for version in (1, 2, 3):
            encoded = npy((2,), [.25, .75], ">f8", version)
            self.assertEqual(results._npy(encoded, shape=(2,), kind="float"), [.25, .75])

    def test_repeated_archive_member_refused(self):
        body = io.BytesIO()
        with zipfile.ZipFile(body, "w") as handle:
            handle.writestr("acc.npy", b"one")
            handle.writestr("acc.npy", b"two")
            handle.writestr("wm_isi.npy", b"three")
        with self.assertRaises(results.ResultError):
            results._archive(body.getvalue(), 1500)

    def test_cli_nonzero_for_failed_source_with_report_retained(self):
        selection = self.prepare(overrides={0: lambda s, v: archive(s, [math.nan] * 3000)})
        selection_path = self.root / "selection.json"
        selection_path.write_text(json.dumps(selection))
        completed = subprocess.run([sys.executable, "-I", "-B", str(HERE / "fig5_results.py"),
                                    "--input-root", str(self.root), "--selection", str(selection_path)],
                                   text=True, capture_output=True, check=False)
        self.assertEqual(completed.returncode, 1, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["missing_accuracy_cells"], 6000)
        selection_path.write_text('{"schema":"x","schema":"y"}')
        with self.assertRaises(results.ResultError):
            results.read_selection(selection_path)

    def test_source_pins_and_actual_aggregation_callers(self):
        repository = HERE.parents[4]
        evidence = json.loads((HERE / "SOURCE_EVIDENCE.json").read_text())
        sources = {}
        for record in evidence["local_sources"]:
            # The contract pin records the build's context; integration may
            # legitimately revise that current contract after this component.
            if record["role"] == "current_improvement_contract":
                continue
            source = (repository / record["path"]).read_bytes()
            self.assertEqual(len(source), record["bytes"])
            self.assertEqual(hashlib.sha256(source).hexdigest(), record["sha256"])
            sources[record["role"]] = source
        tree = ast.parse(sources["author_module"])
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "plot_with_time")
        reductions = [n for n in ast.walk(function) if isinstance(n, ast.Call)
                      and isinstance(n.func, ast.Attribute) and n.func.attr in ("mean", "std")]
        self.assertEqual([n.func.attr for n in reductions], ["mean", "std", "mean", "std"])
        self.assertTrue(all(len(n.args) == 1 and ast.literal_eval(n.args[0]) == 0
                            and not n.keywords for n in reductions))
        notebook = json.loads(sources["notebook_code_projection"])
        caller = "".join(next(c["source"] for c in notebook["code_cells"] if c["original_cell_index"] == 2))
        self.assertEqual(caller.count("niter = 20"), 3)
        self.assertIn("nstim = 15", caller)
        self.assertIn("np.linspace(60, tisi,51)[:-1].astype('int32')", caller)


if __name__ == "__main__":
    unittest.main()
