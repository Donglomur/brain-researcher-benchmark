"""Operator-owned raster presentation of one frozen Helsinki causal packet.

This is a representation and answer adapter, not a process/filesystem sandbox.
Only PNG pixels and allowlisted metadata are returned by the typed interface.
The complete packet and expected binding must remain outside participant access.
"""

import base64
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import struct
import types
import zlib


PROTOCOL_SHA256 = "9ca5ae8f2c1085503b8775d9598c7a495ed532457fb917d4a38654144957add5"
BINDING_FIELDS = frozenset(("case_id", "assessment_id", "protocol_id",
                            "representation_sha256", "fold", "input_sha256"))
PACKET_FIELDS = BINDING_FIELDS | frozenset((
    "schema", "montage", "units", "duration_seconds", "prediction_interval_seconds",
    "sample_clock", "samples", "quality_flags", "detector_sha256"))
MAX_PAGE_SAMPLES = 512
MAX_PAGE_CHANNELS = 6
WIDTH, LEFT, RIGHT, TOP, BAND = 1200, 150, 1180, 150, 130


class ViewError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ViewError(message)


def _load_protocol():
    path = Path(__file__).resolve().parent.parent / "complete-support-evaluator" / "protocol.py"
    body = path.read_bytes()
    require(hashlib.sha256(body).hexdigest() == PROTOCOL_SHA256,
            "existing packet protocol changed; requalification required")
    module = types.ModuleType("_helsinki_raster_bound_protocol")
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def _integer(value, low, high, name):
    require(type(value) is int and low <= value <= high, name + ": integer outside bounds")


def _number(value, name):
    try:
        ok = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        ok = False
    require(ok, name + ": finite number required")


