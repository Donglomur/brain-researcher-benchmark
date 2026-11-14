"""Bounded, nonstreaming, loopback-only chat-completions provider.

Source proposal only. No networking occurs on import. Each complete() owns a new
socket; no retry, proxy, DNS hostname, auth, redirect, or cross-call transcript.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import os
import re
import socket
import stat
import time
from decimal import Decimal, InvalidOperation, localcontext

SOURCE_LIMIT = 262144
_ABS_REQUEST = 1048576
_ABS_RESPONSE = 4194304
_ABS_HEADER = 32768
_ABS_CONFIG = 262144
_ABS_MESSAGES = 512
_ABS_SCHEMA_NODES = 2048
_TOKEN = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")
_ACTION = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_HEADER = re.compile(rb"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")


class ProviderError(RuntimeError):
    """First causal error plus immutable in-memory receipt; never hides cleanup."""

    def __init__(self, first_error, receipt):
        super().__init__(first_error["code"])
        self.first_error = first_error
        self.receipt = receipt


class ProtocolError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _bad(code):
    raise ProtocolError(code)


def _keys(value, required, optional=()):
    if type(value) is not dict:
        _bad("closed_keys")
    if not set(required) <= set(value):
        _bad("missing_keys")
    if set(value) - set(required) - set(optional):
        _bad("closed_keys")


def _integer(value, minimum=0, maximum=2**53 - 1):
    if type(value) is not int or not minimum <= value <= maximum:
        _bad("integer_range")
    return value


def _finite(value, minimum=0, maximum=1e12):
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        _bad("finite_range")
    return float(value)


def _text(value, minimum=1, maximum=4096):
    if type(value) is not str or not minimum <= len(value) <= maximum:
        _bad("text_range")
    try:
        value.encode("utf-8", "strict")
    except UnicodeError:
        _bad("unicode")
    return value


def _digest(value):
    if type(value) is not str or not _HEX.fullmatch(value):
        _bad("sha256")
    return value


def canonical(value):
    """Canonical bytes, duplicate rejection is handled at JSON decoding."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8", "strict")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _bad("duplicate_json_key")
        result[key] = value
    return result


def strict_json(data):
    try:
        return json.loads(data, object_pairs_hook=_unique,
                          parse_constant=lambda _: _bad("nonfinite_json"))
    except ProtocolError:
        raise
    except (ValueError, UnicodeError, RecursionError):
        _bad("json_decode")


def _tick(deadline):
    if type(deadline) not in (int, float) or not math.isfinite(deadline):
        _bad("original_deadline_type")
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        _bad("original_deadline_exhausted")
    return remaining


def _error(exc, stage):
    # Error messages can contain user material; preserve type/code only here.
    # Raw server output and prior input remain in explicitly bounded captures.
    message = str(exc)
    return {"stage": stage, "type": type(exc).__name__,
            "code": getattr(exc, "code", type(exc).__name__),
            "message_prefix": message[:4096], "message_characters": len(message),
            "message_prefix_truncated": len(message) > 4096,
            "errno": exc.errno if isinstance(exc, OSError) else None}


def _declared_estimate(usage, rates):
    with localcontext() as context:
        context.prec = 64
        result = (Decimal(usage["prompt_tokens"]) * Decimal(rates["input_per_million"]) +
                  Decimal(usage["completion_tokens"]) * Decimal(rates["output_per_million"])) / Decimal(1000000)
        return str(result)


def _sum_declared(entries):
    with localcontext() as context:
        context.prec = 64
        return str(sum((Decimal(item["declared_rate_estimate_usd"]) for item in entries
                        if item["state"] == "settled"), Decimal(0)))


def _schema(schema, depth=0, budget=None):
    """Closed finite schema subset; reject unsupported keywords, do not ignore."""
    if budget is None:
        budget = [0]
    budget[0] += 1
    if budget[0] > _ABS_SCHEMA_NODES or depth > 16:
        _bad("schema_complexity")
    if type(schema) is not dict:
        _bad("schema_object")
    kind = schema.get("type")
    common = {"type", "description"}
    if "description" in schema:
        _text(schema["description"], 0, 8192)
    if kind == "object":
        _keys(schema, {"type", "properties", "required", "additionalProperties"}, {"description"})
        if schema["additionalProperties"] is not False or type(schema["properties"]) is not dict:
            _bad("schema_closed_object")
        props = schema["properties"]
        if len(props) > 64 or type(schema["required"]) is not list:
            _bad("schema_properties")
        if len(schema["required"]) != len(set(schema["required"])) or set(schema["required"]) != set(props):
            _bad("schema_all_properties_required")
        for key, child in props.items():
            _text(key, 1, 128)
            _schema(child, depth + 1, budget)
    elif kind == "array":
        _keys(schema, {"type", "items", "minItems", "maxItems"}, {"description"})
        minimum = _integer(schema["minItems"], 0, 1024)
        _integer(schema["maxItems"], minimum, 1024)
        _schema(schema["items"], depth + 1, budget)
    elif kind == "string":
        _keys(schema, {"type", "minLength", "maxLength"}, {"description", "enum"})
        minimum = _integer(schema["minLength"], 0, 65536)
        maximum = _integer(schema["maxLength"], minimum, 65536)
        if "enum" in schema:
            if type(schema["enum"]) is not list or not 1 <= len(schema["enum"]) <= 128:
                _bad("schema_enum")
            if len(set(schema["enum"])) != len(schema["enum"]):
                _bad("schema_enum")
            for value in schema["enum"]:
                _text(value, minimum, maximum)
    elif kind in ("integer", "number"):
        _keys(schema, {"type", "minimum", "maximum"}, {"description"})
        low = _finite(schema["minimum"], -1e12, 1e12)
        _finite(schema["maximum"], low, 1e12)
    elif kind in ("boolean", "null"):
        _keys(schema, {"type"}, {"description"})
    else:
        _bad("schema_unsupported_type")


