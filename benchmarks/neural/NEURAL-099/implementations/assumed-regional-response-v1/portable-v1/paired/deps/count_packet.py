"""Bounded evaluator-private count packet codec; no runtime containment claim.

Wire layout is raw uint64 little endian, 100 history bins then 100 response
bins per case. Cases are ordered asset, source trial row, then literal region.
Only one 1600-byte count row is packed/read at once. Metadata is retained, but
the full count matrix is never loaded. The trusted evaluator owns this reader;
participants must never receive the reader, its file descriptor or its path.

history_projection is a primitive check against the explicitly released case.
It does not enforce chronology: the caller's ChronologicalQuery owns release,
prediction locking and advancing. File signatures detect ordinary concurrent
mutation, not an adversarial filesystem or complete runtime isolation.
"""

from fractions import Fraction
import hashlib
import json
import math
import os
import stat
import struct


BIN_COUNT = 100
BYTES_PER_CASE = 1600
HISTORY_BYTES = 800
UINT64_MAX = 2 ** 64 - 1
HASH_CHUNK_BYTES = 65536
CASE_FIELDS = frozenset((
    "case_id", "asset_id", "animal_id", "source_trial_row", "source_trial_id",
    "trial_start_seconds", "trial_stop_seconds", "region", "source_cluster_count"))
REGIONS = frozenset(("BIC", "MGd", "MGm", "MGv", "MZMG", "SG"))
_ROW = struct.Struct("<200Q")
_HISTORY = struct.Struct("<100Q")
_BINDING_FIELDS = frozenset((
    "schema", "dtype", "case_order", "window_order", "bins_per_window",
    "bytes_per_case", "case_count", "bytes", "sha256", "cases_sha256"))


def _integer(value, name, minimum=None):
    if type(value) is not int or (minimum is not None and value < minimum):
        raise ValueError("Invalid " + name)
    return value


def _identifier(value, name):
    if (type(value) is not str or not value or len(value) > 256
            or any(ord(character) < 32 for character in value)):
        raise ValueError("Invalid " + name)
    return value


def _clock(value, name):
    if type(value) not in (int, float):
        raise ValueError("Invalid " + name)
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError("Nonfinite " + name) from error
    if not math.isfinite(result):
        raise ValueError("Nonfinite " + name)
    return result


def validate_cases(cases):
    """Normalize and validate the supplied complete per-asset regional roster.

    Authentication of biological identity, source trial membership, named
    anatomy and observation assumptions is external. All source rows must be
    supplied, starting at ordinal zero; every available region has every row.
    This codec does not impose an inter-click interval or infer missing rows.
    """
    if type(cases) is not list or not cases:
        raise ValueError("A nonempty case metadata list is required")
    normalized, ids, coordinates = [], set(), set()
    assets, cells, trials, trial_ids = {}, {}, {}, {}
    previous = None
    for original in cases:
        if type(original) is not dict or set(original) != CASE_FIELDS:
            raise ValueError("Invalid case metadata fields")
        case = {field: _identifier(original[field], field)
                for field in ("case_id", "asset_id", "animal_id", "region")}
        if case["region"] not in REGIONS:
            raise ValueError("Unsupported or unassigned region")
        case["source_trial_row"] = _integer(original["source_trial_row"], "source trial row", 0)
        case["source_trial_id"] = _integer(original["source_trial_id"], "source trial ID")
        case["source_cluster_count"] = _integer(original["source_cluster_count"], "source cluster count", 1)
        for field in ("trial_start_seconds", "trial_stop_seconds"):
            case[field] = _clock(original[field], field)
        if case["trial_stop_seconds"] <= case["trial_start_seconds"]:
            raise ValueError("Trial stop must follow trial start")
        coordinate = (case["asset_id"], case["source_trial_row"], case["region"])
        if case["case_id"] in ids or coordinate in coordinates:
            raise ValueError("Duplicate case identity or coordinate")
        if previous is not None and coordinate <= previous:
            raise ValueError("Cases are not ordered asset, source trial row, region")
        previous = coordinate
        ids.add(case["case_id"])
        coordinates.add(coordinate)
        asset, row, region = coordinate
        if asset in assets and assets[asset] != case["animal_id"]:
            raise ValueError("One source asset has conflicting animal identities")
        assets[asset] = case["animal_id"]
        cell = cells.setdefault((asset, region), {
            "clusters": case["source_cluster_count"], "rows": set()})
        if cell["clusters"] != case["source_cluster_count"]:
            raise ValueError("Source cluster denominator changes within an asset/region")
        cell["rows"].add(row)
        trial_key = (asset, row)
        identity = (case["source_trial_id"], case["trial_start_seconds"], case["trial_stop_seconds"])
        if trial_key in trials and trials[trial_key] != identity:
            raise ValueError("Regions disagree on the source trial identity or timing")
        trials[trial_key] = identity
        id_key = (asset, case["source_trial_id"])
        if id_key in trial_ids and trial_ids[id_key] != row:
            raise ValueError("A source trial ID refers to multiple source rows")
        trial_ids[id_key] = row
        normalized.append(case)
    for asset in assets:
        row_sets = [value["rows"] for (owner, _), value in cells.items() if owner == asset]
        if any(rows != row_sets[0] for rows in row_sets[1:]):
            raise ValueError("An available region omits source trial rows")
        rows = row_sets[0]
        if min(rows) != 0 or max(rows) + 1 != len(rows):
            raise ValueError("Source trial row ordinals are incomplete")
    return normalized


