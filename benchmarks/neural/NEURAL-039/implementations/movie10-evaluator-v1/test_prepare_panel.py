"""Generated HDF5 metadata controls; no authentic neural values or fitting."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import h5py
import prepare_panel as pp


class PanelPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name).resolve()
        cls.source = cls.root / "source"
        cls.source.mkdir()
        cls.records = {}
        cls.generated_write_bytes = 0
        keys = ("ses-01_task-bourne1", "ses-02_task-figures1_run-1",
                "ses-03_task-figures1_run-2", "ses-04_task-life1_run-1",
                "ses-05_task-life1_run-2", "ses-06_task-wolf1")
        for subject in pp.ev.SUBJECTS:
            path = cls.source / f"{subject}_movie10.h5"
            with h5py.File(path, "w") as handle:
                for key in keys:
                    # Unallocated chunks: metadata is real HDF5, response arrays
                    # are not materialized or written by these controls.
                    handle.create_dataset(key, shape=(20, 1000), chunks=(1, 1000), dtype="<f4")
            body = path.read_bytes()
            cls.generated_write_bytes += len(body)
            cls.records[subject] = {"file": path.name, "bytes": len(body),
                                    "md5": hashlib.md5(body).hexdigest()}

    @classmethod
    def tearDownClass(cls):
        print(f"generated_fixture_written_bytes={cls.generated_write_bytes}")
        cls.temp.cleanup()

    def test_source_expectations_match_four_pinned_git_blobs(self):
        records = pp.source_records()
        self.assertEqual(tuple(records), pp.ev.SUBJECTS)
        self.assertEqual(sum(r["bytes"] for r in records.values()), 368950005)
        self.assertEqual({r["pointer_bytes"] for r in records.values()}, {137})
        self.assertEqual(records["sub-05"]["pointer_git_sha1"],
                         "634e57160c2482ba706e1233fab185f3caf8d99f")
        changed = dict(pp.POINTERS)
        directory, size, md5, blob = changed["sub-01"]
        changed["sub-01"] = directory, size + 1, md5, blob
        with patch.object(pp, "POINTERS", changed), self.assertRaisesRegex(ValueError, "pointer identity"):
            pp.source_records()

    def test_complete_panel_is_current_evaluator_compatible_without_array_reads(self):
        with patch.object(h5py.Dataset, "__getitem__", side_effect=AssertionError("array read")):
            panel = pp._prepare(self.source, self.records, h5py)
        self.assertIs(pp.ev.validate_panel(panel), panel)
        self.assertEqual(len(pp.ev.queries(panel)), 16)
        self.assertTrue(all(len(x["datasets"]) == 6 for x in panel["subjects"].values()))
        for subject, value in panel["subjects"].items():
            self.assertEqual(value["sha256"], hashlib.sha256((self.source / value["file"]).read_bytes()).hexdigest())

    def test_last_source_hash_failure_precedes_hdf5_parsing(self):
        records = copy.deepcopy(self.records)
        records["sub-05"]["md5"] = "0" * 32
        with patch.object(h5py, "File", side_effect=AssertionError("HDF5 parse")):
            with self.assertRaisesRegex(ValueError, "identity differs for sub-05"):
                pp._prepare(self.source, records, h5py)

    def test_wrong_size_or_cross_person_filename_is_rejected(self):
        records = copy.deepcopy(self.records)
        records["sub-01"]["bytes"] += 1
        with self.assertRaisesRegex(ValueError, "identity differs"):
            pp._prepare(self.source, records, h5py)
        records["sub-01"]["file"] = "sub-02_movie10.h5"
        with self.assertRaisesRegex(ValueError, "subject-specific"):
            pp._prepare(self.source, records, h5py)

    def test_cli_prepare_cannot_select_generated_source_expectations(self):
        # Public preparation always chooses the four original source extents and
        # MD5s. The internal test seam is not a CLI/source-manifest override.
        with self.assertRaises(ValueError):
            pp.prepare(self.source, h5py)

    def test_incomplete_source_directory_is_rejected(self):
        empty = self.root / "empty"
        empty.mkdir(exist_ok=True)
        with self.assertRaisesRegex(ValueError, "Exact complete submission directory"):
            pp._prepare(empty, self.records, h5py)

    def test_soft_link_is_rejected_before_it_is_followed(self):
        class FakeFile:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def keys(self): return ["ses-01_task-bourne1"]
            def get(self, key, getlink=False): return h5py.SoftLink("/untrusted")
            def __getitem__(self, key): raise AssertionError("link followed")
        with patch.object(h5py, "File", return_value=FakeFile()):
            with self.assertRaisesRegex(ValueError, "local hard-linked"):
                pp._prepare(self.source, self.records, h5py)

    def test_native_dtype_and_repeat_coverage_remain_strict(self):
        path = self.source / "sub-01_movie10.h5"
        original = path.read_bytes()
        for defect in ("float64", "missing_repeat"):
            with self.subTest(defect=defect):
                try:
                    with h5py.File(path, "r+") as handle:
                        key = ("ses-01_task-bourne1" if defect == "float64"
                               else "ses-03_task-figures1_run-2")
                        del handle[key]
                        if defect == "float64":
                            handle.create_dataset(key, shape=(20, 1000), chunks=(1, 1000), dtype="<f8")
                    body = path.read_bytes()
                    type(self).generated_write_bytes += len(body)  # full rewrite upper
                    records = copy.deepcopy(self.records)
                    records["sub-01"].update(bytes=len(body), md5=hashlib.md5(body).hexdigest())
                    message = "float32" if defect == "float64" else "Both original viewings"
                    with self.assertRaisesRegex(ValueError, message):
                        pp._prepare(self.source, records, h5py)
                finally:
                    path.write_bytes(original)
                    type(self).generated_write_bytes += len(original)

    def test_file_mutation_before_return_is_detected(self):
        original = pp.ev.validate_panel
        def inspect(panel):
            # Change metadata only; source identity checks must still observe it.
            path = self.source / "sub-01_movie10.h5"
            before = path.stat()
            import os
            os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000))
            return original(panel)
        with patch.object(pp.ev, "validate_panel", side_effect=inspect):
            with self.assertRaisesRegex(ValueError, "Input changed during use"):
                pp._prepare(self.source, self.records, h5py)


if __name__ == "__main__":
    unittest.main()
