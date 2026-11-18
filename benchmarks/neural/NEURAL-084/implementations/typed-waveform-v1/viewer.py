"""Operator-owned NEURAL-084 waveform presentation and first-final collection.

This module does not establish a participant sandbox, source authenticity,
image-only transport, or native neural understanding. See README.md.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import html
import json
import math
from pathlib import Path
import re
from types import ModuleType, SimpleNamespace


SOURCE_PINS = {
    "delivery-source/public/protocol.py": (732, "20d59ca8be134175b5b9c2da81c261231a63b38da12ea1a5b3c8b64e855fa926"),
    "delivery-source/public/io_utils.py": (4396, "9ba54409ff3aae8e17d2c0e96f1c5f335fa46cd33aeaf83d3be427a8ebf585d7"),
    "sequential-programme/sequential-view-v2/program/contracts.py": (19124, "fe7d5047bea2d7ab1ba5bdb87afc70e1701489eefcae18d9d18e82da10466ad8"),
}
MAX_REQUEST_BYTES = 4096
MAX_VIEWS_PER_EPOCH = 128
MAX_RESPONSE_BYTES = 262144
FLOAT32_MAX = 3.4028234663852886e38


def need(condition, message):
    if not condition:
        raise ValueError(message)


def _dependencies(root):
    """Only exact already-published source is executable, never participant code."""
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    modules = []
    for relative, (extent, digest) in SOURCE_PINS.items():
        source = root / relative
        with source.open("rb") as stream:
            raw = stream.read(extent + 1)
        need(len(raw) == extent and hashlib.sha256(raw).hexdigest() == digest,
             "reviewed NEURAL-084 dependency changed")
        module = ModuleType("neural084_viewer_" + str(len(modules)))
        module.__file__ = str(source)
        exec(compile(raw, str(source), "exec"), module.__dict__)
        modules.append(module)
    protocol, io, contracts = modules

    def exact_pin(value):
        io.check_pin(value, 2**63 - 1)
        return dict(value)

    contracts.c = SimpleNamespace(need=need, exact_pin=exact_pin,
                                  only_pin=lambda value: {key: value[key] for key in ("bytes", "sha256")})
    return protocol, io, contracts


def _epoch(value):
    need(type(value) in (list, tuple) and len(value) == 10, "exact ten-channel epoch")
    result = []
    for channel in value:
        need(type(channel) in (list, tuple) and len(channel) == 400,
             "exact 400 samples per channel")
        row = []
        for sample in channel:
            need(type(sample) in (int, float) and abs(sample) <= FLOAT32_MAX
                 and math.isfinite(sample), "finite nonboolean float32-range source amplitude")
            row.append(float(sample))
        result.append(tuple(row))
    return tuple(result)


def _epoch_pin(epoch):
    raw = json.dumps(epoch, separators=(",", ":"), allow_nan=False).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _window(request, channel_names):
    channels, start, stop = request["channels"], request["start"], request["stop"]
    need(type(channels) is list and 1 <= len(channels) <= 10
         and all(type(name) is str and name in channel_names for name in channels),
         "one to ten named source channels")
    indices = [channel_names.index(name) for name in channels]
    need(indices == sorted(set(indices)), "unique channels in original channel order")
    need(type(start) is int and type(stop) is int and 0 <= start < stop <= 400
         and stop - start >= 2, "half-open window with two to 400 exact source samples")
    return indices, start, stop


def _svg(epoch, channels, start, stop, channel_names):
    """No filtering, centering, interpolation or decimation of source samples.

    Polyline edges connect adjacent sample centers. The single common bound
    uses the WHOLE epoch and is unchanged by channel selection or time zoom.
    Coordinate serialization is a finite-precision visual representation.
    """
    bound = max(abs(value) for row in epoch for value in row)
    display_bound = bound if bound else 1.0
    width, lane, left, right = 1000, 86, 112, 980
    height = 78 + lane * len(channels)
    first_time, last_time = 0.0045 + 0.01 * start, 0.0045 + 0.01 * (stop - 1)
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             '<g fill="#111" font-family="sans-serif" font-size="13">',
             '<text x="12" y="18">NEURAL-084 | source amplitudes; physical unit unverified</text>',
             f'<text x="12" y="38">Common full-epoch scale: +/- {display_bound:.12g}; no filtering or re-centering</text>',
             f'<text x="{left}" y="58">Sample centers {first_time:.4f} to {last_time:.4f} s; indices [{start},{stop})</text>',
             '</g>']
    for ordinal, channel in enumerate(channels):
        center = 76 + lane * ordinal + lane / 2
        lines.append(f'<line x1="{left}" y1="{center}" x2="{right}" y2="{center}" stroke="#bbb"/>')
        lines.append(f'<text x="12" y="{center + 4}" font-family="sans-serif" font-size="14">{html.escape(channel_names[channel])}</text>')
        points = []
        for sample in range(start, stop):
            x = left + (right - left) * (sample - start) / (stop - start - 1)
            # Division first avoids overflow even at the maximum allowed source amplitude.
            y = center - 34 * (epoch[channel][sample] / display_bound)
            points.append(f"{x:.12g},{y:.12g}")
        lines.append(f'<polyline data-channel="{channel_names[channel]}" fill="none" stroke="#123b73" stroke-width="1" points="{" ".join(points)}"/>')
    lines.append('</svg>')
    return "\n".join(lines)


class FoldViewer:
    """Trusted operator API for ONE complete fold, with no private-gold argument.

    Providers are trusted operator callables returning one 10x400 epoch in
    already-authenticated packet row order. Never give this object, providers,
    source arrays or Python access to an image-only participant. Only handle()
    responses may cross an independently qualified participant transport.
    """

    def __init__(self, fold, training, training_epoch, query_epoch, *, source_root=None):
        protocol, io, contracts = _dependencies(source_root)
        need(callable(training_epoch) and callable(query_epoch), "trusted epoch providers")
        # Deep copies prevent a caller mutating metadata after validation.
        self._fold = io.decode(io.canonical(fold))
        copied_training = io.decode(io.canonical(training))
        name = self._fold.get("fold")
        need(type(name) is str and re.fullmatch(r"fold0[0-5][0-9]", name), "canonical held-person fold")
        held = int(name[4:])
        need(held in protocol.PEOPLE, "held person 1..54")
        contracts._fold_contract(self._fold, held, self._fold.get("generation"))
        contracts.training_contract(copied_training, held, self._fold["ids"])
        self._protocol, self._io, self._contracts = protocol, io, contracts
        self._training = copied_training["rows"]
        self._training_epoch, self._query_epoch = training_epoch, query_epoch
        self._stage = "training"
        self._training_views = Counter()
        self._training_anchors = {}
        self._query_views = 0
        self._query_index = 0
        self._current_epoch = None
        self._answers = []
        self._final = None

    def _view(self, request, training):
        fields = ("action", "index", "channels", "start", "stop") if training else ("action", "id", "channels", "start", "stop")
        self._io.exact(request, fields)
        channels, start, stop = _window(request, self._protocol.CHANNELS)
        if training:
            need(self._stage == "training", "training retired before query access")
            index = request["index"]
            need(type(index) is int and 0 <= index < 21200, "all 21200 donor rows addressable")
            need(self._training_views[index] < MAX_VIEWS_PER_EPOCH, "training view budget exhausted")
            epoch = _epoch(self._training_epoch(index))
            digest = _epoch_pin(epoch)
            need(self._training_anchors.get(index, digest) == digest, "training provider changed an observed epoch")
            self._training_anchors[index] = digest
            self._training_views[index] += 1
            # These metadata are already public to the original programme.
            result = {"stage": "training", "row": dict(self._training[index])}
        else:
            need(self._stage == "query" and self._query_index < 400, "current unanswered query only")
            need(request["id"] == self._fold["ids"][self._query_index], "exact current opaque query identity")
            need(self._query_views < MAX_VIEWS_PER_EPOCH, "query view budget exhausted")
            if self._current_epoch is None:
                self._current_epoch = _epoch(self._query_epoch(self._query_index))
            epoch = self._current_epoch
            self._query_views += 1
            result = {"stage": "query", "id": request["id"]}
        result.update(kind="svg_waveform", svg=_svg(epoch, channels, start, stop, self._protocol.CHANNELS),
                      channels=[self._protocol.CHANNELS[i] for i in channels], start=start, stop=stop)
        return result

    def _answer(self, request):
        self._io.exact(request, ("action", "id", "scores"))
        need(self._stage == "query" and self._query_index < 400, "unanswered query required")
        identity = self._fold["ids"][self._query_index]
        need(type(request["id"]) is str and request["id"] == identity, "exact first-final query identity")
        scores = request["scores"]
        need(type(scores) is list and len(scores) == 4
             and all(type(score) in (int, float) and math.isfinite(score) for score in scores),
             "four finite nonboolean raw scores, not assumed probabilities")
        self._answers.append({"id": identity, "scores": list(scores)})
        self._query_index += 1
        self._query_views = 0
        self._current_epoch = None
        result = {"accepted": True, "answered": self._query_index}
        if self._query_index < 400:
            result["next_id"] = self._fold["ids"][self._query_index]
        return result

    def handle(self, raw):
        """One strict bounded JSON action; one canonical JSON response, no code."""
        need(type(raw) is bytes and 0 < len(raw) <= MAX_REQUEST_BYTES, "bounded UTF8 request bytes")
        need(self._stage != "closed", "closed fold cannot be reused")
        request = self._io.decode(raw)
        need(type(request) is dict and type(request.get("action")) is str, "typed action object")
        action = request["action"]
        if action == "information":
            self._io.exact(request, ("action",))
            result = {"schema": "neural084-waveform-view-v1", "stage": self._stage,
                      "generation": self._fold["generation"], "fold": self._fold["fold"],
                      "training_rows": 21200, "query_rows": 400,
                      "channels": list(self._protocol.CHANNELS), "sample_count": 400,
                      "sample_rate_hz": 100, "first_sample_center_seconds": 0.0045,
                      "classes": list(self._protocol.CLASSES), "directions": list(self._protocol.DIRECTIONS),
                      "frequencies_hz": list(self._protocol.FREQUENCIES),
                      "max_views_per_epoch": MAX_VIEWS_PER_EPOCH,
                      "physical_amplitude_unit": "unverified", "raw_arrays_delivered": False}
        elif action == "training":
            result = self._view(request, True)
        elif action == "begin_queries":
            self._io.exact(request, ("action",))
            need(self._stage == "training", "one training-to-query transition")
            self._training = None
            self._training_epoch = None
            self._training_anchors.clear()
            self._training_views.clear()
            self._stage = "query"
            result = {"stage": "query", "id": self._fold["ids"][0], "query_rows": 400}
        elif action == "view":
            result = self._view(request, False)
        elif action == "answer":
            result = self._answer(request)
        elif action == "finish":
            self._io.exact(request, ("action",))
            need(self._stage == "query" and self._query_index == 400, "all 400 first-final responses required")
            result = {"schema": "neural084_scores_v1", "generation": self._fold["generation"],
                      "fold": self._fold["fold"], "predictions": self._answers}
            final = self._io.canonical(result)
            self._contracts.prediction(final, self._fold)
            self._stage = "closed"
            self._query_epoch = None
            self._final = final
            return final
        else:
            raise ValueError("unsupported typed action")
        response = self._io.canonical(result)
        need(len(response) <= MAX_RESPONSE_BYTES, "bounded waveform response")
        return response
