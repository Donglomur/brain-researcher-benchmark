"""MorseEEG PNG view kernel and immutable per-fold response collection.

Trusted operator component, not a participant transport or process sandbox.
Inputs are the existing public fold manifests and exact canonical window pins;
no inverse, private target table or authentic data are read at import time.
"""
from collections import Counter
import hashlib
import json
import math
import re
import struct
import zlib

SOURCE_COMMIT = "d2e09f610d267b8b3679997f8bc4e52fe6ca402a"
REPRESENTATION = "float32-le-c-order-62x301-v1"
CHANNELS, SAMPLES, RATE, CLASSES = 62, 301, 600, 26
WINDOW_BYTES = CHANNELS * SAMPLES * 4
TRAINING, QUERY = 9672, 312
CELLS = tuple(f"{task}/{speed}" for task in ("dotcount", "firstlast")
              for speed in ("15CPM", "30CPM", "40CPM"))
# Common EEG gains plus fixed powers of two spanning every finite float32
# magnitude. Even extreme finite inputs can be inspected without autoscaling.
GAINS_UV = tuple(sorted({0.5, 1, 2, 5, 10, 20, 50, 100, 200}
                       | {2.0 ** power for power in range(-149, 129)}))
WIDTH, LEFT, RIGHT, TOP, ROW_HEIGHT = 1000, 48, 952, 16, 96


class ViewerError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise ViewerError(message)


def _id(value):
    _require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
             "opaque64hex identity required")
    return value


def _integer(value, low, high, name):
    _require(type(value) is int and low <= value <= high, name)
    return value


def _json_bytes(document):
    return (json.dumps(document, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def _manifest(body, role):
    _require(type(body) is bytes and 0 < len(body) <= 4 * 2**20,
             "bounded immutable public manifest required")

    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "duplicate manifest key")
            result[key] = value
        return result

    def constant(_):
        raise ViewerError("nonfinite JSON constant")

    try:
        value = json.loads(body, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError) as exc:
        raise ViewerError("invalid public manifest") from exc
    _require(type(value) is dict and set(value) == {"role", "representation", "rows"}
             and value["role"] == role and value["representation"] == REPRESENTATION,
             "public manifest role/representation boundary")
    rows = value["rows"]
    _require(type(rows) is list and len(rows) == (TRAINING if role == "training" else QUERY),
             "complete full-fold public row count required")
    expected = {"id", "cell", "group", "label"} if role == "training" else {"id", "cell"}
    seen, counts, groups = set(), Counter(), set()
    for row in rows:
        _require(type(row) is dict and set(row) == expected, "public row field boundary")
        alias = _id(row["id"])
        _require(alias not in seen and row["cell"] in CELLS, "duplicate alias or unknown cell")
        seen.add(alias)
        if role == "training":
            group = _id(row["group"])
            groups.add(group)
            label = _integer(row["label"], 0, CLASSES - 1, "training label")
            counts[group, row["cell"], label] += 1
        else:
            counts[row["cell"]] += 1
    _require([row["id"] for row in rows] == sorted(seen), "existing opaque alias order required")
    if role == "training":
        _require(len(groups) == 31 and set(counts) == {
            (group, cell, label) for group in groups for cell in CELLS for label in range(CLASSES)
        } and set(counts.values()) == {2}, "complete31-group/six-cell/26-class/two-repeat training support")
    else:
        _require(set(counts) == set(CELLS) and set(counts.values()) == {52},
                 "complete six-cell query support required")
    return tuple(rows)


def _chunk(kind, body):
    return (struct.pack(">I", len(body)) + kind + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xffffffff))


