"""Future trusted, pinned BrainVision file provider. No execution at import.

All four authentic file bodies must be independently selected and acquired
before this API may be invoked. Pins authenticate bytes, not scientific truth.
This source module does not fetch data or grant execution authorization.
"""
import hashlib
import os
from pathlib import Path
import stat
import math
from contract import CHANNELS, RATE, SOURCE_COMMIT, PEOPLE, TASKS, require
from importer import parse_markers, parse_events


def open_pinned(root, pin, maximum):
    require(set(pin) == {"path", "bytes", "sha256"}, "exact file pin schema")
    rel = Path(pin["path"])
    require(not rel.is_absolute() and rel.parts and all(p not in (".", "..") for p in rel.parts)
            and rel.as_posix() == pin["path"] and "\\" not in pin["path"], "canonical relative path")
    require(type(pin["bytes"]) is int and 0 < pin["bytes"] <= maximum, "pinned byte bound")
    require(isinstance(pin["sha256"], str) and len(pin["sha256"]) == 64
            and all(c in "0123456789abcdef" for c in pin["sha256"]), "sha256 pin")
    base = Path(root)
    require(base.is_absolute() and not base.is_symlink(), "absolute ordinary intake root")
    path = base
    for part in rel.parts:
        path = path / part
        require(not path.is_symlink(), "source symlink forbidden")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and before.st_size == pin["bytes"], "source type/size mismatch")
        digest = hashlib.sha256()
        total = 0
        while True:
            part = os.read(fd, min(2**20, maximum + 1 - total))
            if not part:
                break
            total += len(part)
            require(total <= maximum, "source grew beyond limit")
            digest.update(part)
        after = os.fstat(fd)
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                and total == pin["bytes"] and digest.hexdigest() == pin["sha256"],
                "source changed or hash mismatched")
        os.lseek(fd, 0, os.SEEK_SET)
        return fd, after
    except BaseException:
        os.close(fd)
        raise


def _sections(text):
    sections, section = {}, None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            require(line not in sections, "duplicate header section")
            sections[line] = {}
            section = sections[line]
        elif section is not None and "=" in line:
            key, value = line.split("=", 1)
            require(key not in section, "duplicate header key")
            section[key] = value
    return sections


def parse_header(text, data_basename, marker_basename):
    require(isinstance(text, str) and len(text.encode()) <= 2**20, "header text bound")
    require(text.splitlines()[0].startswith("Brain Vision Data Exchange Header File"), "BrainVision version")
    sections = _sections(text)
    common, binary = sections.get("[Common Infos]", {}), sections.get("[Binary Infos]", {})
    require(common.get("DataFile") == data_basename and common.get("MarkerFile") == marker_basename,
            "header must reference the exact pinned recording pair")
    require(common.get("DataFormat") == "BINARY" and common.get("DataOrientation") == "MULTIPLEXED",
            "only explicit binary multiplexed source accepted")
    require(common.get("NumberOfChannels") == str(CHANNELS), "62-channel native source required")
    interval = float(common.get("SamplingInterval", "nan"))
    require(math.isfinite(interval) and abs(interval - 1e6 / RATE) <= .001,
            "native interval differs from600Hz")
    require(binary.get("UseBigEndianOrder", "NO") == "NO", "big-endian provider unsupported")
    dtype = {"IEEE_FLOAT_32": "<f4", "INT_16": "<i2"}.get(binary.get("BinaryFormat"))
    require(dtype is not None, "unimplemented binary encoding")
    channel_info = sections.get("[Channel Infos]", {})
    require(set(channel_info) == {"Ch" + str(i) for i in range(1, 63)}, "exact channel schema")
    names, scales = [], []
    for i in range(1, 63):
        fields = channel_info["Ch" + str(i)].split(",")
        require(len(fields) == 4, "channel label/reference/resolution/unit fields")
        name, _, resolution, unit = fields
        require(name and "\\" not in name and name not in names, "simple unique channel labels")
        scale = float(resolution)
        require(math.isfinite(scale) and scale > 0 and unit in ("µV", "uV", "μV"), "microvolt native scale")
        names.append(name)
        scales.append(scale)
    require("PO4" in names and "TP8" in names, "known-channel names absent")
    return {"dtype": dtype, "channel_names": names, "scales": scales,
            "sampling_hz": RATE, "units": "uV", "source_commit": SOURCE_COMMIT,
            "policy": "raw_fixed_window_v1",
            "bad_channel_policy": "global_zero_PO4_TP8_before_average_reference"}


