"""Prospective FCSTAB bounded output IO; adapted from reviewed PR194 reader.

No source, oracle, stager, statistical kernel or historical-bank imports.
"""
from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
import io
import json
import os
from pathlib import Path
import stat
import zipfile

import numpy as np

REQUIRED = ("connectivity.npz", "stability.csv", "selection_evidence.json",
            "summary.json", "findings.md")
FAILURE = "failure_report.json"
CAPS = {"csv": 2**20, "evidence": 16*2**20, "summary": 8*2**20,
        "text": 65536, "npz": 64*2**20, "expanded": 128*2**20,
        "total": 96*2**20, "entries": 1000, "members": 16,
        "header": 16384, "ndim": 32, "rows": 100000,
        "field": 2**20, "depth": 64}
INT_MIN, INT_MAX = -(2**63), 2**63-1


class ArtifactError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ArtifactError(message)


def guarded_path(path, *, directory=False):
    path = Path(path).absolute()
    for node in reversed((path, *path.parents)):
        try:
            mode = node.lstat().st_mode
        except OSError as exc:
            raise ArtifactError("missing/inaccessible path") from exc
        require(not stat.S_ISLNK(mode), "symlink path")
        if node != path:
            require(stat.S_ISDIR(mode), "non-directory ancestor")
    resolved = path.resolve(strict=True)
    mode = resolved.lstat().st_mode
    require(stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode), "wrong file kind")
    return resolved


def identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def read_bytes(path, maximum):
    path = guarded_path(path)
    before = path.lstat()
    require(0 < before.st_size <= maximum, "empty/oversized artifact")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        require(identity(os.fstat(handle.fileno())) == identity(before), "file replaced before read")
        payload = handle.read(maximum+1)
        require(len(payload) == before.st_size and len(payload) <= maximum, "file size changed")
        require(identity(os.fstat(handle.fileno())) == identity(before), "file changed while reading")
    require(identity(path.lstat()) == identity(before), "file replaced after read")
    return payload


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def finite_json(value, depth=0):
    require(depth <= CAPS["depth"], "JSON nesting limit")
    if isinstance(value, Decimal):
        require(value.is_finite() and abs(value) <= Decimal(str(np.finfo(float).max)), "JSON numeric range")
    elif isinstance(value, float):
        require(np.isfinite(value), "nonfinite JSON number")
    elif isinstance(value, dict):
        for child in value.values(): finite_json(child, depth+1)
    elif isinstance(value, list):
        for child in value: finite_json(child, depth+1)


def parse_json(payload):
    def bad_constant(token):
        raise ArtifactError("nonfinite JSON token: "+token)
    try:
        result = json.loads(payload.decode("utf-8-sig"), object_pairs_hook=unique_pairs,
                            parse_float=Decimal, parse_constant=bad_constant)
        finite_json(result)
    except ArtifactError:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ArtifactError("invalid JSON") from exc
    require(isinstance(result, dict), "JSON root must be object")
    return result


def integer(value, *, json_number=False):
    require(not isinstance(value, (bool, np.bool_)), "Boolean is not integer")
    allowed = (int, float, Decimal) if json_number else (str, int, float, Decimal, np.integer, np.floating)
    require(isinstance(value, allowed), "integer must be numeric" if json_number else "invalid integer token")
    try:
        d = Decimal(str(value))
        require(d.is_finite() and INT_MIN <= d <= INT_MAX, "integer range/finite")
        require(d == d.to_integral_value(), "fractional integer")
    except (InvalidOperation, ValueError, OverflowError) as exc:
        raise ArtifactError("invalid integer") from exc
    return int(d)


def real(value, *, json_number=False):
    require(not isinstance(value, (bool, np.bool_)), "Boolean is not real")
    allowed = (int, float, Decimal) if json_number else (str, int, float, Decimal, np.integer, np.floating)
    require(isinstance(value, allowed), "JSON real must be numeric" if json_number else "invalid real token")
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise ArtifactError("invalid real") from exc
    require(np.isfinite(result), "nonfinite real")
    return result


def parse_csv(payload):
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ArtifactError("invalid CSV encoding") from exc
    require("\x00" not in text, "NUL in CSV")
    previous = csv.field_size_limit(CAPS["field"])
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
        csv.field_size_limit(previous)
    return rows


