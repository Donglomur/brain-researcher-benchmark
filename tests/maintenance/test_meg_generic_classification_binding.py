"""Focused source checks for the exact, separately scoped MEG mode.

No scientific programme, data acquisition, temporary fixture, or benchmark
execution occurs here. The existing task may be before or after native adoption.
"""
import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
HOME = "benchmarks/paper/PAPER-paper-method-add-010"


class TestMegGenericClassificationBinding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = ROOT / "src/neurobench/paper_outcomes_binding.py"
        spec = importlib.util.spec_from_file_location("_meg_scoped_binding_control", source)
        cls.binding = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.binding)
        binding = cls.binding

        def document(relative, upper):
            path = ROOT / relative
            stat = path.lstat()
            if path.is_symlink() or not path.is_file() or stat.st_nlink != 1 or stat.st_size > upper:
                raise AssertionError("Expected bounded selected control metadata")
            raw = path.read_bytes()
            return json.loads(raw.decode("utf-8")), raw

        cls.descriptor, raw = document(binding.MEG_GENERIC_MODE_PIN["path"], 16384)
        if binding.pin(binding.MEG_GENERIC_MODE_PIN["path"], raw) != binding.MEG_GENERIC_MODE_PIN:
            raise AssertionError("Descriptor fixture differs from selected source")
        cls.task, _ = document(HOME + "/task.json", 131072)
        cls.outcomes, _ = document(HOME + "/outcomes.v1.json", 8192)
        modes = cls.task.get("evaluation", {}).pop("scoped_execution_modes", None)
        if modes is not None and modes != [binding.meg_generic_classification_summary(cls.descriptor)]:
            raise AssertionError("Unexpected current scoped mode")
        cls.outcomes["original_task_sha256"] = binding.MEG_GENERIC_BASE_TASK["sha256"]
        if (binding.pin(HOME + "/task.json", binding.encode(cls.task)) != binding.MEG_GENERIC_BASE_TASK
                or binding.pin(HOME + "/outcomes.v1.json", binding.encode(cls.outcomes)) != binding.MEG_GENERIC_BASE_OUTCOMES):
            raise AssertionError("Current metadata does not preserve the exact reviewed predecessor")
        cls.row = {"id": binding.MEG_GENERIC_TASK, "track": "paper",
                   "specification": copy.deepcopy(binding.MEG_GENERIC_BASE_TASK),
                   "paper_outcomes": {"outcomes": copy.deepcopy(binding.MEG_GENERIC_BASE_OUTCOMES)}}

    def read_pin(self, requested, label):
        self.assertEqual(requested, self.binding.MEG_GENERIC_MODE_PIN)
        return copy.deepcopy(self.descriptor)

    def adopt(self, row=None, task=None, outcomes=None, read_pin=None):
        return self.binding.meg_generic_classification_adoption(
            copy.deepcopy(self.row if row is None else row),
            copy.deepcopy(self.task if task is None else task),
            copy.deepcopy(self.outcomes if outcomes is None else outcomes),
            self.read_pin if read_pin is None else read_pin)

    def test_authenticated_projection_preserves_broad_contract(self):
        row, task, outcomes = self.adopt()
        self.assertTrue(self.binding.has_meg_generic_classification(row))
        mode = task["evaluation"].pop("scoped_execution_modes")
        self.assertEqual(task, self.task)
        self.assertEqual(mode, [self.binding.meg_generic_classification_summary(self.descriptor)])
        self.assertEqual(outcomes["original_task_sha256"], row["specification"]["sha256"])
        outcomes["original_task_sha256"] = self.outcomes["original_task_sha256"]
        self.assertEqual(outcomes, self.outcomes)
        self.assertFalse(mode[0]["broader_task_admission_changed"])
        self.assertIsNone(mode[0]["scientific_superiority_established"])

    def test_wrong_task_or_descriptor_selector_is_rejected(self):
        row, _, _ = self.adopt()
        for mutation in ("task", "pin"):
            with self.subTest(mutation=mutation):
                altered = copy.deepcopy(row)
                if mutation == "task":
                    altered["id"] = "PAPER-paper-method-add-011"
                else:
                    altered["paper_outcomes"][self.binding.MEG_GENERIC_FIELD]["sha256"] = "0" * 64
                with self.assertRaises(ValueError):
                    self.binding.has_meg_generic_classification(altered)

    def test_descriptor_scope_or_qualification_mutation_is_rejected(self):
        for section, field, value in (("input", "selected_rows", 187),
                                     ("input", "raw_to_generic_feature_equivalence_established", True),
                                     ("delivery_and_qualification", "broader_task_admission_changed", True),
                                     ("delivery_and_qualification", "benchmark_count_increment", 1)):
            with self.subTest(field=field):
                altered = copy.deepcopy(self.descriptor)
                altered[section][field] = value
                with self.assertRaises(ValueError):
                    self.adopt(read_pin=lambda requested, label: altered)

    def test_retained_task_tampering_is_rejected(self):
        for field in ("goal", "status", "resources"):
            with self.subTest(field=field):
                altered = copy.deepcopy(self.task)
                altered[field] = "unauthorized alteration"
                with self.assertRaises(ValueError):
                    self.adopt(task=altered)

    def test_outcomes_nonidentity_changes_are_rejected(self):
        for mutation in ("pairing", "contract"):
            with self.subTest(mutation=mutation):
                altered = copy.deepcopy(self.outcomes)
                if mutation == "pairing":
                    altered["pairing"]["reproduction"]["status"] = "admitted"
                else:
                    altered["contracts"]["improvement"] = "0" * 64
                with self.assertRaises(ValueError):
                    self.adopt(outcomes=altered)

    def test_selected_adoption_is_an_exact_fixed_point(self):
        first = self.adopt()
        second = self.adopt(row=first[0], task=first[1], outcomes=first[2])
        self.assertEqual(second, first)
        for before, after in zip(first, second):
            self.assertEqual(self.binding.encode(before), self.binding.encode(after))


if __name__ == "__main__":
    unittest.main()
