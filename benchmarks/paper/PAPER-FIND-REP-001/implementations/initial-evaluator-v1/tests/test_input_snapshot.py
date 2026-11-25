"""Generated complete-roster controls for pinned NPZ snapshots."""
from contextlib import contextmanager
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

import numpy as np

SOURCE = Path(__file__).resolve().parents[1] / "evaluator.py"
SPEC = importlib.util.spec_from_file_location("rep001_snapshot_evaluator", SOURCE)
e = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(e)


def fixture(root):
    near = np.tile(np.arange(3.)[:, None], (1, 46))
    source = root / "generated.npz"
    np.savez(source, near_binF=near, far_binF=near, cell_ids=np.arange(3))
    payload = source.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    animals = [{"animal_id": name, "native_session_count": 2, "sessions": [
        {"session_index": day, "cue_sets": ["Cue Set A"], "behavior_record": "generated",
         "selection": "putative/excl_no_response", "arrays": source.name, "sha256": digest}
        for day in range(2)]} for name in e.ANIMALS]
    manifest = {"schema_version": 1, "task_id": e.TASK_ID, "source_revision": e.SOURCE_REVISION,
                "input_kind": "prepared_putative_placefields_binF", "evidence_kind": "generated_engineering_control",
                "lineage": {"article_id": 27273552, "article_version": 1, **{k: "generated" for k in
                    ("placefields_record", "registered_fluorescence_record", "behavior_record", "export_procedure", "rights_review")}},
                "animals": animals}
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path, source, payload, manifest, near


class SnapshotTests(unittest.TestCase):
    def test_complete_roster_preserves_the_unmodified_reference_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path, source, payload, _, _ = fixture(Path(directory))
            result = e.evaluate_manifest(path)
            self.assertEqual(result["group"]["n_animals"], 11)
            self.assertEqual(len(result["input_pins"]), 22)
            self.assertTrue(np.array_equal(result["group"]["mean"], np.ones((6, 1000))))
            self.assertTrue(all(pin["bytes"] == len(payload) for pin in result["input_pins"]))
            self.assertFalse(result["scientifically_qualified"])

    def test_hash_decode_replacement_cannot_change_scored_arrays(self):
        with tempfile.TemporaryDirectory() as directory:
            path, source, payload, _, near = fixture(Path(directory))
            digest = hashlib.sha256(payload).hexdigest()
            buffer = io.BytesIO()
            np.savez(buffer, near_binF=near, far_binF=-near, cell_ids=np.arange(3))
            replacement = buffer.getvalue()
            native_sha, native_load = hashlib.sha256, np.load
            replaced = []

            class Hash:
                def __init__(self, *args, **kwargs):
                    self.inner = native_sha(*args, **kwargs)
                def update(self, data):
                    self.inner.update(data)
                def hexdigest(self):
                    value = self.inner.hexdigest()
                    if value == digest:
                        source.write_bytes(replacement)
                        replaced.append(True)
                    return value

            @contextmanager
            def restore_after_decoding(operand, **kwargs):
                try:
                    with native_load(operand, **kwargs) as arrays:
                        yield arrays
                finally:
                    source.write_bytes(payload)

            with patch.object(e.hashlib, "sha256", Hash), patch.object(e.np, "load", restore_after_decoding):
                result = e.evaluate_manifest(path)
            self.assertEqual(len(replaced), 22)
            self.assertTrue(np.array_equal(result["group"]["mean"], np.ones((6, 1000))))
            self.assertTrue(all(pin["sha256"] == digest and pin["bytes"] == len(payload)
                                for pin in result["input_pins"]))

    def test_duplicate_npz_members_are_rejected_before_scoring(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, source, _, manifest, near = fixture(root)
            data = io.BytesIO()
            np.save(data, -near, allow_pickle=False)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(source, "a") as archive:
                    archive.writestr("far_binF.npy", data.getvalue())
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            for animal in manifest["animals"]:
                for session in animal["sessions"]:
                    session["sha256"] = digest
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(e.ContractError, "duplicate members"):
                e.evaluate_manifest(path)


if __name__ == "__main__":
    unittest.main()
