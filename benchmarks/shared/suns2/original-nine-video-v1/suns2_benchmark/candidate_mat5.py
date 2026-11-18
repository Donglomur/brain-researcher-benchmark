"""Bounded MAT5 Masks-only reader for candidate-produced files.

Adapted from the reviewed SUNS2 numeric-source preflight. Candidate byte/cell
limits are interface resources, not original biological population limits.
No object deserialization, HDF5 access or author-code execution is supported.
"""
import io
import math
import struct
import zlib

from .constants import MASK_HEIGHT, MASK_WIDTH, MAX_INSTANCES

MAX_MAT_BYTES = 16 * 1024 * 1024
MAX_EXPANDED_BYTES = 16 * 1024 * 1024
CLASS_TYPES = {6: 9, 7: 7, 8: 1, 9: 2, 10: 3, 11: 4, 12: 5, 13: 6, 14: 12, 15: 13}
MI_ITEMSIZE = {1: 1, 2: 1, 3: 2, 4: 2, 5: 4, 6: 4, 7: 4, 9: 8, 12: 8, 13: 8}


class CandidateMATError(ValueError):
    """A file is outside the admitted Masks-only MAT5 interface."""


def _need(ok, message):
    if not ok:
        raise CandidateMATError(message)


def _element(data, offset, endian, *, compressed_top=False):
    _need(offset + 8 <= len(data), "truncated MAT tag")
    first = struct.unpack_from(endian + "I", data, offset)[0]
    if first >> 16:
        kind, size = struct.unpack_from(endian + "HH", data, offset)
        _need(1 <= size <= 4, "invalid small MAT element")
        return kind, data[offset + 4:offset + 4 + size], offset + 8
    kind, size = first, struct.unpack_from(endian + "I", data, offset + 4)[0]
    end = offset + 8 + size
    _need(end <= len(data), "MAT element exceeds source extent")
    # MATLAB miCOMPRESSED top-level records are not padded to eight bytes.
    next_offset = end if compressed_top and kind == 15 else offset + 8 + ((size + 7) // 8) * 8
    _need(next_offset <= len(data), "truncated MAT padding")
    return kind, data[offset + 8:end], next_offset


def _inflate(payload, limit):
    _need(limit >= 0, "MAT expansion allowance exhausted")
    try:
        decoder = zlib.decompressobj()
        result = decoder.decompress(payload, limit + 1)
    except zlib.error as exc:
        raise CandidateMATError("invalid compressed MAT stream") from exc
    _need(len(result) <= limit, "MAT expanded-byte cap exceeded")
    _need(decoder.eof and not decoder.unconsumed_tail and not decoder.unused_data,
          "incomplete or trailing compressed MAT stream")
    return result


def _matrix_header(payload, endian, expected_variable):
    pos = 0
    kind, flags, pos = _element(payload, pos, endian)
    _need(kind == 6 and len(flags) == 8, "MAT flags must be uint32[2]")
    flags0, flags1 = struct.unpack(endian + "II", flags)
    cls = flags0 & 0xff
    _need(cls in CLASS_TYPES, "only dense numeric/logical MAT arrays are admitted")
    _need(not flags0 & 0x800, "complex Masks are not admitted")
    _need(not flags0 & ~0x6ff and flags1 == 0, "unsupported MAT array flags")
    kind, dimbytes, pos = _element(payload, pos, endian)
    _need(kind == 5 and len(dimbytes) == 12, "Masks must have exactly three dimensions")
    dims = struct.unpack(endian + "iii", dimbytes)
    _need(dims[:2] == (MASK_HEIGHT, MASK_WIDTH) and 0 <= dims[2] <= MAX_INSTANCES,
          "Masks spatial dimensions or instance resource bound violated")
    count = math.prod(dims)
    kind, rawname, pos = _element(payload, pos, endian)
    _need(kind == 1 and rawname == expected_variable.encode("ascii"),
          "MAT must contain only the declared mask variable")
    kind, real, pos = _element(payload, pos, endian)
    _need(kind == CLASS_TYPES[cls] and len(real) == count * MI_ITEMSIZE[kind],
          "MAT storage type, shape or byte extent mismatch")
    logical = bool(flags0 & 0x200)
    if logical:
        _need(cls == 9 and kind == 2, "logical Masks require canonical uint8 storage")
        _need(all(value in (0, 1) for value in real),
              "logical Masks raw storage must be binary before conversion")
    _need(pos == len(payload), "unexpected elements in Masks matrix")
    return {"name": expected_variable, "shape": list(dims), "mat_class": cls,
            "logical_flag": logical, "storage_type": kind,
            "elements": count, "numeric_data_bytes": len(real)}


def preflight_candidate_mat(data, *, expected_variable="Masks"):
    """Return a bounded uncompressed MAT5 stream and metadata; no values loaded."""
    _need(expected_variable in ("Masks", "FinalMasks"), "unsupported mask variable")
    _need(isinstance(data, bytes), "candidate MAT source must be bytes")
    _need(128 <= len(data) <= MAX_MAT_BYTES, "candidate MAT source-byte cap/header")
    _need(data.startswith(b"MATLAB 5.0 MAT-file"), "only MAT5 is admitted; HDF5/v7.3 rejected")
    _need(data[126:128] in (b"IM", b"MI"), "invalid MAT byte order")
    _need(data[116:124] == b"\x00" * 8, "MAT subsystem references are not admitted")
    endian = "<" if data[126:128] == b"IM" else ">"
    _need(struct.unpack(endian + "H", data[124:126])[0] == 0x100, "unsupported MAT version")
    kind, payload, next_offset = _element(data, 128, endian, compressed_top=True)
    _need(next_offset == len(data), "candidate MAT must have exactly one variable and no trailing records")
    if kind == 15:
        matrix = _inflate(payload, MAX_EXPANDED_BYTES - 128)
        inner_kind, matrix_payload, inner_end = _element(matrix, 0, endian)
        _need(inner_kind == 14 and inner_end == len(matrix), "compressed MAT must contain one matrix")
    else:
        _need(kind == 14, "unsupported MAT top-level element")
        matrix, matrix_payload = data[128:next_offset], payload
    _need(128 + len(matrix) <= MAX_EXPANDED_BYTES, "candidate MAT expanded-byte cap")
    metadata = _matrix_header(matrix_payload, endian, expected_variable)
    metadata["expanded_stream_bytes"] = 128 + len(matrix)
    return data[:128] + matrix, metadata


def load_candidate_mat(data, *, expected_variable="Masks"):
    """Load Masks[column, row, neuron] without any spatial or ROI transpose."""
    normalized, metadata = preflight_candidate_mat(data, expected_variable=expected_variable)
    import numpy as np
    from scipy.io import loadmat, whosmat
    listing = whosmat(io.BytesIO(normalized))
    _need(len(listing) == 1 and listing[0][0] == expected_variable and
          tuple(listing[0][1]) == tuple(metadata["shape"]), "SciPy/preflight variable or shape disagreement")
    values = loadmat(io.BytesIO(normalized), squeeze_me=False, struct_as_record=False,
                     mat_dtype=True, verify_compressed_data_integrity=True)
    _need(set(k for k in values if not k.startswith("__")) == {expected_variable}, "decoded variable set changed")
    masks = values[expected_variable]
    _need(masks.shape == tuple(metadata["shape"]) and masks.dtype.kind in "buif",
          "decoded Masks type or shape changed")
    _need(np.isfinite(masks).all() and np.all((masks == 0) | (masks == 1)),
          "Masks must contain finite binary values")
    # Empty output sets are representable; empty individual ROI instances are not.
    if masks.shape[2]:
        _need(np.all(np.any(masks != 0, axis=(0, 1))), "zero-area individual ROI is not admitted")
    canonical = np.array(masks, dtype=np.bool_, copy=True, order="F")
    canonical.flags.writeable = False
    metadata["canonical_dtype"] = "bool"
    metadata["mask_axis_order"] = ["column", "row", "neuron"]
    metadata["spatial_transpose_applied"] = False
    metadata["instance_order_preserved"] = True
    metadata["duplicate_positive_instances_preserved"] = True
    metadata["empty_output_set"] = masks.shape[2] == 0
    return canonical, metadata