def _validate(value, schema):
    kind = schema["type"]
    if kind == "object":
        _keys(value, schema["required"])
        for key, child in schema["properties"].items():
            _validate(value[key], child)
    elif kind == "array":
        if type(value) is not list or not schema["minItems"] <= len(value) <= schema["maxItems"]:
            _bad("action_array")
        for item in value:
            _validate(item, schema["items"])
    elif kind == "string":
        _text(value, schema["minLength"], schema["maxLength"])
        if "enum" in schema and value not in schema["enum"]:
            _bad("action_enum")
    elif kind == "integer":
        _integer(value, math.ceil(schema["minimum"]), math.floor(schema["maximum"]))
    elif kind == "number":
        _finite(value, schema["minimum"], schema["maximum"])
    elif kind == "boolean":
        if type(value) is not bool:
            _bad("action_boolean")
    elif value is not None:
        _bad("action_null")


def _bounded_json_tree(value, byte_limit, depth=0, nodes=None):
    # Prevent pathological caller structures before canonical serialization.
    if nodes is None:
        nodes = [0, 0]
    nodes[0] += 1
    if depth > 24 or nodes[0] > 16384:
        _bad("input_tree_complexity")
    if type(value) is dict:
        if len(value) > 2048:
            _bad("input_tree_width")
        for key, child in value.items():
            if type(key) is not str:
                _bad("input_tree_key")
            nodes[1] += len(key.encode("utf-8", "strict"))
            _bounded_json_tree(child, byte_limit, depth + 1, nodes)
    elif type(value) is list:
        if len(value) > 2048:
            _bad("input_tree_width")
        for child in value:
            _bounded_json_tree(child, byte_limit, depth + 1, nodes)
    elif type(value) is str:
        # UTF-8 encoding can at most quadruple codepoint length.
        if len(value) > byte_limit:
            _bad("input_string_cap")
        nodes[1] += len(value.encode("utf-8", "strict"))
    elif value is None or type(value) in (bool, int, float):
        if type(value) is int and abs(value) > 2**53 - 1:
            _bad("input_integer_cap")
        if type(value) is float and not math.isfinite(value):
            _bad("input_nonfinite")
        nodes[1] += 32
    else:
        _bad("input_json_type")
    if nodes[1] > byte_limit:
        _bad("input_tree_bytes")


def _snapshot(value, cap):
    _bounded_json_tree(value, cap)
    body = canonical(value)
    if len(body) > cap:
        _bad("input_serialized_cap")
    return strict_json(body), body


def _config(config):
    value, body = _snapshot(config, _ABS_CONFIG)
    _keys(value, {"study", "frozen_study_config_sha256", "owner", "request_id"})
    study = value["study"]
    _keys(study, {"endpoint", "model", "generation", "actions", "caps",
                  "declared_rates", "provider_source_sha256"})
    _digest(study["provider_source_sha256"])
    study_bytes = canonical(study)
    if hashlib.sha256(study_bytes).hexdigest() != _digest(value["frozen_study_config_sha256"]):
        _bad("study_config_binding")
    _keys(value["owner"], {"condition_id", "query_id"})
    for item in list(value["owner"].values()) + [value["request_id"]]:
        if type(item) is not str or not _TOKEN.fullmatch(item):
            _bad("opaque_identity")
    endpoint = study["endpoint"]
    _keys(endpoint, {"ip_literal", "port", "path"})
    literal = _text(endpoint["ip_literal"], 1, 64)
    if "%" in literal or "[" in literal or "]" in literal:
        _bad("endpoint_literal")
    try:
        address = ipaddress.ip_address(literal)
    except ValueError:
        _bad("endpoint_literal")
    if not address.is_loopback or str(address) != literal:
        _bad("endpoint_loopback_canonical")
    _integer(endpoint["port"], 1, 65535)
    path = _text(endpoint["path"], 1, 256)
    if not re.fullmatch(r"/[A-Za-z0-9_./-]+", path) or "//" in path or any(
            part in (".", "..") for part in path.split("/")):
        _bad("endpoint_path")
    _text(study["model"], 1, 160)
    gen = study["generation"]
    _keys(gen, {"temperature", "max_output_tokens", "seed"})
    _finite(gen["temperature"], 0, 2)
    _integer(gen["max_output_tokens"], 1, 32768)
    _integer(gen["seed"], 0, 2**31 - 1)
    caps = study["caps"]
    _keys(caps, {"request_bytes", "response_bytes", "header_bytes", "message_count",
                 "message_content_bytes", "action_content_bytes", "reported_prompt_tokens", "capture_bytes"})
    _integer(caps["request_bytes"], 256, _ABS_REQUEST)
    _integer(caps["response_bytes"], 256, _ABS_RESPONSE)
    _integer(caps["header_bytes"], 64, min(_ABS_HEADER, caps["response_bytes"]))
    _integer(caps["message_count"], 1, _ABS_MESSAGES)
    _integer(caps["message_content_bytes"], 1, caps["request_bytes"])
    _integer(caps["action_content_bytes"], 1, caps["response_bytes"])
    _integer(caps["reported_prompt_tokens"], 1, 1048576)
    _integer(caps["capture_bytes"], SOURCE_LIMIT + _ABS_CONFIG + 65536 +
             caps["request_bytes"] + caps["response_bytes"], 16777216)
    actions = study["actions"]
    if type(actions) is not dict or not 1 <= len(actions) <= 32:
        _bad("action_definitions")
    for name, schema in actions.items():
        if not _ACTION.fullmatch(name) or schema.get("type") != "object":
            _bad("action_name_or_arguments")
        _schema(schema)
    rates = study["declared_rates"]
    _keys(rates, {"currency", "input_per_million", "output_per_million"})
    if rates["currency"] != "USD":
        _bad("declared_currency")
    for key in ("input_per_million", "output_per_million"):
        text = _text(rates[key], 1, 32)
        if not re.fullmatch(r"(0|[1-9][0-9]{0,8})(\.[0-9]{1,12})?", text):
            _bad("declared_rate")
        try:
            number = Decimal(text)
        except InvalidOperation:
            _bad("declared_rate")
        if not number.is_finite() or number < 0:
            _bad("declared_rate")
    return value, body, address