class Recording:
    """Context-managed pinned raw reader; stable descriptor retained until close."""
    def __init__(self, intake_root, selection):
        import numpy as np
        require(set(selection) == {"source_commit", "participant", "task", "files"}, "recording selection schema")
        require(selection["source_commit"] == SOURCE_COMMIT, "recording source version")
        person, task = selection["participant"], selection["task"]
        require(person in PEOPLE and task in TASKS, "declared source participant/task")
        files = selection["files"]
        require(set(files) == {"header", "markers", "events", "signal"}, "all four authentic file pins required")
        prefix = f"{person}/eeg/{person}_task-{task}"
        expected = {"header": prefix + "_eeg.vhdr", "markers": prefix + "_eeg.vmrk",
                    "signal": prefix + "_eeg.eeg", "events": prefix + "_events.tsv"}
        require(all(isinstance(files[role], dict) and files[role].get("path") == path
                    for role, path in expected.items()),
                "source file paths must bind exact participant and task")
        text = {}
        for role in ("header", "markers", "events"):
            fd, info = open_pinned(intake_root, files[role], 2**20)
            try:
                body = os.read(fd, info.st_size + 1)
                after = os.fstat(fd)
                require(len(body) == info.st_size
                        and hashlib.sha256(body).hexdigest() == files[role]["sha256"]
                        and (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
                        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                        "source metadata changed after authentication")
                text[role] = body.decode("utf-8-sig")
            finally:
                os.close(fd)
        self.certificate = parse_header(text["header"], Path(files["signal"]["path"]).name,
                                        Path(files["markers"]["path"]).name)
        self.rows = parse_events(text["events"], selection["participant"], selection["task"],
                                 parse_markers(text["markers"]))
        self.dtype = np.dtype(self.certificate["dtype"])
        self.fd, self.stat = open_pinned(intake_root, files["signal"], 8 * 2**30)
        try:
            require(self.stat.st_size % (CHANNELS * self.dtype.itemsize) == 0, "partial raw sample")
            self.n_samples = self.stat.st_size // (CHANNELS * self.dtype.itemsize)
            require(all(r["start"] >= 301 and r["start"] + 301 <= self.n_samples for r in self.rows),
                    "primary or premarker window extends outside signal")
        except BaseException:
            self.close()
            raise

    def __call__(self, start, stop):
        import numpy as np
        require(self.fd is not None and type(start) is int and type(stop) is int
                and 0 <= start < stop <= self.n_samples and stop - start <= 301, "bounded native range")
        current = os.fstat(self.fd)
        require((current.st_size, current.st_mtime_ns, current.st_ctime_ns) ==
                (self.stat.st_size, self.stat.st_mtime_ns, self.stat.st_ctime_ns), "raw file mutated after authentication")
        length = (stop - start) * CHANNELS * self.dtype.itemsize
        body = os.pread(self.fd, length, start * CHANNELS * self.dtype.itemsize)
        require(len(body) == length, "short raw read")
        after = os.fstat(self.fd)
        require((after.st_size, after.st_mtime_ns, after.st_ctime_ns) ==
                (self.stat.st_size, self.stat.st_mtime_ns, self.stat.st_ctime_ns), "raw file mutated during range read")
        x = np.frombuffer(body, dtype=self.dtype).reshape(stop - start, CHANNELS).T.astype(np.float64)
        return x * np.asarray(self.certificate["scales"])[:, None]

    def close(self):
        if getattr(self, "fd", None) is not None:
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
