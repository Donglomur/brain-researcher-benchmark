"""Lossless transfer encoding for the exact original 1400x820 RGB viewer canvas."""
import hashlib
import struct
import zlib

WIDTH, HEIGHT = 1400, 820
SCAN_BYTES = HEIGHT * (1 + WIDTH * 3)
PNG_CAP = 4 * 1024 * 1024
SIGNATURE = b"\x89PNG\r\n\x1a\n"
IHDR = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0)


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def chunk(kind, raw):
    return struct.pack(">I", len(raw)) + kind + raw + struct.pack(">I", zlib.crc32(kind + raw))


def scanlines(raw):
    need(type(raw) is bytes and 0 < len(raw) <= PNG_CAP and raw.startswith(SIGNATURE),
         "Bounded exact PNG required")
    cursor, parts = len(SIGNATURE), []
    for expected in (b"IHDR", b"IDAT", b"IEND"):
        need(cursor + 12 <= len(raw), "Truncated PNG chunk")
        size = struct.unpack(">I", raw[cursor:cursor+4])[0]
        need(size <= PNG_CAP and cursor + 12 + size <= len(raw), "PNG extent")
        kind = raw[cursor+4:cursor+8]
        body = raw[cursor+8:cursor+8+size]
        crc = struct.unpack(">I", raw[cursor+8+size:cursor+12+size])[0]
        need(kind == expected and zlib.crc32(kind + body) == crc, "PNG chunk order/CRC")
        parts.append(body); cursor += 12 + size
    need(cursor == len(raw) and parts[0] == IHDR and parts[2] == b"", "PNG shape/trailing bytes")
    decoder = zlib.decompressobj()
    scan = decoder.decompress(parts[1], SCAN_BYTES + 1)
    need(len(scan) == SCAN_BYTES and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,
         "Exact bounded complete scanline stream")
    need(all(scan[y * (1 + WIDTH * 3)] == 0 for y in range(HEIGHT)), "Original zero-filter RGB scanlines required")
    return scan


def encode_transport_image(raw):
    scan = scanlines(raw)
    compressed = zlib.compress(scan, level=9)
    out = SIGNATURE + chunk(b"IHDR", IHDR) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")
    need(len(out) <= PNG_CAP, "Transfer PNG cap")
    descriptor = {"schema": "neural077_lossless_png_transfer_v1", "original": pin(raw), "transfer": pin(out),
                  "ihdr": pin(IHDR), "scanlines": pin(scan), "dimensions": [WIDTH, HEIGHT],
                  "pixel_change": False, "filter_change": False, "compression_level": 9,
                  "zlib_compile_version": zlib.ZLIB_VERSION, "zlib_runtime_version": zlib.ZLIB_RUNTIME_VERSION}
    return out, descriptor


def verify_equivalence(original, delivered, descriptor):
    need(type(descriptor) is dict and descriptor.get("schema") == "neural077_lossless_png_transfer_v1",
         "Typed lossless transfer binding")
    a, b = scanlines(original), scanlines(delivered)
    need(a == b and descriptor["original"] == pin(original) and descriptor["transfer"] == pin(delivered)
         and descriptor["ihdr"] == pin(IHDR) and descriptor["scanlines"] == pin(a)
         and descriptor["dimensions"] == [WIDTH, HEIGHT]
         and descriptor["pixel_change"] is False and descriptor["filter_change"] is False
         and descriptor["compression_level"] == 9
         and all(type(descriptor[k]) is str and 0 < len(descriptor[k]) < 64
                 for k in ("zlib_compile_version", "zlib_runtime_version")), "Lossless identity mismatch")
    return True