def _request(messages, config):
    study = config["study"]
    caps = study["caps"]
    if type(messages) is not list or not 1 <= len(messages) <= caps["message_count"]:
        _bad("message_count")
    clean = []
    aggregate = 0
    for original in messages:
        _keys(original, {"role", "content"})
        if original["role"] not in ("system", "user", "assistant"):
            _bad("message_role")
        content = _text(original["content"], 0, caps["message_content_bytes"])
        aggregate += len(content.encode("utf-8", "strict"))
        if aggregate > caps["message_content_bytes"]:
            _bad("message_content_cap")
        clean.append({"role": original["role"], "content": content})
    # The exact caller-provided schemas are preserved verbatim under each branch.
    options = []
    for name, arguments in study["actions"].items():
        options.append({"type": "object", "properties": {
            "name": {"type": "string", "enum": [name]},
            "arguments": arguments}, "required": ["name", "arguments"],
            "additionalProperties": False})
    body = canonical({"model": study["model"], "messages": clean, "stream": False,
                      "n": 1, "temperature": study["generation"]["temperature"],
                      "max_tokens": study["generation"]["max_output_tokens"],
                      "seed": study["generation"]["seed"],
                      "response_format": {"type": "json_schema", "json_schema": {
                          "name": "neurobench_action", "strict": True,
                          "schema": {"type": "object", "properties": {
                              "name": {"type": "string", "enum": list(study["actions"])},
                              "arguments": {"anyOf": [item["properties"]["arguments"] for item in options]}},
                              "required": ["name", "arguments"], "additionalProperties": False}}}})
    endpoint = study["endpoint"]
    host = endpoint["ip_literal"]
    if ":" in host:
        host = "[" + host + "]"
    headers = ("POST " + endpoint["path"] + " HTTP/1.1\r\nHost: " + host + ":" +
               str(endpoint["port"]) + "\r\nContent-Type: application/json\r\n" +
               "Accept: application/json\r\nAccept-Encoding: identity\r\nConnection: close\r\n" +
               "X-Neurobench-Request-Id: " + config["request_id"] + "\r\nContent-Length: " +
               str(len(body)) + "\r\n\r\n").encode("ascii")
    wire = headers + body
    if len(wire) > caps["request_bytes"]:
        _bad("request_cap")
    return wire


class _Capture:
    def __init__(self, sink, name, limit):
        self.writer = sink.create(name, limit)
        self.name = name
        self.limit = limit
        self.count = 0
        self.hash = hashlib.sha256()
        self.closed = False
        self.actual_descriptor = None

    def append(self, data):
        if self.closed or type(data) is not bytes or self.count + len(data) > self.limit:
            _bad("capture_cap_or_state")
        amount = self.writer.append(data)
        if type(amount) is not int or amount != len(data):
            _bad("capture_short_write")
        self.count += amount
        self.hash.update(data)

    def close(self):
        if self.closed:
            _bad("capture_double_close")
        self.closed = True
        try:
            descriptor = self.writer.close()
        except BaseException as exc:
            self.actual_descriptor = getattr(exc, "capture_actual_descriptor", None)
            raise
        self.actual_descriptor = descriptor
        expected = {"name": self.name, "bytes": self.count, "sha256": self.hash.hexdigest()}
        if descriptor != expected:
            _bad("capture_descriptor_mismatch")
        return expected


class _FileWriter:
    def __init__(self, sink, name, fd, limit):
        self.sink, self.name, self.fd, self.limit = sink, name, fd, limit
        self.count = 0
        self.hash = hashlib.sha256()

    def append(self, data):
        if self.fd is None or type(data) is not bytes or self.count + len(data) > self.limit:
            _bad("file_capture_cap_or_state")
        view = memoryview(data)
        while view:
            amount = os.write(self.fd, view)
            if amount <= 0:
                _bad("file_capture_short_write")
            self.hash.update(view[:amount])
            self.count += amount
            view = view[amount:]
        return len(data)

    def close(self):
        if self.fd is None:
            _bad("file_capture_closed")
        fd, self.fd = self.fd, None
        first = None
        try:
            os.fsync(fd)
        except BaseException as exc:
            first = exc
        try:
            os.close(fd)
        except BaseException as exc:
            if first is None:
                first = exc
            else:
                self.sink.close_errors.append(_error(exc, "capture_fd_close"))
        if first is not None:
            first.capture_actual_descriptor = {
                "name": self.name, "bytes": self.count, "sha256": self.hash.hexdigest()}
            raise first
        return {"name": self.name, "bytes": self.count, "sha256": self.hash.hexdigest()}


