"""Generated integration controls with actual NumPy/registered NPZ validator."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_portable import d, fixture, envelopes, ledger


class Native(unittest.TestCase):
    def setUp(self):
        # Production dependencies remain pinned; only tiny generated packet pins
        # are substituted in memory. CLI has no pin override or fixture mode.
        self.modules = d.dependencies()
        self.members = fixture()
        self.modules["exporter"].PINS = {
            name: (len(body), d.descriptor(body)["sha256"]) for name, body in self.members.items()}
        self.contexts = list(d.context_rows(self.members, d.CONDITIONS[0]))

    def prepare(self, tmp):
        tmp = Path(tmp).resolve()  # macOS /var aliases /private/var; validator rejects aliases.
        delivery = Path(tmp) / "delivery"
        (delivery / "public").mkdir(parents=True)
        for name, body in self.members.items():
            (delivery / "public" / name).write_bytes(body)
        responses = Path(tmp) / "responses.jsonl"
        responses.write_bytes(ledger(envelopes(self.contexts)))
        return delivery, responses

    def test_real_numpy_roundtrip_and_existing_destination_refused(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(d, "dependencies", return_value=self.modules):
            delivery, responses = self.prepare(tmp)
            output = Path(tmp).resolve() / "accepted"
            receipt = d.collect(delivery, d.CONDITIONS[0], responses, output)
            self.assertEqual(receipt["responses"], 400)
            self.assertEqual(receipt["private_target_reads"], 0)
            with np.load(output / "submission.npz", allow_pickle=False) as arrays:
                self.assertEqual(set(arrays.files), {"trial_ids", "target_probability"})
                self.assertEqual(arrays["target_probability"].tolist(), [0.25] * 400)
            with self.assertRaises(FileExistsError):
                d.collect(delivery, d.CONDITIONS[0], responses, output)

    def test_all_raw_failures_preserved_and_no_submission(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(d, "dependencies", return_value=self.modules):
            delivery, responses = self.prepare(tmp)
            rows = envelopes(self.contexts)
            rows[-1].update(status="error", response=None, error="generated transport failure")
            raw = ledger(rows)
            responses.write_bytes(raw)
            output = Path(tmp).resolve() / "failed"
            with self.assertRaises(ValueError):
                d.collect(delivery, d.CONDITIONS[0], responses, output)
            self.assertEqual((output / "attempts.jsonl").read_bytes(), raw)
            self.assertTrue((output / "FAILED.json").is_file())
            self.assertFalse((output / "COMPLETE.json").exists())
            self.assertFalse((output / "submission.npz").exists())

    def test_manifest_tamper_refused_before_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(d, "dependencies", return_value=self.modules):
            delivery, responses = self.prepare(tmp)
            path = delivery / "public/manifest.json"
            path.write_bytes(path.read_bytes().replace(b"development-001", b"development-999"))
            output = Path(tmp).resolve() / "refused"
            with self.assertRaises(ValueError):
                d.collect(delivery, d.CONDITIONS[0], responses, output)
            self.assertFalse(output.exists())

    def test_dependency_tamper_refused_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "waveform-contexts/export_contexts.py"
            source.parent.mkdir()
            body = (d.IMPLEMENTATIONS / "waveform-contexts/export_contexts.py").read_bytes()
            source.write_bytes(body[:-1] + b" ")
            with mock.patch.object(d, "IMPLEMENTATIONS", root), self.assertRaisesRegex(ValueError, "pin mismatch"):
                d.dependencies()


if __name__ == "__main__":
    unittest.main()