def _png(values, channels, first, stop, gain):
    """Render every selected sample; no filtering, resampling or autoscaling."""
    height = TOP * 2 + len(channels) * ROW_HEIGHT
    pixels = bytearray(b"\xff" * (WIDTH * height * 3))

    def pixel(x, y, color):
        if 0 <= x < WIDTH and 0 <= y < height:
            at = (y * WIDTH + x) * 3
            pixels[at:at + 3] = color

    def line(x0, y0, x1, y1, color):
        dx, sx = abs(x1 - x0), 1 if x0 < x1 else -1
        dy, sy = -abs(y1 - y0), 1 if y0 < y1 else -1
        error = dx + dy
        while True:
            pixel(x0, y0, color)
            if x0 == x1 and y0 == y1:
                return
            twice = 2 * error
            if twice >= dy:
                error += dy
                x0 += sx
            if twice <= dx:
                error += dx
                y0 += sy

    for position, channel in enumerate(channels):
        center = TOP + position * ROW_HEIGHT + ROW_HEIGHT // 2
        low, high = center - 40, center + 40
        for offset in (-24, 0, 24):
            line(LEFT, center + offset, RIGHT, center + offset,
                 b"\xc6\xdc\xee" if offset == 0 else b"\xe8\xe8\xe8")
        for tick in range(5):
            x = LEFT + round((RIGHT - LEFT) * tick / 4)
            line(x, low, x, high, b"\xe8\xe8\xe8")
        previous = None
        for sample in range(first, stop):
            x = LEFT + round((sample - first) * (RIGHT - LEFT) / (stop - first - 1))
            raw_y = center - values[channel * SAMPLES + sample] * 24 / gain
            clipped = raw_y < low or raw_y > high
            y = round(max(low, min(high, raw_y)))
            if previous is not None:
                line(previous[0], previous[1], x, y, b"\x18\x18\x18")
            if clipped:
                line(x, y - 2, x, y + 2, b"\xdc\x22\x22")
            previous = (x, y)
    stride = WIDTH * 3
    scanlines = b"".join(b"\x00" + pixels[y * stride:(y + 1) * stride] for y in range(height))
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", struct.pack(">IIBBBBB", WIDTH, height, 8, 2, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(scanlines, level=6)) + _chunk(b"IEND", b""))


