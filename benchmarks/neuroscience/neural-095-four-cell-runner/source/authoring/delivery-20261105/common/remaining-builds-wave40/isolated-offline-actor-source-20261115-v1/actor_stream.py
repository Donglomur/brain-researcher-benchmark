"""Bounded Docker attach + offline JSON actor relay. No task numerical ABI import."""
from hashlib import sha256
import queue
import re
import socket
import struct
import threading
import time

STREAM_LIMITS = {"messages": 1024, "stdout_bytes": 4194304,
                 "stderr_bytes": 16384, "raw_bytes": 8388608, "stdin_bytes": 67108864,
                 "line_bytes": 65536}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def attach(docker, container_id, deadline, Wire):
    """Reviewed upgrade successor; existing finite DockerHTTP.request is unchanged."""
    need(re.fullmatch("[a-f0-9]{64}", container_id) is not None, "Captured immutable actor ID")
    sock = docker.connect(deadline)
    wire = Wire(sock, deadline)
    try:
        path = "/" + docker.version + "/containers/" + container_id + (
            "/attach?stream=1&stdin=1&stdout=1&stderr=1&logs=0")
        wire.send(("POST " + path + " HTTP/1.1\r\nHost: docker\r\n"
                   "Connection: Upgrade\r\nUpgrade: tcp\r\nContent-Length: 0\r\n\r\n").encode())
        raw = wire.until(b"\r\n\r\n", 16384)
        lines = raw[:-4].split(b"\r\n")
        status = lines[0].split(b" ", 2)
        need(len(status) >= 2 and status[:2] == [b"HTTP/1.1", b"101"],
             "Explicit Docker upgrade required")
        headers = {}
        for line in lines[1:]:
            need(b":" in line and line[:1] not in (b" ", b"\t"), "Attach header syntax")
            key, value = line.split(b":", 1)
            key, value = key.lower(), value.strip().lower()
            need(key and key not in headers, "Duplicate attach header")
            headers[key] = value
        need(headers.get(b"connection") == b"upgrade" and headers.get(b"upgrade") == b"tcp" and
             headers.get(b"content-type") in (b"application/vnd.docker.raw-stream",
                                             b"application/vnd.docker.multiplexed-stream") and
             b"content-length" not in headers and b"transfer-encoding" not in headers,
             "Unambiguous non-TTY upgraded stream")
        return wire
    except BaseException:
        sock.close()
        raise


def request_body(value):
    need(type(value) is dict and "token" not in value and "seq" not in value,
         "Actor cannot choose capability or sequence")
    op = value.get("op")
    wanted = {"freeze": {"op", "source"}, "public": {"op", "request"},
              "finish": {"op"}, "close": {"op"}}
    need(op in wanted and set(value) == wanted[op], "Exact permitted actor envelope")
    if op == "freeze":
        need(type(value["source"]) is str and 0 < len(value["source"].encode()) <= 60000,
             "Bounded committed program")
    if op == "public":
        need(type(value["request"]) is dict, "Opaque task public request")
    return value


def project_reply(value, sequence, op):
    need(type(value) is dict and type(value.get("seq")) is int and value["seq"] == sequence,
         "Exact endpoint reply sequence")
    if value.get("status") == "rejected":
        raise ValueError("Task endpoint rejected actor request")
    wanted = {"public": {"seq", "status", "payload"},
              "freeze": {"seq", "status", "controller_sha256"}}
    need(op in wanted and set(value) == wanted[op] and
         value["status"] == ("ok" if op == "public" else "committed"),
         "Exact public endpoint reply; no operator/private fields")
    return {k: v for k, v in value.items() if k != "seq"}


