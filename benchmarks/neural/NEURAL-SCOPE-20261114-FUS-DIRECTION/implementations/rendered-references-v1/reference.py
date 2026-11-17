"""Packet-only controls for the registered FUS direction task.

No native arrays, private intake, fitting corpus, filesystem, or model access.
An external owner must freeze the method/lambda using outer-training episodes
and run each query in a fresh process. This function does not enforce custody.
"""
import base64
import binascii
import json
import math
import re
import struct
import zlib


RIDGES = (0.001, 0.01, 0.1, 1, 10, 100)
METHODS = ("uniform", "squared_distance", "cosine", "linear_ridge")
ANGLES = tuple(range(0, 360, 45))
ID = re.compile(r"q_[0-9a-f]{32}\Z")
FOLD = re.compile(r"fold_[0-9a-f]{32}\Z")
MAP_KEYS = frozenset(("map_id", "shape", "spatial_pitch", "spatial_pitch_unit",
                      "native_hz", "source_float", "scale", "invalid_pixels",
                      "saturated_pixels", "png_base64"))
GEOMETRY = ("shape", "spatial_pitch", "spatial_pitch_unit", "native_hz",
            "source_float", "scale")


class ReferenceError(ValueError):
    """Invalid packet/configuration: preserve the query as a failed output."""


def require(condition, message):
    if not condition:
        raise ReferenceError(message)


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def keys(value, expected, label):
    require(type(value) is dict and set(value) == set(expected), label + " keys")


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def png_pixels(encoded, shape):
    """Read exactly delivery-v1's RGB8/filter-zero/three-chunk PNG dialect.

    Restricting the codec to the existing producer avoids hidden metadata and
    transformations. Decompression is bounded to the previously checked shape.
    """
    require(type(encoded) is str, "PNG base64 string")
    try:
        body = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ReferenceError("invalid PNG base64") from error
    require(body[:8] == b"\x89PNG\r\n\x1a\n", "PNG signature")
    offset, chunks = 8, []
    for kind in (b"IHDR", b"IDAT", b"IEND"):
        require(offset + 12 <= len(body), "truncated PNG chunk")
        size = struct.unpack(">I", body[offset:offset + 4])[0]
        require(body[offset + 4:offset + 8] == kind, "unexpected PNG chunk")
        end = offset + 8 + size
        require(end + 4 <= len(body), "truncated PNG payload")
        payload = body[offset + 8:end]
        crc = struct.unpack(">I", body[end:end + 4])[0]
        require(crc == zlib.crc32(kind + payload) & 0xffffffff, "PNG CRC")
        chunks.append(payload)
        offset = end + 4
    require(offset == len(body) and chunks[2] == b"", "PNG trailing data")
    height, width = shape
    require(chunks[0] == struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0),
            "PNG dimensions or codec differ from native metadata")
    expected = height * (3 * width + 1)
    decoder = zlib.decompressobj()
    try:
        raw = decoder.decompress(chunks[1], expected + 1)
    except zlib.error as error:
        raise ReferenceError("invalid compressed PNG") from error
    require(len(raw) == expected and decoder.eof and not decoder.unused_data
            and not decoder.unconsumed_tail, "PNG decompression length/stream")
    pixels = bytearray()
    for row in range(height):
        start = row * (3 * width + 1)
        require(raw[start] == 0, "PNG row filter must be zero")
        pixels.extend(raw[start + 1:start + 1 + 3 * width])
    values, mask = bytearray(), bytearray()
    for start in range(0, len(pixels), 3):
        r, g, b = pixels[start:start + 3]
        valid = (r, g, b) != (255, 0, 255)
        require(not valid or r == g == b, "non-grayscale valid pixel")
        values.append(r if valid else 0)
        mask.append(int(valid))
    return values, mask


