"""Generated software controls only: no authentic input, target, fit or API."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest

SPEC = importlib.util.spec_from_file_location("neural067_bridge", Path(__file__).with_name("bridge.py"))
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)
SCORER_PATH = None


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def vector(run_index, arm_index, row):
    result = [float(run_index * 100000 + arm_index * 10000 + row) + channel / 8 for channel in range(7)]
    if run_index == arm_index == row == 0:
        result[0] = -0.0
    return result


class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scorer = bridge.load_scorer(SCORER_PATH)
        cls.inputs = {}
        cls.descriptors = []
        cls.bodies = {}
        for ri, (run, _, count) in enumerate(cls.scorer.QUERY):
            # Pins identify small explicit generated text, never a real source packet.
            fixture = ("GENERATED SOFTWARE CONTROL INPUT " + run).encode()
            cls.inputs[run] = {"bytes": len(fixture), "sha256": hashlib.sha256(fixture).hexdigest()}
            for ai, arm in enumerate(cls.scorer.ARMS):
                header = encode({"schema": "neural067_action_journal_v1", "run": run, "arm": arm,
                    "rows": count, "input": cls.inputs[run], "encoding": bridge.RECORD.format,
                    "record_bytes": bridge.RECORD.size, "header_bytes": bridge.HEADER_BYTES})
                body = bytearray(header + bytes(bridge.HEADER_BYTES - len(header)))
                previous = bytes(32)
                for row in range(count):
                    # Observation digest is opaque to the adapter; no neural observation exists.
                    prefix = struct.pack("<Q7d", row, *vector(ri, ai, row)) + bytes(32) + previous
                    previous = hashlib.sha256(prefix).digest()
                    body.extend(prefix + previous)
                raw = bytes(body)
                name = f"{run}__{arm}.bin"
                cls.bodies[name] = raw
                cls.descriptors.append({"run": run, "arm": arm, "file": name, "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(), "final_chain": previous.hex()})

    def convert(self, descriptors=None, bodies=None, inputs=None, loader=None):
        return bridge.convert(self.descriptors if descriptors is None else descriptors,
            (self.bodies if bodies is None else bodies).__getitem__ if loader is None else loader,
            self.inputs if inputs is None else inputs, scorer_path=SCORER_PATH)

    def changed_first(self, raw):
        descriptors = copy.deepcopy(self.descriptors)
        bodies = dict(self.bodies)
        bodies[descriptors[0]["file"]] = raw
        descriptors[0]["sha256"] = hashlib.sha256(raw).hexdigest()
        return descriptors, bodies

    def test_complete_panel_lossless_current_admission(self):
        result = self.convert()
        self.assertEqual(result["columns"], ["tx", "ty", "tz", "rx", "g1", "g2", "g3"])
        self.assertEqual(len(result["entries"]), 56)
        self.assertEqual(sum(len(x["prediction"]) for x in result["entries"]), 137960)
        for index, entry in enumerate(result["entries"]):
            ai, ri = divmod(index, 14)
            run, session, count = self.scorer.QUERY[ri]
            self.assertEqual((entry["arm"], entry["run"], entry["session"]),
                             (self.scorer.ARMS[ai], run, session))
            self.assertEqual(entry["row_ids"], list(range(count)))
            for row, values in enumerate(entry["prediction"]):
                self.assertEqual(struct.pack("<7d", *values), struct.pack("<7d", *vector(ri, ai, row)))
        self.assertEqual(len(self.scorer.admit(result)), 56)

    def test_descriptor_shape_order_and_support_refuse_before_loader(self):
        cases = [self.descriptors[:-1], self.descriptors + [self.descriptors[0]]]
        for change in ("swap", "duplicate", "path", "extent", "boolean", "extra"):
            rows = copy.deepcopy(self.descriptors)
            if change == "swap": rows[0], rows[1] = rows[1], rows[0]
            if change == "duplicate": rows[-1] = rows[0]
            if change == "path": rows[-1]["file"] = "../outside.bin"
            if change == "extent": rows[-1]["bytes"] -= 160
            if change == "boolean": rows[-1]["bytes"] = True
            if change == "extra": rows[-1]["unknown"] = 1
            cases.append(rows)
        for rows in cases:
            with self.subTest(case=len(rows)), self.assertRaises(ValueError):
                self.convert(descriptors=rows, loader=lambda _: self.fail("must validate all descriptors first"))

    def test_input_pin_support_and_types_refuse_before_loader(self):
        for change in ("missing", "extra", "boolean", "digest", "extra_field"):
            inputs = copy.deepcopy(self.inputs)
            run = self.scorer.QUERY[-1][0]
            if change == "missing": del inputs[run]
            if change == "extra": inputs["unknown"] = inputs[run]
            if change == "boolean": inputs[run]["bytes"] = True
            if change == "digest": inputs[run]["sha256"] = "g" * 64
            if change == "extra_field": inputs[run]["unknown"] = 1
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.convert(inputs=inputs, loader=lambda _: self.fail("must validate inputs first"))

    def test_extent_and_whole_journal_pin(self):
        raw = self.bodies[self.descriptors[0]["file"]]
        for changed in (raw[:-1], raw + b"x", bytes([raw[0] ^ 1]) + raw[1:], bytearray(raw)):
            bodies = dict(self.bodies)
            bodies[self.descriptors[0]["file"]] = changed
            with self.subTest(kind=type(changed).__name__), self.assertRaises(ValueError):
                self.convert(bodies=bodies)

    def test_header_identity_input_padding_and_duplicate_fields(self):
        original = self.bodies[self.descriptors[0]["file"]]
        for change in ("run", "arm", "count", "input", "padding", "duplicate"):
            header = bridge.parse_header(original)
            if change == "run": header["run"] = self.scorer.QUERY[1][0]
            if change == "arm": header["arm"] = "clock"
            if change == "count": header["rows"] -= 1
            if change == "input": header["input"]["bytes"] += 1
            head = encode(header)
            if change == "duplicate": head = b'{"run":"duplicate",' + head[1:]
            padding = bytes(bridge.HEADER_BYTES - len(head))
            if change == "padding": padding = padding[:-1] + b"x"
            raw = head + padding + original[bridge.HEADER_BYTES:]
            descriptors, bodies = self.changed_first(raw)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.convert(descriptors, bodies)

    def test_record_ordinal_nonfinite_predecessor_and_checksum(self):
        original = self.bodies[self.descriptors[0]["file"]]
        for change in ("ordinal", "nan", "inf", "predecessor", "checksum"):
            raw = bytearray(original)
            offset = bridge.HEADER_BYTES
            if change == "ordinal": struct.pack_into("<Q", raw, offset, 1)
            if change in ("nan", "inf"): struct.pack_into("<d", raw, offset + 8, float(change))
            if change == "predecessor": raw[offset + 96] ^= 1
            if change == "checksum": raw[offset + 64] ^= 1
            descriptors, bodies = self.changed_first(bytes(raw))
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.convert(descriptors, bodies)

    def test_selected_final_chain_must_match(self):
        descriptors = copy.deepcopy(self.descriptors)
        descriptors[0]["final_chain"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "final chain"):
            self.convert(descriptors=descriptors)

    def test_callback_cannot_mutate_later_descriptor_or_input_snapshot(self):
        descriptors = copy.deepcopy(self.descriptors)
        inputs = copy.deepcopy(self.inputs)
        called = []
        def loader(name):
            called.append(name)
            if len(called) == 1:
                descriptors[-1]["file"] = "../mutated"
                inputs[self.scorer.QUERY[-1][0]]["bytes"] += 1
            return self.bodies[name]
        result = self.convert(descriptors=descriptors, inputs=inputs, loader=loader)
        self.assertEqual(called, [row["file"] for row in self.descriptors])
        self.assertEqual(len(result["entries"]), 56)

    def test_loader_failure_returns_no_partial_submission(self):
        called = []
        def loader(name):
            called.append(name)
            if len(called) == 56: raise OSError("generated final capture failure")
            return self.bodies[name]
        with self.assertRaisesRegex(OSError, "generated final capture failure"):
            self.convert(loader=loader)
        self.assertEqual(len(called), 56)

    def test_scorer_source_substitution_refused_before_execution(self):
        with self.assertRaisesRegex(ValueError, "exact unchanged current session scorer source"):
            bridge.load_scorer(Path(__file__).with_name("bridge.py"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scorer-path", type=Path)
    args, remaining = parser.parse_known_args()
    SCORER_PATH = args.scorer_path
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
