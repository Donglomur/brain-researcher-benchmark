"""Generated publication-mode controls; no data, candidates or containers run."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).absolute().parent
REPO = HERE.parents[4]
spec = importlib.util.spec_from_file_location("publication_adapter", HERE / "run.py")
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


class PublicationModes(unittest.TestCase):
    fixture_bytes_before_cleanup = 0

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="publication-modes-")
        self.root = Path(self.temp.name).resolve()
        self.candidate = self.root / "submitted.py"
        self.candidate.write_bytes(b"raise RuntimeError('Generated source must never execute')\n")
        self.stage = self.root / "stage"
        previous = os.umask(0o077)
        self.addCleanup(os.umask, previous)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.count_fixture_bytes)

    def count_fixture_bytes(self):
        count = sum(p.lstat().st_size for p in self.root.rglob("*")
                    if stat.S_ISREG(p.lstat().st_mode))
        type(self).fixture_bytes_before_cleanup += count
        self.assertLess(count, 262144, "Bounded generated fixture")

    def prepare(self):
        return a.stage(REPO, self.candidate, self.root / "absent-public",
                       self.stage, "sha256:" + "a" * 64)

    def transport_bounds(self):
        # Exercise the concrete transport's real permission guard without
        # importing a scorer, starting a provider or touching input payloads.
        _, bodies = a.dependency_sources(REPO)
        package = "_generated_publication_transport"
        namespace = types.ModuleType(package)
        namespace.__path__ = []
        sys.modules[package] = namespace
        self.addCleanup(sys.modules.pop, package, None)
        for name in ("engine", "bounds"):
            module = types.ModuleType(package + "." + name)
            module.__package__ = package
            module.__file__ = str(REPO / a.TRANSPORT / (name + ".py"))
            sys.modules[module.__name__] = module
            self.addCleanup(sys.modules.pop, module.__name__, None)
            exec(compile(bodies[a.TRANSPORT + "/" + name + ".py"],
                         module.__file__, "exec"), module.__dict__)
        return module

    def test_public_stage_survives_umask_and_real_mount_guard(self):
        self.prepare()
        plan = json.loads((self.stage / "PLAN.json").read_text())
        bounds = self.transport_bounds()
        meter = bounds.Meter(262144, 262144, time.monotonic() + 10)
        programs = [row for row in plan["mounts"].values() if row["purpose"] == "program"]
        self.assertEqual(len(programs), 2)
        for row in programs:
            self.assertEqual(stat.S_IMODE(Path(row["path"]).stat().st_mode), 0o444)
            bounds.tree(row, meter)
        self.assertEqual(stat.S_IMODE(self.stage.stat().st_mode), 0o700)
        for name in ("SOURCE.json", "PROGRAM_COMMIT.json", "PLAN.json", "EXPOSURE_REQUEST.json"):
            self.assertEqual(stat.S_IMODE((self.stage / name).stat().st_mode), 0o400)

    def test_private_modes_are_not_relaxed(self):
        with patch.object(a.os, "fchmod", side_effect=AssertionError("Private mode changed")):
            a.publish(self.root / "default-private", b"private")
            a.publish(self.root / "explicit-private", b"private", 0o600)
        self.assertEqual(stat.S_IMODE((self.root / "default-private").stat().st_mode), 0o400)
        self.assertEqual(stat.S_IMODE((self.root / "explicit-private").stat().st_mode), 0o600)

    def test_failed_permission_publication_closes_fd_and_leaves_no_plan(self):
        descriptors = []
        def fail(fd, mode):
            descriptors.append(fd)
            raise PermissionError("generated fchmod failure")
        with patch.object(a.os, "fchmod", side_effect=fail):
            with self.assertRaisesRegex(PermissionError, "generated fchmod failure"):
                self.prepare()
        self.assertEqual(len(descriptors), 1)
        with self.assertRaises(OSError):
            os.fstat(descriptors[0])
        self.assertFalse((self.stage / "SOURCE.json").exists())
        self.assertFalse((self.stage / "PLAN.json").exists())
        self.assertFalse((self.stage / "EXPOSURE_REQUEST.json").exists())
        self.assertEqual(stat.S_IMODE(self.stage.stat().st_mode), 0o700)
        partial = list(self.stage.iterdir())
        self.assertEqual(len(partial), 1)
        self.assertEqual(stat.S_IMODE(partial[0].stat().st_mode), 0o400)
        with self.assertRaises(ValueError):
            self.prepare()

    def test_existing_file_and_symlink_are_not_modified(self):
        target = self.root / "existing"
        target.write_bytes(b"keep")
        original_mode = stat.S_IMODE(target.stat().st_mode)
        with self.assertRaises(FileExistsError):
            a.publish(target, b"replace", 0o444)
        alias = self.root / "alias"
        alias.symlink_to(target)
        with self.assertRaises(ValueError):
            a.publish(alias, b"replace", 0o444)
        self.assertEqual(target.read_bytes(), b"keep")
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), original_mode)

    @classmethod
    def tearDownClass(cls):
        print(json.dumps({"fixture_bytes_before_cleanup": cls.fixture_bytes_before_cleanup,
                          "counter_scope": "Sum of generated regular-file lengths before each fixture cleanup",
                          "authentic_payload_reads": 0, "native_or_container_runs": 0,
                          "candidate_executions": 0}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
