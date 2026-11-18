"""Protected full-source T15 identity export; no labels or neural datasets decoded.

Archive/member hashing reads opaque source bytes, including protected payload.
This operator does not acquire data or admit runtime/scientific execution.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
import zipfile

CONSUMER_SHA256 = "d6af274fdd71fc94cf0a537f5e0bc87f5968e85076a1f30d5b85bb2cd61495c5"
ARCHIVE_BYTES = 11051034483
CHUNK = 1024 * 1024
MAX_GROUPS = 5000
MAX_TRIALS = 50000
MAX_OUTPUT = 8 * 1024 * 1024
GROUP = re.compile(r"trial_[0-9]{4,6}\Z")


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def _identity(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _ordinary_path(path):
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts, "absolute ordinary path required")
    for ancestor in [*reversed(path.parents), path]:
        require(not stat.S_ISLNK(os.lstat(ancestor).st_mode), "symlink path refused")
    return path


class _Reads(io.RawIOBase):
    """Count all file-object read requests used by ZIP/HDF5; never write."""
    def __init__(self, stream, cap):
        self.stream, self.cap, self.used = stream, cap, 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def seek(self, offset, whence=0):
        return self.stream.seek(offset, whence)

    def tell(self):
        return self.stream.tell()

    def read(self, size=-1):
        require(type(size) is int, "integer read size")
        if size < 0:
            position = self.tell()
            size = self.seek(0, 2) - position
            self.seek(position)
        require(0 <= size <= self.cap - self.used, "read budget exceeded")
        body = self.stream.read(size)
        self.used += len(body)
        return body

    def readinto(self, buffer):
        body = self.read(len(buffer))
        buffer[:len(body)] = body
        return len(body)


def _digest(stream, size):
    stream.seek(0)
    digest, total = hashlib.sha256(), 0
    while total < size:
        body = stream.read(min(CHUNK, size - total))
        require(body, "truncated source")
        total += len(body)
        digest.update(body)
    require(stream.read(1) == b"", "unexpected source tail")
    stream.seek(0)
    return digest.hexdigest()


@contextmanager
def _verified_archive(path, expected):
    path = _ordinary_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as raw:
        before = os.fstat(raw.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and before.st_size == expected["bytes"], "exact ordinary archive extent")
        source = _Reads(raw, 3 * expected["bytes"] + 4 * CHUNK)
        require(_digest(source, before.st_size) == expected["sha256"], "archive SHA256 mismatch")
        yield source
        require(_digest(source, before.st_size) == expected["sha256"], "archive changed while exporting")
        require(_identity(before) == _identity(os.fstat(raw.fileno()))
                == _identity(os.lstat(path)), "archive custody changed")


def _consumer():
    path = Path(__file__).resolve().parent.parent / "source-count-reconciliation" / "reconcile.py"
    body = path.read_bytes()
    require(len(body) == 10917 and hashlib.sha256(body).hexdigest() == CONSUMER_SHA256,
            "exact accepted reconciliation consumer required")
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader("t15_count_consumer", loader=None))
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def _contract(task_body, consumer):
    source = consumer.source_members(task_body)
    manifest = consumer.parse(task_body, 256 * 1024)["input_assets"]["readiness_records"][0]["data_manifest"]
    extents = {row["name"]: row for row in manifest["neural_archive_members"]}
    return {"archive": {"bytes": ARCHIVE_BYTES, "sha256": consumer.ARCHIVE_SHA256},
            "members": {name: dict(row, compressed_size=extents[name]["compressed_size"])
                        for name, row in source.items()}}


def _zip_roster(archive, members):
    infos = archive.infolist()
    require(len(infos) <= 1000 and len({row.filename for row in infos}) == len(infos),
            "bounded unique complete ZIP directory")
    parents = {str(parent) + "/" for name in members for parent in PurePosixPath(name).parents
               if str(parent) != "."}
    selected = {}
    for info in infos:
        name = info.filename
        require(name == info.orig_filename and "\x00" not in name and "\\" not in name,
                "ordinary ZIP name")
        parts = PurePosixPath(name).parts
        require(parts and not name.startswith("/") and all(p not in (".", "..") for p in parts),
                "unsafe ZIP path")
        kind = stat.S_IFMT(info.external_attr >> 16)
        require(not info.flag_bits & 1 and info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                "encrypted or unsupported ZIP member")
        if info.is_dir():
            require(name in parents and info.file_size == 0 and kind in (0, stat.S_IFDIR),
                    "unexpected ZIP directory")
            continue
        require(name in members and kind in (0, stat.S_IFREG), "unexpected/nonordinary ZIP file")
        row = members[name]
        require(info.file_size == row["bytes"] and info.compress_size == row["compressed_size"],
                "member extent mismatch")
        selected[name] = info
    require(set(selected) == set(members), "incomplete source member roster")
    return selected


def _scalar_attribute(group, name):
    require(name in group.attrs, "missing native identity attribute")
    identity = group.attrs.get_id(name)
    try:
        require(identity.shape == (), "scalar native identity attribute required")
        dtype = identity.dtype
        if name != "session":
            require(dtype.kind in "iu" and dtype.itemsize <= 8, "native integer attribute required")
        else:
            require(dtype.kind in "SO", "native string session attribute required")
    finally:
        identity.close()
    value = group.attrs[name]
    if name == "session":
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="strict")
        require(type(value) is str and len(value) <= 64, "bounded native session text")
    else:
        value = int(value)
        require(0 <= value <= MAX_TRIALS, "bounded native integer identity")
    return value


def _headers(stream, member, h5py):
    rows = []
    with h5py.File(stream, "r") as source:
        require(len(source) <= MAX_GROUPS, "trial-group limit exceeded")
        for name in sorted(source):
            require(GROUP.fullmatch(name) is not None
                    and isinstance(source.get(name, getlink=True), h5py.HardLink),
                    "ordinary native trial group required")
            group = source[name]
            require(isinstance(group, h5py.Group) and h5py.h5o.get_info(group.id).rc == 1,
                    "unaliased native trial group required")
            row = {"group": name, "session": _scalar_attribute(group, "session"),
                   "block_num": _scalar_attribute(group, "block_num"),
                   "trial_num": _scalar_attribute(group, "trial_num")}
            require(row["session"] == member["session"], "native file/session mismatch")
            rows.append(row)
    return rows


def _collect(archive_path, contract, scratch, h5py):
    """Custody engine. Only export_headers constructs the production contract.

    Tests supply a tiny generated contract here; no CLI override exists.
    """
    scratch = _ordinary_path(scratch)
    require(scratch.is_dir(), "ordinary allocated scratch directory required")
    members, result, seen = contract["members"], [], set()
    counters = {"member_opaque_bytes_staged": 0, "member_fileobject_read_bytes": 0,
                "largest_member_scratch_bytes": 0}
    with _verified_archive(archive_path, contract["archive"]) as source:
        with zipfile.ZipFile(source, "r") as archive:
            roster = _zip_roster(archive, members)
            for name, spec in sorted(members.items()):
                with tempfile.TemporaryFile(mode="w+b", dir=scratch) as raw:
                    digest, size = hashlib.sha256(), 0
                    with archive.open(roster[name], "r") as payload:
                        while True:
                            body = payload.read(min(CHUNK, spec["bytes"] - size + 1))
                            if not body:
                                break
                            size += len(body)
                            require(size <= spec["bytes"], "member expansion exceeds declared extent")
                            raw.write(body)
                            counters["member_opaque_bytes_staged"] += len(body)
                            digest.update(body)
                    require(size == spec["bytes"], "incomplete source member")
                    raw.flush()
                    before = os.fstat(raw.fileno())
                    counters["largest_member_scratch_bytes"] = max(counters["largest_member_scratch_bytes"], size)
                    wrapped = _Reads(raw, 4 * size + 65536)
                    member_hash = digest.hexdigest()
                    require(_digest(wrapped, size) == member_hash, "member staging identity mismatch")
                    rows = _headers(wrapped, spec, h5py)
                    require(_digest(wrapped, size) == member_hash
                            and _identity(before) == _identity(os.fstat(raw.fileno())),
                            "member changed during header extraction")
                    counters["member_fileobject_read_bytes"] += wrapped.used
                    for row in rows:
                        identity = (row["session"], row["block_num"], row["trial_num"])
                        require(identity not in seen, "duplicate native identity across source members")
                        seen.add(identity)
                        require(len(seen) <= MAX_TRIALS, "complete source trial limit exceeded")
                    result.append({"name": name, "bytes": size, "sha256": member_hash, "trials": rows})
        # The context exit performs the final same-open archive hash/identity check.
    counters["archive_fileobject_read_bytes"] = source.used
    return {"schema": "neural014-trial-header-census-v1", "coverage": "all_source_members",
            "archive_sha256": contract["archive"]["sha256"], "members": result}, counters


def export_headers(task_body, csv_body, archive_path, scratch):
    consumer = _consumer()
    contract = _contract(task_body, consumer)
    consumer.blocks(csv_body, {r["date"] for r in contract["members"].values()})
    os.environ["HDF5_PLUGIN_PATH"] = ""
    import h5py
    import numpy
    require(h5py.__version__ == "3.13.0" and numpy.__version__ == "2.2.6",
            "declared header runtime h5py3.13.0/NumPy2.2.6 required")
    census, counters = _collect(archive_path, contract, scratch, h5py)
    header_body = canonical(census)
    require(len(header_body) <= MAX_OUTPUT, "complete header output exceeds bound")
    comparison = canonical(consumer.reconcile(task_body, csv_body, header_body))
    require(len(comparison) <= MAX_OUTPUT, "complete comparison output exceeds bound")
    receipt = {"schema": "neural014-original-header-custody-v1", "task_id": "NEURAL-014",
               "inputs": {"task": pin(task_body), "author_csv": pin(csv_body),
                          "archive": contract["archive"], "consumer_sha256": CONSUMER_SHA256,
                          "exporter": pin(Path(__file__).read_bytes())},
               "outputs": {"header_census": pin(header_body), "comparison": pin(comparison)},
               "coverage": "all_source_members", "members": len(census["members"]),
               "sessions": len({x["session"] for x in contract["members"].values()}),
               "same_open_archive_and_member_custody_verified": True,
               "archive_and_member_opaque_payload_bytes_read": True,
               "neural_label_transcript_datasets_decoded": False,
               "official_test_targets_available": False,
               "resource_counters": counters,
               "runtime": {"h5py": h5py.__version__, "numpy": numpy.__version__},
               "scientific_qualified": False, "readiness_promoted": False,
               "scope": "Original bytes/header custody only; counts are compared, not adjudicated. "
                        "Consumer authentication flag remains false by its unchanged API. "
                        "This separate receipt requires independent operator retention/review."}
    return header_body, comparison, canonical(receipt)


def _capture(path, limit):
    path = _ordinary_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and 0 < before.st_size <= limit, "bounded ordinary metadata input")
        body = stream.read(limit + 1)
        require(len(body) == before.st_size and _identity(before) == _identity(os.fstat(stream.fileno()))
                == _identity(os.lstat(path)), "metadata changed during capture")
        return body


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--task", type=Path, required=True)
    p.add_argument("--author-csv", type=Path, required=True)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--scratch", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    require(args.out.is_absolute() and ".." not in args.out.parts, "absolute fresh output path")
    _ordinary_path(args.out.parent)
    args.out.mkdir(mode=0o700)
    try:
        results = export_headers(_capture(args.task, 256 * 1024), _capture(args.author_csv, 256 * 1024),
                                 args.archive, args.scratch)
        for name, body in zip(("HEADERS.json", "COMPARISON.json", "CUSTODY.json"), results):
            fd = os.open(args.out / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
    except BaseException:
        # Never publish CUSTODY before other outputs. Partial output stays diagnostic.
        with (args.out / "FAILED.json").open("xb") as stream:
            stream.write(canonical({"status": "failed", "complete_export": False}))
        raise


if __name__ == "__main__":
    main()
