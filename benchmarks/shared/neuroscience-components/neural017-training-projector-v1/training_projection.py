"""Copy the exact eight TRAIN NPY members; never decode numerical arrays.

Operator-only construction component. The caller supplies an independently
authorized source pin and absolute monotonic deadline. This is not admission,
an execution sandbox, NPZ numerical validation, or a scientific result.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import os
from pathlib import Path
import stat
import struct
import tempfile
import time
import zipfile

PUBLIC_FIELDS = (
    "train_counts_heldin", "train_counts_heldout", "eval_counts_heldin",
    "train_trial_ids", "eval_trial_ids", "heldin_unit_ids", "heldout_unit_ids",
    "train_condition_ids", "eval_condition_ids", "bin_left_edges_ms",
    "eval_valid_mask", "source_manifest_sha256", "panel_fingerprint",
)
TRAIN_FIELDS = (
    "train_counts_heldin", "train_counts_heldout", "train_trial_ids",
    "heldin_unit_ids", "heldout_unit_ids", "train_condition_ids",
    "bin_left_edges_ms", "source_manifest_sha256",
)
SOURCE_CAP_BYTES = 128_000_000
DECOMPRESSED_CAP_BYTES = 128_000_000
CHUNK_BYTES = 1024 * 1024
DIRECTORY_CAP_BYTES = 65536
SOURCE_READ_CAP_BYTES = 2 * SOURCE_CAP_BYTES + 4 * DIRECTORY_CAP_BYTES


class ProjectionError(ValueError):
    pass


def require(value, message):
    if not value:
        raise ProjectionError(message)


def deadline(value):
    require(time.monotonic() < value, "Projection deadline exceeded")


def identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def ordinary_path(value, *, must_exist):
    path = Path(os.path.abspath(os.fspath(value)))
    require(".." not in Path(value).parts, "Parent traversal is not allowed")
    for part in (*reversed(path.parents), path):
        try:
            info = part.lstat()
        except FileNotFoundError:
            require(part == path and not must_exist, "Missing parent/source")
            continue
        require(not stat.S_ISLNK(info.st_mode), "Symlink path is not allowed")
        if part != path:
            require(stat.S_ISDIR(info.st_mode), "Parent must be a directory")
        else:
            require(must_exist, "Destination already exists")
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                    "Source must be an ordinary single-link file")
    return path


@dataclass(frozen=True)
class MemberPin:
    name: str
    bytes: int
    sha256: str


@dataclass(frozen=True)
class ProjectionReceipt:
    source_path: str
    source_bytes: int
    source_sha256: str
    source_identity: tuple[int, ...]
    output_path: str
    output_bytes: int
    output_sha256: str
    members: tuple[MemberPin, ...]
    verified_members: int
    decompressed_bytes: int
    source_stream_bytes: int
    crc_checked_all_members: bool = True
    numerical_arrays_decoded: bool = False


class BoundedOutput:
    """Append-only output gives one-pass hashing and a hard retained-byte cap."""
    def __init__(self, stream, cap, until):
        self.stream, self.cap, self.until = stream, cap, until
        self.count = 0
        self.hasher = hashlib.sha256()

    def write(self, body):
        deadline(self.until)
        require(self.count + len(body) <= self.cap, "Output byte cap exceeded")
        written = self.stream.write(body)
        require(written == len(body), "Short output write")
        self.hasher.update(body)
        self.count += written
        return written

    def tell(self):
        return self.count

    def flush(self):
        self.stream.flush()


class CountedInput:
    """Count every requested source byte, including repeated ZIP/header reads."""
    def __init__(self, stream, until):
        self.stream, self.until = stream, until
        self.count = 0

    def read(self, size=-1):
        deadline(self.until)
        remaining = SOURCE_READ_CAP_BYTES - self.count
        requested = remaining + 1 if size < 0 else min(size, remaining + 1)
        body = self.stream.read(requested)
        self.count += len(body)
        require(self.count <= SOURCE_READ_CAP_BYTES, "Cumulative source read cap exceeded")
        return body

    def seek(self, *args):
        return self.stream.seek(*args)

    def tell(self):
        return self.stream.tell()

    def seekable(self):
        return True


def bounded_directory(stream, source_bytes, until):
    """Bound allocations before ZipFile parses its central directory.

    Local ZIP64 sizes are supported. Multi-disk/ZIP64 end directories are not
    needed by this <128MB, 13-member format and explicitly refuse.
    """
    deadline(until)
    require(source_bytes >= 22, "ZIP end directory missing")
    stream.seek(source_bytes - 22)
    end = stream.read(22)
    require(len(end) == 22, "Short ZIP end directory")
    magic, disk, central_disk, disk_count, count, size, offset, comment = struct.unpack(
        "<4s4H2IH", end)
    require(magic == b"PK\x05\x06" and disk == central_disk == comment == 0 and
            disk_count == count == 13 and 0 < size <= DIRECTORY_CAP_BYTES and
            offset + size == source_bytes - 22,
            "Bounded single-disk thirteen-member end directory required")
    # CPython probes exactly this position for a ZIP64 locator and would
    # otherwise replace the classic record's size/count before allocation.
    # The ordinary offset/size equation alone cannot exclude a forged locator.
    if source_bytes >= 42:
        stream.seek(source_bytes - 42)
        require(stream.read(4) != b"PK\x06\x07", "ZIP64 end locator is unsupported")
    stream.seek(0)


def derive_training_packet(source_path, destination_path, expected_bytes,
                           expected_sha256, deadline_monotonic,
                           output_cap_bytes=128_000_000):
    """Authenticate the full source, verify all 13 ZIP members, copy eight.

    Only stored/deflated regular flat NPY members are accepted. Uncompressed
    selected NPY bytes are copied verbatim into a deterministic stored ZIP.
    Every discarded member is streamed to EOF too, enforcing its CRC and the
    aggregate expansion cap. An existing destination is never overwritten.

    Read cost includes one source hash pass plus ZIP metadata and all members
    again; compressed member reads and decompressed bytes are distinct. An
    operator must reserve 384 MiB managed source/decode bytes (source reads are
    counted, capped at 256,262,144; expanded bytes capped at 128,000,000),
    128,000,000 retained output bytes and a scratch inode.
    Blocking filesystem calls need an outer process deadline; these checks are
    cooperative. No authentic source is opened merely by importing this file.
    """
    require(type(expected_bytes) is int and 0 < expected_bytes <= SOURCE_CAP_BYTES,
            "Bounded positive exact source size required")
    require(type(expected_sha256) is str and len(expected_sha256) == 64 and
            all(c in "0123456789abcdef" for c in expected_sha256), "SHA256 required")
    require(type(output_cap_bytes) is int and 0 < output_cap_bytes <= SOURCE_CAP_BYTES,
            "Bounded positive output cap required")
    require(type(deadline_monotonic) in (int, float) and
            math.isfinite(deadline_monotonic), "Finite monotonic deadline required")
    deadline(deadline_monotonic)
    source = ordinary_path(source_path, must_exist=True)
    destination = ordinary_path(destination_path, must_exist=False)
    require(source != destination, "Separate destination required")
    before = source.lstat()
    require(before.st_size == expected_bytes, "Source byte count differs")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(source, flags)
    temporary = None
    published = False
    temporary_identity = None
    try:
        with os.fdopen(descriptor, "rb") as stream:
            require(identity(os.fstat(stream.fileno())) == identity(before),
                    "Source identity changed before open")
            digest = hashlib.sha256()
            count = 0
            source_io = CountedInput(stream, deadline_monotonic)
            while True:
                deadline(deadline_monotonic)
                body = source_io.read(min(CHUNK_BYTES, expected_bytes - count + 1))
                if not body:
                    break
                count += len(body)
                require(count <= expected_bytes, "Source grew while reading")
                digest.update(body)
            require(count == expected_bytes and digest.hexdigest() == expected_sha256,
                    "Source digest differs")
            require(identity(os.fstat(stream.fileno())) == identity(before),
                    "Source changed during authentication")
            bounded_directory(source_io, expected_bytes, deadline_monotonic)
            with zipfile.ZipFile(source_io) as archive:
                infos = archive.infolist()
                names = [item.filename for item in infos]
                require(len(infos) == 13 and len(set(names)) == 13 and
                        set(names) == {field + ".npy" for field in PUBLIC_FIELDS},
                        "Exact thirteen unique public NPY members required")
                require(not archive.comment, "ZIP comment is not allowed")
                total = 0
                for item in infos:
                    mode = item.external_attr >> 16
                    require(item.filename == item.orig_filename and not item.is_dir() and
                            not item.flag_bits & 1 and item.compress_type in
                            (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) and
                            stat.S_IFMT(mode) in (0, stat.S_IFREG),
                            "Unsupported ZIP member type or encoding")
                    require(0 <= item.file_size <= DECOMPRESSED_CAP_BYTES and
                            0 <= item.compress_size <= expected_bytes,
                            "Unbounded ZIP member size")
                    total += item.file_size
                require(total <= DECOMPRESSED_CAP_BYTES, "Decompression cap exceeded")
                fd, temporary = tempfile.mkstemp(prefix=".train-packet-", suffix=".tmp",
                                                  dir=destination.parent)
                with os.fdopen(fd, "wb") as output:
                    writer = BoundedOutput(output, output_cap_bytes, deadline_monotonic)
                    member_pins = []
                    expanded = 0
                    # Fixed public order prevents central-directory order from
                    # changing the output or choosing duplicate occurrences.
                    with zipfile.ZipFile(writer, "w", compression=zipfile.ZIP_STORED) as target:
                        for field in PUBLIC_FIELDS:
                            deadline(deadline_monotonic)
                            item = archive.getinfo(field + ".npy")
                            selected = field in TRAIN_FIELDS
                            with archive.open(item, "r") as member:
                                header = member.read(8)
                                require(len(header) == 8 and header[:6] == b"\x93NUMPY" and
                                        header[6:] in (b"\x01\x00", b"\x02\x00", b"\x03\x00"),
                                        "NPY member magic/version required")
                                info = zipfile.ZipInfo(item.filename, (1980, 1, 1, 0, 0, 0))
                                info.create_system = 3
                                info.external_attr = (stat.S_IFREG | 0o600) << 16
                                info.file_size = item.file_size
                                sink = target.open(info, "w", force_zip64=True) if selected else None
                                seen = 0
                                member_digest = hashlib.sha256()
                                try:
                                    body = header
                                    while body:
                                        deadline(deadline_monotonic)
                                        seen += len(body)
                                        expanded += len(body)
                                        require(seen <= item.file_size and
                                                expanded <= DECOMPRESSED_CAP_BYTES,
                                                "Expanded byte cap exceeded")
                                        if sink is not None:
                                            sink.write(body)
                                            member_digest.update(body)
                                        body = member.read(CHUNK_BYTES)
                                    require(seen == item.file_size, "Member size differs")
                                finally:
                                    if sink is not None:
                                        sink.close()
                                if selected:
                                    member_pins.append(MemberPin(item.filename, seen,
                                                                 member_digest.hexdigest()))
                    require(expanded == total, "Aggregate size differs")
                    output.flush()
                    os.fsync(output.fileno())
                    temporary_identity = identity(os.fstat(output.fileno()))
                    require(temporary_identity[4] == writer.count, "Output size differs")
                    output_digest = writer.hasher.hexdigest()
                require(identity(os.fstat(stream.fileno())) == identity(before) and
                        identity(source.lstat()) == identity(before),
                        "Source identity changed during projection")
                deadline(deadline_monotonic)
                # link() is atomic and refuses an existing destination. Both
                # files reside in the same trusted operator-owned directory.
                os.link(temporary, destination, follow_symlinks=False)
                published = True
                os.unlink(temporary)
                temporary = None
                parent_fd = os.open(destination.parent, os.O_RDONLY)
                try:
                    os.fsync(parent_fd)
                finally:
                    os.close(parent_fd)
                return ProjectionReceipt(str(source), count, expected_sha256,
                                         identity(before), str(destination), writer.count,
                                         output_digest, tuple(member_pins), len(infos),
                                         expanded, source_io.count)
    except Exception:
        if published:
            current = destination.lstat()
            if (current.st_dev, current.st_ino) == temporary_identity[:2]:
                destination.unlink()
        raise
    finally:
        if temporary is not None:
            os.unlink(temporary)
