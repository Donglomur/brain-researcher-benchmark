"""Generated CLI custody controls; downstream scientific evaluation is stubbed."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("beta_input_identity", ROOT / "beta_evaluator.py")
beta = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(beta)


def archive(marker):
    stream = io.BytesIO()
    np.savez(stream, index=np.array([marker]), pinky=np.array([marker]))
    return stream.getvalue()


class InputIdentityTests(unittest.TestCase):
    def run_case(self, root, hook=None, mutate_manifest=False):
        original = archive(1)
        source = root / "case.npz"
        source.write_bytes(original)
        manifest = root / "manifest.json"
        manifest_data = json.dumps({"marker": 1, "participants": [
            {"participant_id": "sub-001", "envelopes_npz": source.name,
             "envelopes_sha256": hashlib.sha256(original).hexdigest()}
        ]}).encode()
        manifest.write_bytes(manifest_data)
        output = root / "result.json"
        real_load = np.load

        def evaluate(data, arrays):
            if mutate_manifest:
                manifest.write_text('{"marker": 2}')
            return {"array_marker": int(arrays["sub-001"]["index"][0]), "manifest_marker": data["marker"]}

        with patch.object(beta, "evaluate", side_effect=evaluate), patch.object(
            sys, "argv", ["beta_evaluator.py", str(manifest), str(output)]
        ):
            if hook is None:
                beta.main()
            else:
                with patch.object(beta.np, "load", side_effect=lambda *a, **k: hook(source, real_load, *a, **k)):
                    beta.main()
        return json.loads(output.read_text()), original, manifest_data

    def test_stable_arrays_and_input_pins(self):
        with tempfile.TemporaryDirectory() as name:
            result, original, manifest = self.run_case(Path(name))
        self.assertEqual(result["array_marker"], 1)
        self.assertEqual(result["input_pins"], [{"participant_id": "sub-001", "sha256": hashlib.sha256(original).hexdigest(), "bytes": len(original)}])
        self.assertEqual(result["manifest_sha256"], hashlib.sha256(manifest).hexdigest())

    def test_manifest_pin_identifies_the_parsed_manifest(self):
        with tempfile.TemporaryDirectory() as name:
            result, _, manifest = self.run_case(Path(name), mutate_manifest=True)
        self.assertEqual(result["manifest_marker"], 1)
        self.assertEqual(result["manifest_sha256"], hashlib.sha256(manifest).hexdigest())

    def test_npz_path_replacement_cannot_change_authenticated_arrays(self):
        def swap(path, load, *args, **kwargs):
            replacement = path.with_name("replacement.npz")
            replacement.write_bytes(archive(2))
            os.replace(replacement, path)
            return load(*args, **kwargs)

        with tempfile.TemporaryDirectory() as name:
            try:
                result, _, _ = self.run_case(Path(name), swap)
            except beta.ContractError:
                self.assertFalse((Path(name) / "result.json").exists())
            else:
                self.assertEqual(result["array_marker"], 1)

    def test_in_place_npz_edit_fails_before_evaluation(self):
        def edit(path, load, *args, **kwargs):
            old = path.stat()
            path.write_bytes(archive(2))
            os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns + 1000000000))
            return load(*args, **kwargs)

        with tempfile.TemporaryDirectory() as name:
            with self.assertRaises(beta.ContractError):
                self.run_case(Path(name), edit)
            self.assertFalse((Path(name) / "result.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
