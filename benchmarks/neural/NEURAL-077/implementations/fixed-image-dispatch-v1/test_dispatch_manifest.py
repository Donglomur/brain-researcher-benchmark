"""Generated-only controls; no retained neural payload, prediction or gold."""
import base64
import copy
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

import dispatch_manifest as d

GENERATED_BYTES_WRITTEN = 0


def png(extra_scanline=b"", marker=0):
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xffffffff)
    scanlines = (b"\0" + bytes([marker, 255, 255]) + b"\xff\xff\xff" * 1399
                 + (b"\0" + b"\xff\xff\xff" * 1400) * 819 + extra_scanline)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 1400, 820, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(scanlines)) + chunk(b"IEND", b""))


class DispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        names = ["demo1", "demo2", "demo3", "demo4", "case-0001", "case-0002"]
        cls.images = {name: png(marker=i + 1) for i, name in enumerate(names)}
        cls.image = cls.images["case-0001"]

    def setUp(self):
        global GENERATED_BYTES_WRITTEN
        self.temp = tempfile.TemporaryDirectory(prefix="generated-dispatch-", dir=os.environ.get("ARTIFACT_DIR"))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.protocol = "a" * 64
        def row(name):
            return {"image_id": name, "file": name + ".png", **d.pin(self.images[name])}
        self.obj = {"schema": "erp-image-dispatch/v1", "protocol_sha256": self.protocol,
                    "prompts": {"direct": "Inspect supplied images for {trial_id}.",
                                "programme": "Run frozen image programme for {trial_id}."},
                    "demonstrations": [row(f"demo{i}") for i in range(1, 5)],
                    "queries": [row("case-0001"), row("case-0002")]}
        # case-0002 is deliberately absent. Preparing one query must not read it.
        for row in self.obj["demonstrations"] + self.obj["queries"][:1]:
            body = self.images[row["image_id"]]
            (self.root / row["file"]).write_bytes(body)
            GENERATED_BYTES_WRITTEN += len(body)

    def prepare(self, obj=None, arm="direct", trial_id="case-0001", protocol=None):
        body = d.encode(self.obj if obj is None else obj)
        return d.prepare_payload(body, d.pin(body)["sha256"], protocol or self.protocol,
                                 self.root, trial_id, arm)

    def test_same_attachment_bytes_both_arms_and_no_other_query_read(self):
        direct = self.prepare()
        programme = self.prepare(arm="programme")
        self.assertEqual(direct["images"], programme["images"])
        self.assertEqual([r["image_id"] for r in direct["images"]],
                         ["demo1", "demo2", "demo3", "demo4", "case-0001"])
        for row in direct["images"]:
            self.assertEqual(base64.b64decode(row["data_base64"], validate=True),
                             self.images[row["image_id"]])
        self.assertNotIn(str(self.root), d.encode(direct).decode())
        self.assertIn("case-0001", direct["prompt"])
        self.assertNotIn("{trial_id}", direct["prompt"])

    def test_missing_selected_attachment_refuses_no_replacement(self):
        (self.root / "case-0001.png").unlink()
        with self.assertRaises(FileNotFoundError):
            self.prepare()

    def test_swapped_valid_images_fail_frozen_identity(self):
        global GENERATED_BYTES_WRITTEN
        for destination, source in (("demo1", "case-0001"), ("case-0001", "demo1")):
            body = self.images[source]
            (self.root / (destination + ".png")).write_bytes(body)
            GENERATED_BYTES_WRITTEN += len(body)
        with self.assertRaisesRegex(ValueError, "(hash|extent) mismatch"):
            self.prepare()

    def test_modified_body_fails_its_frozen_hash(self):
        global GENERATED_BYTES_WRITTEN
        p = self.root / "case-0001.png"
        p.write_bytes(self.image[:-1] + bytes([self.image[-1] ^ 1]))
        GENERATED_BYTES_WRITTEN += len(self.image)
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.prepare()

    def test_wrong_extent_fails_before_body_read(self):
        self.obj["queries"][0]["bytes"] += 1
        with self.assertRaisesRegex(ValueError, "extent mismatch"):
            self.prepare()

    def test_symlink_attachment_refused(self):
        p = self.root / "case-0001.png"
        p.unlink()
        p.symlink_to(self.root / "demo1.png")
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.prepare()

    def test_duplicate_manifest_key_refused(self):
        body = b'{"schema":"one","schema":"two"}'
        with self.assertRaisesRegex(ValueError, "duplicate JSON"):
            d.validate_manifest(body, d.pin(body)["sha256"], self.protocol)

    def test_unknown_private_field_refused_before_any_attachment_read(self):
        self.obj["queries"][0]["target"] = 1
        with patch.object(d, "read", side_effect=AssertionError("must not open")):
            with self.assertRaisesRegex(ValueError, "exact image descriptor"):
                self.prepare()

    def test_path_typo_or_traversal_refused_before_read(self):
        for filename in ("case-001.png", "../case-0001.png", "/private/case-0001.png"):
            with self.subTest(filename=filename):
                obj = copy.deepcopy(self.obj)
                obj["queries"][0]["file"] = filename
                with patch.object(d, "read", side_effect=AssertionError("must not open")):
                    with self.assertRaisesRegex(ValueError, "filename must derive"):
                        self.prepare(obj)

    def test_duplicate_query_id_refused(self):
        self.obj["queries"][1] = copy.deepcopy(self.obj["queries"][0])
        with self.assertRaisesRegex(ValueError, "unique image ID"):
            self.prepare()

    def test_protocol_or_manifest_commitment_refused(self):
        with self.assertRaisesRegex(ValueError, "protocol binding"):
            self.prepare(protocol="b" * 64)
        body = d.encode(self.obj)
        with self.assertRaisesRegex(ValueError, "manifest commitment"):
            d.validate_manifest(body, "b" * 64, self.protocol)

    def test_absent_query_or_unknown_arm_refused_before_read(self):
        with patch.object(d, "read", side_effect=AssertionError("must not open")):
            with self.assertRaisesRegex(ValueError, "committed roster"):
                self.prepare(trial_id="case-0003")
            with self.assertRaisesRegex(ValueError, "known arm"):
                self.prepare(arm="raw_signal")

    def test_prompt_substitution_ambiguity_refused(self):
        for prompt in ("no identifier", "{trial_id} {trial_id}", "{trial_id} {private}"):
            with self.subTest(prompt=prompt):
                self.obj["prompts"]["direct"] = prompt
                with self.assertRaises(ValueError):
                    self.prepare()

    def test_rehashed_invalid_png_crc_refused(self):
        global GENERATED_BYTES_WRITTEN
        body = self.image[:-1] + bytes([self.image[-1] ^ 1])
        (self.root / "case-0001.png").write_bytes(body)
        GENERATED_BYTES_WRITTEN += len(body)
        self.obj["queries"][0].update(d.pin(body))
        with self.assertRaisesRegex(ValueError, "CRC mismatch"):
            self.prepare()

    def test_overexpanded_png_refused_even_with_correct_hash(self):
        global GENERATED_BYTES_WRITTEN
        body = png(b"overflow")
        (self.root / "case-0001.png").write_bytes(body)
        GENERATED_BYTES_WRITTEN += len(body)
        self.obj["queries"][0].update(d.pin(body))
        with self.assertRaisesRegex(ValueError, "decoded extent"):
            self.prepare()

    def test_nonfinite_or_boolean_extent_refused(self):
        for value in (True, -1, d.IMAGE_CAP + 1):
            with self.subTest(value=value):
                self.obj["queries"][0]["bytes"] = value
                with self.assertRaisesRegex(ValueError, "bounded image extent"):
                    self.prepare()
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            d.decode(b'{"x":NaN}')


if __name__ == "__main__":
    unittest.main()
