#!/usr/bin/env python3
"""Generated transport checks; no authentic inputs, reference bodies or programs."""
import argparse
import csv
import importlib.util
import io
import json
import os
from pathlib import Path
import resource
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("transport", HERE / "artifact.py")
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)
SCHEMA = SCORER = None
RUN_ROOT = None
PROFILE_ROOT = None
PRIVATE_PINS = PUBLIC_PINS = None


def rss_report(platform_name, native):
    unit, factor = ("bytes", 1) if platform_name == "darwin" else (
        ("KiB", 1024) if platform_name == "linux" else ("unknown_native_unit", None))
    return {"peak_rss_native": native, "peak_rss_native_unit": unit,
            "peak_rss_platform": platform_name,
            "peak_rss_bytes": native * factor if factor is not None else None}


def invented():
    files = {}
    for name, spec in SCHEMA.TABLES.items():
        row = {k: ("H13_Poly_1" if k == "cell_id" else "human" if k == "species" else "1")
               for k in spec["columns"]}
        out = io.StringIO(newline="")
        w = csv.DictWriter(out, fieldnames=spec["columns"]); w.writeheader(); w.writerow(row)
        files[name] = out.getvalue().encode()
    files["summary.json"] = b'{"invented":1}'
    files["interpretation.json"] = b"opaque optional prose, not JSON"
    return files


