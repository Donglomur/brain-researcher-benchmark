"""Generated file/interface doubles only: no NumPy, arrays or scientific core run."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("artifact_score", HERE / "artifact_score.py")
a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)


class FakeCore:
    json_bytes = staticmethod(a.encoded)

    def __init__(self, action=None):
        self.action = action; self.calls = 0; self.seen = None

    def grade(self, body, schema, loader):
        self.calls += 1; self.seen = (body, schema)
        if self.action:
            return self.action(body, schema, loader)
        refs = loader()
        assert set(refs) == set(a.REFERENCE_PINS)
        return {"status": "scored", "private_loader_calls": 1, "private_reference_reads": 3,
                "all_array_field_errors": {"sentinel": "preserve exact nested score"},
                "all_scientific_report_field_errors": {"every_returned_field": ["unchanged"]},
                "metrics": {"symbolic_test_only": "not a scientific score"},
                "overall_composite_reward": None, "scientific_success": None}


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name).resolve()
        self.sub = self.root / "candidate.zip"; self.sub.write_bytes(b"invented candidate bytes")
        self.refs = self.root / "private"; self.refs.mkdir(); self.pins = {}
        for index, name in enumerate(a.REFERENCE_PINS):
            raw = ("invented reference " + str(index)).encode()
            (self.refs / name).write_bytes(raw); self.pins[name] = a.pin(raw)
        self.output = self.root / "score.json"; self.schema = {"generated": True}

    def tearDown(self):
        for base, dirs, files in os.walk(self.root):
            for name in files:
                p = Path(base) / name
                if not p.is_symlink(): p.chmod(0o600)
        self.temp.cleanup()

    def run_score(self, core=None, refs=None):
        return a.score_artifact(self.sub, refs or self.refs, self.output, core or FakeCore(),
                                self.schema, reference_pins=self.pins)

    def report(self):
        return json.loads(self.output.read_bytes())

    def test_complete_returned_score_preserved_without_new_metric(self):
        core = FakeCore(); summary, code = self.run_score(core)
        self.assertEqual(code, 0); self.assertEqual(core.calls, 1)
        self.assertEqual(core.seen, (b"invented candidate bytes", self.schema))
        self.assertEqual(summary["private_loader_calls"], 1)
        self.assertEqual(summary["private_reference_reads"], 3)
        self.assertEqual(summary["private_reference_read_attempts"], 3)
        expected = FakeCore().grade(core.seen[0], self.schema, lambda: dict(self.pins))
        self.assertEqual(self.output.read_bytes(), a.encoded(expected))
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o400)
        self.assertFalse(summary["protected_execution_attested"])

    def test_public_rejection_never_inspects_private_root(self):
        def invalid(body, schema, loader):
            return {"status": "invalid_submission", "private_loader_calls": 0,
                    "private_reference_reads": 0, "reason": "generated public rejection"}
        summary, code = self.run_score(FakeCore(invalid), self.root / "absent-private")
        self.assertEqual(code, 2); self.assertEqual(summary["private_reference_read_attempts"], 0)
        self.assertEqual(self.report()["status"], "invalid_submission")

    def test_wrong_reference_digest_is_operator_failure_with_counts(self):
        p = self.refs / "windows.npz"; raw = p.read_bytes(); p.write_bytes(b"X" + raw[1:])
        summary, code = self.run_score()
        self.assertEqual(code, 1); self.assertEqual(self.report()["status"], "operator_error")
        self.assertEqual((summary["private_reference_read_attempts"], summary["private_reference_reads"]), (1, 1))

    def test_missing_second_reference_preserves_partial_read_counts(self):
        (self.refs / "paired_vectors.npz").unlink()
        summary, code = self.run_score()
        self.assertEqual(code, 1)
        self.assertEqual((summary["private_reference_read_attempts"], summary["private_reference_reads"]), (2, 1))

    def test_second_callback_cannot_read_private_bodies_again(self):
        def twice(body, schema, loader):
            loader(); loader()
        summary, code = self.run_score(FakeCore(twice))
        self.assertEqual(code, 1)
        self.assertEqual((summary["private_loader_calls"], summary["private_reference_reads"]), (2, 3))

    def test_core_counter_mismatch_is_operator_error(self):
        def wrong(body, schema, loader):
            loader(); return {"status": "scored", "private_loader_calls": 0, "private_reference_reads": 0}
        _, code = self.run_score(FakeCore(wrong)); self.assertEqual(code, 1)
        self.assertIn("counts must agree", self.report()["reason"])

    def test_output_extent_failure_retains_bounded_error(self):
        core = FakeCore(); core.json_bytes = lambda value: b"x" * (a.SCORE_CAP + 1)
        _, code = self.run_score(core); self.assertEqual(code, 1)
        self.assertLess(self.output.stat().st_size, 2000)
        self.assertIn("byte cap", self.report()["reason"])

    def test_existing_output_refused_before_candidate_or_gold(self):
        self.output.write_bytes(b"do not overwrite")
        core = FakeCore()
        with self.assertRaises(a.Refusal): self.run_score(core)
        self.assertEqual(core.calls, 0); self.assertEqual(self.output.read_bytes(), b"do not overwrite")

    def test_candidate_link_refused_before_core(self):
        original = self.root / "source"; self.sub.rename(original); self.sub.symlink_to(original)
        core = FakeCore(); summary, code = self.run_score(core)
        self.assertEqual(code, 1); self.assertEqual(core.calls, 0)
        self.assertEqual(summary["private_reference_read_attempts"], 0)

    def test_candidate_hardlink_refused_before_core(self):
        os.link(self.sub, self.root / "hardlink")
        core = FakeCore(); summary, code = self.run_score(core)
        self.assertEqual(code, 1); self.assertEqual(core.calls, 0)
        self.assertEqual(summary["private_reference_reads"], 0)

    def test_captured_submission_not_reopened_after_core_entry(self):
        original = self.sub.read_bytes(); seen = []
        def replace(body, schema, loader):
            self.sub.write_bytes(b"changed after capture"); seen.append(body)
            loader(); return {"status": "scored", "private_loader_calls": 1, "private_reference_reads": 3}
        summary, code = self.run_score(FakeCore(replace))
        self.assertEqual(code, 0); self.assertEqual(seen, [original])
        self.assertEqual(summary["submission"], a.pin(original))

    def test_changed_source_rejected_before_execution_or_native_import(self):
        core = self.root / "core.py"; core.write_bytes(b"raise AssertionError('must not execute')\n")
        with self.assertRaisesRegex(a.Refusal, "identity mismatch"):
            a.load_science(core, self.root / "absent-schema")

    def test_wrong_schema_rejected_before_source_execution(self):
        core = self.root / "core.py"; raw = b"raise AssertionError('must not execute')\n"; core.write_bytes(raw)
        schema = self.root / "schema.json"; schema.write_bytes(b"{}")
        with mock.patch.object(a, "CORE_PIN", a.pin(raw)):
            with self.assertRaisesRegex(a.Refusal, "identity mismatch"):
                a.load_science(core, schema)

    def test_exact_cli_parameter_names_parse_without_loading_science(self):
        values = a.parser().parse_args(["--core", "core.py", "--schema", "schema.json", "--submission", "candidate.zip",
                                       "--reference-root", "private", "--output", "fresh.json"])
        self.assertEqual(values.reference_root, Path("private")); self.assertEqual(values.output, Path("fresh.json"))


if __name__ == "__main__":
    unittest.main()
