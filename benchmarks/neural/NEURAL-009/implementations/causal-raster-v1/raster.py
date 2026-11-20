"""Inactive image-only delivery for the existing NEURAL-009 causal Cohort.

The owner supplies the exact pinned predecessor Cohort. Its SVG stays private;
only PNG bytes and sanitized reply fields may cross the participant boundary.
This source adapter is not an artifact transport, protected host or native run.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import struct
import xml.etree.ElementTree as ET
import zlib

REPRESENTATION = "inactive_raster_png_not_native_qualified"
MAX_PIXELS = 4_194_304
MAX_SVG_BYTES = 8 * 1024 * 1024
MAX_POINTS = 262_144
MAX_LINE_STEPS = 16_777_216
BLACK = (25, 35, 48)
TRACE = (0, 0, 0)

# The uppercase/digit/basic punctuation glyphs and integer line/PNG algorithms
# derive from NEURAL-077 visual-viewer-v1/raster.py at the pin in SOURCE.json.
# Unlike that donor, this font never uppercases input. Lowercase and remaining
# printable ASCII glyphs are explicit; other Unicode is refused, not substituted.
FONT_ROWS = {
    ' ': '00 00 00 00 00 00 00',
    'A': '0e 11 11 1f 11 11 11', 'B': '1e 11 11 1e 11 11 1e',
    'C': '0e 11 10 10 10 11 0e', 'D': '1e 11 11 11 11 11 1e',
    'E': '1f 10 10 1e 10 10 1f', 'F': '1f 10 10 1e 10 10 10',
    'G': '0e 11 10 17 11 11 0f', 'H': '11 11 11 1f 11 11 11',
    'I': '0e 04 04 04 04 04 0e', 'J': '07 02 02 02 12 12 0c',
    'K': '11 12 14 18 14 12 11', 'L': '10 10 10 10 10 10 1f',
    'M': '11 1b 15 15 11 11 11', 'N': '11 19 15 13 11 11 11',
    'O': '0e 11 11 11 11 11 0e', 'P': '1e 11 11 1e 10 10 10',
    'Q': '0e 11 11 11 15 12 0d', 'R': '1e 11 11 1e 14 12 11',
    'S': '0f 10 10 0e 01 01 1e', 'T': '1f 04 04 04 04 04 04',
    'U': '11 11 11 11 11 11 0e', 'V': '11 11 11 11 11 0a 04',
    'W': '11 11 11 15 15 15 0a', 'X': '11 11 0a 04 0a 11 11',
    'Y': '11 11 0a 04 04 04 04', 'Z': '1f 01 02 04 08 10 1f',
    'a': '00 00 0e 01 0f 11 0f', 'b': '10 10 16 19 11 11 1e',
    'c': '00 00 0e 11 10 11 0e', 'd': '01 01 0d 13 11 11 0f',
    'e': '00 00 0e 11 1f 10 0e', 'f': '06 09 08 1c 08 08 08',
    'g': '00 0f 11 11 0f 01 0e', 'h': '10 10 16 19 11 11 11',
    'i': '04 00 0c 04 04 04 0e', 'j': '02 00 06 02 02 12 0c',
    'k': '10 10 12 14 18 14 12', 'l': '0c 04 04 04 04 04 0e',
    'm': '00 00 1a 15 15 15 15', 'n': '00 00 16 19 11 11 11',
    'o': '00 00 0e 11 11 11 0e', 'p': '00 1e 11 11 1e 10 10',
    'q': '00 0f 11 11 0f 01 01', 'r': '00 00 16 19 10 10 10',
    's': '00 00 0f 10 0e 01 1e', 't': '08 08 1c 08 08 09 06',
    'u': '00 00 11 11 11 13 0d', 'v': '00 00 11 11 11 0a 04',
    'w': '00 00 11 11 15 15 0a', 'x': '00 00 11 0a 04 0a 11',
    'y': '00 11 11 11 0f 01 0e', 'z': '00 00 1f 02 04 08 1f',
    '0': '0e 11 13 15 19 11 0e', '1': '04 0c 04 04 04 04 0e',
    '2': '0e 11 01 02 04 08 1f', '3': '1e 01 01 0e 01 01 1e',
    '4': '02 06 0a 12 1f 02 02', '5': '1f 10 10 1e 01 01 1e',
    '6': '0e 10 10 1e 11 11 0e', '7': '1f 01 02 04 08 08 08',
    '8': '0e 11 11 0e 11 11 0e', '9': '0e 11 11 0f 01 01 0e',
    '-': '00 00 00 1f 00 00 00', '.': '00 00 00 00 00 0c 0c',
    ':': '00 0c 0c 00 0c 0c 00', '/': '01 02 02 04 08 08 10',
    '(': '02 04 08 08 08 04 02', ')': '08 04 02 02 02 04 08',
    '[': '0e 08 08 08 08 08 0e', ']': '0e 02 02 02 02 02 0e',
    '=': '00 00 1f 00 1f 00 00', '+': '00 04 04 1f 04 04 00',
    '_': '00 00 00 00 00 00 1f', ',': '00 00 00 00 0c 0c 08',
    '!': '04 04 04 04 04 00 04', '"': '0a 0a 0a 00 00 00 00',
    '#': '0a 0a 1f 0a 1f 0a 0a', '$': '04 0f 14 0e 05 1e 04',
    '%': '19 1a 02 04 08 0b 13', '&': '0c 12 14 08 15 12 0d',
    "'": '04 04 08 00 00 00 00', '*': '00 04 15 0e 15 04 00',
    ';': '00 0c 0c 00 0c 0c 08', '<': '02 04 08 10 08 04 02',
    '>': '08 04 02 01 02 04 08', '?': '0e 11 01 02 04 00 04',
    '@': '0e 11 17 15 17 10 0e', '\\': '10 08 08 04 02 02 01',
    '^': '04 0a 11 00 00 00 00', '`': '08 04 02 00 00 00 00',
    '{': '02 04 04 08 04 04 02', '|': '04 04 04 04 04 04 04',
    '}': '08 04 04 02 04 04 08', '~': '00 00 09 16 00 00 00',
}
FONT = {key: tuple(int(value, 16) for value in rows.split())
        for key, rows in FONT_ROWS.items()}


class RasterRefused(ValueError):
    pass


def need(condition, reason):
    if not condition:
        raise RasterRefused(reason)


def integer(value, minimum=1):
    need(type(value) is int and minimum <= value <= 2**53 - 1, "invalid_integer")
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def png_size(width, height):
    scan_bytes = height * (1 + width * 3)
    return 63 + scan_bytes + 5 * ((scan_bytes + 65534) // 65535)


class Canvas:
    """Bounded variable canvas; out-of-canvas operations refuse rather than clip."""
    def __init__(self, width, height):
        integer(width); integer(height)
        need(width * height <= MAX_PIXELS, "pixel_limit")
        self.width, self.height = width, height
        self.pixels = bytearray(b"\xff" * (width * height * 3))

    def pixel(self, x, y, color):
        need(type(x) is int and type(y) is int and
             0 <= x < self.width and 0 <= y < self.height, "pixel_outside_canvas")
        index = (y * self.width + x) * 3
        self.pixels[index:index + 3] = bytes(color)

    def line(self, x0, y0, x1, y1, color):
        need(all(type(v) is int for v in (x0, y0, x1, y1)) and
             0 <= x0 < self.width and 0 <= x1 < self.width and
             0 <= y0 < self.height and 0 <= y1 < self.height, "line_outside_canvas")
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        error = dx + dy
        while True:
            self.pixel(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            twice = 2 * error
            if twice >= dy:
                error += dy
                x0 += sx
            if twice <= dx:
                error += dx
                y0 += sy

    def text(self, x, y, text, scale, right):
        need(type(text) is str and all(char in FONT for char in text), "unsupported_glyph")
        need(x >= 0 and y >= 0 and y + 7 * scale <= self.height and
             x + (6 * len(text) - 1) * scale <= right <= self.width, "text_does_not_fit")
        for char in text:
            for row, bits in enumerate(FONT[char]):
                for col in range(5):
                    if bits & (1 << (4 - col)):
                        for sy in range(scale):
                            for sx in range(scale):
                                self.pixel(x + col * scale + sx, y + row * scale + sy, BLACK)
            x += 6 * scale

    def png(self):
        def chunk(name, data):
            return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data))
        scan = b"".join(b"\0" + self.pixels[y * self.width * 3:(y + 1) * self.width * 3]
                        for y in range(self.height))
        compressed = bytearray(b"\x78\x01")
        for start in range(0, len(scan), 65535):
            block = scan[start:start + 65535]
            compressed.append(int(start + len(block) == len(scan)))
            compressed += struct.pack("<HH", len(block), len(block) ^ 65535) + block
        compressed += struct.pack(">I", zlib.adler32(scan))
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB",
                self.width, self.height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", compressed)
                + chunk(b"IEND", b""))


def _empty(node):
    return node.tail in (None, "")


def _polylines(svg, record, bands, original, start, stop):
    """Accept exactly the pinned renderer's generated subset, never general SVG."""
    need(type(svg) is str and len(svg) <= MAX_SVG_BYTES, "svg_size")
    need(len(svg.encode()) <= min(MAX_SVG_BYTES, original["max_svg_bytes"]), "svg_size")
    need("<!" not in svg and "<?" not in svg, "svg_declaration")
    count, channels = stop - start, len(bands)
    need(0 < count <= original["max_window_samples"] and
         count * channels <= min(MAX_POINTS, original["max_window_values"]), "point_limit")
    width, height = original["width_px"], original["channel_height_px"]
    root = ET.fromstring(svg)
    tag = "{http://www.w3.org/2000/svg}"
    need(root.tag == tag + "svg" and root.attrib == {
        "viewBox": f"0 0 {width} {height * channels}", "role": "img"}
        and root.text in (None, "") and _empty(root), "svg_root")
    children = list(root)
    need(len(children) == channels + 1, "svg_channels")
    title = children[0]
    need(title.tag == tag + "title" and not title.attrib and len(title) == 0 and
         title.text == "Causal calibrated EEG; fixed ranges in microvolts" and _empty(title), "svg_title")
    result, work = [], 0
    for row, (group, band, channel) in enumerate(zip(children[1:], bands, record["predictor_channels"])):
        need(group.tag == tag + "g" and not group.attrib and len(group) == 2 and
             group.text in (None, "") and _empty(group), "svg_group")
        title, line = list(group)
        expected = (f'{channel["label"]}; {band["minimum"]} to {band["maximum"]} uV; '
                    f'sample times {start}/{record["native_sample_rate_hz"]} to '
                    f'{stop - 1}/{record["native_sample_rate_hz"]} seconds')
        need(title.tag == tag + "title" and not title.attrib and len(title) == 0 and
             title.text == expected and _empty(title), "svg_channel_title")
        need(line.tag == tag + "polyline" and len(line) == 0 and line.text in (None, "")
             and _empty(line) and set(line.attrib) == {"fill", "stroke", "stroke-width", "points"}
             and line.attrib["fill"] == "none" and line.attrib["stroke"] == "black"
             and line.attrib["stroke-width"] == "1", "svg_polyline")
        tokens = line.attrib["points"].split(" ")
        need(len(tokens) == count, "svg_point_count")
        points = []
        for offset, token in enumerate(tokens):
            pair = token.split(",")
            need(len(pair) == 2 and all(len(v) <= 32 and re.fullmatch(
                r"-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", v) for v in pair), "svg_coordinate")
            x, y = map(float, pair)
            expected_x = float(f"{offset * (width - 1) / max(1, count - 1):.9g}")
            need(math.isfinite(x) and math.isfinite(y) and x == expected_x and
                 0 <= x <= width - 1 and row * height <= y <= (row + 1) * height - 1,
                 "svg_coordinate_outside_band")
            point = (round(x), round(y))
            if points:
                work += max(abs(point[0] - points[-1][0]), abs(point[1] - points[-1][1])) + 1
            else:
                work += 1
            need(work <= MAX_LINE_STEPS, "raster_work_limit")
            points.append(point)
        result.append(points)
    return result


