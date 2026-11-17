"""Generated files only; no scorer, dependency installer, network or model run."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("delivery", Path(__file__).resolve().parents[1] / "neurobench_delivery.py")
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        p = self.root / tool.REGISTRY
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({"tasks": [{"id": "NEURAL-FAKE"}]}))
        self.value = {"schema": "neurobench_delivery_v1", "task_ids": ["NEURAL-FAKE"],
            "files": [], "components": {}, "historical_qualification": {"private_secret": "DO_NOT_EXPORT"},
            "asset_bindings": {"never_follow": "private/nonexistent.npy"}}
        bodies = {
            "task_contract": ("public/TASK.md", b"One invented local task.\n"),
            "submission_schema": ("public/schema.json", b'{"type":"object"}\n'),
            "scorer": ("private/score.py", b"def score(value):\n    return value\n"),
            "data": ("public/invented.bin", b"invented bytes, not scientific data"),
            "dependencies": ("private/requirements.txt", b"Python==3.11\n"),
        }
        for role, (target, body) in bodies.items():
            self.add_file(role, target, body)
            self.value["components"][role] = {"status": "complete", "targets": [target], "blockers": []}
        self.pin = {"path": "authoring/delivery-20261105/fake/delivery_manifest.json", "bytes": 42, "sha256": "a" * 64}
        self.output = tool.DELIVERY + "/common/exports/fake"

    def add_file(self, role, target, body):
        source = "authoring/delivery-20261105/fake/" + target
        p = self.root / source
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)
        row = {"source": source, "target": target, "visibility": target.split("/")[0],
               "role": role, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
        self.value["files"].append(row)
        return row

    def test_complete_local_export_round_trip_without_running_source(self):
        result = tool.inspect(self.root, self.value)
        self.assertTrue(result["package_buildable"])
        self.assertFalse(result["package_built"])
        result = tool.assemble(self.root, self.value, self.pin, self.output)
        self.assertTrue(result["package_built"])
        self.assertFalse(result["runtime_verified"])
        checked = tool.check_export(self.root, self.output)
        self.assertTrue(checked["package_built"])
        self.assertEqual(checked["files_checked"], 5)

    def test_public_view_never_opens_private_sources_or_discloses_their_identities(self):
        original, opened = tool.verify_file, []
        def verify(root, row, destination=None):
            self.assertEqual(row["visibility"], "public")
            opened.append(row["source"])
            return original(root, row, destination)
        with patch.object(tool, "verify_file", verify):
            result = tool.assemble(self.root, self.value, self.pin, self.output,
                                   visibility="public", allow_partial=True)
        encoded = tool.encode(result)
        self.assertNotIn(b"DO_NOT_EXPORT", encoded)
        self.assertNotIn(b"private/score.py", encoded)
        self.assertNotIn(b"never_follow", encoded)
        self.assertFalse(result["package_built"])
        self.assertTrue(opened)
        self.assertFalse((self.root / self.output / "private").exists())

    def test_missing_pin_reports_exact_file_and_never_synthesizes_it(self):
        data = self.value["files"][3]
        (self.root / data["source"]).unlink()
        result = tool.inspect(self.root, self.value)
        self.assertEqual(result["file_issues"][0]["target"], data["target"])
        self.assertEqual(result["file_issues"][0]["status"], "missing_file")
        with self.assertRaises(tool.DeliveryError):
            tool.assemble(self.root, self.value, self.pin, self.output)
        result = tool.assemble(self.root, self.value, self.pin, self.output, allow_partial=True)
        self.assertFalse(result["package_built"])
        self.assertFalse((self.root / self.output / data["target"]).exists())

    def test_wrong_digest_is_not_copied_as_valid(self):
        self.value["files"][3]["sha256"] = "0" * 64
        result = tool.inspect(self.root, self.value)
        self.assertFalse(result["package_buildable"])
        self.assertEqual(result["file_issues"][0]["status"], "invalid_file")

    def test_path_traversal_case_collision_and_private_reclassification_rejected(self):
        for mutate in (
            lambda v: v["files"][0].update(target="../escape"),
            lambda v: v["files"].append({**v["files"][0], "target": "public/task.MD"}),
            lambda v: v["files"][0].update(source="authoring/private/secret.md"),
        ):
            value = copy.deepcopy(self.value)
            mutate(value)
            with self.assertRaises(tool.DeliveryError):
                tool.inspect(self.root, value)

    def test_cap_checked_before_any_selected_file_read(self):
        with patch.object(tool, "verify_file", side_effect=AssertionError("file accessed")):
            with self.assertRaisesRegex(tool.DeliveryError, "exceed explicit cap"):
                tool.inspect(self.root, self.value, max_bytes=1)

    def test_no_placeholder_or_stub_is_buildable(self):
        item = self.value["files"][2]
        body = b"def score(value):\n    raise NotImplementedError('pending')\n"
        (self.root / item["source"]).write_bytes(body)
        item.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        result = tool.inspect(self.root, self.value)
        self.assertFalse(result["package_buildable"])
        self.assertTrue(result["file_issues"][0]["stub_signals"])

    def test_stateless_constructor_with_implemented_behavior_is_not_a_stub(self):
        body = b"class Model(BaseModel):\n    def __init__(self):\n        pass\n    def draw(self):\n        return [p.rvs() for p in self.prior]\n"
        self.assertEqual(tool.stub_signals(body, "public/model.py", "source"), [])
        # Constructor treatment must not exempt an empty scientific method.
        body += b"    def estimate(self, values):\n        pass\n"
        self.assertEqual(len(tool.stub_signals(body, "public/model.py", "source")), 1)
        self.assertIn("estimate", tool.stub_signals(body, "public/model.py", "source")[0])

    def test_constructor_only_shell_and_top_level_initializer_still_flagged(self):
        for body in (b"class Model:\n    def __init__(self):\n        pass\n",
                     b"def __init__():\n    pass\n",
                     b"class Model:\n    def __init__(self):\n        pass\n    def estimate(self):\n        raise NotImplementedError\n"):
            self.assertTrue(tool.stub_signals(body, "private/model.py", "source"))

    def test_explicit_partial_recipe_remains_partial(self):
        self.value["components"]["data"].update(status="partial", blockers=["Exact source version unresolved"])
        result = tool.inspect(self.root, self.value)
        self.assertFalse(result["package_buildable"])
        self.assertEqual(result["component_blockers"]["data"], ["Exact source version unresolved"])

    def test_intact_partial_export_preserves_source_findings_without_integrity_failure(self):
        self.value["components"]["data"].update(status="partial", blockers=["Recordings absent"])
        self.add_file("author_source", "private/optional.py", b"def flush():\n    pass\n")
        result = tool.assemble(self.root, self.value, self.pin, self.output, allow_partial=True)
        self.assertFalse(result["package_built"])
        checked = tool.check_export(self.root, self.output)
        self.assertEqual(checked["file_integrity_issues"], [])
        self.assertEqual(len(checked["source_static_signals"]), 1)
        self.assertEqual(checked["file_issues"], checked["source_static_signals"])
        self.assertTrue(checked["package_claim_consistent"])
        self.assertFalse(checked["package_built"])

    def test_separating_source_findings_does_not_waive_unimplemented_scorer(self):
        item = self.value["files"][2]
        body = b"def score(value):\n    raise NotImplementedError\n"
        (self.root / item["source"]).write_bytes(body)
        item.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        with self.assertRaises(tool.DeliveryError):
            tool.assemble(self.root, self.value, self.pin, self.output)
        tool.assemble(self.root, self.value, self.pin, self.output, allow_partial=True)
        checked = tool.check_export(self.root, self.output)
        self.assertEqual(checked["file_integrity_issues"], [])
        self.assertTrue(checked["source_static_signals"])
        self.assertFalse(checked["package_built"])

    def test_partial_export_corruption_is_still_an_integrity_failure(self):
        self.value["components"]["data"].update(status="partial", blockers=["Recordings absent"])
        self.add_file("author_source", "private/optional.py", b"def flush():\n    pass\n")
        tool.assemble(self.root, self.value, self.pin, self.output, allow_partial=True)
        data = self.root / self.output / "public/invented.bin"
        data.chmod(0o600)
        data.write_bytes(b"corrupt")
        checked = tool.check_export(self.root, self.output)
        self.assertEqual(len(checked["file_integrity_issues"]), 1)
        self.assertEqual(checked["file_integrity_issues"][0]["target"], "public/invented.bin")
        self.assertEqual(len(checked["source_static_signals"]), 1)
        self.assertEqual(len(checked["file_issues"]), 2)
        self.assertFalse(checked["package_built"])

    def test_redistribution_limit_is_not_empirical_or_local_build_failure(self):
        self.value["distribution"] = {"public_redistribution_approved": False}
        result = tool.assemble(self.root, self.value, self.pin, self.output)
        self.assertTrue(result["package_built"])
        self.assertFalse(result["distribution"]["public_redistribution_approved"])
        self.assertFalse(result["submission_ready"])

    def test_fresh_output_required_and_unknown_ids_rejected(self):
        tool.assemble(self.root, self.value, self.pin, self.output)
        with self.assertRaisesRegex(tool.DeliveryError, "must be fresh"):
            tool.assemble(self.root, self.value, self.pin, self.output)
        self.value["task_ids"] = ["UNKNOWN"]
        with self.assertRaisesRegex(tool.DeliveryError, "Unknown"):
            tool.inspect(self.root, self.value)

    def test_corrupt_export_reports_exact_file_not_success(self):
        tool.assemble(self.root, self.value, self.pin, self.output)
        p = self.root / self.output / "public/invented.bin"
        p.chmod(0o600)
        p.write_bytes(b"changed")
        result = tool.check_export(self.root, self.output)
        self.assertFalse(result["package_built"])
        self.assertFalse(result["package_claim_consistent"])
        self.assertEqual(result["file_issues"][0]["target"], "public/invented.bin")

    def test_symlinks_and_unlisted_export_files_rejected(self):
        source = self.root / self.value["files"][0]["source"]
        body = source.read_bytes()
        source.unlink()
        source.symlink_to("/unreleased/data")
        self.assertFalse(tool.inspect(self.root, self.value)["package_buildable"])
        source.unlink()
        source.write_bytes(body)
        tool.assemble(self.root, self.value, self.pin, self.output)
        (self.root / self.output / "public/unlisted.txt").write_text("extra")
        with self.assertRaisesRegex(tool.DeliveryError, "Unlisted"):
            tool.check_export(self.root, self.output)

    def test_checks_are_deterministic_and_never_claim_historical_revalidation(self):
        first = tool.inspect(self.root, self.value)
        self.assertEqual(tool.encode(first), tool.encode(tool.inspect(self.root, self.value)))
        self.assertFalse(first["historical_qualification_revalidated"])
        self.assertEqual(first["new_scientific_executions"], 0)

    def test_export_metadata_is_not_a_component_and_unknown_ids_are_rejected(self):
        folder = self.root / self.output
        folder.mkdir(parents=True)
        forged = {"schema": "neurobench_delivery_export_v1", "task_ids": ["NEURAL-FAKE"],
            "visibility": "all", "files": [], "package_built": True,
            "components": {k: {"status": "complete", "targets": [tool.MANIFEST], "blockers": []}
                           for k in tool.COMPONENTS}}
        (folder / tool.MANIFEST).write_bytes(tool.encode(forged))
        with self.assertRaisesRegex(tool.DeliveryError, "allowlisted files"):
            tool.check_export(self.root, self.output)
        forged["task_ids"] = ["UNKNOWN"]
        (folder / tool.MANIFEST).write_bytes(tool.encode(forged))
        with self.assertRaisesRegex(tool.DeliveryError, "Unknown"):
            tool.check_export(self.root, self.output)


if __name__ == "__main__":
    unittest.main()
