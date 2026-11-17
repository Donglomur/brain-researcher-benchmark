"""Generated role-separation and captured-source controls; no native execution."""
import importlib.util
import json
import os
from pathlib import Path
import py_compile
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path("benchmarks/neural/NEURAL-030/implementations/cerebellar-executor")
CURRENT = Path("benchmarks/integrity/current-closures/trust-cerebellar/SOURCE_MANIFEST.json")


def load_source(path, name):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


class RoleSeparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = load_source(ROOT / PACKAGE / "test_executor.py", "_cerebellar_role_fixture")
        cls.c = cls.harness.c

    @classmethod
    def tearDownClass(cls):
        cls.harness.ctx.close()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="cerebellar-roles-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.request, self.commitment = self.harness.fixture(self.root)

    def refuse_before_operands(self, *, authority_edit=None, message="disjoint operand roles"):
        # Authenticated control records are required to learn the declared roles.
        # No commitment, procedure, source, public or private body may be opened
        # after those records expose an invalid mapping.
        with patch.object(self.c, "operand", side_effect=AssertionError("operand opened before refusal")):
            with self.assertRaisesRegex(ValueError, message):
                self.harness.admit(self.root, self.request, self.commitment, authority_edit)
        self.assertFalse(Path(self.request["root"]).exists())

    def test_each_private_operand_cannot_be_candidate_source(self):
        for role in ("expected", "mouse_binding", "fixed_reference"):
            with self.subTest(role=role):
                self.request["sources"]["fit"] = dict(self.request["private_evaluation"][role])
                self.refuse_before_operands()

    def test_private_operands_cannot_alias_other_inputs(self):
        for role in ("commitment", "procedure", "public"):
            with self.subTest(role=role):
                self.request[role] = dict(self.request["private_evaluation"]["expected"])
                self.refuse_before_operands()
                self.request, self.commitment = self.harness.fixture(self.root)

    def test_private_roles_are_distinct(self):
        self.request["private_evaluation"]["fixed_reference"] = dict(self.request["private_evaluation"]["expected"])
        self.refuse_before_operands()

    def test_private_paths_cannot_name_request_or_authority(self):
        for filename in ("REQUEST.json", "AUTHORITY.json"):
            with self.subTest(filename=filename):
                self.request["private_evaluation"]["expected"]["path"] = str(self.root / filename)
                self.refuse_before_operands()

    def test_native_control_cannot_alias_private_input(self):
        for name in ("docker_binary", "docker_socket"):
            with self.subTest(name=name):
                self.request["native"][name] = self.request["private_evaluation"]["expected"]["path"]
                self.refuse_before_operands()
                self.request, self.commitment = self.harness.fixture(self.root)

    def test_canonical_dotdot_alias_is_rejected(self):
        (self.root / "unused").mkdir()
        source = dict(self.request["private_evaluation"]["expected"])
        source["path"] = str(self.root / "unused" / ".." / "EXPECTED.json")
        self.request["sources"]["fit"] = source
        self.refuse_before_operands()

    def test_hardlink_alias_is_rejected_before_body_reads(self):
        alias = self.root / "expected-as-source.py"
        os.link(self.request["private_evaluation"]["expected"]["path"], alias)
        self.request["sources"]["fit"] = {**self.request["private_evaluation"]["expected"], "path": str(alias)}
        self.refuse_before_operands()

    def test_symlink_alias_is_rejected_before_body_reads(self):
        alias = self.root / "expected-as-source.py"
        alias.symlink_to(self.request["private_evaluation"]["expected"]["path"])
        self.request["sources"]["fit"] = {**self.request["private_evaluation"]["expected"], "path": str(alias)}
        self.refuse_before_operands(message="ordinary absolute path")

    def test_output_tree_cannot_contain_a_declared_private_input(self):
        self.request["private_evaluation"]["expected"]["path"] = str(Path(self.request["root"]) / "EXPECTED.json")
        self.refuse_before_operands()

    def test_nested_input_roles_are_rejected(self):
        self.request["private_evaluation"]["expected"]["path"] = str(self.root / "source-tree")
        self.request["sources"]["fit"]["path"] = str(self.root / "source-tree" / "fit.py")
        self.refuse_before_operands()

    def test_multiple_phases_may_use_one_committed_source_file(self):
        source = dict(self.request["sources"]["select"])
        self.request["sources"] = {role: dict(source) for role in self.c.PHASES}
        prepared = self.harness.admit(self.root, self.request, self.commitment)
        self.assertEqual(set(prepared["sources"]), set(self.c.PHASES))
        self.assertEqual(len(set(prepared["sources"].values())), 1)
        self.assertFalse(prepared["root"].exists())

    def test_valid_preflight_never_opens_private_bodies(self):
        private = {value["path"] for value in self.request["private_evaluation"].values()}
        original = self.c.read
        def watched(path, *args, **kwargs):
            self.assertNotIn(str(path), private)
            return original(path, *args, **kwargs)
        with patch.object(self.c, "read", side_effect=watched):
            prepared = self.harness.admit(self.root, self.request, self.commitment)
        self.assertEqual(len(prepared["panel"]["views"]), 64)

    def test_previous_source_authority_cannot_admit_changed_closure(self):
        self.refuse_before_operands(
            authority_edit=lambda authority: authority.update(source=self.harness.entry.HISTORICAL_SOURCE_PIN),
            message="externally selected authority/request/source binding")


class SourceClosureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="cerebellar-current-source-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.package = self.root / PACKAGE
        shutil.copytree(ROOT / PACKAGE, self.package, ignore=shutil.ignore_patterns("__pycache__"))
        self.current = self.root / CURRENT
        self.current.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / CURRENT, self.current)

    def inspect(self, *args):
        return subprocess.run([sys.executable, "-I", "-S", "-B", str(self.package / "entry.py"), "inspect", *args],
                              capture_output=True, text=True, timeout=15)

    def test_current_closure_is_portable_with_repository_layout(self):
        result = self.inspect()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["source_files"], 15)
        self.assertFalse(report["native_qualification"])
        self.assertFalse(report["scientific_qualification"])
        self.assertFalse(report["run_authorized"])

    def test_standalone_copy_requires_exact_explicit_current_companion(self):
        destination = self.root / "standalone"
        shutil.move(str(self.package), destination)
        self.package = destination
        self.assertNotEqual(self.inspect().returncode, 0)
        result = self.inspect("--current-manifest", str(self.current))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_changed_current_manifest_is_rejected(self):
        self.current.write_bytes(self.current.read_bytes() + b" ")
        self.assertNotEqual(self.inspect().returncode, 0)

    def test_historical_manifest_remains_authenticated(self):
        manifest = self.package / "SOURCE_MANIFEST.json"
        manifest.write_bytes(manifest.read_bytes() + b" ")
        self.assertNotEqual(self.inspect().returncode, 0)

    def test_changed_controller_is_rejected(self):
        path = self.package / "controller.py"
        path.write_bytes(path.read_bytes() + b"\nraise AssertionError('not authenticated')\n")
        result = self.inspect()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("AssertionError: not authenticated", result.stderr)

    def test_current_manifest_symlink_is_rejected(self):
        other = self.root / "descriptor.json"
        self.current.rename(other)
        self.current.symlink_to(other)
        self.assertNotEqual(self.inspect().returncode, 0)

    def test_captured_import_ignores_timestamp_valid_bytecode(self):
        source = self.package / "controller.py"
        stamp = source.stat()
        poison = self.root / "poison.py"
        payload = b"CACHE_USED = True\n"
        poison.write_bytes(payload + b"#" * (stamp.st_size - len(payload)))
        os.utime(poison, (stamp.st_atime, stamp.st_mtime))
        cache = Path(importlib.util.cache_from_source(str(source)))
        cache.parent.mkdir(exist_ok=True)
        py_compile.compile(str(poison), cfile=str(cache), doraise=True)
        # Establish that this is an actually usable stale cache, not merely a
        # malformed file ignored for an unrelated reason.
        spec = importlib.util.spec_from_file_location("_cache_witness", source)
        witness = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(witness)
        self.assertTrue(witness.CACHE_USED)
        entry = load_source(self.package / "entry.py", "_captured_cerebellar_entry")
        ctx = entry.context()
        try:
            module = ctx.module("controller")
            self.assertFalse(hasattr(module, "CACHE_USED"))
            self.assertTrue(callable(module.validate_role_paths))
        finally:
            ctx.close()


if __name__ == "__main__":
    unittest.main()
