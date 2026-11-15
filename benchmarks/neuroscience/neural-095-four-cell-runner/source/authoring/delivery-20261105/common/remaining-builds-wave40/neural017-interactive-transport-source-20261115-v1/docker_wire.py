"""Bounded operator-only Docker HTTP over AF_UNIX; no CLI or TCP fallback."""
import json
import math
import selectors
import socket
import struct
import time


def need(ok, message):
    if not ok:
        raise ValueError(message)


def decode(body):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, "Duplicate JSON key")
            out[key] = value
        return out
    def constant(value):
        raise ValueError("Nonfinite JSON constant")
    def finite_float(value):
        number = float(value)
        need(math.isfinite(number), "Nonfinite JSON number")
        return number
    return json.loads(body, object_pairs_hook=pairs, parse_constant=constant,
                      parse_float=finite_float)


def encode(value):
    return json.dumps(value, allow_nan=False, separators=(",", ":")).encode()


class Wire:
    """Absolute deadline on every nonblocking read/write; bounded receive buffer."""
    def __init__(self, sock, deadline, clock=time.monotonic):
        self.sock, self.deadline, self.clock, self.buffer = sock, deadline, clock, bytearray()
        sock.setblocking(False)

    def ready(self, event):
        left = self.deadline - self.clock()
        if left <= 0:
            raise TimeoutError("Whole connection deadline")
        with selectors.DefaultSelector() as selector:
            selector.register(self.sock, event)
            if not selector.select(left):
                raise TimeoutError("Whole connection deadline")

    def send(self, body):
        view = memoryview(body)
        while view:
            self.ready(selectors.EVENT_WRITE)
            try:
                count = self.sock.send(view)
            except BlockingIOError:
                continue
            need(count > 0, "Closed sender")
            view = view[count:]

    def receive(self, maximum):
        need(type(maximum) is int and maximum > 0, "Positive read cap")
        while True:
            self.ready(selectors.EVENT_READ)
            try:
                return self.sock.recv(min(maximum, 65536))
            except BlockingIOError:
                continue

    def exact(self, count):
        need(type(count) is int and count >= 0, "Bounded length")
        while len(self.buffer) < count:
            part = self.receive(count - len(self.buffer))
            need(part, "Truncated stream")
            self.buffer.extend(part)
        result = bytes(self.buffer[:count])
        del self.buffer[:count]
        return result

    def until(self, delimiter, maximum):
        while True:
            index = self.buffer.find(delimiter)
            if index >= 0:
                end = index + len(delimiter)
                need(end <= maximum, "Header/line cap")
                result = bytes(self.buffer[:end])
                del self.buffer[:end]
                return result
            need(len(self.buffer) < maximum, "Header/line cap")
            part = self.receive(maximum - len(self.buffer))
            need(part, "Truncated header")
            self.buffer.extend(part)

    def frame(self, maximum):
        length = struct.unpack("!I", self.exact(4))[0]
        need(0 < length <= maximum, "JSON frame cap")
        return decode(self.exact(length))

    def send_frame(self, value, maximum):
        body = encode(value)
        need(0 < len(body) <= maximum, "JSON response cap")
        self.send(struct.pack("!I", len(body)) + body)