def checked_array(array):
    require(isinstance(array, np.ndarray), "not ndarray")
    require(array.dtype.fields is None and array.dtype.kind in "biufUS", "unsupported array dtype")
    if array.dtype.kind == "f": require(np.isfinite(array).all(), "nonfinite NPZ array")
    if array.dtype.kind == "S":
        try: np.char.decode(array, "utf-8")
        except UnicodeError as exc: raise ArtifactError("invalid NPZ text encoding") from exc
    return array


def integer_array(array):
    checked_array(array)
    require(array.dtype.kind in "iuf", "integer axis requires numeric nonboolean dtype")
    if array.dtype.kind == "f":
        require(np.all(array >= INT_MIN) and np.all(array < 2**63), "integer axis overflow")
        require(np.equal(array, np.floor(array)).all(), "fractional integer axis")
    elif array.dtype.kind == "u":
        require(np.all(array <= INT_MAX), "unsigned axis overflow")
    return array.astype(np.int64, copy=False)


def parse_npz(payload):
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            require(0 < len(names) <= CAPS["members"], "NPZ member cap")
            require(len(names) == len(set(names)), "duplicate NPZ members")
            require(sum(item.file_size for item in infos) <= CAPS["expanded"], "NPZ expanded cap")
            for item in infos:
                require(item.filename.endswith(".npy") and "/" not in item.filename and "\\" not in item.filename
                        and item.filename != ".npy", "unsafe NPZ name")
                require(item.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), "ZIP compression")
                require(not item.flag_bits & 1, "encrypted NPZ")
                require(stat.S_IFMT(item.external_attr >> 16) in (0, stat.S_IFREG), "nonregular NPZ member")
            arrays = {}
            for item in infos:
                raw = archive.read(item)
                stream = io.BytesIO(raw)
                version = np.lib.format.read_magic(stream)
                require(version in ((1,0), (2,0)), "NPY version")
                reader = np.lib.format.read_array_header_1_0 if version == (1,0) else np.lib.format.read_array_header_2_0
                shape, fortran, dtype = reader(stream, max_header_size=CAPS["header"])
                require(dtype.fields is None and dtype.kind in "biufUS" and dtype.itemsize > 0, "NPY dtype")
                require(len(shape) <= CAPS["ndim"] and all(type(d) is int and d >= 0 for d in shape), "NPY shape")
                count = 1
                for dimension in shape:
                    count *= dimension
                    require(count <= CAPS["expanded"], "NPY element cap")
                size = count*dtype.itemsize
                require(size <= CAPS["expanded"] and stream.tell()+size == len(raw), "NPY payload/shape mismatch")
                array = np.frombuffer(raw, dtype=dtype, count=count, offset=stream.tell())
                array = array.reshape(shape, order="F" if fortran else "C").copy()
                arrays[item.filename[:-4]] = checked_array(array)
            return arrays
    except ArtifactError:
        raise
    except (zipfile.BadZipFile, EOFError, UnicodeError, OSError, ValueError) as exc:
        raise ArtifactError("invalid NPZ") from exc


def read_artifacts(output_dir):
    root = guarded_path(output_dir, directory=True)
    require(not os.path.lexists(root/FAILURE), "authoritative failure marker")
    total = entries = 0
    for path in root.rglob("*"):
        entries += 1
        require(entries <= CAPS["entries"], "output entry cap")
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode), "nonregular output inventory")
        if stat.S_ISREG(info.st_mode): total += info.st_size
        require(total <= CAPS["total"], "entire output byte cap")
    result = {}
    for name in REQUIRED:
        if name.endswith(".npz"): result[name] = parse_npz(read_bytes(root/name, CAPS["npz"]))
        elif name.endswith(".csv"): result[name] = parse_csv(read_bytes(root/name, CAPS["csv"]))
        elif name.endswith(".json"):
            cap = CAPS["summary" if name == "summary.json" else "evidence"]
            result[name] = parse_json(read_bytes(root/name, cap))
        else:
            try: result[name] = read_bytes(root/name, CAPS["text"]).decode("utf-8-sig")
            except UnicodeError as exc: raise ArtifactError("invalid findings encoding") from exc
            require(result[name].strip(), "empty findings")
    return result
