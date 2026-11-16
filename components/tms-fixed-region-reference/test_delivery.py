"""Generated delivery-boundary checks; no authentic arrays or statistics."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
BEHAVIOR = None
PINS = {
    "portable_regions.py": (10505, "b7b919c277340ed73953bd8b921f2bb2570008997565c91a41d3eac994089b93"),
    "projection_verify.py": (20338, "c98bdf711e9245202c5f4cbd498e5bc22f65b0387d31367650a4ab8e453b201d"),
    "behavior_reference.py": (14692, "f3c724074660dda8f692831eecd6082fd4c7e1750714aa3e3fb8d15a7d4d9109"),
}


def load(path, name):
    raw = path.read_bytes()
    if (len(raw), hashlib.sha256(raw).hexdigest()) != PINS[path.name]:
        raise ValueError("wrong delivery source: " + str(path))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeliveryChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.producer = load(HERE / "portable_regions.py", "delivered_regions")
        cls.verifier = load(HERE / "projection_verify.py", "delivered_verifier")

    def test_complete_dependency_identity_and_import(self):
        m = self.producer
        self.assertEqual(m.VERIFIER_PIN, PINS["projection_verify.py"])
        self.assertEqual(m.BEHAVIOR_PIN, PINS["behavior_reference.py"])
        v = m.pinned_module(HERE / "projection_verify.py", m.VERIFIER_PIN, "reader_check")
        b = m.pinned_module(BEHAVIOR, m.BEHAVIOR_PIN, "statistics_check")
        self.assertTrue(callable(v.ordinary) and callable(v.decode))
        self.assertTrue(all(callable(getattr(b, n)) for n in
                            ("exact_sign_flip", "paired_summary", "bootstrap_interval", "holm")))

    def test_changed_dependency_refused_before_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "changed.py"
            p.write_text("raise AssertionError('untrusted code executed')\n")
            with self.assertRaisesRegex(ValueError, "wrong immutable source"):
                self.producer.pinned_module(p, self.producer.BEHAVIOR_PIN, "must_not_load")

    def test_json_duplicate_and_nonfinite_refused(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.verifier.decode(raw)

    def test_ordinary_exact_pin_extent_and_alias_refusals(self):
        v = self.verifier
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            p = root / "input.json"; p.write_bytes(b'{}\n')
            v.READS = 0; v.DEADLINE = time.monotonic() + 10
            self.assertEqual(v.ordinary(p, 3, v.pin(b'{}\n'))[0], b'{}\n')
            for cap, expected in ((2, None), (3, {"bytes": 3, "sha256": "0" * 64})):
                with self.subTest(cap=cap), self.assertRaises(ValueError):
                    v.ordinary(p, cap, expected)
            link = root / "symbolic"; link.symlink_to(p)
            with self.assertRaises(ValueError): v.ordinary(link, 3)
            hard = root / "hard"; os.link(p, hard)
            with self.assertRaises(ValueError): v.ordinary(hard, 3)
            with self.assertRaises(ValueError): v.ordinary(Path("relative"), 3)

    def test_bad_projection_refused_before_tensor_read(self):
        # Synthetic metadata reaches geometry checks only. The sentinel reader
        # raises if the producer attempts any tensor read.
        m = self.producer
        base = {
            "schema": "tms-full-paired-original-input-v1", "shape": [4, 7, 53, 200, 15],
            "conditions": list(m.CONDITIONS), "source_positions": list(range(15)),
            "source_declared_roster": list(m.ROSTER), "scientific_contract": {"sha256": m.CONTRACT_SHA},
            "dtype": "little-endian-IEEE754-binary64", "order": "C; source_position fastest",
            "values": {"file": "values.f64", "bytes": 35616000, "sha256": "0" * 64},
            "frequency_coordinates": list(range(53)),
            "time_coordinates": [i / 20 for i in range(200)], "selected_labels": list(m.ROI7),
        }
        invalid = []
        for key, value in (("shape", [4, 7, 53, 200, 14]), ("conditions", list(reversed(m.CONDITIONS))),
                           ("source_positions", list(range(14))), ("dtype", "float32"),
                           ("selected_labels", ["O1"] * 7), ("frequency_coordinates", [1] * 53)):
            row = copy.deepcopy(base); row[key] = value; invalid.append(row)
        row = copy.deepcopy(base); row["values"]["bytes"] = 8; invalid.append(row)
        row = copy.deepcopy(base); del row["scientific_contract"]; invalid.append(row)
        for row in invalid:
            seen = []
            def ordinary(path, cap, expected):
                seen.append(Path(path).name)
                self.assertEqual(seen, ["INPUT.json"], "invalid metadata reached tensor read")
                return json.dumps(row).encode(), {}
            fake = types.SimpleNamespace(ordinary=ordinary, decode=self.verifier.decode)
            with self.subTest(keys=tuple(row)), self.assertRaises((ValueError, KeyError)):
                m.load_projection(Path("/invented/input"), 17, "0" * 64, fake)
            self.assertEqual(seen, ["INPUT.json"])

    def invoke_stubbed_main(self, output):
        m = self.producer
        meta = {"selected_labels": [], "frequency_coordinates": [], "time_coordinates": [],
                "values": {"file": "values.f64", "bytes": 8, "sha256": "0" * 64}}
        argv = ["portable_regions.py", "--input-root", "/invented/private/input", "--manifest-bytes", "17",
                "--manifest-sha256", "0" * 64, "--projection-verifier", "/invented/verifier.py",
                "--behavior-source", "/invented/behavior.py", "--output", str(output)]
        with patch.object(sys, "argv", argv), patch.object(m, "pinned_module", return_value=object()), \
             patch.object(m, "load_projection", return_value=(meta, object())), \
             patch.object(m, "reduce_regions", return_value=object()), \
             patch.object(m, "infer_regions", return_value={"generated_control": True}):
            m.main()

    def test_output_envelope_has_no_input_path(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "generated.json"; self.invoke_stubbed_main(out)
            value = json.loads(out.read_text())
            self.assertEqual(set(value), {"generated_control", "input_manifest", "projection_values"})
            self.assertEqual(value["input_manifest"], {"bytes": 17, "sha256": "0" * 64})
            self.assertNotIn("/invented", out.read_text())

    def test_existing_output_and_symlink_are_not_replaced(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "existing.json"; out.write_bytes(b"preserve")
            with self.assertRaises(FileExistsError): self.invoke_stubbed_main(out)
            self.assertEqual(out.read_bytes(), b"preserve")
            link = Path(temp) / "alias.json"; link.symlink_to(out)
            with self.assertRaises(FileExistsError): self.invoke_stubbed_main(link)
            self.assertEqual(out.read_bytes(), b"preserve")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--behavior-source", required=True, type=Path)
    args, remaining = parser.parse_known_args()
    BEHAVIOR = args.behavior_source.resolve(strict=True)
    unittest.main(argv=[sys.argv[0], *remaining])
