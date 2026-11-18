"""Trusted one-query HTTPS client for the existing NEURAL-077 bridge.

Credentials arrive only on an inherited pipe. No SDK, proxy, redirect, retry,
provider parser replacement, or model execution occurs on import.
"""
from pathlib import Path
import hashlib
import http.client
import importlib.util
import json
import math
import os
import re
import selectors
import signal
import ssl
import stat
import sys
import time

BRIDGE_PIN = {"bytes": 10224, "sha256": "4ee0d10cd424695bf496f12eec66aea0c67efc228d9e136fa9cabe1209df8c0a"}
PARSER_PIN = {"bytes": 2210, "sha256": "5f992a42a2c29905a792a11a9062ca18cdc0c73581013cc125544bf1f6758700"}
ENDPOINT = "https://api.openai.com/v1/responses"
CONFIG_CAP = 16384
CREDENTIAL_CAP = 4096
REQUEST_CAP = 8388608
RESPONSE_CAP = 524288
BOOTSTRAP_SECONDS = 5.0
CUSTODY_SECONDS = 2.0
CONFIG_KEYS = {"schema", "model", "max_output_tokens", "deadline", "trial_id", "context_sha256", "bridge_path", "bridge_pin"}
FILES = {"REQUEST.bin", "RESPONSE.bin", "HTTP.json", "BRIDGE.json"}


class Refused(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class Deadline(TimeoutError):
    pass


def need(ok, code):
    if not ok:
        raise Refused(code)


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def decode(raw):
    def pairs(rows):
        out = {}
        for key, value in rows:
            need(key not in out, "configuration")
            out[key] = value
        return out
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(Refused("configuration")))


def remaining(deadline):
    value = deadline - time.monotonic()
    if value <= 0:
        raise Deadline("deadline")
    return value


class Alarm:
    """Dedicated client process timer, backed by the operator's outer deadline."""
    def __init__(self, deadline):
        need(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0), "inherited_timer")
        self.old = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, self.expired)
        self.arm(deadline)

    @staticmethod
    def expired(number, frame):
        raise Deadline("deadline")

    def arm(self, deadline):
        signal.setitimer(signal.ITIMER_REAL, max(0.000001, deadline - time.monotonic()))

    def close(self):
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, self.old)


def pipe_body(fd, cap, deadline):
    info = os.fstat(fd)
    need(stat.S_ISFIFO(info.st_mode) and info.st_uid == os.geteuid(), "owned_pipe")
    chunks = bytearray()
    with selectors.DefaultSelector() as selector:
        selector.register(fd, selectors.EVENT_READ)
        while True:
            if not selector.select(remaining(deadline)):
                raise Deadline("deadline")
            data = os.read(fd, min(4096, cap + 1 - len(chunks)))
            if not data:
                return bytes(chunks)
            chunks.extend(data)
            need(len(chunks) <= cap, "pipe_cap")


def configuration(raw):
    need(type(raw) is bytes and 0 < len(raw) <= CONFIG_CAP, "configuration")
    value = decode(raw)
    need(type(value) is dict and set(value) == CONFIG_KEYS and value["schema"] == "neural077_openai_client_v1", "configuration")
    need(type(value["model"]) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}", value["model"]), "configuration")
    need(type(value["max_output_tokens"]) is int and 1 <= value["max_output_tokens"] <= 32768, "configuration")
    need(type(value["deadline"]) in (int, float) and math.isfinite(value["deadline"])
         and CUSTODY_SECONDS < value["deadline"] - time.monotonic() <= 3600, "configuration")
    need(type(value["trial_id"]) is str and re.fullmatch(r"development-00[12]-[0-9a-f]{24}", value["trial_id"]), "configuration")
    need(type(value["context_sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", value["context_sha256"]), "configuration")
    need(type(value["bridge_path"]) is str and value["bridge_pin"] == BRIDGE_PIN, "configuration")
    return value


def source_bytes(path, expected):
    path = Path(path)
    need(path.is_absolute() and ".." not in path.parts and not any(p.is_symlink() for p in (path, *path.parents)), "source")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == expected["bytes"], "source")
        chunks = bytearray()
        while len(chunks) <= expected["bytes"]:
            data = os.read(fd, expected["bytes"] + 1 - len(chunks))
            if not data:
                break
            chunks.extend(data)
        after = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")
        need(all(getattr(before, k) == getattr(after, k) == getattr(path.lstat(), k) for k in fields), "source")
        raw = bytes(chunks)
        need(pin(raw) == expected, "source")
        return raw
    finally:
        os.close(fd)


