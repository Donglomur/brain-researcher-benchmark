"""NEURAL-019 trusted-operator PNG framing; no participant execution/isolation."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import math
from pathlib import Path
import re
import time
import types
import xml.etree.ElementTree as ET

VIEWER_SHA256 = "25da9e4d159d17cdaa8c912312a86b17d41eef4774c408d642c59de99e7e9f37"
PROFILE_ID = "n019-dejavu-sans-mono-12-rgb-v1"
FONT_SHA256 = "602ec86b8948cfcd956482fe64f94c36c867770149ef2f791d4613f443bcecb3"
FONT_BYTES = 340240
PILLOW_VERSION = "12.3.0"
MAX_REQUEST = 32768
MAX_PNG = 262144
MAX_FRAME = 393216
NS = "{http://www.w3.org/2000/svg}"


def need(value, message):
    if not value:
        raise ValueError(message)


def pin(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def decode(raw):
    need(type(raw) is bytes and 0 < len(raw) <= MAX_REQUEST, "Bounded UTF-8 frame required")
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "Duplicate key")
            result[key] = value
        return result
    result = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                        parse_constant=lambda _: need(False, "Nonfinite JSON"))
    need(type(result) is dict, "Object frame required")
    return result


def load_viewer(path):
    """Hash exact source bytes before compiling those same bytes; no bytecode writes."""
    raw = Path(path).read_bytes()
    need(len(raw) == 16459 and pin(raw) == VIEWER_SHA256, "Frozen viewer source required")
    module = types.ModuleType("neural019_frozen_viewer")
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


class Renderer:
    """Rasterize only the frozen viewer's subset. Mechanical checks, not perception."""
    def __init__(self, font_bytes):
        need(type(font_bytes) is bytes and len(font_bytes) == FONT_BYTES and
             pin(font_bytes) == FONT_SHA256, "Pinned DejaVu Sans Mono font bytes required")
        # Dependency loading is deferred; frame-only transport uses the standard library.
        import PIL
        from PIL import Image, ImageDraw, ImageFont, features
        need(PIL.__version__ == PILLOW_VERSION, "Declared Pillow version required")
        self._Image, self._ImageDraw = Image, ImageDraw
        self._font = ImageFont.truetype(io.BytesIO(font_bytes), size=12,
                                       layout_engine=ImageFont.Layout.BASIC)
        # Only the verified loader injects this binding into its private module.
        # Direct trusted-library calls remain explicitly unselected.
        binding = globals().get("_SELECTED_PACKAGE_BINDING")
        self.profile = {"profile_id": PROFILE_ID, "selected_package": binding is not None,
                        "package_binding": dict(binding) if binding is not None else None,
                        "font_sha256": FONT_SHA256, "font_bytes": FONT_BYTES,
                        "font_size_px": 12, "layout": "BASIC", "pillow": PIL.__version__,
                        "freetype": features.version("freetype2"),
                        "pixel_format": "RGB", "mechanical_bounds_only": True}
        self.profile["profile_identity_sha256"] = pin(encode(self.profile))
        unsupported = bytes(self._font.getmask("\U0010ffff"))
        masks = []
        for code in range(33, 127):
            mask = self._font.getmask(chr(code))
            need(mask.getbbox() is not None and bytes(mask) != unsupported, "Missing ASCII glyph")
            if 48 <= code <= 57:
                masks.append((mask.size, bytes(mask)))
        need(len(set(masks)) == 10, "Distinct decimal glyph masks required")

    def render(self, result):
        need(type(result) is dict and set(result) ==
             {"kind", "svg", "role", "trial", "unit_range", "bin_range", "rendering_transport_qualified"},
             "Exact viewer response required")
        role, trial = result["role"], result["trial"]
        need(result["kind"] == "svg" and result["rendering_transport_qualified"] is False,
             "Frozen unqualified SVG response required")
        need(role in ("calibration", "assessment") and type(trial) is int and
             0 <= trial < (1340 if role == "calibration" else 126), "Exact role and trial")
        for name, extent, span in (("unit_range", 137, 16), ("bin_range", 140, 20)):
            r = result[name]
            need(type(r) is list and len(r) == 2 and all(type(v) is int for v in r) and
                 0 <= r[0] < r[1] <= extent and r[1] - r[0] <= span, "Exact crop bounds")
        u0, u1 = result["unit_range"]
        b0, b1 = result["bin_range"]
        width = max(760, 100 + (b1 - b0) * 54)
        bottom = 112 + (u1 - u0) * 24
        height = bottom + (52 + (b1 - b0) * 19 if role == "calibration" else 32)
        svg = result["svg"]
        need(type(svg) is str and 0 < len(svg.encode("utf-8")) <= 131072,
             "Bounded SVG required")
        need("<!" not in svg and "<?" not in svg, "No declarations, entities or processing instructions")
        root = ET.fromstring(svg)
        need(root.tag == NS + "svg" and root.attrib ==
             {"width": str(width), "height": str(height), "viewBox": f"0 0 {width} {height}"},
             "Exact canvas")
        children = list(root)
        need(len(children) == 2 and children[0].tag == NS + "rect" and
             children[0].attrib == {"width": "100%", "height": "100%", "fill": "white"} and
             len(children[0]) == 0 and not (children[0].text or "").strip(), "Exact background")
        group = children[1]
        need(group.tag == NS + "g" and group.attrib ==
             {"font-family": "monospace", "font-size": "12", "fill": "black"}, "Exact text group")
        need(not (root.text or "").strip() and not (group.text or "").strip() and
             all(not (node.tail or "").strip() for node in root.iter()), "No unbound text")
        nodes = iter(group)
        image = self._Image.new("RGB", (width, height), "white")
        draw = self._ImageDraw.Draw(image)
        text_count = 0
        def next_node(tag, attrs):
            node = next(nodes, None)
            need(node is not None and node.tag == NS + tag and node.attrib == attrs and
                 len(node) == 0, "Exact ordered SVG primitive")
            return node
        def text(x, y, expected=None, extra=None, bounds=None):
            nonlocal text_count
            node = next_node("text", dict({"x": str(x), "y": str(y)}, **(extra or {})))
            value = node.text or ""
            need(0 < len(value) <= 256 and all(32 <= ord(c) < 127 for c in value),
                 "Printable ASCII profile only; no silent glyph substitution")
            if expected is not None:
                need(value == expected, "Exact frozen label")
            left, top, right, lower = draw.textbbox((x, y), value, font=self._font, anchor="ls")
            a, b, c, d = bounds or (0, 0, width, height)
            need(a <= left < right <= c and b <= top < lower <= d,
                 "Glyph extent clips canvas, row or neighboring cell")
            draw.text((x, y), value, font=self._font, fill="black", anchor="ls")
            text_count += 1
            return value
        text(10, 20, f"NEURAL-019 {role} trial {trial}; spikes per5ms; exact integer counts",
             bounds=(0, 0, width, 24))
        text(10, 40, "Neural clock shown; target velocity clock = neural clock +100ms. Retrospective.",
             bounds=(0, 24, width, 44))
        label = text(10, 60, bounds=(0, 44, width, 64))
        if role == "calibration":
            need(re.fullmatch(r"Training group .{1,64}; training fold [0-3]; measured calibration below", label)
                 is not None, "Bounded calibration group label")
        else:
            need(label == "Assessment velocity is unavailable. Response requires all140 x/y pairs in m/s.",
                 "Exact assessment boundary")
        for b in range(b0, b1):
            x = 94 + (b - b0) * 54
            text(x, 86, str(-250 + 5 * b), bounds=(x - 4, 64, x + 50, 92))
        for u in range(u0, u1):
            y = 112 + (u - u0) * 24
            text(10, y, f"unit {u}", bounds=(0, y - 16, 89, y + 7))
            for b in range(b0, b1):
                x = 90 + (b - b0) * 54
                rect = next(nodes, None)
                attrs = {"x": str(x), "y": str(y - 16), "width": "53", "height": "23",
                         "stroke": "#cccccc"}
                need(rect is not None and rect.tag == NS + "rect" and len(rect) == 0 and
                     not (rect.text or "").strip() and rect.attrib.get("fill") in ("#e6eef8", "#ffffff") and
                     rect.attrib == dict(attrs, fill=rect.attrib.get("fill")), "Exact cell rectangle")
                draw.rectangle((x, y - 16, x + 52, y + 6), fill=rect.attrib["fill"], outline="#cccccc")
                value = text(x + 3, y, extra={"data-bin": str(b), "data-unit": str(u)},
                             bounds=(x + 1, y - 15, x + 52, y + 6))
                need(re.fullmatch(r"0|[1-9][0-9]{0,4}", value) is not None and int(value) <= 65535,
                     "Exact unsigned integer count")
                need(rect.attrib["fill"] == ("#e6eef8" if int(value) else "#ffffff"), "Count color parity")
        if role == "calibration":
            text(10, bottom + 20, "Velocity clock(ms) | measured x(m/s) | measured y(m/s)",
                 bounds=(0, bottom, width, bottom + 24))
            for i, b in enumerate(range(b0, b1)):
                y = bottom + 40 + i * 19
                value = text(10, y, extra={"data-calibration-bin": str(b)},
                             bounds=(0, y - 15, width, y + 4))
                parts = value.split(" | ")
                need(len(parts) == 3 and parts[0] == str(-150 + 5 * b), "Exact separate velocity clock")
                for v in parts[1:]:
                    number = float(v)
                    need(math.isfinite(number) and repr(number) == v, "Exact finite calibration representation")
        need(next(nodes, None) is None, "No extra SVG primitives")
        output = io.BytesIO()
        image.save(output, format="PNG", optimize=False, compress_level=9)
        png = output.getvalue()
        need(0 < len(png) <= MAX_PNG and png.startswith(b"\x89PNG\r\n\x1a\n"), "Bounded actual PNG")
        stimulus = {"profile_identity_sha256": self.profile["profile_identity_sha256"],
                    "svg_sha256": pin(svg.encode()), "png_sha256": pin(png)}
        return png, {"stimulus_identity_sha256": pin(encode(stimulus)), **stimulus,
                     "width": width, "height": height, "text_count": text_count,
                     "count_cells": (u1 - u0) * (b1 - b0), "font_profile": dict(self.profile),
                     "authentic_readability_qualified": False}


