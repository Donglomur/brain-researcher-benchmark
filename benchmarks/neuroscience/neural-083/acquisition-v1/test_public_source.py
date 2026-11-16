"""Finite public relocation checks. No datasets, numerical imports or live transport."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve()
ROOT = HERE.parent
FILES = ("acquire.py", "bounded_http.py", "publisher_roster.json", "test_acquire.py",
         "REQUEST.INERT.json", "README.md", "NOTICE.md", "LICENSE",
         "test_public_source.py", "SOURCE.json")


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def load_source(folder):
    spec = importlib.util.spec_from_file_location("neural083_relocated", folder / "acquire.py")
    module = importlib.util.module_from_spec(spec)
    with patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")):
        spec.loader.exec_module(module)
    return module


class PublicSource(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="neural083 public source ")
        # Only the newly owned test fixture is resolved, for platform temp aliases.
        self.parent = Path(self.temp.name).resolve()
        self.copy = self.parent / "relocated source with spaces"
        self.copy.mkdir()
        for name in FILES:
            shutil.copyfile(ROOT / name, self.copy / name)
        self.other = self.parent / "unrelated cwd"
        self.other.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def test_public_payload_pins_and_privacy(self):
        manifest = json.loads((self.copy / "SOURCE.json").read_bytes())
        self.assertEqual(manifest["schema"], "neural083_public_acquisition_source_v1")
        self.assertEqual(set(manifest["files"]), set(FILES) - {"SOURCE.json"})
        for name, expected in manifest["files"].items():
            self.assertEqual(pin((self.copy / name).read_bytes()), expected, name)
        for name in FILES:
            text = (self.copy / name).read_text()
            for forbidden in ("/" + "Users/", "/" + "home/nicholas/",
                              "benchmark-" + "engineering-evidence",
                              "authoring/" + "delivery-", "X-Amz-" + "Signature="):
                self.assertNotIn(forbidden, text, name)
        self.assertFalse(manifest["authentic_acquisition_completed"])
        self.assertFalse(manifest["scientific_qualified"])

    def test_relocated_import_and_full_roster(self):
        before = Path.cwd()
        try:
            os.chdir(self.other)
            module = load_source(self.copy)
            roster = module.roster(str(self.copy / "publisher_roster.json"))
        finally:
            os.chdir(before)
        rows = roster["files"]
        self.assertEqual(len(rows), 108)
        self.assertEqual([(r["person"], r["session"]) for r in rows],
                         [(p, s) for p in range(1, 55) for s in (1, 2)])
        self.assertEqual(sum(r["bytes"] for r in rows), 64847432285)
        self.assertEqual(hashlib.sha256(module.encoded(rows)).hexdigest(), module.ROWS_SHA256)
        self.assertEqual(roster["inventory_sha256"],
                         "aef0f1c484527da571a2b77a0c93bf081ba4fd51aed6e3bf1babd4fae9f8f9ce")

    def test_relocated_inert_cli_and_no_output(self):
        request = self.copy / "REQUEST.INERT.json"
        request_pin = pin(request.read_bytes())
        before = sorted(p.relative_to(self.parent).as_posix() for p in self.parent.rglob("*"))
        result = subprocess.run([sys.executable, "-I", "-S", "-B", str(self.copy / "acquire.py"),
                                 "--roster", str(self.copy / "publisher_roster.json"),
                                 "--request", str(request),
                                 "--request-bytes", str(request_pin["bytes"]),
                                 "--request-sha256", request_pin["sha256"]],
                                cwd=self.other, capture_output=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"separate actual root execution selection required", result.stderr)
        self.assertEqual(before, sorted(p.relative_to(self.parent).as_posix()
                                       for p in self.parent.rglob("*")))

    def test_relocated_missing_helper_refused(self):
        (self.copy / "bounded_http.py").unlink()
        with self.assertRaises(FileNotFoundError):
            load_source(self.copy)

    def test_relocated_equal_extent_helper_corruption_refused(self):
        helper = self.copy / "bounded_http.py"
        body = helper.read_bytes()
        helper.write_bytes(body.replace(b"HEADER_CAP = 4096", b"HEADER_CAP = 4095", 1))
        self.assertEqual(helper.stat().st_size, len(body))
        with self.assertRaisesRegex(ValueError, "metadata digest mismatch"):
            load_source(self.copy)

    def test_relocated_helper_symlink_refused(self):
        helper = self.copy / "bounded_http.py"
        outside = self.parent / "outside-helper.py"
        helper.rename(outside)
        helper.symlink_to(outside)
        with self.assertRaises(OSError):
            load_source(self.copy)

    def test_relocated_roster_corruption_refused(self):
        module = load_source(self.copy)
        roster = self.copy / "publisher_roster.json"
        body = roster.read_bytes()
        replacement = body.replace(b"5f4efd43bd9d4164a777362062a7e6a5",
                                   b"0f4efd43bd9d4164a777362062a7e6a5", 1)
        self.assertNotEqual(body, replacement)
        roster.write_bytes(replacement)
        with self.assertRaisesRegex(ValueError, "metadata digest mismatch"):
            module.roster(str(roster))

    def test_inert_request_and_fixed_public_urls(self):
        request = json.loads((self.copy / "REQUEST.INERT.json").read_bytes())
        self.assertIs(request["execution_authorized"], False)
        for field in ("output_root", "minimum_free_bytes", "owner_receipt"):
            self.assertIsNone(request[field])
        roster = json.loads((self.copy / "publisher_roster.json").read_bytes())
        base = ("https://s3.ap-northeast-1.wasabisys.com/gigadb-datasets/live/pub/"
                "10.5524/100001_101000/100542/")
        for row in roster["files"]:
            self.assertEqual(row["url"], base + row["path"])
            self.assertNotIn("?", row["url"])
            self.assertNotIn("#", row["url"])
        self.assertEqual(roster["publisher_checksum_sidecar"]["url"], base + "100542.md5")


if __name__ == "__main__":
    unittest.main(verbosity=2)
