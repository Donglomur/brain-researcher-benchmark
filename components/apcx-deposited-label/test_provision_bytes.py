"""Invented transport regressions; authentic cohort validation remains separate."""
import hashlib
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

import task


class ProvisionByteControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        self.output = self.root / "bundle"
        self.args = types.SimpleNamespace(inputs=self.inputs, output=self.output)
        self.budget = task.budget()

    def fixture(self, first=None):
        rows = {}
        bodies = {}
        for i, name in enumerate(task.PROFILE_FILES):
            # An original int-key dictionary sorts 2 before 10. JSON decoding
            # converts keys to strings, whose canonical order is 10 before 2.
            body = task.core.canonical({"invented": True, "flags": {2: [], 10: [i]}})
            if i == 0 and first is not None:
                body = first
            (self.inputs / name).write_bytes(body)
            bodies[name] = body
            rows[name] = {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
        return {"accepted_profile_inputs": rows}, bodies

    def test_original_numeric_key_encoding_survives_provision(self):
        cfg, bodies = self.fixture()
        original = bodies[task.PROFILE_FILES[0]]
        self.assertNotEqual(task.core.canonical(task.json_interface.decode(original)), original)
        # Isolate transport from the separate full authentic-cohort validator.
        with mock.patch.object(task, "config", return_value=cfg), \
                mock.patch.object(task, "finish_bundle", return_value={"invented_only": True}) as finish:
            result = task.provision(self.args, self.budget)
        self.assertEqual(result, {"invented_only": True})
        finish.assert_called_once_with(self.output, self.budget, "exact_authentic86_accepted_profile_inputs")
        for name, body in bodies.items():
            self.assertEqual((self.output / name).read_bytes(), body)
            self.assertEqual((self.inputs / name).read_bytes(), body)
        self.assertEqual(self.budget.used["input_bytes"], sum(map(len, bodies.values())))
        self.assertEqual(self.budget.used["retained_bytes"], sum(map(len, bodies.values())))

    def test_authenticated_whitespace_is_preserved(self):
        original = b'{ "invented": true, "x": 1 }\n'
        cfg, _ = self.fixture(original)
        with mock.patch.object(task, "config", return_value=cfg), \
                mock.patch.object(task, "finish_bundle", return_value={}):
            task.provision(self.args, self.budget)
        self.assertEqual((self.output / task.PROFILE_FILES[0]).read_bytes(), original)

    def assert_invalid_first(self, body, message=None):
        cfg, _ = self.fixture(body)
        with mock.patch.object(task, "config", return_value=cfg), \
                mock.patch.object(task, "finish_bundle") as finish:
            if message is None:
                with self.assertRaises(ValueError):
                    task.provision(self.args, self.budget)
            else:
                with self.assertRaisesRegex(ValueError, message):
                    task.provision(self.args, self.budget)
        finish.assert_not_called()
        self.assertEqual(list(self.output.iterdir()), [])

    def test_duplicate_json_keys_still_refused_before_copy(self):
        self.assert_invalid_first(b'{"invented":true,"x":1,"x":2}\n')

    def test_nonfinite_json_still_refused_before_copy(self):
        self.assert_invalid_first(b'{"invented":true,"x":NaN}\n')

    def test_wrong_original_hash_still_refused_before_copy(self):
        cfg, _ = self.fixture()
        cfg["accepted_profile_inputs"][task.PROFILE_FILES[0]]["sha256"] = "0" * 64
        with mock.patch.object(task, "config", return_value=cfg), \
                mock.patch.object(task, "finish_bundle") as finish:
            with self.assertRaisesRegex(ValueError, "exact input SHA-256"):
                task.provision(self.args, self.budget)
        finish.assert_not_called()
        self.assertEqual(list(self.output.iterdir()), [])

    def test_complete_cohort_audit_is_required_before_manifest(self):
        cfg, bodies = self.fixture()
        # Keep the real finish_bundle path; only its scientific predicate is
        # replaced by a deliberate rejection of this invented tiny cohort.
        with mock.patch.object(task, "config", return_value=cfg), \
                mock.patch.object(task, "audit_pair", side_effect=ValueError("invented cohort refusal")) as audit:
            with self.assertRaisesRegex(ValueError, "invented cohort refusal"):
                task.provision(self.args, self.budget)
        audit.assert_called_once()
        self.assertFalse((self.output / "BUNDLE.json").exists())
        self.assertEqual({p.name for p in self.output.iterdir()}, set(bodies))
        for name, body in bodies.items():
            self.assertEqual((self.output / name).read_bytes(), body)

    def test_byte_writer_rejects_nonbytes_before_output(self):
        path = self.root / "not-bytes"
        with self.assertRaisesRegex(ValueError, "exact output bytes"):
            task.write_bytes(path, "abc", self.budget)
        self.assertFalse(path.exists())

    def test_byte_writer_checks_extent_before_output(self):
        path = self.root / "too-large"
        with self.assertRaisesRegex(ValueError, "whole output-file bound"):
            task.write_bytes(path, b"abc", self.budget, maximum=2)
        self.assertFalse(path.exists())
        self.assertEqual(self.budget.used["retained_bytes"], 0)

    def test_byte_writer_never_replaces_existing_output(self):
        path = self.root / "existing"
        path.write_bytes(b"original")
        with self.assertRaises(FileExistsError):
            task.write_bytes(path, b"replacement", self.budget)
        self.assertEqual(path.read_bytes(), b"original")

    def test_json_writer_keeps_its_canonical_contract(self):
        value = {"invented": True, "flags": {2: [], 10: [1]}}
        path = self.root / "canonical.json"
        pin = task.write_json(path, value, self.budget)
        expected = task.core.canonical(value)
        self.assertEqual(path.read_bytes(), expected)
        self.assertEqual(pin, {"bytes": len(expected), "sha256": hashlib.sha256(expected).hexdigest()})


if __name__ == "__main__":
    unittest.main()
