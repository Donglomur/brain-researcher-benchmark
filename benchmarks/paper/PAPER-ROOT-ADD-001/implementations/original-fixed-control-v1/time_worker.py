"""Fixed time-only engineering control; no learned or response-dependent state.

The caller supplies the complete public time-index vector for exactly one job.
This module neither opens files nor receives features, qids, or response labels.
It is a trusted fixed programme, not a sandbox or an arbitrary-candidate runner.
"""

import struct
import sys


MAGIC = b"LNGTIME1"
MIN_COUNT = 2
MAX_COUNT = 144111
MAX_TIME = 144110
FRAME_HEADER_BYTES = 16
NPY_HEADER_BYTES = 128
MAX_FRAME_BYTES = FRAME_HEADER_BYTES + 8 * MAX_COUNT
MAX_OUTPUT_BYTES = NPY_HEADER_BYTES + 8 * MAX_COUNT
READ_CHUNK_BYTES = 65536
FAILURE_STDERR = b"time-only control: invalid input or I/O failure\n"


class InvalidInput(ValueError):
    """The bounded primitive input contract was not satisfied."""


def _read_exact(stream, count):
    """Bound each requested read; never use unbounded read or decode early."""
    if type(count) is not int or not 0 <= count <= MAX_FRAME_BYTES:
        raise InvalidInput("read extent")
    chunks = []
    remaining = count
    while remaining:
        requested = min(remaining, READ_CHUNK_BYTES)
        chunk = stream.read(requested)
        if type(chunk) is not bytes or not 0 < len(chunk) <= requested:
            raise InvalidInput("short or invalid read")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _validate_times(times):
    # A finite concrete tuple avoids consuming an unbounded caller iterator.
    if type(times) is not tuple or not MIN_COUNT <= len(times) <= MAX_COUNT:
        raise InvalidInput("time count")
    previous = -1
    for value in times:
        if type(value) is not int or not previous < value <= MAX_TIME:
            raise InvalidInput("time domain or strict ordering")
        previous = value
    return times


def read_frame(stream):
    """Read one exact frame, preserving the sorted source time coordinates.

    The stream is allowed to return short reads. A validated count determines
    the maximum payload read before any signed-i64 decoding. The final single
    byte probe rejects all trailing content; no bytes beyond that are read.
    """
    header = _read_exact(stream, FRAME_HEADER_BYTES)
    magic, count = struct.unpack("<8sQ", header)
    if magic != MAGIC or not MIN_COUNT <= count <= MAX_COUNT:
        raise InvalidInput("frame header")
    payload_bytes = 8 * count
    if FRAME_HEADER_BYTES + payload_bytes > MAX_FRAME_BYTES:
        raise InvalidInput("frame cap")
    payload = _read_exact(stream, payload_bytes)
    probe = stream.read(1)
    if type(probe) is not bytes or probe != b"":
        raise InvalidInput("trailing bytes")
    times = tuple(item[0] for item in struct.iter_unpack("<q", payload))
    return _validate_times(times)


def encode_prediction(times):
    """Return canonical NPY1.0 bytes for the fixed dyadic (N,1) output.

    This pure helper revalidates its tuple rather than trusting read_frame was
    called. Each result is exactly representable in IEEE754 binary64.
    """
    times = _validate_times(times)
    count = len(times)
    extent = NPY_HEADER_BYTES + 8 * count
    if extent > MAX_OUTPUT_BYTES:
        raise InvalidInput("output cap")
    dictionary = ("{'descr': '<f8', 'fortran_order': False, 'shape': (%d, 1), }" % count).encode("ascii")
    padding = NPY_HEADER_BYTES - 10 - len(dictionary) - 1
    if padding < 0:
        raise InvalidInput("NPY header extent")
    header = dictionary + b" " * padding + b"\n"
    out = bytearray(extent)
    out[:10] = b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header))
    out[10:NPY_HEADER_BYTES] = header
    for index, value in enumerate(times):
        struct.pack_into("<d", out, NPY_HEADER_BYTES + 8 * index, (value % 17 - 8) / 8)
    return bytes(out)


def _write_all(stream, raw):
    view = memoryview(raw)
    position = 0
    while position < len(view):
        wrote = stream.write(view[position:])
        if type(wrote) is not int or not 0 < wrote <= len(view) - position:
            raise OSError("short or invalid write")
        position += wrote


def run(stdin_binary, stdout_binary, stderr_binary):
    """Return 0 on success or 2 on failure; stdout contains only raw NPY.

    Invalid framing is fully rejected before the first stdout write. An output
    transport failure can leave a partial NPY, so callers must require success
    and exact output extent. Failure text has one fixed bounded byte string.
    """
    try:
        raw = encode_prediction(read_frame(stdin_binary))
        _write_all(stdout_binary, raw)
        return 0
    except (InvalidInput, OSError, ValueError, TypeError, OverflowError):
        try:
            _write_all(stderr_binary, FAILURE_STDERR)
        except (OSError, ValueError, TypeError):
            pass
        return 2


if __name__ == "__main__":
    raise SystemExit(run(sys.stdin.buffer, sys.stdout.buffer, sys.stderr.buffer))
