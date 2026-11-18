"""Trusted operator's NEURAL-019 raster renderer and complete answer collector.

This is an in-process construction component, not a participant sandbox or
transport. SVG text must be rendered by an independently qualified image-only
transport before any image-viewer interpretation claim. No private targets,
reference models, fitting, scoring or participant execution are provided here.
"""
from __future__ import annotations

import hashlib
import html
import json
import math
import os
from pathlib import Path
import stat
import zipfile

import numpy as np

TRAIN, QUERIES, BINS, UNITS = 1340, 126, 140, 137
PACKET_BYTES = 59347496
PACKET_SHA256 = "98e9b00b9a641e3aa1117c2ea2d737956c3e0df5daa8e77105d34a3449ef02c2"
SHAPES = {
    "train_counts": (TRAIN, BINS, UNITS),
    "assessment_counts": (QUERIES, BINS, UNITS),
    "train_velocity": (TRAIN, BINS, 2),
    "train_trial_ids": (TRAIN,), "assessment_trial_ids": (QUERIES,),
    "neural_unit_ids": (UNITS,), "train_group_ids": (TRAIN,),
    "train_cv_fold_ids": (TRAIN,), "neural_left_edges_ms": (BINS,),
    "velocity_left_edges_ms": (BINS,), "velocity_axes": (2,),
    "velocity_units": (), "panel_fingerprint": (),
}
REQUEST_BYTES = 32768
_AUTHENTIC = object()


def need(value, message):
    if not value:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def decode_request(raw):
    need(type(raw) is bytes and 0 < len(raw) <= REQUEST_BYTES, "Bounded UTF-8 request bytes required")
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "Duplicate request key")
            result[key] = value
        return result
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                       parse_constant=lambda _: need(False, "Nonfinite JSON"))
    need(type(value) is dict, "Request object required")
    return value


def _dtype(name, dtype):
    need(not dtype.hasobject, "No object arrays")
    if name.endswith("counts"):
        need(dtype == np.dtype("uint16"), "Exact uint16 counts")
    elif name == "train_velocity":
        need(dtype == np.dtype("float64"), "Exact float64 training velocity")
    elif name == "train_cv_fold_ids":
        need(dtype.kind in "iu" and dtype.itemsize <= 8, "Bounded integer training folds")
    elif name == "train_group_ids":
        need((dtype.kind in "iu" and dtype.itemsize <= 8) or
             (dtype.kind == "U" and 0 < dtype.itemsize <= 256), "Bounded training groups")
    elif name.endswith("edges_ms"):
        need(dtype.kind in "ifu" and dtype.itemsize <= 8, "Bounded real time axis")
    else:
        need(dtype.kind == "U" and 0 < dtype.itemsize <= 256, "Bounded Unicode metadata")


def _validate(values):
    need(type(values) is dict and set(values) == set(SHAPES), "Exact public-only fields required")
    for name, shape in SHAPES.items():
        value = values[name]
        need(isinstance(value, np.ndarray) and value.shape == shape, "Exact shape: " + name)
        _dtype(name, value.dtype)
    for name in ("train_trial_ids", "assessment_trial_ids", "neural_unit_ids"):
        ids = values[name].tolist()
        need(all(ids) and len(set(ids)) == len(ids), "Unique nonempty anonymous identities")
    need(set(values["train_trial_ids"].tolist()).isdisjoint(values["assessment_trial_ids"].tolist()),
         "Training and assessment identities must be disjoint")
    need(np.array_equal(values["neural_left_edges_ms"], np.arange(-250, 450, 5)), "Exact neural clock")
    need(np.array_equal(values["velocity_left_edges_ms"], np.arange(-150, 550, 5)), "Exact velocity clock")
    need(np.array_equal(values["velocity_axes"], ["x", "y"]) and
         values["velocity_units"].item() == "m/s", "Exact axes and physical velocity units")
    fingerprint = values["panel_fingerprint"].item()
    need(len(fingerprint) == 64 and all(c in "0123456789abcdef" for c in fingerprint), "Panel fingerprint")
    need(np.isfinite(values["train_velocity"]).all(), "Finite training calibration")
    groups, folds = values["train_group_ids"], values["train_cv_fold_ids"]
    need(len(np.unique(groups)) == 28 and set(folds.tolist()) == {0, 1, 2, 3}, "All28 training groups/four folds")
    if groups.dtype.kind == "U":
        need(np.all(groups != ""), "Nonempty training groups")
    for group in np.unique(groups):
        need(len(np.unique(folds[groups == group])) == 1, "Whole training group stays in one fold")


