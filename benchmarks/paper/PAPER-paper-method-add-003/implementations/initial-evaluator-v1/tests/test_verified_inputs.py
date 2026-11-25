"""Generated input-authentication regressions; no scientific observations."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from scipy.io import savemat
import scipy.io

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get("BENCHMARK_EVALUATOR_SOURCE", ROOT / "evaluator.py"))
spec = importlib.util.spec_from_file_location("dredge_verified_inputs", SOURCE)
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs(root, patient="Pt01"):
    raw = root / f"{patient}.imec0.lf.bin"
    meta = root / f"{patient}.imec0.lf.meta"
    channel_map = root / f"{patient}.mat"
    values = np.arange(28, dtype="<i2").reshape(4, 7)
    values[:, -1] = int(patient[-1])
    values.tofile(raw)
    meta.write_text("nSavedChans=7\nimSampRate=250\nsnsApLfSy=0,6,1\n")
    savemat(channel_map, {"chanMap": np.arange(1, 7), "xcoords": np.zeros(6),
                         "ycoords": np.arange(6), "connected": np.ones(6)})
    kwargs = {"patient": patient, "start_sample": 0, "stop_sample": 4,
              "expected_sha256": digest(raw), "expected_meta_sha256": digest(meta),
              "expected_map_sha256": digest(channel_map), "column_x": 0.0}
    return (raw, meta, channel_map), kwargs, values[:, :6].astype(float)


def protocol_inputs(root):
    protocol = {"task_id": e.TASK_ID, "source_commit": e.SOURCE_COMMIT,
                "metric_status": "prospective_unqualified", "rigid_settings": {},
                "fixed_offset_um": 0.0, "segments": []}
    for patient in e.PATIENTS:
        paths, kwargs, _ = inputs(root, patient)
        row = {"patient": patient, "segment_id": "generated", "role": "evaluation",
               "start_sample": 0, "stop_sample": 4,
               "binary": paths[0].name, "meta": paths[1].name,
               "channel_map": paths[2].name,
               "recording_sha256": kwargs["expected_sha256"],
               "meta_sha256": kwargs["expected_meta_sha256"],
               "map_sha256": kwargs["expected_map_sha256"], "column_x": 0.0,
               "fit_channels": [0, 2, 4], "evaluation_channels": [1, 3, 5], "estimates": {}}
        for method in e.REQUIRED_METHODS:
            p = root / f"{patient}-{method}.npz"
            np.savez(p, times_s=np.arange(4) / 250, depths_um=np.arange(6),
                     displacement_um=np.zeros(4))
            row["estimates"][method] = {"path": p.name, "sha256": digest(p),
                "recording_sha256": row["recording_sha256"], "start_sample": 0,
                "stop_sample": 4, "fit_channels": row["fit_channels"],
                "source_commit": e.SOURCE_COMMIT, "settings": {"generated": True}}
        protocol["segments"].append(row)
    return protocol


class VerifiedInputTests(unittest.TestCase):
    def test_unchanged_inputs_preserve_values_and_wrong_hash_refuses(self):
        with tempfile.TemporaryDirectory() as folder:
            paths, kwargs, expected = inputs(Path(folder))
            actual = e.load_raw_lfp(*paths, **kwargs)
            np.testing.assert_array_equal(actual["values"], expected)
            self.assertEqual(actual["recording_sha256"], kwargs["expected_sha256"])
            with self.assertRaises(ValueError):
                e.load_raw_lfp(*paths, **{**kwargs, "expected_sha256": "0" * 64})

    def test_raw_replacement_cannot_use_an_earlier_digest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths, kwargs, _ = inputs(root)
            replacement = root / "replacement.bin"
            np.full((4, 7), 123, dtype="<i2").tofile(replacement)
            original_loadmat = scipy.io.loadmat
            def replace_then_decode(*args, **kw):
                os.replace(replacement, paths[0])
                return original_loadmat(*args, **kw)
            with patch.object(scipy.io, "loadmat", side_effect=replace_then_decode):
                with self.assertRaisesRegex(ValueError, "changed"):
                    e.load_raw_lfp(*paths, **kwargs)

    def test_in_place_raw_mutation_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            paths, kwargs, _ = inputs(Path(folder))
            original_loadmat = scipy.io.loadmat
            def mutate_then_decode(*args, **kw):
                np.full((4, 7), 99, dtype="<i2").tofile(paths[0])
                return original_loadmat(*args, **kw)
            with patch.object(scipy.io, "loadmat", side_effect=mutate_then_decode):
                with self.assertRaisesRegex(ValueError, "changed"):
                    e.load_raw_lfp(*paths, **kwargs)

    def test_protocol_receipt_identifies_the_parsed_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            protocol = root / "protocol.json"
            protocol.write_text(json.dumps(protocol_inputs(root)))
            original_digest = digest(protocol)
            out = root / "out.json"
            original_loader = e.load_raw_lfp
            def load_then_replace(*args, **kwargs):
                packet = original_loader(*args, **kwargs)
                protocol.write_text("{}")
                return packet
            # These two numerical operations are explicitly outside this
            # metadata regression. The real CLI still authenticates all files.
            with patch.object(sys, "argv", ["evaluator", str(protocol), str(out)]), \
                 patch.object(e, "load_raw_lfp", side_effect=load_then_replace), \
                 patch.object(e, "evaluate_segment", return_value={"generated": True}), \
                 patch.object(e, "summarize_cohort", side_effect=lambda rows: {"count": len(rows)}):
                e.main()
            report = json.loads(out.read_bytes())
            self.assertEqual(report["protocol_sha256"], original_digest)
            self.assertNotEqual(report["protocol_sha256"], digest(protocol))
            self.assertEqual(len(report["segment_results"]), 3)

    def test_displacement_replacement_is_rejected_before_evaluation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            body = protocol_inputs(root)
            protocol = root / "protocol.json"
            protocol.write_text(json.dumps(body))
            target = root / body["segments"][0]["estimates"]["default_dredge"]["path"]
            replacement = root / "replacement.npz"
            np.savez(replacement, times_s=np.arange(4) / 250, depths_um=np.arange(6),
                     displacement_um=np.ones(4))
            original_load = np.load
            def replace_then_load(*args, **kwargs):
                if replacement.exists():
                    os.replace(replacement, target)
                return original_load(*args, **kwargs)
            with patch.object(sys, "argv", ["evaluator", str(protocol), str(root / "out.json")]), \
                 patch.object(e.np, "load", side_effect=replace_then_load), \
                 patch.object(e, "evaluate_segment", return_value={"generated": True}), \
                 patch.object(e, "summarize_cohort", side_effect=lambda rows: {"count": len(rows)}):
                with self.assertRaisesRegex(ValueError, "changed"):
                    e.main()


if __name__ == "__main__":
    unittest.main()