class ActorPump:
    """One continuously draining reader; bounded one-request queue, no pipelining."""
    def __init__(self, wire, decode, *, stdout_cap=4194304, stderr_cap=16384,
                 raw_cap=8388608, line_cap=65536, message_cap=1024):
        for value, key in ((stdout_cap,"stdout_bytes"),(stderr_cap,"stderr_bytes"),
                           (raw_cap,"raw_bytes"),(line_cap,"line_bytes"),(message_cap,"messages")):
            need(type(value) is int and 0 < value <= STREAM_LIMITS[key], "Reviewed stream ceiling")
        self.wire, self.decode = wire, decode
        self.stdout_cap, self.stderr_cap, self.raw_cap = stdout_cap, stderr_cap, raw_cap
        self.line_cap, self.message_cap = line_cap, message_cap
        self.stdout_bytes = self.raw_bytes = self.messages = 0
        self.stderr = bytearray()
        self.partial = bytearray()
        self.allowed, self.terminal, self.closed = True, False, False
        self.lock, self.inbox = threading.Lock(), queue.Queue(maxsize=1)
        self.failure = None
        self.thread = threading.Thread(target=self._read, name="bounded-actor-stream", daemon=False)

    def start(self):
        self.thread.start()

    def _read(self):
        try:
            while not self.closed:
                header = self.wire.exact(8)
                kind, length = header[0], struct.unpack("!I", header[4:])[0]
                need(kind in (1, 2) and header[1:4] == b"\0\0\0", "Actor stream framing")
                self.raw_bytes += 8 + length
                need(self.raw_bytes <= self.raw_cap, "Aggregate actor raw-stream cap")
                cap = self.stdout_cap - self.stdout_bytes if kind == 1 else self.stderr_cap - len(self.stderr)
                need(length <= cap, "Aggregate actor stdout/stderr cap")
                body = self.wire.exact(length)
                if kind == 2:
                    self.stderr.extend(body)
                    continue
                self.stdout_bytes += length
                with self.lock:
                    need(self.allowed or not body, "No actor requests while awaiting a reply")
                    self.partial.extend(body)
                    need(len(self.partial) <= self.line_cap, "Bounded actor JSON line")
                    if b"\n" not in self.partial:
                        continue
                    line, remainder = bytes(self.partial).split(b"\n", 1)
                    need(line and not remainder, "One complete request, no pipeline or surplus bytes")
                    value = request_body(self.decode(line))
                    self.partial.clear()
                    self.messages += 1
                    need(self.messages <= self.message_cap, "Actor message count cap")
                    self.allowed = False
                    self.terminal = value["op"] in ("finish", "close")
                    self.inbox.put_nowait(value)
                    if self.terminal:
                        return
        except BaseException as error:
            if not self.closed:
                self.failure = type(error).__name__
                try:
                    self.inbox.put_nowait(error)
                except queue.Full:
                    pass

    def next(self):
        left = self.wire.deadline - self.wire.clock()
        need(left > 0, "Actor deadline before next message")
        if self.failure is not None:
            raise ValueError("Actor stream failed")
        try:
            value = self.inbox.get(timeout=left)
        except queue.Empty:
            raise TimeoutError("Actor request deadline") from None
        need(not isinstance(value, BaseException) and self.failure is None, "Actor stream failed")
        return value

    def allow_reply(self):
        with self.lock:
            need(not self.terminal and not self.allowed and self.failure is None,
                 "One response to current actor request")
            self.allowed = True

    def close(self):
        self.closed = True
        try:
            self.wire.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.wire.sock.close()
        if self.thread.ident is not None:
            self.thread.join(timeout=1)
            need(not self.thread.is_alive(), "Actor stream reader termination")

    def report(self):
        return {"stdout_bytes": self.stdout_bytes, "stderr_bytes": len(self.stderr),
                "stderr_before_terminal": self.stderr.decode("utf-8", errors="replace"),
                "raw_stream_bytes": self.raw_bytes, "messages": self.messages,
                "terminal_observed": self.terminal, "error_type": self.failure,
                "complete_post_terminal_logs_claimed": False}


def relay(pump, arm_wire, token, config, encode, *, response_cap=262144,
          stdin_cap=67108864, terminal_intent):
    """Owned relay keeps capability off container stdin and never returns a private grade."""
    need(type(token) is str and re.fullmatch("[a-f0-9]{64}", token), "Exact host capability")
    need(type(stdin_cap) is int and 0 < stdin_cap <= STREAM_LIMITS["stdin_bytes"] and
         type(response_cap) is int and 0 < response_cap <= 1048576, "Explicit relay byte ceilings")
    body = encode(config) + b"\n"
    need(len(body) <= 65536, "Bounded sanitized actor config")
    sent, sequence = len(body), 1
    transcript = sha256()
    pump.start()
    try:
        pump.wire.send(body)
        while True:
            message = pump.next()
            need(sequence <= STREAM_LIMITS["messages"], "Finite actor dispatches")
            op = message["op"]
            envelope = dict(message, token=token, seq=sequence)
            transcript.update(encode(message))
            if op in ("finish", "close"):
                # Persist intent before dispatch; EOF is NOT scientific/validation success.
                terminal_intent({"op": op, "sequence": sequence,
                                 "request_sha256": sha256(encode(message)).hexdigest(),
                                 "transcript_sha256": transcript.hexdigest(),
                                 "private_grade_observed": False})
                arm_wire.send_frame(envelope, 65536)
                return {"terminal": op + "_sent", "requests": sequence,
                        "stdin_bytes": sent, "transcript_sha256": transcript.hexdigest(),
                        "trusted_validation_complete": False}
            arm_wire.send_frame(envelope, 65536)
            response = project_reply(arm_wire.frame(response_cap), sequence, op)
            reply = encode(response) + b"\n"
            sent += len(reply)
            need(sent <= stdin_cap, "Aggregate actor stdin cap")
            transcript.update(reply)
            pump.allow_reply()
            pump.wire.send(reply)
            sequence += 1
    finally:
        pump.close()

