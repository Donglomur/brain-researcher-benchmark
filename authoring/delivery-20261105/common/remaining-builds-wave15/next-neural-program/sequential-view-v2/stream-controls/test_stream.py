"""Tiny opaque-byte transport controls with preventive cumulative write gates.

No NumPy, numerical interpretation, complete1.6MB phase fixture, or production
gather is executed. Private profile (3,1,2) exercises exactly the same transport.
"""
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(name, path, **bindings):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    module.__dict__.update(bindings)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


c = load("stream_control_common", HERE.parents[1] / "program/common.py")
s = load("stream_control_tested", HERE.parent / "program/stream.py", c=c)
PROFILE = s._Profile((3, 1, 2), (6,))
ORDER = ((1, 2), (0, 0), (1, 0), (0, 2), (0, 1), (1, 1))


class Guard:
    def __init__(self):
        self.write_limit = 40000  # parent prospectively reserved this whole pool
        self.write_reserved = 0
        self.write_actual = 0
        self.canonical_limit = 512 * 1024  # prospective parent transfer; prior costs carried
        self.canonical_reserved = 0
        self.canonical_actual = 0
        self.max_retained = 0
        self.managed_reads = 0
        self.managed_writes = 0
        self.short_pwrite = False
        self.corrupt_once = False
        self.corrupted = False
        self.original_write = os.write
        self.original_pwrite = os.pwrite

    def reserve_write(self, count):
        if type(count) is not int or count < 0 or self.write_reserved + count > self.write_limit:
            raise ValueError("preventive cumulative fixture write cap")
        self.write_reserved += count

    def canonical(self, count):
        if self.canonical_reserved + count > self.canonical_limit:
            raise ValueError("preventive cumulative canonical cap")
        self.canonical_reserved += count

    def _before_write(self, count):
        if self.write_actual + count > self.write_reserved or self.write_actual + count > self.write_limit:
            raise ValueError("physical write before full reservation")

    def write(self, fd, raw):
        self._before_write(len(raw))
        count = self.original_write(fd, raw)
        self.write_actual += count
        return count

    def pwrite(self, fd, raw, offset):
        if self.short_pwrite:
            raw = raw[:3]
        if self.corrupt_once and not self.corrupted and offset >= 128 and raw:
            raw = bytes([raw[0] ^ 1]) + bytes(raw[1:])
            self.corrupted = True
        self._before_write(len(raw))
        count = self.original_pwrite(fd, raw, offset)
        self.write_actual += count
        return count


GUARD = Guard()
ORIGINAL_HEADER = s._header


def metered_header(shape):
    GUARD.canonical(4096)  # reserve before any header serialization
    value = ORIGINAL_HEADER(shape)
    assert len(value) <= 4096
    GUARD.canonical_actual += len(value)
    return value


def wire(rows, version=1, literal=None):
    shape = (len(rows), 1, 2)
    if literal is None and version == 1:
        header = s._header(shape)
    else:
        GUARD.canonical(4096)
        text = literal if literal is not None else "{'descr': '<f4', 'fortran_order': False, 'shape': " + repr(shape) + ", }"
        body = text.encode("ascii")
        offset = 10 if version == 1 else 12
        padding = (-(offset + len(body) + 1)) % 64
        body += b" " * padding + b"\n"
        header = b"\x93NUMPY" + bytes([version, 0]) + len(body).to_bytes(offset - 8, "little") + body
        GUARD.canonical_actual += len(header)
    length = sum(map(len, rows))
    GUARD.canonical(length)
    payload = b"".join(rows)
    GUARD.canonical_actual += len(payload)
    return header + payload


