#!/usr/bin/env python3
"""Focused generated metadata controls for the exact REVE reporting revision."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source-root", type=Path, default=ROOT / "src/neurobench")
parser.add_argument("--task-root", type=Path, default=ROOT / "benchmarks/paper/PAPER-paper-method-003")
parser.add_argument("--archive-root", type=Path, default=None)
parser.add_argument("--history-file", type=Path, default=None)
args, remaining = parser.parse_known_args()
archive_root = args.archive_root or args.task_root / "historical"
history_file = args.history_file or args.task_root / "historical/task.pre-outcomes.v1.json"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


checks = module("_reve_reporting_repository_checks", args.source_root / "repository_checks.py")
binding = checks.paper_outcome_module()
HOME = binding._REVE_HOME
raws = {}
for descriptor in (binding._REVE_TASK, binding._REVE_IMPROVEMENT, binding._REVE_OUTCOMES):
    raw = (args.task_root / descriptor["path"].rsplit("/", 1)[1]).read_bytes()
    assert binding.pin(descriptor["path"], raw) == descriptor, "Changed selected metadata fixture"
    raws[descriptor["path"]] = raw
for descriptor in (binding._REVE_RETAINED_IMPROVEMENT, binding._REVE_RETAINED_OUTCOMES):
    raw = (archive_root / descriptor["path"].rsplit("/", 1)[1]).read_bytes()
    assert binding.pin(descriptor["path"], raw) == descriptor, "Changed retained metadata fixture"
    raws[descriptor["path"]] = raw
history_raw = history_file.read_bytes()
assert len(history_raw) == 18420 and hashlib.sha256(history_raw).hexdigest() == (
    "2325143fbf783f0810a84e4d4de71f40148c2c5a23eaed37b516c4cbac2ba816"
), "Changed immutable pre-outcomes metadata fixture"
previous = json.loads(history_raw)
row = {"id": "PAPER-paper-method-003", "track": "paper"}
old_contract = json.loads(raws[binding._REVE_RETAINED_IMPROVEMENT["path"]])
new_contract = json.loads(raws[binding._REVE_IMPROVEMENT["path"]])


class MetadataReader:
    """Generated in-memory transport using actual raw metadata byte identities."""
    def __init__(self, files):
        self.files = dict(files)
        self.pins = {}
        self.reads = []

    def document(self, path):
        self.reads.append(path)
        if path not in self.files:
            raise ValueError("Missing generated metadata member: " + path)
        body = self.files[path]
        self.pins[path] = {**binding.pin(path, body), "mode": "100644"}
        return json.loads(body), self.pins[path]


def read(reader, descriptor):
    return checks.metadata_pin(reader, descriptor, descriptor["path"], "Generated metadata control")


def changed(files, path, edit):
    result = dict(files)
    value = json.loads(result[path])
    edit(value)
    result[path] = binding.encode(value)
    return result


class ReportingControls(unittest.TestCase):
    def test_original_equality_route_needs_no_archives(self):
        descriptor = binding._REVE_OLD_IMPROVEMENT
        reader = MetadataReader({descriptor["path"]: raws[binding._REVE_RETAINED_IMPROVEMENT["path"]]})
        self.assertEqual(read(reader, descriptor), old_contract)
        self.assertEqual(reader.reads, [descriptor["path"]])
        result = binding.project_task(previous, row, old_contract)
        self.assertEqual(binding.pin(HOME + "/task.json", binding.encode(result)), binding._REVE_OLD_TASK)

    def test_complete_selected_revision_keeps_actual_current_pin(self):
        reader = MetadataReader(raws)
        self.assertEqual(read(reader, binding._REVE_OLD_IMPROVEMENT), old_contract)
        self.assertEqual({k: reader.pins[HOME + "/improvement.v1.json"][k]
                          for k in ("path", "bytes", "sha256")}, binding._REVE_IMPROVEMENT)
        result = binding.project_task(previous, row, new_contract)
        self.assertEqual(binding.pin(HOME + "/task.json", binding.encode(result)), binding._REVE_TASK)
        self.assertEqual(result, json.loads(raws[HOME + "/task.json"]))
        self.assertEqual(result["admission"]["runnable"], False)
        self.assertEqual(result["admission"]["research_qualified"], False)
        self.assertEqual(result["admission"]["full_contract_complete"], False)
        self.assertEqual(old_contract["same_task"], new_contract["same_task"])
        self.assertEqual(old_contract["comparison"], new_contract["comparison"])

    def test_changed_old_descriptor_cannot_resolve(self):
        requested = {**binding._REVE_OLD_IMPROVEMENT, "sha256": "0" * 64}
        reader = MetadataReader(raws)
        with self.assertRaises(ValueError):
            read(reader, requested)
        self.assertEqual(reader.reads, [requested["path"]])

    def test_unrelated_mismatch_cannot_resolve(self):
        reader = MetadataReader({"unrelated.json": b"{}\n"})
        with self.assertRaises(ValueError):
            read(reader, {"path": "unrelated.json", "bytes": 3, "sha256": "0" * 64})
        self.assertEqual(reader.reads, ["unrelated.json"])

    def test_partial_current_bundle_is_rejected(self):
        for missing in (binding._REVE_TASK["path"], binding._REVE_OUTCOMES["path"],
                        binding._REVE_RETAINED_IMPROVEMENT["path"], binding._REVE_RETAINED_OUTCOMES["path"]):
            with self.subTest(missing=missing):
                files = {k: v for k, v in raws.items() if k != missing}
                with self.assertRaises(ValueError):
                    read(MetadataReader(files), binding._REVE_OLD_IMPROVEMENT)

    def test_changed_retained_contract_is_rejected(self):
        files = changed(raws, binding._REVE_RETAINED_IMPROVEMENT["path"],
                        lambda value: value["comparison"].update(direction="lower"))
        with self.assertRaises(ValueError):
            read(MetadataReader(files), binding._REVE_OLD_IMPROVEMENT)

    def test_changed_retained_outcome_evidence_is_rejected(self):
        files = changed(raws, binding._REVE_RETAINED_OUTCOMES["path"],
                        lambda value: value["pairing"]["improvement"].update(status="specified"))
        with self.assertRaises(ValueError):
            read(MetadataReader(files), binding._REVE_OLD_IMPROVEMENT)

    def test_changed_current_task_cannot_promote_readiness(self):
        files = changed(raws, binding._REVE_TASK["path"],
                        lambda value: value["admission"].update(runnable=True))
        with self.assertRaises(ValueError):
            read(MetadataReader(files), binding._REVE_OLD_IMPROVEMENT)

    def test_changed_old_task_lineage_is_rejected(self):
        prior = copy.deepcopy(previous)
        prior["resources"]["roster_resource_statement"] += " changed"
        with self.assertRaises(ValueError):
            binding.project_task(prior, row, new_contract)

    def test_unselected_scientific_contract_is_rejected(self):
        value = copy.deepcopy(new_contract)
        value["same_task"]["split"]["description"] += " changed"
        with self.assertRaises(ValueError):
            binding.project_task(previous, row, value)

    def test_unrelated_task_retains_existing_projection(self):
        prior = copy.deepcopy(previous)
        contract = copy.deepcopy(old_contract)
        other = {"id": "PAPER-generated-reporting-control", "track": "paper"}
        contract["task_id"] = other["id"]
        result = binding.project_task(prior, other, contract)
        self.assertEqual(result["blocking_issues"]["improvement"], previous["blocking_issues"])
        self.assertEqual(result["holds"]["preserved_limits"], previous["holds"])


class BoundedLog:
    """Keep the retained generated-control log below its finite byte allowance."""
    def __init__(self, limit=6144):
        self.remaining = limit

    def write(self, value):
        raw = value.encode("utf-8")[:self.remaining]
        self.remaining -= len(raw)
        sys.stderr.write(raw.decode("utf-8", errors="ignore"))

    def flush(self):
        sys.stderr.flush()


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ReportingControls)
    result = unittest.TextTestRunner(stream=BoundedLog(), verbosity=1).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
