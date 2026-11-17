"""Pure typed DoSEI trace renderer; no source I/O, model tools or diagnostics.

This renders a caller-authenticated observation and exact release profile. It
checks the profile's required bindings, but cannot authenticate source-array
identity itself: that is an unimplemented host delivery-driver obligation.
Only the host may call the constructor. A participant runtime must expose the
typed actions and returned raster bytes, never this module or the raw packet.
"""
import copy
import hashlib
import json
import math
import re
import struct
import zlib

POLICY = "dosei_observed_points_gap8_display_v1"
SOURCE_PROOF = "f83503c5a6031c9043579b84bd48ae6925ceb9ace491c2c9abf1198fe00bd202"
SOURCE_COHORT = "1faf6f9c9d1b5c202c8d80a86fb779c50040f4ca94ab2e6b660984335464a2ed"
WIDTH, HEIGHT = 1000, 640
LEFT, RIGHT = 90, 960
PANELS = ((85, 265), (340, 520))
GAINS_UV = (25, 50, 100, 187.5)
HASH = re.compile(r"[0-9a-f]{64}\Z")
PUBLIC_FIELDS = frozenset(("schema", "condition", "case_id", "channels", "units",
    "interval_ms", "relative_time_ms", "values_uv", "observation_mask",
    "source_endpoint_mask", "coverage"))
PROFILE_FIELDS = frozenset(("schema", "source_proof_sha256", "source_cohort_sha256",
    "array_identity_binding_sha256", "case_id", "observation_sha256",
    "source_quality_values", "display_policy"))
# Small deterministic bitmap font: calibration remains present without system
# fonts, browser dependencies, software installation or external resources.
FONT = {
 " ":(0,0,0,0,0,0,0), "0":(14,17,19,21,25,17,14), "1":(4,12,4,4,4,4,14),
 "2":(14,17,1,2,4,8,31), "3":(30,1,1,14,1,1,30), "4":(2,6,10,18,31,2,2),
 "5":(31,16,16,30,1,1,30), "6":(14,16,16,30,17,17,14), "7":(31,1,2,4,8,8,8),
 "8":(14,17,17,14,17,17,14), "9":(14,17,17,15,1,1,14), ".":(0,0,0,0,0,12,12),
 "-":(0,0,0,31,0,0,0), "+":(0,4,4,31,4,4,0), "/":(1,2,2,4,8,8,16),
 ":":(0,12,12,0,12,12,0), "=":(0,0,31,0,31,0,0),
 "A":(14,17,17,31,17,17,17), "B":(30,17,17,30,17,17,30),
 "C":(14,17,16,16,16,17,14), "D":(30,17,17,17,17,17,30),
 "E":(31,16,16,30,16,16,31), "F":(31,16,16,30,16,16,16),
 "G":(14,17,16,23,17,17,15), "H":(17,17,17,31,17,17,17),
 "I":(14,4,4,4,4,4,14), "J":(7,2,2,2,2,18,12),
 "K":(17,18,20,24,20,18,17), "L":(16,16,16,16,16,16,31),
 "M":(17,27,21,21,17,17,17), "N":(17,25,25,21,19,19,17),
 "O":(14,17,17,17,17,17,14), "P":(30,17,17,30,16,16,16),
 "Q":(14,17,17,17,21,18,13), "R":(30,17,17,30,20,18,17),
 "S":(15,16,16,14,1,1,30), "T":(31,4,4,4,4,4,4),
 "U":(17,17,17,17,17,17,14), "V":(17,17,17,17,17,10,4),
 "W":(17,17,17,21,21,21,10), "X":(17,17,10,4,10,17,17),
 "Y":(17,17,10,4,4,4,4), "Z":(31,1,2,4,8,16,31),
}


