"""Prepare five authenticated image attachments; no model call, scoring or gold.

The eventual transport must consume the returned image bytes directly. This
module does not establish delivery, tool isolation or semantic leakage absence.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import zlib

MANIFEST_CAP = 2 * 1024**2
IMAGE_CAP = 4 * 1024**2
SHA = re.compile(r"[0-9a-f]{64}\Z")
CASE = re.compile(r"case-[0-9]{4}\Z")
ARMS = ("direct", "programme")


def need(condition, message):
    if not condition:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def decode(body):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, "nonfinite JSON"))


def sha(value):
    need(type(value) is str and SHA.fullmatch(value), "exact lowercase SHA256")


def ordinary(path):
    path = Path(path)
    need(path.is_absolute() and ".." not in path.parts,
         "absolute path without traversal required")
    need(all(not item.is_symlink() for item in (path, *path.parents)),
         "symlink paths refused")
    return path


def read(path, cap, expected=None):
    path = ordinary(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 < before.st_size <= cap, "ordinary bounded single-link file")
        if expected is not None:
            need(before.st_size == expected["bytes"], "attachment extent mismatch")
        body = stream.read(before.st_size + 1)
        after = os.fstat(stream.fileno())
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns,
                          s.st_ctime_ns, s.st_nlink)
    need(identity(before) == identity(after) == identity(path.lstat())
         and len(body) == before.st_size, "input changed while reading")
    need(expected is None or pin(body) == expected, "attachment hash mismatch")
    return body


def validate_manifest(body, manifest_sha, protocol_sha):
    """Validate all descriptors without opening any image or protected locator."""
    sha(manifest_sha)
    sha(protocol_sha)
    need(type(body) is bytes and 0 < len(body) <= MANIFEST_CAP,
         "bounded manifest bytes")
    need(pin(body)["sha256"] == manifest_sha, "manifest commitment mismatch")
    obj = decode(body)
    need(type(obj) is dict and set(obj) == {
        "schema", "protocol_sha256", "prompts", "demonstrations", "queries"
    }, "exact manifest schema; no private or label fields")
    need(obj["schema"] == "erp-image-dispatch/v1"
         and obj["protocol_sha256"] == protocol_sha, "protocol binding mismatch")
    prompts = obj["prompts"]
    need(type(prompts) is dict and set(prompts) == set(ARMS), "both arm prompts")
    for prompt in prompts.values():
        need(type(prompt) is str and 0 < len(prompt.encode("utf-8")) <= 16384
             and prompt.count("{trial_id}") == 1,
             "bounded prompt requires exactly one trial_id placeholder")
        need("{" not in prompt.replace("{trial_id}", "")
             and "}" not in prompt.replace("{trial_id}", ""),
             "no other prompt substitution")
    demos, queries = obj["demonstrations"], obj["queries"]
    need(type(demos) is list and len(demos) == 4, "exactly four demonstrations")
    need(type(queries) is list and 1 <= len(queries) <= 6400, "bounded query roster")
    seen = set()
    for role, rows in (("demo", demos), ("query", queries)):
        for index, row in enumerate(rows):
            need(type(row) is dict and set(row) == {
                "image_id", "file", "bytes", "sha256"
            }, "exact image descriptor; no query labels or arbitrary paths")
            image_id = row["image_id"]
            need(type(image_id) is str and image_id not in seen, "unique image ID")
            if role == "demo":
                need(image_id == f"demo{index + 1}", "ordered demo1 through demo4")
            else:
                need(CASE.fullmatch(image_id), "anonymous four-digit query ID")
            need(row["file"] == image_id + ".png", "filename must derive from ID")
            need(type(row["bytes"]) is int and 0 < row["bytes"] <= IMAGE_CAP,
                 "bounded image extent")
            sha(row["sha256"])
            seen.add(image_id)
    return obj


def check_png(body):
    """Check the retained renderer's fixed RGB format, CRCs and decoded extent."""
    need(body[:8] == b"\x89PNG\r\n\x1a\n", "PNG signature")
    offset, chunks = 8, []
    while offset < len(body):
        need(offset + 12 <= len(body), "complete PNG chunk")
        size = struct.unpack(">I", body[offset:offset + 4])[0]
        need(size <= IMAGE_CAP and offset + size + 12 <= len(body), "PNG chunk bound")
        kind = body[offset + 4:offset + 8]
        data = body[offset + 8:offset + 8 + size]
        crc = struct.unpack(">I", body[offset + 8 + size:offset + 12 + size])[0]
        need(crc == zlib.crc32(kind + data) & 0xffffffff, "PNG CRC mismatch")
        chunks.append((kind, data))
        need(len(chunks) <= 3, "no ancillary image metadata")
        offset += size + 12
    need([kind for kind, _ in chunks] == [b"IHDR", b"IDAT", b"IEND"],
         "retained renderer chunk order")
    need(chunks[0][1] == struct.pack(">IIBBBBB", 1400, 820, 8, 2, 0, 0, 0)
         and chunks[2][1] == b"", "fixed 1400 by 820 RGB raster")
    expected = 820 * (1 + 1400 * 3)
    decoder = zlib.decompressobj()
    decoded = decoder.decompress(chunks[1][1], expected + 1)
    need(len(decoded) == expected and decoder.eof and not decoder.unused_data
         and not decoder.unconsumed_tail, "exact bounded PNG decoded extent")
    need(all(decoded[i] <= 4 for i in range(0, expected, 4201)), "valid PNG row filters")


def prepare_payload(manifest_body, manifest_sha, protocol_sha, assets, trial_id, arm):
    """Return one no-path payload. Other query images are never opened."""
    obj = validate_manifest(manifest_body, manifest_sha, protocol_sha)
    need(arm in ARMS, "known arm")
    matches = [row for row in obj["queries"] if row["image_id"] == trial_id]
    need(len(matches) == 1, "query must be in committed roster")
    root = ordinary(assets)
    need(root.is_dir(), "asset root must be a directory")
    images = []
    for row in [*obj["demonstrations"], matches[0]]:
        expected = {key: row[key] for key in ("bytes", "sha256")}
        body = read(root / row["file"], IMAGE_CAP, expected)
        check_png(body)
        images.append({"image_id": row["image_id"], "mime_type": "image/png",
                       **expected, "data_base64": base64.b64encode(body).decode("ascii")})
    return {"schema": "erp-five-image-payload/v1", "protocol_sha256": protocol_sha,
            "manifest_sha256": manifest_sha, "arm": arm, "trial_id": trial_id,
            "prompt": obj["prompts"][arm].replace("{trial_id}", trial_id),
            "images": images}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "manifest-sha256", "protocol-sha256", "assets", "trial-id", "arm"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    body = read(args.manifest, MANIFEST_CAP)
    payload = prepare_payload(body, args.manifest_sha256, args.protocol_sha256,
                              args.assets, args.trial_id, args.arm)
    # A future selected transport consumes these exact attachment bytes. The
    # module intentionally has no participant-dispatch or gold-reading backend.
    print(encode(payload).decode("utf-8"), end="")


if __name__ == "__main__":
    main()
