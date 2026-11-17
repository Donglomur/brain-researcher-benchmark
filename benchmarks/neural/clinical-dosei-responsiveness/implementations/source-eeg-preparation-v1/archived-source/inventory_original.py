#!/usr/bin/env python3
"""Bounded ZIP-directory inspection only: no native CSV decompression or CRC run.

This script is a proposal until separately reviewed and executed by the lead.
The full archive was authenticated by the acquisition receipt, whose hash must
be pinned independently. The receipt's immutable file signature must still match.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import unicodedata
import uuid
import zipfile

DESTINATION = Path("/Users/nicholas/Documents/Codex/neuroscience-benchmark-data/dosei-native-v2-20261117")
ARCHIVE = DESTINATION / "data.zip"
SIZE = 724_356_077
MD5 = "b98c8a81d2e866085f9e7ac75a950754"
INSPECTION = Path("/Users/nicholas/Documents/Codex/benchmark-engineering-evidence/comprehensive-revision-20261116-v2/completion2-v1/dosei/source-contract/METADATA_INSPECTION.json")
INSPECTION_SHA256 = "bb6b4e8951d8a6ace086d8e157eb7f4082417d01956f98c86575f6706e15a994"
METADATA_ARCHIVE_SHA256 = "a2e90c906969364e9def40a83b46843fcf7809324ac893a3d428a481481b2798"
MAX_DIRECTORY = 1_048_576
MAX_MEMBERS = 512
MAX_FILE = 1_073_741_824
MAX_TOTAL = 34_359_738_368
STAT_FIELDS = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def signature(value):
    return {key: getattr(value, key) for key in STAT_FIELDS}


def small_bytes(path, limit):
    with path.open("rb") as handle:
        raw = handle.read(limit + 1)
    require(len(raw) <= limit, "small input exceeds limit: " + str(path))
    return raw


def directory_bounds(handle):
    # Preflight BEFORE ZipFile allocates the central-directory member objects.
    tail_size = min(SIZE, 65_558)
    handle.seek(SIZE - tail_size)
    tail = handle.read(tail_size)
    require(len(tail) == tail_size, "short archive tail")
    index = tail.rfind(b"PK\x05\x06")
    require(index >= 0 and index + 22 <= len(tail), "EOCD missing/truncated")
    values = struct.unpack("<4s4H2LH", tail[index:index + 22])
    _, disk, start_disk, disk_count, count, directory_size, offset, comment_length = values
    require(index + 22 + comment_length == len(tail), "EOCD comment/trailing-byte mismatch")
    eocd_offset = SIZE - tail_size + index
    require(disk == 0 and start_disk == 0 and disk_count == count, "multi-disk ZIP prohibited")
    upper = eocd_offset
    sentinel_zip64 = any((disk_count == 0xFFFF, count == 0xFFFF,
                          directory_size == 0xFFFFFFFF, offset == 0xFFFFFFFF))
    locator = b""
    if eocd_offset >= 20:
        handle.seek(eocd_offset - 20)
        locator = handle.read(20)
    # ZipFile inspects the locator even when ordinary EOCD fields are not
    # sentinels. Preflight must use the same effective directory metadata.
    is_zip64 = sentinel_zip64 or locator[:4] == b"PK\x06\x07"
    if is_zip64:
        require(eocd_offset >= 20, "ZIP64 locator missing")
        require(len(locator) == 20, "short ZIP64 locator")
        magic, locator_disk, record_offset, total_disks = struct.unpack("<4sLQL", locator)
        require(magic == b"PK\x06\x07" and locator_disk == 0 and total_disks == 1,
                "invalid/multi-disk ZIP64 locator")
        require(0 <= record_offset <= eocd_offset - 76, "ZIP64 record offset outside archive")
        handle.seek(record_offset)
        record = handle.read(56)
        require(len(record) == 56, "short ZIP64 record")
        fields = struct.unpack("<4sQ2H2L4Q", record)
        magic, record_size, _made, _needed, disk64, start64, count_disk64, count64, size64, offset64 = fields
        require(magic == b"PK\x06\x06" and record_size == 44, "invalid/unsupported extended ZIP64 record")
        require(record_offset + 12 + record_size == eocd_offset - 20, "ZIP64 record/locator discontinuity")
        require(disk64 == 0 and start64 == 0 and count_disk64 == count64, "multi-disk ZIP64 prohibited")
        for short, full, sentinel in ((count, count64, 0xFFFF),
                                       (directory_size, size64, 0xFFFFFFFF), (offset, offset64, 0xFFFFFFFF)):
            require(short == sentinel or short == full, "contradictory ZIP64/EOCD fields")
        count, directory_size, offset = count64, size64, offset64
        upper = record_offset
    require(0 < count <= MAX_MEMBERS, "declared ZIP member count exceeds 512")
    require(0 < directory_size <= MAX_DIRECTORY, "central directory exceeds 1 MiB")
    require(0 <= offset and offset + directory_size == upper,
            "central directory is outside region or has unsupported trailing layout")
    return {"declared_members": count, "offset": offset, "bytes": directory_size,
            "zip64": is_zip64, "eocd_offset": eocd_offset,
            "directory_end_upper_bound": upper}


def inspect(receipt_path, receipt_sha256, protocol_sha256):
    receipt_raw = small_bytes(receipt_path, 65_536)
    require(hashlib.sha256(receipt_raw).hexdigest() == receipt_sha256, "acquisition receipt SHA256 mismatch")
    acquisition = json.loads(receipt_raw)
    require(acquisition.get("schema") == "dosei_original_acquisition_v1", "wrong acquisition receipt schema")
    require(acquisition.get("status") == "succeeded" and acquisition.get("hashes_cover_complete_archive") is True,
            "acquisition did not authenticate a complete archive")
    require(acquisition.get("expected_bytes") == SIZE and acquisition.get("expected_md5") == MD5,
            "acquisition source pin differs")
    require(acquisition.get("body_bytes_written") == SIZE and acquisition.get("written_prefix_md5") == MD5,
            "acquisition size/hash verification absent")
    require(acquisition.get("final_path") == str(ARCHIVE), "acquisition final path differs")
    require(re.fullmatch(r"[0-9a-f]{64}", acquisition.get("written_prefix_sha256", "")) is not None,
            "archive SHA256 receipt absent")
    require(ARCHIVE.parent.resolve() == ARCHIVE.parent, "archive parent path is a symlink")
    expected_stat = acquisition.get("verified_final_stat")
    require(isinstance(expected_stat, dict) and set(expected_stat) == set(STAT_FIELDS), "immutable file signature absent")
    metadata_raw = small_bytes(INSPECTION, 131_072)
    require(hashlib.sha256(metadata_raw).hexdigest() == INSPECTION_SHA256, "pinned metadata inspection differs")
    metadata = json.loads(metadata_raw)
    require(next(f["sha256"] for f in metadata["files"] if f["name"] == "metadata.zip") == METADATA_ARCHIVE_SHA256,
            "metadata archive pin differs")
    expected_ids = metadata["metadata"]["ids"]
    require(len(expected_ids) == len(set(expected_ids)) == 171, "pinned metadata IDs not unique/complete")
    result = {
        "schema": "dosei_original_directory_inventory_v1", "created_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": protocol_sha256,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "acquisition_receipt_path": str(receipt_path), "acquisition_receipt_sha256": receipt_sha256,
        "archive_path": str(ARCHIVE), "archive_expected_md5": MD5,
        "archive_sha256_verified_during_acquisition": acquisition["written_prefix_sha256"],
        "archive_rehashed_in_this_run": False, "archive_signature_before": expected_stat,
        "metadata_inspection_sha256": INSPECTION_SHA256,
        "csv_decompression_performed": False, "member_payloads_decompressed": 0,
        "tail_scan_max_bytes": 65_558,
        "crc_verification_performed": False, "members": [], "status": "failed",
    }
    require(stat.S_ISREG(ARCHIVE.lstat().st_mode), "archive is not a regular file")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(ARCHIVE, flags), "rb") as handle:
        require(stat.S_ISREG(os.fstat(handle.fileno()).st_mode), "opened archive is not a regular file")
        require(signature(os.fstat(handle.fileno())) == expected_stat, "archive changed since authenticated acquisition")
        require(os.fstat(handle.fileno()).st_size == SIZE, "archive size differs")
        bounds = directory_bounds(handle)
        result["central_directory"] = bounds
        with zipfile.ZipFile(handle, "r") as archive:
            require(archive.start_dir == bounds["offset"], "ZIP parser directory offset differs from preflight")
            infos = archive.infolist()
            require(len(infos) == bounds["declared_members"] and len(infos) <= MAX_MEMBERS,
                    "actual directory count differs/exceeds bound")
            seen, csv_ids, total = set(), [], 0
            for item in infos:
                name = item.orig_filename
                require(name == item.filename and len(name) <= 256 and not any(ord(c) < 32 for c in name),
                        "invalid/truncated/oversized member name")
                pure = PurePosixPath(name)
                require(not pure.is_absolute() and "\\" not in name and ":" not in name,
                        "absolute/platform-dependent member path")
                components = name.rstrip("/").split("/")
                require(all(c not in ("", ".", "..") for c in components), "unsafe member path component")
                normalized = unicodedata.normalize("NFC", name.rstrip("/")).casefold()
                require(normalized not in seen, "duplicate/colliding member name")
                seen.add(normalized)
                mode = (item.external_attr >> 16) & 0xFFFF
                kind = stat.S_IFMT(mode)
                require(kind in (0, stat.S_IFREG, stat.S_IFDIR), "symlink/special-file member prohibited")
                require(not (item.flag_bits & 0x41), "encrypted ZIP member prohibited")
                require(item.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), "unsupported compression")
                require(0 <= item.file_size <= MAX_FILE and 0 <= item.compress_size <= SIZE, "member size outside bound")
                require(0 <= item.header_offset < bounds["offset"], "member header outside data region")
                require(item.header_offset + 30 + item.compress_size <= bounds["offset"], "member compressed extent exceeds data region")
                is_directory = item.is_dir()
                require(kind != stat.S_IFDIR or is_directory, "directory mode/name mismatch")
                require(not is_directory or item.file_size == 0, "nonempty directory member")
                require(not (is_directory and kind == stat.S_IFREG), "regular mode/directory name mismatch")
                csv_match = re.fullmatch(r"10-(\d{3})\.csv", pure.name)
                if not is_directory:
                    if csv_match:
                        study_id = str(int(csv_match[1]))
                        require(study_id not in csv_ids, "duplicate study CSV")
                        csv_ids.append(study_id)
                    else:
                        require(re.fullmatch(r"(?i).*readme.*\.(?:md|txt)", pure.name) is not None,
                                "unexpected non-CSV/non-readme payload")
                total += item.file_size
                require(total <= MAX_TOTAL, "expanded byte sum exceeds 32 GiB")
                result["members"].append({
                    "path": name, "directory": is_directory, "expanded_bytes": item.file_size,
                    "compressed_bytes": item.compress_size, "compression_method": item.compress_type,
                    "crc32_from_directory_only": f"{item.CRC:08x}", "header_offset": item.header_offset,
                    "flag_bits": item.flag_bits, "unix_mode": mode,
                    "study_id": str(int(csv_match[1])) if csv_match and not is_directory else None})
            require(len(csv_ids) == 171 and set(csv_ids) == set(expected_ids), "native CSV/metadata 171-ID mismatch")
            result["csv_count"] = len(csv_ids)
            result["expanded_bytes_from_directory"] = total
            result["max_member_expanded_bytes"] = max(i.file_size for i in infos)
        require(signature(os.fstat(handle.fileno())) == expected_stat, "archive changed during directory inspection")
    require(signature(ARCHIVE.stat()) == expected_stat, "archive path replaced during inspection")
    result["original_file_signature_unchanged"] = True
    result["status"] = "succeeded"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acquisition-receipt", type=Path, required=True)
    parser.add_argument("--receipt-sha256", required=True)
    parser.add_argument("--protocol-sha256", required=True)
    args = parser.parse_args()
    for value in (args.receipt_sha256, args.protocol_sha256):
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            parser.error("SHA256 arguments must be 64 lowercase hexadecimal characters")
    try:
        result = inspect(args.acquisition_receipt, args.receipt_sha256, args.protocol_sha256)
    except Exception as exc:
        result = {"schema": "dosei_original_directory_inventory_v1", "status": "failed",
                  "error_type": type(exc).__name__, "error": str(exc)[:1000],
                  "archive_path": str(ARCHIVE), "protocol_sha256": args.protocol_sha256,
                  "acquisition_receipt_path": str(args.acquisition_receipt),
                  "acquisition_receipt_sha256": args.receipt_sha256,
                  "csv_decompression_performed": False, "crc_verification_performed": False}
    raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8")
    require(len(raw) <= 1_048_576, "inventory output exceeds 1 MiB")
    output = DESTINATION / ("central-directory-inventory-" + uuid.uuid4().hex + ".json")
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    print(json.dumps({"status": result["status"], "output": str(output),
                      "csv_count": result.get("csv_count"),
                      "expanded_bytes_from_directory": result.get("expanded_bytes_from_directory"),
                      "error": result.get("error")}, indent=2))
    return 0 if result["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
