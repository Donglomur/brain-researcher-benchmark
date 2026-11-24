"""Generated interface controls; no targets, decoder, Docker or subprocesses."""
import hashlib
import importlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
IMPLEMENTATIONS = Path(os.environ.get("NEURAL067_IMPLEMENTATIONS", str(HERE.parent)))
HOST = IMPLEMENTATIONS / "trusted-grading-wiring-v1"


def load(name, path, package=False):
    spec = importlib.util.spec_from_file_location(name, path,
        submodule_search_locations=[str(path.parent)] if package else None)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


client = load("neural067_participant_client", HERE / "client.py")
builder = load("neural067_participant_bundle", HERE / "bundle.py")
sys.path.insert(0, str(HOST))  # Existing profile.py imports its sibling mount_policy.
load("neural067_client_host", HOST / "runtime/__init__.py", package=True)
host = importlib.import_module("neural067_client_host.candidate")
host_stream = importlib.import_module("neural067_client_host.stream")
scorer = load("neural067_client_scorer", HOST / "worker/grading/session-evaluator-v1/scorer.py")


def observation(arm, ordinal):
    result = {}
    if arm != "clock":
        result["spikes"] = [(ordinal + i) % 256 for i in range(176)]
    if arm != "neural":
        result.update(elapsed_run_s=ordinal * .02,
                      observed_segment_age_s=(ordinal % 20) * .02,
                      segment_started_now=ordinal % 20 == 0)
    return result


def prediction(value):
    # Deliberate generated callback, not a proposed decoder or reference model.
    if "spikes" in value:
        return [float(x - 128) for x in value["spikes"][:7]]
    return [value["elapsed_run_s"] * (i - 3) for i in range(7)]


def wire(value):
    return (json.dumps(value, separators=(",", ":")) + "\n").encode()


def row(arm="neural", ordinal=0, token="a" * 32):
    return {"schema": "neural067_observation_v1", "token": token,
            "ordinal": ordinal, "observation": observation(arm, ordinal)}


