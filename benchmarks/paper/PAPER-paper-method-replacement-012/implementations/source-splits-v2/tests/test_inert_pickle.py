import importlib.util
from pathlib import Path
import pickle
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from inert_pickle import FormatError, Record, Symbol, parse


class NeverRun:
    def __reduce__(self):
        return eval, ("1/0",)


class StaticReaderTests(unittest.TestCase):
    def test_primitive_metadata_roundtrip(self):
        value = {"label_map": {"sb025_20191007_u0": "EC"}, "splits": [{"train": ["a", "b"], "test": ("c",)}], "flags": (None, False, 17, b"bytes")}
        for protocol in (2, 3, 4, 5):
            raw = pickle.dumps(value, protocol=protocol)
            if protocol == 2:  # bytes reduce through codecs, which remains inert
                value2 = parse(raw)
                self.assertIsInstance(value2["flags"][-1], Record)
            else:
                self.assertEqual(parse(raw), value)

    def test_reduce_is_data_never_execution(self):
        record = parse(pickle.dumps(NeverRun(), protocol=4))
        self.assertIsInstance(record, Record)
        self.assertEqual(record.constructor.name, "builtins.eval")
        self.assertEqual(record.args, ("1/0",))

    def test_unknown_opcodes_and_malformed_streams(self):
        for raw in (b"\x80\x04Pforeign\n.", b"\x80\x04\x82\x01.", b"\x80\x04h\x00.", b"\x80\x04N.N", b"\x80\x04N", b"\x80\x04(."):
            with self.assertRaises(FormatError):
                parse(raw)

    def test_duplicate_keys_and_bounds(self):
        with self.assertRaisesRegex(FormatError, "duplicate dictionary"):
            parse(b"\x80\x04}(\x8c\x01aK\x01\x8c\x01aK\x02u.")
        raw = pickle.dumps(list(range(20)), protocol=4)
        with self.assertRaises(FormatError): parse(raw, max_bytes=8)
        with self.assertRaises(FormatError): parse(raw, max_ops=3)
        with self.assertRaises(FormatError): parse(raw, max_items=5)


if __name__ == "__main__":
    unittest.main()