class ViewerRefusal(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise ViewerRefusal(message)


def canonical_packet(packet):
    return json.dumps(packet, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def validate_packet(packet):
    require(type(packet) is dict and set(packet) == PUBLIC_FIELDS, "public packet fields differ")
    require(packet["schema"] == "dosei_paired_observation_v1" and
            packet["condition"] == "native_marker_relative_30s_v1" and
            type(packet["case_id"]) is str and HASH.fullmatch(packet["case_id"]) and
            packet["channels"] == ["Intellivue/EEG_1", "Intellivue/EEG_2"] and
            packet["units"] == "microvolt" and type(packet["interval_ms"]) is list and
            all(type(t) is int for t in packet["interval_ms"]) and packet["interval_ms"] == [-30000, 0],
            "source observation condition differs")
    times, values, masks, endpoints = (packet[key] for key in
        ("relative_time_ms", "values_uv", "observation_mask", "source_endpoint_mask"))
    require(all(type(v) is list for v in (times, values, masks, endpoints)) and
            len(times) <= 7501 and len(times) == len(values) == len(masks) == len(endpoints),
            "complete bounded two-channel packet required")
    previous = None
    for t, pair, mask, endpoint in zip(times, values, masks, endpoints):
        require(type(t) is int and -30000 <= t < 0 and
                (previous is None or t-previous in (0, 4)), "exact native table clock required")
        previous = t
        require(all(type(v) is list and len(v) == 2 for v in (pair, mask, endpoint)),
                "two source channels required")
        for value, valid, flag in zip(pair, mask, endpoint):
            require(type(valid) is bool and type(flag) is bool, "exact mask booleans required")
            if not valid:
                require(value is None and not flag, "unobserved cell must remain null")
            else:
                require(type(value) is float and math.isfinite(value) and abs(value) <= 187.5,
                        "finite source observation required")
                require(not flag or abs(value) == 187.5, "source endpoint flag mismatch")
    coverage = packet["coverage"]
    require(type(coverage) is dict and set(coverage) ==
            {"source_prefix_missing_ms", "full_interval_recorded", "row_count"} and
            type(coverage["source_prefix_missing_ms"]) is int and
            0 <= coverage["source_prefix_missing_ms"] <= 30000 and
            type(coverage["full_interval_recorded"]) is bool and
            coverage["full_interval_recorded"] == (coverage["source_prefix_missing_ms"] == 0) and
            type(coverage["row_count"]) is int and coverage["row_count"] == len(times),
            "source interval coverage differs")


def validate_profile(packet, profile):
    """Check declared release/input bindings; host authenticates their provenance.

    Missing/wrong profile is a refusal under this policy, never a point-only
    fallback. The release proof establishes that masked cells are source blanks
    because the complete cohort contains only numeric quality states0/1/16.
    The host must authenticate that proof and closed-array identity and disclose
    this same profile to both workflows before calling this pure component.
    """
    require(type(profile) is dict and set(profile) == PROFILE_FIELDS, "exact release profile required")
    quality = profile["source_quality_values"]
    require(type(quality) is list and len(quality) == 2 and
            all(type(channel) is list and len(channel) == 3 and
                all(type(value) is int for value in channel) for channel in quality),
            "exact integer source quality vocabulary required")
    require(profile["schema"] == "dosei_renderer_source_profile_v1" and
            profile["source_proof_sha256"] == SOURCE_PROOF and
            profile["source_cohort_sha256"] == SOURCE_COHORT and
            profile["case_id"] == packet["case_id"] and
            profile["source_quality_values"] == [[0, 1, 16], [0, 1, 16]] and
            profile["display_policy"] == POLICY, "wrong source or display profile")
    require(type(profile["array_identity_binding_sha256"]) is str and
            HASH.fullmatch(profile["array_identity_binding_sha256"]), "closed-array binding required")
    digest = hashlib.sha256(canonical_packet(packet)).hexdigest()
    require(profile["observation_sha256"] == digest, "profile is for a different observation")
    return digest


def geometry(packet, start, end):
    """Host-internal drawing primitives; never a participant tool result."""
    points, lines, blanks = [[], []], [[], []], [[], []]
    previous = [None, None]
    prior_time = None
    for t, values, masks, flags in zip(packet["relative_time_ms"], packet["values_uv"],
                                     packet["observation_mask"], packet["source_endpoint_mask"]):
        if prior_time is not None and t == prior_time:
            previous = [None, None]  # Never connect across a duplicate table time.
        prior_time = t
        if not start <= t < end:
            previous = [None, None]
            continue
        for channel in range(2):
            if not masks[channel]:
                blanks[channel].append(t)
                continue  # Exact source profile makes this a blank, not invalid data.
            value, flagged = values[channel], flags[channel]
            points[channel].append((t, value, flagged))
            if flagged:
                previous[channel] = None
                continue
            old = previous[channel]
            if old is not None and 0 < t-old[0] <= 8:
                lines[channel].append((old[0], old[1], t, value))
            previous[channel] = (t, value)
    return points, lines, blanks


def clip_display_segment(a, av, b, bv, gain):
    """Clip the original display line to gain bounds, without moving samples.

    Clamping both vertices before drawing would change the in-range trajectory.
    New fractional boundary coordinates are drawing geometry only: no source
    timestamp/value is altered or inserted into the underlying observation.
    """
    if (av > gain and bv > gain) or (av < -gain and bv < -gain):
        return None
    if abs(av) <= gain and abs(bv) <= gain:
        return a, av, b, bv
    delta = bv-av
    low, high = sorted(((-gain-av)/delta, (gain-av)/delta))
    enter, leave = max(0.0, low), min(1.0, high)
    if enter > leave:
        return None
    return (a+(b-a)*enter, av+delta*enter,
            a+(b-a)*leave, av+delta*leave)


class Canvas:
    def __init__(self): self.pixels = bytearray(b"\xff" * (WIDTH*HEIGHT*3))
    def pixel(self, x, y, color):
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            offset = 3*(y*WIDTH+x); self.pixels[offset:offset+3] = bytes(color)
    def line(self, x0, y0, x1, y1, color):
        dx, dy = abs(x1-x0), -abs(y1-y0)
        sx, sy = 1 if x0 < x1 else -1, 1 if y0 < y1 else -1
        error = dx+dy
        while True:
            self.pixel(x0, y0, color)
            if x0 == x1 and y0 == y1: break
            twice = 2*error
            if twice >= dy: error += dy; x0 += sx
            if twice <= dx: error += dx; y0 += sy
    def text(self, x, y, text, color=(35, 35, 35), scale=1):
        for character in text.upper():
            require(character in FONT, "unsupported deterministic font glyph")
            for row, bits in enumerate(FONT[character]):
                for column in range(5):
                    if bits & (1 << (4-column)):
                        for a in range(scale):
                            for b in range(scale):
                                self.pixel(x+column*scale+a, y+row*scale+b, color)
            x += 6*scale
    def png(self):
        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind+data))
        raw = b"".join(b"\0" + self.pixels[y*WIDTH*3:(y+1)*WIDTH*3] for y in range(HEIGHT))
        result = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0))
                  + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))
        require(len(result) <= 2097152, "bounded frame encoding exceeded")
        return result


