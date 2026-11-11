"""Strict, standard-library-only length-prefixed JSON objects.

The unsigned four-byte big-endian prefix counts UTF-8 body bytes. Limits are
explicit and apply to each body. A decoder retains only the current prefix or
body, not the entire input chunk. Returned objects can of course occupy memory
proportional to the number and content of complete frames in a feed call.

Invalid wire data permanently fails a decoder. No objects from a feed call that
raises are returned, including complete frames preceding the invalid frame.
This codec supplies framing checks; it does not establish process containment.
"""

from collections.abc import Mapping
import json
import math


class FrameError(ValueError):
    """Invalid frame, JSON value, stream state, or frame-size limit."""


def _check_limit(max_frame_bytes):
    if type(max_frame_bytes) is not int or not 1 <= max_frame_bytes <= 0xFFFFFFFF:
        raise FrameError("max_frame_bytes must be an integer in 1..2**32-1")
    return max_frame_bytes


def _check_value(value, active=None):
    """Reject key coercion, nonfinite numbers, cycles, and lone surrogates."""
    if isinstance(value, str):
        value.encode("utf-8", errors="strict")
    elif value is None or isinstance(value, (bool, int)):
        return
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise FrameError("nonfinite JSON number")
    elif isinstance(value, (dict, list, tuple)):
        active = set() if active is None else active
        identity = id(value)
        if identity in active:
            raise FrameError("cyclic JSON value")
        active.add(identity)
        try:
            if isinstance(value, dict):
                for key, item in value.items():
                    if not isinstance(key, str):
                        raise FrameError("JSON object keys must be strings")
                    _check_value(key, active)
                    _check_value(item, active)
            else:
                for item in value:
                    _check_value(item, active)
        finally:
            active.remove(identity)
    else:
        raise FrameError("unsupported JSON value type")


def _pairs_to_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise FrameError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_constant(_value):
    raise FrameError("nonfinite JSON number")


def _decode_body(body):
    try:
        value = json.loads(
            body.decode("utf-8", errors="strict"),
            object_pairs_hook=_pairs_to_object,
            parse_constant=_reject_constant,
        )
        if not isinstance(value, dict):
            raise FrameError("JSON frame must contain an object")
        _check_value(value)
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise FrameError("invalid JSON frame") from exc


def encode_frame(mapping, max_frame_bytes):
    """Encode a mapping as one frame; nested values use ordinary JSON types.

    Nested dictionaries must have string keys. Tuples encode as JSON arrays.
    No implicit/default limit is provided. Invalid values raise FrameError.
    """
    limit = _check_limit(max_frame_bytes)
    if not isinstance(mapping, Mapping):
        raise FrameError("JSON frame must contain a mapping")
    try:
        value = dict(mapping)
        _check_value(value)
        body = json.dumps(
            value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode("utf-8", errors="strict")
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise FrameError("cannot encode JSON frame") from exc
    if len(body) > limit:
        raise FrameError("JSON frame exceeds max_frame_bytes")
    return len(body).to_bytes(4, "big") + body


class FrameDecoder:
    """Incremental object decoder with terminal failure and explicit EOF."""

    def __init__(self, max_frame_bytes):
        self.max_frame_bytes = _check_limit(max_frame_bytes)
        self._prefix = bytearray()
        self._body = bytearray()
        self._expected = None
        self._failed = False
        self._finished = False

    @property
    def buffered_bytes(self):
        """Pending wire bytes, at most max(max_frame_bytes, 3) on return."""
        return len(self._prefix) + len(self._body)

    def _fail(self, message):
        self._failed = True
        self._prefix.clear()
        self._body.clear()
        self._expected = None
        raise FrameError(message)

    def feed(self, data):
        """Consume bytes and return all complete objects; reject invalid frames."""
        if self._failed:
            raise FrameError("decoder has failed")
        if self._finished:
            raise FrameError("decoder is finished")
        if not isinstance(data, bytes):
            raise TypeError("feed requires bytes")
        view = memoryview(data)
        offset = 0
        completed = []
        while offset < len(view):
            if self._expected is None:
                count = min(4 - len(self._prefix), len(view) - offset)
                self._prefix.extend(view[offset:offset + count])
                offset += count
                if len(self._prefix) < 4:
                    break
                size = int.from_bytes(self._prefix, "big")
                self._prefix.clear()
                if size == 0:
                    self._fail("zero-length JSON frame")
                if size > self.max_frame_bytes:
                    self._fail("JSON frame exceeds max_frame_bytes")
                self._expected = size
            count = min(self._expected - len(self._body), len(view) - offset)
            self._body.extend(view[offset:offset + count])
            offset += count
            if len(self._body) == self._expected:
                body = bytes(self._body)
                self._body.clear()
                self._expected = None
                try:
                    completed.append(_decode_body(body))
                except FrameError:
                    self._fail("invalid JSON frame")
        return completed

    def finish(self):
        """Mark EOF; reject incomplete prefix/body. Successful EOF is idempotent."""
        if self._failed:
            raise FrameError("decoder has failed")
        if self._prefix or self._expected is not None:
            self._fail("incomplete frame at EOF")
        self._finished = True