class DirectoryCaptureSink:
    """Create-only bytes in a caller-owned existing directory, never overwrites.

    Caller closes this sink after complete() and preserves any sink close error.
    max_total_bytes is reserved at create time, including failed captures.
    Trusted parent path components must already be admitted by the outer caller.
    """
    def __init__(self, root, max_bytes):
        _integer(max_bytes, 1, 16777216)
        self.fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        self.remaining = max_bytes
        self.names = set()
        self.close_errors = []

    def create(self, name, limit):
        if self.fd is None or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,220}", name):
            _bad("capture_name_or_state")
        _integer(limit, 0, 8388608)
        if name in self.names or limit > self.remaining:
            _bad("capture_reservation")
        self.names.add(name)
        self.remaining -= limit
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW |
                     os.O_CLOEXEC, 0o600, dir_fd=self.fd)
        return _FileWriter(self, name, fd, limit)

    def close(self):
        if self.fd is None:
            _bad("sink_closed")
        fd, self.fd = self.fd, None
        os.close(fd)


class TokenCostCollector:
    """Study-owned synchronous ledger; unknown output reservations are retained.

    No CPU meter or billing API is used. Estimated dollars use declared rates.
    This class must be owned by one serial actor; cross-process budgets belong
    to the outer controller. No token estimate is presented as a measured bill.
    """
    def __init__(self, input_token_budget, output_token_budget, request_budget):
        self.input_token_budget = _integer(input_token_budget, 0, 2**53 - 1)
        self.output_token_budget = _integer(output_token_budget, 0, 2**53 - 1)
        self.request_budget = _integer(request_budget, 0, 1048576)
        self.entries = {}
        self._charged_input_tokens = 0
        self._charged_output_tokens = 0

    def reserve(self, request_id, owner, max_input_tokens, max_output_tokens, request_binding):
        _integer(max_input_tokens, 1, 1048576)
        _integer(max_output_tokens, 1, 32768)
        _digest(request_binding)
        _keys(owner, {"condition_id", "query_id"})
        for value in list(owner.values()) + [request_id]:
            if type(value) is not str or not _TOKEN.fullmatch(value):
                _bad("collector_identity")
        if request_id in self.entries or len(self.entries) >= self.request_budget:
            _bad("request_budget_or_reuse")
        charged = self._charged_output_tokens
        charged_input = self._charged_input_tokens
        if charged_input + max_input_tokens > self.input_token_budget:
            _bad("input_token_reservation")
        if charged + max_output_tokens > self.output_token_budget:
            _bad("output_token_reservation")
        entry = {"request_id": request_id, "owner": dict(owner), "request_binding": request_binding,
                 "reserved_output_tokens": max_output_tokens,
                 "reserved_input_tokens": max_input_tokens,
                 "charged_input_tokens": max_input_tokens,
                 "charged_output_tokens": max_output_tokens, "state": "reserved",
                 "usage": None, "declared_rate_estimate_usd": None}
        self.entries[request_id] = entry
        self._charged_input_tokens += max_input_tokens
        self._charged_output_tokens += max_output_tokens
        return request_id

    def settle(self, reservation, owner, request_binding, usage, declared_rates):
        entry = self.entries[reservation]
        if (entry["state"] != "reserved" or entry["owner"] != owner or
                entry["request_binding"] != request_binding or
                usage["completion_tokens"] > entry["reserved_output_tokens"] or
                usage["prompt_tokens"] > entry["reserved_input_tokens"]):
            _bad("usage_binding")
        _integer(usage["prompt_tokens"], 0, entry["reserved_input_tokens"])
        _integer(usage["completion_tokens"], 0, entry["reserved_output_tokens"])
        if _integer(usage["total_tokens"]) != usage["prompt_tokens"] + usage["completion_tokens"]:
            _bad("collector_usage_sum")
        estimate = _declared_estimate(usage, declared_rates)
        next_input = self._charged_input_tokens - entry["charged_input_tokens"] + usage["prompt_tokens"]
        next_output = self._charged_output_tokens - entry["charged_output_tokens"] + usage["completion_tokens"]
        entry.update(state="settled", charged_output_tokens=usage["completion_tokens"],
                     charged_input_tokens=usage["prompt_tokens"],
                     usage=strict_json(canonical(usage)),
                     declared_rate_estimate_usd=estimate)
        self._charged_input_tokens = next_input
        self._charged_output_tokens = next_output
        return strict_json(canonical(entry))

    def mark_unknown(self, reservation, owner, request_binding):
        entry = self.entries[reservation]
        if entry["owner"] != owner or entry["request_binding"] != request_binding:
            _bad("unknown_binding")
        if entry["state"] == "reserved":
            entry["state"] = "unknown"
        return strict_json(canonical(entry))

    def snapshot(self):
        # One final fold, with independent reconciliation of maintained counters.
        result = {"input_token_budget": self.input_token_budget,
                  "output_token_budget": self.output_token_budget,
                  "request_budget": self.request_budget, "request_count": len(self.entries),
                  "charged_input_tokens": 0, "charged_output_tokens": 0,
                  "validated_reported_input_tokens": 0, "validated_reported_output_tokens": 0,
                  "unsettled_reserved_input_tokens": 0, "unsettled_reserved_output_tokens": 0,
                  "declared_rate_estimate_usd": "0", "observed_billing": None,
                  "observed_cpu": None, "entries": []}
        with localcontext() as context:
            context.prec = 64
            estimate = Decimal(0)
            for entry in self.entries.values():
                result["entries"].append(entry)
                result["charged_input_tokens"] += entry["charged_input_tokens"]
                result["charged_output_tokens"] += entry["charged_output_tokens"]
                if entry["state"] == "settled":
                    result["validated_reported_input_tokens"] += entry["usage"]["prompt_tokens"]
                    result["validated_reported_output_tokens"] += entry["usage"]["completion_tokens"]
                    estimate += Decimal(entry["declared_rate_estimate_usd"])
                elif entry["state"] in ("reserved", "unknown"):
                    result["unsettled_reserved_input_tokens"] += entry["reserved_input_tokens"]
                    result["unsettled_reserved_output_tokens"] += entry["reserved_output_tokens"]
                else:
                    _bad("collector_state_invariant")
            result["declared_rate_estimate_usd"] = str(estimate)
        if (result["charged_input_tokens"] != self._charged_input_tokens or
                result["charged_output_tokens"] != self._charged_output_tokens):
            _bad("collector_counter_invariant")
        return strict_json(canonical(result))


