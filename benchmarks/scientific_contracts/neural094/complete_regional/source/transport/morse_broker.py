"""Host-only, phase-bound model broker. No candidate command/file/URL tools.

The concrete HTTPS route is future-facing: no provider or token-bound
qualification is established by constructing this module. Its subprocess is
fixed trusted broker code, never candidate Python. Credentials never enter a
candidate container or a receipt. Injected engines are engineering controls.
"""
import hashlib
import json
import math
import os
import re
import selectors
import signal
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from morse_protocol import _decode_body, encode_frame


class BrokerError(ValueError):
    pass


def integer(value, label, minimum=1):
    if type(value) is not int or value < minimum:
        raise BrokerError("invalid " + label)
    return value


def positive(value, label):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise BrokerError("invalid " + label)
    return value


def exact(value, keys, label):
    if type(value) is not dict or set(value) != set(keys):
        raise BrokerError("invalid " + label + " schema")


def canonical(value):
    return encode_frame(value, 0xffffffff)[4:]


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def validate_model_spec(spec):
    exact(spec, ("endpoint", "model_revision", "credential_env", "protocol",
                 "request_max_bytes", "response_max_bytes", "stderr_max_bytes",
                 "timeout_seconds", "token_bound"), "model_spec")
    if spec["protocol"] != "messages-text-usage-v1":
        raise BrokerError("unsupported model protocol")
    uri = urlsplit(spec["endpoint"])
    if (uri.scheme != "https" or not uri.hostname or uri.username or uri.password
            or uri.fragment):
        raise BrokerError("trusted endpoint must be fixed HTTPS without userinfo")
    if not isinstance(spec["model_revision"], str) or not spec["model_revision"]:
        raise BrokerError("model revision required")
    if not isinstance(spec["credential_env"], str) or not re.fullmatch(
            r"[A-Z][A-Z0-9_]{0,127}", spec["credential_env"]):
        raise BrokerError("invalid credential environment key")
    for key in ("request_max_bytes", "response_max_bytes", "stderr_max_bytes"):
        integer(spec[key], key)
    positive(spec["timeout_seconds"], "timeout_seconds")
    bound = spec["token_bound"]
    exact(bound, ("utf8_multiplier", "fixed_overhead", "per_message_overhead",
                  "certificate_sha256"), "token_bound")
    integer(bound["utf8_multiplier"], "utf8_multiplier")
    integer(bound["fixed_overhead"], "fixed_overhead", 0)
    integer(bound["per_message_overhead"], "per_message_overhead", 0)
    if not re.fullmatch(r"[0-9a-f]{64}", bound["certificate_sha256"]):
        raise BrokerError("token bound certificate required")
    return spec