class Transport(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="fixture-", dir=RUN_ROOT)).resolve()
        self.source = self.root / "source"; self.source.mkdir()
        self.private = self.root / "private"; self.private.mkdir()
        self.files = invented()
        self.assets = {"references": {}}
        for n, b in self.files.items():
            (self.source / n).write_bytes(b)
            if n in SCHEMA.REQUIRED:
                p = self.private / n; p.write_bytes(b)
                self.assets["references"][n] = {"path": str(p.relative_to(self.root)), **A.pin(b)}
        self.attempt = self.root / "attempt"
        self.output = self.root / "score.json"

    def seal(self):
        return A.freeze(self.source, self.attempt, SCHEMA, SCORER, True)["receipt"]

    def grade(self, expected):
        return A.score(self.root, self.attempt, expected, self.output,
                       SCHEMA, SCORER, self.assets)

    def test_complete_capture_and_unchanged_generated_grade(self):
        expected = self.seal()
        self.assertEqual(A.load_attempt(self.attempt, expected, SCHEMA, SCORER), self.files)
        result = self.grade(expected)
        self.assertEqual(result["status"], "scored")
        grade = json.loads(self.output.read_bytes())["grade"]
        self.assertEqual(grade["comparison"]["metrics"]["primary_equal_cell_branch_length_rmse_um"], 0)
        self.assertEqual(grade["private_numeric_reference_loads"], 1)
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)

    def test_finite_wrong_prediction_remains_score(self):
        self.files["branches.csv"] = self.files["branches.csv"].replace(b",1,1\r\n", b",2,1\r\n")
        (self.source / "branches.csv").write_bytes(self.files["branches.csv"])
        expected = self.seal(); self.grade(expected)
        grade = json.loads(self.output.read_bytes())["grade"]
        self.assertEqual(grade["status"], "scored")
        self.assertEqual(grade["comparison"]["metrics"]["primary_equal_cell_branch_length_rmse_um"], 1)

    def test_extra_and_missing_file_rejected_before_attempt(self):
        (self.source / "reproduce.py").write_bytes(b"raise Exception('never execute')")
        with self.assertRaises(A.Refusal): self.seal()
        self.assertFalse(self.attempt.exists())
        (self.source / "reproduce.py").unlink(); (self.source / "cells.csv").unlink()
        with self.assertRaises(A.Refusal): self.seal()
        self.assertFalse(self.attempt.exists())

    def test_malformed_numerics_refused_before_capture(self):
        (self.source / "summary.json").write_bytes(b'{"x":NaN}')
        with self.assertRaises(SCORER.Invalid): self.seal()
        self.assertFalse(self.attempt.exists())

    def test_wrong_receipt_pin_and_mutation_no_private_read(self):
        expected = self.seal()
        original = A.read; private_reads = []
        def traced(p, *a, **kw):
            if Path(p).is_relative_to(self.private): private_reads.append(str(p))
            return original(p, *a, **kw)
        with mock.patch.object(A, "read", traced):
            with self.assertRaises(A.Refusal):
                self.grade({**expected, "sha256": "0" * 64})
            p = self.attempt / "summary.json"; p.chmod(0o600)
            p.write_bytes(b'{"invented":2}'); p.chmod(0o400)
            with self.assertRaises(A.Refusal): self.grade(expected)
        self.assertEqual(private_reads, [])
        self.assertFalse(self.output.exists())

    def test_changed_public_syntax_rejected_even_with_new_receipt_pin(self):
        expected = self.seal()
        self.attempt.chmod(0o700)
        p = self.attempt / "summary.json"; p.chmod(0o600)
        p.write_bytes(b'{"x":NaN}'); p.chmod(0o400)
        rp = self.attempt / "SUBMISSION.json"; rp.chmod(0o600)
        receipt = json.loads(rp.read_bytes())
        receipt["files"]["summary.json"] = A.pin(p.read_bytes())
        receipt["total_bytes"] = sum(x["bytes"] for x in receipt["files"].values())
        raw = A.encoded(receipt, A.RECEIPT_CAP); rp.write_bytes(raw); rp.chmod(0o400)
        self.attempt.chmod(0o500)
        with mock.patch.object(A, "read", wraps=A.read) as read:
            with self.assertRaises(SCORER.Invalid): self.grade(A.pin(raw))
            self.assertFalse(any(Path(c.args[0]).is_relative_to(self.private) for c in read.call_args_list))
        self.assertFalse(self.output.exists())

    def test_private_pin_failure_is_operational(self):
        expected = self.seal()
        (self.private / "summary.json").write_bytes(b'{"invented":9}')
        with self.assertRaises(A.Refusal): self.grade(expected)
        self.assertFalse(self.output.exists())

    def test_seal_modes_and_existing_output_refused(self):
        expected = self.seal()
        self.attempt.chmod(0o700)
        with self.assertRaises(A.Refusal): self.grade(expected)
        self.attempt.chmod(0o500)
        self.output.write_bytes(b"preexisting")
        with mock.patch.object(A, "read", wraps=A.read) as read:
            with self.assertRaises(A.Refusal): self.grade(expected)
            self.assertEqual(read.call_count, 0)
        self.assertEqual(self.output.read_bytes(), b"preexisting")

    def test_symlink_hardlink_and_overlap_refused(self):
        p = self.source / "summary.json"; p.unlink(); p.symlink_to(self.private / "summary.json")
        with self.assertRaises(A.Refusal): self.seal()
        p.unlink(); os.link(self.private / "summary.json", p)
        with self.assertRaises(A.Refusal): self.seal()
        p.unlink(); p.write_bytes(self.files["summary.json"])
        with self.assertRaises(A.Refusal):
            A.freeze(self.source, self.source / "child", SCHEMA, SCORER, True)
        with self.assertRaises(A.Refusal):
            A.freeze(self.source, self.attempt, SCHEMA, SCORER, False)

    def test_missing_topology_does_not_get_subset_score(self):
        # Different generated identity remains syntactically valid; original scorer owns full join.
        b = self.files["branches.csv"].replace(b"H13_Poly_1,1,1", b"H13_Poly_1,2,1")
        (self.source / "branches.csv").write_bytes(b)
        self.grade(self.seal())
        grade = json.loads(self.output.read_bytes())["grade"]
        self.assertEqual(grade["status"], "incomplete_numerical_coverage")
        self.assertIsNone(grade["comparison"]["metrics"])

    def test_exact_source_loader_and_changed_source_refusal(self):
        fake = self.root / "repo"
        for n, pin in A.PINS.items():
            p = fake / n; p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"wrong")
        with self.assertRaises(A.Refusal): A.contracts(fake)

    def test_receipt_schema_and_namespace_refused(self):
        expected = self.seal(); self.attempt.chmod(0o700)
        (self.attempt / "unlisted").write_bytes(b"x"); self.attempt.chmod(0o500)
        with self.assertRaises(A.Refusal): self.grade(expected)

    def test_owned_timeout_refuses_without_work(self):
        with mock.patch.object(A, "contracts", side_effect=TimeoutError("invented deadline")):
            with mock.patch.object(A.signal, "setitimer"):
                with mock.patch.object(A.signal, "signal"):
                    self.assertEqual(A.main(["--profile-root", str(self.root), "--seconds", "1",
                                             "inputs", "--source-root", str(self.source), "--destination", str(self.root / "new")]), 2)
        self.assertFalse((self.root / "new").exists())


