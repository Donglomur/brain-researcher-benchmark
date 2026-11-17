"""Fixed inherited FIND032 lifecycle channel; no command or data forwarding."""
import json
import os
import socket
import struct
import time

LIMIT = 1048576


def need(ok, message):
    if not ok:
        raise ValueError(message)


def decode(raw):
    need(type(raw) is bytes and 0 < len(raw) <= LIMIT, "bounded-lifecycle-frame")
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, "duplicate-lifecycle-key")
            result[key] = value
        return result
    value = json.loads(raw.decode("utf8", "strict"), object_pairs_hook=pairs,
                       parse_constant=lambda _: need(False, "finite-lifecycle-json"))
    need(type(value) is dict, "lifecycle-object")
    count = 0
    def visit(v, depth):
        nonlocal count
        count += 1
        need(count <= 10000 and depth <= 12, "lifecycle-structure-bound")
        if type(v) is dict:
            for k, x in v.items():
                need(type(k) is str and len(k) <= 256, "lifecycle-key-bound")
                visit(x, depth + 1)
        elif type(v) is list:
            for x in v:
                visit(x, depth + 1)
        elif type(v) is str:
            need(len(v.encode("utf8")) <= 2048, "lifecycle-string-bound")
        else:
            need(v is None or type(v) in (int, bool), "lifecycle-value-domain")
    visit(value, 0)
    return value


def encode(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     allow_nan=False).encode("utf8")
    decode(raw)
    return struct.pack("!I", len(raw)) + raw


class Client:
    def __init__(self, fd, deadline):
        need(type(fd) is int and fd > 2 and type(deadline) in (int, float),
             "inherited-owned-channel")
        self.socket = socket.socket(fileno=fd)
        need(self.socket.family == socket.AF_UNIX and
             self.socket.type & socket.SOCK_STREAM == socket.SOCK_STREAM,
             "private-unix-stream")
        os.set_inheritable(fd, False)
        self.deadline, self.sequence, self.index = deadline, 0, None
        self.failed, self.first, self.closed = False, None, False

    def _timeout(self):
        left = self.deadline - time.monotonic()
        need(left > 0, "original-channel-deadline")
        self.socket.settimeout(left)

    def _read(self, count):
        parts = bytearray()
        while len(parts) < count:
            self._timeout()
            raw = self.socket.recv(count - len(parts))
            need(raw, "original-parent-channel-eof")
            parts.extend(raw)
        return bytes(parts)

    def request(self, request):
        need(not self.failed and not self.closed, "no-channel-retry")
        sequence = self.sequence
        self.sequence += 1  # Attempt retained before any possible send.
        try:
            raw = encode({"sequence": sequence, "request": request})
            self._timeout()
            self.socket.sendall(raw)
            size = struct.unpack("!I", self._read(4))[0]
            need(0 < size <= LIMIT, "bounded-parent-reply")
            reply = decode(self._read(size))
            need(set(reply) == {"sequence", "result"} and reply["sequence"] == sequence,
                 "same-original-parent-reply")
            return reply["result"]
        except BaseException as error:
            self.failed, self.first = True, error
            raise

    def programme(self, identities):
        return self.request({"op": "programme", "identities": identities})

    def begin(self, index, identity):
        result = self.request({"op": "begin", "index": index, "identity": identity})
        self.index = index
        return result

    def reserve(self, role):
        return self.request({"op": "reserve", "index": self.index, "role": role})

    def attempt(self, role):
        return self.request({"op": "attempt", "index": self.index, "role": role})

    def ack(self, role, identifier):
        return self.request({"op": "ack", "index": self.index, "role": role,
                             "identifier": identifier})

    def retired(self, role, result):
        return self.request({"op": "close", "index": self.index, "role": role,
                             "result": result})

    def finish(self):
        result = self.request({"op": "finish", "index": self.index})
        self.index = None
        return result

    def close(self):
        if not self.closed:
            self.closed = True
            self.socket.close()
