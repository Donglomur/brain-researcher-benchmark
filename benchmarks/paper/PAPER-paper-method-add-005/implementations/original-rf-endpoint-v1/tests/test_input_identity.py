"""Generated CLI input-custody controls; scoring is stubbed, no RF/model run."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ajile_input_identity", ROOT / "endpoint.py")
endpoint = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(endpoint)


def archive(marker):
    stream = io.BytesIO()
    np.savez(stream, marker=np.array([marker], dtype=np.int64))
    return stream.getvalue()


class InputIdentityTests(unittest.TestCase):
    def case(self, root, hook=None):
        source, out = root / "case.npz", root / "score.json"
        original = archive(1)
        source.write_bytes(original)
        calls = []

        def score(data, **kwargs):
            calls.append(int(data["marker"][0]))
            return {"marker": calls[-1], "input_sha256": kwargs["input_digest"]}

        argv = ["score-case", str(source), str(out), "--participant", "EC01",
                "--dropout", "0.5", "--repeat", "0", "--kind", "generated_control"]
        real_load = np.load
        with patch.object(endpoint, "evaluate_case", side_effect=score):
            if hook is None:
                endpoint.main(argv)
            else:
                with patch.object(endpoint.np, "load", side_effect=lambda *a, **k: hook(source, real_load, *a, **k)):
                    with contextlib.redirect_stderr(io.StringIO()):
                        endpoint.main(argv)
        return json.loads(out.read_text()), hashlib.sha256(original).hexdigest(), calls

    def test_stable_npz_arrays_and_input_pin(self):
        with tempfile.TemporaryDirectory() as name:
            result, digest, calls = self.case(Path(name))
        self.assertEqual(calls, [1])
        self.assertEqual(result, {"marker": 1, "input_sha256": digest})

    def test_npz_path_replacement_cannot_rebind_loaded_arrays(self):
        def swap(path, load, *args, **kwargs):
            opened = load(*args, **kwargs)
            other = path.with_name("replacement.npz")
            other.write_bytes(archive(2))
            os.replace(other, path)
            return opened

        with tempfile.TemporaryDirectory() as name:
            try:
                result, original_digest, _ = self.case(Path(name), swap)
            except SystemExit as error:
                self.assertEqual(error.code, 2)
                self.assertFalse((Path(name) / "score.json").exists())
            else:
                self.assertEqual(result, {"marker": 1, "input_sha256": original_digest})

    def test_npz_in_place_edit_cannot_rebind_loaded_arrays(self):
        def edit_after_decode(path, load, *args, **kwargs):
            opened = load(*args, **kwargs)

            class Changed:
                def keys(self):
                    return opened.keys()

                def __getitem__(self, key):
                    value = opened[key]
                    old = path.stat()
                    path.write_bytes(archive(2))
                    os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns + 1000000000))
                    return value

                def __enter__(self):
                    return self

                def __exit__(self, *exc):
                    opened.close()

            return Changed()

        with tempfile.TemporaryDirectory() as name:
            try:
                result, original_digest, _ = self.case(Path(name), edit_after_decode)
            except SystemExit as error:
                self.assertEqual(error.code, 2)
                self.assertFalse((Path(name) / "score.json").exists())
            else:
                self.assertEqual(result, {"marker": 1, "input_sha256": original_digest})

    def test_receipt_parse_uses_authenticated_snapshot(self):
        real_sha = hashlib.sha256
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            original = b'{"marker": 1}'
            changed = b'{"marker": 2}'
            digest = real_sha(original).hexdigest()
            paths = [root / (str(i) + ".json") for i in range(180)]
            for path in paths:
                path.write_bytes(original)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps([{"path": p.name, "sha256": digest} for p in paths]))
            swapped = []

            class Hash:
                def __init__(self, *args, **kwargs):
                    self.inner = real_sha(*args, **kwargs)

                def update(self, data):
                    self.inner.update(data)

                def hexdigest(self):
                    value = self.inner.hexdigest()
                    if value == digest and not swapped:
                        paths[0].write_bytes(changed)
                        swapped.append(True)
                    return value

            with patch.object(endpoint.hashlib, "sha256", Hash), patch.object(
                endpoint, "aggregate_panel", side_effect=lambda rows: {"markers": [r["marker"] for r in rows]}
            ):
                endpoint.main(["aggregate", str(manifest), str(root / "result.json")])
            result = json.loads((root / "result.json").read_text())
            self.assertTrue(swapped)
            self.assertEqual(result["markers"], [1] * 180)

    def test_wrong_receipt_hash_rejects_before_aggregate(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "receipt.json").write_text('{"marker": 1}')
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps([{"path": "receipt.json", "sha256": "0" * 64}] * 180))
            with patch.object(endpoint, "aggregate_panel") as aggregate, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    endpoint.main(["aggregate", str(manifest), str(root / "result.json")])
            self.assertEqual(error.exception.code, 2)
            aggregate.assert_not_called()
            self.assertFalse((root / "result.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
