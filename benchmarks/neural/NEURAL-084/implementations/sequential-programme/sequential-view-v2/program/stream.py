"""Authenticated opaque NPY row transport; no NumPy or numerical transforms.

The controller injects the reviewed common module as `c`. Public wrappers fix
NEURAL084 production geometry/counts. Private profile arguments exist solely to
exercise transport with tiny invented byte fixtures. No input is read at import.
"""
import ast
from collections import namedtuple
import hashlib
import os
from pathlib import Path
import stat
import sys

ContentPin = namedtuple("ContentPin", "bytes sha256")
SourceDescriptor = namedtuple("SourceDescriptor", "path pin offset shape stamp")
_Profile = namedtuple("_Profile", "phase_shape output_counts")


def _close_all(*descriptors):
    primary = sys.exc_info()[1]
    errors = []
    for descriptor in descriptors:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except BaseException as error:
                errors.append(error)
    if primary is not None:
        for error in errors:
            primary.add_note("Descriptor cleanup also failed: " + type(error).__name__ + ": " + str(error))
    elif len(errors) == 1:
        raise errors[0]
    elif errors:
        raise BaseExceptionGroup("Independent descriptor cleanup failures", errors)


def _sync_dir(path, budget):
    budget.tick()
    fd = os.open(c.path(path), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        budget.tick()
        os.fsync(fd)
        budget.tick()
    finally:
        _close_all(fd)


def _profile(profile):
    c.need(type(profile) is _Profile and type(profile.phase_shape) is tuple
           and len(profile.phase_shape) == 3
           and all(type(value) is int and value > 0 for value in profile.phase_shape),
           "explicit positive three-axis transport profile")
    c.need(type(profile.output_counts) is tuple and profile.output_counts
           and all(type(value) is int and value > 0 for value in profile.output_counts),
           "explicit positive output row counts")
    c.need(profile.phase_shape[0] <= 100 and profile.phase_shape[1] <= 10
           and profile.phase_shape[2] <= 400 and max(profile.output_counts) <= 21200,
           "bounded internal transport geometry")
    return profile


def _production():
    # Literals, not caller-selectable geometry or mutable public count knobs.
    return _Profile((100, 10, 400), (21200, 400))


def _pin(value):
    if type(value) is ContentPin:
        value = dict(bytes=value.bytes, sha256=value.sha256)
    c.exact_pin(value)
    return ContentPin(value["bytes"], value["sha256"])


def _same(fd, path, initial):
    c.need(c.stamp(initial) == c.stamp(os.fstat(fd)) == c.stamp(c.path(path).lstat()),
           "stable complete descriptor and named source identity")


def _start_source(fd, path, expected, budget, required_stamp=None):
    initial = os.fstat(fd)
    c.need(stat.S_ISREG(initial.st_mode) and initial.st_nlink == 1
           and stat.S_IMODE(initial.st_mode) == 0o444 and initial.st_size == expected.bytes,
           "exact readonly single-link source extent")
    c.need(c.stamp(initial) == c.stamp(c.path(path).lstat()), "same opened/named source")
    c.need(required_stamp is None or c.stamp(initial) == required_stamp,
           "same source identity since authentication")
    # Must precede the first source byte read, including its header.
    budget.read(initial.st_size + 1)
    budget.tick()
    return initial


class _Reader:
    def __init__(self, fd, budget, total):
        self.fd = fd
        self.budget = budget
        self.digest = hashlib.sha256()
        self.count = 0
        self.total = total

    def take(self, count):
        c.need(type(count) is int and 0 <= count <= 65536, "bounded retained byte fragment")
        c.need(count <= self.total - self.count, "source fragment inside declared extent")
        parts = []
        remaining = count
        while remaining:
            self.budget.tick()
            chunk = os.read(self.fd, remaining)
            self.budget.tick()
            c.need(chunk, "complete source fragment")
            c.need(len(chunk) <= remaining, "bounded source read result")
            parts.append(chunk)
            remaining -= len(chunk)
            self.count += len(chunk)
            self.digest.update(chunk)
        return b"".join(parts)

    def drain(self, count):
        while count:
            take = min(65536, count)
            self.take(take)
            count -= take

    def finish(self, expected):
        self.budget.tick()
        extra = os.read(self.fd, 1)
        self.budget.tick()
        c.need(not extra and self.count == expected.bytes and self.digest.hexdigest() == expected.sha256,
               "exact full source SHA256 and EOF")


def _parse_header(reader, expected, profile):
    prefix = reader.take(8)
    c.need(prefix[:6] == b"\x93NUMPY" and prefix[6:] in (b"\x01\x00", b"\x02\x00"),
           "bounded NPY1.0 or2.0 container")
    width = 2 if prefix[6:] == b"\x01\x00" else 4
    size = int.from_bytes(reader.take(width), "little")
    c.need(0 < size <= 4096, "bounded NPY header length")
    header = reader.take(size)
    c.need(header.endswith(b"\n"), "newline terminated NPY header")
    try:
        tree = ast.parse(header.decode("ascii").strip(), mode="eval")
        body = tree.body
        c.need(type(body) is ast.Dict and len(body.keys) == 3
               and all(type(key) is ast.Constant and type(key.value) is str for key in body.keys),
               "literal three-field NPY header")
        keys = tuple(key.value for key in body.keys)
        c.need(len(set(keys)) == 3 and set(keys) == {"descr", "fortran_order", "shape"},
               "exact unique NPY header fields")
        value = ast.literal_eval(tree)
    except (UnicodeError, SyntaxError, RecursionError, TypeError) as error:
        raise ValueError("bounded literal NPY header") from error
    c.need(type(value) is dict and value["descr"] == "<f4" and type(value["descr"]) is str
           and value["fortran_order"] is False, "literal little-endian float32 C order")
    shape = value["shape"]
    c.need(type(shape) is tuple and len(shape) == 3 and all(type(n) is int for n in shape)
           and shape == profile.phase_shape, "complete canonical per-phase axes")
    offset = 8 + width + size
    payload = 4 * shape[0] * shape[1] * shape[2]
    c.need(expected.bytes == offset + payload, "exact header plus full phase byte extent")
    return offset, shape


def _authenticate(path, pin, budget, profile):
    profile = _profile(profile)
    expected = _pin(pin)
    c.need(expected.bytes <= 4108 + 4 * profile.phase_shape[0] * profile.phase_shape[1] * profile.phase_shape[2],
           "bounded declared phase extent")
    budget.tick()
    path = c.path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        initial = _start_source(fd, path, expected, budget)
        reader = _Reader(fd, budget, expected.bytes)
        offset, shape = _parse_header(reader, expected, profile)
        reader.drain(expected.bytes - offset)
        reader.finish(expected)
        _same(fd, path, initial)
        budget.tick()
        result = SourceDescriptor(path, expected, offset, shape, c.stamp(initial))
    finally:
        _close_all(fd)
    budget.tick()
    return result


def authenticate(path, pin, budget):
    """Authenticate full canonical100x10x400 source; never decode its samples."""
    return _authenticate(path, pin, budget, _production())


inspect = authenticate


def opaque_hash(path, pin, budget):
    """Authenticate an ordinary readonly opaque file; return its stable stamp."""
    expected = _pin(pin)
    budget.tick()
    path = c.path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        initial = _start_source(fd, path, expected, budget)
        reader = _Reader(fd, budget, expected.bytes)
        reader.drain(expected.bytes)
        reader.finish(expected)
        _same(fd, path, initial)
        budget.tick()
        result = c.stamp(initial)
    finally:
        _close_all(fd)
    budget.tick()
    return result


def _header(shape):
    # Deterministic NPY1.0 header, ASCII literal, 64-byte aligned full prefix.
    literal = ("{'descr': '<f4', 'fortran_order': False, 'shape': " + repr(shape) + ", }").encode("ascii")
    padding = (-(10 + len(literal) + 1)) % 64
    header = literal + b" " * padding + b"\n"
    c.need(len(header) <= 65535, "NPY1 output header extent")
    return b"\x93NUMPY\x01\x00" + len(header).to_bytes(2, "little") + header


def output_size(rows):
    c.need(type(rows) is int and rows in (21200, 400), "complete training or query row count")
    return len(_header((rows, 10, 400))) + rows * 16000


def _pwrite(fd, raw, offset, budget):
    view = memoryview(raw)
    while view:
        budget.tick()
        written = os.pwrite(fd, view, offset)
        budget.tick()
        c.need(type(written) is int and 0 < written <= len(view), "complete positional write progress")
        offset += written
        view = view[written:]


def _pread(fd, count, offset, budget):
    c.need(0 <= count <= 65536, "bounded retained output fragment")
    chunks = []
    remaining = count
    while remaining:
        budget.tick()
        raw = os.pread(fd, remaining, offset)
        budget.tick()
        c.need(raw and len(raw) <= remaining, "complete output fragment")
        chunks.append(raw)
        remaining -= len(raw)
        offset += len(raw)
    return b"".join(chunks)


def _layout(ordered_rows, sources, profile):
    c.need(type(ordered_rows) is tuple and len(ordered_rows) in profile.output_counts,
           "complete ordered output row tuple")
    c.need(type(sources) is tuple and len(sources) * profile.phase_shape[0] == len(ordered_rows),
           "exact selected source count with no unused sources")
    paths = set()
    identities = set()
    positions = []
    for source in sources:
        c.need(type(source) is SourceDescriptor and type(source.stamp) is tuple and len(source.stamp) == 9,
               "immutable authenticated source descriptor")
        c.need(type(source.pin) is ContentPin and all(type(value) is int for value in source.stamp),
               "immutable content pin and plain integer identity stamp")
        c.need(source.shape == profile.phase_shape and type(source.offset) is int and 10 < source.offset <= 4108,
               "descriptor phase axes and bounded header offset")
        expected = _pin(source.pin)
        c.need(expected.bytes == source.offset + 4 * profile.phase_shape[0] * profile.phase_shape[1] * profile.phase_shape[2],
               "descriptor exact complete extent")
        path = c.path(source.path)
        identity = source.stamp[:2]
        c.need(path not in paths and identity not in identities, "distinct selected source paths and inodes")
        paths.add(path)
        identities.add(identity)
        positions.append([-1] * profile.phase_shape[0])
    for destination, pair in enumerate(ordered_rows):
        c.need(type(pair) is tuple and len(pair) == 2 and all(type(value) is int for value in pair),
               "literal source-index and phase-row pair")
        source, row = pair
        c.need(0 <= source < len(sources) and 0 <= row < profile.phase_shape[0], "selected source/row bounds")
        c.need(positions[source][row] == -1, "no repeated source row")
        positions[source][row] = destination
    c.need(all(position >= 0 for rows in positions for position in rows), "every selected phase row exactly once")
    return positions


def _verify_output(fd, output, expected_header, rows, row_bytes, row_hashes, total, budget):
    # Read output once in destination order; compare every row to its source-row
    # digest. Computing only an output pin would not independently catch a bad
    # positional write/mapping. Hash storage is bounded32bytes per output row.
    budget.read(total + 1)
    budget.tick()
    initial = os.fstat(fd)
    c.need(initial.st_size == total and initial.st_nlink == 1 and stat.S_ISREG(initial.st_mode),
           "complete ordinary gathered output extent")
    header = _pread(fd, len(expected_header), 0, budget)
    c.need(header == expected_header, "exact deterministic output header")
    digest = hashlib.sha256(header)
    offset = len(header)
    for row in range(rows):
        raw = _pread(fd, row_bytes, offset, budget)
        c.need(hashlib.sha256(raw).digest() == row_hashes[row * 32:(row + 1) * 32],
               "exact source bytes at each ordered output row")
        digest.update(raw)
        offset += row_bytes
    budget.tick()
    extra = os.pread(fd, 1, total)
    budget.tick()
    c.need(not extra, "no trailing output bytes")
    _same(fd, output, initial)
    return dict(bytes=total, sha256=digest.hexdigest()), c.stamp(initial)


def _gather(output, ordered_rows, sources, budget, profile):
    profile = _profile(profile)
    positions = _layout(ordered_rows, sources, profile)
    row_bytes = 4 * profile.phase_shape[1] * profile.phase_shape[2]
    shape = (len(ordered_rows),) + profile.phase_shape[1:]
    header = _header(shape)
    total = len(header) + len(ordered_rows) * row_bytes
    output = c.path(output)
    c.need(output != budget.root and output.is_relative_to(budget.root)
           and output.parent.is_dir() and not output.exists(), "fresh output inside owned execution root")
    c.need(all(output != source.path for source in sources), "output distinct from all sources")
    # Both the complete output write and physical capacity are selected before
    # output creation. Failed partial files/counters are retained, never refunded.
    budget.capacity(((total + 4095) // 4096) * 4096 + 16384)
    budget.write(total)
    budget.tick()
    out = os.open(output, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    try:
        _pwrite(out, header, 0, budget)
        row_hashes = bytearray(32 * len(ordered_rows))
        for source_index, source in enumerate(sources):
            budget.tick()
            path = c.path(source.path)
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
            try:
                initial = _start_source(fd, path, source.pin, budget, source.stamp)
                reader = _Reader(fd, budget, source.pin.bytes)
                offset, source_shape = _parse_header(reader, source.pin, profile)
                c.need(offset == source.offset and source_shape == source.shape, "same authenticated source header")
                for source_row, destination in enumerate(positions[source_index]):
                    raw = reader.take(row_bytes)
                    row_hashes[destination * 32:(destination + 1) * 32] = hashlib.sha256(raw).digest()
                    _pwrite(out, raw, len(header) + destination * row_bytes, budget)
                reader.finish(source.pin)
                _same(fd, path, initial)
                budget.tick()
            finally:
                _close_all(fd)
        budget.tick()
        os.fchmod(out, 0o444)
        os.fsync(out)
        budget.tick()
        result, verified_stamp = _verify_output(out, output, header, len(ordered_rows), row_bytes, row_hashes, total, budget)
        budget.tick()
        final = os.fstat(out)
        c.need(stat.S_ISREG(final.st_mode) and final.st_nlink == 1 and stat.S_IMODE(final.st_mode) == 0o444
               and final.st_size == total and c.stamp(final) == verified_stamp == c.stamp(output.lstat()),
               "same sealed complete named output")
    finally:
        _close_all(out)
    _sync_dir(output.parent, budget)
    budget.tick()
    return result


def gather(output, ordered_rows, source_descriptors, budget):
    """Gather all212x100 training or4x100 query rows in supplied ID-sorted order.

    The parent binds source/row references to globally sorted opaque IDs. This
    transport verifies complete row coverage and unchanged bytes, not ID labels,
    numerical finiteness, scientific provenance, or model-fit chronology.
    """
    return _gather(output, ordered_rows, source_descriptors, budget, _production())
