"""Original ZuCo2 sentence-content projection; no scientific admission implied.

Whole-file authentication reads each selected MAT file's bytes. HDF5 value
projection dereferences sentence UTF-16 content only, never EEG or gaze arrays.
Source field bindings and release pins must be supplied independently.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat

PEOPLE = ("YAC", "YAG", "YAK", "YDG", "YDR", "YFR", "YFS", "YHS", "YIS",
          "YLS", "YMD", "YMS", "YRH", "YRK", "YRP", "YSD", "YSL", "YTL")
CONDITIONS = ("NR", "TSR")
COUNTS = {"NR": 349, "TSR": 390}
MAX_CODE_UNITS = 10000
MAX_TEXT_BYTES = 16 * 1024 * 1024
PIN_FIELDS = {"person", "condition", "path", "bytes", "sha256",
              "sentence_group", "content_field"}


class ContentError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContentError(message)


def _unique(rows):
    out = {}
    for key, value in rows:
        require(key not in out, "duplicate JSON key")
        out[key] = value
    return out


def parse_json(raw):
    def reject(_):
        raise ContentError("nonfinite JSON number")
    return json.loads(raw, object_pairs_hook=_unique, parse_constant=reject)


def validate_manifest(document, max_source_bytes):
    require(type(max_source_bytes) is int and 0 < max_source_bytes < 2 ** 63,
            "explicit positive source-byte ceiling required")
    require(type(document) is dict and set(document) == {"schema", "containers"}
            and document["schema"] == "zuco2-presentation-content-input/v1",
            "exact input-manifest schema required")
    rows = document["containers"]
    require(type(rows) is list and len(rows) == 36, "complete36-container manifest required")
    expected = {(p, c) for p in PEOPLE for c in CONDITIONS}
    seen, paths, total = set(), set(), 0
    for row in rows:
        require(type(row) is dict and set(row) == PIN_FIELDS, "exact source-binding fields required")
        require(type(row["person"]) is str and type(row["condition"]) is str,
                "person and condition must be strings")
        key = (row["person"], row["condition"])
        require(key in expected and key not in seen, "unknown or duplicate source container")
        seen.add(key)
        require(type(row["path"]) is str and Path(row["path"]).is_absolute()
                and ".." not in Path(row["path"]).parts, "absolute ordinary source path required")
        path = str(Path(row["path"]))
        require(path not in paths, "source path reused across containers")
        paths.add(path)
        require(type(row["bytes"]) is int and row["bytes"] > 0, "positive exact source size required")
        require(type(row["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]),
                "exact source SHA256 required")
        group = row["sentence_group"]
        require(type(group) is str and re.fullmatch(r"/(?:[A-Za-z][A-Za-z0-9_]*)(?:/[A-Za-z][A-Za-z0-9_]*)*", group),
                "explicit ordinary HDF5 group path required")
        require(type(row["content_field"]) is str
                and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", row["content_field"]),
                "explicit content field name required")
        total += row["bytes"]
        require(total <= max_source_bytes, "source-byte ceiling exceeded before file access")
    require(seen == expected, "complete original cohort required")
    return sorted(rows, key=lambda r: (PEOPLE.index(r["person"]), CONDITIONS.index(r["condition"])))


def _identity(st):
    return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns


@contextmanager
def authenticated_file(row, observed_files):
    """Hash and parse the same opened inode; reject ordinary observable mutation."""
    path = Path(row["path"])
    require(not any(p.is_symlink() for p in (path, *path.parents)), "symlink source path refused")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_size == row["bytes"],
                "source is not the exact declared regular file")
        file_key = before.st_dev, before.st_ino
        require(file_key not in observed_files, "source inode reused across containers")
        observed_files.add(file_key)
        with os.fdopen(fd, "rb", closefd=False) as stream:
            digest, count = hashlib.sha256(), 0
            while True:
                raw = stream.read(min(1024 * 1024, row["bytes"] - count + 1))
                if not raw:
                    break
                count += len(raw)
                require(count <= row["bytes"], "source grew during authentication")
                digest.update(raw)
            require(count == row["bytes"] and digest.hexdigest() == row["sha256"],
                    "source identity mismatch")
            stream.seek(0)
            yield stream
            require(_identity(before) == _identity(os.fstat(fd)) == _identity(path.lstat()),
                    "source changed during projection")
    finally:
        os.close(fd)


def _hard_child(group, name, h5py):
    require(isinstance(group.get(name, getlink=True), h5py.HardLink),
            "HDF5 soft or external links refused")
    return group[name]


def _safe_dataset(dataset, h5py):
    require(isinstance(dataset, h5py.Dataset), "HDF5 dataset required")
    require(not dataset.is_virtual and not dataset.external, "virtual or external dataset refused")
    props = dataset.id.get_create_plist()
    require(all(props.get_filter(i)[0] in (1, 2, 3) for i in range(props.get_nfilters())),
            "nonstandard HDF5 filter refused")


def _matlab_char_attribute(dataset):
    """Inspect fixed scalar storage before materializing a source attribute."""
    require("MATLAB_class" in dataset.attrs, "MATLAB char binding required")
    attribute = dataset.attrs.get_id("MATLAB_class")
    try:
        dtype = attribute.dtype
        require(attribute.shape == () and dtype.kind == "S"
                and 0 < dtype.itemsize <= 16 and 0 < attribute.get_storage_size() <= 16,
                "tiny scalar fixed-length MATLAB class attribute required")
    finally:
        attribute.close()
    require(dataset.attrs["MATLAB_class"] == b"char", "MATLAB char binding required")


def read_manifest(path):
    """Capture at most65537 bytes from one verified ordinary opened inode."""
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), "ordinary manifest path required")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= 65536,
                "bounded regular input manifest required")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(65537)
        require(len(raw) <= 65536 and len(raw) == before.st_size,
                "manifest changed or exceeded bounded read")
        require(_identity(before) == _identity(os.fstat(fd)) == _identity(path.lstat()),
                "manifest changed during read")
        return raw
    finally:
        os.close(fd)


def project_hdf5(h, row):
    """Project content references only; all unknown bindings remain unqualified."""
    import h5py
    group = h
    for name in row["sentence_group"].strip("/").split("/"):
        group = _hard_child(group, name, h5py)
        require(isinstance(group, h5py.Group), "sentence-group binding is not a group")
    table = _hard_child(group, row["content_field"], h5py)
    _safe_dataset(table, h5py)
    count = COUNTS[row["condition"]]
    require(table.shape == (count, 1) and h5py.check_dtype(ref=table.dtype) is h5py.Reference,
            "complete original sentence-reference column required")
    result = []
    for index in range(count):
        ref = table[index, 0]
        require(bool(ref), "null sentence-content reference")
        content = h[ref]
        _safe_dataset(content, h5py)
        require(content.dtype.kind == "u" and content.dtype.itemsize == 2
                and content.ndim == 2 and 1 in content.shape
                and 0 < content.size <= MAX_CODE_UNITS, "bounded UTF16 sentence column or row required")
        _matlab_char_attribute(content)
        # Convert code-unit byte order explicitly and preserve literal whitespace,
        # punctuation and quotes. Normalization belongs to the downstream join.
        text = content[()].astype("<u2", copy=False).reshape(-1).tobytes().decode("utf-16-le", errors="strict")
        require(bool(text) and "\x00" not in text, "empty or NUL-containing source text refused")
        result.append({"source_index": index, "text": text})
    return {"person": row["person"], "condition": row["condition"],
            "source_bytes": row["bytes"], "source_sha256": row["sha256"], "presentations": result}


def project_container(row, observed_files):
    import h5py
    with authenticated_file(row, observed_files) as stream:
        with h5py.File(stream, "r") as h:
            return project_hdf5(h, row)


def project_cohort(document, max_source_bytes):
    rows = validate_manifest(document, max_source_bytes)
    containers, observed_files, text_bytes = [], set(), 0
    for row in rows:
        container = project_container(row, observed_files)
        text_bytes += sum(len(p["text"].encode("utf-8")) for p in container["presentations"])
        require(text_bytes <= MAX_TEXT_BYTES, "content-byte ceiling exceeded; no partial cohort emitted")
        containers.append(container)
    return {"schema": "zuco2-presentation-content-v1", "containers": containers}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--max-source-bytes", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True, help="fresh operator-owned directory outside the repository")
    args = parser.parse_args(argv)
    raw = read_manifest(args.manifest)
    document = parse_json(raw)
    # Refuse Git checkout destinations without depending on installation depth.
    output = args.output.absolute()
    require(not any(p.is_symlink() for p in (output, *output.parents)), "ordinary output path required")
    require(not any((p / ".git").exists() for p in (output, *output.parents)), "operator output must be outside Git")
    require(not output.exists() and output.parent.is_dir(), "fresh output under existing operator parent required")
    result = project_cohort(document, args.max_source_bytes)
    result_raw = (json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    report = {
        "schema": "zuco2-presentation-content-projection-receipt/v1",
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "source_bytes_hashed": sum(r["bytes"] for r in document["containers"]),
        "source_containers": 36, "source_people": 18, "presentations": 13302,
        "content_file": {"path": "presentation_content.json", "bytes": len(result_raw),
                         "sha256": hashlib.sha256(result_raw).hexdigest()},
        "source_bindings": [{k: v for k, v in r.items() if k != "path"}
                            for r in validate_manifest(document, args.max_source_bytes)],
        "qualification": "authenticated_supplied_bindings_only",
        "independent_source_binding_qualification": False,
        "paper_duplicate_obligations_reconciled": False,
        "scientific_readiness_promoted": False,
        "limits": ["Whole-file hashing reads physiological-file bytes; HDF5 value projection reads sentence text only.",
                   "Operator-supplied pins and field bindings are not independently established release provenance.",
                   "Original content remains operator-private; apply both material dialect joins without selecting favorable counts.",
                   "No EEG/gaze representation, candidate delivery, isolation or scientific result is qualified."],
    }
    output.mkdir(mode=0o700)
    for name, body in (("presentation_content.json", result_raw),
                       ("projection_receipt.json", (json.dumps(report, indent=2) + "\n").encode())):
        with (output / name).open("xb") as stream:
            stream.write(body)
    print(json.dumps({"containers": 36, "presentations": 13302, "readiness_promoted": False}))


if __name__ == "__main__":
    main()