def decode_packet(wire, *, max_packet_bytes, max_map_pixels):
    """Validate the entire same-nine-map input before any method is applied."""
    require(type(max_packet_bytes) is int and max_packet_bytes > 0
            and type(max_map_pixels) is int and max_map_pixels > 0, "positive input budgets")
    require(type(wire) is bytes and 0 < len(wire) <= max_packet_bytes, "packet byte budget")
    try:
        packet = json.loads(wire, object_pairs_hook=unique_pairs,
                            parse_constant=lambda _: (_ for _ in ()).throw(ReferenceError("nonfinite JSON")))
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ReferenceError("invalid packet JSON: " + str(error)) from error
    keys(packet, ("schema", "fold_key", "query_id", "class_angles_degrees", "context",
                  "calibration", "query"), "packet")
    require(packet["schema"] == "fus_nine_map_packet_v1", "packet schema")
    require(type(packet["fold_key"]) is str and FOLD.fullmatch(packet["fold_key"]), "fold key")
    require(type(packet["query_id"]) is str and ID.fullmatch(packet["query_id"]), "query key")
    angles = packet["class_angles_degrees"]
    require(type(angles) is list and all(type(a) is int for a in angles)
            and tuple(angles) == ANGLES, "canonical angles")
    require(type(packet["context"]) is str, "context string")
    calibration = packet["calibration"]
    require(type(calibration) is list and len(calibration) == 8, "eight calibration maps")
    decoded, ids, geometry = [], set(), None
    for index, item in enumerate(calibration + [packet["query"]]):
        keys(item, MAP_KEYS | ({"direction_degrees"} if index < 8 else set()), "map")
        mid = item["map_id"]
        require(type(mid) is str and ID.fullmatch(mid) and mid not in ids, "unique opaque map IDs")
        ids.add(mid)
        if index < 8:
            require(type(item["direction_degrees"]) is int
                    and item["direction_degrees"] == ANGLES[index], "canonical calibration order")
        else:
            require(mid == packet["query_id"], "query map identity")
        shape = item["shape"]
        require(type(shape) is list and len(shape) == 2
                and all(type(x) is int and 0 < x < 2**31 for x in shape)
                and shape[0] * shape[1] <= max_map_pixels, "complete native shape/pixel budget")
        pitch = item["spatial_pitch"]
        require(type(pitch) is list and len(pitch) == 2
                and all(finite(x) and x > 0 for x in pitch), "spatial pitch")
        unit = item["spatial_pitch_unit"]
        require(type(unit) is str and 0 < len(unit) <= 64 and unit.strip() == unit
                and all(ord(c) >= 32 for c in unit), "spatial pitch unit")
        require(type(item["native_hz"]) is int and item["native_hz"] in (1, 2), "native rate")
        require(item["source_float"] in ("binary32", "binary64"), "source arithmetic")
        require(finite(item["scale"]) and item["scale"] > 0, "frozen training scale")
        signature = json.dumps({k: item[k] for k in GEOMETRY}, sort_keys=True)
        if geometry is None:
            geometry = signature
        require(signature == geometry, "mismatched map geometry or scale")
        values, mask = png_pixels(item["png_base64"], shape)
        invalid = len(mask) - sum(mask)
        require(type(item["invalid_pixels"]) is int and item["invalid_pixels"] == invalid,
                "invalid-pixel count")
        require(type(item["saturated_pixels"]) is int
                and 0 <= item["saturated_pixels"] <= len(mask) - invalid, "saturated-pixel count")
        decoded.append((values, mask))
    return packet["query_id"], decoded


def template(maps, method):
    # All nine images use the same label-independent validity intersection.
    positions = [p for p in range(len(maps[0][0])) if all(m[p] for _, m in maps)]
    if not positions:
        return [1 / 8] * 8
    query = maps[-1][0]
    if method == "squared_distance":
        scores = [-sum((v[p] - query[p])**2 for p in positions) for v, _ in maps[:8]]
    else:
        # Center on the encoding's zero-response midpoint, not the support mean.
        qnorm = sum((2 * query[p] - 255)**2 for p in positions)
        norms = [sum((2 * v[p] - 255)**2 for p in positions) for v, _ in maps[:8]]
        if qnorm == 0 or any(n == 0 for n in norms):
            return [1 / 8] * 8
        scores = [sum((2 * v[p] - 255) * (2 * query[p] - 255) for p in positions)
                  / math.sqrt(norm * qnorm) for (v, _), norm in zip(maps[:8], norms)]
    best = max(scores)
    tied = [s == best for s in scores]
    return [int(t) / sum(tied) for t in tied]


