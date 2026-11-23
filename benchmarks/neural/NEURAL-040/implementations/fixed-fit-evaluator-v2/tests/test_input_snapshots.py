"""Generated small file controls; no authentic neural data or fitted models."""
import builtins
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

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("neural040_snapshot_controls", ROOT / "evaluator.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)
GENERATED_BYTES_WRITTEN = 0


def write_bytes(path, payload):
    global GENERATED_BYTES_WRITTEN
    GENERATED_BYTES_WRITTEN += len(payload)
    path.write_bytes(payload)


def json_bytes(value):
    return json.dumps(value, sort_keys=True).encode()


def archive_bytes(value):
    buffer = io.BytesIO()
    np.savez(buffer, sample=np.asarray(value))
    return buffer.getvalue()


@contextmanager
def replace_after_read(path, replacements):
    """Deterministically replace a named file after each selected read closes."""
    original_open = builtins.open
    path = Path(path)
    index = 0

    class ReadProxy:
        def __init__(self, stream, replacement):
            self.stream, self.replacement, self.closed_once = stream, replacement, False

        def __getattr__(self, key):
            return getattr(self.stream, key)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            self.close()

        def close(self):
            if not self.closed_once:
                self.closed_once = True
                self.stream.close()
                if self.replacement is not None:
                    write_bytes(path, self.replacement)

    def intercept(file, mode="r", *args, **kwargs):
        nonlocal index
        stream = original_open(file, mode, *args, **kwargs)
        if not isinstance(file, int) and Path(file) == path and "r" in mode:
            replacement = replacements[index] if index < len(replacements) else None
            index += 1
            return ReadProxy(stream, replacement)
        return stream

    with patch("builtins.open", side_effect=intercept):
        yield


class SnapshotControls(unittest.TestCase):
    def test_target_metadata_digest_identifies_parsed_bytes(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            archive, metadata = directory / "targets.npz", directory / "metadata.json"
            payload = archive_bytes([1.0, 2.0])
            old = json_bytes({"npz_sha256": hashlib.sha256(payload).hexdigest(), "marker": "captured"})
            write_bytes(archive, payload)
            write_bytes(metadata, old)
            hashes = {}
            with replace_after_read(metadata, [json_bytes({"marker": "replacement"})]):
                _, parsed = ev._read_targets(archive, metadata, hashes, "training")
            self.assertEqual(parsed["marker"], "captured")
            self.assertEqual(hashes["training_target_metadata"], hashlib.sha256(old).hexdigest())
            self.assertNotEqual(hashes["training_target_metadata"], hashlib.sha256(metadata.read_bytes()).hexdigest())

    def test_archive_replacement_cannot_relabel_loaded_arrays(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            archive, metadata = directory / "targets.npz", directory / "metadata.json"
            original, alternate = archive_bytes([1.0, 2.0]), archive_bytes([91.0, 92.0])
            write_bytes(archive, original)
            write_bytes(metadata, json_bytes({"npz_sha256": hashlib.sha256(original).hexdigest()}))
            hashes = {}
            # Old hash/load/hash accepts B arrays under A's hash when A is restored.
            # A single captured byte string loads A regardless of later replacements.
            with replace_after_read(archive, [alternate, original]):
                targets, _ = ev._read_targets(archive, metadata, hashes, "training")
            self.assertEqual(hashes["training_targets"], hashlib.sha256(original).hexdigest())
            np.testing.assert_array_equal(targets["sample"], [1.0, 2.0])

    def test_cli_records_each_captured_json_and_prediction_metadata(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            paths = {key: directory / (key + suffix) for key, suffix in (
                ("protocol", ".json"), ("features", ".npz"), ("claims", ".json"),
                ("training-targets", ".npz"), ("training-target-metadata", ".json"),
                ("predictions", ".npz"), ("prediction-metadata", ".json"),
                ("private-targets", ".npz"), ("private-target-metadata", ".json"),
                ("output", ".json"))}
            payload = archive_bytes([[1.0, 2.0], [3.0, 4.0]])
            archive_digest = hashlib.sha256(payload).hexdigest()
            claims = [{"family": family, "mean_delta_r": 0.0} for family in ev.base.FAMILIES]
            values = {"protocol": {"marker": "captured"}, "claims": claims,
                      "training-target-metadata": {"npz_sha256": archive_digest, "marker": "train"},
                      "private-target-metadata": {"npz_sha256": archive_digest, "marker": "private"},
                      "prediction-metadata": {"artifact_sha256": {"predictions": archive_digest}}}
            captured = {key: json_bytes(value) for key, value in values.items()}
            expected_keys = {"protocol": "protocol_file", "claims": "claims",
                             "training-target-metadata": "training_target_metadata",
                             "private-target-metadata": "private_target_metadata",
                             "prediction-metadata": "prediction_metadata"}

            def fixed_fit(protocol, features, training, training_metadata,
                          predictions, prediction_metadata, supplied_claims, evaluation_loader):
                self.assertEqual(protocol, values["protocol"])
                self.assertEqual(training_metadata, values["training-target-metadata"])
                self.assertEqual(prediction_metadata, values["prediction-metadata"])
                self.assertEqual(supplied_claims, claims)
                targets, target_metadata = evaluation_loader()
                self.assertEqual(target_metadata, values["private-target-metadata"])
                np.testing.assert_array_equal(targets["sample"], [[1., 2.], [3., 4.]])
                return {"scope": "generated I/O control, no fit or science"}

            for changed in values:
                with self.subTest(changed=changed):
                    for key, data in captured.items():
                        write_bytes(paths[key], data)
                    for key in ("features", "training-targets", "predictions", "private-targets"):
                        write_bytes(paths[key], payload)
                    argv = [argument for key, path in paths.items() for argument in ("--" + key, str(path))]
                    with patch.object(ev.base, "validate_protocol"), patch.object(ev, "score_fixed_fit", side_effect=fixed_fit), \
                            replace_after_read(paths[changed], [b'{}']):
                        ev.main(argv)
                    result = json.loads(paths["output"].read_bytes())
                    global GENERATED_BYTES_WRITTEN
                    GENERATED_BYTES_WRITTEN += paths["output"].stat().st_size
                    for key, digest_key in expected_keys.items():
                        self.assertEqual(result["artifact_sha256"][digest_key], hashlib.sha256(captured[key]).hexdigest())
                    paths["output"].unlink()

    def test_json_snapshot_rejects_duplicate_keys_and_nonfinite_constants(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "input.json"
            for payload in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}'):
                write_bytes(path, payload)
                with self.subTest(payload=payload), self.assertRaises(ev.ContractError):
                    ev._read_json_snapshot(path)

    def test_npz_snapshot_rejects_duplicate_members_and_pickles(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "input.npz"
            member = io.BytesIO()
            np.save(member, np.array([1.0]), allow_pickle=False)
            archive = io.BytesIO()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(archive, "w") as output:
                    output.writestr("sample.npy", member.getvalue())
                    output.writestr("sample.npy", member.getvalue())
            write_bytes(path, archive.getvalue())
            with self.assertRaisesRegex(ev.ContractError, "duplicate NPZ keys"):
                ev._read_npz_snapshot(path)
            write_bytes(path, archive_bytes(np.array([{"unsafe": "object"}], dtype=object)))
            with self.assertRaises(ValueError):
                ev._read_npz_snapshot(path)

    def test_incomplete_claims_fail_before_any_other_file_is_read(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "claims.json"
            write_bytes(path, b'[]')
            options = ("protocol", "features", "training-targets", "training-target-metadata",
                       "predictions", "prediction-metadata", "private-targets", "private-target-metadata", "output")
            argv = [argument for key in options for argument in ("--" + key, str(Path(name) / key))]
            with self.assertRaisesRegex(ev.ContractError, "three complete"):
                ev.main(argv + ["--claims", str(path)])

    def test_target_archive_hash_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            archive, metadata = directory / "targets.npz", directory / "metadata.json"
            write_bytes(archive, archive_bytes([1.0]))
            write_bytes(metadata, json_bytes({"npz_sha256": "0" * 64}))
            with self.assertRaisesRegex(ev.ContractError, "target hash mismatch"):
                ev._read_targets(archive, metadata, {}, "private")


if __name__ == "__main__":
    unittest.main()