def _own_source(expected, capture):
    fd = None
    first = None
    cleanup = []
    body = None
    try:
        fd = os.open(__file__, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= SOURCE_LIMIT:
            _bad("provider_source_shape")
        parts = []
        remaining = info.st_size
        while remaining:
            part = os.read(fd, min(65536, remaining))
            if not part:
                _bad("provider_source_short_read")
            capture.append(part)
            parts.append(part)
            remaining -= len(part)
        after = os.fstat(fd)
        if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) != (
                info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns):
            _bad("provider_source_changed")
        body = b"".join(parts)
        if hashlib.sha256(body).hexdigest() != expected:
            _bad("provider_source_binding")
    except BaseException as exc:
        first = exc
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except BaseException as exc:
                if first is None:
                    first = exc
                else:
                    cleanup.append(_error(exc, "provider_source_close"))
    if first is not None:
        first.provider_cleanup_errors = cleanup
        raise first
    return body


def _headers(raw, caps):
    if len(raw) > caps["header_bytes"]:
        _bad("http_header_cap")
    lines = raw[:-4].split(b"\r\n")
    if not lines or not re.fullmatch(rb"HTTP/1\.1 [0-9]{3} [\x20-\x7e]*", lines[0]):
        _bad("http_status_line")
    status = int(lines[0].split(b" ", 2)[1])
    fields = {}
    for line in lines[1:]:
        if b":" not in line:
            _bad("http_header_line")
        name, value = line.split(b":", 1)
        name = name.lower()
        if not _HEADER.fullmatch(name) or name in fields:
            _bad("http_header_duplicate_or_name")
        value = value.strip(b" \t")
        if any(byte < 32 or byte > 126 for byte in value):
            _bad("http_header_value")
        fields[name] = value
    if status != 200:
        _bad("http_status_" + str(status))
    if any(name in fields for name in (b"transfer-encoding", b"content-encoding",
                                      b"location", b"www-authenticate", b"proxy-authenticate")):
        _bad("http_unsupported_encoding_redirect_auth")
    if not re.fullmatch(rb"0|[1-9][0-9]{0,9}", fields.get(b"content-length", b"")):
        _bad("http_content_length")
    length = int(fields[b"content-length"])
    if len(raw) + length > caps["response_bytes"]:
        _bad("http_response_declared_cap")
    content_type = fields.get(b"content-type", b"").lower().replace(b" ", b"")
    if content_type not in (b"application/json", b"application/json;charset=utf-8"):
        _bad("http_content_type")
    return length


def _wire_response(sock, capture, caps, deadline):
    prefix = bytearray()
    boundary = -1
    while boundary < 0:
        allowance = caps["header_bytes"] - len(prefix)
        if allowance <= 0:
            _bad("http_header_cap")
        sock.settimeout(_tick(deadline))
        chunk = sock.recv(min(4096, allowance))
        if not chunk:
            _bad("http_header_eof")
        capture.append(chunk)
        prefix.extend(chunk)
        boundary = prefix.find(b"\r\n\r\n")
    end = boundary + 4
    body_length = _headers(bytes(prefix[:end]), caps)
    body = bytearray(prefix[end:])
    if len(body) > body_length:
        _bad("http_trailing_bytes")
    while len(body) < body_length:
        sock.settimeout(_tick(deadline))
        chunk = sock.recv(min(65536, body_length - len(body)))
        if not chunk:
            _bad("http_body_eof")
        capture.append(chunk)
        body.extend(chunk)
    _tick(deadline)
    return bytes(body), {"header_bytes": end, "body_bytes": body_length,
                         "framing_complete": True, "peer_eof_observed": False}


