"""FCMATUR bounded five-artifact I/O, adapted from qualified PR194.

No source, oracle, stager or bank imports. Scientific acceptance is separate.
"""
from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
import io
import json
import os
from pathlib import Path
import stat

import numpy as np


REQUIRED = ("connectivity.csv", "connectivity_age.json", "sensitivity.json",
            "run_metadata.json", "findings.md")
FAILURE = "failure_report.json"
CAPS = {"csv": 16 * 2**20, "json": 16 * 2**20, "text": 2**20,
        "rows": 100000, "field": 2**20,
        "depth": 64}
INT_MIN, INT_MAX = -(2**63), 2**63 - 1


class ArtifactError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ArtifactError(message)


def guarded_path(path, *, directory=False):
    """Reject lexical symlink traversal before normalizing '..'."""
    path = Path(path).absolute()
    for node in reversed((path, *path.parents)):
        try:
            mode = node.lstat().st_mode
        except OSError as exc:
            raise ArtifactError(f"missing/inaccessible path: {node}") from exc
        require(not stat.S_ISLNK(mode), f"symlink path: {node}")
        if node != path:
            require(stat.S_ISDIR(mode), f"non-directory ancestor: {node}")
    resolved = path.resolve(strict=True)
    mode = resolved.lstat().st_mode
    require(stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode),
            f"wrong file kind: {resolved}")
    return resolved


def identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def read_bytes(path, maximum):
    path = guarded_path(path)
    before = path.lstat()
    require(0 < before.st_size <= maximum, f"empty/oversized artifact: {path}")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        require(stat.S_ISREG(os.fstat(handle.fileno()).st_mode), "not regular fd")
        require(identity(os.fstat(handle.fileno())) == identity(before), "file replaced before read")
        payload = handle.read(maximum + 1)
        require(len(payload) == before.st_size and len(payload) <= maximum, "file size changed")
        require(identity(os.fstat(handle.fileno())) == identity(before), "file changed while reading")
    require(identity(path.lstat()) == identity(before), "file replaced after read")
    return payload


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def finite_json(value, depth=0):
    require(depth <= CAPS["depth"], "JSON nesting limit")
    if isinstance(value, Decimal):
        require(value.is_finite() and abs(value) <= Decimal(str(np.finfo(float).max)),
                "nonfinite/out-of-float64-range JSON number")
    elif isinstance(value, float):
        require(np.isfinite(value), "nonfinite JSON number")
    elif isinstance(value, dict):
        for child in value.values():
            finite_json(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            finite_json(child, depth + 1)


def parse_json(payload):
    def bad_constant(token):
        raise ArtifactError(f"nonfinite JSON token: {token}")
    try:
        result = json.loads(payload.decode("utf-8-sig"), object_pairs_hook=unique_pairs,
                            parse_float=Decimal, parse_constant=bad_constant)
        finite_json(result)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ArtifactError("invalid JSON") from exc
    require(isinstance(result, dict), "JSON top level must be object")
    return result


def integer(value, *, json_number=False):
    require(not isinstance(value, (bool, np.bool_)), "Boolean is not integer")
    if json_number:
        require(isinstance(value, (int, float, Decimal)), "JSON integer must be numeric")
    else:
        require(isinstance(value, (str, int, float, Decimal, np.integer, np.floating)),
                "integer requires real number or CSV token")
    try:
        d = Decimal(str(value))
        require(d.is_finite() and INT_MIN <= d <= INT_MAX, "integer range/finite")
        require(d == d.to_integral_value(), "fractional integer")
    except (InvalidOperation, ValueError, OverflowError) as exc:
        raise ArtifactError("invalid integer") from exc
    return int(d)


def real(value, *, json_number=False):
    require(not isinstance(value, (bool, np.bool_)), "Boolean is not real")
    if json_number:
        require(isinstance(value, (int, float, Decimal)), "JSON real must be numeric")
    else:
        require(isinstance(value, (str, int, float, Decimal, np.integer, np.floating)),
                "real requires number or CSV token")
    try:
        converted = float(value)
    except (ValueError, OverflowError) as exc:
        raise ArtifactError("invalid real") from exc
    require(np.isfinite(converted), "nonfinite real")
    return converted


def csv_boolean(token):
    require(isinstance(token, str), "CSV Boolean must be literal text")
    token = token.lower()
    require(token in ("0", "1", "true", "false"), "invalid CSV Boolean literal")
    return token in ("1", "true")


def parse_csv(payload):
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ArtifactError("invalid CSV encoding") from exc
    require("\x00" not in text, "NUL in CSV")
    old_limit = csv.field_size_limit(CAPS["field"])
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        names = reader.fieldnames
        require(names and all(names) and len(names) == len(set(names)), "missing/duplicate CSV columns")
        rows = []
        for row in reader:
            require(len(rows) < CAPS["rows"], "CSV row cap")
            require(None not in row and all(x is not None for x in row.values()), "ragged CSV row")
            rows.append(row)
    except csv.Error as exc:
        raise ArtifactError("invalid CSV") from exc
    finally:
        csv.field_size_limit(old_limit)
    return rows


def keyed_rows(rows, columns, *, integer_columns=()):
    """Declare integer key columns; never normalize literal participant IDs."""
    require(set(integer_columns).issubset(columns), "integer key not in key columns")
    result = {}
    for row in rows:
        require(all(key in row for key in columns), "missing key columns")
        require(all(row[name] != "" for name in columns), "empty row key")
        key = tuple(integer(row[name]) if name in integer_columns else row[name]
                    for name in columns)
        require(key not in result, "duplicate row key")
        result[key] = row
    return result


def read_artifacts(output_dir):
    """Read only five required artifacts. No scientific or completeness claim."""
    root = guarded_path(output_dir, directory=True)
    require(not os.path.lexists(root / FAILURE), "authoritative failure_report.json present")
    total, n_entries = 0, 0
    for path in root.rglob("*"):
        n_entries += 1
        require(n_entries <= 1000, "output inventory entry cap")
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode), "nonregular output inventory")
        if stat.S_ISREG(info.st_mode): total += info.st_size
        require(total <= 64*2**20, "total output byte cap")
    result = {}
    for name in REQUIRED:
        if name.endswith(".csv"):
            result[name] = parse_csv(read_bytes(root / name, CAPS["csv"]))
        elif name.endswith(".json"):
            result[name] = parse_json(read_bytes(root / name, CAPS["json"]))
        else:
            try:
                result[name] = read_bytes(root / name, CAPS["text"]).decode("utf-8-sig")
            except UnicodeError as exc:
                raise ArtifactError("invalid findings encoding") from exc
            require(result[name].strip(), "empty findings")
    require(not os.path.lexists(root / FAILURE), "authoritative failure_report.json present")
    return result
