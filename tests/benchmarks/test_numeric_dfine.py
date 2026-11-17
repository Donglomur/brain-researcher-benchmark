"""Authenticate current DFINE source before generated numeric/relocation controls."""

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
DESCRIPTOR = Path("benchmarks/integrity/current-closures/numeric-dfine/CURRENT_SOURCE.json")
DESCRIPTOR_BYTES = 5261
DESCRIPTOR_SHA256 = "7aa489bfcad71dca1834c5f1698d037b676019c597e7160014c7cd409f838611"


def read_pin(root, pin):
    relative = Path(pin["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("source path must be repository-relative")
    path = root / relative
    if any(part.is_symlink() for part in (path, *path.parents) if part != root.parent):
        raise ValueError("source requires ordinary non-symlink paths")
    if not path.is_file():
        raise ValueError("source member must be an ordinary file")
    body = path.read_bytes()
    if (len(body), hashlib.sha256(body).hexdigest()) != (pin["bytes"], pin["sha256"]):
        raise ValueError("current source identity mismatch: " + pin["path"])
    return body


def authenticate(root):
    descriptor = json.loads(read_pin(root, {"path": str(DESCRIPTOR),
        "bytes": DESCRIPTOR_BYTES, "sha256": DESCRIPTOR_SHA256}))
    if descriptor["schema"] != "dfine_numeric_current_source_v1":
        raise ValueError("wrong current descriptor schema")
    package = root / descriptor["package_root"]
    expected = {root / pin["path"] for pin in descriptor["files"]}
    entries = set(package.iterdir())
    if package.is_symlink() or entries != expected:
        raise ValueError("current source namespace mismatch")
    for pin in descriptor["files"]:
        read_pin(root, pin)
    return descriptor


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class CurrentBinding(unittest.TestCase):
    def test_current_identity_historical_manifest_and_qualification_holds(self):
        descriptor = authenticate(ROOT)
        package = ROOT / descriptor["package_root"]
        historical = json.loads(read_pin(ROOT, descriptor["historical_manifest"]))
        changed = []
        for pin in historical["files"]:
            body = (package / pin["path"]).read_bytes()
            if (len(body), hashlib.sha256(body).hexdigest()) != (pin["bytes"], pin["sha256"]):
                changed.append(pin["path"])
        self.assertEqual(changed, descriptor["changed_historical_members"])
        self.assertEqual(changed, ["scorer.py", "test_scorer.py"])
        self.assertEqual({p.name for p in package.iterdir()},
                         {pin["path"] for pin in historical["files"]} | {"SOURCE_MANIFEST.json"})
        for pin in descriptor["preserved_task_and_correction"]:
            read_pin(ROOT, pin)
        for pin in descriptor["files"]:
            body = read_pin(ROOT, pin)
            self.assertNotIn(b"/" + b"Users/", body)
            self.assertNotIn(b"benchmark-" + b"engineering-evidence", body)
            self.assertEqual(body, ("\n".join(line.rstrip() for line in body.decode().splitlines()).rstrip() + "\n").encode())
        spec = json.loads((package / "SPEC.json").read_bytes())
        for field in ("ready_to_run_authentic_benchmark", "candidate_execution_verified", "native_reference_qualified"):
            self.assertIs(spec[field], False)
        self.assertEqual(spec["runtime"]["third_party_packages"], [])
        for field in ("execution_authority", "authentic_data_verified", "native_reference_qualified", "scientific_qualification"):
            self.assertIs(descriptor[field], False)

    def test_current_authentication_refuses_changed_bytes_and_namespace(self):
        descriptor = authenticate(ROOT)
        with tempfile.TemporaryDirectory(prefix="dfine-current-binding-") as td:
            root = Path(td).resolve()
            package = root / descriptor["package_root"]
            shutil.copytree(ROOT / descriptor["package_root"], package)
            (root / DESCRIPTOR).parent.mkdir(parents=True)
            shutil.copyfile(ROOT / DESCRIPTOR, root / DESCRIPTOR)
            authenticate(root)
            scorer = package / "scorer.py"
            original = scorer.read_bytes()
            scorer.write_bytes(b"#" + original[1:])
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                authenticate(root)
            scorer.write_bytes(original)
            extra = package / "unexpected.py"
            extra.write_text("raise AssertionError('must never import')\n")
            with self.assertRaisesRegex(ValueError, "namespace mismatch"):
                authenticate(root)
            extra.unlink()
            backup = root / "scorer.backup"
            scorer.rename(backup)
            scorer.symlink_to(backup)
            with self.assertRaisesRegex(ValueError, "non-symlink"):
                authenticate(root)


def load_tests(loader, standard_tests, pattern):
    # The unchanged historical inventory hashes are superseded explicitly; its
    # relocated CLI/target-last test still runs against the authenticated source.
    descriptor = authenticate(ROOT)
    package = ROOT / descriptor["package_root"]
    numeric = module(package / "test_scorer.py", "current_dfine_numeric_controls")
    portable = module(package / "test_portability.py", "current_dfine_portable_controls")
    standard_tests.addTests(loader.loadTestsFromModule(numeric))
    standard_tests.addTest(portable.PortableSource("test_relocated_complete_cli_and_private_target_order"))
    if standard_tests.countTestCases() != descriptor["validation"]["total_tests"]:
        raise ValueError("complete current DFINE test population required")
    return standard_tests


if __name__ == "__main__":
    unittest.main(verbosity=2)