def _envelope(body, study, receipt):
    response = strict_json(body)
    _keys(response, {"id", "object", "created", "model", "choices", "usage"},
          {"system_fingerprint", "service_tier"})
    _text(response["id"], 1, 256)
    if response["object"] != "chat.completion" or response["model"] != study["model"]:
        _bad("response_object_or_model")
    _integer(response["created"])
    if "system_fingerprint" in response and response["system_fingerprint"] is not None:
        _text(response["system_fingerprint"], 1, 256)
    if "service_tier" in response and response["service_tier"] is not None:
        _text(response["service_tier"], 1, 64)
    choices = response["choices"]
    if type(choices) is not list or len(choices) != 1:
        _bad("response_choices")
    choice = choices[0]
    _keys(choice, {"index", "message", "finish_reason"}, {"logprobs"})
    if type(choice["index"]) is not int or choice["index"] != 0:
        _bad("response_choice_index")
    if "logprobs" in choice and choice["logprobs"] is not None:
        _bad("response_logprobs")
    usage = response["usage"]
    usage_body = canonical(usage)
    receipt["decoded_unvalidated_usage"] = {
        "bytes": len(usage_body), "sha256": hashlib.sha256(usage_body).hexdigest(),
        "counters": {key: (value if type(value) is int and abs(value) <= 2**53 - 1 else
                           {"type": type(value).__name__})
                     for key, value in usage.items() if key in
                     ("prompt_tokens", "completion_tokens", "total_tokens")}
        if type(usage) is dict else {"type": type(usage).__name__}}
    _keys(usage, {"prompt_tokens", "completion_tokens", "total_tokens"},
          {"prompt_tokens_details", "completion_tokens_details"})
    prompt = _integer(usage["prompt_tokens"], 0, study["caps"]["reported_prompt_tokens"])
    completion = _integer(usage["completion_tokens"], 0, study["generation"]["max_output_tokens"])
    if _integer(usage["total_tokens"]) != prompt + completion:
        _bad("usage_sum")
    for field, allowed, maximum in (
        ("prompt_tokens_details", {"cached_tokens", "audio_tokens"}, prompt),
        ("completion_tokens_details", {"reasoning_tokens", "audio_tokens",
                                       "accepted_prediction_tokens", "rejected_prediction_tokens"}, completion),
    ):
        if field in usage:
            details = usage[field]
            if type(details) is not dict or not set(details) <= allowed:
                _bad("usage_details")
            for value in details.values():
                _integer(value, 0, maximum)
    return response, choice, usage


def _action(choice, study):
    if choice["finish_reason"] != "stop":
        _bad("response_finish_reason")
    message = choice["message"]
    _keys(message, {"role", "content"}, {"refusal", "tool_calls"})
    if message["role"] != "assistant" or message.get("refusal") is not None or message.get("tool_calls") not in (None, []):
        _bad("response_assistant_kind")
    content = _text(message["content"], 1, study["caps"]["action_content_bytes"])
    if len(content.encode("utf-8", "strict")) > study["caps"]["action_content_bytes"]:
        _bad("action_content_cap")
    action = strict_json(content)
    _keys(action, {"name", "arguments"})
    if type(action["name"]) is not str or action["name"] not in study["actions"]:
        _bad("action_unknown")
    _validate(action["arguments"], study["actions"][action["name"]])
    return {"role": "assistant", "content": content}, action