class HttpsJsonEngine:
    """One stateless HTTPS call per fixed trusted child process.

    `token_admission` must be an independently selected trusted policy object
    implementing require_model_bound(spec). No built-in policy admits a model;
    a caller boolean or digest alone is not evidence of token semantics.
    The parent campaign must separately authorize actual API expenditure.
    """
    kind = "real_future_https_child"

    def __init__(self, model_spec, *, token_admission=None):
        self.spec = validate_model_spec(json.loads(canonical(model_spec)))
        if token_admission is None:
            raise BrokerError("model-token qualification unavailable")
        token_admission.require_model_bound(self.spec)
        self._process = None
        self._lock = threading.Lock()

    def cancel(self):
        with self._lock:
            proc = self._process
        if proc is not None and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def terminal_observed(self):
        with self._lock:
            proc = self._process
        return proc is None or proc.poll() is not None

    def generate(self, messages, max_output_tokens, input_bound, timeout, cancelled):
        if cancelled.is_set():
            raise BrokerError("model call cancelled")
        secret = os.environ.get(self.spec["credential_env"])
        if not secret:
            raise BrokerError("configured model credential unavailable")
        # Explicit message list only: no session IDs, provider files, tools,
        # candidate endpoints, previous-response IDs, or persistent conversation.
        payload = {"spec": self.spec, "credential": secret,
                   "request": {"model_revision": self.spec["model_revision"],
                               "messages": messages,
                               "max_output_tokens": max_output_tokens}}
        request = canonical(payload)
        if len(canonical(payload["request"])) > self.spec["request_max_bytes"]:
            raise BrokerError("model request byte limit")
        # Fixed module path and fixed flags; untrusted text is stdin data.
        proc = subprocess.Popen(
            [sys.executable, "-I", "-B", os.path.abspath(__file__), "--https-child"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={"PATH": os.defpath}, start_new_session=True, close_fds=True)
        with self._lock:
            self._process = proc
        try:
            raw, _ = bounded_exchange(proc, request, self.spec["response_max_bytes"],
                                      self.spec["stderr_max_bytes"],
                                      min(timeout, self.spec["timeout_seconds"]), cancelled)
            result = _decode_body(raw)
            if proc.returncode != 0:
                raise BrokerError("trusted HTTPS child failed")
            return result
        finally:
            cleanup_error = None
            try:
                self.cancel()
            except Exception as exc:
                cleanup_error = exc
            try:
                proc.wait(timeout=2)
            except Exception as exc:
                cleanup_error = exc
            finally:
                for stream in (proc.stdin, proc.stdout, proc.stderr):
                    try:
                        stream.close()
                    except Exception as exc:
                        cleanup_error = exc
                with self._lock:
                    # Keep an unresolved process reachable for later cancellation.
                    if proc.poll() is not None:
                        self._process = None
            if cleanup_error is not None:
                raise BrokerError("trusted HTTPS child cleanup incomplete") from cleanup_error


def bounded_exchange(proc, outgoing, stdout_limit, stderr_limit, timeout, cancelled):
    """Concurrent bounded exchange for the fixed trusted child; no shell."""
    deadline = time.monotonic() + timeout
    output, errors = bytearray(), bytearray()
    sent = 0
    with selectors.DefaultSelector() as selector:
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            os.set_blocking(stream.fileno(), False)
        selector.register(proc.stdin, selectors.EVENT_WRITE, "input")
        selector.register(proc.stdout, selectors.EVENT_READ, "output")
        selector.register(proc.stderr, selectors.EVENT_READ, "error")
        while selector.get_map():
            if cancelled.is_set() or time.monotonic() >= deadline:
                raise BrokerError("trusted model child deadline/cancellation")
            for key, _ in selector.select(min(0.05, max(0, deadline-time.monotonic()))):
                if key.data == "input":
                    try:
                        count = os.write(key.fd, outgoing[sent:sent+65536])
                    except BrokenPipeError as exc:
                        raise BrokerError("trusted model child closed input") from exc
                    sent += count
                    if sent == len(outgoing):
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                else:
                    data = os.read(key.fd, 65536)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    target, bound = ((output, stdout_limit) if key.data == "output"
                                     else (errors, stderr_limit))
                    if len(target) + len(data) > bound:
                        raise BrokerError("trusted model child output byte limit")
                    target.extend(data)
        proc.wait(timeout=max(0.001, deadline-time.monotonic()))
    return bytes(output), bytes(errors)


def validate_broker_limits(limits):
    exact(limits, ("max_calls", "input_tokens", "output_tokens", "max_input_bytes",
                   "max_messages", "frame_bytes", "call_seconds"), "broker limits")
    for key in limits:
        (positive if key == "call_seconds" else integer)(limits[key], key)
    if limits["frame_bytes"] > 0xffffffff:
        raise BrokerError("frame limit exceeds protocol length field")
    return limits


class ModelBroker:
    def __init__(self, engine, context_id, phase, limits, model_spec):
        if phase not in ("train", "query") or not isinstance(context_id, str) or not context_id:
            raise BrokerError("invalid broker binding")
        validate_broker_limits(limits)
        self.spec = validate_model_spec(json.loads(canonical(model_spec)))
        self.engine, self.context_id, self.phase = engine, context_id, phase
        if getattr(engine, "kind", None) not in ("real_future_https_child", "engineering_injected_engine"):
            raise BrokerError("engine path must be explicitly classified")
        if engine.kind == "real_future_https_child" and engine.spec != self.spec:
            raise BrokerError("model engine binding mismatch")
        self.limits = dict(limits)
        self.calls = self.input_reserved = self.output_reserved = 0
        self.input_actual = self.output_actual = 0
        self.traces = []
        self._private_calls = []
        self.cancelled = threading.Event()
        self.failed = False
        self._busy = threading.Lock()

    def cancel(self):
        self.cancelled.set()
        self.engine.cancel()

    def handle(self, request):
        if not self._busy.acquire(blocking=False):
            raise BrokerError("concurrent model requests forbidden")
        try:
            return self._handle(request)
        except Exception:
            self.failed = True
            if self.traces and self.traces[-1].get("status") == "reserved":
                self.traces[-1]["status"] = "failed"
                self._private_calls[-1]["status"] = "failed"
            raise
        finally:
            self._busy.release()

    def _handle(self, request):
        if self.failed or self.cancelled.is_set():
            raise BrokerError("broker is terminal")
        exact(request, ("seq", "tool", "arguments"), "tool request")
        if type(request["seq"]) is not int or request["seq"] != self.calls:
            raise BrokerError("tool request sequence mismatch")
        if request["tool"] != "model.generate":
            raise BrokerError("unavailable tool")
        if len(encode_frame(request, self.limits["frame_bytes"]))-4 > self.limits["frame_bytes"]:
            raise BrokerError("request frame limit")
        args = request["arguments"]
        exact(args, ("messages", "max_output_tokens"), "model arguments")
        messages = args["messages"]
        if type(messages) is not list or not 1 <= len(messages) <= self.limits["max_messages"]:
            raise BrokerError("message count limit")
        for message in messages:
            exact(message, ("role", "content"), "message")
            if message["role"] not in ("system", "user", "assistant") or type(message["content"]) is not str:
                raise BrokerError("invalid message")
        byte_count = sum(len(m["content"].encode("utf-8")) + len(m["role"].encode("utf-8")) for m in messages)
        if byte_count > self.limits["max_input_bytes"]:
            raise BrokerError("message byte limit")
        bound = self.spec["token_bound"]
        reserved = (byte_count * bound["utf8_multiplier"] + bound["fixed_overhead"]
                    + len(messages)*bound["per_message_overhead"])
        output_limit = integer(args["max_output_tokens"], "max_output_tokens")
        if (self.calls >= self.limits["max_calls"] or
                self.input_reserved + reserved > self.limits["input_tokens"] or
                self.output_reserved + output_limit > self.limits["output_tokens"]):
            raise BrokerError("model budget exhausted")
        self.calls += 1
        self.input_reserved += reserved
        self.output_reserved += output_limit
        started = time.monotonic()
        trace = {"seq": request["seq"], "request_sha256": digest(request),
                 "response_sha256": None, "input_reserved": reserved,
                 "output_reserved": output_limit, "usage": None,
                 "elapsed_seconds": None, "status": "reserved"}
        self.traces.append(trace)
        private = {"seq": request["seq"], "status": "reserved",
                   "request": json.loads(canonical(request)), "response": None}
        self._private_calls.append(private)
        # Reservation is never refunded, including provider failures.
        result = self.engine.generate(messages, output_limit, reserved,
                                      self.limits["call_seconds"], self.cancelled)
        if time.monotonic()-started > self.limits["call_seconds"]:
            raise BrokerError("model call deadline exceeded")
        exact(result, ("model_revision", "text", "usage"), "model response")
        if result["model_revision"] != self.spec["model_revision"] or type(result["text"]) is not str:
            raise BrokerError("model response identity/text mismatch")
        exact(result["usage"], ("input_tokens", "output_tokens"), "model usage")
        used_in = integer(result["usage"]["input_tokens"], "input usage", 0)
        used_out = integer(result["usage"]["output_tokens"], "output usage", 0)
        if used_in > reserved or used_out > output_limit or self.cancelled.is_set():
            raise BrokerError("provider usage exceeded admitted bound/cancelled")
        self.input_actual += used_in
        self.output_actual += used_out
        response = {"seq": request["seq"], "ok": True,
                    "result": {"text": result["text"], "usage": result["usage"]}}
        encode_frame(response, self.limits["frame_bytes"])
        # Captured before delivery. This remains host-private, never a mount or
        # worker receipt. Operator capture charges its explicit metadata budget.
        private.update(status="complete", response=json.loads(canonical(response)))
        trace.update({"response_sha256": digest(response), "usage": result["usage"],
                      "elapsed_seconds": time.monotonic()-started, "status": "complete"})
        return response

    def private_transcript(self):
        """Full bounded evidence for private source/trace review, no credentials.

        At most max_calls request frames and max_calls response frames. Failed
        calls retain the dispatched request and no undelivered response. This
        does not certify absence of hidden in-memory query fitting.
        """
        return json.loads(canonical({"context_id": self.context_id, "phase": self.phase,
                    "model_revision": self.spec["model_revision"],
                    "model_spec_sha256": digest(self.spec),
                    "engine_path": self.engine.kind, "calls": self._private_calls}))

    def receipt(self):
        return {"context_id": self.context_id, "phase": self.phase,
                "engine_path": self.engine.kind, "model_spec_sha256": digest(self.spec),
                "model_revision": self.spec["model_revision"], "calls": self.calls,
                "model_child_terminal": self.engine.terminal_observed() if isinstance(self.engine, HttpsJsonEngine) else None,
                "input_tokens_reserved": self.input_reserved,
                "output_tokens_reserved": self.output_reserved,
                "input_tokens_reported": self.input_actual,
                "output_tokens_reported": self.output_actual,
                "failed": self.failed, "cancelled": self.cancelled.is_set(),
                "traces": json.loads(canonical({"traces": self.traces}))["traces"], "provider_state_qualification": False,
                "token_bound_native_qualification": False}


def _https_child():
    # This is only entered by the fixed trusted host engine. Import dependency
    # location manually for -I, avoiding cwd and candidate PYTHONPATH.
    import urllib.request
    body = sys.stdin.buffer.read()
    envelope = _decode_body(body)
    exact(envelope, ("spec", "credential", "request"), "trusted child envelope")
    spec = validate_model_spec(envelope["spec"])
    request_body = canonical(envelope["request"])
    if len(request_body) > spec["request_max_bytes"]:
        raise BrokerError("request limit")
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise BrokerError("redirect refused")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(spec["endpoint"], data=request_body,
            headers={"Authorization": "Bearer " + envelope["credential"],
                     "Content-Type": "application/json", "Accept": "application/json"},
            method="POST")
    with opener.open(request, timeout=spec["timeout_seconds"]) as response:
        if response.status != 200 or response.headers.get_content_type() != "application/json":
            raise BrokerError("unexpected model response status/content type")
        result = response.read(spec["response_max_bytes"]+1)
        if len(result) > spec["response_max_bytes"]:
            raise BrokerError("response limit")
        _decode_body(result)
        sys.stdout.buffer.write(result)
        sys.stdout.buffer.flush()


if __name__ == "__main__":
    if sys.argv[1:] != ["--https-child"]:
        raise SystemExit(2)
    try:
        _https_child()
    except Exception:
        # Never print exception text, URL headers, credentials, or response body.
        sys.stderr.write("trusted HTTPS child failed\n")
        raise SystemExit(1)
