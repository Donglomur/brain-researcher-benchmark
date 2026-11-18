"""PNG delivery around the exact accepted NEURAL-084 Panel.

Trusted operator API, not a process, network or model-context sandbox. The
participant receives allowlisted metadata and PNG bytes, never SVG geometry.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import struct
from types import ModuleType
import xml.etree.ElementTree as ET


PANEL_PIN = (8802, "10b8182174dcc338ab683ff6f367164030b0bdb6d8909406e32a3a91a7adbb63")
CANVAS_PIN = (17096, "4645cb193d1307a0a8ce7bb7c0135cc0101f65c055063608d0b304e898a569b6")
CHANNELS = ("P7", "P3", "Pz", "P4", "P8", "PO9", "PO10", "O1", "Oz", "O2")
WIDTH, LANE, LEFT, RIGHT = 1000, 86, 112, 980
MAX_PNG_BYTES, MAX_METADATA_BYTES = 4194304, 16384
NS = "{http://www.w3.org/2000/svg}"


def need(value, message):
    if not value:
        raise ValueError(message)


def _load(path, pin, name):
    path = Path(path)
    with path.open("rb") as stream:
        body = stream.read(pin[0] + 1)
    need(len(body) == pin[0] and hashlib.sha256(body).hexdigest() == pin[1],
         "exact reviewed dependency required")
    module = ModuleType(name)
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def _canvas(path):
    module = _load(path, CANVAS_PIN, "neural084_private_canvas")
    # A separate captured module per owner: never mutate another task's module.
    # Reuse only its pixel, line, text and PNG primitives, not its task renderer.
    module.WIDTH = WIDTH
    module._FONT_ROWS.update({
        "[": "01110/01000/01000/01000/01000/01000/01110",
        "]": "01110/00010/00010/00010/00010/00010/01110",
        "|": "00100/00100/00100/00100/00100/00100/00100",
        ",": "00000/00000/00000/00000/00110/00100/01000",
    })
    return module


def _json(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def _node(node, tag, attributes):
    need(node.tag == NS + tag and node.attrib == attributes, "fixed N084 SVG grammar")
    need(not (node.tail or "").strip(), "no extra SVG text")


def _text(canvas, module, node, x, baseline, text=None):
    need(len(node) == 0 and type(node.text) is str, "plain bitmap label")
    if text is not None:
        need(node.text == text, "original waveform label")
    label = node.text.upper()  # Explicit bitmap casing; never silent '?' fallback.
    need(len(label) <= 96 and all(c in module._FONT_ROWS for c in label),
         "supported complete label glyphs")
    need(0 <= x and x + 12 * len(label) <= WIDTH and baseline >= 14,
         "complete unclipped bitmap label")
    canvas.text(x, baseline - 14, label, color=(17, 17, 17), scale=2)


def rasterize(response, module):
    """Rasterize only the exact accepted viewer's finite waveform grammar.

    Every serialized source point is visited, rounded to its nearest pixel and
    connected by the reviewed integer-line primitive. No numerical EEG transform
    occurs here. Pixel quantization and bitmap fonts differ from SVG rendering.
    """
    training = response.get("stage") == "training"
    need(type(response) is dict and set(response) ==
         {"stage", "row" if training else "id", "kind", "svg", "channels", "start", "stop"},
         "exact waveform response fields")
    need(response["stage"] in ("training", "query") and response["kind"] == "svg_waveform",
         "original waveform response")
    channels, start, stop = response["channels"], response["start"], response["stop"]
    need(type(channels) is list and 1 <= len(channels) <= 10 and
         all(type(c) is str and c in CHANNELS for c in channels), "original selected channels")
    indices = [CHANNELS.index(c) for c in channels]
    need(indices == sorted(set(indices)), "original unique channel order")
    need(type(start) is int and type(stop) is int and 0 <= start < stop <= 400
         and stop - start >= 2, "original half-open source window")
    svg = response["svg"]
    need(type(svg) is str and 0 < len(svg.encode("utf-8")) <= 262144
         and "<!" not in svg and "<?" not in svg, "bounded fixed SVG without declarations")
    root = ET.fromstring(svg)
    height = 78 + LANE * len(channels)
    _node(root, "svg", {"width": "1000", "height": str(height), "viewBox": f"0 0 1000 {height}"})
    need(not (root.text or "").strip() and len(root) == 2 + 3 * len(channels),
         "complete fixed SVG children")
    _node(root[0], "rect", {"width": "100%", "height": "100%", "fill": "white"})
    need(len(root[0]) == 0 and root[0].text is None, "plain background")
    _node(root[1], "g", {"fill": "#111", "font-family": "sans-serif", "font-size": "13"})
    need(len(root[1]) == 3 and not (root[1].text or "").strip(), "three fixed header labels")
    canvas = module._Canvas(height)
    for node, x, y in zip(root[1], (12, 12, LEFT), (18, 38, 58)):
        _node(node, "text", {"x": str(x), "y": str(y)})
        _text(canvas, module, node, x, y)
    need(root[1][0].text == "NEURAL-084 | source amplitudes; physical unit unverified",
         "source units remain explicit")
    scale_text = root[1][1].text
    prefix, suffix = "Common full-epoch scale: +/- ", "; no filtering or re-centering"
    need(scale_text.startswith(prefix) and scale_text.endswith(suffix), "original scale annotation")
    bound = float(scale_text[len(prefix):-len(suffix)])
    need(math.isfinite(bound) and 0 < bound <= 3.40282346640e38, "finite display scale")
    first, last = 0.0045 + .01 * start, 0.0045 + .01 * (stop - 1)
    need(root[1][2].text == f"Sample centers {first:.4f} to {last:.4f} s; indices [{start},{stop})",
         "unchanged sample-center annotation")
    for slot, name in enumerate(channels):
        line, label, trace = root[2 + 3 * slot:5 + 3 * slot]
        center = 119.0 + LANE * slot
        _node(line, "line", {"x1": "112", "y1": str(center), "x2": "980",
                             "y2": str(center), "stroke": "#bbb"})
        need(len(line) == 0 and line.text is None, "plain zero line")
        canvas.line(LEFT, int(center), RIGHT, int(center), (187, 187, 187))
        _node(label, "text", {"x": "12", "y": str(center + 4),
                              "font-family": "sans-serif", "font-size": "14"})
        _text(canvas, module, label, 12, int(center + 4), name)
        need(trace.tag == NS + "polyline" and len(trace) == 0 and trace.text is None
             and not (trace.tail or "").strip() and set(trace.attrib) ==
             {"data-channel", "fill", "stroke", "stroke-width", "points"}, "plain bounded polyline")
        need({k: trace.attrib[k] for k in ("data-channel", "fill", "stroke", "stroke-width")} ==
             {"data-channel": name, "fill": "none", "stroke": "#123b73", "stroke-width": "1"},
             "original trace identity/style")
        points = trace.attrib["points"].split(" ")
        need(len(points) == stop - start, "every selected source sample preserved")
        previous = None
        for offset, point in enumerate(points):
            parts = point.split(",")
            need(len(parts) == 2, "one finite coordinate pair per sample")
            x, y = map(float, parts)
            expected_x = float(format(LEFT + (RIGHT - LEFT) * offset / (stop - start - 1), ".12g"))
            need(math.isfinite(x) and math.isfinite(y) and x == expected_x
                 and center - 34 <= y <= center + 34, "bounded original sample coordinates")
            pixel = (round(x), round(y))
            if previous is not None:
                canvas.line(*previous, *pixel, (18, 59, 115))
            canvas.pixel(*pixel, (18, 59, 115))
            previous = pixel
    png = canvas.png()
    need(type(png) is bytes and len(png) <= MAX_PNG_BYTES and png[:8] == b"\x89PNG\r\n\x1a\n"
         and png[8:16] == b"\0\0\0\rIHDR" and struct.unpack(">II", png[16:24]) == (WIDTH, height),
         "bounded exact raster dimensions")
    return png, WIDTH, height


class RasterPanel:
    """Keep the accepted collection behind one fixed trusted delivery callback.

    Callback(metadata_bytes, png_bytes_or_None) must return exactly True after
    accepting the delivery. This acknowledges the operator transport call, not
    external model perception or OS isolation. Never give this object to a peer.
    """
    def __init__(self, folds, transport, *, max_requests, max_capture_bytes,
                 max_delivery_bytes, panel_source=None, canvas_source=None,
                 viewer_source=None, source_root=None):
        need(callable(transport), "fixed trusted delivery callback")
        need(type(max_delivery_bytes) is int and 1 <= max_delivery_bytes <= 2**53 - 1,
             "explicit bounded whole-panel delivery allowance")
        here = Path(__file__).resolve()
        panel_source = panel_source or here.parents[1] / "full-panel-viewer-bridge-v1/panel.py"
        canvas_source = canvas_source or here.parents[3] / "NEURAL-EXP-005/implementations/typed-raster-viewer-v1/viewer.py"
        panel = _load(panel_source, PANEL_PIN, "neural084_raster_bound_panel")
        self._canvas = _canvas(canvas_source)
        self._panel = panel.Panel(folds, max_requests=max_requests,
            max_capture_bytes=max_capture_bytes, viewer_source=viewer_source, source_root=source_root)
        self._io = self._panel._io
        self._transport = transport
        self._limit, self._attempted, self._acknowledged, self._frames = max_delivery_bytes, 0, 0, 0
        self._failed, self._busy, self._complete = False, False, None
        self._transcript = hashlib.sha256()

    def _ready(self):
        if self._busy:
            self._failed = True
            raise ValueError("reentrant delivery is terminal")
        need(not self._failed and self._complete is None, "closed or failed delivery owner")

    def open_next(self, training_raw, training_epoch, query_epoch):
        self._ready()
        return self._panel.open_next(training_raw, training_epoch, query_epoch)

    def dispatch(self, raw):
        self._ready()
        # Original Panel performs request limits, strict decoding and all state
        # transitions. Its ordinary rejected actions retain original semantics.
        response_raw = self._panel.handle(raw)
        self._busy = True
        try:
            request, response = self._io.decode(raw), self._io.decode(response_raw)
            action = request["action"]
            image = None
            if action in ("training", "view"):
                image, width, height = rasterize(response, self._canvas)
                body = {k: v for k, v in response.items() if k not in ("svg", "kind")}
                body["kind"] = "png_waveform"
                picture = {"mime_type": "image/png", "bytes": len(image),
                           "sha256": hashlib.sha256(image).hexdigest(), "width": width, "height": height}
            else:
                fields = {
                    "information": {"schema", "stage", "generation", "fold", "training_rows", "query_rows",
                        "channels", "sample_count", "sample_rate_hz", "first_sample_center_seconds", "classes",
                        "directions", "frequencies_hz", "max_views_per_epoch", "physical_amplitude_unit", "raw_arrays_delivered"},
                    "begin_queries": {"stage", "id", "query_rows"},
                    "answer": {"accepted", "answered"} | ({"next_id"} if response.get("answered", 400) < 400 else set()),
                    "finish": {"schema", "fold", "closed_folds", "required_folds"},
                }
                need(action in fields and type(response) is dict and set(response) == fields[action],
                     "allowlisted original metadata response")
                body, picture = response, None
            envelope = {"schema": "neural084-raster-delivery-v1", "sequence": self._acknowledged + 1,
                        "action": action, "body": body, "image": picture}
            metadata = _json(envelope)
            need(len(metadata) <= MAX_METADATA_BYTES, "bounded delivery metadata")
            charge = len(metadata) + (len(image) if image is not None else 0)
            need(self._attempted + charge <= self._limit, "whole-panel delivery byte allowance")
            self._attempted += charge  # Failed callback attempts remain charged.
            need(self._transport(metadata, image) is True and not self._failed,
                 "delivery acknowledgement required")
            self._transcript.update(struct.pack(">Q", len(metadata)) + metadata)
            self._transcript.update(struct.pack(">Q", len(image) if image is not None else 0))
            if image is not None:
                self._transcript.update(image)
                self._frames += 1
            self._acknowledged += 1
            return {"acknowledged": True, "sequence": self._acknowledged, "png_delivered": image is not None}
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    def finish_collection(self):
        self._ready()
        original = self._panel.finish_collection()  # Still requires all54 folds.
        try:
            self._complete = _json({"schema": "neural084-raster-collection-v1", "status": "complete_unqualified",
                "original_collection": self._io.pin(original), "acknowledged_messages": self._acknowledged,
                "png_frames": self._frames, "attempted_delivery_bytes": self._attempted,
                "transcript_sha256": self._transcript.hexdigest(), "representation": "PNG_bitmap_waveform",
                "external_participant_context_isolation_qualified": False,
                "authentic_inputs_qualified": False, "native_programme_execution_receipt": False,
                "comparators_generated": False, "private_scoring_performed": False, "scientific_qualified": False})
            return self._complete
        except BaseException:
            self._failed = True
            raise

    def candidate_prediction(self, fold):
        need(not self._failed and self._complete is not None, "complete acknowledged54-fold raster collection required")
        return self._panel.candidate_prediction(fold)