class Transport:
    """In-process framing only. The operator must never expose this object to a model."""
    def __init__(self, session, renderer, *, session_id, max_frames, deadline, clock=time.monotonic):
        need(type(session_id) is str and re.fullmatch(r"[0-9a-f]{64}", session_id), "Fresh operator session ID")
        need(type(max_frames) is int and 127 <= max_frames <= 200000, "Explicit frame budget")
        need(type(deadline) in (int, float) and math.isfinite(deadline) and deadline > clock(),
             "Explicit future monotonic deadline")
        initial = session.receipt()
        need(initial["actions"] == 0 and initial["answered"] == 0 and initial["closed"] is False,
             "Fresh operator-owned collector required")
        self._session, self._renderer = session, renderer
        self._id, self._limit, self._deadline, self._clock = session_id, max_frames, deadline, clock
        self._sequence, self._attempts, self._invalidated = 0, 0, False
        self._events = []
        self._chain = "0" * 64

    def _time(self):
        if self._clock() >= self._deadline:
            self._invalidated = True
            raise ValueError("Operator deadline exceeded")

    def exchange(self, raw):
        need(not self._invalidated, "Transport invalidated")
        self._time()
        need(self._attempts < self._limit, "Declared frame budget exhausted")
        self._attempts += 1
        event = {"attempt": self._attempts, "request_sha256": pin(raw) if type(raw) is bytes and
                 len(raw) <= MAX_REQUEST else None}
        try:
            frame = decode(raw)
            need(set(frame) == {"session", "sequence", "request"} and frame["session"] == self._id and
                 type(frame["sequence"]) is int and frame["sequence"] == self._sequence,
                 "Session and next sequence must match")
            # A correctly sequenced frame consumes that sequence even if its action is rejected.
            sequence = self._sequence
            self._sequence += 1
            need(type(frame["request"]) is dict, "Typed inner request")
            result = self._session.dispatch(encode(frame["request"]))
            self._time()
            if result["kind"] == "svg":
                png, record = self._renderer.render(result)
                response = {"kind": "image", "media_type": "image/png", "png_base64": base64.b64encode(png).decode(),
                            "width": record["width"], "height": record["height"],
                            "role": result["role"], "trial": result["trial"],
                            "unit_range": result["unit_range"], "bin_range": result["bin_range"]}
                event["render"] = record
            else:
                response = result
                if result["kind"] == "collection_complete":
                    event["collection_complete"] = True
            self._time()
            out = encode({"session": self._id, "sequence": sequence, "response": response})
            need(len(out) <= MAX_FRAME, "Bounded response frame")
            event.update(status="delivered", response_sha256=pin(out))
            self._time()
            self._record(event, enforce_deadline=True)
        except (ValueError, TypeError, UnicodeError, OverflowError, RecursionError, ET.ParseError) as exc:
            event.update(status="refused", error=type(exc).__name__)
            self._record(event)
            raise ValueError("Frame refused; no SVG or numeric fallback") from exc
        return out

    def _record(self, event, *, enforce_deadline=False):
        event["previous_sha256"] = self._chain
        next_chain = pin(encode(event))
        if enforce_deadline:
            self._time()
        self._chain = next_chain
        self._events.append(dict(event, event_sha256=self._chain))

    def export(self):
        self._time()
        need(not self._invalidated, "Transport invalidated")
        need(any(e["status"] == "delivered" and e.get("collection_complete") is True
                 for e in self._events), "A complete finish response must have been delivered")
        values = self._session.submission()
        receipt = self.receipt()
        self._time()
        return values, receipt

    def receipt(self):
        return {"frame_attempts": self._attempts, "next_sequence": self._sequence,
                "chain_sha256": self._chain, "invalidated": self._invalidated,
                "delivered_images": sum(e["status"] == "delivered" and "render" in e for e in self._events),
                "source": self._session.receipt(), "font_profile": dict(self._renderer.profile),
                "mechanical_transport_constructed": True, "authentic_image_run": False,
                "provider_delivery_qualified": False, "participant_isolation_qualified": False,
                "perceptual_readability_qualified": False, "scientific_mode_selected": False}

    def events(self):
        return json.loads(json.dumps(self._events))
