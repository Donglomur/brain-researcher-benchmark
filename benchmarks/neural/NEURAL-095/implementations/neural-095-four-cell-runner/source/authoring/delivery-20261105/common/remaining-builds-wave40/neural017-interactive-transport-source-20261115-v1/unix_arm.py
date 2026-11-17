"""Single authenticated, serialized AF_UNIX endpoint for one benchmark arm."""
from dataclasses import asdict
from hashlib import sha256
import ctypes
import hmac
import os
from pathlib import Path
import secrets
import socket
import stat
import struct
import time

from broker import Usage
from docker_wire import Wire, encode, need
from interactive_backend import PYTHON_TOOL


def peer_uid(sock):
    """Kernel peer credentials, never a client JSON identity."""
    if hasattr(socket, "SO_PEERCRED"):
        raw = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        return struct.unpack("3i", raw)[1]
    libc = ctypes.CDLL(None, use_errno=True)
    function = libc.getpeereid
    function.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint),
                         ctypes.POINTER(ctypes.c_uint)]
    function.restype = ctypes.c_int
    uid, gid = ctypes.c_uint(), ctypes.c_uint()
    if function(sock.fileno(), ctypes.byref(uid), ctypes.byref(gid)) != 0:
        raise OSError(ctypes.get_errno(), "Peer credential lookup")
    return uid.value


class ReservationPolicy:
    """Same immutable reservation schedule for both modes; no client cost fields."""
    def __init__(self, tool_cpu_us, outer_holder_cpu_us):
        need(type(tool_cpu_us) is int and tool_cpu_us > 512000000,
             "Full tool interval including cleanup reserved")
        need(type(outer_holder_cpu_us) is int and outer_holder_cpu_us > 0,
             "Explicit outer holder reservation")
        self.tool = Usage(calls=1, cpu_us=tool_cpu_us)
        self.view = Usage(calls=1)
        self.outer_holder_cpu_us = outer_holder_cpu_us

    def descriptor(self):
        return {"schema": "neural017-offline-python-reservations/v2", "tool": PYTHON_TOOL,
                "tool_reservation": asdict(self.tool), "view_reservation": asdict(self.view),
                "outer_holder_cpu_reserved_us": self.outer_holder_cpu_us,
                "cpu_kind": "64-task candidate wall upper bound;16-task holder outer bound",
                "model_tools": False,
                "fixed_case_cpu": "all remaining common total; one invocation",
                "adaptive_cpu": "common chunk per invocation, same total cap"}

    def digest(self):
        return sha256(encode(self.descriptor())).hexdigest()

    def for_request(self, request, session=None):
        need(isinstance(request, dict), "Public request object")
        if request.get("op") == "view":
            return self.view
        need(request.get("op") == "tool" and request.get("tool_id") == PYTHON_TOOL,
             "No external model or unlisted numerical tools")
        if session is not None and session.mode == "frozen_program" and session.state == "case":
            return Usage(calls=1, cpu_us=session.limits.total.cpu_us - session.used.cpu_us)
        return self.tool