def kernel(a, b):
    """Linear full-field response + invalid-indicator kernel, / (2 * pixels)."""
    av, am = a
    bv, bm = b
    total = math.fsum(((2 * x / 255 - 1) * (2 * y / 255 - 1) if va and vb else 0)
                      + int(not va and not vb) for x, va, y, vb in zip(av, am, bv, bm))
    return total / (2 * len(av))


def solve_spd(matrix, rhs):
    """Cholesky solve; the strictly positive registered ridge removes singularity."""
    n = len(rhs)
    lower = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            residual = matrix[i][j] - math.fsum(lower[i][k] * lower[j][k] for k in range(j))
            if i == j:
                require(finite(residual) and residual > 0, "ridge system is not positive definite")
                lower[i][j] = math.sqrt(residual)
            else:
                lower[i][j] = residual / lower[j][j]
    intermediate, result = [0.0] * n, [0.0] * n
    for i in range(n):
        intermediate[i] = (rhs[i] - math.fsum(lower[i][j] * intermediate[j] for j in range(i))) / lower[i][i]
    for i in range(n - 1, -1, -1):
        result[i] = (intermediate[i] - math.fsum(lower[j][i] * result[j] for j in range(i + 1, n))) / lower[i][i]
    return result


def ridge(maps, lam):
    if not any(maps[-1][1]) or not any(any(mask) for _, mask in maps[:8]):
        return [1 / 8] * 8
    gram = [[kernel(a, b) for b in maps[:8]] for a in maps[:8]]
    means = [math.fsum(row) / 8 for row in gram]
    grand = math.fsum(means) / 8
    centered = [[gram[i][j] - means[i] - means[j] + grand + (lam if i == j else 0)
                 for j in range(8)] for i in range(8)]
    cross = [kernel(maps[-1], a) for a in maps[:8]]
    crossmean = math.fsum(cross) / 8
    cross = [cross[i] - means[i] - crossmean + grand for i in range(8)]
    # Solve once using symmetry, rather than eight identical matrix factorizations.
    weights = solve_spd(centered, cross)
    meanweight = math.fsum(weights) / 8
    raw = [1 / 8 + w - meanweight for w in weights]
    require(all(finite(x) for x in raw), "nonfinite ridge output")
    # Fixed rectification/renormalization, with no query-fitted calibration.
    positive = [max(0.0, x) for x in raw]
    total = math.fsum(positive)
    return [p / total for p in positive] if total else [1 / 8] * 8


def predict(wire, *, method, ridge_lambda=None, max_packet_bytes, max_map_pixels):
    """Return exactly one existing scorer-compatible row, never a study score.

    Method and ridge_lambda are external frozen choices. No tuning or persistent
    query state is performed. Malformed input raises instead of changing cohort.
    """
    require(type(method) is str and method in METHODS, "explicit reference method")
    if method == "linear_ridge":
        require(finite(ridge_lambda) and ridge_lambda in RIDGES, "registered positive ridge")
    else:
        require(ridge_lambda is None, "ridge is only valid for linear_ridge")
    qid, maps = decode_packet(wire, max_packet_bytes=max_packet_bytes, max_map_pixels=max_map_pixels)
    if method == "uniform":
        probabilities = [1 / 8] * 8
    elif method in ("squared_distance", "cosine"):
        probabilities = template(maps, method)
    else:
        probabilities = ridge(maps, ridge_lambda)
    return {"query_id": qid, "probabilities": probabilities}
