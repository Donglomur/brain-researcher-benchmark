"""Invented interface controls. No originals, fits, native imports or private answers."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = json.loads((HERE / "SOURCE_MANIFEST.json").read_text())
PREFIX = MANIFEST["worker"]["path"].rsplit("/", 1)[0]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CONTRACT = load("portable_contract_test", ROOT / PREFIX / "external_contract.py")
BINDER = load("portable_binder_test", HERE / "bind_request.py")


def invented_metadata():
    subjects = ["invented-animal-%02d" % n for n in range(16)]
    members = [{"path": name, "bytes": 1, "columns": ["invented_field"],
                "footer_advertised_rows": 0, "footer_sha256": "0" * 64}
               for name in sorted(CONTRACT.TABLES)]
    members += [{"path": "invented-metadata-%d.txt" % n, "bytes": 1} for n in range(4)]
    inputs = {"schema": "findlay-full-input-contract/v1", "member_count": 17,
        "parquet_member_count": 13, "static_subjects": 16, "static_sessions": 29,
        "archive_bytes": 3015691, "members": members,
        "static_source_roster": [{"subject": name, "protocols": ["invented-one"] +
            (["invented-two"] if i < 13 else [])} for i, name in enumerate(subjects)]}
    families = {"schema": "findlay-published98-exact-family-join/v1", "published_families": 98,
        "rows": [{"source_analysis_id": name, "source_parameters": {},
                  "input_tables": [], "table1_row": i}
                 for i, name in enumerate(sorted(CONTRACT.IDS))]}
    policy = {"schema": "findlay-private-identity-policy/v1", "balanced_subjects": subjects[:5],
        "ordinary_exclusion": {"subject": subjects[0], "experiment": "Novelty",
            "columns": ["invented-column-%02d" % n for n in range(13)]},
        "provenance": {
            "family_rules_sha256": "099c182250d5610a4f9aea3c58e9897fae96157eb464c5c24f327eb60a35d2f4",
            "ordinary_policy_sha256": "d9ef897d0387fa3785ea46f94730e886b429a38ca5e589e89e82134fa1725b01",
            "input_ledger_sha256": CONTRACT.PINS["input_ledger"]["sha256"],
            "family_ledger_sha256": CONTRACT.PINS["published_families"]["sha256"]}}
    return {"input_ledger": inputs, "published_families": families, "private_policy": policy}


class MetadataTests(unittest.TestCase):
    def test_full_shape_and_join_are_not_authentic_admission(self):
        values = invented_metadata()
        for field, value in values.items():
            CONTRACT.validate_schema(field, value)
            with self.assertRaises(ValueError):
                CONTRACT.authenticate(field, (json.dumps(value) + "\n").encode())
        CONTRACT.join(values)

    def test_reduced_duplicate_and_relabelled_family_scope_refused(self):
        for mode in ("short", "duplicate", "alias"):
            value = invented_metadata()["published_families"]
            if mode == "short": value["rows"].pop()
            if mode == "duplicate": value["rows"][-1] = copy.deepcopy(value["rows"][0])
            if mode == "alias": value["rows"][-1]["source_analysis_id"] = "invented:99"
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                CONTRACT.validate_schema("published_families", value)

    def test_missing_table_duplicate_animal_and_boolean_count_refused(self):
        for mode in ("missing_table", "duplicate_animal", "bool"):
            value = invented_metadata()["input_ledger"]
            if mode == "missing_table": value["members"][0]["path"] = "invented-other.pqt"
            if mode == "duplicate_animal": value["static_source_roster"][-1]["subject"] = value["static_source_roster"][0]["subject"]
            if mode == "bool": value["static_subjects"] = True
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                CONTRACT.validate_schema("input_ledger", value)

    def test_policy_provenance_and_identity_join_refused(self):
        values = invented_metadata()
        values["private_policy"]["provenance"]["family_rules_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            CONTRACT.validate_schema("private_policy", values["private_policy"])
        values = invented_metadata()
        values["private_policy"]["balanced_subjects"][0] = "invented-absent-animal"
        with self.assertRaises(ValueError): CONTRACT.join(values)

    def test_duplicate_and_nonfinite_json_refused(self):
        for body in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.assertRaises(ValueError): CONTRACT.decode(body)


class RelocationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve() / "relocated checkout"
        self.root.mkdir()
        for relative in MANIFEST["files"]:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        self.component = self.root / "components/findlay-complete-preparation"
        self.component.mkdir(parents=True)
        for name in ("SOURCE_MANIFEST.json", "bind_request.py"):
            shutil.copyfile(HERE / name, self.component / name)
        self.owner = load("portable_relocated_owner", self.root / MANIFEST["entrypoint"]["path"])
        self.binder = load("portable_relocated_binder", self.component / "bind_request.py")
        self.private = Path(self.temp.name).resolve() / "private"
        self.private.mkdir()
        self.output_parent = self.root / "artifacts-build"
        self.output_parent.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def make_request(self):
        lock = {**MANIFEST, "schema": "findlay-intake-source-lock/v1", "repository_root": str(self.root)}
        lock_pin = self.owner.write(self.private / "lock.json", lock)
        # These are deliberately invalid invented metadata. They must never be admitted.
        metadata = self.owner.write(self.private / "invented.json", {"invented": True})
        request = {"schema": "findlay-portable-census-continuation-request/v1",
            "execution": {"repository_root": str(self.root), "output_root": str(self.output_parent / "unused"),
                "source_lock": lock_pin, "runtime_manifest": metadata,
                "source_adoption": {"commit": "0" * 40, "worker": MANIFEST["worker"]},
                "profile": self.owner.PROFILE},
            "task": {key: metadata for key in CONTRACT.PINS}}
        request["task"].update(prior_attempt=metadata, data_read_cap=33554432, worker_output_cap=33554432)
        return request, lock

    def test_complete_source_graph_relocates_and_private_data_are_not_git_members(self):
        request, lock = self.make_request()
        body = self.owner.canonical(request)
        path = self.private / "request.json";path.write_bytes(body)
        self.owner.load_request(path, hashlib.sha256(body).hexdigest())
        checked = self.owner.source_lock(request)
        self.assertEqual(len(checked["files"]), 13)
        self.assertTrue(all(p.endswith(".py") and not Path(p).is_absolute() for p in checked["files"]))
        self.assertEqual(self.binder.ROOT, self.root)
        # Admitted software is read from relocated paths. Fixed metadata then rejects;
        # no Git adoption, runtime verification or native operation is mocked as success.
        with self.assertRaisesRegex(ValueError, "Exact accepted private metadata"):
            self.owner.source_capture(request, lock, time.monotonic() + 5)
        self.assertFalse((self.output_parent / "unused").exists())

    def test_private_admission_preserves_original_deadline(self):
        request, lock = self.make_request()
        with mock.patch.object(self.owner.time, "monotonic", side_effect=[0] * 13 + [2]):
            with self.assertRaisesRegex(ValueError, "Private metadata original deadline"):
                self.owner.source_capture(request, lock, 1)

    def test_software_drift_refuses_before_private_metadata(self):
        request, lock = self.make_request()
        path = self.root / PREFIX / "ordinary_reconciliation.py"
        path.write_bytes(path.read_bytes() + b"\n# invented drift\n")
        with self.assertRaisesRegex(ValueError, "pin mismatch"):
            self.owner.source_capture(request, lock, time.monotonic() + 5)

    def test_private_metadata_inside_checkout_refused(self):
        request, _ = self.make_request()
        request["task"]["private_policy"]["path"] = str(self.root / "invented-private.json")
        body = self.owner.canonical(request);path = self.private / "request.json";path.write_bytes(body)
        with self.assertRaisesRegex(ValueError, "outside checkout"):
            self.owner.load_request(path, hashlib.sha256(body).hexdigest())

    def test_binding_invalid_metadata_writes_nothing(self):
        p = self.private / "invented.json";p.write_text('{"invented":true}\n')
        args = types.SimpleNamespace(commit="0" * 40, input_ledger=str(p),
            published_families=str(p), private_policy=str(p), prior_attempt=str(p),
            runtime_manifest=str(p), operation_output=str(self.output_parent / "unused"),
            write_dir=str(self.private))
        with self.assertRaisesRegex(ValueError, "Exact accepted private metadata"):
            self.binder.build(args)
        self.assertFalse((self.private / "source-lock.json").exists())
        self.assertFalse((self.private / "request.json").exists())

    def test_symlinked_external_member_refused(self):
        p = self.private / "original";p.write_bytes(b"x")
        alias = self.private / "alias";alias.symlink_to(p)
        with self.assertRaisesRegex(ValueError, "Unlinked"):
            self.owner.checked({"path": str(alias), "bytes": 1, "sha256": hashlib.sha256(b"x").hexdigest()})

    def test_binder_help_is_portable_and_inert(self):
        result = subprocess.run([sys.executable, "-I", "-S", "-B", str(self.component / "bind_request.py"), "--help"],
            capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn(b"--private-policy", result.stdout)
        self.assertFalse((self.output_parent / "unused").exists())


class BootstrapTests(unittest.TestCase):
    def test_oversized_empty_and_linked_source_refused_before_open(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            large = root / "large";large.write_bytes(b"x" * 65)
            empty = root / "empty";empty.write_bytes(b"")
            original = root / "original";original.write_bytes(b"x")
            link = root / "hardlink";os.link(original, link)
            for path in (large, empty, link):
                with mock.patch.object(BINDER.os, "open", side_effect=AssertionError("must refuse before opening")):
                    with self.assertRaises(ValueError): BINDER.capture(path, 64)

    def test_loaded_bytes_are_the_captured_body_after_path_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp).resolve() / "source.py"
            path.write_bytes(b"VALUE = 17\n")
            body = BINDER.capture(path, 64)
            path.write_bytes(b"raise AssertionError('reopened path')\n")
            module = BINDER.load("invented_captured_module", path, body)
            self.assertEqual(module.VALUE, 17)

    def test_fifo_replacement_refuses_without_blocking_and_closes_fd(self):
        import os
        owner = load("invented_fifo_owner", ROOT / MANIFEST["entrypoint"]["path"])
        for reader in (BINDER.capture, owner.capture):
            with self.subTest(reader=reader.__module__), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp).resolve() / "replace-me"
                path.write_bytes(b"ordinary source")
                original_open = os.open; opened = []
                def replace_before_open(actual_path, flags):
                    self.assertTrue(flags & os.O_NONBLOCK, "replacement must never block")
                    path.unlink();os.mkfifo(path)
                    fd = original_open(actual_path, flags)
                    opened.append(fd)
                    return fd
                with mock.patch.object(os, "open", side_effect=replace_before_open):
                    with self.assertRaises(ValueError): reader(path, 64)
                self.assertEqual(len(opened), 1)
                with self.assertRaises(OSError): os.fstat(opened[0])

    def test_duplicate_or_nonfinite_source_manifest_refused(self):
        for body in (b'{"a":1,"a":2}', b'{"a":NaN}'):
            with self.assertRaises(ValueError): BINDER.decode(body)


class SourceTests(unittest.TestCase):
    def test_private_output_root_is_ignored(self):
        self.assertIn("/artifacts-build/", (ROOT / ".gitignore").read_text().splitlines())

    def test_unchanged_numeric_core_tail_and_v4_owner(self):
        pins = {
            PREFIX + "/ordinary_reconciliation.py": "5f0097505103558f6bdcae564f8c3ea4dd509e2c5016d14cb0c83f665c5a9133",
            PREFIX + "/census_tail.py": "3c58c6cbd22ac5389c1695ca40d7fdb90585a5d7ab497cba1bdb626a0c74a86f",
            "authoring/shared-program-ownership-v4/process_owner.py": "b9e8f366f4b639a87e6c7c580e4bceff228c031cd767a4a3bebe37ea85d496ea"}
        for relative, digest in pins.items():
            self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), digest)

    def test_all_runtime_files_are_pinned_and_public_body_has_no_local_identity(self):
        for relative, pin in MANIFEST["files"].items():
            body = (ROOT / relative).read_bytes()
            self.assertEqual((len(body), hashlib.sha256(body).hexdigest()), (pin["bytes"], pin["sha256"]))
            self.assertNotIn(b"/Users/", body)
            self.assertNotIn(b"CN" + b"PIX", body)
        self.assertFalse(any(name in sys.modules for name in ("numpy", "pyarrow", "pandas")))


if __name__ == "__main__":
    unittest.main(verbosity=2)

