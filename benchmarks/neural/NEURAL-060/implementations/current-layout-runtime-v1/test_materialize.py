"""Tiny source-only controls; no recording, estimator, provider, or target access."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
spec = importlib.util.spec_from_file_location("neural060_materialize", HERE / "materialize.py")
relocation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relocation)


class RelocationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="neural060-source-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.original = REPO / relocation.PROGRAM
        self.source = self.repo / relocation.PROGRAM
        self.source.mkdir(parents=True)
        manifest = json.loads((self.original / "SOURCE_MANIFEST.json").read_bytes())
        for name in [*manifest["files"], "SOURCE_MANIFEST.json"]:
            destination = self.source / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.original / name, destination)
        roster = self.repo / relocation.ROSTER
        roster.parent.mkdir(parents=True)
        shutil.copyfile(REPO / relocation.ROSTER, roster)
        self.output = self.root / "runtime"

    def test_original_fails_and_successor_loads_exact_original_roster(self):
        original = relocation.captured_bootstrap(
            (self.source / "bootstrap.py").read_bytes(), self.source / "bootstrap.py")
        with self.assertRaises(FileNotFoundError):
            original.roster(self.repo)
        receipt = relocation.materialize(str(self.repo), str(self.output))
        current = relocation.captured_bootstrap(
            (self.output / "bootstrap.py").read_bytes(), self.output / "bootstrap.py")
        raw = current.roster(self.repo)
        self.assertEqual(relocation.pin(raw), relocation.ROSTER_PIN)
        loaded = current.Sources(self.output, receipt["successor_manifest"])
        roster = loaded.module("projection").admit_sources(raw)
        self.assertEqual(len(roster["assets"]), 29)
        self.assertEqual(len({row["subject"] for row in roster["assets"]}), 13)
        self.assertEqual(len({row["lab"] for row in roster["assets"]}), 7)
        # Import every captured scientific module, without invoking numerical work.
        for module in current.MODULES:
            loaded.module(module)
        self.assertFalse({"numpy", "h5py", "sklearn"} & set(sys.modules))

    def test_only_declared_compatibility_changes_and_manifest_covers_full_closure(self):
        receipt = relocation.materialize(str(self.repo), str(self.output))
        before = json.loads((self.source / "SOURCE_MANIFEST.json").read_bytes())
        after = json.loads((self.output / "SOURCE_MANIFEST.json").read_bytes())
        self.assertEqual(set(before["files"]), set(after["files"]))
        self.assertEqual(len(after["files"]), 18)
        changed = []
        for name in before["files"]:
            left, right = (self.source / name).read_bytes(), (self.output / name).read_bytes()
            self.assertEqual(after["files"][name], relocation.pin(right))
            if left != right:
                changed.append(name)
                if name == "bootstrap.py":
                    self.assertEqual(right.replace(relocation.ROSTER.encode(), relocation.OLD_ROSTER.encode()), left)
                else:
                    self.assertEqual(name, "engine.py")
                    self.assertEqual(right.replace(relocation.ENGINE_CHECK_AFTER, relocation.ENGINE_CHECK_BEFORE), left)
        self.assertEqual(changed, ["bootstrap.py", "engine.py"])
        self.assertEqual(len(receipt["unchanged_runtime_files"]), 16)
        self.assertNotEqual(receipt["predecessor_manifest"], receipt["successor_manifest"])
        self.assertEqual(relocation.pin((self.source / "SOURCE_MANIFEST.json").read_bytes()),
                         relocation.MANIFEST_PIN)
        print(json.dumps({"successor_manifest": receipt["successor_manifest"],
                          "successor_bootstrap": receipt["change"]["after"],
                          "successor_engine": receipt["inspect_compatibility"]["after"]}, sort_keys=True))

    def test_real_entrypoint_help_from_unrelated_working_directory(self):
        relocation.materialize(str(self.repo), str(self.output))
        process = subprocess.run([sys.executable, "-I", "-B", str(self.output / "entry.py"), "--help"],
                                 cwd=self.root, text=True, capture_output=True, timeout=5)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("{observe,worker,grade}", process.stdout)

    def test_real_entrypoint_preserves_inactive_authority_gate(self):
        receipt = relocation.materialize(str(self.repo), str(self.output))
        authority = self.root / "inactive.json"
        raw = b'{"schema":"neural060_root_authority_v1","active":false}'
        authority.write_bytes(raw)
        bootstrap, manifest, declared = (receipt["change"]["after"],
                                         receipt["successor_manifest"], relocation.pin(raw))
        command = [sys.executable, "-I", "-B", str(self.output / "entry.py"), "observe",
                   "--repo", str(self.repo), "--bootstrap-bytes", str(bootstrap["bytes"]),
                   "--bootstrap-sha256", bootstrap["sha256"], "--manifest-bytes", str(manifest["bytes"]),
                   "--manifest-sha256", manifest["sha256"], "--authority", str(authority),
                   "--authority-bytes", str(declared["bytes"]), "--authority-sha256", declared["sha256"],
                   "--original-origin", "0"]
        process = subprocess.run(command, cwd=self.root, text=True, capture_output=True, timeout=5)
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("not qualified: source-only NEURAL060 authority", process.stderr)
        self.assertEqual(process.stdout, "")

    def test_successor_is_deterministic_across_destination_paths(self):
        first = relocation.materialize(str(self.repo), str(self.output))
        other = self.root / "another-runtime"
        second = relocation.materialize(str(self.repo), str(other))
        self.assertEqual(first, second)
        for path in self.output.rglob("*"):
            if path.is_file():
                self.assertEqual(path.read_bytes(), (other / path.relative_to(self.output)).read_bytes())

    def test_mutated_predecessor_or_roster_fails_before_output(self):
        for name in [self.source / "bootstrap.py", self.source / "grader.py",
                     self.source / "SOURCE_MANIFEST.json", self.repo / relocation.ROSTER]:
            with self.subTest(name=name.name):
                before = name.read_bytes()
                name.write_bytes(before[:-1] + bytes([before[-1] ^ 1]))
                with self.assertRaises(ValueError):
                    relocation.materialize(str(self.repo), str(self.output))
                self.assertFalse(self.output.exists())
                name.write_bytes(before)

    def test_reject_source_symlink_without_output(self):
        path = self.source / "grader.py"
        backup = self.root / "actual-grader.py"
        path.rename(backup)
        path.symlink_to(backup)
        with self.assertRaises((ValueError, OSError)):
            relocation.materialize(str(self.repo), str(self.output))
        self.assertFalse(self.output.exists())

    def test_refuse_alias_noncanonical_existing_and_in_repo_destinations(self):
        for path in [str(self.root) + "/../runtime", str(self.root) + "//runtime",
                     str(self.root) + "/./runtime", "runtime", str(self.repo / "generated")]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                relocation.materialize(str(self.repo), path)
        alias = self.root / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            relocation.materialize(str(self.repo), str(alias / "runtime"))
        self.output.mkdir()
        sentinel = self.output / "keep"
        sentinel.write_text("do not replace")
        with self.assertRaises(ValueError):
            relocation.materialize(str(self.repo), str(self.output))
        self.assertEqual(sentinel.read_text(), "do not replace")


if __name__ == "__main__":
    unittest.main(verbosity=2)