def _case_hash(cases):
    digest = hashlib.sha256()
    digest.update(b"[")
    for index, case in enumerate(cases):
        if index:
            digest.update(b",")
        digest.update(json.dumps(case, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=True, allow_nan=False).encode("utf-8"))
    digest.update(b"]")
    return digest.hexdigest()


def _shape(cases, max_bytes):
    _integer(max_bytes, "maximum packet bytes", 1)
    expected = len(cases) * BYTES_PER_CASE
    if expected > max_bytes:
        raise ValueError("Declared packet shape exceeds the admitted byte bound")
    return expected


def _binding(cases, expected_bytes, digest):
    return {
        "schema": "neural099-private-count-packet/v1",
        "dtype": "uint64-little-endian",
        "case_order": ["asset_id", "source_trial_row", "region"],
        "window_order": ["history", "response"],
        "bins_per_window": BIN_COUNT,
        "bytes_per_case": BYTES_PER_CASE,
        "case_count": len(cases),
        "bytes": expected_bytes,
        "sha256": digest,
        "cases_sha256": _case_hash(cases),
    }


def _digest(value, name):
    if (type(value) is not str or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)):
        raise ValueError("Invalid " + name)
    return value


def _validate_binding(binding, cases, expected_bytes):
    if type(binding) is not dict or set(binding) != _BINDING_FIELDS:
        raise ValueError("Invalid packet binding fields")
    _digest(binding["sha256"], "packet checksum")
    _digest(binding["cases_sha256"], "case metadata checksum")
    # Reject bool/int substitutions explicitly before comparing fixed shape.
    for field in ("bins_per_window", "bytes_per_case", "case_count", "bytes"):
        _integer(binding[field], field, 1)
    expected = _binding(cases, expected_bytes, binding["sha256"])
    if binding != expected:
        raise ValueError("Packet binding does not match exact metadata, shape or endian layout")


def _signature(fd):
    status = os.fstat(fd)
    if not stat.S_ISREG(status.st_mode):
        raise ValueError("Count packet must be a regular file")
    return (status.st_dev, status.st_ino, status.st_size,
            status.st_mtime_ns, status.st_ctime_ns, status.st_nlink)


def _nofollow_flags():
    if not hasattr(os, "O_NOFOLLOW"):
        raise ValueError("This platform cannot enforce the packet no-symlink open rule")
    return os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)


def _counts(value, name):
    if type(value) is not list or len(value) != BIN_COUNT:
        raise ValueError(name + " must be a 100-bin list")
    for count in value:
        _integer(count, name + " count", 0)
        if count > UINT64_MAX:
            raise ValueError("Count exceeds uint64 packet range")
    return value


def _write_all(fd, data):
    remaining = memoryview(data)
    while remaining:
        written = os.write(fd, remaining)
        if written <= 0:
            raise OSError("Packet write made no progress")
        remaining = remaining[written:]


