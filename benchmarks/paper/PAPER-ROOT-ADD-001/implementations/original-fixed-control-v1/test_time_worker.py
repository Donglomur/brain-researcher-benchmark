"""Generated in-memory controls only; never launch a worker process."""

import ast
import importlib.util
import io
from pathlib import Path
import struct
import unittest

import numpy as np


PATH = Path(__file__).with_name("time_worker.py")
SPEC = importlib.util.spec_from_file_location("language_fixed_time_control_under_test", PATH)
W = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(W)


def frame(times):
    return struct.pack("<8sQ", W.MAGIC, len(times)) + b"".join(struct.pack("<q", item) for item in times)


class TimeWorkerTests(unittest.TestCase):
    def test_full_valid_domain_has_bit_exact_dyadic_float64_outputs(self):
        times = tuple(range(W.MAX_COUNT))
        stdin = io.BytesIO(frame(times))
        stdout, stderr = io.BytesIO(), io.BytesIO()
        self.assertEqual(W.run(stdin, stdout, stderr), 0)
        raw = stdout.getvalue()
        values = np.load(io.BytesIO(raw), allow_pickle=False)
        expected = np.asarray([(value % 17 - 8) / 8 for value in times], dtype="<f8").reshape(-1, 1)
        self.assertEqual(values.shape, (W.MAX_COUNT, 1))
        self.assertEqual(values.dtype.str, "<f8")
        self.assertEqual(values.tobytes(order="C"), expected.tobytes(order="C"))
        self.assertEqual(raw[W.NPY_HEADER_BYTES:], expected.tobytes(order="C"))
        self.assertEqual(len(raw), W.MAX_OUTPUT_BYTES)
        self.assertEqual(len(stdin.getvalue()), W.MAX_FRAME_BYTES)
        self.assertEqual(stderr.getvalue(), b"")

    def test_canonical_npy_header_and_smallest_frame(self):
        times = (0, W.MAX_TIME)
        self.assertEqual(W.read_frame(io.BytesIO(frame(times))), times)
        raw = W.encode_prediction(times)
        self.assertEqual(raw[:8], b"\x93NUMPY\x01\x00")
        self.assertEqual(struct.unpack("<H", raw[8:10]), (118,))
        self.assertEqual(raw[127:128], b"\n")
        self.assertEqual(ast.literal_eval(raw[10:128].decode("ascii")), {
            "descr": "<f8", "fortran_order": False, "shape": (2, 1)})
        self.assertEqual(len(raw), 144)

    def test_invalid_count_or_magic_rejected_before_payload_read(self):
        class HeaderOnly:
            def __init__(self, header):
                self.header = header
                self.calls = 0
            def read(self, requested):
                self.calls += 1
                if self.calls != 1 or requested != 16:
                    raise AssertionError("invalid header must not admit a payload read")
                return self.header
        for count in (0, 1, W.MAX_COUNT + 1, 2**64 - 1):
            with self.subTest(count=count), self.assertRaises(W.InvalidInput):
                W.read_frame(HeaderOnly(struct.pack("<8sQ", W.MAGIC, count)))
        with self.assertRaises(W.InvalidInput):
            W.read_frame(HeaderOnly(struct.pack("<8sQ", b"WRONGMAG", 2)))

    def test_invalid_time_domain_duplicates_or_order_rejected(self):
        for times in ((-1, 1), (0, W.MAX_TIME + 1), (0, 0), (3, 2), (-(2**63), 1), (0, 2**63-1)):
            with self.subTest(times=times), self.assertRaises(W.InvalidInput):
                W.read_frame(io.BytesIO(frame(times)))

    def test_truncation_and_trailing_content_are_rejected(self):
        raw = frame((0, 10))
        for body in (b"", raw[:15], raw[:-1], raw + b"x", raw + b"\x00" * 400):
            with self.subTest(size=len(body)), self.assertRaises(W.InvalidInput):
                W.read_frame(io.BytesIO(body))

    def test_bounded_reads_and_one_byte_eof_probe(self):
        class Recorded(io.BytesIO):
            def __init__(self, raw):
                super().__init__(raw)
                self.requests = []
            def read(self, requested=-1):
                self.requests.append(requested)
                if not 0 < requested <= W.READ_CHUNK_BYTES:
                    raise AssertionError("unbounded read")
                return super().read(requested)
        stream = Recorded(frame(tuple(range(10000))) + b"extra")
        with self.assertRaises(W.InvalidInput):
            W.read_frame(stream)
        self.assertEqual(stream.requests[-1], 1)
        self.assertEqual(stream.tell(), 16 + 80000 + 1)

    def test_forged_read_return_types_and_extents_rejected(self):
        class Bad:
            def __init__(self, result):
                self.result = result
            def read(self, requested):
                return self.result
        for bad in (None, bytearray(16), "x" * 16, b"x" * 17):
            with self.subTest(kind=type(bad).__name__), self.assertRaises(W.InvalidInput):
                W.read_frame(Bad(bad))

    def test_pure_encoder_revalidates_concrete_tuple_and_integer_values(self):
        def forbidden():
            raise AssertionError("arbitrary iterator consumed")
            yield 0
        for value in (forbidden(), [0, 1], (), (0,), (False, 1), (0, 1.0), (2, 1), (-1, 2)):
            with self.subTest(kind=type(value).__name__), self.assertRaises(W.InvalidInput):
                W.encode_prediction(value)

    def test_failure_is_bounded_and_has_no_stdout(self):
        stdout, stderr = io.BytesIO(), io.BytesIO()
        self.assertEqual(W.run(io.BytesIO(frame((1, 1))), stdout, stderr), 2)
        self.assertEqual(stdout.getvalue(), b"")
        self.assertEqual(stderr.getvalue(), W.FAILURE_STDERR)
        self.assertLessEqual(len(stderr.getvalue()), 64)

    def test_short_reads_and_short_writes_preserve_exact_bytes(self):
        class ShortRead(io.BytesIO):
            def read(self, requested=-1):
                return super().read(min(requested, 3))
        class ShortWrite(io.BytesIO):
            def write(self, raw):
                return super().write(raw[:5])
        times = (0, 8, 16, 17, 144110)
        stdout, stderr = ShortWrite(), io.BytesIO()
        self.assertEqual(W.run(ShortRead(frame(times)), stdout, stderr), 0)
        self.assertEqual(stdout.getvalue(), W.encode_prediction(times))
        self.assertEqual(stderr.getvalue(), b"")

    def test_worker_imports_only_stdlib_and_contains_no_file_or_model_access(self):
        tree = ast.parse(PATH.read_text())
        imports = [item.name for node in ast.walk(tree) if isinstance(node, ast.Import) for item in node.names]
        self.assertEqual(imports, ["struct", "sys"])
        self.assertFalse(any(isinstance(node, ast.ImportFrom) for node in ast.walk(tree)))
        forbidden = {"open", "exec", "eval", "compile", "__import__"}
        self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                             and node.func.id in forbidden for node in ast.walk(tree)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