def _validate(packet, binding, protocol):
    require(type(packet) is dict and set(packet) == PACKET_FIELDS, "exact public packet fields required")
    require(type(binding) is dict and set(binding) == BINDING_FIELDS, "trusted exact case binding required")
    for name in ("case_id", "representation_sha256", "input_sha256", "detector_sha256"):
        value = packet[name]
        require(type(value) is str and len(value) == 64 and
                all(c in "0123456789abcdef" for c in value), "invalid " + name)
    require(type(packet["assessment_id"]) is str and 0 < len(packet["assessment_id"]) <= 256,
            "invalid assessment identifier")
    require(packet["schema"] == "helsinki-causal-packet-v1" and
            packet["protocol_id"] == protocol.PROTOCOL, "wrong packet protocol")
    _integer(packet["fold"], 0, 4, "fold")
    require(type(binding["fold"]) is int and
            all(packet[k] == binding[k] for k in BINDING_FIELDS), "wrong protected case binding")
    require(type(packet["montage"]) is list and packet["montage"] == list(protocol.MONTAGE),
            "original ordered18-channel montage required")
    require(packet["units"] in ("uV", "mV", "V", "digital_count"), "unadmitted units")
    require(type(packet["duration_seconds"]) is int and packet["duration_seconds"] == 30 and
            type(packet["prediction_interval_seconds"]) is list and
            all(type(n) is int for n in packet["prediction_interval_seconds"]) and
            packet["prediction_interval_seconds"] == [29, 30], "exact causal support required")
    clock = packet["sample_clock"]
    require(type(clock) is dict and set(clock) == {"first_tick", "step_ticks", "ticks_per_second"},
            "exact rational sample clock required")
    require(all(type(v) is int for v in clock.values()) and clock["step_ticks"] > 0 and
            clock["ticks_per_second"] > 0 and 0 <= clock["first_tick"] < clock["step_ticks"] and
            math.gcd(clock["step_ticks"], clock["ticks_per_second"]) == 1, "invalid native clock")
    first, step, per_second = (clock[k] for k in ("first_tick", "step_ticks", "ticks_per_second"))
    expected = max(0, (30 * per_second - first + step - 1) // step)
    samples = packet["samples"]
    require(type(samples) is list and len(samples) == expected, "incomplete or extended causal samples")
    for row in samples:
        require(type(row) is list and len(row) == 18, "all18 channel samples required")
        for value in row:
            _number(value, "EEG sample")
    flags = packet["quality_flags"]
    require(type(flags) is list and len(flags) == 30 and all(type(v) is bool for v in flags),
            "original30 Boolean quality flags required")
    body = {k: v for k, v in packet.items() if k != "input_sha256"}
    require(protocol.digest(body) == packet["input_sha256"], "packet differs from protected input hash")


# Fixed bitmap labels avoid dependencies, fonts, external resources or embedded
# raw waveform text in the image. Unsupported label characters render as '?'.
_FONT_ROWS = {
    "0":"01110/10001/10011/10101/11001/10001/01110", "1":"00100/01100/00100/00100/00100/00100/01110",
    "2":"01110/10001/00001/00010/00100/01000/11111", "3":"11110/00001/00001/01110/00001/00001/11110",
    "4":"00010/00110/01010/10010/11111/00010/00010", "5":"11111/10000/10000/11110/00001/00001/11110",
    "6":"01110/10000/10000/11110/10001/10001/01110", "7":"11111/00001/00010/00100/01000/01000/01000",
    "8":"01110/10001/10001/01110/10001/10001/01110", "9":"01110/10001/10001/01111/00001/00001/01110",
    "A":"01110/10001/10001/11111/10001/10001/10001", "B":"11110/10001/10001/11110/10001/10001/11110",
    "C":"01111/10000/10000/10000/10000/10000/01111", "D":"11110/10001/10001/10001/10001/10001/11110",
    "E":"11111/10000/10000/11110/10000/10000/11111", "F":"11111/10000/10000/11110/10000/10000/10000",
    "G":"01111/10000/10000/10111/10001/10001/01111", "H":"10001/10001/10001/11111/10001/10001/10001",
    "I":"01110/00100/00100/00100/00100/00100/01110", "J":"00111/00010/00010/00010/10010/10010/01100",
    "K":"10001/10010/10100/11000/10100/10010/10001", "L":"10000/10000/10000/10000/10000/10000/11111",
    "M":"10001/11011/10101/10101/10001/10001/10001", "N":"10001/11001/10101/10011/10001/10001/10001",
    "O":"01110/10001/10001/10001/10001/10001/01110", "P":"11110/10001/10001/11110/10000/10000/10000",
    "Q":"01110/10001/10001/10001/10101/10010/01101", "R":"11110/10001/10001/11110/10100/10010/10001",
    "S":"01111/10000/10000/01110/00001/00001/11110", "T":"11111/00100/00100/00100/00100/00100/00100",
    "U":"10001/10001/10001/10001/10001/10001/01110", "V":"10001/10001/10001/10001/10001/01010/00100",
    "W":"10001/10001/10001/10101/10101/10101/01010", "X":"10001/10001/01010/00100/01010/10001/10001",
    "Y":"10001/10001/01010/00100/00100/00100/00100", "Z":"11111/00001/00010/00100/01000/10000/11111",
    "-":"00000/00000/00000/11111/00000/00000/00000", "+":"00000/00100/00100/11111/00100/00100/00000",
    ".":"00000/00000/00000/00000/00000/00110/00110", "/":"00001/00010/00010/00100/01000/01000/10000",
    "=":"00000/00000/11111/00000/11111/00000/00000", ":":"00000/00110/00110/00000/00110/00110/00000",
    ";":"00000/00110/00110/00000/00110/00100/01000",
    "(":"00010/00100/01000/01000/01000/00100/00010", ")":"01000/00100/00010/00010/00010/00100/01000",
    "_":"00000/00000/00000/00000/00000/00000/11111", " ":"00000/00000/00000/00000/00000/00000/00000",
    "?":"01110/10001/00001/00010/00100/00000/00100",
}


class _Canvas:
    def __init__(self, height):
        self.width, self.height = WIDTH, height
        self.pixels = bytearray(b"\xff" * (WIDTH * height * 3))

    def pixel(self, x, y, color):
        if 0 <= x < self.width and 0 <= y < self.height:
            at = (y * self.width + x) * 3
            self.pixels[at:at + 3] = bytes(color)

    def rectangle(self, x0, y0, x1, y1, color):
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(self.width, x1), min(self.height, y1)
        stripe = bytes(color) * max(0, x1 - x0)
        for y in range(y0, y1):
            at = (y * self.width + x0) * 3
            self.pixels[at:at + len(stripe)] = stripe

    def line(self, x0, y0, x1, y1, color):
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = 1 if x0 < x1 else -1, 1 if y0 < y1 else -1
        error = dx + dy
        while True:
            self.pixel(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * error
            if e2 >= dy:
                error += dy
                x0 += sx
            if e2 <= dx:
                error += dx
                y0 += sy

    def text(self, x, y, text, color=(20, 20, 20), scale=2):
        for letter in text.upper():
            for row, bits in enumerate(_FONT_ROWS.get(letter, _FONT_ROWS["?"]).split("/")):
                for col, bit in enumerate(bits):
                    if bit == "1":
                        self.rectangle(x + col * scale, y + row * scale,
                                       x + (col + 1) * scale, y + (row + 1) * scale, color)
            x += 6 * scale

    def png(self):
        def chunk(kind, body):
            return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
        scanlines = b"".join(b"\x00" + self.pixels[y * WIDTH * 3:(y + 1) * WIDTH * 3]
                             for y in range(self.height))
        return (b"\x89PNG\r\n\x1a\n" +
                chunk(b"IHDR", struct.pack(">IIBBBBB", WIDTH, self.height, 8, 2, 0, 0, 0)) +
                chunk(b"IDAT", zlib.compress(scanlines, 6)) + chunk(b"IEND", b""))


def _render(packet, start, stop, channels, scale):
    canvas = _Canvas(TOP + BAND * len(channels) + 40)
    first, step, per_second = (packet["sample_clock"][k]
                               for k in ("first_tick", "step_ticks", "ticks_per_second"))
    canvas.text(20, 16, "NEONATAL EEG - RELATIVE PACKET TIME - NO FILTER OR RESAMPLING")
    canvas.text(20, 42, "QUALITY FLAGS (NOT MISSINGNESS): 0 TO 30 SECONDS")
    for second, flag in enumerate(packet["quality_flags"]):
        x = 150 + 34 * second
        canvas.rectangle(x, 67, x + 29, 82, (225, 145, 20) if flag else (235, 235, 235))
        canvas.text(x + 5, 86, str(second), scale=1)
    canvas.line(150 + 34 * 29, 64, 150 + 34 * 29 + 29, 64, (200, 0, 0))
    canvas.text(20, 108, "SAMPLES " + str(start) + " TO " + str(stop) + " EXCLUSIVE; SCALE " +
                format(scale, ".6g") + " " + packet["units"] + "/DIV", scale=1)
    canvas.text(20, 124, "FIRST " + str(first + start * step) + "/" + str(per_second) +
                " S; LAST " + str(first + (stop - 1) * step) + "/" + str(per_second) +
                " S; FINAL-SECOND REGION SHADED", scale=1)
    clipped = []
    def x_for(index):
        return LEFT + round((RIGHT - LEFT) * (index - start) / max(1, stop - start - 1))
    for slot, channel in enumerate(channels):
        base_y = TOP + BAND * slot
        center = base_y + 50
        shaded = next((i for i in range(start, stop) if first + i * step >= 29 * per_second), None)
        if shaded is not None:
            canvas.rectangle(x_for(shaded), base_y, RIGHT + 1, base_y + 101, (255, 242, 242))
        for division in (-2, -1, 0, 1, 2):
            canvas.line(LEFT, center + division * 25, RIGHT, center + division * 25,
                        (165, 165, 165) if division == 0 else (218, 218, 218))
        for x in range(LEFT, RIGHT + 1, 103):
            canvas.line(x, base_y, x, base_y + 100, (235, 235, 235))
        canvas.text(8, center - 7, packet["montage"][channel], scale=2)
        canvas.text(8, center + 17, "ZERO CENTER", scale=1)
        previous = None
        count = 0
        for i in range(start, stop):
            ratio = packet["samples"][i][channel] / scale
            outside = not math.isfinite(ratio) or abs(ratio) > 2
            count += int(outside)
            ratio = max(-2, min(2, ratio))
            point = (x_for(i), center - round(ratio * 25))
            if previous is not None:
                canvas.line(*previous, *point, (0, 0, 0))
            canvas.pixel(*point, (200, 0, 0) if outside else (0, 0, 0))
            previous = point
        clipped.append(count)
        canvas.text(LEFT, base_y + 108, "CLIPPED SAMPLES: " + str(count) + " - CHANGE SCALE TO INSPECT", scale=1)
    return canvas.png(), clipped


class Session:
    """Trusted-side adapter for one case, with a single final probability.

    Passing Session or its Python process to a participant defeats its boundary.
    Use a separate externally admitted transport/sandbox for actual participants.
    No cohort roster, next-case accessor, file/network action or scoring is here.
    """

    def __init__(self, packet, expected_binding):
        protocol = _load_protocol()
        self._packet = deepcopy(packet)
        self._binding = deepcopy(expected_binding)
        # Validate the exact owned snapshot that will be rendered. Validating a
        # caller object first, then copying it, leaves a mutation race between
        # the protected-input hash check and the subsequently displayed bytes.
        _validate(self._packet, self._binding, protocol)
        self._answer = None

    def act(self, action):
        require(self._answer is None, "case is finalized")
        require(type(action) is dict and type(action.get("action")) is str, "typed action required")
        name = action["action"]
        if name == "describe":
            require(set(action) == {"action"}, "describe accepts no arguments")
            return {"schema": "helsinki-raster-description-v1", "binding": deepcopy(self._binding),
                    "sample_count": len(self._packet["samples"]), "montage": list(self._packet["montage"]),
                    "sample_clock": dict(self._packet["sample_clock"]), "units": self._packet["units"],
                    "duration_seconds": 30, "prediction_interval_seconds": [29, 30],
                    "quality_flags": list(self._packet["quality_flags"]),
                    "maximum_page_samples": MAX_PAGE_SAMPLES, "maximum_page_channels": MAX_PAGE_CHANNELS,
                    "representation": "PNG waveform pages; pixel quantization and gain clipping are explicit",
                    "quality_flag_interpretation": "original-input quality indicators, not verified missingness"}
        if name == "view":
            require(set(action) == {"action", "start_sample", "stop_sample", "channels", "units_per_division"},
                    "view requires exact sample/channel/gain fields")
            start, stop, channels, scale = (action[k] for k in
                                           ("start_sample", "stop_sample", "channels", "units_per_division"))
            _integer(start, 0, len(self._packet["samples"]) - 1, "start_sample")
            _integer(stop, start + 1, min(start + MAX_PAGE_SAMPLES, len(self._packet["samples"])), "stop_sample")
            require(type(channels) is list and 1 <= len(channels) <= MAX_PAGE_CHANNELS,
                    "choose1..6 original channels")
            for channel in channels:
                _integer(channel, 0, 17, "channel")
            require(len(set(channels)) == len(channels), "duplicate channel")
            _number(scale, "units_per_division")
            require(scale > 0, "positive scale required")
            png, clipped = _render(self._packet, start, stop, channels, scale)
            return {"schema": "helsinki-raster-frame-v1", "binding": deepcopy(self._binding),
                    "mime_type": "image/png", "png_base64": base64.b64encode(png).decode("ascii"),
                    "png_sha256": hashlib.sha256(png).hexdigest(), "width": WIDTH,
                    "height": TOP + BAND * len(channels) + 40,
                    "selection": {"start_sample": start, "stop_sample": stop, "channels": list(channels),
                                  "units_per_division": scale},
                    "clipped_sample_counts": clipped,
                    "source_samples_visited_per_channel": stop - start}
        if name == "answer":
            require(set(action) == {"action", "case_id", "input_sha256", "probability"},
                    "answer requires exact case/input/probability fields")
            require(action["case_id"] == self._binding["case_id"] and
                    action["input_sha256"] == self._binding["input_sha256"], "wrong answer binding")
            probability = action["probability"]
            _number(probability, "probability")
            require(0 <= probability <= 1, "probability outside[0,1]")
            self._answer = dict(self._binding, probability=probability)
            return {"schema": "helsinki-raster-answer-receipt-v1", "accepted": True,
                    "case_id": self._binding["case_id"], "input_sha256": self._binding["input_sha256"]}
        raise ViewError("unknown action; only describe, view and answer are available")

    def finish(self):
        """Trusted collector receives the exact row consumed by existing evaluate."""
        require(self._answer is not None, "missing final probability")
        return deepcopy(self._answer)