def write_packet(path, cases, rows, *, max_bytes):
    """Stream an exclusive 0600 packet and return its complete binding.

    rows yields exactly {case_id, history_counts, response_counts}, in sealed
    metadata order. On failure the partial private file is retained, with no
    returned binding; callers must never admit a partial artifact. No existing
    destination is overwritten. The parent directory must already exist.
    """
    normalized = validate_cases(cases)
    expected_bytes = _shape(normalized, max_bytes)
    iterator = iter(rows)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | _nofollow_flags()
    fd = os.open(os.fspath(path), flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        if _signature(fd)[2] != 0:
            raise ValueError("New packet unexpectedly contains bytes")
        digest, written = hashlib.sha256(), 0
        sentinel = object()
        for case in normalized:
            row = next(iterator, sentinel)
            if (row is sentinel or type(row) is not dict
                    or set(row) != {"case_id", "history_counts", "response_counts"}
                    or row["case_id"] != case["case_id"]
                    or type(row["case_id"]) is not str):
                raise ValueError("Count row does not match the next sealed case identity")
            history = _counts(row["history_counts"], "history")
            response = _counts(row["response_counts"], "response")
            payload = _ROW.pack(*(history + response))
            if len(payload) != BYTES_PER_CASE or written + len(payload) > expected_bytes:
                raise ValueError("Packet write exceeds its exact declared shape")
            _write_all(fd, payload)
            digest.update(payload)
            written += len(payload)
        if next(iterator, sentinel) is not sentinel:
            raise ValueError("Count iterator has extra cases")
        os.fsync(fd)
        if written != expected_bytes or _signature(fd)[2] != expected_bytes:
            raise ValueError("Completed packet has the wrong extent")
        return _binding(normalized, expected_bytes, digest.hexdigest())
    finally:
        os.close(fd)


class VerifiedPacket:
    """Trusted evaluator object returned by verify_packet, never a candidate API."""

    def __init__(self, fd, cases, binding, signature):
        self._fd = fd
        self._cases = tuple(cases)
        self._indices = {case["case_id"]: index for index, case in enumerate(cases)}
        self._binding = dict(binding)
        self._signature = signature

    @property
    def case_ids(self):
        return tuple(case["case_id"] for case in self._cases)

    def close(self):
        if self._fd is not None:
            fd, self._fd = self._fd, None
            os.close(fd)

    def __enter__(self):
        self._unchanged()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def _unchanged(self):
        if self._fd is None:
            raise ValueError("Verified count packet reader is closed")
        try:
            if _signature(self._fd) != self._signature:
                raise ValueError("Count packet changed after verification")
        except BaseException:
            self.close()
            raise

    def _read(self, case_id, size):
        _identifier(case_id, "case ID")
        if case_id not in self._indices:
            raise ValueError("Unknown packet case ID")
        self._unchanged()
        index = self._indices[case_id]
        try:
            payload = bytearray()
            while len(payload) < size:
                part = os.pread(self._fd, size - len(payload),
                                index * BYTES_PER_CASE + len(payload))
                if not part or len(part) > size - len(payload):
                    raise ValueError("Count packet row is truncated or exceeds its read bound")
                payload.extend(part)
            self._unchanged()
        except BaseException:
            self.close()
            raise
        return dict(self._cases[index]), bytes(payload)

    def read_private(self, case_id):
        """Evaluator-only full row access; this must never be candidate-exposed."""
        case, payload = self._read(case_id, BYTES_PER_CASE)
        counts = _ROW.unpack(payload)
        return {"case": case, "history_counts": list(counts[:BIN_COUNT]),
                "response_counts": list(counts[BIN_COUNT:])}

    def history_projection(self, case_id, *, released_case_id):
        """Only history rates for the caller's currently released query case.

        The supplied release identity comes from trusted ChronologicalQuery
        state. Matching two arbitrary participant strings is not authorization
        or chronological enforcement. This method reads only the 800 history
        bytes, and returns neither count vectors nor future response values.
        Source trial IDs and absolute start/stop clocks remain private provenance.
        """
        _identifier(released_case_id, "released case ID")
        if case_id != released_case_id:
            raise ValueError("Only the explicitly released current case may be projected")
        case, payload = self._read(case_id, HISTORY_BYTES)
        counts = _HISTORY.unpack(payload)
        rates = [float(Fraction(count * 1000, case["source_cluster_count"])) for count in counts]
        visible_case = {field: case[field] for field in (
            "case_id", "animal_id", "asset_id", "region",
            "source_trial_row", "source_cluster_count")}
        return {"case": visible_case, "history_rates": rates}


def verify_packet(path, cases, binding, *, max_bytes):
    """Authenticate exact shape, endian declaration, ordered metadata and checksum.

    Evaluator preflight reads the full file, including private response bytes.
    The same regular-file descriptor used for streaming verification supplies
    later bounded row reads. An unexpected signature change closes it. This is
    a codec integrity check, not a claim that candidates cannot access the host.
    """
    normalized = validate_cases(cases)
    expected_bytes = _shape(normalized, max_bytes)
    _validate_binding(binding, normalized, expected_bytes)
    # Opening a substituted FIFO must not block before fstat can reject it.
    fd = os.open(os.fspath(path), os.O_RDONLY | os.O_NONBLOCK | _nofollow_flags())
    try:
        before = _signature(fd)
        if before[2] != expected_bytes:
            raise ValueError("Packet file does not have its exact declared extent")
        digest, remaining = hashlib.sha256(), expected_bytes
        while remaining:
            payload = os.read(fd, min(HASH_CHUNK_BYTES, remaining))
            if not payload:
                raise ValueError("Packet ended before its declared extent")
            digest.update(payload)
            remaining -= len(payload)
        if os.read(fd, 1):
            raise ValueError("Packet has trailing bytes")
        after = _signature(fd)
        if before != after:
            raise ValueError("Packet changed while its checksum was being verified")
        if digest.hexdigest() != binding["sha256"]:
            raise ValueError("Count packet checksum mismatch")
        return VerifiedPacket(fd, normalized, binding, after)
    except BaseException:
        os.close(fd)
        raise