class RasterDelivery:
    """Owner-only adapter for a source-authenticated predecessor Cohort instance.

    The owner must retain exclusive serialized access to the Cohort and deliver
    only this adapter's replies. Python object access is not a security boundary.
    Constructor protocol failures are non-consuming. Post-view image failures
    fail the original case, retaining its original cleanup and ledger semantics.
    """
    def __init__(self, cohort, raster_protocol, *, expected_protocol_sha256):
        fields = {"schema", "gutter_px", "header_px", "footer_px", "font_scale",
                  "max_image_pixels", "max_png_bytes", "max_total_png_bytes_per_record"}
        need(type(raster_protocol) is dict and set(raster_protocol) == fields, "raster_protocol_fields")
        need(raster_protocol["schema"] == "neural009_causal_raster_v1", "raster_protocol_schema")
        for name in fields - {"schema"}:
            integer(raster_protocol[name])
        need(type(expected_protocol_sha256) is str and
             re.fullmatch("[0-9a-f]{64}", expected_protocol_sha256) is not None and
             digest(raster_protocol) == expected_protocol_sha256, "raster_protocol_commitment")
        scale = raster_protocol["font_scale"]
        need(scale <= 4 and raster_protocol["gutter_px"] >= 16 and
             raster_protocol["header_px"] >= 40 * scale and
             raster_protocol["footer_px"] >= 12 * scale and
             raster_protocol["max_image_pixels"] <= MAX_PIXELS and
             raster_protocol["max_png_bytes"] <= 16 * 1024 * 1024 and
             raster_protocol["max_total_png_bytes_per_record"] >= raster_protocol["max_png_bytes"],
             "raster_protocol_geometry")
        need(cohort._protocol["channel_height_px"] >= 32 * scale, "channel_band_not_readable")
        self._cohort = cohort
        self._protocol = dict(raster_protocol)
        self._protocol_sha256 = expected_protocol_sha256
        self._png_bytes = {name: 0 for name in cohort._state}

    def case_ids(self):
        return self._cohort.case_ids()

    def start_edf(self, *args, **kwargs):
        reply = dict(self._cohort.start_edf(*args, **kwargs))
        if reply.get("status") == "active":
            reply["representation"] = REPRESENTATION
        return reply

    def abort_active(self):
        return self._cohort.abort_active()

    def finish(self):
        """Operator-only original candidate/ledger, with private image accounting."""
        result = dict(self._cohort.finish())
        result["raster_delivery"] = {"protocol_sha256": self._protocol_sha256,
                                     "png_bytes_by_record": dict(self._png_bytes),
                                     "mode_activated": False, "scientific_qualification": False}
        return result

    def dispatch(self, request):
        reply = self._cohort.dispatch(request)
        if reply.get("status") != "view":
            return reply
        try:
            image = self._render(reply, request)
        except Exception:
            return self._cohort._fail("raster_refused")
        return {"case_id": reply["case_id"], "status": "view",
                "endpoint_tick": reply["endpoint_tick"], "view_id": reply["view_id"],
                "representation": REPRESENTATION, "image_mime_type": "image/png",
                "image_png": image, "image_sha256": hashlib.sha256(image).hexdigest()}

    def _render(self, reply, request):
        owner, protocol = self._cohort, self._protocol
        name = owner._join[reply["case_id"]]
        record, original = owner._records[name], owner._protocol
        bands = original["scales_uv"][name]
        scale, gutter, header = protocol["font_scale"], protocol["gutter_px"], protocol["header_px"]
        trace_width, band_height = original["width_px"], original["channel_height_px"]
        width = gutter + trace_width + 8
        height = header + len(bands) * band_height + protocol["footer_px"]
        need(width * height <= protocol["max_image_pixels"], "image_pixel_budget")
        predicted_size = png_size(width, height)
        need(predicted_size <= protocol["max_png_bytes"] and
             self._png_bytes[name] + predicted_size <= protocol["max_total_png_bytes_per_record"],
             "image_byte_budget")
        rate = record["native_sample_rate_hz"]
        end, lookback = request["end_tick"], request["lookback_ticks"]
        start = (max(0, end - lookback) * rate + 9) // 10
        stop = min(record["native_sample_count"], end * rate // 10 + 1)
        points = _polylines(reply["svg"], record, bands, original, start, stop)
        canvas = Canvas(width, height)
        titles = ["CAUSAL EEG - uV", f"NATIVE TIME {start}/{rate} TO {stop - 1}/{rate} s",
                  f'DECISION ENDPOINT {reply["endpoint_tick"]}/10 s',
                  "ALL SELECTED SAMPLES; NO FILTER"]
        for line, title in enumerate(titles):
            canvas.text(8, 4 + 9 * scale * line, title, scale, width - 8)
        for row, (channel, band, trace) in enumerate(zip(record["predictor_channels"], bands, points)):
            top = header + row * band_height
            for line, title in enumerate((channel["label"], f'MAX {band["maximum"]} uV', f'MIN {band["minimum"]} uV')):
                canvas.text(8, top + 4 + 9 * scale * line, title, scale, gutter - 8)
            previous = None
            for x, y in trace:
                point = (gutter + x, header + y)
                if previous is None:
                    canvas.pixel(*point, TRACE)
                else:
                    canvas.line(*previous, *point, TRACE)
                previous = point
        canvas.text(8, header + len(bands) * band_height + 4,
                    "RASTER DISPLAY; NATIVE EXECUTION UNQUALIFIED", scale, width - 8)
        png = canvas.png()
        need(len(png) == predicted_size, "png_size_invariant")
        self._png_bytes[name] += len(png)
        return png
