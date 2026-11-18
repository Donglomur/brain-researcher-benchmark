"""Generated full-geometry controls; no original simulations or model fits."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
import warnings
import zipfile

import numpy as np


HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("reference_panel", HERE / "reference_panel.py")
panel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panel)
# The public default is its sibling component. Private review can point at the
# existing read-only source; its exact source pin is still enforced by the API.
SCORER = Path(os.environ.get("RASTERMAP_REVIEW_SCORER", str(panel.SCORER_PATH)))


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def npy(array, version=None):
    out = io.BytesIO()
    np.lib.format.write_array(out, array, version=version, allow_pickle=True)
    return out.getvalue()


def archive(entries):
    out = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for name, body in entries:
                z.writestr(name, body)
    return out.getvalue()


class ReferencePanelTests(unittest.TestCase):
    fixture_written_bytes = 0

    @classmethod
    def tearDownClass(cls):
        print("generated_fixture_written_bytes=" + str(cls.fixture_written_bytes))

    @classmethod
    def setUpClass(cls):
        cls.scores = np.zeros((10, 2, 8, 5), dtype="float64")
        # Full original axes, deliberately different realized random control.
        for r in range(10):
            cls.scores[r] = r / 20
        cls.scores[:, :, 7] = 0.2
        cls.embeddings = np.zeros((10, 7, 6000, 1), dtype="float64")
        cls.scores_bytes = npy(cls.scores)
        cls.emb_bytes = npy(cls.embeddings)
        cls.valid = archive([("scores_all.npy", cls.scores_bytes),
                             ("embs_all.npy", cls.emb_bytes)])

    def load(self, entries):
        payload = archive(entries)
        return panel.load_panel(payload, digest(payload))

    def report(self, payload=None):
        payload = self.valid if payload is None else payload
        return panel.report_panel(payload, digest(payload), scorer_path=SCORER)

    def test_complete_panel_and_original_sem(self):
        report = self.report()
        self.assertEqual(report["axes"]["realizations"], list(range(10)))
        self.assertEqual(len(report["axes"]["plotted_methods"]), 7)
        self.assertEqual(len(report["axes"]["scored_methods"]), 8)
        self.assertAlmostEqual(report["panel"]["mean_percent"][0][0][0], 22.5)
        # r/20 for r=0..9: population variance = 8.25/400; source SEM /sqrt(9).
        self.assertAlmostEqual(report["panel"]["sem_percent"][0][0][0],
                               100 * (8.25 / 400) ** 0.5 / 3)
        self.assertEqual(len(report["panel"]["per_realization_percent"]), 10)

    def test_sampled_random_and_analytic_guides_remain_distinct(self):
        report = self.report()
        self.assertAlmostEqual(report["panel"]["mean_percent"][1][7][0], 20)
        self.assertAlmostEqual(report["analytical_guides_percent"]["correct_triplets"][0], 100 / 3)
        self.assertAlmostEqual(report["analytical_guides_percent"]["contamination"][4], 200 / 3)

    def test_shape_compatible_bytes_never_promote_publication(self):
        q = self.report()["qualification"]
        self.assertTrue(q["operator_supplied_byte_identity_and_layout_only"])
        self.assertIsNone(q["paper_win"])
        for key in ("published_artifact_authenticated", "source_execution_verified",
                    "original_post_fit_rng_recovered", "reproduction_established", "improvement_established"):
            self.assertFalse(q[key])

    def test_missing_realization_random_method_or_neurons_rejected(self):
        for scores, emb in [(self.scores[:9], self.embeddings),
                            (self.scores[:, :, :7], self.embeddings),
                            (self.scores, self.embeddings[:, :, :5999])]:
            with self.subTest(shapes=(scores.shape, emb.shape)), self.assertRaises(panel.InvalidPanel):
                self.load([("scores_all.npy", npy(scores)), ("embs_all.npy", npy(emb))])

    def test_missing_duplicate_extra_and_path_members_rejected(self):
        valid = [("scores_all.npy", self.scores_bytes), ("embs_all.npy", self.emb_bytes)]
        cases = [valid[:1], valid + [valid[0]], valid + [("extra.txt", b"x")],
                 [("scores_all.npy", self.scores_bytes), ("../embs_all.npy", self.emb_bytes)]]
        for entries in cases:
            with self.subTest(names=[x[0] for x in entries]), self.assertRaises(panel.InvalidPanel):
                self.load(entries)

    def test_nonfinite_and_out_of_range_scores_rejected(self):
        for value in (np.nan, np.inf, -0.001, 1.001):
            scores = self.scores.copy()
            scores[0, 0, 0, 0] = value
            with self.subTest(value=value), self.assertRaises(panel.InvalidPanel):
                self.load([("scores_all.npy", npy(scores)), ("embs_all.npy", self.emb_bytes)])

    def test_missing_coordinate_rejected_but_ties_preserved(self):
        arrays, _ = panel.load_panel(self.valid, digest(self.valid))
        self.assertTrue((arrays["embs_all.npy"] == 0).all())
        emb = self.embeddings.copy()
        emb[9, 6, 5999, 0] = np.nan
        with self.assertRaises(panel.InvalidPanel):
            self.load([("scores_all.npy", self.scores_bytes), ("embs_all.npy", npy(emb))])

    def test_dtype_layout_and_object_payload_rejected(self):
        for scores in (self.scores.astype("float32"), self.scores.astype("complex128"),
                       np.asfortranarray(self.scores), self.scores.astype(object)):
            with self.subTest(dtype=str(scores.dtype), c=scores.flags.c_contiguous), self.assertRaises(panel.InvalidPanel):
                self.load([("scores_all.npy", npy(scores)), ("embs_all.npy", self.emb_bytes)])

    def test_geometry_bomb_and_trailing_member_payload_rejected(self):
        header = b"{'descr': '<f8', 'fortran_order': False, 'shape': (999999999999,)}\n"
        bomb = b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header
        for body in (bomb, self.scores_bytes + b"trailing"):
            with self.subTest(body_size=len(body)), self.assertRaises(panel.InvalidPanel):
                self.load([("scores_all.npy", body), ("embs_all.npy", self.emb_bytes)])

    def test_duplicate_header_keys_rejected(self):
        header = b"{'descr': '<f8', 'descr': '<f8', 'fortran_order': False, 'shape': (10,2,8,5)}\n"
        body = b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header + self.scores.tobytes()
        with self.assertRaises(panel.InvalidPanel):
            self.load([("scores_all.npy", body), ("embs_all.npy", self.emb_bytes)])

    def test_npy_version_two_is_admitted(self):
        arrays, _ = self.load([("scores_all.npy", npy(self.scores, (2, 0))),
                               ("embs_all.npy", npy(self.embeddings, (2, 0)))])
        np.testing.assert_array_equal(arrays["scores_all.npy"], self.scores)

    def test_wrong_pin_oversize_and_nonzip_rejected(self):
        for body, pin in [(self.valid, "0" * 64), (self.valid, "A" * 64),
                           (b"not zip", digest(b"not zip")),
                           (b"x" * (panel.MAX_ARCHIVE_BYTES + 1), "0" * 64)]:
            with self.subTest(length=len(body), pin=pin[:8]), self.assertRaises(panel.InvalidPanel):
                panel.load_panel(body, pin)

    def test_coordinate_commitment_retains_all_seventy_vectors(self):
        original = self.report()["coordinate_sha256"]
        emb = self.embeddings.copy()
        emb[9, 6, 5999, 0] = 2
        payload = archive([("scores_all.npy", self.scores_bytes), ("embs_all.npy", npy(emb))])
        changed = self.report(payload)["coordinate_sha256"]
        self.assertEqual(len(original), 10)
        self.assertTrue(all(len(row) == 7 for row in original))
        differences = [(r, m) for r in range(10) for m in range(7) if original[r][m] != changed[r][m]]
        self.assertEqual(differences, [(9, 6)])

    def test_changed_aggregator_source_refused(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            path = Path(tmp) / "untrusted.py"
            path.write_text("raise RuntimeError('must not execute')\n")
            type(self).fixture_written_bytes += path.stat().st_size
            with self.assertRaises(panel.InvalidPanel):
                panel.report_panel(self.valid, digest(self.valid), scorer_path=path)

    def test_cli_writes_once_and_uses_operator_pin(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            artifact, output = Path(tmp) / "sim_performance.npz", Path(tmp) / "report.json"
            artifact.write_bytes(self.valid)
            type(self).fixture_written_bytes += artifact.stat().st_size
            with mock.patch.object(panel, "SCORER_PATH", SCORER):
                panel.main([str(artifact), "--expected-sha256", digest(self.valid), "--output", str(output)])
                report = json.loads(output.read_text())
                type(self).fixture_written_bytes += output.stat().st_size
                self.assertFalse(report["qualification"]["published_artifact_authenticated"])
                with self.assertRaises(FileExistsError):
                    panel.main([str(artifact), "--expected-sha256", digest(self.valid), "--output", str(output)])


if __name__ == "__main__":
    unittest.main(verbosity=1)
