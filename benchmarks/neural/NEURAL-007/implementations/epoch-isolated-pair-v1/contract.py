"""Exact same-epoch information contract; no participant code is imported here."""
from __future__ import annotations
import ast
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import stat
import struct

CASES = (("development-001", 2780), ("development-002", 2670))
CHANNELS = ("EEG Fpz-Cz", "EEG Pz-Oz", "EOG horizontal")
CLOCK = ("elapsed_hours", "wall_clock_sin", "wall_clock_cos")
CLASSES = ("W", "N1", "N2", "N3", "R")
VISUAL_CONDITION = "epoch_isolated_raw_viewer_zero_shot_v1"
PROGRAMME_CONDITION = "epoch_isolated_raw_programme_zero_shot_v1"
PAIR_CONDITION = "epoch_isolated_same_epoch_v1"
KNOWLEDGE_POLICY = "shared_declared_base_agent_prior_only"
SAMPLES = 3000
SAMPLE_RATE = 100
TOTAL = 5450


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def decode(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, "Duplicate JSON field")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, "Nonfinite JSON"))


def pin(raw):
    need(type(raw) is bytes, "Exact bytes required")
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def checked_pin(value, cap=8 * 2**20):
    need(type(value) is dict and set(value) == {"bytes", "sha256"}
         and type(value["bytes"]) is int and 0 < value["bytes"] <= cap
         and type(value["sha256"]) is str and re.fullmatch("[0-9a-f]{64}", value["sha256"]),
         "Exact bounded pin")
    return dict(value)


def target(case, index):
    need(type(case) is str and case in dict(CASES) and type(index) is int
         and 0 <= index < dict(CASES)[case], "Original person and epoch required")
    return f"{case}/{index:05d}"


def checked_target(epoch_id):
    need(type(epoch_id) is str and epoch_id.count("/") == 1, "Exact target ID")
    case, index = epoch_id.split("/")
    need(re.fullmatch("[0-9]{5}", index), "Canonical epoch index")
    need(target(case, int(index)) == epoch_id, "Canonical target ID")
    return case, int(index)


def required_targets():
    return tuple(target(case, index) for case, count in CASES for index in range(count))


def checked_knowledge(value):
    need(type(value) is dict and set(value) == {
        "schema", "provider", "model", "revision", "policy", "external_assets"},
        "Exact shared prior declaration")
    need(value["schema"] == "sleep007_epoch_shared_knowledge_v1"
         and value["policy"] == KNOWLEDGE_POLICY and value["external_assets"] == [],
         "Only declared shared base-agent prior; no additional assets")
    for key in ("provider", "model", "revision"):
        need(type(value[key]) is str and 0 < len(value[key].encode()) <= 256
             and "\0" not in value[key] and value[key] == value[key].strip(),
             "Explicit bounded agent identity")
    return decode(encode(value))


def probabilities(values):
    # Identical float64 summation and tolerance to original viewer.probabilities.
    import numpy as np
    need(type(values) is list and len(values) == 5 and all(type(v) in (int, float)
         and math.isfinite(v) and 0 <= v <= 1 for v in values), "Five finite class probabilities")
    need(abs(float(np.sum(values, dtype=np.float64)) - 1) <= 1e-6, "Original probability tolerance")
    return [float(v) for v in values]


def signal_bytes(rows):
    need(type(rows) in (list, tuple) and len(rows) == 3, "All three channels required")
    flat = []
    for row in rows:
        need(type(row) in (list, tuple) and len(row) == SAMPLES, "Complete 3000-sample epoch")
        need(all(type(x) in (int, float) and math.isfinite(x) for x in row), "Finite calibrated samples")
        flat.extend(float(x) for x in row)
    header = "{'descr': '<f8', 'fortran_order': False, 'shape': (3, 3000), }".encode("ascii")
    header += b" " * (-(10 + len(header) + 1) % 64) + b"\n"
    return b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header + struct.pack("<9000d", *flat)


