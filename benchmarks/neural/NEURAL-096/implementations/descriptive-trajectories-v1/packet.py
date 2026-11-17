"""Bounded operator loading of the previously authenticated Set–Go packet.

Loading is an operator action, never a participant action. This module does not
load data on import. The exact original preparation receipt is required; a caller
cannot confer provenance by supplying a self-authored source hash.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path
import zipfile

import numpy as np


RECEIPT_BYTES = 3688
RECEIPT_SHA256 = "3011373f5286ee20e3b308644f22c27203cfcd69b971d2f1ff039584734982ac"
SOURCE_SHA256 = "6212aaee2c978d1cd53fbfb433d11f418ed27cd83017b8b2befa4a1d7add5198"
MAX_PACKET_BYTES = 20 * 1024 * 1024
MAX_JSON_BYTES = 512 * 1024
MAX_EXPANDED_ARRAY_BYTES = 4 * 1024 * 1024
ARRAY_NAMES = frozenset(("counts", "phase_edges_seconds", "exposure_seconds",
                         "spike_times_seconds", "spike_offsets", "trial_ids",
                         "unit_ids", "nlb_heldout_unit_flags"))
ARRAY_LAYOUT = {
    "counts": ((204, 54, 20), "<u4"),
    "phase_edges_seconds": ((204, 21), "<f8"),
    "exposure_seconds": ((204, 20), "<f8"),
    "spike_times_seconds": ((81311,), "<f8"),
    "spike_offsets": ((11017,), "<i8"),
    "trial_ids": ((204,), "<i8"),
    "unit_ids": ((54,), "<i8"),
    "nlb_heldout_unit_flags": ((54,), "|u1"),
}


class PacketError(ValueError):
    """An input does not match the already accepted operator packet."""


def require(condition, message):
    if not condition:
        raise PacketError(message)


def sha256(body):
    return hashlib.sha256(body).hexdigest()


def strict_json(body):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def constant(value):
        raise PacketError("nonfinite JSON constant: " + value)

    def real(value):
        number = float(value)
        require(math.isfinite(number), "JSON floating value exceeds finite range")
        return number

    try:
        return json.loads(body, object_pairs_hook=pairs, parse_constant=constant,
                          parse_float=real)
    except PacketError:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise PacketError("invalid JSON") from exc


def bounded_file(path, limit):
    path = Path(path)
    require(not path.is_symlink() and path.is_file(), "ordinary file required")
    require(0 < path.stat().st_size <= limit, "input file size outside bound")
    with path.open("rb") as handle:
        body = handle.read(limit + 1)
    require(0 < len(body) <= limit, "input changed or exceeded byte bound")
    return body


def decode_arrays(body):
    """Decode an already authenticated NPZ with finite expansion and no pickle."""
    require(type(body) is bytes and len(body) <= MAX_PACKET_BYTES,
            "bounded NPZ bytes required")
    try:
        arrays = {}
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            entries = archive.infolist()
            require(len(entries) == len(ARRAY_NAMES), "unexpected array count")
            require({entry.filename for entry in entries} ==
                    {name + ".npy" for name in ARRAY_NAMES}, "unexpected array names")
            require(sum(entry.file_size for entry in entries) <= MAX_EXPANDED_ARRAY_BYTES,
                    "array expansion exceeds bound")
            require(all(not entry.is_dir() and not (entry.flag_bits & 1)
                        and entry.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                        and 0 < entry.file_size <= MAX_EXPANDED_ARRAY_BYTES
                        for entry in entries), "unsupported ZIP member")
            for entry in entries:
                name = entry.filename[:-4]
                with archive.open(entry) as handle:
                    member = handle.read(entry.file_size + 1)
                require(len(member) == entry.file_size, "member expansion changed")
                stream = io.BytesIO(member)
                require(np.lib.format.read_magic(stream) == (1, 0),
                        "original NPY version required")
                shape, fortran_order, dtype = np.lib.format.read_array_header_1_0(
                    stream, max_header_size=1024)
                expected_shape, expected_dtype = ARRAY_LAYOUT[name]
                require(shape == expected_shape and dtype == np.dtype(expected_dtype)
                        and not fortran_order and not dtype.hasobject,
                        "original array layout required: " + name)
                require(len(member) - stream.tell() == int(np.prod(shape)) * dtype.itemsize,
                        "array payload extent disagrees with header")
                # Header size, shape and dtype were checked before allocation.
                arrays[name] = np.load(io.BytesIO(member), allow_pickle=False,
                                       max_header_size=1024)
    except (OSError, ValueError, zipfile.BadZipFile, EOFError) as exc:
        if isinstance(exc, PacketError):
            raise
        raise PacketError("invalid finite numeric NPZ") from exc
    require(all(array.dtype.kind in "biuf" and not array.dtype.hasobject
                for array in arrays.values()), "numeric arrays required")
    require(sum(array.nbytes for array in arrays.values()) <= MAX_EXPANDED_ARRAY_BYTES,
            "decoded arrays exceed bound")
    return arrays


def load_original_packet(directory):
    """Load only the exact earlier preparation, preserving its stated limits.

    This authenticates the saved packet, not a second reread of the original NWB
    spikes or an independent recovery of the fourteen extra unit identities.
    """
    directory = Path(directory)
    require(not directory.is_symlink() and directory.is_dir(), "packet directory required")
    receipt_body = bounded_file(directory / "receipt.json", RECEIPT_BYTES)
    require(len(receipt_body) == RECEIPT_BYTES and sha256(receipt_body) == RECEIPT_SHA256,
            "original preparation receipt identity required")
    receipt = strict_json(receipt_body)
    require(receipt.get("schema") == "neural096_source_preparation_receipt_v1"
            and receipt.get("status") == "complete_source_observations_prepared"
            and receipt.get("source_sha256") == SOURCE_SHA256,
            "original preparation identity mismatch")
    files = receipt.get("files")
    require(type(files) is list and len(files) == 2, "exact packet inventory required")
    inventory = {}
    for item in files:
        require(type(item) is dict and item.get("path") in
                ("observations.json", "observations.npz"), "unexpected packet file")
        name = item["path"]
        require(name not in inventory and type(item.get("bytes")) is int
                and item["bytes"] > 0 and type(item.get("sha256")) is str
                and len(item["sha256"]) == 64, "invalid packet inventory entry")
        inventory[name] = item
    bodies = {}
    for name, pin in inventory.items():
        limit = MAX_JSON_BYTES if name.endswith(".json") else MAX_PACKET_BYTES
        body = bounded_file(directory / name, min(limit, pin["bytes"]))
        require(len(body) == pin["bytes"] and sha256(body) == pin["sha256"],
                "packet file changed: " + name)
        bodies[name] = body
    require(sum(map(len, bodies.values())) + len(receipt_body) <= MAX_PACKET_BYTES,
            "complete packet exceeds bound")
    metadata = strict_json(bodies["observations.json"])
    arrays = decode_arrays(bodies["observations.npz"])
    return metadata, arrays, {
        "receipt_sha256": RECEIPT_SHA256,
        "source_sha256": SOURCE_SHA256,
        "files": inventory,
        "verification_scope": "authenticated saved preparation; no independent original spike reread",
    }