class FoldViewer:
    """Host-owned one-fold session. Do not give this object to participant code.

    The callback accepts only a validated opaque alias and returns immutable
    canonical bytes. It must be supplied by a separately qualified operator.
    These API restrictions do not isolate the caller's filesystem or process.
    """
    def __init__(self, training_manifest, query_manifest, window_pins, certificate, read_window):
        self._rows = {"training": _manifest(training_manifest, "training"),
                      "query": _manifest(query_manifest, "query")}
        self._lookup = {role: {row["id"]: row for row in rows} for role, rows in self._rows.items()}
        aliases = set(self._lookup["training"]) | set(self._lookup["query"])
        _require(len(aliases) == TRAINING + QUERY, "training/query identities must be disjoint")
        _require(type(window_pins) is dict and set(window_pins) == aliases,
                 "exact full-fold window pins required")
        self._pins = {}
        for alias, pin in window_pins.items():
            _require(type(pin) is dict and set(pin) == {"bytes", "sha256"}
                     and type(pin["bytes"]) is int and pin["bytes"] == WINDOW_BYTES,
                     "canonical window extent/pin schema")
            self._pins[alias] = _id(pin["sha256"])
        expected = {"source_commit", "sampling_hz", "units", "channel_names", "policy", "bad_channel_policy"}
        _require(type(certificate) is dict and set(certificate) == expected
                 and certificate["source_commit"] == SOURCE_COMMIT
                 and type(certificate["sampling_hz"]) is int and certificate["sampling_hz"] == RATE
                 and certificate["units"] == "uV" and certificate["policy"] == "raw_fixed_window_v1"
                 and certificate["bad_channel_policy"] == "global_zero_PO4_TP8_before_average_reference",
                 "explicit existing fixed-window certificate required")
        names = certificate["channel_names"]
        _require(type(names) is list and len(names) == CHANNELS
                 and all(type(name) is str and 0 < len(name) <= 32
                         and all(32 <= ord(char) <= 126 for char in name) for name in names)
                 and len(set(names)) == CHANNELS and "PO4" in names and "TP8" in names,
                 "explicit unique printable62-channel order required")
        self._names = tuple(names)
        self._removed = (names.index("PO4"), names.index("TP8"))
        _require(callable(read_window), "trusted window callback required")
        self._read_window = read_window
        self._answers = {}
        self._closed = False

    def _open(self):
        _require(not self._closed, "session already finalized")

    def index(self, role, offset, limit):
        """Page the already-public aliases/context; calibration remains optional."""
        self._open()
        _require(type(role) is str and role in self._rows, "unknown public role")
        _integer(offset, 0, len(self._rows[role]), "index offset")
        _integer(limit, 1, 52, "index page limit")
        return [dict(row) for row in self._rows[role][offset:offset + limit]]

    def view(self, request):
        self._open()
        keys = {"role", "id", "channel_start", "channel_count", "sample_start", "sample_stop", "uv_per_division"}
        _require(type(request) is dict and set(request) == keys, "typed view request schema")
        role, alias = request["role"], _id(request["id"])
        _require(type(role) is str and role in self._lookup and alias in self._lookup[role],
                 "unknown alias or wrong role")
        start = _integer(request["channel_start"], 0, CHANNELS - 1, "channel start")
        count = _integer(request["channel_count"], 1, 8, "channel count")
        _require(start + count <= CHANNELS, "channel range")
        first = _integer(request["sample_start"], 0, SAMPLES - 2, "sample start")
        stop = _integer(request["sample_stop"], first + 2, SAMPLES, "sample stop")
        gain = request["uv_per_division"]
        _require(type(gain) in (int, float) and gain in GAINS_UV, "fixed microvolt gain choice")
        # Validate the entire exact snapshot before returning any image.
        body = self._read_window(alias)
        _require(type(body) is bytes and len(body) == WINDOW_BYTES
                 and hashlib.sha256(body).hexdigest() == self._pins[alias],
                 "window snapshot identity differs")
        values = struct.unpack("<" + str(CHANNELS * SAMPLES) + "f", body)
        _require(all(math.isfinite(value) for value in values), "nonfinite canonical window")
        _require(all(value == 0 for channel in self._removed
                     for value in values[channel * SAMPLES:(channel + 1) * SAMPLES]),
                 "fixed damaged-channel zero policy differs")
        channels = tuple(range(start, start + count))
        metadata = dict(self._lookup[role][alias])
        metadata.update(role=role, channels=[{"slot": ch, "name": self._names[ch]} for ch in channels],
                        sample_start=first, sample_stop=stop, sampling_hz=RATE,
                        time_origin="software marker; not authenticated acoustic onset",
                        time_start_ms=first * 1000 / RATE, time_last_ms=(stop - 1) * 1000 / RATE,
                        units="uV", uv_per_division=gain,
                        rendering={"horizontal_divisions": 4, "pixels_per_vertical_division": 24,
                                   "channel_row_pixels": ROW_HEIGHT, "clipping": "red marks at trace boundary",
                                   "filtering": "none", "resampling": "none", "autoscaling": False})
        return {"mime_type": "image/png", "image": _png(values, channels, first, stop, gain),
                "metadata": metadata}

    def answer(self, response):
        self._open()
        _require(type(response) is dict and set(response) == {"id", "probabilities"}, "answer schema")
        alias = _id(response["id"])
        _require(alias in self._lookup["query"] and alias not in self._answers,
                 "unknown or already-final query answer")
        probabilities = response["probabilities"]
        _require(type(probabilities) is list and len(probabilities) == CLASSES
                 and all(type(value) in (int, float) and 0 <= value <= 1
                         and math.isfinite(value) for value in probabilities)
                 and abs(math.fsum(probabilities) - 1) <= 1e-6,
                 "26 finite probabilities on the existing simplex required")
        self._answers[alias] = tuple(float(value) for value in probabilities)
        return {"id": alias, "accepted": True, "remaining": QUERY - len(self._answers)}

    def finish(self):
        self._open()
        _require(set(self._answers) == set(self._lookup["query"]), "all312 query answers required")
        rows = [{"id": alias, "probabilities": list(self._answers[alias])}
                for alias in sorted(self._answers)]
        body = _json_bytes(rows)
        self._closed = True
        return {"predictions": rows, "prediction_sha256": hashlib.sha256(body).hexdigest(),
                "prediction_bytes": len(body), "count": QUERY, "scientific_qualification": False}