def _signal_offset(raw):
    need(type(raw) is bytes and 72010 < len(raw) <= 76106 and raw[:8] == b"\x93NUMPY\x01\x00",
         "Bounded NPY v1 signal bytes only")
    size = struct.unpack("<H", raw[8:10])[0]
    need(0 < size <= 4096 and size + 10 + 72000 == len(raw), "Exact epoch payload extent")
    descriptor = ast.literal_eval(raw[10:10 + size].decode("latin1"))
    need(descriptor == {"descr": "<f8", "fortran_order": False, "shape": (3, SAMPLES)},
         "Exactly three original float64 channels, no richer arrays")
    need(type(descriptor["fortran_order"]) is bool and type(descriptor["shape"]) is tuple
         and all(type(x) is int for x in descriptor["shape"]), "Exact NPY field types")
    need(all(math.isfinite(x) for x in struct.unpack_from("<9000d", raw, 10 + size)), "Finite epoch payload")
    return 10 + size


class EpochPacket:
    """Immutable byte-backed target projection; never retains its parent packet."""
    __slots__ = ("_metadata", "_signals", "_offset")

    def __init__(self, metadata, signals_npy):
        need(type(metadata) is dict and set(metadata) == {
            "schema", "information_contract", "case_id", "epoch_index", "epoch_id", "start_sample",
            "sample_count", "sample_rate_hz", "duration_seconds", "channels", "units",
            "dtype", "shape", "clock_features", "signals"}, "Only exact same-target public metadata")
        need(metadata["schema"] == "sleep007_epoch_public_v1"
             and metadata["information_contract"] == PAIR_CONDITION
             and metadata["epoch_id"] == target(metadata["case_id"], metadata["epoch_index"])
             and type(metadata["start_sample"]) is int and metadata["start_sample"] == metadata["epoch_index"] * SAMPLES
             and type(metadata["sample_count"]) is int and metadata["sample_count"] == SAMPLES
             and type(metadata["sample_rate_hz"]) is int and metadata["sample_rate_hz"] == SAMPLE_RATE
             and type(metadata["duration_seconds"]) is int and metadata["duration_seconds"] == 30
             and metadata["channels"] == list(CHANNELS) and metadata["units"] == "V"
             and metadata["dtype"] == "<f8" and metadata["shape"] == [3, SAMPLES]
             and type(metadata["shape"]) is list and all(type(x) is int for x in metadata["shape"]),
             "Complete unchanged epoch signal geometry")
        clock = metadata["clock_features"]
        need(type(clock) is dict and set(clock) == set(CLOCK)
             and all(type(v) in (int, float) and math.isfinite(v) for v in clock.values()),
             "Only the target clock row")
        self._offset = _signal_offset(signals_npy)
        need(checked_pin(metadata["signals"], 76106) == pin(signals_npy), "Target signal identity")
        self._metadata, self._signals = encode(metadata), signals_npy

    @property
    def case(self): return self.metadata()["case_id"]
    @property
    def case_id(self): return self.case
    @property
    def epoch_index(self): return self.metadata()["epoch_index"]
    @property
    def epoch_id(self): return self.metadata()["epoch_id"]
    @property
    def start_sample(self): return self.metadata()["start_sample"]
    @property
    def clock_features(self): return self.metadata()["clock_features"]
    @property
    def signals_npy(self): return self._signals

    def metadata(self):
        return decode(self._metadata)

    def samples(self, start, stop, channels):
        need(type(start) is int and type(stop) is int and 0 <= start < stop <= SAMPLES
             and 100 <= stop - start <= SAMPLES
             and type(channels) is list and channels
             and channels == [name for name in CHANNELS if name in channels],
             "Only a bounded window inside this exact epoch")
        return [list(struct.unpack_from("<" + "d" * (stop - start), self._signals,
                    self._offset + (CHANNELS.index(name) * SAMPLES + start) * 8)) for name in channels]


def project_epoch(packet, index):
    """Trusted projection helper; original provenance is independently replayed at admission."""
    case = packet.case
    epoch_id = target(case, index)
    need(packet.epochs == dict(CASES)[case], "Canonical original person")
    start = index * SAMPLES
    raw = signal_bytes(packet.samples(start, start + SAMPLES, list(CHANNELS)))
    clock = {name: float(packet.clock[index][i]) for i, name in enumerate(CLOCK)}
    metadata = {"schema": "sleep007_epoch_public_v1", "information_contract": PAIR_CONDITION,
                "case_id": case, "epoch_index": index, "epoch_id": epoch_id, "start_sample": start,
                "sample_count": SAMPLES, "sample_rate_hz": SAMPLE_RATE, "duration_seconds": 30,
                "channels": list(CHANNELS), "units": "V", "dtype": "<f8", "shape": [3, SAMPLES],
                "clock_features": clock, "signals": pin(raw)}
    return EpochPacket(metadata, raw)