def fixture(path, raw):
    # Reserve BEFORE file creation; writes are independently checked by patches.
    used = c.inventory(path.parent, 1024 * 1024, 100)[2]
    GUARD.max_retained = max(GUARD.max_retained, used)
    if used + ((len(raw) + 4095) // 4096) * 4096 + 16384 > 1024 * 1024:
        raise ValueError("preventive retained fixture allocation cap")
    GUARD.reserve_write(len(raw))
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    try:
        view = memoryview(raw)
        while view:
            count = os.write(fd, view)
            assert count > 0
            view = view[count:]
        os.fchmod(fd, 0o444)
    finally:
        os.close(fd)
    GUARD.max_retained = max(GUARD.max_retained, c.inventory(path.parent, 1024 * 1024, 100)[2])
    return c.pin(raw)


class Budget:
    def __init__(self, root):
        self.root = root
        self.reads = 0
        self.writes = 0
        self.expired = False
        self.capacity_denied = False

    def tick(self):
        if self.expired:
            raise ValueError("invented original deadline")

    def read(self, count):
        assert type(count) is int and count >= 0
        self.reads += count
        GUARD.managed_reads += count
        self.tick()

    def capacity(self, extra=0):
        self.tick()
        size = c.inventory(self.root, 1024 * 1024, 100)[2]
        GUARD.max_retained = max(GUARD.max_retained, size)
        if self.capacity_denied or size + extra > 1024 * 1024:
            raise ValueError("invented retained allocation cap")
        return size

    def write(self, count):
        self.capacity(count + 16384)
        GUARD.reserve_write(count)
        self.writes += count
        GUARD.managed_writes += count


def sources(root, budget):
    payloads = ((b"abcdefgh", b"ijklmnop", b"qrstuvwx"),
                (b"12345678", b"ABCDEFGH", b"QRSTUVWX"))
    descriptors = []
    for index, rows in enumerate(payloads):
        raw = wire(rows, version=index + 1)
        path = root / ("phase%d.npy" % index)
        pin = fixture(path, raw)
        descriptors.append(s._authenticate(path, pin, budget, PROFILE))
    return tuple(descriptors), payloads


class StreamControls(unittest.TestCase):
    def setUp(self):
        self.patches = (patch.object(s.os, "write", side_effect=GUARD.write),
                        patch.object(s.os, "pwrite", side_effect=GUARD.pwrite),
                        patch.object(s, "_header", side_effect=metered_header))
        for item in self.patches:
            item.start()

    def tearDown(self):
        GUARD.short_pwrite = False
        GUARD.corrupt_once = False
        for item in reversed(self.patches):
            item.stop()

    def test_01_npy1_npy2_reorder_short_writes_and_exact_read_formula(self):
        with tempfile.TemporaryDirectory(dir=HERE, prefix="tiny-stream-") as temp:
            root = Path(temp); budget = Budget(root)
            descriptors, payloads = sources(root, budget)
            before_reads = budget.reads
            GUARD.short_pwrite = True
            output = root / "gathered.npy"
            pin = s._gather(output, ORDER, descriptors, budget, PROFILE)
            budget.capacity()
            GUARD.short_pwrite = False
            self.assertEqual(pin["bytes"], 176)
            expected = s._header((6, 1, 2)) + b"".join(payloads[source][row] for source, row in ORDER)
            # Independent tiny expected bytes only, never a production array.
            GUARD.canonical(len(expected)); GUARD.canonical_actual += len(expected)
            self.assertEqual(pin, c.pin(expected))
            self.assertEqual(budget.reads - before_reads, sum(d.pin.bytes + 1 for d in descriptors) + pin["bytes"] + 1)
            self.assertEqual(budget.writes, pin["bytes"])
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o444)
            opaque_stamp = s.opaque_hash(output, pin, budget)
            self.assertEqual(opaque_stamp, c.stamp(output.stat()))
            self.assertEqual(descriptors[0].shape, (3, 1, 2))
            self.assertEqual(descriptors[0].offset, descriptors[1].offset)

    def test_02_production_wrappers_and_full_bijection_refuse_before_write(self):
        self.assertEqual(s.output_size(21200), 339200128)
        self.assertEqual(s.output_size(400), 6400128)
        self.assertIs(s.inspect, s.authenticate)
        with tempfile.TemporaryDirectory(dir=HERE, prefix="tiny-layout-") as temp:
            root = Path(temp); budget = Budget(root)
            descriptors, _ = sources(root, budget)
            with self.assertRaises(ValueError):
                s.authenticate(descriptors[0].path, descriptors[0].pin, budget)
            cases = (ORDER[:-1], (ORDER[0],) + ORDER[0:5], ((True, 2),) + ORDER[1:], ((2, 0),) + ORDER[1:])
            for order in cases:
                with self.assertRaises(ValueError):
                    s._gather(root / "absent.npy", order, descriptors, budget, PROFILE)
                self.assertFalse((root / "absent.npy").exists())
            with self.assertRaises(ValueError):
                s._gather(root / "absent.npy", ORDER, descriptors + descriptors[:1], budget, PROFILE)
            with self.assertRaises(ValueError):
                s.gather(root / "absent.npy", ORDER, descriptors, budget)
            self.assertEqual(budget.writes, 0)

    def test_03_strict_headers_extent_and_authentication_hash(self):
        literals = (
            "{'descr': '>f4', 'fortran_order': False, 'shape': (3,1,2)}",
            "{'descr': '<f4', 'fortran_order': True, 'shape': (3,1,2)}",
            "{'descr': '<f4', 'fortran_order': False, 'shape': (3,2,1)}",
            "{'descr': '<f4', 'shape': (3,1,2), 'shape': (3,1,2)}",
            "{'descr': '<f4', 'fortran_order': False, 'shape': (True,1,2)}",
        )
        with tempfile.TemporaryDirectory(dir=HERE, prefix="tiny-header-") as temp:
            root = Path(temp); budget = Budget(root)
            for ordinal, literal in enumerate(literals):
                raw = wire((b"12345678",) * 3, literal=literal)
                path = root / (str(ordinal) + ".npy")
                pin = fixture(path, raw)
                with self.assertRaises(ValueError):
                    s._authenticate(path, pin, budget, PROFILE)
            raw = wire((b"12345678",) * 3)
            for name, bad in (("truncated.npy", raw[:-1]), ("trailing.npy", raw + b"x")):
                GUARD.canonical(len(bad)); GUARD.canonical_actual += len(bad)
                path = root / name; pin = fixture(path, bad)
                with self.assertRaisesRegex(ValueError, "full phase byte extent"):
                    s._authenticate(path, pin, budget, PROFILE)
            path = root / "wronghash.npy"; pin = fixture(path, raw)
            with self.assertRaisesRegex(ValueError, "full source SHA256"):
                s._authenticate(path, dict(bytes=pin["bytes"], sha256="0" * 64), budget, PROFILE)

    def test_04_output_byte_corruption_is_detected_with_costs_retained(self):
        with tempfile.TemporaryDirectory(dir=HERE, prefix="tiny-corruption-") as temp:
            root = Path(temp); budget = Budget(root)
            descriptors, _ = sources(root, budget)
            GUARD.corrupt_once = True; GUARD.corrupted = False
            output = root / "failed.npy"
            with self.assertRaisesRegex(ValueError, "source bytes at each ordered output row"):
                s._gather(output, ORDER, descriptors, budget, PROFILE)
            self.assertTrue(GUARD.corrupted)
            self.assertTrue(output.exists())
            self.assertEqual(budget.writes, 176)
            budget.capacity()

    def test_05_capacity_and_cumulative_write_guards_precede_creation(self):
        with tempfile.TemporaryDirectory(dir=HERE, prefix="tiny-budget-") as temp:
            root = Path(temp); budget = Budget(root)
            descriptors, _ = sources(root, budget)
            output = root / "never-created.npy"
            budget.capacity_denied = True
            with self.assertRaisesRegex(ValueError, "retained allocation cap"):
                s._gather(output, ORDER, descriptors, budget, PROFILE)
            self.assertFalse(output.exists())
            budget.capacity_denied = False
            old_limit = GUARD.write_limit
            GUARD.write_limit = GUARD.write_reserved
            try:
                with self.assertRaisesRegex(ValueError, "cumulative fixture write cap"):
                    s._gather(output, ORDER, descriptors, budget, PROFILE)
            finally:
                GUARD.write_limit = old_limit
            self.assertFalse(output.exists())
            self.assertEqual(budget.writes, 0)

    def test_06_deadline_after_final_read_and_independent_descriptor_cleanup(self):
        with tempfile.TemporaryDirectory(dir=HERE, prefix="tiny-deadline-") as temp:
            root = Path(temp); budget = Budget(root)
            pin = fixture(root / "opaque", b"abcd")
            read = os.read
            def delayed(fd, count):
                value = read(fd, count)
                if value:
                    budget.expired = True
                return value
            with patch.object(s.os, "read", side_effect=delayed):
                with self.assertRaisesRegex(ValueError, "original deadline"):
                    s.opaque_hash(root / "opaque", pin, budget)
            self.assertEqual(budget.reads, 5)
        closed = []
        def close(fd):
            closed.append(fd)
            if fd == 1:
                raise OSError("invented close failure")
        with patch.object(s.os, "close", side_effect=close):
            with self.assertRaises(OSError):
                s._close_all(1, 2)
            self.assertEqual(closed, [1, 2])
            error = ValueError("primary failure")
            try:
                try:
                    raise error
                finally:
                    s._close_all(1, 2)
            except ValueError as caught:
                self.assertIs(caught, error)
                self.assertTrue(any("close failure" in note for note in caught.__notes__))


if __name__ == "__main__":
    unittest.main()
