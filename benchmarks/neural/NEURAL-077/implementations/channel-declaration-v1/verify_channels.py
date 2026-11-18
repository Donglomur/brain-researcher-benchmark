"""Offline NEMAR nm000132/v1.0.0 P3 channel declaration verification.

This reads only the exact release manifest and one 512-byte channel table.
It neither reads EEG nor converts amplitudes or changes event coordinates.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import stat

MANIFEST_BYTES = 491920
MANIFEST_SHA256 = "23fd73297855f844ddab3948129937fff5cf91d454026fe091d36494ab943f8e"
CHANNEL_BYTES = 512
CHANNEL_GIT_SHA1 = "4da38d26a268f636b287dfc0d9333d0cde5f5f63"
CHANNELS = (
    "FP1", "F3", "F7", "FC3", "C3", "C5", "P3", "P7", "P9", "PO7", "PO3",
    "O1", "Oz", "Pz", "CPz", "FP2", "Fz", "F4", "F8", "FC4", "FCz", "Cz",
    "C4", "C6", "P4", "P8", "P10", "PO8", "PO4", "O2", "HEOG_left",
    "HEOG_right", "VEOG_lower",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def unique(items):
    result = {}
    for key, value in items:
        require(key not in result, "Duplicate JSON field")
        result[key] = value
    return result


def validate_inventory(rows):
    """Check all 40 release paths against the same independently pinned blob."""
    require(type(rows) is list, "Manifest must be an array")
    selected = {}
    for row in rows:
        require(type(row) is dict and type(row.get("path")) is str,
                "Manifest row requires a path")
        path = row["path"]
        if not path.endswith("_task-P3_channels.tsv"):
            continue
        require(path not in selected, "Duplicate channel-table path")
        require(type(row.get("size")) is int and row["size"] == CHANNEL_BYTES
                and row.get("checksum_algorithm") == "git"
                and row.get("checksum") == CHANNEL_GIT_SHA1,
                "Channel table extent or Git identity differs")
        expected_url = "https://data.nemar.org/nm000132/v1.0.0/" + path
        require(row.get("bytes_url") == expected_url and row.get("url") == expected_url,
                "Exact versioned source URL required")
        selected[path] = expected_url
    expected = {
        f"sub-{person:03d}/eeg/sub-{person:03d}_task-P3_channels.tsv"
        for person in range(1, 41)
    }
    require(set(selected) == expected, "Complete original 40-person inventory required")
    return sorted(selected)


def parse_channels(body):
    """Report declarations, including unknown units, without physical conversion."""
    require(type(body) is bytes and 0 < len(body) <= 16384, "Bounded table bytes required")
    text = body.decode("utf-8", errors="strict")
    require("\x00" not in text, "NUL in table")
    reader = csv.reader(io.StringIO(text, newline=""), delimiter="\t", strict=True)
    header = next(reader, [])
    require(len(header) == len(set(header)) and {"name", "type", "units"} <= set(header),
            "Unique name/type/units columns required")
    records = []
    for fields in reader:
        require(len(fields) == len(header), "Ragged channel table")
        row = dict(zip(header, fields))
        require(all(type(row[key]) is str and row[key].strip() and len(row[key]) <= 128
                    for key in ("name", "type", "units")), "Bounded nonempty declarations required")
        records.append({key: row[key] for key in ("name", "type", "units")})
    require(len(records) == 33, "Exactly 33 original channels required")
    # This matches the already qualified SET-name normalization, not relabeling.
    require(tuple(row["name"].strip().upper() for row in records)
            == tuple(name.upper() for name in CHANNELS), "Original channel order required")
    require([row["type"] for row in records] == ["EEG"] * 30 + ["EOG"] * 3,
            "Original 30 EEG / 3 EOG roles required")
    units = sorted({row["units"] for row in records})
    return {
        "channels": records,
        "declared_unit_strings": units,
        "unit_declaration_complete": all(unit.strip().lower() not in {"n/a", "na", "unknown"}
                                         for unit in units),
        "units_uniform": len(units) == 1,
        "amplitude_scale_applied": None,
        "device_calibration_verified": False,
        "event_timing_verified": False,
    }


def verify(manifest_body, channel_body):
    require(pin(manifest_body) == {"bytes": MANIFEST_BYTES, "sha256": MANIFEST_SHA256},
            "Exact retained release manifest required")
    manifest = json.loads(manifest_body.decode("utf-8"), object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
    paths = validate_inventory(manifest)
    require(type(channel_body) is bytes and len(channel_body) == CHANNEL_BYTES,
            "Exact channel table extent required")
    git_digest = hashlib.sha1(b"blob " + str(len(channel_body)).encode("ascii") + b"\0" + channel_body).hexdigest()
    require(git_digest == CHANNEL_GIT_SHA1, "Exact manifest-bound Git blob required")
    observation = parse_channels(channel_body)
    return {
        "schema": "neural077_channel_declaration_v1",
        "release": "nm000132/v1.0.0",
        "manifest": pin(manifest_body),
        "channel_table": {**pin(channel_body), "git_blob_sha1": git_digest},
        "manifest_paths": paths,
        "scope": "One shared metadata body authenticates the declaration at 40 release paths; no EEG bytes read",
        **observation,
        "current_packet_changed": False,
        "readiness_promoted": False,
    }


def read_exact(path, size):
    # Trusted operator directories; this is a bounded file reader, not a sandbox.
    path = Path(path)
    require(not path.is_symlink(), "Symlink input refused")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        before = os.fstat(handle.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size == size, "Exact regular file extent required")
        body = handle.read(size + 1)
        after = os.fstat(handle.fileno())
        require(len(body) == size and (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "File changed during read")
    return body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--channels", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = verify(read_exact(args.manifest, MANIFEST_BYTES), read_exact(args.channels, CHANNEL_BYTES))
    body = (json.dumps(result, indent=2, allow_nan=False) + "\n").encode("utf-8")
    with Path(args.output).open("xb") as handle:
        handle.write(body)
    print(json.dumps({"status": "channel_declaration_verified", "output": pin(body),
                      "device_calibration_verified": False, "readiness_promoted": False}))


if __name__ == "__main__":
    main()
