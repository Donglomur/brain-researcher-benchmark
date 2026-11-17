"""Generated public-navigation controls; no scientific or private input reads."""

from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "navigation_under_test", ROOT / "src/neurobench/navigation.py")
navigation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(navigation)


class NavigationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.scratch = Path(temporary.name).resolve()
        self.root = self.scratch / "repo"
        self.root.mkdir()
        self.write("README.md", "# Generated repository\n")
        (self.root / "docs/usage").mkdir(parents=True)
        self.registry = {"tasks": [{
            "id": "NEURAL-001", "track": "neural",
            "task_directory": "benchmarks/neural/NEURAL-001",
            "documentation": [],
        }]}
        self.write("benchmarks/neural/NEURAL-001/README.md", "# Generated task\n")
        self.write_json("benchmarks/registry.json", self.registry)
        self.write_json("docs/provenance/relocations/2026-11-16.json", {"files": []})
        (self.root / navigation.CURRENT_CLOSURES).mkdir(parents=True)
        for name, value in (("ROOT", self.root), ("PAGES", ("README.md",))):
            context = patch.object(navigation, name, value)
            context.start()
            self.addCleanup(context.stop)

    def write(self, relative, body):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path

    def write_json(self, relative, document):
        return self.write(relative, json.dumps(document) + "\n")

    def document(self, relative, body):
        path = self.write(relative, body)
        self.registry["tasks"][0]["documentation"].append({"label": "Generated guide", "path": relative})
        self.write_json("benchmarks/registry.json", self.registry)
        return path

    def check(self):
        # Even a regression in path validation must not open the outside fixture.
        actual_open = os.open
        actual_scandir = os.scandir
        actual_listdir = os.listdir
        opened = []

        def guarded_open(path, *args, **kwargs):
            resolved = Path(path).resolve()
            self.assertTrue(resolved.is_relative_to(self.root), "External source read attempted")
            opened.append(resolved)
            return actual_open(path, *args, **kwargs)

        def guarded_scandir(path):
            self.assertTrue(Path(path).resolve().is_relative_to(self.root), "External directory traversal attempted")
            return actual_scandir(path)

        def guarded_listdir(path):
            self.assertTrue(Path(path).resolve().is_relative_to(self.root), "External directory traversal attempted")
            return actual_listdir(path)

        with patch("os.open", guarded_open), patch("os.scandir", guarded_scandir), \
             patch("os.listdir", guarded_listdir), redirect_stdout(io.StringIO()) as output:
            status = navigation.main()
        return status, output.getvalue(), opened

    def test_current_usage_guides_are_discovered_and_broken_links_refuse(self):
        guide = "docs/usage/construction-components.md"
        self.write("README.md", f"[Construction]({guide})\n")
        self.write(guide, "[Missing command guide](missing.md)\n")
        status, output, opened = self.check()
        self.assertEqual(status, 1)
        self.assertIn(f"{guide}: missing or external local path missing.md", output)
        self.assertIn(self.root / guide, opened)
        self.write("docs/usage/missing.md", "# Available guide\n")
        self.assertEqual(self.check()[0], 0)

    def test_registered_task_markdown_is_checked_without_manual_page_enrollment(self):
        guide = "benchmarks/neural/NEURAL-001/docs/inputs.md"
        self.document(guide, "[Missing schema](not-here.json)\n")
        status, output, opened = self.check()
        self.assertEqual(status, 1)
        self.assertIn(f"{guide}: missing or external local path not-here.json", output)
        self.assertIn(self.root / guide, opened)

    def test_current_binding_guides_have_current_link_checks(self):
        guide = navigation.CURRENT_CLOSURES + "/example/nested/README.md"
        self.write(guide, "[Current descriptor](SOURCE.json)\n")
        status, output, opened = self.check()
        self.assertEqual(status, 1)
        self.assertIn(f"{guide}: missing or external local path SOURCE.json", output)
        self.assertIn(self.root / guide, opened)
        descriptor = str(Path(guide).parent / "SOURCE.json")
        self.write_json(descriptor, {"private_payload": "/private/never-read-this.json"})
        status, output, opened = self.check()
        self.assertEqual(status, 0)
        self.assertNotIn(self.root / descriptor, opened)
        self.assertIn("0 historical references resolved", output)
        # A relocation entry does not turn an ordinary binding guide historical.
        self.write(guide, "[Old-only route](old.json)\n")
        self.write_json("docs/provenance/relocations/2026-11-16.json", {"files": [
            {"old": "old/README.md", "new": guide},
            {"old": "old/old.json", "new": descriptor},
        ]})
        self.assertEqual(self.check()[0], 1)

    def test_current_binding_guide_aliases_refuse_before_external_reads_or_traversal(self):
        directory = self.root / navigation.CURRENT_CLOSURES / "example"
        directory.mkdir()
        outside = self.scratch / "outside-binding"
        outside.mkdir()
        (outside / "README.md").write_text("Outside generated fixture\n")
        guide = directory / "README.md"
        guide.symlink_to(outside / "README.md")
        status, output, _ = self.check()
        self.assertEqual(status, 1)
        self.assertIn("ordinary single-link file", output)
        guide.unlink()
        directory.rmdir()
        directory.symlink_to(outside, target_is_directory=True)
        status, output, _ = self.check()
        self.assertEqual(status, 1)
        self.assertIn("ordinary single-link file", output)

    def test_current_binding_discovery_keeps_exact_names_and_depth_bound(self):
        directory = self.root / navigation.CURRENT_CLOSURES / "example"
        directory.mkdir()
        for name in ("notes.md", "readme.md", "README.MD", "source.py"):
            path = directory / name
            path.write_text("[Must not be read](missing.md)\n")
            status, output, opened = self.check()
            self.assertEqual(status, 1)
            self.assertIn("Unexpected current-binding member", output)
            self.assertNotIn(path, opened)
            path.unlink()
        deep = directory
        for _ in range(33):
            deep /= "nested"
            deep.mkdir()
        (deep / "README.md").write_text("# Too deep\n")
        status, output, _ = self.check()
        self.assertEqual(status, 1)
        self.assertIn("Source directory depth limit exceeded", output)

    def test_non_markdown_descriptors_are_targets_not_markdown_or_payload_routes(self):
        descriptor = "benchmarks/neural/NEURAL-001/docs/inputs.json"
        self.document(descriptor, json.dumps({
            "private_payload": "/private/never-read-this.json",
            "note": "[This is data, not Markdown](does-not-exist.bin)",
        }))
        status, output, opened = self.check()
        self.assertEqual(status, 0)
        self.assertIn("1 registered non-Markdown targets", output)
        self.assertNotIn(self.root / descriptor, opened)
        (self.root / descriptor).unlink()
        self.assertEqual(self.check()[0], 1)

    def test_symlinked_page_refuses_before_any_external_read(self):
        outside = self.scratch / "outside.md"
        outside.write_text("Outside generated fixture\n")
        page = self.root / "README.md"
        page.unlink()
        page.symlink_to(outside)
        status, output, _ = self.check()
        self.assertEqual(status, 1)
        self.assertIn("ordinary single-link file", output)

    def test_symlinked_task_readme_refuses_before_any_external_read(self):
        outside = self.scratch / "outside.md"
        outside.write_text("Outside generated fixture\n")
        page = self.root / "benchmarks/neural/NEURAL-001/README.md"
        page.unlink()
        page.symlink_to(outside)
        self.assertEqual(self.check()[0], 1)

    def test_symlinked_ledger_refuses_before_any_external_read(self):
        outside = self.scratch / "outside-ledger.json"
        outside.write_text('{"files": []}\n')
        ledger = self.root / "docs/provenance/relocations/2026-11-16.json"
        ledger.unlink()
        ledger.symlink_to(outside)
        status, output, _ = self.check()
        self.assertEqual(status, 1)
        self.assertIn("Navigation source refused", output)

    def test_symlinked_usage_directory_refuses_before_external_traversal(self):
        outside = self.scratch / "outside-guides"
        outside.mkdir()
        (outside / "guide.md").write_text("Outside generated fixture\n")
        usage = self.root / "docs/usage"
        usage.rmdir()
        usage.symlink_to(outside, target_is_directory=True)
        status, output, _ = self.check()
        self.assertEqual(status, 1)
        self.assertIn("Source directory alias", output)

    def test_registry_document_cannot_escape_or_belong_to_another_task(self):
        for relative in ("../outside.md", "benchmarks/neural/NEURAL-002/docs/guide.md",
                         "benchmarks/neural/NEURAL-001/docs/../../outside.md"):
            with self.subTest(path=relative):
                self.registry["tasks"][0]["documentation"] = [{"label": "Invalid", "path": relative}]
                self.write_json("benchmarks/registry.json", self.registry)
                self.assertEqual(self.check()[0], 1)

    def test_frozen_notice_uses_only_exact_relocation_mappings(self):
        notice = "benchmarks/neural/NEURAL-001/docs/rights/notice.md"
        old_notice = "docs/neuroscience-benchmarks/releases/notice.md"
        old_license = "benchmarks/neuroscience/neural-001/LICENSE"
        license_path = "benchmarks/neural/NEURAL-001/implementations/example/LICENSE"
        body = "[MIT](../../../benchmarks/neuroscience/neural-001/LICENSE)\n"
        path = self.document(notice, body)
        original = path.read_bytes()
        self.write(license_path, "Generated license fixture\n")
        self.write_json("docs/provenance/relocations/2026-11-16.json", {"files": [
            {"old": old_notice, "new": notice}, {"old": old_license, "new": license_path},
        ]})
        with patch.object(navigation, "FROZEN_PAGES", frozenset({notice})):
            status, output, _ = self.check()
            self.assertEqual(status, 0)
            self.assertIn("1 historical references resolved", output)
            self.assertEqual(path.read_bytes(), original)
            self.write(notice, body + "[Unknown](unmapped.json)\n")
            status, output, _ = self.check()
            self.assertEqual(status, 1)
            self.assertIn("unresolved historical reference unmapped.json", output)

    def test_invalid_metadata_and_malformed_links_refuse_cleanly(self):
        self.write("README.md", "[Bad URL](https://[invalid)\n")
        status, output, _ = self.check()
        self.assertEqual(status, 1)
        self.assertIn("malformed link", output)
        self.write_json("benchmarks/registry.json", {"tasks": "invalid"})
        status, output, _ = self.check()
        self.assertEqual(status, 1)
        self.assertIn("Registry tasks must be a list", output)


if __name__ == "__main__":
    unittest.main()