def load_bridge(config):
    path = Path(config["bridge_path"])
    raw = source_bytes(path, BRIDGE_PIN)
    source_bytes(path.parent.parent / "direct-response/portable/response_contract.py", PARSER_PIN)
    spec = importlib.util.spec_from_loader("neural077_owned_https_bridge", loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


class Blob:
    def __init__(self, custody, name, cap):
        need(name in FILES and name not in custody.created, "custody_failure")
        remaining(custody.deadline)
        self.owner, self.cap, self.count, self.digest, self.fd = custody, cap, 0, hashlib.sha256(), None
        self.fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=custody.fd)
        custody.created.add(name)
        try:
            os.fchmod(self.fd, 0o600)
        except BaseException:
            fd, self.fd = self.fd, None
            os.close(fd)
            raise

    def append(self, raw):
        need(type(raw) is bytes and self.count + len(raw) <= self.cap, "custody_failure")
        at = 0
        while at < len(raw):
            remaining(self.owner.deadline)
            count = os.write(self.fd, raw[at:])
            need(type(count) is int and count > 0, "custody_failure")
            self.digest.update(raw[at:at + count]); self.count += count; at += count

    def descriptor(self):
        return {"bytes": self.count, "sha256": self.digest.hexdigest()}

    def close(self):
        if self.fd is not None:
            fd, self.fd = self.fd, None
            try:
                os.fsync(fd)
            finally:
                os.close(fd)


class Custody:
    def __init__(self, fd, config_pin, deadline):
        info = os.fstat(fd)
        need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid()
             and stat.S_IMODE(info.st_mode) == 0o700 and os.listdir(fd) == [], "private_fresh_custody")
        self.fd, self.config_pin, self.deadline, self.created = fd, config_pin, deadline, set()

    def put(self, name, raw):
        file = Blob(self, name, max(16384, len(raw)))
        try:
            file.append(raw)
        finally:
            file.close()
        os.fsync(self.fd)
        return file.descriptor()

    def json(self, name, value):
        raw = encode(value); need(len(raw) <= 16384, "custody_failure")
        return self.put(name, raw)


def category(error):
    if isinstance(error, Refused):
        return error.code
    if isinstance(error, TimeoutError):
        return "deadline"
    if isinstance(error, http.client.IncompleteRead):
        return "incomplete_body"
    return "network_error"