def load_public(path, *, max_actions):
    """Future admitted operator route; exact fixed packet only, no pin override.

    Hashes the complete compressed file before parsing, bounds each NPY geometry
    before allocation, then checks source stability after reading. This function
    has not been exercised on authentic data by the construction controls.
    """
    path = Path(path).absolute()
    need(not any(p.is_symlink() for p in (path, *path.parents)), "No linked source paths")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        first = os.fstat(fd)
        need(stat.S_ISREG(first.st_mode) and first.st_nlink == 1 and first.st_size == PACKET_BYTES,
             "Exact bounded ordinary public packet")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            h = hashlib.sha256()
            for block in iter(lambda: stream.read(65536), b""):
                h.update(block)
            need(h.hexdigest() == PACKET_SHA256, "Exact public packet identity")
            stream.seek(0)
            with zipfile.ZipFile(stream) as archive:
                entries = archive.infolist()
                need(len(entries) == len(SHAPES) and {r.filename for r in entries} ==
                     {k + ".npy" for k in SHAPES}, "Exact unique public NPZ inventory")
                need(sum(r.file_size for r in entries) <= 64 * 1024**2, "Expanded public packet bound")
                for row in entries:
                    need(not row.is_dir() and not row.flag_bits & 1 and
                         stat.S_IFMT(row.external_attr >> 16) in (0, stat.S_IFREG) and
                         row.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), "Ordinary supported NPY")
                    with archive.open(row) as member:
                        version = np.lib.format.read_magic(member)
                        need(version in ((1, 0), (2, 0)), "Supported NPY version")
                        reader = (np.lib.format.read_array_header_1_0 if version == (1, 0)
                                  else np.lib.format.read_array_header_2_0)
                        shape, fortran, dtype = reader(member, max_header_size=10000)
                        name = row.filename[:-4]
                        need(shape == SHAPES[name] and type(fortran) is bool, "Exact public header geometry")
                        _dtype(name, dtype)
                        need(member.tell() + math.prod(shape) * dtype.itemsize == row.file_size,
                             "Exact NPY payload extent")
            stream.seek(0)
            with np.load(stream, allow_pickle=False) as archive:
                values = {name: archive[name] for name in SHAPES}
            last = os.fstat(fd)
            fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")
            need(all(getattr(first, k) == getattr(last, k) == getattr(path.lstat(), k) for k in fields),
                 "Public source changed during reading")
        return Session(values, max_actions=max_actions, _authentication=_AUTHENTIC)
    finally:
        os.close(fd)