class UnixArmServer:
    """One connection, strict sequence IDs, no private-grade or arbitrary-path API.

    The process is a trusted v4-owned host controller. A benchmarked actor gets
    only this capability, never host shell/filesystem or the Docker daemon socket.
    The actor itself is outside the numerical sandbox; no model provider is
    implemented or billed by this offline adapter.
    """
    def __init__(self, path, session, policy, *, token=None, expected_uid=None,
                 authenticate=peer_uid):
        path = Path(path).absolute()
        parent = path.parent.resolve()
        need(path.name not in ("", ".", "..") and not path.exists() and not path.is_symlink(),
             "Fresh Unix socket")
        st = parent.stat()
        need(stat.S_ISDIR(st.st_mode) and stat.S_IMODE(st.st_mode) == 0o700 and
             st.st_uid == os.geteuid(), "Private operator socket directory")
        self.path, self.session, self.policy = parent / path.name, session, policy
        need(policy.digest() == session.reservation_policy_sha and
             session.tool_ids == (PYTHON_TOOL,), "Exact common offline policy and tool")
        need(policy.outer_holder_cpu_us == session.backend.holder_cpu_reservation_us,
             "Common policy binds complete outer holder reservation")
        self.token = token or secrets.token_hex(32)
        need(isinstance(self.token, str) and len(self.token) == 64 and
             all(x in "0123456789abcdef" for x in self.token), "One unguessable arm capability")
        self.expected_uid = os.geteuid() if expected_uid is None else expected_uid
        need(type(self.expected_uid) is int and self.expected_uid >= 0, "Kernel UID binding")
        self.authenticate, self.listener, self.socket_identity = authenticate, None, None
        self.connection, self.revoked = None, False
        session.backend.bind_channel(self.revoke_channel)

    def revoke_channel(self):
        # Terminal capability, including any accepted descriptor. No actor process
        # reaping is inferred. The external owned launcher remains responsible for
        # stopping/proving absence of the trusted server process group.
        self.revoked = True
        if self.listener is not None:
            self.listener.close()
        if self.connection is not None:
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.connection.close()
        return True

    def _dispatch(self, message, sequence):
        need(not self.revoked, "Irrevocably revoked arm")
        need(isinstance(message, dict) and type(message.get("seq")) is int and
             message["seq"] == sequence, "Exact ordered request sequence")
        need(isinstance(message.get("token"), str) and
             hmac.compare_digest(message["token"], self.token), "Authenticated arm capability")
        op = message.get("op")
        if op == "public":
            need(set(message) == {"seq", "token", "op", "request"}, "Exact public envelope")
            request = message["request"]
            payload = self.session.request(request, self.policy.for_request(request, self.session))
            return {"seq": sequence, "status": "ok", "payload": payload}, False
        if op == "freeze":
            need(set(message) == {"seq", "token", "op", "source"} and
                 isinstance(message["source"], str), "Exact controller envelope")
            value = self.session.freeze_controller(message["source"].encode())
            return {"seq": sequence, "status": "committed", "controller_sha256": value}, False
        if op == "finish":
            need(set(message) == {"seq", "token", "op"}, "No extra finish arguments")
            receipt = self.session.finish()
            # finalize closes this capability before capture. This return value
            # is operator-only: handle never sends a response on a revoked socket.
            return {"seq": sequence, "status": "committed",
                    "submission_sha256": receipt["submission_sha256"]}, True
        if op == "close":
            need(set(message) == {"seq", "token", "op"}, "No extra close arguments")
            self.session.close()
            return {"seq": sequence, "status": "closed"}, True
        raise ValueError("Unsupported operation; private grading is operator-only")

    def handle(self, connection):
        need(not self.revoked, "No reattachment after revocation")
        self.connection = connection
        need(self.authenticate(connection) == self.expected_uid, "Kernel peer UID mismatch")
        deadline = (self.session.started + self.session.limits.wall_us) / 1000000
        wire = Wire(connection, deadline)
        sequence = 1
        while True:
            try:
                message = wire.frame(65536)
                response, done = self._dispatch(message, sequence)
                if not self.revoked:
                    wire.send_frame(response, self.session.limits.response_bytes)
            except BaseException as error:
                # Never serialize operator errors, filenames, receipts or tokens.
                try:
                    wire.send_frame({"seq": sequence, "status": "rejected",
                                     "error_type": type(error).__name__}, 4096)
                except BaseException:
                    pass
                raise
            if done:
                return
            sequence += 1

    def serve_one(self):
        need(not self.revoked and self.listener is None, "One irreversible server lifetime")
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener = listener
        try:
            listener.bind(str(self.path))
            os.chmod(self.path, 0o600)
            st = self.path.lstat()
            self.socket_identity = (st.st_dev, st.st_ino)
            listener.listen(1)
            deadline = (self.session.started + self.session.limits.wall_us) / 1000000
            left = deadline - time.monotonic()
            if left <= 0:
                raise TimeoutError("Arm preparation deadline")
            listener.settimeout(left)
            connection, _ = listener.accept()
            try:
                self.handle(connection)
            finally:
                connection.close()  # No private-grade feedback can reach a live actor.
        finally:
            try:
                self.revoke_channel()
                if self.socket_identity is not None:
                    try:
                        st = self.path.lstat()
                    except FileNotFoundError:
                        st = None
                    if st is not None:
                        need(stat.S_ISSOCK(st.st_mode) and
                             (st.st_dev, st.st_ino) == self.socket_identity,
                             "Do not unlink a replaced socket")
                        self.path.unlink()
            finally:
                # A missing/replaced socket never prevents numerical cleanup.
                # Preserve validated state for the paired private-grade barrier.
                if self.session.state == "validated":
                    self.session.backend.stop()
                else:
                    self.session.close()


def call(sock, message, *, deadline, response_cap=262144):
    """Candidate client helper: bounded messages only, no daemon or host handles."""
    wire = Wire(sock, deadline)
    wire.send_frame(message, 65536)
    return wire.frame(response_cap)

