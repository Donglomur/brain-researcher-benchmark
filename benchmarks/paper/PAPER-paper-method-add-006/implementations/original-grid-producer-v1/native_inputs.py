"""Consume the existing identity-preserving 128-packet native preparation.

No HDF5 parser is replaced: the existing preparer's source-native unit, trial,
time and epoch identities are retained. Its strict_columns/training-unit list is
deliberately not a native filter. Loading is explicit and hash-bound.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import zipfile

import numpy as np
from glm_search import K, ContractError

SOURCE_ORDER = {
    "KL8": ("9fcb710b-00ea-435b-900c-454a5af46ab3",),
    "ER1": ("b6425692-0f32-4087-8412-aebcfc37cd96",),
    "JS34": ("b79b4575-b3c9-4449-ac4b-7a11c17bdbf9",),
    "JS14": ("4b7c7959-04b3-4817-8f96-1af6f41888c1",),
    "JS17": ("f1f51660-4c23-4b61-a6bd-64d817d141e5",),
    "JS21": ("f3a457e9-fa5b-45b4-9778-9c0e69de91a9",),
    "JS15": ("8fae63eb-84c2-4f7c-8a13-acb0832178f9",),
    "ZT2": ("785df3db-c72d-4ac7-927f-d88725dd4944", "efae9f4d-6628-4fcb-b1c1-414af48a9d08"),
}


def need(condition, message):
    if not condition:
        raise ContractError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def bounded_bytes(path, expected_bytes=None, limit=128 * 1024**2):
    path = Path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        need(stat.S_ISREG(info.st_mode), "input must be an ordinary file")
        need(0 < info.st_size <= limit and (expected_bytes is None or info.st_size == expected_bytes),
             "input byte count or ceiling differs")
        chunks, count = [], 0
        while count <= info.st_size:
            chunk = os.read(fd, min(1024**2, info.st_size + 1 - count))
            if not chunk:
                break
            count += len(chunk)
            chunks.append(chunk)
        data = b"".join(chunks)
        need(len(data) == info.st_size, "input byte count changed")
    finally:
        os.close(fd)
    return data


def checked_bytes(path, expected_sha, expected_bytes=None, limit=128 * 1024**2):
    data = bounded_bytes(path, expected_bytes, limit)
    need(sha256(data) == expected_sha, "input SHA256 differs")
    return data


def validate_design(design):
    need(design.get("schema") == "population_geometry_operator_design_v1", "native design schema")
    cases = design.get("cases", [])
    expected = [(a, s, r) for a in K.ANIMALS for s in range(1, 9) for r in K.REGIONS]
    need([(c.get("rat"), c.get("session"), c.get("area")) for c in cases] == expected,
         "complete ordered eight rats x eight sessions x two regions required")
    seen_epochs, seen_paths = set(), set()
    for c, (animal, session, region) in zip(cases, expected):
        need(type(c["session"]) is int and type(c.get("source_epoch")) is int
             and c["source_epoch"] >= 0, "native integer session and epoch required")
        need(c.get("id") == f"{animal}-s{session:02d}-{region}", "case identity differs")
        need(c.get("source_asset_id") in SOURCE_ORDER[animal], "native animal/asset identity differs")
        key = (animal, region, c["source_asset_id"], c["source_epoch"])
        need(key not in seen_epochs, "duplicate native epoch")
        seen_epochs.add(key)
        pin = c.get("native", {})
        need(pin.get("path") == c["id"] + ".npz" and pin["path"] not in seen_paths,
             "native packet must have distinct conventional path")
        seen_paths.add(pin["path"])
        need(type(pin.get("bytes")) is int and 0 < pin["bytes"] <= 128 * 1024**2,
             "native packet byte bound")
        digest = pin.get("sha256", "")
        need(len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), "native packet SHA256")
        need(type(c.get("rows")) is int and c["rows"] > 0, "native row count required")
    for i in range(0, 128, 2):
        a, b = cases[i:i + 2]
        need((a["source_asset_id"], a["source_epoch"], a["rows"]) ==
             (b["source_asset_id"], b["source_epoch"], b["rows"]), "paired regions must share native epoch")
    for animal in K.ANIMALS:
        observed = list(dict.fromkeys(c["source_asset_id"] for c in cases if c["rat"] == animal))
        need(observed == list(SOURCE_ORDER[animal]), "complete ordered source asset roster required")
    return cases


def load_packet(data, case):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        names = [i.filename for i in infos]
        expected = {s + ".npy" for s in ("x", "z", "t", "trial", "unit_ids", "strict_columns")}
        need(set(names) == expected and len(names) == len(expected), "numeric NPZ members differ")
        need(sum(i.file_size for i in infos) <= 128 * 1024**2, "expanded packet exceeds ceiling")
        raw_members, shapes = {}, {}
        for info in infos:
            raw = archive.read(info)
            stream = io.BytesIO(raw)
            version = np.lib.format.read_magic(stream)
            need(version in ((1, 0), (2, 0)), "supported numeric NPY version required")
            shape, fortran, dtype = np.lib.format._read_array_header(stream, version, max_header_size=16384)
            need(type(fortran) is bool and dtype.kind in "biuf" and not dtype.hasobject,
                 "plain numeric arrays with a boolean C/F storage-order flag required")
            need(all(type(v) is int and v >= 0 for v in shape), "array dimensions required")
            nbytes = math.prod(shape) * dtype.itemsize
            need(nbytes <= 128 * 1024**2 and stream.tell() + nbytes == len(raw),
                 "NPY shape and payload length disagree or exceed ceiling")
            key = info.filename[:-4]
            raw_members[key], shapes[key] = raw, shape
        n = case["rows"]
        need(len(shapes["x"]) == 2 and shapes["x"][0] == n and shapes["x"][1] > 0,
             "count header shape differs")
        need(shapes["z"] == (n, 7) and shapes["t"] == shapes["trial"] == (n,)
             and shapes["unit_ids"] == (shapes["x"][1],) and len(shapes["strict_columns"]) == 1,
             "native member header dimensions differ")
        # Original advanced column selection followed by astype(order='K') can
        # legitimately produce Fortran storage. Let NumPy decode each recorded
        # C/F flag; never reinterpret its flat bytes with a default-C reshape.
        arrays = {key: np.load(io.BytesIO(raw), allow_pickle=False) for key, raw in raw_members.items()}
    z = K.latents(arrays["z"])
    x = K.counts_array(arrays["x"], len(z))
    n, units = x.shape
    need(n == case["rows"], "packet row count differs from design")
    t, trial, ids = arrays["t"], arrays["trial"], arrays["unit_ids"]
    need(t.shape == (n,) and t.dtype.kind in "fiu" and np.isfinite(t).all()
         and (np.diff(t) > 0).all(), "native times must be finite and strictly increasing")
    need(trial.shape == (n,) and trial.dtype.kind in "iu" and (trial >= 0).all(), "native trial IDs required")
    need(ids.shape == (units,) and ids.dtype.kind in "iu" and (ids >= 0).all()
         and len(np.unique(ids)) == units, "all native region unit IDs required")
    need(np.isin(z[:, 5], (0, 1)).all(), "native trial correctness must be binary")
    unique_trials, first = np.unique(trial, return_index=True)
    correctness = z[first, 5]
    need(np.array_equal(z[:, 5], correctness[np.searchsorted(unique_trials, trial)]),
         "correctness must be constant within each native trial")
    aid, epoch = case["source_asset_id"], case["source_epoch"]
    rows = np.array([f"{aid}|epoch={epoch}|t={float(ti).hex()}|trial={int(tr)}"
                     for ti, tr in zip(t, trial)])
    return {"x": x, "z": z, "t": t, "trial": trial,
            "unit_ids": np.array([f"{aid}|unit={int(u)}" for u in ids]),
            "native_unit_ids": ids, "row_ids": rows,
            "source_asset_id": aid, "source_epoch": epoch, "case_id": case["id"],
            "packet_pin": case["native"], "represented_trial_ids": unique_trials,
            "represented_trial_correctness": correctness}


class PreparedPanel:
    def __init__(self, directory, design_path, design_sha256, coverage_path=None):
        self.directory = Path(directory)
        data = checked_bytes(design_path, design_sha256, limit=10 * 1024**2)
        self.design_sha256 = design_sha256
        self.cases = validate_design(json.loads(data))
        self.by_key = {(c["rat"], c["session"] - 1, c["area"]): c for c in self.cases}
        self.coverage = None
        if coverage_path is not None:
            # These exact historical metadata receipts establish equal-trial
            # support, including short trials. They are not a new data run.
            known_designs = {"fd4904ed7a96fb57b32eee36c50e859f1c69fd16c0614f5ff60a6985d8bb3da4",
                             "5ff7542d9d78aee6f86a4d97fa8e535882c3b582ac45aba5b4fdb5c026bde403"}
            need(design_sha256 in known_designs, "coverage receipt does not bind this design")
            self.coverage_sha256 = "82cf82f172ebbe00908517f6bef429f30eb0ec3904f225da9e761aa3282f473d"
            coverage = json.loads(checked_bytes(coverage_path, self.coverage_sha256, 15317))
            need(coverage.get("all_128_passed") is True and
                 coverage.get("schema") == "population_geometry_complete_trial_roster_guard_v1",
                 "complete historical coverage receipt required")
            self.coverage = {c["case_id"]: c for c in coverage["cases"]}
            need(len(coverage["cases"]) == len(self.coverage) == 128 and
                 set(self.coverage) == {c["id"] for c in self.cases}, "coverage case roster differs")

    def load_session(self, animal, session_index, region):
        case = self.by_key[(animal, session_index, region)]
        pin = case["native"]
        data = checked_bytes(self.directory / pin["path"], pin["sha256"], pin["bytes"])
        result = load_packet(data, case)
        result["design_sha256"] = self.design_sha256
        if self.coverage is not None:
            coverage = self.coverage[case["id"]]
            need(coverage["all_source_trials_represented"] is True and
                 coverage["source_trial_count"] == coverage["represented_trial_count"] ==
                 len(result["represented_trial_ids"]), "complete native trial support differs")
            result["epoch_trials"] = {"trial_ids": result["represented_trial_ids"],
                                      "correct": result["represented_trial_correctness"],
                                      "source_binding": f"coverage:{self.coverage_sha256};design:{self.design_sha256};packet:{pin['sha256']}"}
        return result

    def paired(self, animal, session_index):
        packets = [self.load_session(animal, session_index, region) for region in K.REGIONS]
        a, b = packets
        for key in ("z", "t", "trial", "row_ids"):
            need(np.array_equal(a[key], b[key]), "paired region native rows/latents differ")
        ids = np.concatenate([p["unit_ids"] for p in packets])
        need(len(np.unique(ids)) == len(ids), "native unit identity reused across regions")
        return {"latents": a["z"], "counts": np.column_stack([p["x"] for p in packets]),
                "bin_ids": a["row_ids"], "unit_ids": ids,
                "locations": np.concatenate([np.full(p["x"].shape[1], r) for p, r in zip(packets, K.REGIONS)])}
