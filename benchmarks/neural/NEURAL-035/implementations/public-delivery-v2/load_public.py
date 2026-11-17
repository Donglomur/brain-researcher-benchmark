"""Load the complete NEURAL-035 public view without opening query observations.

This version preserves the v1 NPZ/manifest format and return shape. It validates
the whole public manifest before reading any session archive, then checks NPY
headers and exact data lengths before NumPy can allocate their declared shapes.
"""
from __future__ import annotations

import ast
import importlib.util
import io
from pathlib import Path
import re
import struct
import zipfile


# Reuse the original ordinary-file capture implementation without installing a
# generic io_utils alias in sys.modules or altering the participant import path.
_IO_PATH = Path(__file__).resolve().parents[1] / "delivery-source" / "io_utils.py"
_SPEC = importlib.util.spec_from_file_location("_neural035_delivery_io", _IO_PATH)
safe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(safe)

SESSION_FIELDS = {"session_id", "cell_ids", "file", "bytes", "sha256",
                  "calibration_starts_seconds", "validation_starts_seconds", "queries"}
ARCHIVE_CAP = 20_000_000
HEADER_CAP = 4096


def _opaque(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _starts(value, expected):
    return (type(value) is list and len(value) == len(expected)
            and all(type(x) is int for x in value) and value == expected)


def validate_manifest(value):
    """Require every original cell and chronological query before array access.

    Cell identity is session-local. Repeated cell IDs across sessions are not
    evidence of cross-context correspondence and are not forbidden here.
    """
    safe.need(type(value) is dict and set(value) == {"schema", "sessions"}
              and value["schema"] == "neural035-public-v1", "exact public schema")
    rows = value["sessions"]
    safe.need(type(rows) is list and len(rows) == 14, "all 14 public sessions")
    sessions, queries, cell_count = set(), set(), 0
    for row in rows:
        safe.need(type(row) is dict and set(row) == SESSION_FIELDS,
                  "exact public session fields")
        sid = row["session_id"]
        safe.need(_opaque(sid) and sid not in sessions, "unique opaque session")
        sessions.add(sid)
        cells = row["cell_ids"]
        safe.need(type(cells) is list and 2 <= len(cells) <= 1012
                  and all(_opaque(cell) for cell in cells)
                  and len(set(cells)) == len(cells), "ordered session-local cell identities")
        cell_count += len(cells)
        safe.need(row["file"] == sid + ".npz", "session archive identity")
        safe.need(type(row["bytes"]) is int and 0 < row["bytes"] <= ARCHIVE_CAP
                  and _opaque(row["sha256"]), "bounded archive content descriptor")
        safe.need(_starts(row["calibration_starts_seconds"], [0, 30, 60, 90])
                  and _starts(row["validation_starts_seconds"], [150]),
                  "original calibration and validation windows")
        pending = row["queries"]
        safe.need(type(pending) is list and len(pending) == 2, "two future query blocks")
        for query, start in zip(pending, [210, 270], strict=True):
            safe.need(type(query) is dict and set(query) == {"query_id", "start_seconds"}
                      and type(query["start_seconds"]) is int
                      and query["start_seconds"] == start, "original ordered query windows")
            qid = query["query_id"]
            safe.need(_opaque(qid) and qid not in queries, "unique opaque query")
            queries.add(qid)
    safe.need(cell_count == 1012 and len(queries) == 28,
              "complete 1012 session-local cells and 28 queries")
    return value


def _npy_header(raw, shape):
    """Validate bounded NPY metadata without trusting its allocation request."""
    safe.need(len(raw) >= 10 and raw[:6] == b"\x93NUMPY", "NPY magic")
    version = tuple(raw[6:8])
    if version == (1, 0):
        offset = 10
        length = struct.unpack("<H", raw[8:10])[0]
    else:
        safe.need(version in {(2, 0), (3, 0)} and len(raw) >= 12, "supported NPY format")
        offset = 12
        length = struct.unpack("<I", raw[8:12])[0]
    safe.need(0 < length <= HEADER_CAP and offset + length <= len(raw), "bounded NPY header")
    header = raw[offset:offset + length]
    safe.need(header.endswith(b"\n"), "complete NPY header line")
    try:
        tree = ast.parse(header.decode("utf-8" if version == (3, 0) else "latin1").strip(), mode="eval")
        safe.need(isinstance(tree.body, ast.Dict), "NPY header dictionary")
        keys = [ast.literal_eval(key) for key in tree.body.keys]
        safe.need(len(keys) == 3 and set(keys) == {"descr", "fortran_order", "shape"},
                  "exact unique NPY header keys")
        info = ast.literal_eval(tree)
    except (SyntaxError, TypeError, UnicodeError, RecursionError) as exc:
        raise ValueError("invalid NPY header") from exc
    safe.need(type(info["descr"]) is str and info["descr"] in {"<f8", ">f8", "=f8"}
              and type(info["fortran_order"]) is bool, "scalar float64 NPY data")
    actual = info["shape"]
    safe.need(type(actual) is tuple and all(type(x) is int for x in actual)
              and actual == shape, "exact NPY public trace geometry")
    expected_bytes = shape[0] * shape[1] * shape[2] * 8
    safe.need(len(raw) == offset + length + expected_bytes, "exact NPY payload length")
    return info


def _archive_members(raw, cells):
    """Decompress only the two bounded public members; reject hidden arrays."""
    expected = {"calibration.npy": (4, 300, cells), "validation.npy": (1, 300, cells)}
    result = {}
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = archive.infolist()
            safe.need(len(members) == 2 and {m.filename for m in members} == set(expected),
                      "exact public archive members, no query arrays")
            for member in members:
                shape = expected[member.filename]
                cap = shape[0] * shape[1] * cells * 8 + HEADER_CAP + 12
                safe.need(not member.flag_bits & 1 and 0 < member.file_size <= cap
                          and member.compress_type in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED},
                          "bounded unencrypted public NPY member")
                with archive.open(member) as source:
                    body = source.read(cap + 1)
                safe.need(len(body) == member.file_size, "complete bounded NPY member")
                _npy_header(body, shape)
                result[member.filename.removesuffix(".npy")] = body
    except (zipfile.BadZipFile, EOFError, NotImplementedError) as exc:
        raise ValueError("invalid public NPZ archive") from exc
    return result


def load(folder, np):
    """Return v1-compatible metadata/calibration/validation rows for all sessions.

    `np` is the caller's qualified NumPy module. This loader performs neither
    fitting nor grading and does not resolve an evaluator/private-data root.
    """
    folder = Path(folder)
    manifest = validate_manifest(safe.strict(safe.read(folder / "MANIFEST.json", 2_000_000)))
    result = []
    for row in manifest["sessions"]:
        raw = safe.captured(folder, {"path": row["file"], "bytes": row["bytes"],
                                     "sha256": row["sha256"]}, ARCHIVE_CAP)
        members = _archive_members(raw, len(row["cell_ids"]))
        arrays = {}
        for name, body in members.items():
            x = np.load(io.BytesIO(body), allow_pickle=False, max_header_size=HEADER_CAP)
            safe.need(x.dtype == np.dtype("float64") and np.isfinite(x).all(),
                      "finite native float64 public traces")
            arrays[name] = x
        result.append({"metadata": row, **arrays})
    return result
