"""APCx typed count images and first-final answers; operator-side source only.

The external host owns the episode and this object. The participant receives
only dispatch replies. This module is neither a process sandbox nor a provider
transport, and never opens an owner packet, fits a decoder or computes a score.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
from pathlib import Path
import struct
import types
import zlib

BOUNDARY_SHA256 = "212ffcc52f6a4a76f4e5a052bef107b6369871a79cf9988b2e590215be1eeb74"
SCHEMA = "apcx-typed-count-viewer-v1"
SPLITS = ("calibration", "development", "queries")
CELL_W, CELL_H, LEFT, TOP = 56, 18, 56, 64

# A fixed bitmap font makes exact integer annotations portable. No OS fonts,
# browser JavaScript, image library or signal-specific rescaling is involved.
_GLYPHS = {
    "0": "01110/10001/10011/10101/11001/10001/01110",
    "1": "00100/01100/00100/00100/00100/00100/01110",
    "2": "01110/10001/00001/00010/00100/01000/11111",
    "3": "11110/00001/00001/01110/00001/00001/11110",
    "4": "00010/00110/01010/10010/11111/00010/00010",
    "5": "11111/10000/10000/11110/00001/00001/11110",
    "6": "01110/10000/10000/11110/10001/10001/01110",
    "7": "11111/00001/00010/00100/01000/01000/01000",
    "8": "01110/10001/10001/01110/10001/10001/01110",
    "9": "01110/10001/10001/01111/00001/00001/01110",
    "A": "01110/10001/10001/11111/10001/10001/10001",
    "B": "11110/10001/10001/11110/10001/10001/11110",
    "C": "01111/10000/10000/10000/10000/10000/01111",
    "D": "11110/10001/10001/10001/10001/10001/11110",
    "E": "11111/10000/10000/11110/10000/10000/11111",
    "F": "11111/10000/10000/11110/10000/10000/10000",
    "G": "01111/10000/10000/10111/10001/10001/01111",
    "H": "10001/10001/10001/11111/10001/10001/10001",
    "I": "01110/00100/00100/00100/00100/00100/01110",
    "J": "00111/00010/00010/00010/10010/10010/01100",
    "K": "10001/10010/10100/11000/10100/10010/10001",
    "L": "10000/10000/10000/10000/10000/10000/11111",
    "M": "10001/11011/10101/10101/10001/10001/10001",
    "N": "10001/11001/10101/10011/10001/10001/10001",
    "O": "01110/10001/10001/10001/10001/10001/01110",
    "P": "11110/10001/10001/11110/10000/10000/10000",
    "Q": "01110/10001/10001/10001/10101/10010/01101",
    "R": "11110/10001/10001/11110/10100/10010/10001",
    "S": "01111/10000/10000/01110/00001/00001/11110",
    "T": "11111/00100/00100/00100/00100/00100/00100",
    "U": "10001/10001/10001/10001/10001/10001/01110",
    "V": "10001/10001/10001/10001/10001/01010/00100",
    "W": "10001/10001/10001/10101/10101/10101/01010",
    "X": "10001/10001/01010/00100/01010/10001/10001",
    "Y": "10001/10001/01010/00100/00100/00100/00100",
    "Z": "11111/00001/00010/00100/01000/10000/11111",
    "[": "01110/01000/01000/01000/01000/01000/01110",
    "]": "01110/00010/00010/00010/00010/00010/01110",
    "(": "00010/00100/01000/01000/01000/00100/00010",
    ")": "01000/00100/00010/00010/00010/00100/01000",
    "=": "00000/00000/11111/00000/11111/00000/00000",
    ",": "00000/00000/00000/00000/00110/00110/00100",
    "-": "00000/00000/00000/11111/00000/00000/00000",
    "/": "00001/00001/00010/00100/01000/10000/10000",
    " ": "00000/00000/00000/00000/00000/00000/00000",
}


def _canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _closed(value, fields):
    _need(type(value) is dict and set(value) == set(fields), "closed typed action schema")


def _boundary(directory=None):
    directory = Path(directory) if directory is not None else Path(__file__).resolve().parent.parent / "deposited-label"
    path = directory / "episode_boundary.py"
    data = path.read_bytes()
    _need(len(data) == 5486 and _sha(data) == BOUNDARY_SHA256, "pinned APCx episode boundary")
    module = types.ModuleType("apcx_pinned_episode_boundary")
    # Execute the bytes just hashed, rather than reopening a possibly replaced file.
    exec(compile(data, str(path), "exec"), module.__dict__)
    return module


def _chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def _png(matrix, unit_start, bin_start, label):
    """Fixed-scale grayscale heatmap with every exact integer visibly printed."""
    width = max(480, LEFT + CELL_W * len(matrix[0]) + 8)
    height = TOP + CELL_H * len(matrix) + 12
    pixels = bytearray([255]) * (width * height)

    def rect(x, y, w, h, gray):
        for yy in range(y, y + h):
            pixels[yy * width + x:yy * width + x + w] = bytes([gray]) * w

    def text(x, y, value, gray=0):
        for char in value:
            glyph = _GLYPHS[char]
            for yy, line in enumerate(glyph.split("/")):
                for xx, bit in enumerate(line):
                    if bit == "1" and 0 <= x + xx < width and 0 <= y + yy < height:
                        pixels[(y + yy) * width + x + xx] = gray
            x += 6

    text(8, 5, "APCX EXACT SPIKE COUNTS / 50MS")
    text(8, 17, label)
    text(8, 29, "FIXED LOG2 GRAY SCALE - COUNTS PRINTED EXACTLY")
    text(8, 41, "TIME MS - [500,5000) OBSERVED - NO FIRST 500MS")
    for col in range(len(matrix[0])):
        text(LEFT + col * CELL_W + 3, TOP - 11, str(500 + 50 * (bin_start + col)))
    for row, counts in enumerate(matrix):
        text(3, TOP + row * CELL_H + 5, "U" + str(unit_start + row))
        for col, count in enumerate(counts):
            x, y = LEFT + col * CELL_W, TOP + row * CELL_H
            gray = 255 - min(224, 16 * count.bit_length())
            rect(x, y, CELL_W - 1, CELL_H - 1, gray)
            # Int32 needs at most10 decimal digits within the fixed56px cell.
            digits = str(count)
            # Use a5px glyph advance for10-digit counts, preserving all digits.
            if len(digits) == 10:
                for idx, digit in enumerate(digits):
                    text(x + 2 + idx * 5, y + 5, digit, 255 if gray < 128 else 0)
            else:
                text(x + 2, y + 5, digits, 255 if gray < 128 else 0)
    scan = b"".join(b"\0" + pixels[y * width:(y + 1) * width] for y in range(height))
    data = (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(scan, 6)) + _chunk(b"IEND", b""))
    return data, width, height


class Session:
    """One operator-owned session/condition. Dispatch is the participant API."""

    def __init__(self, episode, expected_episode_sha256, *, boundary_directory=None):
        self._boundary = _boundary(boundary_directory)
        payload = _canonical(episode)
        _need(len(payload) <= self._boundary.MAX_EPISODE_BYTES, "bounded complete episode")
        _need(type(expected_episode_sha256) is str and _sha(payload) == expected_episode_sha256,
              "externally pinned episode identity")
        # Detach caller-owned mutable containers before validating or rendering.
        self._episode = json.loads(payload)
        self._boundary.validate_episode(self._episode)
        self.episode_sha256 = expected_episode_sha256
        self._session = self._episode["session"]
        self._rows = {split: {row["case_id"]: row for row in self._session[split]} for split in SPLITS}
        self._answers = {}
        self._closed = False
        self._events = []
        self._root = _sha(_canonical({"schema": SCHEMA, "episode_sha256": expected_episode_sha256,
                                     "boundary_sha256": BOUNDARY_SHA256}))

    def _record(self, request, response):
        # Only reply digests are retained: repeated large images do not accumulate.
        event = {"sequence": len(self._events), "previous_sha256": self._root,
                 "request": json.loads(_canonical(request)), "response_sha256": _sha(_canonical(response))}
        self._root = _sha(_canonical(event))
        self._events.append({**event, "event_sha256": self._root})
        return response

    def dispatch(self, request):
        """Closed describe/view/answer/finish actions; no code/path/owner access."""
        _need(not self._closed, "session already finalized")
        _need(type(request) is dict and type(request.get("action")) is str, "typed action object")
        action = request["action"]
        if action == "describe":
            _closed(request, ("action",))
            reply = {"schema": SCHEMA, "condition": self._episode["condition"],
                     "session_id": self._session["session_id"], "episode_sha256": self.episode_sha256,
                     "documentation_utf8": self._episode["documentation_utf8"],
                     "unit_count": len(self._session["channel_ids"]), "bins": 90,
                     "bin_width_ms": 50, "observed_interval_ms": [500, 5000],
                     "case_ids": {split: list(self._rows[split]) for split in SPLITS},
                     "answer_target": "deposited_Total_pulse_label",
                     "support_views_optional": True}
        elif action == "view":
            _closed(request, ("action", "split", "case_id", "unit_start", "unit_stop", "bin_start", "bin_stop"))
            split, cid = request["split"], request["case_id"]
            _need(type(split) is str and split in SPLITS and type(cid) is str and cid in self._rows[split],
                  "case belongs to selected split and episode")
            us, ue, bs, be = (request[k] for k in ("unit_start", "unit_stop", "bin_start", "bin_stop"))
            _need(all(type(v) is int for v in (us, ue, bs, be)), "exact integer viewport")
            _need(0 <= us < ue <= len(self._session["channel_ids"]) and 0 <= bs < be <= 90,
                  "nonempty viewport inside complete observed support")
            row = self._rows[split][cid]
            support = None if split == "queries" else {"count": row["count"], "high": row["high"]}
            label = "QUERY - NO TARGET" if support is None else split.upper() + " COUNT=" + str(support["count"]) + " HIGH=" + str(support["high"])
            data, width, height = _png([v[bs:be] for v in row["spikes"][us:ue]], us, bs, label)
            reply = {"schema": "apcx-count-image-v1", "media_type": "image/png",
                     "png_base64": base64.b64encode(data).decode("ascii"), "png_sha256": _sha(data),
                     "width": width, "height": height, "split": split, "case_id": cid,
                     "unit_indices": [us, ue], "bin_indices": [bs, be],
                     "half_open_interval_ms": [500 + 50 * bs, 500 + 50 * be],
                     "support_label": support, "counts_rendered_exactly": True}
        elif action == "answer":
            _closed(request, ("action", "case_id", "count"))
            cid, value = request["case_id"], request["count"]
            _need(type(cid) is str and cid in self._rows["queries"] and cid not in self._answers,
                  "expected unanswered query; first-final answers cannot change")
            try:
                valid = type(value) in (int, float) and math.isfinite(value)
            except (OverflowError, ValueError):
                valid = False
            _need(valid, "finite numeric prediction, not boolean")
            self._answers[cid] = value
            reply = {"schema": "apcx-answer-accepted-v1", "case_id": cid,
                     "count": value, "remaining_queries": len(self._rows["queries"]) - len(self._answers)}
        elif action == "finish":
            _closed(request, ("action",))
            records = [{"case_id": cid, "count": self._answers[cid]}
                       for cid in self._rows["queries"] if cid in self._answers]
            self._boundary.validate_candidate_records(self._episode, records)
            response = {"schema": "apcx-candidate-session-result-v1", "profile": self._episode["profile"],
                        "condition": self._episode["condition"], "session_id": self._session["session_id"],
                        "participant_packet_sha256": self._episode["participant_packet_sha256"],
                        "episode_sha256": self.episode_sha256, "records": records}
            reply = {"schema": "apcx-viewer-finish-v1", "response": response,
                     "response_sha256": _sha(_canonical(response)),
                     "prior_action_chain_sha256": self._root,
                     "scientific_qualification": False, "process_isolation_verified": False}
            self._closed = True
        else:
            raise ValueError("unknown typed action")
        return self._record(request, reply)

    def operator_audit(self):
        """Operator-only snapshot, never a substitute for an external transcript."""
        return json.loads(_canonical({"schema": "apcx-viewer-action-audit-v1",
                                      "episode_sha256": self.episode_sha256,
                                      "closed": self._closed, "events": self._events,
                                      "final_chain_sha256": self._root,
                                      "rejected_actions_recorded": False,
                                      "external_process_isolation_verified": False}))