def complete(messages, config, original_deadline, capture_sink, cost_collector):
    """One request on one fresh socket, preserving its original absolute deadline.

    capture_sink.create(name, limit) -> writer with append(bytes)->exact count
    and close()->{name,bytes,sha256}. See concrete DirectoryCaptureSink.
    cost_collector exposes reserve/settle/mark_unknown as TokenCostCollector.
    Caller owns both capabilities and must preserve ProviderError.receipt.
    """
    receipt = {"schema": "neurobench-loopback-provider-receipt-v1", "outcome": "error",
               "first_error": None, "cleanup_errors": [], "captures": {},
               "dispatch_attempted": False, "socket_created": False, "socket_closed": False,
               "reported_usage": None, "cost": None, "observed_billing": None,
               "observed_cpu": None, "http": None, "original_deadline": original_deadline}
    captures = []
    sock = None
    reservation = None
    settled = False
    result = None
    stage = "deadline"
    receipt_capture = None
    config_copy = None
    binding = None
    try:
        _tick(original_deadline)
        stage = "configuration"
        config_copy, config_body, address = _config(config)
        study = config_copy["study"]
        receipt["owner"] = config_copy["owner"]
        receipt["request_id"] = config_copy["request_id"]
        receipt["frozen_study_config_sha256"] = config_copy["frozen_study_config_sha256"]
        prefix = config_copy["request_id"] + "."
        # Open the receipt first, so downstream refusals can be retained.
        receipt_capture = _Capture(capture_sink, prefix + "receipt.json", 65536)
        stage = "source"
        config_capture = _Capture(capture_sink, prefix + "config.json", _ABS_CONFIG)
        captures.append(config_capture)
        config_capture.append(config_body)
        source_capture = _Capture(capture_sink, prefix + "provider.py", SOURCE_LIMIT)
        captures.append(source_capture)
        _own_source(study["provider_source_sha256"], source_capture)
        _tick(original_deadline)
        stage = "request"
        wire = _request(messages, config_copy)
        request_capture = _Capture(capture_sink, prefix + "request.http", study["caps"]["request_bytes"])
        captures.append(request_capture)
        request_capture.append(wire)
        request_sha256 = hashlib.sha256(wire).hexdigest()
        binding = hashlib.sha256(canonical({
            "owner": config_copy["owner"], "request_id": config_copy["request_id"],
            "request_sha256": request_sha256,
            "study_sha256": config_copy["frozen_study_config_sha256"],
            "provider_source_sha256": study["provider_source_sha256"]})).hexdigest()
        receipt["request_sha256"] = request_sha256
        receipt["request_binding"] = binding
        raw_capture = _Capture(capture_sink, prefix + "response.http-prefix", study["caps"]["response_bytes"])
        captures.append(raw_capture)
        # Close input captures successfully before reserving or dispatching.
        stage = "input_capture_close"
        for item in captures[:-1]:
            receipt["captures"][item.name] = item.close()
        _tick(original_deadline)
        stage = "reservation"
        reservation = cost_collector.reserve(config_copy["request_id"], config_copy["owner"],
                                              study["caps"]["reported_prompt_tokens"],
                                              study["generation"]["max_output_tokens"], binding)
        stage = "socket_create"
        family = socket.AF_INET if address.version == 4 else socket.AF_INET6
        sock = socket.socket(family, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        receipt["socket_created"] = True
        stage = "connect"
        sock.settimeout(_tick(original_deadline))
        # Canonical validated IP literals take the numeric address path; no DNS.
        receipt["dispatch_attempted"] = True
        endpoint = study["endpoint"]
        destination = ((endpoint["ip_literal"], endpoint["port"]) if address.version == 4 else
                       (endpoint["ip_literal"], endpoint["port"], 0, 0))
        sock.connect(destination)
        stage = "send"
        view = memoryview(wire)
        while view:
            sock.settimeout(_tick(original_deadline))
            amount = sock.send(view)
            if type(amount) is not int or not 1 <= amount <= len(view):
                _bad("socket_send_progress")
            view = view[amount:]
        stage = "response"
        body, receipt["http"] = _wire_response(sock, raw_capture, study["caps"], original_deadline)
        stage = "usage"
        response, choice, usage = _envelope(body, study, receipt)
        receipt["response_id"] = response["id"]
        receipt["reported_usage"] = usage
        receipt["cost"] = cost_collector.settle(reservation, config_copy["owner"], binding,
                                               usage, study["declared_rates"])
        settled = True
        stage = "action"
        message, action = _action(choice, study)
        _tick(original_deadline)
        result = {"message": message, "action": action}
    except BaseException as exc:
        receipt["first_error"] = _error(exc, stage)
        receipt["cleanup_errors"].extend(getattr(exc, "provider_cleanup_errors", []))
        for item in captures:
            if item.closed and item.name not in receipt["captures"] and item.actual_descriptor is not None:
                receipt.setdefault("unconfirmed_capture_descriptors", {})[item.name] = item.actual_descriptor
    finally:
        if sock is not None:
            try:
                sock.close()
                receipt["socket_closed"] = True
            except BaseException as exc:
                error = _error(exc, "socket_close")
                if receipt["first_error"] is None:
                    receipt["first_error"] = error
                else:
                    receipt["cleanup_errors"].append(error)
        if reservation is not None and not settled:
            try:
                receipt["cost"] = cost_collector.mark_unknown(reservation, config_copy["owner"], binding)
            except BaseException as exc:
                error = _error(exc, "cost_mark_unknown")
                if receipt["first_error"] is None:
                    receipt["first_error"] = error
                else:
                    receipt["cleanup_errors"].append(error)
        for item in captures:
            if not item.closed:
                try:
                    receipt["captures"][item.name] = item.close()
                except BaseException as exc:
                    if item.actual_descriptor is not None:
                        receipt.setdefault("unconfirmed_capture_descriptors", {})[item.name] = item.actual_descriptor
                    error = _error(exc, "capture_close:" + item.name)
                    if receipt["first_error"] is None:
                        receipt["first_error"] = error
                    else:
                        receipt["cleanup_errors"].append(error)
        receipt["cleanup_errors"].extend(getattr(capture_sink, "close_errors", []))
        sink_cleanup_seen = len(getattr(capture_sink, "close_errors", []))
        try:
            receipt["deadline_remaining_at_finalize"] = _tick(original_deadline)
        except BaseException as exc:
            error = _error(exc, "final_original_deadline")
            if receipt["first_error"] is None:
                receipt["first_error"] = error
            else:
                receipt["cleanup_errors"].append(error)
        receipt["outcome"] = "complete" if result is not None and receipt["first_error"] is None else "error"
        if receipt_capture is not None:
            try:
                # Receipt descriptor cannot be included in its own bytes.
                receipt_capture.append(canonical(receipt))
            except BaseException as exc:
                error = _error(exc, "receipt_write")
                if receipt["first_error"] is None:
                    receipt["first_error"] = error
                else:
                    receipt["cleanup_errors"].append(error)
            try:
                receipt["receipt_capture"] = receipt_capture.close()
            except BaseException as exc:
                if receipt_capture.actual_descriptor is not None:
                    receipt.setdefault("unconfirmed_capture_descriptors", {})[receipt_capture.name] = receipt_capture.actual_descriptor
                error = _error(exc, "receipt_close")
                if receipt["first_error"] is None:
                    receipt["first_error"] = error
                else:
                    receipt["cleanup_errors"].append(error)
        # Receipt publication can exhaust the original deadline too. Such a
        # failure is present in the returned error; the caller must preserve it.
        receipt["cleanup_errors"].extend(getattr(capture_sink, "close_errors", [])[sink_cleanup_seen:])
        try:
            _tick(original_deadline)
        except BaseException as exc:
            error = _error(exc, "postpublication_original_deadline")
            if receipt["first_error"] is None:
                receipt["first_error"] = error
            else:
                receipt["cleanup_errors"].append(error)
    if receipt["first_error"] is not None:
        receipt["outcome"] = "error"
        raise ProviderError(receipt["first_error"], receipt)
    result["receipt"] = receipt
    return result


def validate_receipt(receipt, config, expected_owner, captured_artifact_reader):
    """Pure bounded source/HTTP/action/cost coherence check; never contacts server.

    Reader(descriptor, limit) must return exact bytes from an externally admitted
    immutable capture root. This verifies hashes and content again. It returns
    captured input messages for the outer actor to compare with its own transcript.
    It does not attest that local artifacts were produced by a real model, that a
    model is scientifically qualified, or that a historical clock is trustworthy.
    """
    _keys(receipt, {"schema", "outcome", "first_error", "cleanup_errors", "captures",
                   "dispatch_attempted", "socket_created", "socket_closed", "reported_usage",
                   "cost", "observed_billing", "observed_cpu", "http", "original_deadline",
                   "owner", "request_id", "frozen_study_config_sha256", "request_sha256",
                   "request_binding", "decoded_unvalidated_usage", "response_id",
                   "deadline_remaining_at_finalize", "receipt_capture"})
    cfg, config_body, _ = _config(config)
    study = cfg["study"]
    _keys(expected_owner, {"condition_id", "query_id"})
    if expected_owner != cfg["owner"] or receipt.get("owner") != expected_owner:
        _bad("receipt_owner_binding")
    if receipt.get("request_id") != cfg["request_id"] or receipt.get("frozen_study_config_sha256") != cfg["frozen_study_config_sha256"]:
        _bad("receipt_configuration_binding")
    if (receipt.get("schema") != "neurobench-loopback-provider-receipt-v1" or
            receipt.get("outcome") != "complete" or receipt.get("first_error") is not None or
            receipt.get("cleanup_errors") != [] or receipt.get("dispatch_attempted") is not True or
            receipt.get("socket_created") is not True or receipt.get("socket_closed") is not True or
            receipt.get("observed_billing") is not None or receipt.get("observed_cpu") is not None):
        _bad("receipt_not_complete")
    if type(receipt.get("original_deadline")) not in (float, int) or not math.isfinite(receipt["original_deadline"]):
        _bad("receipt_original_deadline")
    _finite(receipt.get("deadline_remaining_at_finalize"), 1e-15, 1e12)
    prefix = cfg["request_id"] + "."
    captures = receipt.get("captures")
    expected_names = {prefix + x for x in ("provider.py", "config.json", "request.http", "response.http-prefix")}
    if type(captures) is not dict or set(captures) != expected_names:
        _bad("receipt_capture_set")

    def read(descriptor, name, cap):
        _keys(descriptor, {"name", "bytes", "sha256"})
        if descriptor["name"] != name:
            _bad("receipt_capture_name")
        _integer(descriptor["bytes"], 0, cap)
        _digest(descriptor["sha256"])
        body = captured_artifact_reader(dict(descriptor), cap)
        if type(body) is not bytes or len(body) != descriptor["bytes"] or hashlib.sha256(body).hexdigest() != descriptor["sha256"]:
            _bad("receipt_capture_content")
        return body

    source = read(captures[prefix + "provider.py"], prefix + "provider.py", SOURCE_LIMIT)
    if hashlib.sha256(source).hexdigest() != study["provider_source_sha256"]:
        _bad("receipt_provider_source")
    actual_config = read(captures[prefix + "config.json"], prefix + "config.json", _ABS_CONFIG)
    if actual_config != config_body:
        _bad("receipt_config_content")
    request = read(captures[prefix + "request.http"], prefix + "request.http", study["caps"]["request_bytes"])
    pieces = request.split(b"\r\n\r\n", 1)
    if len(pieces) != 2:
        _bad("receipt_request_framing")
    payload = strict_json(pieces[1])
    if type(payload) is not dict or "messages" not in payload:
        _bad("receipt_request_payload")
    if _request(payload["messages"], cfg) != request:
        _bad("receipt_request_content")
    request_hash = hashlib.sha256(request).hexdigest()
    binding = hashlib.sha256(canonical({
        "owner": cfg["owner"], "request_id": cfg["request_id"], "request_sha256": request_hash,
        "study_sha256": cfg["frozen_study_config_sha256"],
        "provider_source_sha256": study["provider_source_sha256"]})).hexdigest()
    if receipt.get("request_sha256") != request_hash or receipt.get("request_binding") != binding:
        _bad("receipt_request_binding")
    raw = read(captures[prefix + "response.http-prefix"], prefix + "response.http-prefix", study["caps"]["response_bytes"])
    boundary = raw.find(b"\r\n\r\n")
    if boundary < 0:
        _bad("receipt_response_header")
    end = boundary + 4
    length = _headers(raw[:end], study["caps"])
    if end + length != len(raw):
        _bad("receipt_response_length")
    expected_http = {"header_bytes": end, "body_bytes": length, "framing_complete": True, "peer_eof_observed": False}
    if receipt.get("http") != expected_http:
        _bad("receipt_http_observation")
    decoded = {}
    response, choice, usage = _envelope(raw[end:], study, decoded)
    message, action = _action(choice, study)
    if (receipt.get("response_id") != response["id"] or receipt.get("reported_usage") != usage or
            receipt.get("decoded_unvalidated_usage") != decoded["decoded_unvalidated_usage"]):
        _bad("receipt_usage_content")
    rates = study["declared_rates"]
    estimate = _declared_estimate(usage, rates)
    expected_entry = {"request_id": cfg["request_id"], "owner": cfg["owner"], "request_binding": binding,
                      "reserved_input_tokens": study["caps"]["reported_prompt_tokens"],
                      "reserved_output_tokens": study["generation"]["max_output_tokens"],
                      "charged_input_tokens": usage["prompt_tokens"],
                      "charged_output_tokens": usage["completion_tokens"], "state": "settled",
                      "usage": usage, "declared_rate_estimate_usd": estimate}
    if receipt.get("cost") != expected_entry:
        _bad("receipt_cost_entry")
    receipt_body = read(receipt.get("receipt_capture"), prefix + "receipt.json", 65536)
    without_self = {key: value for key, value in receipt.items() if key != "receipt_capture"}
    if receipt_body != canonical(without_self):
        _bad("receipt_self_capture")
    return {"owner": cfg["owner"], "request_id": cfg["request_id"], "request_binding": binding,
            "message": message, "action": action, "usage": usage, "cost_entry": expected_entry,
            "input_messages": payload["messages"], "frozen_study_config_sha256": cfg["frozen_study_config_sha256"]}



