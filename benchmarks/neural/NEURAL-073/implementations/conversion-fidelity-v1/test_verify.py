"""Generated software controls; no authentic observations or model trials."""
from __future__ import annotations

import argparse
import copy
import gzip
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("n073_fidelity", HERE / "verify.py")
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


def fixture(version=1, endian="<", slope=2., intercept=-3., units=2, code=4,
            signed_zero=False, compressed=False):
    """Hand encode a non-cubic image and expected canonical coordinate sequence."""
    shape = (4, 8, 8)
    formats = {4: "h", 16: "f", 64: "d", 1024: "q"}
    scalar = formats[code]
    width = struct.calcsize(scalar)
    size = 352 if version == 1 else 544
    header = bytearray(size)
    def put(offset, fmt, *values):
        struct.pack_into(endian + fmt, header, offset, *values)
    affine = [-2., .25, 0., 10., 0., 3., 0., 20., 0., 0., 4., 30., 0., 0., 0., 1.]
    if version == 1:
        put(0, "i", 348)
        put(40, "8h", 3, *shape, 1, 1, 1, 1)
        put(70, "2h", code, width*8)
        put(76, "8f", 1., 2., 3., 4., 1., 1., 1., 1.)
        put(108, "3f", 352., slope, intercept)
        put(123, "B", units)
        put(252, "2h", 0, 2)
        put(280, "12f", *affine[:12])
        header[344:348] = b"n+1\0"
    else:
        put(0, "i", 540)
        header[4:12] = b"n+2\0\r\n\x1a\n"
        put(12, "2h", code, width*8)
        put(16, "8q", 3, *shape, 1, 1, 1, 1)
        put(104, "8d", 1., 2., 3., 4., 1., 1., 1., 1.)
        put(168, "q", 544)
        put(176, "2d", slope, intercept)
        put(344, "2i", 0, 2)
        put(400, "12d", *affine[:12])
        put(500, "i", units)
    values = [i - 80 for i in range(256)]
    if signed_zero:
        values[0] = -0.
    original = bytes(header) + struct.pack(endian + "256" + scalar, *values)
    expanded_bytes = len(original)
    if compressed:
        original = gzip.compress(original, mtime=0)
    effective_slope, effective_intercept = (1., 0.) if slope == 0 else (slope, intercept)
    def expected(x, y, z):
        value = float(values[x + 4*y + 32*z])
        if effective_slope != 1:
            value *= effective_slope
        if effective_intercept != 0:
            value += effective_intercept
        return value
    canonical = b"".join(struct.pack("<d", expected(x, y, z))
                         for x in range(4) for y in range(8) for z in range(8))
    evidence = {"original_sha256": verify.digest(original), "original_bytes": len(original),
                "canonical_sha256": verify.digest(canonical), "canonical_bytes": len(canonical),
                "geometry": {"shape": list(shape), "affine": affine, "orientation": ["L", "A", "S"]},
                "format": "NIfTI-" + str(version), "gzip": compressed,
                "expanded_bytes": expanded_bytes, "sform_code": 2, "qform_code": 0,
                "sform": affine, "spatial_units": {0: "unknown", 1: "meter", 2: "mm", 3: "micron"}[units],
                "selected_affine": "sform", "unit_conversion_performed": False,
                "slope": effective_slope, "intercept": effective_intercept}
    return original, canonical, evidence


