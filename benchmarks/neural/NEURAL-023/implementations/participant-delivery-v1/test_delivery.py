"""Generated file controls only; no authentic arrays or method execution."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("neural023_export", HERE / "export_public.py")
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="neural023-public-control-")).resolve()
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        self.output = self.root / "output"
        self.bodies = {name: ("generated opaque fixture: " + name).encode()
                       for name in delivery.ASSET_PINS}
        self.pins = {name: delivery.pin(body) for name, body in self.bodies.items()}
        for name, body in self.bodies.items():
            (self.inputs / name).write_bytes(body)
        self.patcher = patch.object(delivery, "ASSET_PINS", self.pins)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        for directory, _, _ in os.walk(self.root):
            Path(directory).chmod(0o700)
        shutil.rmtree(self.root)

    def test_only_four_public_inputs_are_opened_and_sources_are_complete(self):
        # Extra assessment target / saved prediction files must never be inspected.
        for name in ("private-targets.npz", "reference_metrics.json", "predictions.npz"):
            (self.inputs / name).write_bytes(b"operator-only sentinel")
        opened_inputs = []
        original = delivery.snapshot

        def audited(path, *args, **kwargs):
            path = Path(path)
            if path.parent == self.inputs:
                opened_inputs.append(path.name)
                self.assertIn(path.name, self.bodies)
            return original(path, *args, **kwargs)

        with patch.object(delivery, "snapshot", side_effect=audited):
            receipt = delivery.export_public(self.inputs, self.output)
        self.assertEqual(set(opened_inputs), set(self.bodies))
        self.assertEqual(len(opened_inputs), 4)
        recovered = json.loads((HERE / "SOURCE_PINS.json").read_text())["files"]
        expected = set(self.bodies) | set(recovered) | {"README.md"}
        self.assertEqual(set(p.name for p in (self.output / "public").iterdir()), expected)
        self.assertEqual(set(receipt["files"]), expected)
        for name, identity in receipt["files"].items():
            self.assertEqual(delivery.pin((self.output / "public" / name).read_bytes()), identity)
        for name, body in self.bodies.items():
            self.assertEqual((self.output / "public" / name).read_bytes(), body)
        self.assertEqual(json.loads((self.output / "receipt.json").read_text()), receipt)
        self.assertEqual(receipt["private_files_opened"], 0)
        self.assertEqual(receipt["numerical_arrays_loaded"], 0)
        self.assertNotIn(str(self.root), json.dumps(receipt))
        self.assertFalse((self.output / "public").stat().st_mode & 0o222)

    def test_wrong_digest_stops_before_any_output(self):
        p = self.inputs / "assessment.npz"
        p.write_bytes(b"X" * p.stat().st_size)
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            delivery.export_public(self.inputs, self.output)
        self.assertFalse(self.output.exists())

    def test_wrong_size_stops_before_any_output(self):
        (self.inputs / "source.npz").write_bytes(b"wrong")
        with self.assertRaisesRegex(ValueError, "length mismatch"):
            delivery.export_public(self.inputs, self.output)
        self.assertFalse(self.output.exists())

    def test_missing_fourth_input_stops_before_any_output(self):
        (self.inputs / "manifest.json").unlink()
        with self.assertRaises(FileNotFoundError):
            delivery.export_public(self.inputs, self.output)
        self.assertFalse(self.output.exists())

    def test_symlinked_asset_and_ancestor_are_rejected(self):
        file = self.inputs / "source.npz"
        actual = self.root / "actual.npz"
        file.rename(actual)
        file.symlink_to(actual)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            delivery.export_public(self.inputs, self.output)
        alias = self.root / "alias"
        alias.symlink_to(self.inputs, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            delivery.export_public(alias, self.output)
        self.assertFalse(self.output.exists())

    def test_hardlinked_asset_is_rejected(self):
        os.link(self.inputs / "source.npz", self.root / "linked.npz")
        with self.assertRaisesRegex(ValueError, "single-link"):
            delivery.export_public(self.inputs, self.output)
        self.assertFalse(self.output.exists())

    def test_existing_output_is_preserved(self):
        self.output.mkdir()
        marker = self.output / "sentinel"
        marker.write_bytes(b"keep")
        with self.assertRaisesRegex(ValueError, "never overwritten"):
            delivery.export_public(self.inputs, self.output)
        self.assertEqual(marker.read_bytes(), b"keep")
        self.assertEqual(list(self.output.iterdir()), [marker])

    def test_changed_recovered_source_stops_before_output(self):
        copy = self.root / "recovered"
        shutil.copytree(HERE / "participant", copy / "participant")
        shutil.copyfile(HERE / "SOURCE_PINS.json", copy / "SOURCE_PINS.json")
        file = copy / "participant" / "reference_core.py"
        raw = file.read_bytes()
        file.write_bytes(b"X" + raw[1:])
        with patch.object(delivery, "HERE", copy), self.assertRaisesRegex(ValueError, "digest mismatch"):
            delivery.export_public(self.inputs, self.output)
        self.assertFalse(self.output.exists())

    def test_changed_recovery_manifest_is_not_accepted(self):
        copy = self.root / "recovered"
        copy.mkdir()
        (copy / "SOURCE_PINS.json").write_text('{"files": {}}')
        with patch.object(delivery, "HERE", copy), self.assertRaisesRegex(ValueError, "manifest changed"):
            delivery.export_public(self.inputs, self.output)
        self.assertFalse(self.output.exists())

    def test_failed_copy_cannot_emit_completion_receipt(self):
        original = delivery.write_new

        def fail(path, body):
            if Path(path).name == "assessment.npz":
                raise OSError("generated write failure")
            return original(path, body)

        with patch.object(delivery, "write_new", side_effect=fail), self.assertRaises(OSError):
            delivery.export_public(self.inputs, self.output)
        self.assertTrue(self.output.exists())
        self.assertFalse((self.output / "receipt.json").exists())

    def test_source_and_real_asset_pins_match_historical_delivery(self):
        # Independent contract authority is the existing delivery manifest,
        # not hashes recalculated only from the newly recovered source files.
        manifest = json.loads((HERE.parents[1] / "contracts/delivery/delivery_manifest.json").read_text())
        public = {Path(row["target"]).name: row for row in manifest["files"]
                  if row["visibility"] == "public"}
        metadata = json.loads((HERE / "SOURCE_PINS.json").read_text())
        self.assertEqual(len(metadata["files"]), 11)
        for name, identity in metadata["files"].items():
            self.assertEqual(identity, {key: public[name][key] for key in ("bytes", "sha256")})
            self.assertEqual(identity, delivery.pin((HERE / "participant" / name).read_bytes()))
        self.patcher.stop()
        try:
            self.assertEqual(set(delivery.ASSET_PINS), {"source.npz", "calibration.npz", "assessment.npz", "manifest.json"})
            for name, identity in delivery.ASSET_PINS.items():
                self.assertEqual(identity, {key: public[name][key] for key in ("bytes", "sha256")})
        finally:
            self.patcher.start()


if __name__ == "__main__":
    unittest.main(verbosity=2)
