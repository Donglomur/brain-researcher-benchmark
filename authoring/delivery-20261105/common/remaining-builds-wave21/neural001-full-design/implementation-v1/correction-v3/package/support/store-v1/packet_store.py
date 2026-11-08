"""Bounded operator-only prepared-packet store; never a candidate capability.

Owner must authorize authentic admission before constructing/using this store.
No source body is opened on import or while validating constructor descriptors.
Candidates receive serialize_* results in isolated contexts, never this object,
its root, records, source paths, full query cache or any target/private key.
"""
from contextlib import contextmanager
import hashlib
import io
import math
import os
from pathlib import PurePosixPath
import re
import stat
import zipfile

import numpy as np

from support import packets as p

MAX_SOURCE_BYTES = 1500000000


class IOBudget:
    """Monotone attempted logical extents; no refunds on failed operations.

    Expanded and materialized extents are different from source bytes. Counters
    are not physical I/O/RSS measurements, nor whole-study resource authority.
    """
    def __init__(self, *, source_read_limit, expanded_limit, materialized_limit, serialized_limit):
        self.limits = dict(source_read=source_read_limit, expanded=expanded_limit,
                           materialized=materialized_limit, serialized=serialized_limit)
        p.require(all(type(n) is int and n >= 0 for n in self.limits.values()), "Finite nonnegative logical byte limits")
        self.used = {key: 0 for key in self.limits}
        self.refusals = []

    def charge(self, category, amount):
        p.require(category in self.limits and type(amount) is int and amount >= 0, "Known nonnegative charge")
        if self.used[category] + amount > self.limits[category]:
            self.refusals.append({"category": category, "attempted_bytes": amount,
                                  "already_charged_bytes": self.used[category]})
            raise ValueError("Logical byte budget exhausted before operation")
        self.used[category] += amount

    def report(self):
        return {"limits": dict(self.limits), "charged": dict(self.used),
                "refusals": [dict(row) for row in self.refusals],
                "meaning": "Attempted logical body/decompression/materialization/serialization extents; not physical I/O or RSS."}


