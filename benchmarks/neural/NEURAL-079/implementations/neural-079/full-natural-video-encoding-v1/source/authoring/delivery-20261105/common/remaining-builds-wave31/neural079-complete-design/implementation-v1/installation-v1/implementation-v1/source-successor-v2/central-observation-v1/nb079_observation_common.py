"""Typed-resource primitives. No target access or deployment at import time."""
import hashlib
import json
import math
import os
import stat
import struct
import time


class ResourceRefusal(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ResourceRefusal(message)


def integer(value, minimum=0):
    require(type(value) is int and value >= minimum, 'exact nonnegative integer')
    return value


def fields(value, names, label):
    require(type(value) is dict and set(value) == set(names), label)
    return value


def body_pin(raw):
    require(type(raw) is bytes, 'exact byte body')
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def check_pin(value):
    fields(value, ('bytes', 'sha256'), 'exact pin')
    integer(value['bytes'])
    require(type(value['sha256']) is str and len(value['sha256']) == 64 and
            all(c in '0123456789abcdef' for c in value['sha256']), 'sha256')
    return value


def token(value):
    require(type(value) is str and value and len(value) <= 256 and
            all(c.isascii() and (c.isalnum() or c in '-_.') for c in value), 'source-owned token')
    return value


def attach_secondary(primary, secondary, phase):
    try:
        errors = list(getattr(primary, 'typed_secondary_errors', []))
        errors.append({'phase': str(phase)[:192], 'type': type(secondary).__name__})
        primary.typed_secondary_errors = errors
    except BaseException:
        try:
            primary.add_note('Secondary typed cleanup failure: ' + str(phase)[:192])
        except BaseException:
            pass


def collect_errors(operations, primary=None):
    """Attempt every owned action; return first plus ordered secondary errors."""
    first = primary
    for phase, operation in operations:
        try:
            operation()
        except BaseException as error:
            if first is None:
                first = error
            else:
                attach_secondary(first, error, phase)
    return first


def close_all(operations, primary=None):
    first = collect_errors(operations, primary)
    if primary is None and first is not None:
        raise first


def encoding_limits(value):
    fields(value, ('bytes', 'nodes', 'depth', 'string_chars'), 'explicit bounded encoding limits')
    for x in value.values():
        integer(x, 1)
    return value


def bounded_encode(value, limits):
    """Canonical ASCII JSON with output growth checked before every append.

    Unlike iterencode, this does not materialize an entire escaped long string
    before checking its output extent. Existing caller-owned objects are not
    claimed to have been allocated under these serializer bounds.
    """
    encoding_limits(limits)
    out = bytearray()
    nodes = 0

    def emit(block):
        require(len(out) + len(block) <= limits['bytes'], 'encoded byte ceiling')
        out.extend(block)

    def string(text):
        require(type(text) is str and len(text) <= limits['string_chars'], 'string ceiling')
        emit(b'"')
        escapes = {8: b'\\b', 9: b'\\t', 10: b'\\n', 12: b'\\f', 13: b'\\r',
                   34: b'\\"', 92: b'\\\\'}
        for char in text:
            code = ord(char)
            if code in escapes:
                emit(escapes[code])
            elif 32 <= code < 127:
                emit(bytes((code,)))
            elif code <= 65535:
                emit(('\\u%04x' % code).encode('ascii'))
            else:
                code -= 65536
                emit(('\\u%04x\\u%04x' % (55296 + (code >> 10), 56320 + (code & 1023))).encode('ascii'))
        emit(b'"')

    def visit(item, depth):
        nonlocal nodes
        nodes += 1
        require(nodes <= limits['nodes'] and depth <= limits['depth'], 'JSON structural ceiling')
        if item is None:
            emit(b'null')
        elif type(item) is bool:
            emit(b'true' if item else b'false')
        elif type(item) is int:
            # Bound decimal conversion before constructing the decimal string.
            digits = (abs(item).bit_length() * 30103 + 99999) // 100000 + 1
            require(digits + (item < 0) <= limits['bytes'] - len(out), 'integer encoding extent')
            emit(str(item).encode('ascii'))
        elif type(item) is str:
            string(item)
        elif type(item) is float:
            require(math.isfinite(item), 'finite binary64 metadata only')
            emit(repr(item).encode('ascii'))
        elif type(item) is list:
            require(len(item) <= limits['nodes'] - nodes, 'array nodes before traversal')
            emit(b'[')
            for i, child in enumerate(item):
                if i:
                    emit(b',')
                visit(child, depth + 1)
            emit(b']')
        elif type(item) is dict:
            require(len(item) <= limits['nodes'] - nodes and all(type(k) is str for k in item),
                    'dictionary extent and literal keys')
            emit(b'{')
            for i, key in enumerate(sorted(item)):
                if i:
                    emit(b',')
                string(key)
                emit(b':')
                visit(item[key], depth + 1)
            emit(b'}')
        else:
            raise ResourceRefusal('no arbitrary metadata objects')

    visit(value, 0)
    return bytes(out)


def bounded_decode(raw, limits):
    encoding_limits(limits)
    require(type(raw) is bytes and len(raw) <= limits['bytes'], 'bounded received body')

    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, 'duplicate key')
            out[key] = value
        return out

    def no_nonfinite(value):
        raise ResourceRefusal('no nonfinite metadata')

    # JSON parsing allocations are bounded by admitted frame extent; structural
    # validation below is not falsely described as a pre-parse allocation gate.
    value = json.loads(raw.decode('utf-8', 'strict'), object_pairs_hook=pairs,
                       parse_constant=no_nonfinite)
    bounded_encode(value, limits)
    return value


class Clock:
    def __init__(self, origin, scientific, closeout, outer):
        for value in (origin, scientific, closeout, outer):
            integer(value)
        require(origin < scientific < closeout < outer, 'original ordered clock cutoffs')
        self.origin, self.scientific, self.closeout, self.outer = origin, scientific, closeout, outer

    def tick(self, phase):
        require(phase in ('scientific', 'closeout', 'outer'), 'named original cutoff')
        now = time.monotonic_ns()
        require(self.origin <= now < getattr(self, phase), 'original typed operation cutoff')
        return now


def read_fd(fd, maximum, clock, phase):
    integer(maximum)
    pieces = []
    total = 0
    while True:
        clock.tick(phase)
        block = os.read(fd, min(65536, maximum + 1 - total))
        if not block:
            break
        total += len(block)
        require(total <= maximum, 'file extent overrun')
        pieces.append(block)
    return b''.join(pieces)


def read_body(path, expected, maximum, clock, phase='closeout'):
    check_pin(expected)
    require(expected['bytes'] <= maximum, 'admitted exact file extent before open')
    clock.tick(phase)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    primary = None
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                before.st_size == expected['bytes'], 'ordinary exact immutable body')
        raw = read_fd(fd, expected['bytes'], clock, phase)
        after = os.fstat(fd)
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                'body identity changed')
        require(body_pin(raw) == expected, 'exact body pin')
        return raw
    except BaseException as error:
        primary = error
        raise
    finally:
        close_all([('body descriptor', lambda: os.close(fd))], primary)


def write_all(fd, raw, clock, phase):
    view = memoryview(raw)
    while view:
        clock.tick(phase)
        sent = os.write(fd, view)
        require(sent > 0, 'complete positive write')
        view = view[sent:]


def peer_identity(sock):
    import socket
    require(hasattr(socket, 'SO_PEERCRED'), 'Linux peer credentials required')
    raw = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i'))
    pid, uid, gid = struct.unpack('3i', raw)
    return {'pid': integer(pid, 1), 'uid': integer(uid), 'gid': integer(gid)}
