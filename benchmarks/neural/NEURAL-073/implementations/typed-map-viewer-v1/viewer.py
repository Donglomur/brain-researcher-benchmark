"""Operator-owned native-grid viewer for NEURAL-073; not an isolation boundary.

The operator supplies already admitted canonical maps and blinded context keys.
Only dispatch() responses are suitable for a participant transport. Never pass
this Python object, its loader, or canonical bytes to the participant.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import math
import re
import struct
import time
import zlib


class ViewerError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise ViewerError(message)


def number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def token(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{32}", value) is not None


def digest(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def json_body(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class Limits:
    """Explicit operator-selected limits, measured logically, not OS limits."""

    max_voxels: int
    max_plane_pixels: int
    max_svg_bytes: int
    max_actions: int
    max_frames_per_case: int
    wall_seconds: float

    def validate(self):
        for name in ("max_voxels", "max_plane_pixels", "max_svg_bytes",
                     "max_actions", "max_frames_per_case"):
            value = getattr(self, name)
            need(type(value) is int and 1 <= value <= 2**31 - 1,
                 "invalid limit: " + name)
        need(number(self.wall_seconds) and self.wall_seconds > 0,
             "positive finite wall_seconds required")


@dataclass(frozen=True)
class CanonicalMap:
    """Immutable C-order little-endian float64 data supplied by the operator.

    SHA equality is an input-identity check, not scientific admission. Original
    NIfTI identity/fidelity and same-context permission must be established by
    the existing operator before this constructor is called.
    """

    body: bytes
    shape: tuple
    affine: tuple
    units: str
    sha256: str

    def validate(self, limits):
        need(type(limits) is Limits, "explicit limits required")
        limits.validate()
        need(type(self.body) is bytes, "immutable canonical bytes required")
        need(type(self.shape) is tuple and len(self.shape) == 3 and
             all(type(n) is int and n >= 4 for n in self.shape), "native 3D grid required")
        voxels = math.prod(self.shape)
        need(256 <= voxels <= limits.max_voxels, "native-grid voxel limit")
        need(len(self.body) == 8 * voxels, "canonical byte extent mismatch")
        need(digest(self.sha256) and hashlib.sha256(self.body).hexdigest() == self.sha256,
             "canonical digest mismatch")
        need(type(self.affine) is tuple and len(self.affine) == 4 and
             all(type(row) is tuple and len(row) == 4 and
                 all(number(x) for x in row) for row in self.affine), "finite 4x4 affine required")
        need(self.affine[3] == (0, 0, 0, 1), "homogeneous affine bottom row")
        a, b, c = (self.affine[i][:3] for i in range(3))
        determinant = (a[0] * (b[1] * c[2] - b[2] * c[1]) -
                       a[1] * (b[0] * c[2] - b[2] * c[0]) +
                       a[2] * (b[0] * c[1] - b[1] * c[0]))
        need(math.isfinite(determinant) and determinant != 0, "nonsingular affine required")
        need(self.units in ("unknown", "meter", "mm", "micron"), "unrecognized spatial unit")
        need(all(math.isfinite(v[0]) for v in struct.iter_unpack("<d", self.body)),
             "canonical values must be finite")
        # Every native slice must fit. Do not silently crop a large plane.
        need(max(self.shape[0] * self.shape[1], self.shape[0] * self.shape[2],
                 self.shape[1] * self.shape[2]) <= limits.max_plane_pixels,
             "complete native planes exceed pixel limit")


def _rgb(value, low, high):
    # Convex-combination normalization avoids overflow of high-low for extreme
    # but finite float64 endpoints. Scaling by max absolute magnitude preserves
    # the declared window without producing an infinite denominator.
    if value <= low:
        t = 0.0
    elif value >= high:
        t = 1.0
    else:
        scale = max(abs(low), abs(high), abs(value))
        t = (value / scale - low / scale) / (high / scale - low / scale)
        t = min(1.0, max(0.0, t))
    # Blue -> white -> red. This is deliberately quantized display information.
    if t <= 0.5:
        part = round(510 * t)
        return bytes((part, part, 255))
    part = round(510 * (1 - t))
    return bytes((255, part, part))


def _chunk(kind, body):
    return (struct.pack(">I", len(body)) + kind + body +
            struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))


def _png(width, height, rows):
    # No source filename, label, text, EXIF, clock or ancillary chunk is emitted.
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) +
            _chunk(b"IDAT", zlib.compress(rows, 6)) + _chunk(b"IEND", b""))


def render_slice(volume, *, axis, index, low, high, limits, check_deadline):
    """Render a whole native-index plane; no resampling or anatomical relabeling.

    The caller must already have called CanonicalMap.validate with these limits.
    Indices increase right and up in the two displayed axes. A native-index
    plane need not be an anatomical axial/coronal/sagittal plane under an oblique
    affine. The literal affine is displayed so this distinction remains visible.
    """
    need(type(volume) is CanonicalMap and type(limits) is Limits, "typed map and limits required")
    need(type(axis) is int and axis in (0, 1, 2), "axis must be integer 0, 1 or 2")
    need(type(index) is int and 0 <= index < volume.shape[axis], "slice index outside native grid")
    need(number(low) and number(high) and low < high, "finite increasing display window required")
    check_deadline()
    horizontal, vertical = (a for a in range(3) if a != axis)
    width, height = volume.shape[horizontal], volume.shape[vertical]
    need(width * height <= limits.max_plane_pixels, "complete plane exceeds pixel limit")
    # zlib output is bounded by the uncompressed bytes plus zlib overhead. This
    # conservative preflight prevents constructing a response we cannot return.
    raw_extent = height * (1 + 3 * width)
    png_upper = raw_extent + raw_extent // 1000 + 256
    svg_upper = 8192 + 4 * ((png_upper + 2) // 3)
    need(svg_upper <= limits.max_svg_bytes, "complete frame exceeds SVG output limit")
    rows = bytearray()
    nx, ny, nz = volume.shape
    for image_y in range(height):
        check_deadline()
        rows.append(0)  # PNG filter NONE, followed by exactly one full row.
        coords = [0, 0, 0]
        coords[axis] = index
        coords[vertical] = height - 1 - image_y
        for x in range(width):
            coords[horizontal] = x
            flat = (coords[0] * ny + coords[1]) * nz + coords[2]
            value = struct.unpack_from("<d", volume.body, flat * 8)[0]
            rows.extend(_rgb(value, low, high))
    payload = base64.b64encode(_png(width, height, bytes(rows))).decode("ascii")
    affine_lines = " | ".join(",".join(format(float(v), ".17g") for v in row)
                              for row in volume.affine)
    # Only closed-schema numeric data and the validated unit enum enter text.
    window = format(float(low), ".17g") + " .. " + format(float(high), ".17g")
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="760" '
           f'viewBox="0 0 900 760"><rect width="900" height="760" fill="white"/>'
           f'<text x="20" y="24">Native axis {axis}, index {index}; '
           f'grid {nx} x {ny} x {nz}; spatial unit: {volume.units}</text>'
           f'<text x="20" y="48">Right: axis {horizontal} increasing; '
           f'up: axis {vertical} increasing. Native-index plane; no anatomical relabeling.</text>'
           f'<text x="20" y="72">Window {window}; blue=low, white=midpoint, red=high; clipped RGB8 display.</text>'
           f'<image x="20" y="90" width="640" height="560" '
           f'preserveAspectRatio="xMidYMid meet" style="image-rendering:pixelated" '
           f'href="data:image/png;base64,{payload}"/>'
           f'<text x="20" y="684">Pixel grid {width} x {height}; all voxel positions in this plane represented.</text>'
           f'<text x="20" y="708" font-size="9">Affine: {affine_lines}</text>'
           '</svg>')
    check_deadline()
    need(len(svg.encode("utf-8")) <= limits.max_svg_bytes, "SVG output cap")
    return svg


class ViewerSession:
    """Sequential complete-response collector owned by a trusted operator.

    case_ids are blinded context keys, never source record IDs. Their membership
    and order must come from a separately admitted context. This class validates
    their exact expected roster, but does not authenticate the full catalogue,
    person partition, cross-condition matching, calibration or 234-context study.
    """

    def __init__(self, *, case_ids, roster_sha256, class_labels, ontology_sha256,
                 loader, limits, clock=time.monotonic):
        need(type(case_ids) is tuple and 1 <= len(case_ids) <= 9532 and
             all(token(x) for x in case_ids) and len(set(case_ids)) == len(case_ids),
             "explicit unique blinded case roster required")
        need(digest(roster_sha256) and
             hashlib.sha256(json_body(list(case_ids)).encode()).hexdigest() == roster_sha256,
             "case roster digest mismatch")
        need(type(class_labels) is tuple and len(class_labels) == 25 and
             all(type(label) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _./()+-]{0,95}", label)
                 is not None for label in class_labels) and len(set(class_labels)) == 25,
             "explicit unique public 25-class label order required")
        need(digest(ontology_sha256) and
             hashlib.sha256(json_body(list(class_labels)).encode()).hexdigest() == ontology_sha256,
             "public ontology digest mismatch")
        need(callable(loader) and callable(clock), "operator loader and clock required")
        need(type(limits) is Limits, "explicit limits required")
        limits.validate()
        self._ids = case_ids
        self._roster_digest = roster_sha256
        self._labels = class_labels
        self._ontology_digest = ontology_sha256
        self._loader = loader
        self._limits = limits
        self._clock = clock
        start = clock()
        need(number(start), "finite operator clock required")
        self._deadline = start + limits.wall_seconds
        need(math.isfinite(self._deadline), "finite deadline required")
        self._cursor = 0
        self._actions = 0
        self._frames = [0] * len(case_ids)
        self._answers = []
        self._map = None
        self._closed = False

    def _check(self):
        value = self._clock()
        need(number(value) and value < self._deadline, "viewer deadline exceeded")
        need(not self._closed, "viewer session closed")

    def _current_map(self):
        if self._map is None:
            try:
                value = self._loader(self._ids[self._cursor])
            except Exception:
                # Transport code must not receive an author's filename, label
                # or private deployment path through an exception message.
                raise ViewerError("operator map unavailable") from None
            self._check()
            need(type(value) is CanonicalMap, "operator loader returned invalid map")
            value.validate(self._limits)
            self._check()
            self._map = value
        return self._map

    def dispatch(self, request):
        """Closed typed action -> JSON-safe response, never bytes/paths/objects."""
        self._check()
        need(self._actions < self._limits.max_actions, "viewer action budget exhausted")
        self._actions += 1  # Malformed or refused actions are still charged.
        need(type(request) is dict and type(request.get("action")) is str,
             "typed request object required")
        action = request["action"]
        if action == "status":
            need(set(request) == {"action"}, "unexpected status fields")
            if self._cursor == len(self._ids):
                return {"state": "all_responses_collected", "responses": len(self._answers)}
            # The participant must be able to abstain even when loading or
            # validating this map fails. This route exposes no map or target.
            return {"state": "awaiting_response", "case_id": self._ids[self._cursor],
                    "ordinal": self._cursor, "total": len(self._ids),
                    "frames_remaining": self._limits.max_frames_per_case - self._frames[self._cursor],
                    "answer_classes": 25, "class_labels": list(self._labels),
                    "ontology_sha256": self._ontology_digest}
        if action == "describe":
            need(set(request) == {"action"}, "unexpected describe fields")
            if self._cursor == len(self._ids):
                return {"state": "all_responses_collected", "responses": len(self._answers)}
            volume = self._current_map()
            return {"state": "awaiting_response", "case_id": self._ids[self._cursor],
                    "ordinal": self._cursor, "total": len(self._ids),
                    "shape": list(volume.shape), "spatial_units": volume.units,
                    "frames_remaining": self._limits.max_frames_per_case - self._frames[self._cursor],
                    "answer_classes": 25, "class_labels": list(self._labels),
                    "ontology_sha256": self._ontology_digest}
        need(self._cursor < len(self._ids), "no unanswered cases")
        need(request.get("case_id") == self._ids[self._cursor], "current blinded case key required")
        if action == "slice":
            need(set(request) == {"action", "case_id", "axis", "index", "low", "high"},
                 "unexpected slice fields")
            need(self._frames[self._cursor] < self._limits.max_frames_per_case,
                 "case frame budget exhausted")
            self._frames[self._cursor] += 1  # A failed render also consumes a frame.
            volume = self._current_map()
            svg = render_slice(volume, axis=request["axis"], index=request["index"],
                               low=request["low"], high=request["high"],
                               limits=self._limits, check_deadline=self._check)
            return {"case_id": self._ids[self._cursor], "media_type": "image/svg+xml",
                    "svg": svg, "frame": self._frames[self._cursor]}
        if action == "answer":
            need(set(request) == {"action", "case_id", "probabilities"}, "unexpected answer fields")
            values = request["probabilities"]
            need(values is None or (type(values) is list and len(values) == 25 and
                 all(number(v) and 0 <= v <= 1 for v in values) and
                 abs(math.fsum(values) - 1.0) <= 1e-8),
                 "answer must be null abstention or 25 normalized finite probabilities")
            self._answers.append(None if values is None else tuple(float(v) for v in values))
            accepted = self._ids[self._cursor]
            self._cursor += 1
            self._map = None
            return {"accepted_case_id": accepted, "responses": self._cursor,
                    "state": "all_responses_collected" if self._cursor == len(self._ids)
                    else "awaiting_response"}
        raise ViewerError("unsupported viewer action")

    def finish(self):
        """Trusted operator call; complete collection is not scientific grading."""
        self._check()
        need(self._cursor == len(self._ids), "complete expected roster required")
        self._closed = True
        records = [{"case_id": key, "probabilities": None if value is None else list(value)}
                   for key, value in zip(self._ids, self._answers)]
        response_digest = hashlib.sha256(json_body(records).encode()).hexdigest()
        return {"schema": "n073-typed-map-response-collection/v1", "task_id": "NEURAL-073",
                "expected_case_roster_sha256": self._roster_digest,
                "public_ontology_sha256": self._ontology_digest,
                "response_sha256": response_digest, "records": records,
                "actions": self._actions, "frames_by_case": list(self._frames),
                "scope": "explicit_operator_context_only", "scientific_qualification": False,
                "isolated_transport_qualified": False, "full_catalogue_qualified": False}
