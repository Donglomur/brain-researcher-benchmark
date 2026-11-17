"""Generated fixtures only: no retained scientific MAT or reference reads."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
from unittest import mock
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from scipy.io import savemat
from scipy import sparse
from suns2_benchmark import candidate_io as cio, candidate_mat5 as cm
from suns2_benchmark.constants import VIDEO_IDS

DIGEST = "a" * 64


def masks(dtype=np.uint8):
    result = np.zeros((50, 50, 3), dtype=dtype)
    result[3:5, 8:10, 0] = 1
    result[20:23, 30:33, 1] = 1
    result[:, :, 2] = result[:, :, 0]  # Explicit positive duplicate, order preserved.
    return result


def mat_bytes(array=None, *, name="Masks", compressed=True, extra=None):
    output = io.BytesIO()
    values = {name: masks() if array is None else array}
    if extra:
        values.update(extra)
    savemat(output, values, do_compression=compressed)
    return output.getvalue()


def raw_mat(array=None, *, cls=9, storage=2, flags=0, dims=None, endian="<", compressed=False,
            name=b"Masks", subsystem=False):
    array = masks() if array is None else array
    def element(kind, payload):
        return struct.pack(endian + "II", kind, len(payload)) + payload + b"\0" * (-len(payload) % 8)
    dimensions = array.shape if dims is None else dims
    payload = element(6, struct.pack(endian + "II", cls | flags, 0))
    payload += element(5, struct.pack(endian + "i" * len(dimensions), *dimensions))
    payload += element(1, name)
    payload += element(storage, array.tobytes(order="F"))
    matrix = element(14, payload)
    if compressed:
        zipped = zlib.compress(matrix)
        matrix = struct.pack(endian + "II", 15, len(zipped)) + zipped
    header = b"MATLAB 5.0 MAT-file, generated test only".ljust(116, b" ")
    header += (b"\1" if subsystem else b"\0") + b"\0" * 7
    header += struct.pack(endian + "H", 0x100) + (b"IM" if endian == "<" else b"MI")
    return header + matrix


class MatBoundaryTests(unittest.TestCase):
    def test_asymmetric_source_column_row_neuron_order_preserved(self):
        original = np.zeros((50, 50, 1), dtype=bool)
        original[13, 7, 0] = True
        actual, metadata = cm.load_candidate_mat(mat_bytes(original))
        self.assertTrue(actual[13, 7, 0])
        self.assertFalse(actual[7, 13, 0])
        np.testing.assert_array_equal(actual, original)
        self.assertEqual(metadata["mask_axis_order"], ["column", "row", "neuron"])
        self.assertFalse(metadata["spatial_transpose_applied"])

    def test_binary_numeric_and_logical_preserve_orientation_order_duplicates(self):
        for dtype in (np.bool_, np.uint8, np.int16, np.float32, np.float64):
            with self.subTest(dtype=str(dtype)):
                original = masks(dtype)
                actual, metadata = cm.load_candidate_mat(mat_bytes(original))
                np.testing.assert_array_equal(actual, original)
                self.assertEqual(actual.dtype, np.dtype(bool))
                self.assertFalse(actual.flags.writeable)
                self.assertTrue(metadata["instance_order_preserved"])
                self.assertTrue(metadata["duplicate_positive_instances_preserved"])

    def test_empty_output_set_accepted_but_empty_individual_roi_rejected(self):
        value, metadata = cm.load_candidate_mat(mat_bytes(np.zeros((50, 50, 0), dtype=bool)))
        self.assertEqual(value.shape, (50, 50, 0))
        self.assertTrue(metadata["empty_output_set"])
        with self.assertRaisesRegex(cm.CandidateMATError, "zero-area"):
            cm.load_candidate_mat(mat_bytes(np.zeros((50, 50, 1), dtype=bool)))

    def test_weighted_and_nonfinite_values_rejected(self):
        for value in (0.5, -1, 2, np.nan, np.inf):
            array = masks(float)
            array[0, 0, 0] = value
            with self.subTest(value=str(value)), self.assertRaises(cm.CandidateMATError):
                cm.load_candidate_mat(mat_bytes(array))

    def test_logical_raw_two_rejected_before_lossy_scipy_cast(self):
        array = masks()
        array[0, 0, 0] = 2
        with mock.patch("scipy.io.loadmat", side_effect=AssertionError("preflight must refuse first")):
            with self.assertRaisesRegex(cm.CandidateMATError, "raw storage"):
                cm.load_candidate_mat(raw_mat(array, flags=0x200, compressed=True))

    def test_dimensions_and_instance_resource_cap(self):
        for shape in ((49, 50, 1), (50, 50), (50, 50, 513), (50, 50, 1, 1)):
            with self.subTest(shape=shape), self.assertRaises(cm.CandidateMATError):
                cm.preflight_candidate_mat(raw_mat(np.zeros(shape, dtype=np.uint8)))

    def test_unsafe_mat_classes_complex_and_hdf5(self):
        examples = [mat_bytes(masks(complex)), mat_bytes(np.array([[{"x": 1}]], dtype=object)),
                    mat_bytes(np.array([[1]], dtype=object)), mat_bytes(sparse.eye(3)),
                    b"\x89HDF\r\n\x1a\n" + b"\0" * 128]
        for data in examples:
            with self.subTest(prefix=data[:16]), self.assertRaises(cm.CandidateMATError):
                cm.preflight_candidate_mat(data)

    def test_wrong_name_extra_variable_and_trailing_bytes(self):
        for data in (mat_bytes(name="FinalMasks"), mat_bytes(extra={"injected": np.ones((1, 1))}),
                     mat_bytes() + b"injected"):
            with self.assertRaises(cm.CandidateMATError):
                cm.preflight_candidate_mat(data)

    def test_subsystem_and_reserved_flags_refused(self):
        for data in (raw_mat(subsystem=True), raw_mat(flags=0x100)):
            with self.assertRaises(cm.CandidateMATError):
                cm.preflight_candidate_mat(data)

    def test_both_endian_orders_and_small_tags(self):
        for endian in ("<", ">"):
            actual, _ = cm.load_candidate_mat(raw_mat(endian=endian))
            np.testing.assert_array_equal(actual, masks())
            tag = struct.pack(endian + "HH", 1, 3) + b"abc\0"
            self.assertEqual(cm._element(tag, 0, endian), (1, b"abc", 8))

    def test_source_and_expansion_caps_and_trailing_zlib_stream(self):
        data = raw_mat(compressed=True)
        with mock.patch.object(cm, "MAX_MAT_BYTES", len(data) - 1), self.assertRaises(cm.CandidateMATError):
            cm.preflight_candidate_mat(data)
        with mock.patch.object(cm, "MAX_EXPANDED_BYTES", 512), self.assertRaisesRegex(cm.CandidateMATError, "expanded-byte"):
            cm.preflight_candidate_mat(data)
        with self.assertRaisesRegex(cm.CandidateMATError, "trailing"):
            cm._inflate(zlib.compress(b"abc") + zlib.compress(b"extra"), 128)
        with self.assertRaises(cm.CandidateMATError):
            cm._inflate(zlib.compress(b"abc")[:-1], 128)

    def test_shape_storage_mismatch_and_truncated_tags(self):
        for data in (raw_mat(storage=9), raw_mat()[:-1], raw_mat()[:132]):
            with self.assertRaises(cm.CandidateMATError):
                cm.preflight_candidate_mat(data)


class CandidateFilesystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="generated-only-", dir=os.environ.get("TMPDIR") or None)
        self.addCleanup(self.temp.cleanup)
        self.arena = Path(self.temp.name).resolve()
        self.root = self.arena / "parent" / "submission"
        (self.root / "masks").mkdir(parents=True)
        self.manifest = {"schema": cio.MANIFEST_SCHEMA, "condition": "paper_data",
                         "procedure_digest": DIGEST, "cases": []}
        for index, video in enumerate(VIDEO_IDS):
            data = mat_bytes(masks(bool if index % 2 else float))
            (self.root / "masks" / f"{video}.mat").write_bytes(data)
            self.manifest["cases"].append({"video_id": video, "path": f"masks/{video}.mat",
                "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
        self.save_manifest()

    def save_manifest(self):
        (self.root / "submission.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def load(self):
        return cio.load_candidate_submission(self.root, "paper_data", DIGEST)

    def test_complete_panel_and_declared_procedure_binding(self):
        self.manifest["cases"].reverse()
        self.save_manifest()
        actual, metadata = self.load()
        self.assertEqual(tuple(actual), VIDEO_IDS)
        for value in actual.values():
            np.testing.assert_array_equal(value, masks(bool))
        self.assertTrue(metadata["exact_support_and_file_census_verified"])
        self.assertFalse(metadata["procedure_production_provenance_verified"])
        self.assertEqual(metadata["procedure_digest"], DIGEST)
        self.assertEqual(metadata["manifest_sha256"], hashlib.sha256((self.root / "submission.json").read_bytes()).hexdigest())

    def test_missing_extra_duplicate_ids_and_paths_refused_before_decode(self):
        original = json.loads(json.dumps(self.manifest))
        mutations = [lambda m: m["cases"].pop(),
                     lambda m: m["cases"].append(dict(m["cases"][0])),
                     lambda m: m["cases"][0].update(video_id="unknown"),
                     lambda m: m["cases"][1].update(video_id=m["cases"][0]["video_id"]),
                     lambda m: m["cases"][0].update(path="../outside.mat"),
                     lambda m: m["cases"][0].update(path="/outside.mat"),
                     lambda m: m["cases"][0].update(path="masks/./" + VIDEO_IDS[0] + ".mat"),
                     lambda m: m.update(injected=True),
                     lambda m: m["cases"][0].update(injected=True)]
        with mock.patch.object(cm, "load_candidate_mat", side_effect=AssertionError("no MAT decoding allowed")):
            for mutation in mutations:
                self.manifest = json.loads(json.dumps(original))
                mutation(self.manifest)
                self.save_manifest()
                with self.assertRaises(cio.CandidateSubmissionError):
                    self.load()

    def test_wrong_condition_digest_bool_size_and_digest_syntax(self):
        original = json.loads(json.dumps(self.manifest))
        for field, value, per_case in (("condition", "paper_data_official_code", False),
            ("procedure_digest", "b" * 64, False), ("bytes", True, True),
            ("sha256", "A" * 64, True), ("bytes", 17 * 1024 * 1024, True)):
            self.manifest = json.loads(json.dumps(original))
            (self.manifest["cases"][0] if per_case else self.manifest)[field] = value
            self.save_manifest()
            with self.assertRaises(cio.CandidateSubmissionError):
                self.load()
        with self.assertRaises(cio.CandidateSubmissionError):
            cio.load_candidate_submission(self.root, "unknown", DIGEST)
        with self.assertRaises(cio.CandidateSubmissionError):
            cio.load_candidate_submission(self.root, "paper_data", "not-a-hash")

    def test_malformed_duplicate_nonfinite_json_and_manifest_cap(self):
        for raw in (b"{", b"\xff", b'{"schema":1,"schema":2}', b'{"value":NaN}',
                    b" " * (cio.MAX_MANIFEST_BYTES + 1)):
            (self.root / "submission.json").write_bytes(raw)
            with self.assertRaises(cio.CandidateSubmissionError):
                self.load()

    def test_hash_and_size_tampering(self):
        path = self.root / self.manifest["cases"][0]["path"]
        original = path.read_bytes()
        path.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
        with self.assertRaisesRegex(cio.CandidateSubmissionError, "SHA256"):
            self.load()
        path.write_bytes(original + b"x")
        with self.assertRaisesRegex(cio.CandidateSubmissionError, "size"):
            self.load()

    def test_missing_extra_census_and_special_file(self):
        extra = self.root / "unexpected"
        extra.write_text("x")
        with self.assertRaises(cio.CandidateSubmissionError):
            self.load()
        extra.unlink()
        path = self.root / self.manifest["cases"][0]["path"]
        path.unlink()
        with self.assertRaises(cio.CandidateSubmissionError):
            self.load()
        os.mkfifo(path)
        with self.assertRaisesRegex(cio.CandidateSubmissionError, "regular"):
            self.load()

    def test_file_and_masks_directory_symlinks(self):
        path = self.root / self.manifest["cases"][0]["path"]
        outside = self.arena / "outside.mat"
        path.rename(outside)
        path.symlink_to(outside)
        with self.assertRaises(cio.CandidateSubmissionError):
            self.load()
        path.unlink()
        outside.rename(path)
        outside_dir = self.arena / "outside-masks"
        (self.root / "masks").rename(outside_dir)
        (self.root / "masks").symlink_to(outside_dir, target_is_directory=True)
        with self.assertRaises(cio.CandidateSubmissionError):
            self.load()

    def test_root_and_ancestor_aliases(self):
        link = self.arena / "root-link"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(cio.CandidateSubmissionError, "alias"):
            cio.load_candidate_submission(link, "paper_data", DIGEST)
        ancestor = self.arena / "ancestor-link"
        ancestor.symlink_to(self.root.parent, target_is_directory=True)
        with self.assertRaisesRegex(cio.CandidateSubmissionError, "alias"):
            cio.load_candidate_submission(ancestor / "submission", "paper_data", DIGEST)

    def test_hardlink_external_alias_refused(self):
        path = self.root / self.manifest["cases"][0]["path"]
        os.link(path, self.arena / "alias.mat")
        with self.assertRaisesRegex(cio.CandidateSubmissionError, "hardlinked"):
            self.load()

    def test_ancestor_swap_between_resolution_and_open(self):
        original_open = cio._open_canonical_directory
        parent = self.root.parent
        held = self.arena / "held-parent"
        external = self.arena / "external-parent"
        shutil.copytree(parent, external)
        def swapped(path):
            parent.rename(held)
            parent.symlink_to(external, target_is_directory=True)
            return original_open(path)
        try:
            with mock.patch.object(cio, "_open_canonical_directory", side_effect=swapped):
                with self.assertRaises(cio.CandidateSubmissionError):
                    self.load()
        finally:
            if parent.is_symlink():
                parent.unlink()
                held.rename(parent)

    def test_postread_file_mutation_refused(self):
        original_read = cio._read_regular
        first = f"{VIDEO_IDS[0]}.mat"
        def mutate(fd, name, *args, **kwargs):
            result = original_read(fd, name, *args, **kwargs)
            if name == first:
                path = self.root / "masks" / first
                raw = path.read_bytes()
                path.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
            return result
        with mock.patch.object(cio, "_read_regular", side_effect=mutate):
            with self.assertRaisesRegex(cio.CandidateSubmissionError, "changed after read"):
                self.load()

    def test_ancestor_becomes_alias_after_pinned_open(self):
        original_read = cio._read_regular
        parent = self.root.parent
        held = self.arena / "held-parent"
        def swap_after_manifest(fd, name, *args, **kwargs):
            result = original_read(fd, name, *args, **kwargs)
            if name == "submission.json":
                parent.rename(held)
                parent.symlink_to(held, target_is_directory=True)
            return result
        try:
            with mock.patch.object(cio, "_read_regular", side_effect=swap_after_manifest):
                with self.assertRaises(cio.CandidateSubmissionError):
                    self.load()
        finally:
            if parent.is_symlink():
                parent.unlink()
                held.rename(parent)

    def test_census_stops_at_first_unknown_entry(self):
        class Entries:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def __iter__(self):
                yield type("Entry", (), {"name": "unexpected"})()
                raise AssertionError("must not consume beyond first unknown entry")
        with mock.patch.object(cio.os, "scandir", return_value=Entries()):
            with self.assertRaisesRegex(cio.CandidateSubmissionError, "extra"):
                cio._check_census(0, {"masks", "submission.json"})

    def test_trusted_reference_api_is_separate_and_exact_variable_pinned(self):
        path = self.arena / "trusted-reference.mat"
        data = mat_bytes(name="FinalMasks")
        path.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        actual, metadata = cio.load_trusted_mask(path, "FinalMasks", digest, len(data))
        np.testing.assert_array_equal(actual, masks(bool))
        self.assertTrue(metadata["source_bytes_authenticated"])
        for variable, wanted_digest, size in (("Masks", digest, len(data)), ("wrong", digest, len(data)),
                                             ("FinalMasks", "b" * 64, len(data)),
                                             ("FinalMasks", digest, len(data) + 1)):
            with self.assertRaises(cio.CandidateSubmissionError):
                cio.load_trusted_mask(path, variable, wanted_digest, size)


if __name__ == "__main__":
    unittest.main(verbosity=2)
