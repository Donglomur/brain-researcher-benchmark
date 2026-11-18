#!/usr/bin/env python3
"""Metadata/source-byte controls only; no archived module is executed."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("n079_map_renderer", HERE / "render_source_maps.py")
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)
ARCHIVE = Path(os.environ.get("N079_TEST_ARCHIVE", str(HERE.parent / "full-natural-video-encoding-v1"))).resolve()


def tiny_output(destination, extra=False):
    output = {"source/a.py": b"pass\n"}
    if extra:
        output["source/b.py"] = b"pass\n"
    output["SOURCE_PACKAGE.json"] = r.compact({
        "schema": "neural079_source_staging_v1", "destination_root": str(destination),
        "execution_qualified": False, "scientifically_qualified": False,
        "readiness_promoted": False,
        "members": [{"path": rel, "pin": r.pin(body)} for rel, body in sorted(output.items())],
    })
    return output


class SourceMapControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = r.inspect_archive(str(ARCHIVE))
        cls.destination = str(ARCHIVE.parent.parent.parent / "uncreated-n079-staging-control")
        cls.output = r.render_maps(cls.snapshot, cls.destination)

    def test_complete_original_source_and_no_readiness_promotion(self):
        receipt = json.loads(self.output["SOURCE_PACKAGE.json"])
        self.assertEqual(len(self.snapshot["bodies"]), 101)
        self.assertEqual(len(self.output), 104)
        self.assertEqual(receipt["runtime_modules"], 55)
        self.assertEqual(receipt["closure_members"], 72)
        self.assertFalse(receipt["execution_qualified"])
        self.assertFalse(receipt["scientifically_qualified"])
        self.assertFalse(receipt["all_consumer_bindings_regenerated"])
        changed = set(self.snapshot["transformed"].values())
        unchanged = [rel for rel in self.snapshot["bodies"] if rel not in changed]
        self.assertEqual(len(unchanged), 98)
        for rel in unchanged:
            self.assertEqual(r.pin(self.output["source/" + rel]), self.snapshot["original_pins"][rel])
        self.assertEqual(self.output["provenance/INSTALLED_SOURCE_MANIFEST.json"], self.snapshot["authority"]["INSTALLED_SOURCE_MANIFEST.json"])

    def test_new_maps_pin_actual_rendered_effective_and_public_job(self):
        transformed = self.snapshot["transformed"]
        effective_rel = transformed[r.EFFECTIVE_TEMPLATE]
        closure_rel = transformed[r.CLOSURE_TEMPLATE]
        job_rel = transformed[r.JOB_TEMPLATE]
        effective = json.loads(self.output["source/" + effective_rel])
        closure = json.loads(self.output["source/" + closure_rel])
        root = Path(self.destination) / "source"
        for row in effective["modules"].values():
            rel = str(Path(row["path"]).relative_to(root))
            self.assertEqual(row["pin"], r.pin(self.output["source/" + rel]))
        for row in closure:
            rel = str(Path(row["path"]).relative_to(root))
            self.assertEqual(row["pin"], r.pin(self.output["source/" + rel]))
        effective_row = next(row for row in closure if row["path"] == str(root / effective_rel))
        job_row = next(row for row in closure if row["path"] == str(root / job_rel))
        self.assertNotEqual(effective_row["pin"], self.snapshot["original_pins"][effective_rel])
        self.assertNotEqual(job_row["pin"], self.snapshot["original_pins"][job_rel])
        self.assertEqual(job_row["pin"]["bytes"], 588)
        self.assertIn(b"${N079_SITE_HOME:?set_site_home}", self.output["source/" + job_rel])

    def test_deterministic_and_destination_sensitive(self):
        self.assertEqual(self.output, r.render_maps(self.snapshot, self.destination))
        other = r.render_maps(self.snapshot, self.destination + "-other")
        effective = self.snapshot["transformed"][r.EFFECTIVE_TEMPLATE]
        self.assertNotEqual(self.output["source/" + effective], other["source/" + effective])
        for rel, body in self.snapshot["bodies"].items():
            if rel not in self.snapshot["transformed"].values():
                self.assertEqual(body, other["source/" + rel])

    def test_bad_marker_traversal_and_unpublished_member_rejected(self):
        effective_rel = self.snapshot["transformed"][r.EFFECTIVE_TEMPLATE]
        for bad in ("/absolute.py", "@SOURCE_ROOT@/../escape.py", "@SOURCE_ROOT@/unpublished.py"):
            snapshot = copy.deepcopy(self.snapshot)
            effective = json.loads(snapshot["bodies"][effective_rel])
            next(iter(effective["modules"].values()))["path"] = bad
            snapshot["bodies"][effective_rel] = r.compact(effective)
            with self.subTest(bad=bad), self.assertRaises(r.ConstructionError):
                r.render_maps(snapshot, self.destination)

    def test_module_pin_or_body_tamper_rejected(self):
        effective_rel = self.snapshot["transformed"][r.EFFECTIVE_TEMPLATE]
        for tamper_body in (False, True):
            snapshot = copy.deepcopy(self.snapshot)
            effective = json.loads(snapshot["bodies"][effective_rel])
            row = next(iter(effective["modules"].values()))
            if tamper_body:
                snapshot["bodies"][row["path"][len(r.MARKER):]] += b"# changed\n"
            else:
                row["pin"]["sha256"] = "0" * 64
                snapshot["bodies"][effective_rel] = r.compact(effective)
            with self.subTest(body=tamper_body), self.assertRaises(r.ConstructionError):
                r.render_maps(snapshot, self.destination)

    def test_duplicate_or_missing_closure_dependency_rejected(self):
        closure_rel = self.snapshot["transformed"][r.CLOSURE_TEMPLATE]
        effective_rel = self.snapshot["transformed"][r.EFFECTIVE_TEMPLATE]
        for mode in ("duplicate", "missing"):
            snapshot = copy.deepcopy(self.snapshot)
            closure = json.loads(snapshot["bodies"][closure_rel])
            if mode == "duplicate":
                closure[1] = copy.deepcopy(closure[0])
            else:
                closure = [row for row in closure if row["path"] != r.MARKER + effective_rel]
            snapshot["bodies"][closure_rel] = r.compact(closure)
            with self.subTest(mode=mode), self.assertRaises(r.ConstructionError):
                r.render_maps(snapshot, self.destination)

    def test_pinned_read_rejects_tamper_symlink_and_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "source.py").write_bytes(b"pass\n")
            expected = r.pin(b"pass\n")
            self.assertEqual(r._read_pinned(root, "source.py", expected, [0]), b"pass\n")
            with self.assertRaises(r.ConstructionError):
                r._read_pinned(root, "source.py", r.pin(b"fail\n"), [0])
            with self.assertRaises(r.ConstructionError):
                r._read_pinned(root, "source.py", expected, [r.MAX_READ])
            (root / "link.py").symlink_to(root / "source.py")
            with self.assertRaises(OSError):
                r._read_pinned(root, "link.py", expected, [0])
            (root / "directory-link").symlink_to(root, target_is_directory=True)
            with self.assertRaises(r.ConstructionError):
                r._read_pinned(root, "directory-link/source.py", expected, [0])

    def test_duplicate_json_nonfinite_and_path_collisions_rejected(self):
        for body in (b'{"x":1,"x":2}', b'{"x":NaN}'):
            with self.assertRaises(r.ConstructionError):
                r.strict_json(body)
        for paths in (["a.py", "A.py"], ["a", "a/b.py"], ["../escape"], ["a//b"]):
            with self.subTest(paths=paths), self.assertRaises(r.ConstructionError):
                r._unique_paths(paths)

    def test_original_archive_cannot_be_destination(self):
        for target in (str(ARCHIVE), str(ARCHIVE / "new"), "relative-root"):
            with self.subTest(target=target), self.assertRaises(r.ConstructionError):
                r.render_maps(self.snapshot, target)

class PublicationControls(unittest.TestCase):
    """Tiny generated files only; no archive setup/read is needed."""

    def test_fresh_publication_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = str(Path(tmp).resolve() / "stage")
            output = tiny_output(destination)
            result = r.publish(output, destination)
            self.assertTrue(result["completion_marker_published"])
            self.assertIsNone(result["temporary_cleanup_warning"])
            self.assertEqual((Path(destination) / "source/a.py").read_bytes(), b"pass\n")
            with self.assertRaises(r.ConstructionError):
                r.publish(output, destination)
            self.assertEqual((Path(destination) / "SOURCE_PACKAGE.json").read_bytes(), output["SOURCE_PACKAGE.json"])

    def test_partial_publication_has_no_completion_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp).resolve() / "stage"
            output = tiny_output(destination, extra=True)
            original_open = os.open
            def fail_second(path, *args, **kwargs):
                if str(path).endswith("/b.py"):
                    raise OSError("injected disk failure")
                return original_open(path, *args, **kwargs)
            with patch.object(r.os, "open", side_effect=fail_second), self.assertRaises(OSError):
                r.publish(output, str(destination))
            self.assertTrue((destination / "source/a.py").exists())
            self.assertFalse((destination / "SOURCE_PACKAGE.json").exists())

    def test_publication_rejects_destination_receipt_or_body_mismatch_before_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp).resolve() / "stage"
            for mode in ("destination", "body", "qualification"):
                output = tiny_output(destination)
                receipt = json.loads(output["SOURCE_PACKAGE.json"])
                if mode == "destination":
                    receipt["destination_root"] += "-wrong"
                elif mode == "body":
                    output["source/a.py"] += b"changed\n"
                else:
                    receipt["execution_qualified"] = True
                output["SOURCE_PACKAGE.json"] = r.compact(receipt)
                with self.subTest(mode=mode), self.assertRaises(r.ConstructionError):
                    r.publish(output, str(destination))
                self.assertFalse(destination.exists())

    def test_partial_receipt_write_never_exposes_final_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp).resolve() / "stage"
            output = tiny_output(destination)
            def fail_write(stream, body):
                stream.write(body[:len(body) // 2])
                stream.flush()
                raise OSError("injected receipt write failure")
            with patch.object(r, "_sync_receipt", side_effect=fail_write), self.assertRaises(OSError):
                r.publish(output, str(destination))
            self.assertTrue((destination / "source/a.py").exists())
            self.assertFalse((destination / "SOURCE_PACKAGE.json").exists())
            self.assertEqual(list(destination.glob(".SOURCE_PACKAGE.*.pending")), [])

    def test_receipt_fsync_failure_never_exposes_final_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp).resolve() / "stage"
            original_fsync = os.fsync
            calls = [0]
            def fail_receipt(fd):
                calls[0] += 1
                if calls[0] == 2:  # first source body, then the receipt temp
                    raise OSError("injected receipt fsync failure")
                return original_fsync(fd)
            with patch.object(r.os, "fsync", side_effect=fail_receipt), self.assertRaises(OSError):
                r.publish(tiny_output(destination), str(destination))
            self.assertEqual(calls[0], 2)
            self.assertFalse((destination / "SOURCE_PACKAGE.json").exists())
            self.assertEqual(list(destination.glob(".SOURCE_PACKAGE.*.pending")), [])

    def test_postcommit_cleanup_failure_preserves_complete_marker_and_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp).resolve() / "stage"
            output = tiny_output(destination)
            with patch.object(r.os, "unlink", side_effect=OSError("injected cleanup failure")):
                result = r.publish(output, str(destination))
            self.assertTrue(result["completion_marker_published"])
            self.assertIsNotNone(result["temporary_cleanup_warning"])
            self.assertEqual((destination / "SOURCE_PACKAGE.json").read_bytes(), output["SOURCE_PACKAGE.json"])
            pending = list(destination.glob(".SOURCE_PACKAGE.*.pending"))
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0].read_bytes(), output["SOURCE_PACKAGE.json"])

    def test_atomic_marker_does_not_replace_existing_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp).resolve()
            marker = destination / "SOURCE_PACKAGE.json"
            marker.write_bytes(b"existing receipt")
            with self.assertRaises(FileExistsError):
                r._publish_marker(destination, b"new receipt")
            self.assertEqual(marker.read_bytes(), b"existing receipt")
            self.assertEqual(list(destination.glob(".SOURCE_PACKAGE.*.pending")), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
