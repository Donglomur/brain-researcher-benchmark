"""Generated portable-package boundaries, separate from scientific qualification."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

BOOTSTRAP = None
PACKAGE = None


class PackageControls(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "relocated programme with spaces"
        self.root.mkdir()
        for name, body in PACKAGE.captured.items():
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
        manifest = BOOTSTRAP.stable_read(PACKAGE.manifest_path,
                                       BOOTSTRAP.MAX_MEMBER, PACKAGE.selected)
        self.current_manifest = None
        self.manifest_path = self.root / BOOTSTRAP.MANIFEST
        if PACKAGE.predecessor is not None:
            historical = BOOTSTRAP.stable_read(PACKAGE.root / BOOTSTRAP.MANIFEST,
                                               BOOTSTRAP.MAX_MEMBER, PACKAGE.predecessor)
            self.manifest_path.write_bytes(historical)
            self.manifest_path = self.base / "current-manifest.json"
            self.current_manifest = self.manifest_path
        self.manifest_path.write_bytes(manifest)
        self.selected = dict(PACKAGE.selected)

    def tearDown(self):
        self.temporary.cleanup()

    def verify(self, root=None):
        return BOOTSTRAP.verify(self.root if root is None else root,
                                self.selected["bytes"], self.selected["sha256"],
                                current_manifest=self.current_manifest)

    def repin_manifest(self, mutate):
        path = self.manifest_path
        doc = json.loads(path.read_bytes())
        mutate(doc)
        body = (json.dumps(doc, indent=2) + "\n").encode()
        path.write_bytes(body)
        self.selected.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())

    def test_relocated_closed_package_preserves_full_scope(self):
        p = self.verify()
        d = p.describe()
        self.assertEqual(len(d["operations"]), 26)
        self.assertEqual(d["dense_spectra"], 40)
        self.assertEqual(d["dense_output_shapes"], [(10000, 2)])
        self.assertEqual(d["main_sessions"], 29)
        self.assertEqual(len(d["scientific_runtime_gates"]), 32)
        self.assertTrue(all(x["state"] == "open" for x in d["scientific_runtime_gates"]))
        self.assertEqual(d["profiles"]["complete"], d["profiles"]["reproduction"])

    def test_relocated_cli_verifies_without_private_checkout(self):
        command = [sys.executable, "-I", "-S", "-B", str(self.root / "package_tools.py"),
                   "verify", "--root", str(self.root), "--manifest-bytes", str(self.selected["bytes"]),
                   "--manifest-sha256", self.selected["sha256"]]
        if self.current_manifest is not None:
            command.extend(["--current-manifest", str(self.current_manifest)])
        result = subprocess.run(command, cwd=self.base, capture_output=True, timeout=15, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["source_members"], len(PACKAGE.captured))

    def test_wrong_release_pin_refused(self):
        self.selected["sha256"] = "0" * 64
        with self.assertRaises(BOOTSTRAP.PackageError):
            self.verify()

    def test_current_selection_preserves_historical_manifest(self):
        if self.current_manifest is None:
            return
        path = self.root / BOOTSTRAP.MANIFEST
        path.write_bytes(path.read_bytes()+b" ")
        with self.assertRaisesRegex(BOOTSTRAP.PackageError, "source pin mismatch"):
            self.verify()

    def test_current_selection_cannot_crop_roster(self):
        if self.current_manifest is None:
            return
        self.repin_manifest(lambda document: document["members"].pop())
        with self.assertRaisesRegex(BOOTSTRAP.PackageError, "same complete source roster"):
            self.verify()

    def test_current_selection_cannot_repin_scientific_contract(self):
        if self.current_manifest is None:
            return
        def change(document):
            row = next(x for x in document["members"] if x["path"] == "source/contracts/COHORT.json")
            row["sha256"] = "0"*64
        self.repin_manifest(change)
        with self.assertRaisesRegex(BOOTSTRAP.PackageError, "preserved scientific contracts"):
            self.verify()

    def test_changed_scientific_contract_refused(self):
        path = self.root / "source/contracts/COHORT.json"
        path.write_bytes(path.read_bytes().replace(b'"session_count": 29', b'"session_count": 28'))
        with self.assertRaises(BOOTSTRAP.PackageError):
            self.verify()

    def test_missing_module_refused(self):
        (self.root / "source/critical/native_worker.py").unlink()
        with self.assertRaises(BOOTSTRAP.PackageError):
            self.verify()

    def test_extra_module_and_empty_directory_refused(self):
        (self.root / "source/critical/injected.py").write_text("raise AssertionError('not executed')\n")
        with self.assertRaises(BOOTSTRAP.PackageError):
            self.verify()
        (self.root / "source/critical/injected.py").unlink()
        (self.root / "extra-empty").mkdir()
        with self.assertRaises(BOOTSTRAP.PackageError):
            self.verify()

    def test_symlink_member_never_opened(self):
        path = self.root / "source/critical/native.py"
        path.unlink()
        path.symlink_to(self.base / "forbidden-target")
        with patch.object(BOOTSTRAP.os, "open", side_effect=AssertionError("body read before tree refusal")):
            with self.assertRaises(BOOTSTRAP.PackageError):
                BOOTSTRAP.closed_tree(self.root, {*PACKAGE.captured, BOOTSTRAP.MANIFEST})

    def test_hardlink_member_refused(self):
        os.link(self.root / "README.md", self.base / "other-readme")
        with self.assertRaises(BOOTSTRAP.PackageError):
            self.verify()

    def test_fifo_member_refused_without_block(self):
        path = self.root / "README.md"
        path.unlink()
        os.mkfifo(path)
        with self.assertRaises(BOOTSTRAP.PackageError):
            self.verify()

    def test_root_symlink_refused(self):
        alias = self.base / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(BOOTSTRAP.PackageError):
            self.verify(alias)

    def test_noncanonical_root_refused_before_metadata(self):
        with patch.object(Path, "lstat", side_effect=AssertionError("metadata before lexical check")):
            for root in ("/" + str(self.root), str(self.root) + "/../x", str(self.root) + "/", "relative"):
                with self.subTest(root=root), self.assertRaises(BOOTSTRAP.PackageError):
                    self.verify(root)

    def test_traversal_manifest_refused(self):
        self.repin_manifest(lambda d: d["members"][0].update(path="../outside.py"))
        with self.assertRaises(BOOTSTRAP.PackageError):
            self.verify()

    def test_duplicate_manifest_member_refused(self):
        self.repin_manifest(lambda d: d["members"].append(d["members"][0]))
        with self.assertRaises(BOOTSTRAP.PackageError):
            self.verify()

    def test_manifest_boolean_extent_refused(self):
        self.repin_manifest(lambda d: d["members"][0].update(bytes=True))
        with self.assertRaises(BOOTSTRAP.PackageError):
            self.verify()

    def test_duplicate_json_key_refused(self):
        with self.assertRaises(BOOTSTRAP.PackageError):
            BOOTSTRAP.decode(b'{"x": 1, "x": 2}')

    def test_pycache_refused_before_code_load(self):
        cache = self.root / "source/critical/__pycache__"
        cache.mkdir()
        (cache / "native.cpython-311.pyc").write_bytes(b"generated not bytecode")
        with self.assertRaises(BOOTSTRAP.PackageError):
            self.verify()

    def test_existing_module_owner_refused(self):
        p = self.verify()
        # Outer actual test context owns critical; a second owner must refuse.
        with self.assertRaises(BOOTSTRAP.PackageError):
            with p.installed():
                self.fail("preloaded module escaped")

    def test_captured_loader_ignores_changed_module_body(self):
        p = self.verify()
        target = self.root / "source/critical/__init__.py"
        target.write_text("raise AssertionError('changed disk executed')\n")
        module = types.ModuleType("generated_captured_probe")
        loader = BOOTSTRAP.CapturedLoader(p, module.__name__, "source/critical/__init__.py")
        loader.exec_module(module)
        self.assertIs(p.loaded[module.__name__], module)
        self.assertIsNone(module.__cached__)

    def test_offline_dependency_roster_retains_drivers(self):
        rows = self.verify().author_members()
        self.assertEqual(len(rows), 18)
        self.assertEqual(sum(r["path"].endswith(".py") for r in rows), 15)
        self.assertIn("fig2/fig2.driver.code.py", {r["path"] for r in rows})
        self.assertIn("fig3/fig3.driver.code.py", {r["path"] for r in rows})

    def test_generated_external_source_exact_tree_and_pin(self):
        p = self.verify()
        p.captured = dict(p.captured)
        doc = json.loads(p.captured["source/contracts/AUTHOR_EXPOSURE.json"])
        external = self.base / "generated-external"
        external.mkdir()
        for row in doc["members"]:
            body = ("generated source-only role: " + row["path"] + "\n").encode()
            row.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
            target = external / row["path"][7:]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
        p.captured["source/contracts/AUTHOR_EXPOSURE.json"] = json.dumps(doc).encode()
        result = p.verify_author(external)
        self.assertEqual(result["verified_external_members"], 18)
        self.assertFalse(result["native_authority_granted"])
        (external / "fig2/fig2.driver.code.py").write_text("changed")
        with self.assertRaises(BOOTSTRAP.PackageError):
            p.verify_author(external)

    def test_external_source_overlap_refused(self):
        p = self.verify()
        for path in (self.root, self.root / "source", self.base):
            with self.subTest(path=str(path)), self.assertRaises(BOOTSTRAP.PackageError):
                p.verify_author(path)

    def test_argument_does_not_issue_live_lease(self):
        from critical.native_worker import run_reference_programme
        from critical.core import Costs
        # JSON is not a live issuer; failure happens before native work.
        with self.assertRaises((AttributeError, ValueError)):
            run_reference_programme({}, {"source_sha256": "a" * 64}, {}, {}, Costs(0, 0),
                                    {}, {}, self.root, self.root, "generated")