class Checks(unittest.TestCase):
    def check(self, pair):
        return verify.verify_pair(*pair, max_expanded_bytes=16384)

    def test_versions_endianness_compression_units_and_scaling(self):
        for version in (1, 2):
            for endian in ("<", ">"):
                for compressed in (False, True):
                    for units in (0, 1, 2, 3):
                        with self.subTest(version=version, endian=endian, compressed=compressed, units=units):
                            report = self.check(fixture(version, endian, -2., 7., units, compressed=compressed))
                            self.assertEqual(report["voxels_checked"], 256)
                            self.assertFalse(report["scientific_qualification"])

    def test_scalar_types_and_disabled_scaling(self):
        for code in (4, 16, 64, 1024):
            self.check(fixture(code=code))
            self.check(fixture(code=code, slope=0, intercept=100))

    def test_signed_zero_and_tampering_with_updated_hash(self):
        original, canonical, evidence = fixture(code=16, slope=1, intercept=0, signed_zero=True)
        self.check((original, canonical, evidence))
        tampered = b"\0"*8 + canonical[8:]
        evidence["canonical_sha256"] = verify.digest(tampered)
        with self.assertRaisesRegex(verify.FidelityError, "value/order mismatch"):
            self.check((original, tampered, evidence))

    def test_incorrect_order_even_when_hash_is_self_consistent(self):
        original, canonical, evidence = fixture()
        tampered = b"".join(struct.pack("<d", 2*(i-80)-3) for i in range(256))
        evidence["canonical_sha256"] = verify.digest(tampered)
        with self.assertRaisesRegex(verify.FidelityError, "value/order mismatch"):
            self.check((original, tampered, evidence))

    def test_unit_and_affine_and_metadata_changes(self):
        for field, value in (("spatial_units", "meter"), ("sform_code", 1), ("slope", 1.),
                             ("unit_conversion_performed", True), ("expanded_bytes", 1)):
            original, canonical, evidence = fixture()
            evidence[field] = value
            with self.subTest(field=field), self.assertRaises(verify.FidelityError):
                self.check((original, canonical, evidence))
        original, canonical, evidence = fixture()
        evidence["geometry"] = copy.deepcopy(evidence["geometry"])
        evidence["geometry"]["affine"][3] += 1
        with self.assertRaisesRegex(verify.FidelityError, "shape/sform"):
            self.check((original, canonical, evidence))

    def test_original_hash_binding(self):
        original, canonical, evidence = fixture()
        evidence["original_sha256"] = "0"*64
        with self.assertRaisesRegex(verify.FidelityError, "original evidence"):
            self.check((original, canonical, evidence))

    def test_truncation_offsets_extensions_and_unsupported_sform(self):
        original, canonical, evidence = fixture()
        for offset, fmt, value in ((108, "f", 0), (108, "f", 352.5),
                                    (254, "h", 0), (72, "h", 8), (40, "h", 4)):
            changed = bytearray(original)
            struct.pack_into("<" + fmt, changed, offset, value)
            with self.subTest(offset=offset), self.assertRaises(verify.FidelityError):
                verify.parse_original(bytes(changed), 16384)
        with self.assertRaises(verify.FidelityError):
            verify.parse_original(original[:-1], 16384)
        changed = bytearray(original)
        changed[348] = 1
        with self.assertRaises(verify.FidelityError):
            verify.parse_original(bytes(changed), 16384)
        extended = bytearray(original[:352]) + struct.pack("<ii8s", 16, 6, b"fixture\0") + original[352:]
        extended[348] = 1
        struct.pack_into("<f", extended, 108, 368)
        evidence.update(original_bytes=len(extended), original_sha256=verify.digest(extended),
                        expanded_bytes=len(extended))
        self.check((bytes(extended), canonical, evidence))

    def test_nonfinite_and_lossy_integer_refused(self):
        for code, fmt, value in ((64, "d", float("nan")), (1024, "q", 2**53+1)):
            original, canonical, evidence = fixture(code=code, slope=1, intercept=0)
            changed = bytearray(original)
            struct.pack_into("<" + fmt, changed, 352, value)
            evidence["original_sha256"] = verify.digest(changed)
            with self.assertRaises(verify.FidelityError):
                self.check((bytes(changed), canonical, evidence))

    def test_gzip_bound_and_crc(self):
        original, canonical, evidence = fixture(compressed=True)
        with self.assertRaises(verify.FidelityError):
            verify.verify_pair(original, canonical, evidence, max_expanded_bytes=544)
        changed = original[:-8] + bytes([original[-8] ^ 1]) + original[-7:]
        with self.assertRaises((gzip.BadGzipFile, EOFError)):
            verify.parse_original(changed, 16384)

    def test_cli_and_pinned_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            pair = fixture(version=2, endian=">", compressed=True)
            bodies = dict(original=pair[0], canonical=pair[1],
                          evidence=json.dumps(pair[2], allow_nan=False).encode())
            command = [sys.executable, "-I", "-S", "-B", str(HERE/"verify.py")]
            for name, body in bodies.items():
                path = root/name
                path.write_bytes(body)
                command += ["--"+name, str(path), "--"+name+"-sha256", verify.digest(body),
                            "--"+name+"-cap-bytes", str(len(body))]
            command += ["--max-expanded-bytes", "16384"]
            result = subprocess.run(command, capture_output=True, check=True, text=True)
            self.assertTrue(json.loads(result.stdout)["passed"])
            with self.assertRaises(verify.FidelityError):
                verify.read_pinned(root/"original", "0"*64, 16384)
            with self.assertRaises(verify.FidelityError):
                verify.read_pinned(root/"original", verify.digest(pair[0]), 1)
            (root/"linked").symlink_to(root/"original")
            with self.assertRaises(OSError):
                verify.read_pinned(root/"linked", verify.digest(pair[0]), 16384)

    def test_duplicate_json_refused(self):
        with self.assertRaises(verify.FidelityError):
            verify.strict_json(b'{"a":1,"a":2}')


def check_prior_converter_fixtures(root):
    """Optional compatibility check of explicit existing invented converter output."""
    original_root = root/"invented-originals"
    corpus = root/"complete-invented-corpus"
    inventory = verify.strict_json((corpus/"INVENTORY.json").read_bytes())
    rows = inventory["records"]
    if len(rows) != 6 or {r["record_id"] for r in rows} != {"invented:"+str(i) for i in range(6)}:
        raise AssertionError("only the six invented converter fixtures are permitted")
    for row in rows:
        name = verify.digest(row["record_id"].encode())
        # The frozen converter generated six identical originals, then mutated
        # some files for negative controls. The unchanged first original is a
        # valid source for every receipt only if its full digest still agrees.
        original = (original_root/"0.nii").read_bytes()
        canonical = (corpus/"canonical"/(name+".f64")).read_bytes()
        evidence = verify.strict_json((corpus/"conversion"/(name+".json")).read_bytes())
        verify.verify_pair(original, canonical, evidence, max_expanded_bytes=16384)
    return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prior-generated-fixtures", type=Path)
    args = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    if not result.wasSuccessful():
        raise SystemExit(1)
    if args.prior_generated_fixtures:
        print(json.dumps({"prior_generated_converter_pairs_checked":
                          check_prior_converter_fixtures(args.prior_generated_fixtures),
                          "authentic_data_reads": 0, "scientific_qualification": False}, sort_keys=True))
