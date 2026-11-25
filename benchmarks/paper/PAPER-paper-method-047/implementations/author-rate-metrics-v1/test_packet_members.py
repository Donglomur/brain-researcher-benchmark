"""Generated CLI controls for unambiguous prepared-rate NPZ membership."""
from contextlib import redirect_stderr
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

import numpy as np

HERE = Path(__file__).resolve().parent
METRICS_PATH = HERE / "metrics.py"
FAMILY_PATH = HERE.parent / "figure1e-family-v1" / "family.py"


def load(path, name):
    spec = importlib.util.spec_from_loader(name, loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


def fixture(paired=False):
    values = {"prediction": np.array([1., 2., 4.]),
              "target": np.array([1., 2., 3.]),
              "valid_mask": np.array([True, True, True])}
    if paired:
        values["author"] = np.array([1., 3., 2.])
    return values


def packet(path, values, extra=None):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(path, "w") as archive:
            for key, value in values.items():
                stream = io.BytesIO()
                np.save(stream, value, allow_pickle=False)
                archive.writestr(key + ".npy", stream.getvalue())
            if extra:
                name, value = extra
                stream = io.BytesIO()
                np.save(stream, value, allow_pickle=False)
                archive.writestr(name, stream.getvalue())


class PacketMembers(unittest.TestCase):
    def invoke(self, module, source, output):
        argv = ["metrics.py", "--input", str(source), "--output", str(output),
                "--sampling-rate-hz", "30", "--smoothing-seconds", "0.05"]
        with patch.object(sys, "argv", argv), redirect_stderr(io.StringIO()):
            module.main()

    def check_rejected(self, key, alias):
        module = load(METRICS_PATH, "gcamp8_packet_members_test")
        values = fixture(paired=True)
        alternate = np.array([True, True, False]) if key == "valid_mask" else np.array([3., 2., 1.])
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "input.npz", Path(directory) / "score.json"
            packet(source, values, (key if alias else key + ".npy", alternate))
            with self.assertRaises(SystemExit) as refusal:
                self.invoke(module, source, output)
            self.assertEqual(refusal.exception.code, 2)
            self.assertFalse(output.exists())

    def test_duplicate_required_and_optional_members_refused(self):
        for key in ("prediction", "target", "valid_mask", "author"):
            with self.subTest(key=key):
                self.check_rejected(key, False)

    def test_normalized_member_aliases_refused(self):
        for key in ("prediction", "target", "valid_mask", "author"):
            with self.subTest(key=key):
                self.check_rejected(key, True)

    def test_unique_plain_and_paired_packets_preserve_scores_and_dependency(self):
        module = load(METRICS_PATH, "gcamp8_packet_members_valid_test")
        for paired in (False, True):
            with self.subTest(paired=paired), tempfile.TemporaryDirectory() as directory:
                source, output = Path(directory) / "input.npz", Path(directory) / "score.json"
                values = fixture(paired)
                packet(source, values)
                kwargs = dict(valid_mask=values["valid_mask"], sampling_rate_hz=30, smoothing_seconds=0.05)
                expected = (module.compare_rates(values["prediction"], values["author"], values["target"], **kwargs)
                            if paired else module.score_rates(values["prediction"], values["target"], **kwargs))
                self.invoke(module, source, output)
                self.assertEqual(json.loads(output.read_text()), expected)
        family = load(FAMILY_PATH, "gcamp8_packet_members_family_test")
        self.assertEqual(family.METRIC_SHA256, hashlib.sha256(METRICS_PATH.read_bytes()).hexdigest())
        self.assertEqual(family._metrics().score_rates([1., 2., 3.], [1., 2., 3.],
                          valid_mask=[True, True, True], sampling_rate_hz=30, smoothing_seconds=0.05)["pearson"], 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
