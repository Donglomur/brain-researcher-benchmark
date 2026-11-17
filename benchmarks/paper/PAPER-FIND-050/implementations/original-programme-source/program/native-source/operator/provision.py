"""Offline exact-local-asset verification and bounded NPZ header census. No download.

This command does not decode neural arrays. An explicit expanded-member ceiling
must be selected by the operator; no archive is extracted or copied.
"""
import argparse
import ast
import hashlib
import json
import os
import re
import stat
import struct
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def need(ok, message):
    if not ok:
        raise ValueError(message)


def header(stream):
    need(stream.read(6) == b"\x93NUMPY", "NPY magic")
    version = stream.read(2)
    need(version in (b"\x01\x00", b"\x02\x00", b"\x03\x00"), "NPY version")
    n = 2 if version == b"\x01\x00" else 4
    raw = stream.read(n)
    need(len(raw) == n, "Complete NPY length")
    length = int.from_bytes(raw, "little")
    need(0 < length <= 65536, "Bounded NPY header")
    raw = stream.read(length)
    need(len(raw) == length, "Complete NPY header")
    obj = ast.literal_eval(raw.decode("utf-8" if version == b"\x03\x00" else "latin1"))
    need(type(obj) is dict and set(obj) == {"descr", "fortran_order", "shape"}, "NPY header keys")
    need(type(obj["shape"]) is tuple and len(obj["shape"]) <= 4 and
         all(type(x) is int and 0 <= x <= 1000000000 for x in obj["shape"]), "Finite NPY shape")
    need(type(obj["fortran_order"]) is bool, "NPY memory order")
    return {"dtype": obj["descr"], "shape": list(obj["shape"]), "fortran_order": obj["fortran_order"],
            "header_bytes": 8 + n + length}


def decoded_fields(modality):
    need(modality in ("calcium", "ephys"), "Exact source modality")
    return {"sp", "xpos", "ypos", "tstart"} if modality == "calcium" else {"st", "clu", "ypos", "iprobe"}


def numeric_extent(h, member_bytes):
    # No NumPy import/allocation: reconcile every decoded numeric field before
    # np.load can trust its declared shape. Object/string extras stay descriptive.
    dtype = h["dtype"]
    m = re.fullmatch(r"[<>=|]([biufc])([0-9]+)", dtype) if type(dtype) is str else None
    need(m is not None, "Decoded NPY field has primitive numeric dtype")
    kind, itemsize = m.group(1), int(m.group(2))
    allowed = {"b": {1}, "i": {1, 2, 4, 8}, "u": {1, 2, 4, 8}, "f": {2, 4, 8, 16}, "c": {8, 16, 32}}
    need(itemsize in allowed[kind], "Supported primitive numeric itemsize")
    count = 1
    for dimension in h["shape"]:
        count *= dimension
    payload = count * itemsize
    need(h["header_bytes"] + payload == member_bytes, "Exact numeric NPY shape/itemsize/member extent")
    return payload


def inspect_file(path, asset, max_expanded_bytes, numeric_fields):
    path = Path(path)
    need(all(not p.is_symlink() for p in (path, *path.parents)), "Unlinked local source")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == asset["bytes"], "Exact ordinary source size")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            md5, sha = hashlib.md5(), hashlib.sha256()
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                md5.update(chunk)
                sha.update(chunk)
            need(md5.hexdigest() == asset["provider_md5"], "Exact provider content identity")
            stream.seek(0)
            with zipfile.ZipFile(stream) as z:
                members = z.infolist()
                need(0 < len(members) <= 128 and len({m.filename for m in members}) == len(members), "Bounded unique archive members")
                need(sum(m.file_size for m in members) <= max_expanded_bytes, "Selected expanded extent ceiling")
                rows = []
                for member in members:
                    need(member.filename.endswith(".npy") and "/" not in member.filename and "\\" not in member.filename,
                         "Flat NPZ member names")
                    need(not member.flag_bits & 1 and member.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), "Supported nonencrypted NPZ")
                    with z.open(member) as f:
                        h = header(f)
                    selected = member.filename[:-4] in numeric_fields
                    payload = numeric_extent(h, member.file_size) if selected else None
                    rows.append({"name": member.filename, "expanded_bytes": member.file_size, **h,
                                 "decoded_field_extent_verified": selected, "numeric_payload_bytes": payload})
        after = os.fstat(fd)
        named = path.lstat()
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")
        need(all(getattr(before, k) == getattr(after, k) == getattr(named, k) for k in fields), "Stable source through census")
        return {"session_id": asset["session_id"], "filename": asset["filename"], "bytes": before.st_size,
                "sha256": sha.hexdigest(), "provider_md5": md5.hexdigest(), "members": rows,
                "expanded_bytes": sum(x["expanded_bytes"] for x in rows), "neural_arrays_decoded": False}
    finally:
        os.close(fd)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-root", required=True)
    p.add_argument("--session", help="One exact source session for incremental census; absence requires all29")
    p.add_argument("--max-expanded-bytes-per-file", required=True, type=int)
    p.add_argument("--max-compressed-total-bytes", required=True, type=int)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    need(a.max_expanded_bytes_per_file > 0 and a.max_compressed_total_bytes > 0, "Positive operator ceilings")
    inventory = json.loads((ROOT / "public/ASSETS.json").read_text())["assets"]
    sessions = {x["session_id"]: x for x in json.loads((ROOT / "public/COHORT.json").read_text())["sessions"]}
    selected = [x for x in inventory if a.session is None or x["session_id"] == a.session]
    need(bool(selected) and sum(x["bytes"] for x in selected) <= a.max_compressed_total_bytes, "Exact selection within cap")
    records = [inspect_file(Path(a.data_root) / x["filename"], x, a.max_expanded_bytes_per_file,
                            decoded_fields(sessions[x["session_id"]]["modality"])) for x in selected]
    out = {"schema": "critical_init_local_census_v1", "records": records,
           "all29_present": len(records) == 29, "status": "header_census_only_not_analysis_ready",
           "scientific_outputs_computed": False, "raw_copy_or_acquisition": False}
    with open(a.output, "x", encoding="utf-8") as f:
        json.dump(out, f, indent=2, allow_nan=False)
        f.write("\n")


if __name__ == "__main__":
    main()