class Sender:
    def __init__(self, config, config_pin, credential, custody, bridge, alarm,
                 http_factory=http.client.HTTPSConnection, response_cap=RESPONSE_CAP):
        need(type(credential) is str and 1 <= len(credential) <= CREDENTIAL_CAP
             and all(33 <= ord(c) <= 126 for c in credential), "credential")
        need(type(response_cap) is int and 1 <= response_cap <= RESPONSE_CAP, "response_cap")
        self.config, self.config_pin, self.credential, self.custody = config, config_pin, credential, custody
        self.bridge, self.alarm, self.factory, self.cap = bridge, alarm, http_factory, response_cap
        self.called = False

    def __call__(self, request):
        need(not self.called, "second_sender_call")
        self.called = True
        c = self.config; end = c["deadline"] - CUSTODY_SECONDS; start = time.monotonic()
        request_file = response_file = connection = response = None
        status = None; complete = overflow = request_complete = False
        failure = None; attempted = 0; closed = True; close_failed = False; body = bytearray()
        pending = bytearray(); seen = 0; credential_bytes = self.credential.encode("ascii")
        def retain(part):
            nonlocal seen
            seen += len(part); pending.extend(part)
            found = pending.find(credential_bytes)
            if found >= 0:
                safe = bytes(pending[:found]); pending.clear()
                response_file.append(safe); body.extend(safe)
                raise Refused("credential_echo")
            safe_count = max(0, len(pending) - (len(credential_bytes) - 1))
            safe = bytes(pending[:safe_count]); del pending[:safe_count]
            response_file.append(safe); body.extend(safe)
        def flush_pending():
            # No complete literal credential occurs in this bounded suffix.
            safe = bytes(pending); pending.clear()
            response_file.append(safe); body.extend(safe)
        try:
            need(type(request) is bytes and 0 < len(request) <= REQUEST_CAP, "request_cap")
            need(credential_bytes not in request, "credential_echo")
            request_file = Blob(self.custody, "REQUEST.bin", REQUEST_CAP)
            request_file.append(request); request_file.close(); request_complete = True
            response_file = Blob(self.custody, "RESPONSE.bin", self.cap + 1)
            value = self.bridge.decode(request)
            prompt = value["input"][0]["content"][0]["text"]
            need(self.bridge.query_identity(prompt) == c["trial_id"]
                 and pin(prompt.encode("utf-8"))["sha256"] == c["context_sha256"], "context_mismatch")
            need(request == self.bridge.request_body(prompt, c["model"], c["max_output_tokens"]), "request_mismatch")
            context = ssl.create_default_context()
            need(context.check_hostname is True and context.verify_mode == ssl.CERT_REQUIRED, "tls_policy")
            connection = self.factory("api.openai.com", port=443, timeout=remaining(end), context=context)
            connection.set_debuglevel(0)
            attempted = 1; closed = False
            connection.request("POST", "/v1/responses", body=request, headers={
                "Authorization": "Bearer " + self.credential, "Content-Type": "application/json",
                "Accept": "application/json", "Accept-Encoding": "identity", "Connection": "close"}, encode_chunked=False)
            if connection.sock is not None:
                connection.sock.settimeout(remaining(end))
            response = connection.getresponse(); status = response.status
            need(type(status) is int and 100 <= status <= 599, "http_status")
            while True:
                remaining(end)
                if connection.sock is not None:
                    connection.sock.settimeout(remaining(end))
                try:
                    part = response.read(min(65536, self.cap + 1 - seen))
                except http.client.IncompleteRead as error:
                    partial = error.partial
                    need(type(partial) is bytes, "incomplete_body")
                    retained = partial[:self.cap + 1 - seen]
                    retain(retained)
                    overflow = seen > self.cap
                    raise Refused("response_oversize" if overflow else "incomplete_body") from None
                need(type(part) is bytes, "invalid_http_body")
                if not part:
                    need(getattr(response, "length", None) in (None, 0), "incomplete_body")
                    flush_pending(); complete = True; break
                need(len(part) <= self.cap + 1 - seen, "invalid_http_body")
                retain(part)
                if seen > self.cap:
                    overflow = True
                    raise Refused("response_oversize")
            need(response.getheader("Content-Encoding", "identity").lower() == "identity", "content_encoding")
            need(status == 200, "http_status")
        except Exception as error:
            failure = category(error)
        finally:
            # Spend only the already reserved part of the original deadline.
            self.alarm.arm(c["deadline"])
            if response_file is not None and pending:
                try:
                    flush_pending()
                except Exception:
                    failure = failure or "custody_failure"
            for owned in (response, connection):
                if owned is not None:
                    try:
                        owned.close()
                    except Exception:
                        close_failed = True; failure = failure or "connection_close"
            closed = not close_failed
            for file in (request_file, response_file):
                if file is not None:
                    try:
                        file.close()
                    except Exception:
                        failure = failure or "custody_failure"
            if request_file is None:
                self.custody.put("REQUEST.bin", b"")
            if response_file is None:
                self.custody.put("RESPONSE.bin", b"")
            self.custody.json("HTTP.json", {
                "schema": "neural077_https_binding_v1", "config_pin": self.config_pin, "endpoint": ENDPOINT,
                "request": request_file.descriptor() if request_file else pin(b""),
                "response": response_file.descriptor() if response_file else pin(b""),
                "status_code": status, "request_complete": request_complete, "response_complete": complete,
                "body_overflow": overflow, "requests_attempted": attempted, "redirects_followed": 0, "retries": 0,
                "connection_closed": closed, "credential_retained": False, "failure": failure,
                "started_monotonic": start, "finished_monotonic": time.monotonic(), "deadline": c["deadline"]})
        if failure is not None:
            raise Refused(failure)
        return bytes(body)


