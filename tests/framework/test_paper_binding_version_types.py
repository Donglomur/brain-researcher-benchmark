"""Typed reproduction selection with invented metadata and no task execution."""
import copy
import importlib.util
from pathlib import Path
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/neurobench/paper_outcomes_binding.py"
spec = importlib.util.spec_from_file_location("_paper_binding_version_types", SOURCE)
binding = importlib.util.module_from_spec(spec)
exec(compile(SOURCE.read_bytes(), str(SOURCE), "exec"), binding.__dict__)


class PaperBindingVersionTypeTests(unittest.TestCase):
    def test_selectors_require_versioned_text_before_read_or_projection(self):
        home = "benchmarks/paper/PAPER-GENERATED-TYPE-CONTROL"
        previous = {"id": "PAPER-GENERATED-TYPE-CONTROL", "track": "paper",
                    "objective": "surpass_source_paper_same_task"}
        row = {"id": previous["id"], "track": "paper"}
        improvement = {"task_id": row["id"],
                       "same_task": {"target": {"description": "Invented metadata target"}}}
        originals = copy.deepcopy((previous, row, improvement))
        invalid = (None, False, True, 0, 1, 1.5, [], {}, "", "paper-reproduction/v999")
        valid_pin = {"path": home + "/reproduction.v1.json", "bytes": 1, "sha256": "0" * 64}
        with mock.patch.object(binding, "engine", side_effect=AssertionError("validator dispatched")):
            for value in invalid:
                with self.subTest(route="path", value=value):
                    reader = mock.Mock(side_effect=AssertionError("invalid path was read"))
                    selected = dict(valid_pin, path=value)
                    with self.assertRaisesRegex(ValueError, "versioned reproduction filename"):
                        binding.read_reproduction(selected, home, reader)
                    reader.assert_not_called()
                with self.subTest(route="schema_version", value=value):
                    reader = mock.Mock(return_value={"schema_version": value})
                    with self.assertRaisesRegex(ValueError, "Unsupported reproduction contract version"):
                        binding.read_reproduction(valid_pin, home, reader)
                    reader.assert_called_once_with(valid_pin, "Reproduction contract")
                with self.subTest(route="projection_version", value=value):
                    with mock.patch.object(binding.copy, "deepcopy", side_effect=AssertionError("projection started")):
                        with self.assertRaisesRegex(ValueError, "Unsupported reproduction projection version"):
                            binding.project_task(previous, row, improvement, reproduction_version=value)
            for version, filename in (("paper-reproduction/v1", "reproduction.v1.json"),
                                      ("paper-reproduction/v2", "reproduction.v2.json")):
                with self.subTest(route="valid", version=version):
                    selected = dict(valid_pin, path=home + "/" + filename)
                    document = {"schema_version": version}
                    reader = mock.Mock(return_value=document)
                    self.assertIs(binding.read_reproduction(selected, home, reader), document)
                    reader.assert_called_once_with(selected, "Reproduction contract")
                    projected = binding.project_task(previous, row, improvement, reproduction_version=version)
                    self.assertEqual(projected["evaluation"]["contracts"]["reproduction"], filename)
                    self.assertEqual(projected["evaluation"]["contracts"]["improvement"], "improvement.v1.json")
                    self.assertIs(projected["evaluation"]["binary_reward_registered"], False)
                    wrong = "reproduction.v2.json" if filename == "reproduction.v1.json" else "reproduction.v1.json"
                    with self.assertRaisesRegex(ValueError, "filename must match its declared schema"):
                        binding.read_reproduction(dict(selected, path=home + "/" + wrong), home, reader)
        self.assertEqual((previous, row, improvement), originals)
        default = binding.project_task(previous, row, improvement)
        explicit = binding.project_task(previous, row, improvement, reproduction_version="paper-reproduction/v1")
        self.assertEqual(binding.encode(default), binding.encode(explicit))


if __name__ == "__main__":
    unittest.main()
