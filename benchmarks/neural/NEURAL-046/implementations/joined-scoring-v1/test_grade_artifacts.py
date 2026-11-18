"""Generated artifact controls; no neural observations, fits or candidate execution."""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


grader = load("neural046_artifact_grader", HERE / "grade_artifacts.py")
prior = load("neural046_join_fixture", HERE / "test_score.py")
WRITTEN = 0


def write(path, raw):
    global WRITTEN
    Path(path).write_bytes(raw)
    WRITTEN += len(raw)


class ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="n046-artifacts-",
                                              dir=os.environ.get("NEURAL046_TEST_TMP"))
        cls.root = Path(cls.tmp.name)
        cls.bundle = cls.root / "bundle"
        cls.bundle.mkdir()
        p, s, z, b, h = prior.fixture()
        cls.values = dict(public=p, submission=s, sensitivity=z, binding=b,
                          private=h, closure=prior.seal(p, s, z, b))
        cls.manifest = {"schema": "neural046-joined-artifacts-v1", "inputs": {},
                        "limits": {"max_file_bytes": 16384, "max_total_bytes": 65536,
                                   "max_report_bytes": 16384}}
        for name, value in cls.values.items():
            raw = grader.encode(value)
            write(cls.bundle / (name + ".json"), raw)
            cls.manifest["inputs"][name] = {"path": name + ".json", "bytes": len(raw),
                                            "sha256": hashlib.sha256(raw).hexdigest()}
        write(cls.bundle / "manifest.json", grader.encode(cls.manifest))
        original = grader.exclusive_write

        def counted(path, raw):
            global WRITTEN
            original(path, raw)
            WRITTEN += len(raw)

        cls.writer = patch.object(grader, "exclusive_write", counted)
        cls.writer.start()

    @classmethod
    def tearDownClass(cls):
        cls.writer.stop()
        cls.tmp.cleanup()
        print("GENERATED_ARTIFACT_BYTES_WRITTEN=" + str(WRITTEN))

    def setUp(self):
        self.state = self.root / self._testMethodName
        self.state.mkdir()
        self.output = self.state / "report.json"

    @contextmanager
    def altered(self, replacements=None, manifest_mutator=None):
        saved = {"manifest.json": (self.bundle / "manifest.json").read_bytes()}
        manifest = deepcopy(self.manifest)
        try:
            for name, value in (replacements or {}).items():
                filename = name + ".json"
                saved[filename] = (self.bundle / filename).read_bytes()
                raw = value if type(value) is bytes else grader.encode(value)
                write(self.bundle / filename, raw)
                manifest["inputs"][name].update(bytes=len(raw), sha256=grader.sha256(raw))
            if manifest_mutator:
                manifest_mutator(manifest)
            write(self.bundle / "manifest.json", grader.encode(manifest))
            yield manifest
        finally:
            for name, raw in saved.items():
                write(self.bundle / name, raw)

    def run_grade(self):
        return grader.grade_bundle(self.bundle, self.state, self.output)

    def before_targets(self, expected):
        original = grader.read_descriptor
        reads = []

        def observe(root, descriptor):
            reads.append(descriptor["path"])
            return original(root, descriptor)

        with patch.object(grader, "read_descriptor", observe):
            with self.assertRaisesRegex(ValueError, expected):
                self.run_grade()
        self.assertNotIn("private.json", reads)
        self.assertEqual(list(self.state.iterdir()), [])

    def test_real_join_path_preserves_hand_computed_macro_and_sensitivity(self):
        report = self.run_grade()
        self.assertEqual(report["result"]["metrics"]["models"]["M0"]["animal_macro_mse"], 35.5)
        self.assertEqual(report["result"]["metrics"]["contrasts"]["Delta"], 3.)
        self.assertEqual(report["result"]["mandatory_sensitivity"]["MEN_independently_tuned"]
                         ["animal_macro_mse"], 2.)
        self.assertFalse(report["scientific_qualification"])
        self.assertFalse(report["custody"]["production_sandbox_qualified"])
        self.assertEqual(json.loads(self.output.read_text()), report)
        marker = self.state / report["custody"]["consumption_marker"]
        self.assertEqual(json.loads(marker.read_text())["target_access_state"],
                         "consumed_before_private_read")

    def test_shuffled_targets_retain_identity_pairing(self):
        with self.altered({"private": list(reversed(self.values["private"]))}):
            report = self.run_grade()
        self.assertEqual(report["result"]["metrics"]["contrasts"]["Delta"], 3.)
        self.assertEqual(report["result"]["mandatory_sensitivity"]["MEN_independently_tuned"]
                         ["animal_macro_mse"], 2.)

    def test_missing_sensitivity_case_fails_before_private_read(self):
        z = deepcopy(self.values["sensitivity"])
        del z["MEN_independently_tuned"]["native-0"]
        closure = deepcopy(self.values["closure"])
        closure["sensitivity_digest"] = prior.scorer.digest(z)
        with self.altered({"sensitivity": z, "closure": closure}):
            self.before_targets("sensitivity_case_join")

    def test_unsealed_producer_fails_before_private_read(self):
        closure = deepcopy(self.values["closure"])
        closure["all_required_producers_closed"] = False
        with self.altered({"closure": closure}):
            self.before_targets("target_last_closure_required")

    def test_public_file_identity_mismatch_fails_before_private_read(self):
        def mutate(m):
            m["inputs"]["public"]["sha256"] = "0" * 64
        with self.altered(manifest_mutator=mutate):
            self.before_targets("artifact_identity_mismatch")

    def test_duplicate_members_and_nonrepresentable_numbers_rejected_before_private(self):
        for raw, reason in ((b'{"x":1,"x":2}', "duplicate_json_member"),
                            (b'{"x":NaN}', "nonfinite_number"),
                            (b'{"x":1e999}', "nonfinite_number"),
                            (b'{"x":1e-999}', "literal_underflow"),
                            (b'{"x":"\\ud800"}', "invalid_json")):
            with self.subTest(raw=raw), self.altered({"submission": raw}):
                self.before_targets(reason)

    def test_fixed_roster_prevents_path_traversal_and_input_omission(self):
        for change in (lambda m: m["inputs"]["private"].update(path="../targets.json"),
                       lambda m: m["inputs"].pop("binding")):
            with self.altered(manifest_mutator=change):
                self.before_targets("fixed_input_path|input_roster")

    def test_declared_resource_limits_fail_before_payload_read(self):
        for change in (lambda m: m["inputs"]["private"].update(bytes=16385),
                       lambda m: m["limits"].update(max_total_bytes=1),
                       lambda m: m["limits"].update(max_file_bytes=True)):
            with self.altered(manifest_mutator=change):
                self.before_targets("descriptor_size|total_input_cap|invalid_limit")

    def test_symlink_input_rejected_without_opening_private(self):
        path = self.bundle / "public.json"
        backup = self.bundle / "public.saved"
        path.rename(backup)
        path.symlink_to(backup.name)
        try:
            with self.assertRaises(OSError):
                self.run_grade()
            self.assertEqual(list(self.state.iterdir()), [])
        finally:
            path.unlink()
            backup.rename(path)

    def test_private_identity_failure_consumes_attempt_before_target_read(self):
        def mutate(m):
            m["inputs"]["private"]["sha256"] = "0" * 64
        with self.altered(manifest_mutator=mutate):
            with self.assertRaisesRegex(ValueError, "artifact_identity_mismatch"):
                self.run_grade()
            self.assertEqual(len(list(self.state.glob("*.consumed.json"))), 1)
            with self.assertRaisesRegex(ValueError, "grading_already_consumed"):
                self.run_grade()
            self.assertFalse(self.output.exists())

    def test_fifo_input_is_rejected_without_waiting_for_a_writer(self):
        path = self.bundle / "public.json"
        backup = self.bundle / "public.saved"
        path.rename(backup)
        os.mkfifo(path)
        try:
            self.before_targets("nonregular_file")
        finally:
            path.unlink()
            backup.rename(path)

    def test_private_metadata_rejection_keeps_consumption_evidence(self):
        hidden = deepcopy(self.values["private"])
        hidden[-1]["endpoint"] = "reward"
        with self.altered({"private": hidden}):
            with self.assertRaisesRegex(ValueError, "private_metadata_changed"):
                self.run_grade()
            self.assertEqual(len(list(self.state.glob("*.consumed.json"))), 1)
            self.assertFalse(self.output.exists())

    def test_formatting_or_report_path_changes_cannot_repeat_consumed_manifest(self):
        self.run_grade()
        self.output = self.state / "different-report.json"
        path = self.bundle / "manifest.json"
        original = path.read_bytes()
        try:
            write(path, json.dumps(self.manifest, indent=2).encode())
            with patch.object(grader, "read_descriptor", side_effect=AssertionError("reopened")):
                with self.assertRaisesRegex(ValueError, "grading_already_consumed"):
                    self.run_grade()
        finally:
            write(path, original)

    def test_report_cap_failure_is_consumed_and_cannot_selectively_retry(self):
        def mutate(m):
            m["limits"]["max_report_bytes"] = 1
        with self.altered(manifest_mutator=mutate):
            with self.assertRaisesRegex(ValueError, "report_size_cap"):
                self.run_grade()
            self.assertEqual(len(list(self.state.glob("*.consumed.json"))), 1)
            with self.assertRaisesRegex(ValueError, "grading_already_consumed"):
                self.run_grade()
            self.assertFalse(self.output.exists())

    def test_existing_report_is_not_overwritten(self):
        write(self.output, b"existing result\n")
        with self.assertRaisesRegex(ValueError, "report_exists"):
            self.run_grade()
        self.assertEqual(self.output.read_bytes(), b"existing result\n")
        self.assertEqual(list(self.state.glob("*.consumed.json")), [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
