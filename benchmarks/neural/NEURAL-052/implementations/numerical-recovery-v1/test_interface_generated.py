"""Temporary invented JSON/files only; no dataset, model or scientific I/O."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import interface as io


class GeneratedIOChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_same_captured_bytes_hash_decode_and_roundtrip(self):
        path = self.root / "input.json"
        raw = '{"unicode":"μ","braces":"[\\\"{]","v":[null,3,0.125]}'.encode("utf-8")
        path.write_bytes(raw)
        captured = io.capture_regular(path, cap=len(raw))
        self.assertEqual(hashlib.sha256(captured).digest(), hashlib.sha256(raw).digest())
        value = io.decode_json(captured)
        self.assertEqual(value, io.read_json(path))
        output = self.root / "output.json"
        io.write_json_fresh(output, value)
        self.assertEqual(io.read_json(output), value)
        self.assertTrue(output.read_bytes().endswith(b"\n"))

    def test_nonregular_symlink_dangling_fifo_and_missing_rejected(self):
        target = self.root / "regular"
        target.write_text("{}")
        symlink = self.root / "link"
        symlink.symlink_to(target)
        dangling = self.root / "dangling"
        dangling.symlink_to(self.root / "missing")
        fifo = self.root / "fifo"
        os.mkfifo(fifo)
        for path in (symlink, dangling, fifo, self.root, self.root / "absent"):
            with self.subTest(path=path.name), self.assertRaises(io.Invalid):
                io.capture_regular(path)

    def test_initial_cap_growth_and_named_replacement_rejected(self):
        path = self.root / "input"
        path.write_bytes(b"{}")
        with self.assertRaises(io.Invalid):
            io.capture_regular(path, cap=1)
        original_read = os.read
        touched = False
        def grow(fd, size):
            nonlocal touched
            if not touched:
                touched = True
                with path.open("ab") as stream:
                    stream.write(b" ")
            return original_read(fd, size)
        with mock.patch.object(io.os, "read", side_effect=grow), self.assertRaises(io.Invalid):
            io.capture_regular(path, cap=20)
        path.write_bytes(b"{}")
        replacement = self.root / "replacement"
        replacement.write_bytes(b"[]")
        touched = False
        def replace(fd, size):
            nonlocal touched
            result = original_read(fd, size)
            if not touched:
                touched = True
                os.replace(replacement, path)
            return result
        with mock.patch.object(io.os, "read", side_effect=replace), self.assertRaises(io.Invalid):
            io.capture_regular(path)

    def test_duplicate_nonfinite_overflow_deep_and_large_integer_normalized(self):
        examples = [b'{"a":1,"a":2}', b'{"x":{"a":0,"a":1}}', b'NaN', b'Infinity',
                    b'-Infinity', b'1e999', b'-1e999', b'\xff', b'{broken}',
                    b'[' * 5000 + b'0' + b']' * 5000, b'9' * 5000]
        for body in examples:
            with self.subTest(body=body[:30]), self.assertRaises(io.Invalid):
                io.decode_json(body)
        self.assertEqual(io.decode_json(b'[' * 4 + b'0' + b']' * 4, max_depth=4), [[[[0]]]])
        with self.assertRaises(io.Invalid):
            io.decode_json(b'[' * 5 + b'0' + b']' * 5, max_depth=4)
        # String punctuation/escapes must not be mistaken for nested containers.
        text = '[' * 1000 + '"' + '\\' + '}' * 1000
        self.assertEqual(io.decode_json(json.dumps(text).encode(), max_depth=1), text)

    def test_fresh_writer_preserves_existing_and_dangling_destinations(self):
        existing = self.root / "existing"
        existing.write_bytes(b"original")
        target = self.root / "not_created"
        dangling = self.root / "dangling"
        dangling.symlink_to(target)
        for path in (existing, dangling):
            with self.subTest(path=path.name), self.assertRaises(io.Invalid):
                io.write_json_fresh(path, {"new": 1})
        self.assertEqual(existing.read_bytes(), b"original")
        self.assertTrue(dangling.is_symlink())
        self.assertFalse(target.exists())
        # A destination appearing after serialization still loses to O_EXCL.
        race = self.root / "race"
        original_open = os.open
        def create_first(path, flags, *args, **kwargs):
            if Path(path) == race:
                race.write_bytes(b"racer")
            return original_open(path, flags, *args, **kwargs)
        with mock.patch.object(io.os, "open", side_effect=create_first), self.assertRaises(io.Invalid):
            io.write_json_fresh(race, {})
        self.assertEqual(race.read_bytes(), b"racer")

    def test_invalid_reports_fail_before_creating_any_output(self):
        cyclic = []
        cyclic.append(cyclic)
        deep = 0
        for _ in range(65):
            deep = [deep]
        for i, value in enumerate((float("nan"), float("inf"), cyclic, deep, "\ud800", {1: 0, "1": 1})):
            path = self.root / f"bad{i}.json"
            with self.subTest(value_type=type(value).__name__), self.assertRaises(io.Invalid):
                io.write_json_fresh(path, value)
            self.assertFalse(path.exists())
        capped = self.root / "cap"
        with self.assertRaises(io.Invalid):
            io.write_json_fresh(capped, "x" * 100, cap=20)
        self.assertFalse(capped.exists())
        with self.assertRaises(io.Invalid):
            io.write_json_fresh(self.root / "absent" / "report", {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