def ordinary_path(value):
    p = Path(os.path.abspath(value))
    need(all(not q.is_symlink() for q in (p, *p.parents)), "No linked custody path")
    return p


def read_exact(path, expected, cap=8 * 2**20):
    expected = checked_pin(expected, cap)
    p = ordinary_path(path)
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and before.st_size == expected["bytes"], "Exact ordinary retained file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(expected["bytes"] + 1)
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mode, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
        need(stamp(before) == stamp(os.fstat(fd)) == stamp(p.lstat()) and pin(raw) == expected,
             "Retained bytes changed")
        return raw
    finally:
        os.close(fd)


def write_new(path, raw):
    need(type(raw) is bytes and 0 < len(raw) <= 8 * 2**20, "Bounded immutable publication")
    path = ordinary_path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        at = 0
        while at < len(raw):
            count = os.write(fd, raw[at:])
            need(count > 0, "Complete publication")
            at += count
        os.fsync(fd)
    finally:
        os.close(fd)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(directory)
    finally: os.close(directory)
    return {"path": str(path), **pin(raw)}


def write_projection(packet, root):
    need(type(packet) is EpochPacket, "Immutable target projection")
    root = ordinary_path(root)
    root.mkdir(mode=0o700)
    case = write_new(root / "case.json", encode(packet.metadata()))
    signals = write_new(root / "signals.npy", packet.signals_npy)
    return {"root": str(root), "case": {k: case[k] for k in ("bytes", "sha256")},
            "signals": {k: signals[k] for k in ("bytes", "sha256")}}


def read_projection(descriptor):
    need(type(descriptor) is dict and set(descriptor) == {"root", "case", "signals"}, "Exact projection descriptor")
    root = ordinary_path(descriptor["root"])
    need({p.name for p in root.iterdir()} == {"case.json", "signals.npy"}, "No undeclared target inputs")
    raw = read_exact(root / "case.json", descriptor["case"], 4096)
    signals = read_exact(root / "signals.npy", descriptor["signals"], 76106)
    packet = EpochPacket(decode(raw), signals)
    need(raw == encode(packet.metadata()), "Canonical public metadata bytes")
    return packet


class FirstAnswers:
    def __init__(self):
        self._rows = {}

    def accept(self, epoch_id, values, evidence):
        checked_target(epoch_id)
        need(epoch_id not in self._rows, "First accepted answer is irreversible")
        self._rows[epoch_id] = {"epoch_id": epoch_id, "probabilities": probabilities(values),
                                "evidence": checked_pin(evidence)}

    def complete(self):
        need(set(self._rows) == set(required_targets()), "All5450 original targets and both people required")
        return [decode(encode(self._rows[name])) for name in required_targets()]


def checked_complete_rows(rows):
    need(type(rows) is list and len(rows) == TOTAL, "Complete5450 target rows")
    need(all(type(row) is dict for row in rows), "Ordinary target records")
    need([row.get("epoch_id") for row in rows] == list(required_targets()), "Original exact ordered complete roster")
    return rows


def submission_bytes(rows):
    import numpy as np
    checked_complete_rows(rows)
    arrays = {"class_order": np.asarray(CLASSES)}
    at = 0
    for case, count in CASES:
        selected = rows[at:at + count]
        arrays[case + "__epoch_id"] = np.asarray([row["epoch_id"] for row in selected])
        arrays[case + "__probabilities"] = np.asarray([probabilities(row["probabilities"]) for row in selected], dtype=np.float64)
        at += count
    stream = io.BytesIO()
    np.savez(stream, **arrays)
    raw = stream.getvalue()
    need(len(raw) <= 4_000_000, "Original complete submission cap")
    return raw