class TraceViewer:
    """Server-side typed window/gain actions; runtime isolation is separate work."""
    def __init__(self, packet, profile):
        validate_packet(packet)
        self.observation_sha256 = validate_profile(packet, profile)
        self._packet, self._profile = copy.deepcopy(packet), copy.deepcopy(profile)
        self.start, self.end, self.gain = -30000, 0, 187.5

    def action(self, command):
        require(type(command) is dict and type(command.get("action")) is str, "typed viewer action required")
        kind = command["action"]
        if kind == "window":
            require(set(command) == {"action", "start_ms", "end_ms"}, "window action fields differ")
            start, end = command["start_ms"], command["end_ms"]
            require(type(start) is int and type(end) is int and
                    -30000 <= start < end <= 0 and 100 <= end-start <= 30000,
                    "window must be100–30000ms inside the observation")
            self.start, self.end = start, end
        elif kind == "gain":
            require(set(command) == {"action", "limit_uv"} and
                    type(command["limit_uv"]) in (int, float) and command["limit_uv"] in GAINS_UV,
                    "gain must be25,50,100or187.5 microvolts")
            self.gain = command["limit_uv"]
        elif kind == "view":
            require(set(command) == {"action"}, "view action fields differ")
        else:
            raise ViewerRefusal("unsupported viewer action")
        return self.render()

    def render(self):
        points, lines, blanks = geometry(self._packet, self.start, self.end)
        canvas = Canvas(); black = (25, 40, 55); orange = (190, 85, 0); gray = (225, 229, 233)
        canvas.text(90, 18, "DOSEI SOURCE EEG - RETROSPECTIVE MARKER WINDOW", scale=2)
        canvas.text(90, 43, "125 HZ NOMINAL SIGNAL / 250 HZ TABLE - OBSERVED POINTS", scale=1)
        def x(t): return LEFT+round((t-self.start)*(RIGHT-LEFT)/(self.end-self.start))
        clipped = [False, False]
        for channel, (top, bottom) in enumerate(PANELS):
            def y(v): return round((top+bottom)/2 - max(-self.gain, min(self.gain, v))*(bottom-top)/(2*self.gain))
            canvas.text(LEFT, top-23, "EEG "+str(channel+1)+" / MICROVOLT", scale=2)
            for value in (-self.gain, 0, self.gain):
                canvas.line(LEFT, y(value), RIGHT, y(value), gray)
                canvas.text(10, y(value)-3, format(value, "g"))
            for part in range(5):
                t = self.start+(self.end-self.start)*part/4
                canvas.line(x(t), top, x(t), bottom, gray)
                label = format(t, "g")
                label_x = max(0, min(WIDTH-6*len(label)-1, x(t)-3*len(label)))
                canvas.text(label_x, bottom+8, label)
            for a, av, b, bv in lines[channel]:
                clipped_segment = clip_display_segment(a, av, b, bv, self.gain)
                if clipped_segment is not None:
                    ca, cav, cb, cbv = clipped_segment
                    canvas.line(x(ca), y(cav), x(cb), y(cbv), black)
            for t, value, flagged in points[channel]:
                color = orange if flagged else black
                px, py = x(t), y(value)
                for offset in (-1, 0, 1):
                    canvas.pixel(px+offset, py, color); canvas.pixel(px, py+offset, color)
                if abs(value) > self.gain:
                    clipped[channel] = True
                    direction = 1 if value > 0 else -1
                    canvas.line(px-2, py+3*direction, px, py, color)
                    canvas.line(px+2, py+3*direction, px, py, color)
            # A separate strip preserves blank positions; it is not a zero trace.
            for t in blanks[channel]: canvas.pixel(x(t), bottom+23, (145, 155, 165))
            canvas.text(LEFT, bottom+32, "MS RELATIVE TO MARKER / GRAY STRIP = BLANK GRID CELLS")
            if clipped[channel]: canvas.text(700, top-14, "CLIPPED AT VIEW GAIN", orange)
        canvas.text(LEFT, 583, "ORANGE = SOURCE ENDPOINT / LINES ARE DISPLAY ONLY")
        canvas.text(LEFT, 599, "NO IMPUTED SAMPLES / PAN AND GAIN DO NOT CHANGE INPUT")
        if not self._packet["coverage"]["full_interval_recorded"]:
            canvas.text(LEFT, 615, "SOURCE PREFIX UNAVAILABLE - NO PADDING", orange)
        receipt = {"schema": "dosei_typed_view_receipt_v1", "case_id": self._packet["case_id"],
                   "observation_sha256": self.observation_sha256, "display_policy": POLICY,
                   "window_ms": [self.start, self.end], "gain_limit_uv": self.gain,
                   "units": "microvolt", "time_units": "millisecond relative to source marker",
                   "clipped_at_view_gain": clipped, "source_values_changed": False,
                   "source_provenance_authenticated_by_renderer": False}
        return canvas.png(), receipt
