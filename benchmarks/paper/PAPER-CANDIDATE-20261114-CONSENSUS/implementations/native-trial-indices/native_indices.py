"""Inert decoder for the bounded Consensus native trial-index list.

This is deliberately not an OCaml Marshal implementation. It accepts only one
small-header, no-sharing, canonically encoded nonnegative int list, with the
caller-supplied trial count and raw SHA256. It never runs native code or pickle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import struct

MAX_TRIALS = 10_000
MAX_NATIVE_BYTES = 20 + 4 * MAX_TRIALS + 1
MAX_COMPANION_BYTES = 200_000
SMALL_MAGIC = 0x8495A6BE
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def trial_count(value):
    require(type(value) is int and 1 <= value <= MAX_TRIALS,
            "source_trial_count must be an integer in [1,10000]")
    return value


def decode_indices(raw, *, source_trial_count, expected_sha256):
    """Validate declared raw identity and return the exact ordered int list.

    The expected hash is an owner-supplied binding, not proof of deposit origin.
    This format check does not verify the companion NPY, neural trial axis,
    historical execution, or the interpretation of a particular source file.
    """
    n = trial_count(source_trial_count)
    require(type(expected_sha256) is str and _SHA256.fullmatch(expected_sha256),
            "expected_sha256 must be a lowercase SHA256")
    require(type(raw) is bytes and 21 <= len(raw) <= MAX_NATIVE_BYTES,
            "native body outside bounded byte extent")
    require(hashlib.sha256(raw).hexdigest() == expected_sha256,
            "native raw identity mismatch")
    magic, payload_size, shared_blocks, words32, words64 = struct.unpack(">5I", raw[:20])
    require(magic == SMALL_MAGIC, "unsupported Marshal header magic")
    require(payload_size == len(raw) - 20, "declared payload extent mismatch")
    require(shared_blocks == 0, "only the no-sharing writer profile is supported")
    require(words32 == words64 == 3 * n,
            "heap-word counts do not match the declared int-list length")
    offset = 20
    result = []
    for _ in range(n):
        require(offset < len(raw) and raw[offset] == 0xA0,
                "expected canonical tag-zero, size-two list cell")
        offset += 1
        require(offset < len(raw), "truncated list head")
        code = raw[offset]
        offset += 1
        if 0x40 <= code < 0x80:
            value = code - 0x40
        elif code in (0x00, 0x01):
            width = 1 if code == 0 else 2
            require(offset + width <= len(raw), "truncated encoded integer")
            value = int.from_bytes(raw[offset:offset + width], "big", signed=True)
            offset += width
            require((64 <= value < 128) if width == 1 else (128 <= value < 32768),
                    "noncanonical or negative encoded integer")
        else:
            raise ValueError("unsupported list-head encoding")
        require(value < n, "trial index outside the declared source axis")
        result.append(value)
    require(offset + 1 == len(raw) and raw[offset] == 0x40,
            "expected exactly one canonical empty-list terminator and EOF")
    return result


def companion_values(values, n):
    """Use the existing occurrence-adapter's integral-number convention."""
    require(type(values) is list and len(values) == n, "complete companion list required")
    result = []
    for value in values:
        if type(value) is float:
            require(math.isfinite(value) and value.is_integer(),
                    "companion contains a nonfinite or nonintegral float")
            value = int(value)
        require(type(value) is int and 0 <= value < n,
                "companion value outside the declared source axis")
        result.append(value)
    return result


def inspect_native(raw, *, source_trial_count, expected_sha256, companion_indices=None):
    """Produce an owner-private record; never repair or deduplicate indices."""
    native = decode_indices(raw, source_trial_count=source_trial_count,
                            expected_sha256=expected_sha256)
    companion = None if companion_indices is None else companion_values(
        companion_indices, source_trial_count)
    counts = [0] * source_trial_count
    for index in native:
        counts[index] += 1
    mismatches = None if companion is None else [
        i for i, (left, right) in enumerate(zip(native, companion)) if left != right
    ]
    return {
        "schema": "consensus_native_trial_indices_v1",
        "source_trial_count": source_trial_count,
        "native_body": {"bytes": len(raw), "sha256": expected_sha256},
        "native_indices": native,
        "supplied_companion_indices": companion,
        "supplied_companion_equal": None if mismatches is None else not mismatches,
        "mismatch_positions": mismatches,
        "count_by_source_id": counts,
        "omitted_source_ids": [i for i, count in enumerate(counts) if count == 0],
        "repeated_occurrences": sum(max(0, count - 1) for count in counts),
        "format_profile": "small_header_no_sharing_canonical_nonnegative_int_list",
        "source_origin_authenticated": False,
        "companion_npy_bytes_authenticated": False,
        "native_ocaml_execution_verified": False,
        "scientific_qualification": False,
    }


def read_regular(path, limit):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size <= limit,
                "bounded ordinary file required")
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
        require(len(raw) <= limit and len(raw) == before.st_size and
                (before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                "input changed or exceeded the byte bound")
    return raw


def parse_companion(raw):
    def bad_constant(_):
        raise ValueError("nonfinite companion JSON")
    values = json.loads(raw.decode("utf-8"), parse_constant=bad_constant)
    require(type(values) is list, "supplied companion JSON must contain a list")
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", required=True)
    parser.add_argument("--source-trial-count", required=True, type=int)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--companion-json")
    args = parser.parse_args()
    try:
        n = trial_count(args.source_trial_count)
        raw = read_regular(args.native, MAX_NATIVE_BYTES)
        companion = None if args.companion_json is None else parse_companion(
            read_regular(args.companion_json, MAX_COMPANION_BYTES))
        result = inspect_native(raw, source_trial_count=n,
                                expected_sha256=args.expected_sha256,
                                companion_indices=companion)
        print(json.dumps(result, sort_keys=True, allow_nan=False, separators=(",", ":")))
    except (OSError, ValueError, UnicodeError) as exc:
        parser.exit(2, "native index admission refused: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
