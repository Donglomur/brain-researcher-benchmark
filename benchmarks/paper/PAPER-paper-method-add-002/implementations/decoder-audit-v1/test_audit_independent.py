"""Independent generated boundary controls; no original data or fitting.

Tiny incomplete payloads intentionally exercise metadata rejection before any
scientific decoding. Passing admission alone is never treated as full verification.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("slice_independent_audit_packet", HERE / "audit_packet.py")
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


class CoreMetadata:
    def __init__(self, count=12):
        self.plan = {"recipe": "source_code_ridge1", "bank_manifest_sha256": "b" * 64}
        self.manifest = {"angle_counts": {"straight": count, "curved": count}}
        self.manifest_sha256 = "c" * 64


class IndependentBoundaries(unittest.TestCase):
    cumulative_fixture_write_bytes = 0

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=HERE)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def write(self, path, body):
        type(self).cumulative_fixture_write_bytes += len(body)
        self.assertLessEqual(type(self).cumulative_fixture_write_bytes, 2 * 1024**2)
        path.write_bytes(body)

    def fixture(self, count=12):
        core = CoreMetadata(count)
        root = self.root / "packet"
        root.mkdir()
        rows = {}
        for index, (key, shape) in enumerate(sorted(q._shape_keys(core.manifest["angle_counts"]).items())):
            name = f"{index:04d}.npy.gz"
            body = b"x"
            self.write(root / name, body)
            rows[key] = {"file": name, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
                         "shape": list(shape), "dtype": "<f8"}
        manifest = {"schema": q.SCHEMA, "core_manifest_sha256": core.manifest_sha256,
                    "plan_sha256": q.b.digest(core.plan), "bridge_sha256": q.BRIDGE_SHA256,
                    "audited_producer_sha256": q.AUDITED_PRODUCER_SHA256,
                    "representation_pins": {model: {"shape": [150, 511, 182], "dtype": "<f8",
                        "bytes": 150 * 511 * 182 * 8, "sha256": "d" * 64} for model in q.b.MODELS},
                    "fit_records": {"single": {}, "averaged": {}}, "files": rows,
                    "fit_execution_authenticated": False, "scientific_admission": False}
        return root, core, manifest

    def manifest(self, root, value):
        body = q.b.canonical(value)
        self.write(root / "MANIFEST.json", body)
        return hashlib.sha256(body).hexdigest(), len(body)

    def test_literal_public_feature_count_and_full_source_support_stay_fixed(self):
        self.assertEqual(q.FEATURES, 182)
        with self.assertRaises(ValueError):
            q.a.repeated_decoding(np.zeros((150, 511, 3)), np.zeros((150, 511, 2)),
                                  recipe="source_code_ridge1")
        with self.assertRaises(ValueError):
            q.a._repeated_windowed(np.zeros((80, 510, 2)), np.zeros((80, 510, 2)),
                                  np.zeros((150, 511, 2)), recipe="source_code_ridge1")

    def test_declared_gigabyte_mean_expansion_refused_before_payload_decode(self):
        root, core, manifest = self.fixture(count=246)
        digest, _ = self.manifest(root, manifest)
        # The payloads are only one byte each, yet unbounded shape admission
        # would permit >1 GiB for one mean and several GiB collectively.
        with mock.patch.object(q.AuditPacket, "get", side_effect=AssertionError("payload must not decode")):
            with self.assertRaises(ValueError):
                q.AuditPacket(root, digest, core)

    def test_whole_packet_cap_counts_manifest_as_well_as_payloads(self):
        root, core, manifest = self.fixture()
        digest, manifest_bytes = self.manifest(root, manifest)
        payload_bytes = sum(row["bytes"] for row in manifest["files"].values())
        q.AuditPacket(root, digest, core)  # Metadata only, not valid numeric evidence.
        with mock.patch.object(q, "MAX_PACKET_BYTES", manifest_bytes + payload_bytes - 1):
            with self.assertRaises(ValueError):
                q.AuditPacket(root, digest, core)

    def test_post_parse_manifest_shrink_cannot_reduce_captured_extent_charge(self):
        root, core, manifest = self.fixture()
        digest, manifest_bytes = self.manifest(root, manifest)
        payload_bytes = sum(row["bytes"] for row in manifest["files"].values())
        original_reader = q._manifest

        def capture_then_shrink(*args, **kwargs):
            captured = original_reader(*args, **kwargs)
            self.write(root / "MANIFEST.json", b"x")
            return captured

        with mock.patch.object(q, "_manifest", side_effect=capture_then_shrink) as reader:
            with mock.patch.object(q, "MAX_PACKET_BYTES", manifest_bytes + payload_bytes - 1):
                with self.assertRaises(ValueError):
                    q.AuditPacket(root, digest, core)
            self.assertEqual(reader.call_count, 1)

    def test_manifest_reader_rejects_duplicate_nonfinite_and_hardlink_inputs(self):
        path = self.root / "manifest.json"
        for body in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}'):
            self.write(path, body)
            with self.assertRaises(ValueError):
                q._manifest(path, hashlib.sha256(body).hexdigest())
        body = b'{}'
        self.write(path, body)
        os.link(path, self.root / "alias.json")
        with self.assertRaises(ValueError):
            q._manifest(path, hashlib.sha256(body).hexdigest())

    def test_heldout_movement_is_not_an_exported_candidate_audit_requirement(self):
        self.assertNotIn("movement_test_mean", q.HALF_FIELDS)
        root, core, manifest = self.fixture()
        self.assertFalse(any("movement_test_mean" in key for key in manifest["files"]))
        extra = copy.deepcopy(next(iter(manifest["files"].values())))
        manifest["files"]["averaged/straight/movement_test_mean"] = extra
        digest, _ = self.manifest(root, manifest)
        with self.assertRaises(ValueError):
            q.AuditPacket(root, digest, core)

    def test_exact_core_binding_cannot_be_relabelled_as_another_submission(self):
        root, core, manifest = self.fixture()
        digest, _ = self.manifest(root, manifest)
        core.manifest_sha256 = "e" * 64
        with self.assertRaises(ValueError):
            q.AuditPacket(root, digest, core)

    def test_fitting_or_scientific_authentication_flags_cannot_be_promoted(self):
        root, core, manifest = self.fixture()
        for field in ("fit_execution_authenticated", "scientific_admission"):
            changed = copy.deepcopy(manifest)
            changed[field] = True
            digest, _ = self.manifest(root, changed)
            with self.assertRaises(ValueError):
                q.AuditPacket(root, digest, core)

    def test_payload_replacement_and_symlink_after_admission_are_rejected(self):
        root, core, manifest = self.fixture()
        key = "single/raw/straight/weight"
        row = manifest["files"][key]
        value = np.zeros(tuple(row["shape"]), dtype=np.float64)
        stream = io.BytesIO()
        np.save(stream, value, allow_pickle=False)
        payload = gzip.compress(stream.getvalue(), compresslevel=1, mtime=0)
        self.write(root / row["file"], payload)
        row.update(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
        digest, _ = self.manifest(root, manifest)
        packet = q.AuditPacket(root, digest, core)
        np.testing.assert_array_equal(packet.get(key), value)
        corrupt = payload[:-1] + bytes([payload[-1] ^ 1])
        self.write(root / row["file"], corrupt)
        with self.assertRaises(ValueError):
            packet.get(key)
        target = self.root / "outside.gz"
        self.write(target, payload)
        (root / row["file"]).unlink()
        (root / row["file"]).symlink_to(target)
        with self.assertRaises((OSError, ValueError)):
            packet.get(key)

    def test_duplicate_array_filename_and_wrong_plan_rejected(self):
        root, core, manifest = self.fixture()
        rows = list(manifest["files"].values())
        rows[1]["file"] = rows[0]["file"]
        digest, _ = self.manifest(root, manifest)
        with self.assertRaises(ValueError):
            q.AuditPacket(root, digest, core)
        rows[1]["file"] = "0001.npy.gz"
        manifest["plan_sha256"] = "f" * 64
        digest, _ = self.manifest(root, manifest)
        with self.assertRaises(ValueError):
            q.AuditPacket(root, digest, core)

    @classmethod
    def tearDownClass(cls):
        print("INDEPENDENT_FIXTURE_CUMULATIVE_WRITES=" + str(cls.cumulative_fixture_write_bytes))


if __name__ == "__main__":
    unittest.main(verbosity=2)