def _pin(pin, basename):
    p.require(type(pin) is dict and set(pin) == {"path", "bytes", "sha256"}, "Exact prepared-file pin")
    value = pin["path"]
    p.require(type(value) is str and value, "Contained source path")
    path = PurePosixPath(value)
    p.require(not path.is_absolute() and path.as_posix() == value and
              all(part not in ("", ".", "..") for part in path.parts) and path.name == basename,
              "Canonical contained training/queries filename")
    p.require(type(pin["bytes"]) is int and 0 < pin["bytes"] <= MAX_SOURCE_BYTES and
              type(pin["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", pin["sha256"]),
              "Bounded exact source byte/SHA identity")
    return path.parts


@contextmanager
def _directory_fd(absolute_root):
    root = PurePosixPath(absolute_root)
    p.require(type(absolute_root) is str and root.is_absolute() and root.as_posix() == absolute_root
              and ".." not in root.parts, "Canonical absolute store root")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open("/", flags)
    try:
        for part in root.parts[1:]:
            next_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        yield fd
    finally:
        os.close(fd)


def _ordinary_source(root, pin, basename, budget):
    parts = _pin(pin, basename)
    budget.charge("source_read", pin["bytes"])
    with _directory_fd(root) as root_fd:
        directory_fd = os.dup(root_fd)
        try:
            for part in parts[:-1]:
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory_fd)
                os.close(directory_fd)
                directory_fd = next_fd
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
        finally:
            os.close(directory_fd)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            p.require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                      before.st_size == pin["bytes"], "Ordinary single-link exact-size source")
            body = stream.read(pin["bytes"])
            after = os.fstat(stream.fileno())
    p.require(len(body) == pin["bytes"] and all(getattr(before, key) == getattr(after, key)
              for key in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")),
              "Stable complete source read")
    p.require(hashlib.sha256(body).hexdigest() == pin["sha256"], "Exact prepared source bytes")
    return body


def _npz(body, spec, budget):
    """Authenticate predetermined NPY shapes before materializing numeric values."""
    result = {}
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        rows = archive.infolist()
        p.require(len(rows) == len(spec) and len({row.filename for row in rows}) == len(rows)
                  and {row.filename for row in rows} == {name + ".npy" for name in spec},
                  "Exact prepared NPZ member set")
        numeric_bytes = sum(math.prod(shape) * np.dtype(dtype).itemsize for dtype, shape in spec.values())
        p.require(sum(row.file_size for row in rows) <= numeric_bytes + len(spec) * 4106,
                  "Bounded complete NPY expansion from admitted shapes")
        budget.charge("expanded", sum(row.file_size for row in rows))
        budget.charge("materialized", numeric_bytes)
        for row in rows:
            p.require(row.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                      and not row.flag_bits & 1 and stat.S_IFMT(row.external_attr >> 16) in (0, stat.S_IFREG),
                      "Ordinary nonencrypted NPY source member")
            raw = archive.read(row)
            header, start = p._header(raw)
            name = row.filename[:-4]
            dtype, shape = spec[name]
            p.require(header == {"descr": dtype, "fortran_order": False, "shape": shape} and
                      len(raw) == start + math.prod(shape) * np.dtype(dtype).itemsize,
                      "Exact NPY dtype/shape/order/extent; no object/pickle/trailing values")
            array = np.frombuffer(raw, dtype=np.dtype(dtype), offset=start).reshape(shape).copy()
            array.flags.writeable = False
            result[name] = array
    return result


def _training_descriptor(desc, person):
    fields = {"pin", "samples", "epoch_ids", "epoch_runs", "epoch_lengths", "run_ids",
              "channel_labels", "channel_kinds"}
    p.require(type(desc) is dict and set(desc) == fields, "Exact full training descriptor")
    _pin(desc["pin"], "training.npz")
    p.require(type(desc["samples"]) is int and 4 <= desc["samples"] <= p.MAX_TRAIN_ROWS,
              "Complete training rows within provisional cap; never crop")
    for name in ("epoch_ids", "epoch_runs", "epoch_lengths", "run_ids"):
        p.require(type(desc[name]) is list, "Ordinary training descriptor lists")
    count = len(desc["epoch_ids"])
    p.require(count >= 2 and count == len(desc["epoch_runs"]) == len(desc["epoch_lengths"])
              and len(set(desc["epoch_ids"])) == count and
              all(type(n) is int and n >= 4 for n in desc["epoch_lengths"])
              and sum(desc["epoch_lengths"]) == desc["samples"], "Exact epoch/run/length alignment")
    expected_count = 2 if person == "sub-01" else 4
    p.require(len(desc["run_ids"]) == expected_count and len(set(desc["run_ids"])) == expected_count
              and set(desc["epoch_runs"]) == set(desc["run_ids"]), "All original released person runs contribute")
    for ident in desc["epoch_ids"] + desc["epoch_runs"] + desc["run_ids"]:
        p.opaque_id(ident)
    p.validate_channels(desc["channel_labels"], desc["channel_kinds"])


class PacketStore:
    """Trusted operator store with at most one person's query arrays cached.

    Source query caching does not authorize giving a candidate the cache or its
    path. Serialization is the only intended candidate-facing transfer.
    """
    def __init__(self, root, records, budget):
        p.require(type(root) is str, "Operator store root string")
        p.require(type(records) is dict and set(records) == set(p.PERSONS), "All24 person source records")
        p.require(type(budget) is IOBudget, "Explicit cumulative IO budget")
        p.validate_study_manifest([records[person]["subject"] for person in p.PERSONS])
        for person in p.PERSONS:
            record = records[person]
            p.require(type(record) is dict and set(record) == {"subject", "training", "queries"}
                      and record["subject"]["id"] == person, "Exact matching source record")
            _training_descriptor(record["training"], person)
            query = record["queries"]
            p.require(type(query) is dict and set(query) == {"pin", "channel_labels"}, "Exact query descriptor")
            _pin(query["pin"], "queries.npz")
            p.require(query["channel_labels"] == record["training"]["channel_labels"],
                      "Query/training channel identity and order")
        # Deep-copy ordinary descriptor lists/dicts without serialization or key/file access.
        def clone(value):
            if type(value) is dict: return {key: clone(item) for key, item in value.items()}
            if type(value) is list: return [clone(item) for item in value]
            if type(value) is tuple: return tuple(clone(item) for item in value)
            p.require(type(value) in (str, int), "Source descriptors contain only ordinary strings/integers")
            return value
        self._root = root
        self._records = clone(records)
        self._budget = budget
        self._query_cache = None

    def load_training(self, person, arm="neural"):
        p.require(person in p.PERSONS and arm in p.ARMS, "Declared person and arm")
        desc = self._records[person]["training"]
        n, e = desc["samples"], len(desc["epoch_ids"])
        spec = {"meg": ("<f8", (n, 306)), "envelope": ("<f8", (n,)),
                "offsets": ("<i8", (e + 1,)), "interval_ids": ("<U32", (e,)),
                "run_ids": ("<U32", (e,)), "channel_labels": ("<U16", (306,))}
        view = _npz(_ordinary_source(self._root, desc["pin"], "training.npz", self._budget), spec, self._budget)
        p.require(view["interval_ids"].tolist() == desc["epoch_ids"] and
                  view["run_ids"].tolist() == desc["epoch_runs"] and
                  np.diff(view["offsets"]).tolist() == desc["epoch_lengths"] and
                  view["channel_labels"].tolist() == list(desc["channel_labels"]),
                  "All exact training epoch/run/length/channel metadata agree")
        view["channel_labels"] = tuple(desc["channel_labels"])
        view["channel_kinds"] = tuple(desc["channel_kinds"])
        view["fs_hz"] = 64
        p.validate_training_view(view, desc["run_ids"])
        if arm == "no_neural":
            copied_bytes = sum(view[name].nbytes for name in ("envelope", "offsets", "interval_ids", "run_ids"))
            self._budget.charge("materialized", copied_bytes)
            return p.no_neural_training_view(view, desc["run_ids"])
        return view

    def clear_query_cache(self):
        self._query_cache = None  # Cumulative charges never reset/refund.

    def load_query(self, person, opaque_query_id, arm="neural"):
        p.require(person in p.PERSONS and arm in p.ARMS, "Declared person and arm")
        p.opaque_id(opaque_query_id)
        record = self._records[person]
        subject, desc = record["subject"], record["queries"]
        p.require(opaque_query_id in subject["query_ids"], "Query belongs to current person")
        index = subject["query_ids"].index(opaque_query_id)
        first, last = subject["query_offsets"][index:index + 2]
        if arm == "no_neural":
            # Uses admitted exact support metadata only, never MEG or query-batch statistics.
            return p.make_query_view(opaque_query_id, None, None, None, arm, length=last - first)
        if self._query_cache is None or self._query_cache[0] != person:
            n = subject["query_samples"]
            spec = {"meg": ("<f8", (n, 306)), "offsets": ("<i8", (121,)),
                    "interval_ids": ("<U32", (120,)), "channel_labels": ("<U16", (306,))}
            arrays = _npz(_ordinary_source(self._root, desc["pin"], "queries.npz", self._budget), spec, self._budget)
            p.require(arrays["interval_ids"].tolist() == subject["query_ids"] and
                      arrays["offsets"].tolist() == subject["query_offsets"] and
                      arrays["channel_labels"].tolist() == list(desc["channel_labels"])
                      and np.isfinite(arrays["meg"]).all(), "Exact complete query IDs/support/channel data")
            self._query_cache = (person, arrays)
        meg = self._query_cache[1]["meg"][first:last]
        # p.make_query_view copies once, plus an explicit temporary roll in shifted arm.
        self._budget.charge("materialized", meg.nbytes * (2 if arm == "within_query_half_shift" else 1))
        return p.make_query_view(opaque_query_id, meg, record["training"]["channel_labels"],
                                 record["training"]["channel_kinds"], arm)


def _serialize_arrays(arrays, budget):
    """NPY1/stored ZIP, with a prospective upper charge before byte allocation."""
    p.require(all(type(array) is np.ndarray and array.flags.c_contiguous and
                  array.dtype.kind in ("f", "i", "U") for array in arrays.values()),
              "Only ordinary C-order numeric/Unicode arrays")
    upper = sum(array.nbytes + 4106 + 2 * len(name.encode("ascii")) + 256
                for name, array in arrays.items()) + 256
    budget.charge("serialized", upper)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, array in arrays.items():
            stream = io.BytesIO()
            np.lib.format.write_array(stream, array, version=(1, 0), allow_pickle=False)
            archive.writestr(name + ".npy", stream.getvalue())
    body = output.getvalue()
    p.require(len(body) <= upper, "Serialization stayed inside prospective bound")
    return body


def serialize_query(view, budget):
    """Return (allowed_json_metadata, current_query_npz_or_None), no source path."""
    p.require(type(budget) is IOBudget and type(view) is dict, "Typed query serialization")
    arm = view.get("arm")
    basic = {"id", "length", "arm", "fs_hz"}
    p.require(arm in p.ARMS and view.get("fs_hz") == 64, "Declared query arm/clock")
    p.opaque_id(view["id"])
    p.require(type(view["length"]) is int and 4 <= view["length"] <= p.MAX_QUERY_ROWS, "Current query extent")
    if arm == "no_neural":
        p.require(set(view) == basic, "No-neural context has no signal/sensor payload")
        return dict(view), None
    p.require(set(view) == basic | {"meg", "channel_labels", "channel_kinds"}, "One-query view only")
    p.validate_channels(view["channel_labels"], view["channel_kinds"])
    meg = view["meg"]
    p.require(type(meg) is np.ndarray and meg.dtype.str == "<f8" and
              meg.shape == (view["length"], 306) and np.isfinite(meg).all(), "One complete current signal")
    metadata = {key: view[key] for key in ("id", "length", "arm", "fs_hz")}
    metadata.update(channel_labels=list(view["channel_labels"]), channel_kinds=list(view["channel_kinds"]))
    return metadata, _serialize_arrays({"meg": meg}, budget)


def serialize_training(view, arm, expected_run_ids, budget):
    """Return allowed training metadata and NPZ; no canonical person/source path."""
    p.require(type(view) is dict and type(budget) is IOBudget and arm in p.ARMS, "Typed training serialization")
    basic = {"envelope", "offsets", "interval_ids", "run_ids", "fs_hz"}
    if arm == "no_neural":
        p.require(set(view) == basic and view["fs_hz"] == 64, "Only no-neural training fields")
        env, off, ids, runs = (view[key] for key in ("envelope", "offsets", "interval_ids", "run_ids"))
        p.require(type(env) is np.ndarray and env.dtype.str == "<f8" and env.ndim == 1 and
                  4 <= len(env) <= p.MAX_TRAIN_ROWS and np.isfinite(env).all(), "Complete finite training envelope")
        p.require(type(off) is np.ndarray and off.dtype.str == "<i8" and off.ndim == 1 and len(off) >= 3
                  and off[0] == 0 and off[-1] == len(env) and np.all(np.diff(off) >= 4), "Complete prior epochs")
        for value in (ids, runs):
            p.require(type(value) is np.ndarray and value.dtype.str == "<U32" and value.shape == (len(off) - 1,),
                      "Exact prior epoch/run metadata")
            for ident in value.tolist(): p.opaque_id(ident)
        p.require(len(set(ids.tolist())) == len(ids) and len(expected_run_ids) in (2, 4)
                  and len(set(expected_run_ids)) == len(expected_run_ids) and set(runs.tolist()) == set(expected_run_ids),
                  "Every admitted training run retained")
        metadata = {"fs_hz": 64, "arm": arm}
    else:
        p.validate_training_view(view, expected_run_ids)
        metadata = {"fs_hz": 64, "arm": arm, "channel_labels": list(view["channel_labels"]),
                    "channel_kinds": list(view["channel_kinds"])}
    names = ("envelope", "offsets", "interval_ids", "run_ids") + (() if arm == "no_neural" else ("meg",))
    return metadata, _serialize_arrays({name: view[name] for name in names}, budget)
