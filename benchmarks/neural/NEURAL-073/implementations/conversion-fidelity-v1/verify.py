"""Independent, standard-library NIfTI/canonical value and sform check.

This does not import the converter or NiBabel and does not qualify a corpus.
Only explicit pinned inputs are opened. No targets, labels or model execution.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import struct


class FidelityError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise FidelityError(message)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def strict_json(body):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON field")
            result[key] = value
        return result
    def nonfinite(_):
        raise FidelityError("nonfinite JSON number")
    return json.loads(body, object_pairs_hook=object_pairs, parse_constant=nonfinite)


def read_pinned(path, expected_sha256, cap):
    """Non-following descriptor walk; bounded regular-file read and identity pin."""
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts, "absolute path required")
    require(type(cap) is int and cap > 0, "positive read cap required")
    require(type(expected_sha256) is str and len(expected_sha256) == 64
            and all(c in "0123456789abcdef" for c in expected_sha256), "SHA256 pin required")
    fds = [os.open("/", os.O_RDONLY | os.O_DIRECTORY)]
    try:
        for part in path.parts[1:-1]:
            fds.append(os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                               dir_fd=fds[-1]))
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fds[-1])
        fds.append(fd)
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and 0 < before.st_size <= cap, "bounded single-link regular file required")
        parts, remaining = [], before.st_size
        while remaining:
            part = os.read(fd, min(65536, remaining))
            require(bool(part), "short input")
            parts.append(part)
            remaining -= len(part)
        after = os.fstat(fd)
        require((before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_size, after.st_mtime_ns, after.st_ctime_ns), "input changed")
        body = b"".join(parts)
        require(digest(body) == expected_sha256, "input digest mismatch")
        return body
    finally:
        for fd in reversed(fds):
            os.close(fd)


# NIfTI scalar types whose byte representation can be read by struct.
TYPES = {2: "B", 4: "h", 8: "i", 16: "f", 64: "d", 256: "b",
         512: "H", 768: "I", 1024: "q", 1280: "Q"}
UNITS = {0: "unknown", 1: "meter", 2: "mm", 3: "micron"}


def parse_original(original, max_expanded_bytes):
    require(type(original) is bytes, "original bytes required")
    require(type(max_expanded_bytes) is int and max_expanded_bytes >= 544,
            "explicit expanded-file cap required")
    compressed = original.startswith(b"\x1f\x8b")
    if compressed:
        with gzip.GzipFile(fileobj=io.BytesIO(original)) as stream:
            body = stream.read(max_expanded_bytes + 1)
    else:
        body = original
    require(len(body) <= max_expanded_bytes, "expanded-file cap exceeded")
    require(len(body) >= 352, "complete NIfTI header required")
    endian = "<"
    size = struct.unpack_from("<i", body)[0]
    if size not in (348, 540):
        endian = ">"
        size = struct.unpack_from(">i", body)[0]
    require(size in (348, 540) and len(body) >= size + 4, "NIfTI-1/2 required")
    def read(fmt, offset):
        return struct.unpack_from(endian + fmt, body, offset)
    if size == 348:
        require(body[344:348] == b"n+1\0", "single-file NIfTI-1 required")
        dims = read("8h", 40)
        datatype, bitpix = read("2h", 70)
        offset = read("f", 108)[0]
        slope, intercept = read("2f", 112)
        unit_code = body[123] & 7
        qcode, scode = read("2h", 252)
        sform = list(read("12f", 280)) + [0., 0., 0., 1.]
    else:
        require(body[4:12] == b"n+2\0\r\n\x1a\n", "single-file NIfTI-2 required")
        dims = read("8q", 16)
        datatype, bitpix = read("2h", 12)
        offset = read("q", 168)[0]
        slope, intercept = read("2d", 176)
        unit_code = read("i", 500)[0] & 7
        qcode, scode = read("2i", 344)
        sform = list(read("12d", 400)) + [0., 0., 0., 1.]
    require(dims[0] == 3 and min(dims[1:4]) >= 4 and math.prod(dims[1:4]) >= 256,
            "complete three-dimensional task map required")
    require(datatype in TYPES and bitpix == 8 * struct.calcsize(TYPES[datatype]),
            "supported real scalar datatype/bitpix required")
    require(math.isfinite(offset) and int(offset) == offset and offset >= size + 4,
            "integral payload offset beyond header required")
    offset = int(offset)
    shape = tuple(dims[1:4])
    width = bitpix // 8
    require(offset + math.prod(shape) * width <= len(body), "complete voxel payload required")
    marker = body[size:size + 4]
    require(marker[1:] == b"\0\0\0", "reserved extension marker bytes")
    if marker[0]:
        require(offset > size + 4, "extension flag without record")
        pos = size + 4
        while pos < offset:
            require(pos + 8 <= offset, "short extension")
            extent = read("i", pos)[0]
            require(extent >= 16 and extent % 16 == 0 and pos + extent <= offset,
                    "invalid extension extent")
            pos += extent
    require(unit_code in UNITS, "recognized spatial units required")
    # This version deliberately does not reconstruct quaternion rotations.
    require(0 < scode <= 5, "independent sform profile requires a coded sform")
    require(all(math.isfinite(v) for v in sform), "finite sform required")
    a, b, c, _, d, e, f, _, g, h, i, *_ = sform
    det = a * (e*i-f*h) - b * (d*i-f*g) + c * (d*h-e*g)
    require(math.isfinite(det) and det != 0, "nonsingular sform required")
    if slope == 0 or not math.isfinite(slope):
        slope, intercept = 1., 0.
    require(math.isfinite(intercept), "finite effective intercept required")
    return body, {"shape": shape, "datatype": datatype, "width": width,
                  "endian": endian, "offset": offset, "slope": slope,
                  "intercept": intercept, "sform": sform, "sform_code": scode,
                  "qform_code": qcode, "spatial_units": UNITS[unit_code],
                  "format": "NIfTI-1" if size == 348 else "NIfTI-2", "gzip": compressed}


def verify_pair(original, canonical, evidence, *, max_expanded_bytes):
    """Check every voxel against independent file-order/float64 arithmetic.

    Errors never return a passing receipt. This verifies one explicit pair;
    source authenticity, registration, cohort completeness and orientation-axis
    derivation are deliberately outside the checked scope.
    """
    require(type(canonical) is bytes and type(evidence) is dict, "pair/evidence required")
    body, meta = parse_original(original, max_expanded_bytes)
    nx, ny, nz = meta["shape"]
    require(len(canonical) == nx * ny * nz * 8, "complete canonical extent required")
    require(evidence.get("original_sha256") == digest(original)
            and evidence.get("original_bytes") == len(original), "original evidence binding")
    require(evidence.get("canonical_sha256") == digest(canonical)
            and evidence.get("canonical_bytes") == len(canonical), "canonical evidence binding")
    require(evidence.get("geometry", {}).get("shape") == list(meta["shape"])
            and evidence.get("geometry", {}).get("affine") == meta["sform"], "shape/sform mismatch")
    for field in ("format", "gzip", "spatial_units", "sform_code", "qform_code", "sform",
                  "slope", "intercept"):
        require(evidence.get(field) == meta[field], "conversion metadata mismatch: " + field)
    require(evidence.get("selected_affine") == "sform"
            and evidence.get("unit_conversion_performed") is False, "native sform/units required")
    require(evidence.get("expanded_bytes") == len(body), "expanded extent mismatch")
    slope, intercept = meta["slope"], meta["intercept"]
    scalar = struct.Struct(meta["endian"] + TYPES[meta["datatype"]])
    for x in range(nx):
        for y in range(ny):
            for z in range(nz):
                file_index = x + nx * (y + ny * z)
                value = scalar.unpack_from(body, meta["offset"] + meta["width"] * file_index)[0]
                expected = float(value)
                require(math.isfinite(expected), "finite stored voxel required")
                if isinstance(value, int):
                    require(int(expected) == value, "integer not exactly representable in float64")
                # Identity operations are skipped, as in the declared decoder;
                # adding +0 would otherwise erase a stored negative zero.
                if slope != 1:
                    expected *= slope
                if intercept != 0:
                    expected += intercept
                require(math.isfinite(expected), "finite float64 scaling profile required")
                start = ((x * ny + y) * nz + z) * 8
                require(canonical[start:start+8] == struct.pack("<d", expected),
                        "canonical value/order mismatch at voxel " + str((x, y, z)))
    return {"schema": "n073_independent_map_fidelity_v1", "passed": True,
            "original_sha256": digest(original), "canonical_sha256": digest(canonical),
            "voxels_checked": nx * ny * nz, "shape": list(meta["shape"]),
            "format": meta["format"], "spatial_units": meta["spatial_units"],
            "scope": "all_voxel_values_file_order_scaling_coded_sform_and_units",
            "corpus_qualified": False, "scientific_qualification": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("original", "canonical", "evidence"):
        parser.add_argument("--" + name, type=Path, required=True)
        parser.add_argument("--" + name + "-sha256", required=True)
        parser.add_argument("--" + name + "-cap-bytes", type=int, required=True)
    parser.add_argument("--max-expanded-bytes", type=int, required=True)
    args = parser.parse_args()
    inputs = {name: read_pinned(getattr(args, name), getattr(args, name + "_sha256"),
                               getattr(args, name + "_cap_bytes"))
              for name in ("original", "canonical", "evidence")}
    receipt = verify_pair(inputs["original"], inputs["canonical"], strict_json(inputs["evidence"]),
                          max_expanded_bytes=args.max_expanded_bytes)
    receipt["conversion_evidence_sha256"] = digest(inputs["evidence"])
    receipt["verifier_sha256"] = digest(Path(__file__).read_bytes())
    print(json.dumps(receipt, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