def arguments(argv):
    need(len(argv) == 6, "arguments")
    values = {}
    for name, value in zip(argv[::2], argv[1::2]):
        need(name in ("--credential-fd", "--config-fd", "--custody-fd") and name not in values
             and value.isascii() and value.isdecimal(), "arguments")
        values[name] = int(value)
    need(len(set(values.values())) == 3 and all(3 <= x <= 1048576 for x in values.values()), "arguments")
    return values


def main(argv=None, *, http_factory=http.client.HTTPSConnection, input_stream=None, output_stream=None):
    """CLI has descriptor numbers only; all HTTP injection is trusted test code."""
    started = time.monotonic(); alarm = None; fds = {}; custody = None; sender = None; config = None
    recorded = False; success = False
    try:
        fds = arguments(sys.argv[1:] if argv is None else argv)
        alarm = Alarm(started + BOOTSTRAP_SECONDS)
        raw = pipe_body(fds["--config-fd"], CONFIG_CAP, started + BOOTSTRAP_SECONDS)
        os.close(fds.pop("--config-fd"))
        config = configuration(raw); config_pin = pin(raw)
        custody = Custody(fds["--custody-fd"], config_pin, config["deadline"])
        alarm.arm(config["deadline"] - CUSTODY_SECONDS)
        secret = pipe_body(fds["--credential-fd"], CREDENTIAL_CAP, config["deadline"] - CUSTODY_SECONDS)
        os.close(fds.pop("--credential-fd"))
        need(1 <= len(secret) <= CREDENTIAL_CAP and all(33 <= byte <= 126 for byte in secret), "credential")
        credential = secret.decode("ascii"); del secret
        bridge = load_bridge(config)
        sender = Sender(config, config_pin, credential, custody, bridge, alarm, http_factory)
        del credential
        def record(receipt):
            nonlocal recorded
            need(not recorded, "second_bridge_receipt")
            # A decoded provider ID can contain literal token bytes even when
            # the raw JSON encoded them; never persist that metadata echo.
            need(sender.credential.encode("ascii") not in encode(receipt), "credential_echo")
            custody.json("BRIDGE.json", {"schema": "neural077_provider_binding_bridge_v1", "config_pin": config_pin,
                         "status": "recorded", "receipt": receipt, "failure": None})
            need(custody.created == FILES and set(os.listdir(custody.fd)) == FILES, "custody_membership")
            recorded = True
        bridge.serve(sys.stdin.buffer if input_stream is None else input_stream,
                     sys.stdout.buffer if output_stream is None else output_stream,
                     model=config["model"], max_output_tokens=config["max_output_tokens"], send_json=sender, record=record)
        need(custody.created == FILES and set(os.listdir(custody.fd)) == FILES, "custody_membership")
        success = True
    except Exception:
        # Exception strings may contain credentials, URLs or header values.
        success = False
    finally:
        if sender is not None:
            sender.credential = None
        if custody is not None and config is not None:
            try:
                alarm.arm(config["deadline"])
                if "REQUEST.bin" not in custody.created:
                    custody.put("REQUEST.bin", b"")
                if "RESPONSE.bin" not in custody.created:
                    custody.put("RESPONSE.bin", b"")
                if "HTTP.json" not in custody.created:
                    custody.json("HTTP.json", {"schema": "neural077_https_binding_v1", "config_pin": custody.config_pin,
                        "endpoint": ENDPOINT, "request": pin(b""), "response": pin(b""), "status_code": None,
                        "request_complete": False, "response_complete": False, "body_overflow": False,
                        "requests_attempted": 0, "redirects_followed": 0, "retries": 0, "connection_closed": False,
                        "credential_retained": False, "failure": "preflight_or_incomplete_custody",
                        "started_monotonic": started, "finished_monotonic": time.monotonic(), "deadline": config["deadline"]})
                if not recorded and "BRIDGE.json" not in custody.created:
                    custody.json("BRIDGE.json", {"schema": "neural077_provider_binding_bridge_v1", "config_pin": custody.config_pin,
                                 "status": "not_called", "receipt": None, "failure": "preflight_or_invalid_prompt"})
            except Exception:
                success = False
        if alarm is not None:
            alarm.close()
        for fd in fds.values():
            try:
                os.close(fd)
            except OSError:
                success = False
    return 0 if success else 3


if __name__ == "__main__":
    raise SystemExit(main())