class Relocation(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="relocation-", dir=RUN_ROOT)).resolve()

    def test_public_descriptor_mapping_preserves_complete_identity(self):
        inputs = PUBLIC_PINS["public_inputs"]
        references = PRIVATE_PINS["references"]
        self.assertEqual(len(inputs), 15)
        self.assertEqual(sum(p["bytes"] for p in inputs.values()), 11990405)
        self.assertEqual(set(references), set(SCHEMA.REQUIRED))
        for mapping in (inputs, references):
            for name, row in mapping.items():
                self.assertEqual(row["path"], name)
                self.assertFalse(Path(name).is_absolute())
                self.assertNotIn("..", Path(name).parts)

    def test_peak_rss_units(self):
        self.assertEqual(rss_report("darwin", 123)["peak_rss_bytes"], 123)
        self.assertEqual(rss_report("linux", 123)["peak_rss_bytes"], 125952)
        other = rss_report("unknown-platform", 123)
        self.assertIsNone(other["peak_rss_bytes"])
        self.assertEqual(other["peak_rss_native"], 123)
        self.assertEqual(other["peak_rss_native_unit"], "unknown_native_unit")

    def test_six_file_relocation_and_changed_descriptor_refusal(self):
        for n in A.PINS:
            (self.root / n).write_bytes((PROFILE_ROOT / n).read_bytes())
        schema, scorer, private, public = A.contracts(self.root)
        self.assertEqual(schema.CAPS, SCHEMA.CAPS)
        self.assertEqual(private, PRIVATE_PINS)
        self.assertEqual(public, PUBLIC_PINS)
        self.assertEqual(scorer.S.CELLS, SCHEMA.CELLS)
        (self.root / "REFERENCE_PINS.json").write_bytes(b"{}")
        with self.assertRaises(A.Refusal): A.contracts(self.root)

    def test_CLI_uses_explicit_external_roots(self):
        source = self.root / "inputs"; reference = self.root / "reference"
        with mock.patch.object(A, "copy_inputs", return_value={}) as copy:
            with mock.patch("builtins.print"):
                result = A.main(["--profile-root", str(PROFILE_ROOT), "--seconds", "5",
                    "inputs", "--source-root", str(source), "--destination", str(self.root / "new")])
            self.assertEqual(result, 0)
            self.assertEqual(copy.call_args.args[0], str(source))
            self.assertEqual(copy.call_args.args[2], PUBLIC_PINS)
        with mock.patch.object(A, "score", return_value={}) as score:
            with mock.patch("builtins.print"):
                result = A.main(["--profile-root", str(PROFILE_ROOT), "--seconds", "5",
                    "score", "--reference-root", str(reference), "--attempt", str(self.root / "attempt"),
                    "--receipt-bytes", "100", "--receipt-sha256", "a" * 64,
                    "--output", str(self.root / "score.json")])
            self.assertEqual(result, 0)
            self.assertEqual(score.call_args.args[0], str(reference))
            self.assertEqual(score.call_args.args[-1], PRIVATE_PINS)

    def test_wrong_provider_payload_refused_and_partial_retained(self):
        source = self.root / "provider"; source.mkdir()
        (source / "SCHEMA.json").write_bytes(b"wrong")
        destination = self.root / "copy"
        with self.assertRaises(A.Refusal): A.copy_inputs(source, destination, PUBLIC_PINS)
        self.assertTrue(destination.is_dir())
        self.assertEqual(list(destination.iterdir()), [])


def main():
    global SCHEMA, SCORER, RUN_ROOT, PROFILE_ROOT, PRIVATE_PINS, PUBLIC_PINS
    p = argparse.ArgumentParser(); p.add_argument("--profile-root", required=True)
    p.add_argument("--output-root", required=True)
    p.add_argument("--relocation-only", action="store_true")
    args = p.parse_args()
    root = Path(args.output_root).absolute(); root.mkdir()
    RUN_ROOT = root
    start = time.monotonic(); cpu = time.process_time()
    PROFILE_ROOT = Path(args.profile_root).resolve()
    SCHEMA, SCORER, PRIVATE_PINS, PUBLIC_PINS = A.contracts(PROFILE_ROOT)
    suite = unittest.TestSuite()
    classes = (Relocation,) if args.relocation_only else (Transport, Relocation)
    for cls in classes:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {"cases": result.testsRun, "passed": result.wasSuccessful(),
              "failure_cases": [str(x[0]) for x in result.failures],
              "error_cases": [str(x[0]) for x in result.errors],
              "wall_seconds": time.monotonic() - start,
              "CPU_seconds": time.process_time() - cpu,
              **rss_report(sys.platform, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
              "authentic_payload_reads": 0, "authentic_science_runs": 0,
              "relocation_only": args.relocation_only,
              "fixture_scope": "Tiny invented files, transport and original API only; not full-ten-tree validation"}
    (root / "RESULTS.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