class DockerHTTP:
    """Socket and API version are operator inputs; never mounted into candidates."""
    def __init__(self, socket_path, *, api_version="v1.47", connect=None):
        need(isinstance(socket_path, str) and socket_path.startswith("/") and
             "\x00" not in socket_path, "Absolute operator socket")
        need(api_version in ("v1.41", "v1.47"), "Explicit reviewed Docker API version")
        self.socket_path, self.version = socket_path, api_version
        self.connect = connect or self._connect

    def _connect(self, deadline):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Docker connect deadline")
            sock.settimeout(remaining)
            sock.connect(self.socket_path)
            return sock
        except BaseException:
            sock.close()
            raise

    def request(self, method, path, *, body=None, deadline, cap=262144):
        need(method in ("GET", "POST", "DELETE"), "Bounded Docker method")
        need(path.startswith("/") and all(32 < ord(c) < 127 for c in path) and
             not any(c in path for c in "\r\n#"), "Literal Docker route")
        need(type(cap) is int and 0 <= cap <= 45000000, "Docker body cap")
        data = b"" if body is None else encode(body)
        need(len(data) <= 65536, "Docker request cap")
        head = (method + " /" + self.version + path +
                " HTTP/1.1\r\nHost: docker\r\nConnection: close\r\n" +
                "Content-Type: application/json\r\nContent-Length: " +
                str(len(data)) + "\r\n\r\n").encode("ascii")
        sock = self.connect(deadline)
        try:
            wire = Wire(sock, deadline)
            wire.send(head + data)
            header = wire.until(b"\r\n\r\n", 16384)
            lines = header[:-4].split(b"\r\n")
            status = lines[0].split(b" ", 2)
            need(len(status) >= 2 and status[0] in (b"HTTP/1.0", b"HTTP/1.1") and
                 len(status[1]) == 3 and status[1].isdigit(), "HTTP response status")
            code = int(status[1])
            headers = {}
            for line in lines[1:]:
                need(b":" in line and line[:1] not in (b" ", b"\t"), "HTTP header syntax")
                key, value = line.split(b":", 1)
                key, value = key.lower(), value.strip()
                need(key and key not in headers, "Duplicate HTTP header")
                headers[key] = value
            length, transfer = headers.get(b"content-length"), headers.get(b"transfer-encoding")
            need(not (length is not None and transfer is not None), "Ambiguous HTTP framing")
            output = bytearray()
            if code in (204, 304):
                need(transfer is None and length in (None, b"0"), "Bodyless status")
            elif length is not None:
                need(length.isdigit() and len(length) <= 12, "HTTP content length")
                count = int(length)
                need(count <= cap, "Docker response too large")
                output.extend(wire.exact(count))
            elif transfer == b"chunked":
                while True:
                    line = wire.until(b"\r\n", 128)[:-2]
                    need(line and all(c in b"0123456789abcdefABCDEF" for c in line),
                         "Strict chunk size; extensions not permitted")
                    count = int(line, 16)
                    need(count <= cap - len(output), "Docker chunk aggregate cap")
                    if count == 0:
                        need(wire.exact(2) == b"\r\n", "No response trailers")
                        break
                    output.extend(wire.exact(count))
                    need(wire.exact(2) == b"\r\n", "Chunk delimiter")
            else:
                need(transfer is None, "Unsupported transfer encoding")
                # Docker close-delimited response: bounded until EOF.
                output.extend(wire.buffer)
                wire.buffer.clear()
                need(len(output) <= cap, "Docker response too large")
                while True:
                    part = wire.receive(min(65536, cap - len(output) + 1))
                    if not part:
                        break
                    output.extend(part)
                    need(len(output) <= cap, "Docker response too large")
            return code, bytes(output)
        finally:
            sock.close()

    def json(self, method, path, *, body=None, deadline, cap=262144, statuses=(200, 201)):
        status, data = self.request(method, path, body=body, deadline=deadline, cap=cap)
        need(status in statuses, "Docker HTTP status " + str(status))
        return {} if not data else decode(data)


def multiplex(body, cap):
    """Decode Docker's non-TTY stdout/stderr framing under one aggregate bound."""
    need(len(body) <= cap, "Raw Docker stream cap")
    streams = {1: bytearray(), 2: bytearray()}
    offset = 0
    while offset < len(body):
        need(len(body) - offset >= 8, "Truncated Docker stream header")
        kind, padding, length = body[offset], body[offset+1:offset+4], struct.unpack("!I", body[offset+4:offset+8])[0]
        need(kind in streams and padding == b"\0\0\0", "Docker stream type")
        offset += 8
        need(length <= len(body) - offset, "Truncated Docker stream body")
        streams[kind].extend(body[offset:offset+length])
        offset += length
    return bytes(streams[1]), bytes(streams[2])

