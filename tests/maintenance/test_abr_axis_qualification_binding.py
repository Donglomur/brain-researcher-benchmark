"""ABR active documentation/axis binding controls; no data or model execution."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
TASK = "NEURAL-SCOPE-20261114-ABR-TRANSFER"
HOME = "benchmarks/neural/" + TASK
README = HOME + "/implementations/native-inputs-v1/README.md"
HISTORY_SHA = "3ac11adf902d863075f6c38ee76365321a1fe44f23fde898e7f13c6b6a3c0f86"
OLD_README_SHA = "d8a7ad3b6039a368a50489fe6231108fdde90bbd29b67541fa442bdd390032d9"
NEW_README_SHA = "afae1d86ba77dcd31bbea737fd1079f90fb2af8c10ec2e4a4f245f56afd4838f"


class AbrAxisBindingControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "abr_axis_binding_control", ROOT / "src/neurobench/neural_understanding.py")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.original_body = (ROOT / HOME / cls.module.HISTORY).read_bytes()
        if hashlib.sha256(cls.original_body).hexdigest() != HISTORY_SHA:
            raise AssertionError("Original ABR registration changed")
        cls.original = json.loads(cls.original_body)
        cls.contract_body = (ROOT / HOME / cls.module.CONTRACT).read_bytes()
        cls.contract = json.loads(cls.contract_body)
        cls.current = json.loads((ROOT / HOME / "task.json").read_bytes())
        cls.row = {"id": TASK, "task_directory": HOME,
                   "original_specification": {"bytes": len(cls.original_body), "sha256": HISTORY_SHA}}

    def project(self, contract):
        return self.module._current(
            self.original, contract,
            self.module._binding(self.module._bytes(contract), self.original_body), TASK)

    def test_active_contract_loads_against_revised_documentation(self):
        self.assertEqual(self.module._load(ROOT, TASK, self.row), self.contract)
        entry = next(e for e in self.contract["evidence"]
                     if e["id"] == "abr-storage-layout-qualification-v1")
        self.assertEqual(entry["sha256"], NEW_README_SHA)
        self.assertEqual(hashlib.sha256((ROOT / README).read_bytes()).hexdigest(), NEW_README_SHA)

    def test_current_projection_preserves_physical_and_historical_holds(self):
        projected = self.project(self.contract)
        self.assertEqual(projected, self.current)
        timing = copy.deepcopy(projected["units_and_timing"])
        gate = timing.pop("preparation_gate")
        original_timing = copy.deepcopy(self.original["units_and_timing"])
        original_gate = original_timing.pop("preparation_gate")
        self.assertEqual(timing, original_timing)
        self.assertTrue(gate.startswith(original_gate))
        self.assertIn("sample-index axes with null physical sample periods", gate)
        self.assertIn("Existing sealed preparations retain their historical", gate)
        self.assertIn("withhold both a continuous 17 ms axis", gate)
        self.assertFalse(projected["admission"]["runnable"])
        self.assertFalse(projected["admission"]["research_qualified"])
        self.assertFalse(projected["admission"]["submission_ready"])
        self.assertEqual(self.contract["empirical_claims"]["new_model_trials"], 0)

    def test_stale_readme_pin_is_not_accepted_as_current_evidence(self):
        stale = copy.deepcopy(self.contract)
        entry = next(e for e in stale["evidence"]
                     if e["id"] == "abr-storage-layout-qualification-v1")
        entry["sha256"] = OLD_README_SHA
        original_read = self.module._read
        replacements = {HOME + "/" + self.module.CONTRACT: self.module._bytes(stale),
                        HOME + "/task.json": self.module._bytes(self.project(stale))}
        def read(root, relative):
            return replacements[relative] if relative in replacements else original_read(root, relative)
        with mock.patch.object(self.module, "_read", side_effect=read):
            with self.assertRaisesRegex(ValueError, "Evidence SHA-256 mismatch"):
                self.module._load(ROOT, TASK, self.row)

    def test_changed_documentation_requires_a_new_reviewed_binding(self):
        original_read = self.module._read
        def read(root, relative):
            body = original_read(root, relative)
            return body + b"changed\n" if relative == README else body
        with mock.patch.object(self.module, "_read", side_effect=read):
            with self.assertRaisesRegex(ValueError, "Evidence SHA-256 mismatch"):
                self.module._load(ROOT, TASK, self.row)

    def test_wrong_selector_cannot_activate_axis_qualification(self):
        for field, value in (("kind", "local_source"), ("sha256", "0" * 64)):
            contract = copy.deepcopy(self.contract)
            entry = next(e for e in contract["evidence"]
                         if e["id"] == "abr-storage-layout-qualification-v1")
            entry[field] = value
            with self.subTest(field=field):
                projected = self.project(contract)
                self.assertEqual(projected["units_and_timing"]["preparation_gate"],
                                 self.original["units_and_timing"]["preparation_gate"])
                self.assertFalse(projected["admission"]["research_qualified"])


if __name__ == "__main__":
    unittest.main()