class ClientTests(unittest.TestCase):
    def test_state_frame_decodes_in_production_host(self):
        body = b"\x00\xffopaque\nstate\x00"
        output = io.BytesIO()
        client.write_state(body, output)
        raw = output.getvalue()
        magic_length = len(host_stream.MAGIC)
        self.assertEqual(raw[:magic_length], b"N067STATE1\n")
        self.assertEqual(struct.unpack("<Q", raw[magic_length:magic_length + 8]), (len(body),))
        stream = host_stream.Stream.__new__(host_stream.Stream)
        stream._header = bytearray()
        stream._length = None
        stream._state_written = 0
        stream._state_hash = hashlib.sha256()
        stream._expected_hash = None
        stream._state_complete = False
        captured = io.BytesIO()
        stream._sink = captured.write
        for i in range(0, len(raw), 7):
            stream._training(raw[i:i + 7])
        self.assertTrue(stream._state_complete)
        self.assertEqual(captured.getvalue(), body)
        for invalid in (b"", "text", bytearray(b"x")):
            with self.assertRaises(ValueError):
                client.write_state(invalid, io.BytesIO())
        with patch.object(client, "STATE_CAP", 4), self.assertRaises(ValueError):
            client.write_state(b"12345", io.BytesIO())

    def test_query_flushes_each_action_before_next_read(self):
        output = io.BytesIO()
        lines = [wire(row()), wire(row(ordinal=1)), wire({"schema": "neural067_end_v1", "token": "a" * 32})]
        outer = self

        class Input:
            calls = 0

            def readline(self, cap):
                outer.assertEqual(output.getvalue().count(b"\n"), self.calls + 1)
                outer.assertEqual(cap, client.INPUT_CAP + 1)
                result = lines[self.calls]
                self.calls += 1
                return result

        source = Input()
        self.assertEqual(client.query("neural", prediction, source, output), 2)
        self.assertEqual(source.calls, 3)
        self.assertEqual(len(output.getvalue().splitlines()), 4)
        self.assertEqual(json.loads(output.getvalue().splitlines()[-1]),
                         {"schema": "neural067_stopped_v1", "token": "a" * 32})
        with self.assertRaisesRegex(ValueError, "EOF"):
            client.query("neural", prediction, io.BytesIO(wire(row())), io.BytesIO())

    def test_invalid_transport_never_calls_method(self):
        cases = [b'{"schema":"x","schema":"y"}\n', wire(dict(row(), ordinal=True)),
                 wire(dict(row(), ordinal=1)), wire(dict(row(), token="wrong")),
                 wire(dict(row(), target=[1] * 7)), wire(row()).rstrip(b"\n"),
                 wire(row()) + wire(row()), b" " * 4097 + b"\n",
                 wire({"schema": "neural067_end_v1", "token": "a" * 32})]
        for value in ({"spikes": [0] * 175}, {"spikes": [True] * 176},
                      {"spikes": [-1] * 176}, {"spikes": [256] * 176},
                      {"spikes": [0.1] * 176}, {"spikes": [0] * 176, "velocity": [0] * 7}):
            cases.append(wire(dict(row(), observation=value)))
        for body in cases:
            with self.subTest(body=body[:80]), self.assertRaises(ValueError):
                client.Query("neural", lambda _: self.fail("method called for invalid input")).accept(body)
        q = client.Query("neural", prediction)
        q.accept(wire(row()))
        with self.assertRaises(ValueError):
            q.accept(wire(row(ordinal=1, token="b" * 32)))
        q.accept(wire({"schema": "neural067_end_v1", "token": "a" * 32}))
        with self.assertRaises(ValueError):
            q.accept(wire(row(ordinal=1)))

    def test_malformed_model_outputs_are_not_silently_repaired(self):
        for invalid in ([0] * 6, [True] * 7, [float("inf")] * 7, [float("nan")] * 7,
                        (0,) * 7, ["0"] * 7):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                client.Query("neural", lambda _: invalid).accept(wire(row()))

    def test_all_declared_blocks_interoperate_with_production_converse(self):
        blocks = total = 0
        end = time.monotonic() + 100
        outer = self
        for run, _, count in scorer.QUERY:
            for arm in scorer.ARMS:
                class Journal:
                    i = 0

                    def append(self, current, vector):
                        outer.assertEqual(current["ordinal"], self.i)
                        outer.assertEqual(vector, prediction(current["observation"]))
                        self.i += 1
                        return {"bytes": 160, "sha256": "0" * 64}

                journal = Journal()

                class Rows:
                    i = 0

                    def next(self):
                        outer.assertEqual(journal.i, self.i, "no next observation before commit")
                        if self.i == count:
                            return None
                        value = row(arm, self.i)
                        self.i += 1
                        del value["schema"]
                        return value

                class Stream:
                    def __init__(self):
                        self.client = client.Query(arm, prediction)
                        self.pending = self.client.ready()
                        self.finished = False

                    def line(self):
                        outer.assertIsNotNone(self.pending)
                        result, self.pending = self.pending, None
                        return result

                    def idle(self):
                        outer.assertIsNone(self.pending)

                    def send(self, body):
                        self.idle()
                        self.pending = self.client.accept(body)

                    def finish(self):
                        self.idle()
                        outer.assertTrue(self.client.closed)
                        self.finished = True

                stream = Stream()
                result = host.converse(stream, arm, Rows(), journal, end)
                self.assertEqual(result, {"rows": count, "token": "a" * 32})
                self.assertTrue(stream.finished)
                self.assertEqual(journal.i, count)
                blocks += 1
                total += count
        self.assertEqual((blocks, total), (56, 137960))

    def test_bundle_is_single_file_and_builder_does_not_run_method(self):
        method = b"raise RuntimeError('do not run while bundling')\n"
        self.assertIn(b"entry(_method", builder.bundle(method))
        method = b'''from __future__ import annotations
from dataclasses import dataclass
import pickle
@dataclass
class State:
    label: str
def fit(path, arm):
    assert str(path) == '/train/TRAIN.json' and arm == 'clock'
    return pickle.dumps(State('generated-state'))
def start(state, arm):
    assert pickle.loads(state) == State('generated-state') and arm == 'clock'
    return lambda observation: [0.0] * 7
'''
        program = builder.bundle(method)
        self.assertLessEqual(len(program), 1_048_576)
        out = io.BytesIO()
        stdout = io.TextIOWrapper(out, encoding="utf8")
        with patch.object(sys, "argv", ["program.py", "train", "--arm", "clock", "--train", "/train/TRAIN.json", "--state-stdout"]), patch.object(sys, "stdout", stdout):
            exec(compile(program, "program.py", "exec"), {"__name__": "__main__"})
        state_body = out.getvalue()[host_stream.STATE_HEADER:]
        self.assertTrue(state_body)
        # Files are restricted to this test's explicitly supplied owned temp root.
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as directory:
            state = Path(directory) / "state.bin"
            state.write_bytes(state_body)
            feed = io.TextIOWrapper(io.BytesIO(wire(row("clock")) + wire({"schema": "neural067_end_v1", "token": "a" * 32})), encoding="utf8")
            result = io.BytesIO()
            target = io.TextIOWrapper(result, encoding="utf8")
            with patch.object(sys, "argv", ["program.py", "predict", "--arm", "clock", "--state", str(state), "--protocol", "neural067_causal_v1"]), patch.object(sys, "stdin", feed), patch.object(sys, "stdout", target):
                exec(compile(program, "program.py", "exec"), {"__name__": "__main__"})
            frames = [json.loads(x) for x in result.getvalue().splitlines()]
            self.assertEqual([x["schema"] for x in frames], ["neural067_ready_v1", "neural067_action_v1", "neural067_stopped_v1"])
        with self.assertRaises(SyntaxError):
            builder.bundle(b"def invalid syntax")
        with self.assertRaises(ValueError):
            builder.bundle(b"#" + b"x" * 1_048_576)

    def test_exact_host_dependencies(self):
        manifest = json.loads((HERE / "SOURCE.json").read_text())
        for name, pin in manifest["dependencies"].items():
            body = (IMPLEMENTATIONS / name).read_bytes()
            self.assertEqual({"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}, pin)


if __name__ == "__main__":
    unittest.main()
