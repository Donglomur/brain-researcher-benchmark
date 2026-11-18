#!/usr/bin/env python3
"""Focused controls for retained REVE policy in the actual integrity API."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

parser = argparse.ArgumentParser(description=__doc__, add_help=False)
parser.add_argument("--pre-improvement-history", type=Path)
options, _ = parser.parse_known_args()
fixture_path = Path(__file__).with_name("test_reve_readiness_reporting.py")
spec = importlib.util.spec_from_file_location("_reve_integrity_fixture_inputs", fixture_path)
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)  # Loads pinned metadata fixtures; never runs its 11 tests.
integrity = fixtures.module("_reve_integrity_control", fixtures.args.source_root / "source_integrity.py")
binding = integrity.outcome_binding_module()
HOME = binding._REVE_HOME
history_path = options.pre_improvement_history or fixtures.history_file.with_name("task.pre-improvement.v1.json")
historical_body = history_path.read_bytes()
historical_pin = fixtures.previous["evaluation"]["calibration"]["historical_task"]
assert binding.pin(historical_pin["path"], historical_body) == historical_pin, "Changed original task history"


class IntegrityReader:
    def __init__(self, files):
        self.files = dict(files)
        self.reads = []

    def read(self, path, *, limit=None):
        integrity.relative(path)
        self.reads.append(path)
        if path not in self.files:
            raise integrity.InvalidSource("Missing generated metadata: " + path)
        body = self.files[path]
        integrity.require(len(body) <= (limit or integrity.MEMBER_LIMIT), "Oversized generated metadata")
        return body

    def checked(self, path, descriptor):
        integrity.descriptor(descriptor)
        body = self.read(path)
        integrity.require(len(body) == descriptor["bytes"]
                          and hashlib.sha256(body).hexdigest() == descriptor["sha256"],
                          "Generated metadata pin mismatch")
        return body


def lineage(task_id="PAPER-paper-method-003", document=None, previous_pin=None, contract_pin=None):
    """Generate registration plumbing while retaining exact source evidence."""
    doc = copy.deepcopy(fixtures.previous if document is None else document)
    old = copy.deepcopy(historical_pin if previous_pin is None else previous_pin)
    policy = copy.deepcopy(binding._REVE_OLD_IMPROVEMENT if contract_pin is None else contract_pin)
    home = "benchmarks/paper/" + task_id
    current = binding.pin(home + "/task.json", binding.encode(doc))
    revision = {"version": integrity.PAPER_REVISION, "previous_specification": old, "improvement_contract": policy}
    original = {**old, "path": "generated/original-paper-task.json"}
    task_pin = {**current, "original_path": original["path"], "predecessor": old,
                "specification_revision": revision}
    registered = {"id": task_id, "track": "paper", "task_directory": home,
                  "specification_id": task_id, "specification": current,
                  "specification_revision": revision, "original_specification": original}
    return task_id, task_pin, doc, registered


def files_for_selected():
    return {**fixtures.raws, historical_pin["path"]: historical_body}


class IntegrityControls(unittest.TestCase):
    def test_original_contract_path_still_validates(self):
        files = {historical_pin["path"]: historical_body,
                 binding._REVE_OLD_IMPROVEMENT["path"]: fixtures.raws[binding._REVE_RETAINED_IMPROVEMENT["path"]]}
        reader = IntegrityReader(files)
        self.assertEqual(integrity.checked_paper_revision(reader, *lineage()), historical_body)
        self.assertNotIn(binding._REVE_RETAINED_IMPROVEMENT["path"], reader.reads)

    def test_selected_reporting_retains_exact_original_lineage(self):
        reader = IntegrityReader(files_for_selected())
        self.assertEqual(integrity.checked_paper_revision(reader, *lineage()), historical_body)
        self.assertIn(binding._REVE_RETAINED_IMPROVEMENT["path"], reader.reads)
        self.assertIn(binding._REVE_RETAINED_OUTCOMES["path"], reader.reads)
        self.assertEqual(reader.files[binding._REVE_IMPROVEMENT["path"]],
                         fixtures.raws[binding._REVE_IMPROVEMENT["path"]])

    def test_changed_old_descriptor_is_rejected(self):
        policy = {**binding._REVE_OLD_IMPROVEMENT, "sha256": "0" * 64}
        with self.assertRaises(integrity.InvalidSource):
            integrity.checked_paper_revision(IntegrityReader(files_for_selected()), *lineage(contract_pin=policy))

    def test_changed_retained_contract_is_rejected(self):
        files = files_for_selected()
        files[binding._REVE_RETAINED_IMPROVEMENT["path"]] += b" "
        with self.assertRaises(integrity.InvalidSource):
            integrity.checked_paper_revision(IntegrityReader(files), *lineage())

    def test_partial_correction_is_rejected(self):
        files = files_for_selected()
        del files[binding._REVE_RETAINED_OUTCOMES["path"]]
        with self.assertRaises(integrity.InvalidSource):
            integrity.checked_paper_revision(IntegrityReader(files), *lineage())

    def test_original_registration_hash_is_not_relaxed(self):
        args = lineage()
        args[3]["original_specification"]["sha256"] = "0" * 64
        with self.assertRaises(integrity.InvalidSource):
            integrity.checked_paper_revision(IntegrityReader(files_for_selected()), *args)

    def test_unrelated_paper_uses_original_direct_path(self):
        task_id = "PAPER-generated-integrity-control"
        home = "benchmarks/paper/" + task_id
        original = binding.encode({"id": task_id, "track": "paper", "objective": "generated_original"})
        previous_pin = binding.pin(home + "/historical/task.pre-improvement.v1.json", original)
        contract = copy.deepcopy(fixtures.old_contract)
        contract["task_id"] = task_id
        body = binding.encode(contract)
        policy = binding.pin(home + "/improvement.v1.json", body)
        doc = copy.deepcopy(fixtures.previous)
        doc["id"] = task_id
        doc["evaluation"]["contract"] = policy
        doc["evaluation"]["calibration"]["historical_task"] = previous_pin
        reader = IntegrityReader({previous_pin["path"]: original, policy["path"]: body})
        self.assertEqual(integrity.checked_paper_revision(
            reader, *lineage(task_id, doc, previous_pin, policy)), original)
        self.assertEqual(reader.reads, [previous_pin["path"], policy["path"]])


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(IntegrityControls)
    result = unittest.TextTestRunner(stream=fixtures.BoundedLog(limit=2048), verbosity=1).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
