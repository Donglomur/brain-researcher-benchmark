"""Grader-owned immutable identity and strict serialization; no source helper imports."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import csv
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat

from category_statistics import require

SOURCE_SHA256 = "3819f2b5e9403f184b94be7d1374476c964c08c054763ec7b8d40cf6bbf7e7b9"
METHOD_SHA256 = "945f61392b72f065fd5c6067b8ae578a4168986dd01fe8c21e1c4900e51842ac"
LOW, HIGH = -(2**63), 2**63-1


def safe_path(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        require(not part.is_symlink(), f"Symlink path: {part}")
    return path.resolve(strict=False)


def regular(path):
    path = safe_path(path)
    require(stat.S_ISREG(path.stat().st_mode), f"Not a regular file: {path}")
    return path


def finite_json(value):
    if isinstance(value, dict):
        for v in value.values(): finite_json(v)
    elif isinstance(value, list):
        for v in value: finite_json(v)
    elif isinstance(value, float):
        require(math.isfinite(value), "Nonfinite JSON")


def parse_json(body):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    def invalid(token):
        raise AssertionError(f"Nonfinite JSON token: {token}")
    result = json.loads(body, object_pairs_hook=pairs, parse_constant=invalid)
    finite_json(result)
    return result


def read_bytes(path, maximum):
    path = regular(path)
    require(path.stat().st_size <= maximum, "File size bound")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), "Regular file required")
        body = stream.read(maximum+1)
    require(len(body) <= maximum, "File size bound")
    return body


def json_load(path):
    return parse_json(read_bytes(path, 32_000_000))


def authenticated_json(path, expected):
    body = read_bytes(path, 2_000_000)
    require(hashlib.sha256(body).hexdigest() == expected, "Frozen JSON identity mismatch")
    return parse_json(body)


def integer(value):
    require(not isinstance(value, bool), "Boolean is not an integer")
    require(type(value) in (int, float, str), "Integer type required")
    try:
        number = Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise AssertionError("Invalid integer") from exc
    require(number.is_finite() and LOW <= number <= HIGH, "Nonfinite/overflow integer")
    require(number == number.to_integral_value(), "Fractional integer")
    return int(number)


def number(value):
    require(type(value) in (int, float, str), "Real number required")
    try: result = float(value)
    except (ValueError, OverflowError) as exc: raise AssertionError("Invalid real number") from exc
    require(math.isfinite(result), "Nonfinite real number")
    return result


def flag(value):
    require(isinstance(value, str) and value.lower() in ("0", "1", "true", "false"), "Invalid CSV Boolean")
    return value.lower() in ("1", "true")


def verify_file(path, size, expected):
    path = regular(path); before = path.stat()
    require(before.st_size == size, "Source file size mismatch")
    checksum, total = hashlib.sha256(), 0
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        opened = os.fstat(stream.fileno())
        require(stat.S_ISREG(opened.st_mode) and opened.st_size == size and
                (opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino), "Source changed during opening")
        while True:
            block = stream.read(min(1 << 20, size-total+1))
            if not block: break
            total += len(block); require(total <= size, "Source grew during verification")
            checksum.update(block)
        after = os.fstat(stream.fileno())
    require(all(getattr(opened, k) == getattr(after, k) for k in
                ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")), "Source changed during verification")
    require(total == size and checksum.hexdigest() == expected, "Original source SHA256 mismatch")


def authenticate_source(source_dir):
    root = safe_path(source_dir)
    require(root.is_dir(), "Source directory required")
    manifest = authenticated_json(root/"source_manifest.json", SOURCE_SHA256)
    rows = manifest["files"]
    require(isinstance(rows, list) and len(rows) == 87 and type(manifest["n_files"]) is int
            and manifest["n_files"] == 87, "Complete 87-file manifest required")
    expected, directories, total = {"source_manifest.json"}, set(), 0
    for row in rows:
        name = row["path"]
        require(isinstance(name, str) and name and not name.startswith("/") and "\\" not in name and
                "\x00" not in name and all(p not in ("", ".", "..") for p in name.split("/")), "Unsafe manifest path")
        require(name not in expected and row["role"] == "session_nwb", "Duplicate/unknown source record")
        expected.add(name)
        directories.update(str(p) for p in PurePosixPath(name).parents if str(p) != ".")
        size, digest = row["size_bytes"], row["sha256"]
        require(type(size) is int and size > 0, "Invalid source size")
        require(isinstance(digest, str) and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), "Invalid SHA256")
        total += size
    require(type(manifest["total_size_bytes"]) is int and total == manifest["total_size_bytes"], "Source byte total")
    files = set()
    for path in root.rglob("*"):
        name, mode = path.relative_to(root).as_posix(), path.lstat().st_mode
        if stat.S_ISDIR(mode): require(name in directories, "Unexpected source directory")
        else:
            require(stat.S_ISREG(mode) and name in expected, "Unexpected/nonregular source file")
            files.add(name)
    require(files == expected, "Missing original source file")
    for row in rows: verify_file(root/row["path"], row["size_bytes"], row["sha256"])
    return root, manifest


def csv_load(path, columns):
    with regular(path).open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames is not None and len(set(reader.fieldnames)) == len(reader.fieldnames), "Missing/duplicate CSV headers")
        require(set(columns) <= set(reader.fieldnames), "Missing CSV column")
        rows = list(reader)
    require(all(None not in row and all(row[k] is not None for k in columns) for row in rows), "Malformed CSV rows")
    return rows


def destinations(paths, protected):
    paths = [safe_path(p) for p in paths]
    protected = [safe_path(p) for p in protected]
    require(len(set(paths)) == len(paths), "Evidence destinations collide")
    for path in paths:
        require(not os.path.lexists(path), "Refuse existing evidence")
        for other in protected:
            require(path != other and path not in other.parents and other not in path.parents, "Evidence/input overlap")
        for other in paths:
            require(path == other or (path not in other.parents and other not in path.parents), "Nested evidence destinations")
    return paths