class Session:
    """Operator-owned public-only state. Never hand this object to a participant.

    Bare construction accepts in-memory generated or operator-supplied values and
    is always marked unauthenticated. Only load_public can record fixed identity.
    max_actions is an explicit operator-selected budget, not a qualified study
    default. It includes failed requests and the final finish request.
    """
    def __init__(self, values, *, max_actions, _authentication=None):
        need(type(max_actions) is int and QUERIES + 1 <= max_actions <= 200000,
             "Explicit bounded action budget must permit complete answers and finish")
        _validate(values)
        self._data = {name: value.copy() for name, value in values.items()}
        for value in self._data.values():
            value.flags.writeable = False
        self._answers = {}
        self._events = []
        self._chain = "0" * 64
        self._budget = max_actions
        self._closed = False
        self._authenticated = _authentication is _AUTHENTIC

    def _view(self, request):
        need(set(request) == {"action", "role", "trial", "unit_start", "unit_stop", "bin_start", "bin_stop"},
             "Exact typed view fields")
        role = request["role"]
        need(role in ("calibration", "assessment"), "Named public role only")
        for name in ("trial", "unit_start", "unit_stop", "bin_start", "bin_stop"):
            need(type(request[name]) is int, "Integer view coordinates")
        trial = request["trial"]
        need(0 <= trial < (TRAIN if role == "calibration" else QUERIES), "Complete role trial range")
        u0, u1, b0, b1 = (request[k] for k in ("unit_start", "unit_stop", "bin_start", "bin_stop"))
        need(0 <= u0 < u1 <= UNITS and u1 - u0 <= 16, "At most16 exact units per view")
        need(0 <= b0 < b1 <= BINS and b1 - b0 <= 20, "At most20 exact bins per view")
        counts = self._data[("train" if role == "calibration" else "assessment") + "_counts"][trial]
        width = max(760, 100 + (b1 - b0) * 54)
        raster_bottom = 112 + (u1 - u0) * 24
        height = raster_bottom + (52 + (b1 - b0) * 19 if role == "calibration" else 32)
        pieces = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
                  '<rect width="100%" height="100%" fill="white"/>',
                  '<g font-family="monospace" font-size="12" fill="black">',
                  f'<text x="10" y="20">NEURAL-019 {role} trial {trial}; spikes per5ms; exact integer counts</text>',
                  '<text x="10" y="40">Neural clock shown; target velocity clock = neural clock +100ms. Retrospective.</text>']
        if role == "calibration":
            group = html.escape(str(self._data["train_group_ids"][trial]), quote=True)
            fold = int(self._data["train_cv_fold_ids"][trial])
            pieces.append(f'<text x="10" y="60">Training group {group}; training fold {fold}; measured calibration below</text>')
        else:
            pieces.append('<text x="10" y="60">Assessment velocity is unavailable. Response requires all140 x/y pairs in m/s.</text>')
        for b in range(b0, b1):
            x = 94 + (b - b0) * 54
            pieces.append(f'<text x="{x}" y="86">{int(self._data["neural_left_edges_ms"][b])}</text>')
        for u in range(u0, u1):
            y = 112 + (u - u0) * 24
            pieces.append(f'<text x="10" y="{y}">unit {u}</text>')
            for b in range(b0, b1):
                count = int(counts[b, u])
                x = 90 + (b - b0) * 54
                # Fixed zero/nonzero background; every exact count is printed.
                fill = "#e6eef8" if count else "#ffffff"
                pieces.extend((f'<rect x="{x}" y="{y-16}" width="53" height="23" fill="{fill}" stroke="#cccccc"/>',
                               f'<text x="{x+3}" y="{y}" data-bin="{b}" data-unit="{u}">{count}</text>'))
        if role == "calibration":
            pieces.append(f'<text x="10" y="{raster_bottom+20}">Velocity clock(ms) | measured x(m/s) | measured y(m/s)</text>')
            for offset, b in enumerate(range(b0, b1)):
                vx, vy = (repr(float(v)) for v in self._data["train_velocity"][trial, b])
                stamp = int(self._data["velocity_left_edges_ms"][b])
                pieces.append(f'<text x="10" y="{raster_bottom+40+offset*19}" data-calibration-bin="{b}">{stamp} | {vx} | {vy}</text>')
        pieces.append('</g></svg>')
        svg = "\n".join(pieces)
        need(len(svg.encode()) <= 131072, "Bounded SVG output")
        return {"kind": "svg", "svg": svg, "role": role, "trial": trial,
                "unit_range": [u0, u1], "bin_range": [b0, b1],
                "rendering_transport_qualified": False}

    def _answer(self, request):
        need(set(request) == {"action", "trial", "velocity"}, "Exact answer fields")
        trial, values = request["trial"], request["velocity"]
        need(type(trial) is int and 0 <= trial < QUERIES, "Exact assessment trial range")
        need(trial not in self._answers, "First final answer is immutable")
        need(type(values) is list and len(values) == BINS and
             all(type(row) is list and len(row) == 2 for row in values), "All140 x/y pairs required")
        need(all(type(v) in (int, float) and math.isfinite(v) for row in values for v in row),
             "Finite signed numerical velocity; no bools or fill")
        array = np.asarray(values, dtype=np.float64)
        need(np.isfinite(array).all(), "Finite float64 velocity")
        array.flags.writeable = False
        self._answers[trial] = array
        return {"kind": "answer_committed", "trial": trial,
                "answer_sha256": digest(encoded(array.tolist())), "answered": len(self._answers)}

    def dispatch(self, raw):
        need(not self._closed, "Session already closed")
        need(len(self._events) < self._budget, "Declared action budget exhausted")
        raw_pin = digest(raw) if type(raw) is bytes and len(raw) <= REQUEST_BYTES else None
        try:
            request = decode_request(raw)
            action = request.get("action")
            if action == "view":
                result = self._view(request)
            elif action == "answer":
                result = self._answer(request)
            elif action == "finish":
                need(set(request) == {"action"}, "Exact finish fields")
                need(set(self._answers) == set(range(QUERIES)), "All126 complete trajectories required")
                self._closed = True
                result = {"kind": "collection_complete", "cases": QUERIES,
                          "velocity_values": QUERIES * BINS * 2, "scored": False}
            else:
                raise ValueError("Only view, answer and finish actions are supported")
            output_pin = digest(encoded(result))
            event = {"request_sha256": raw_pin, "response_sha256": output_pin, "status": "accepted"}
        except (ValueError, TypeError, OverflowError, UnicodeError, RecursionError) as error:
            event = {"request_sha256": raw_pin, "status": "rejected", "error": type(error).__name__}
            self._record(event)
            raise ValueError("Invalid typed viewer request") from error
        self._record(event)
        return result

    def _record(self, event):
        event = dict(event, sequence=len(self._events), previous_sha256=self._chain)
        self._chain = digest(encoded(event))
        self._events.append(dict(event, sha256=self._chain))

    def submission(self):
        """Operator-only export after complete collection; unchanged six-field schema."""
        need(self._closed, "Close a complete collection before exporting")
        return {"velocity": np.stack([self._answers[i] for i in range(QUERIES)]),
                "trial_ids": self._data["assessment_trial_ids"].copy(),
                **{k: self._data[k].copy() for k in
                   ("velocity_left_edges_ms", "velocity_axes", "velocity_units", "panel_fingerprint")}}

    def receipt(self):
        return {"schema": "neural019_typed_viewer_collection_v1", "closed": self._closed,
                "answered": len(self._answers), "actions": len(self._events),
                "declared_max_actions": self._budget, "event_chain_sha256": self._chain,
                "public_packet_authenticated": self._authenticated,
                "public_packet_sha256": PACKET_SHA256 if self._authenticated else None,
                "native_understanding_measured": False, "transport_qualified": False,
                "scored": False, "private_targets_received": False}

    def events(self):
        return [dict(event) for event in self._events]
