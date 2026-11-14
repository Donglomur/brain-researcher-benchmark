"""One source-owned N006 OpenAI Responses request; no candidate code or retry.

This executable is a trusted host worker. The parent authenticates its source and
the live root authorization, owns the process group and hard absolute deadline,
and charges cumulative reservations before starting it. This worker never grants
live authority from an untrusted candidate message or from a digest alone.
"""
import base64
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import re
import ssl
import stat
import sys
import time

ENDPOINT = {"scheme": "https", "host": "api.openai.com", "port": 443, "path": "/v1/responses"}
ENVELOPE_KEYS = {"schema", "request_id", "deadline", "config", "input"}
EXPECTED_CONFIG_KEYS = {"endpoint", "model", "parameters", "credential", "token_bound", "limits", "bindings"}
LIMIT_KEYS = {"request_bytes", "response_bytes", "result_bytes", "input_tokens", "output_tokens", "total_tokens", "timeout_seconds"}
BINDING_KEYS = {"adapter_sha256", "source_sha256", "prompt_sha256", "config_sha256", "qualification_sha256"}
TOKEN_BOUND_KEYS = {"model", "source_sha256", "qualification_sha256", "per_utf8_byte", "overhead_tokens"}
CREDENTIAL_KEYS = {"path", "device", "inode", "uid", "mode", "bytes", "mtime_ns", "ctime_ns"}
MAX_ENVELOPE_BYTES = 16 * 1024 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_RESULT_BYTES = 16 * 1024 * 1024
MAX_ITEMS = 4096
MAX_READ_OBSERVATIONS = 256

class Refusal(ValueError):
    pass

def need(ok, code):
    if not ok:
        raise Refusal(code)

def keys(value, expected, code):
    need(type(value) is dict and set(value) == set(expected), code)

def integer(value, minimum=0, maximum=2**63 - 1):
    need(type(value) is int and minimum <= value <= maximum, "integer_range")

def finite(value):
    return type(value) in (int, float) and math.isfinite(value)

def pin(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None

def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")

def digest(body):
    return hashlib.sha256(body).hexdigest()

def parse(body):
    def pairs(items):
        result = {}
        for name, value in items:
            need(name not in result, "duplicate_json_key")
            result[name] = value
        return result
    value = json.loads(body, object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(Refusal("nonfinite_json")))
    def visit(item, depth=0):
        need(depth <= 64, "json_depth")
        if type(item) is float:
            need(math.isfinite(item), "nonfinite_json")
        elif type(item) is str:
            need(not any(0xD800 <= ord(c) <= 0xDFFF for c in item), "unicode_scalar")
        elif type(item) is list:
            for child in item:
                visit(child, depth + 1)
        elif type(item) is dict:
            for name, child in item.items():
                visit(name, depth + 1)
                visit(child, depth + 1)
    visit(value)
    return value

def opaque_error(errors, phase, error):
    # Never stringify an exception: HTTP, JSON and credential errors can contain
    # private request bodies or key bytes. Preserve primary/secondary order.
    errors.append({"phase": phase, "class": type(error).__name__,
                   "code": str(error) if type(error) is Refusal else "opaque_failure"})

def remaining(deadline, timeout):
    need(finite(deadline) and finite(timeout) and timeout > 0, "finite_original_deadline")
    left = deadline - time.monotonic()
    need(left > 0, "original_deadline_expired")
    return min(left, timeout)

def selected_model(value):
    need(type(value) is str and 0 < len(value) <= 256 and
         all(32 < ord(c) < 127 for c in value), "explicit_model_snapshot")
    return value

def credential_metadata(value):
    keys(value, CREDENTIAL_KEYS, "credential_metadata_fields")
    name = value["path"]
    need(type(name) is str and name.startswith("/") and "\0" not in name, "absolute_private_credential")
    path = Path(name)
    need(str(path) == name and ".." not in path.parts, "canonical_private_credential")
    for name in CREDENTIAL_KEYS - {"path"}:
        integer(value[name])
    integer(value["bytes"], 1, 16384)
    need(value["mode"] == 0o600, "owner_only_credential")
    return value

def credential_stamp(value):
    return (value.st_dev, value.st_ino, value.st_uid, stat.S_IMODE(value.st_mode),
            value.st_size, value.st_mtime_ns, value.st_ctime_ns)

def read_credential(selected, deadline, timeout, observation, errors):
    """Selected file only: no discovery, environment fallback or content hash."""
    fd = None
    raw = bytearray()
    key = None
    primary = len(errors)
    path = Path(selected["path"])
    try:
        remaining(deadline, timeout)
        need(all(not p.is_symlink() for p in (path, *path.parents)), "credential_symlink")
        observation["read_attempted"] = True
        before = path.lstat()
        expected = tuple(selected[k] for k in ("device", "inode", "uid", "mode", "bytes", "mtime_ns", "ctime_ns"))
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             credential_stamp(before) == expected and before.st_uid == os.getuid(), "credential_identity")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        opened = os.fstat(fd)
        need(stat.S_ISREG(opened.st_mode) and opened.st_nlink == 1 and
             credential_stamp(opened) == expected, "credential_open_identity")
        while len(raw) < selected["bytes"]:
            remaining(deadline, timeout)
            block = os.read(fd, min(4096, selected["bytes"] - len(raw)))
            observation["read_bytes"] += len(block)
            need(block, "credential_short_read")
            raw.extend(block)
        remaining(deadline, timeout)
        probe = os.read(fd, 1)
        observation["read_bytes"] += len(probe)
        need(not probe, "credential_growth")
        need(credential_stamp(os.fstat(fd)) == expected == credential_stamp(path.lstat()), "credential_changed")
        need(all(c in b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-" for c in raw),
             "credential_opaque_format")
        key = bytes(raw).decode("ascii")
    except BaseException as error:
        opaque_error(errors, "credential", error)
    finally:
        for index in range(len(raw)):
            raw[index] = 0
        if fd is not None:
            observation["close_attempted"] = True
            try:
                os.close(fd)
                observation["closed"] = True
            except BaseException as error:
                opaque_error(errors, "credential_close", error)
    if len(errors) != primary:
        key = None
    return key

def output_items(items, *, require_text):
    need(type(items) is list and 1 <= len(items) <= MAX_ITEMS, "complete_provider_output")
    ids = set()
    texts = []
    for item in items:
        need(type(item) is dict, "provider_output_item")
        identity = item.get("id")
        need(type(identity) is str and identity and identity not in ids, "unique_provider_item")
        ids.add(identity)
        kind = item.get("type")
        if kind == "reasoning":
            need(type(item.get("encrypted_content")) is str and item["encrypted_content"],
                 "complete_encrypted_reasoning")
            need(item.get("status") in (None, "completed"), "complete_reasoning_item")
        elif kind == "message":
            need(item.get("role") == "assistant" and item.get("status") == "completed" and
                 type(item.get("content")) is list, "complete_assistant_item")
            for block in item["content"]:
                need(type(block) is dict, "assistant_content")
                need(block.get("type") != "refusal", "provider_refusal")
                need(block.get("type") == "output_text" and type(block.get("text")) is str,
                     "only_plain_output_text")
                texts.append(block["text"])
        else:
            raise Refusal("provider_tool_or_unknown_output_forbidden")
    text = "".join(texts)
    if require_text:
        need(bool(text), "nonempty_model_action_text")
    return text

def validate_input(items, bindings):
    need(type(items) is list and 2 <= len(items) <= MAX_ITEMS, "bounded_complete_input")
    first = items[0]
    keys(first, {"role", "content"}, "selected_developer_fields")
    need(first["role"] == "developer" and type(first["content"]) is str and
         digest(first["content"].encode("utf-8")) == bindings["prompt_sha256"], "selected_developer_prompt")
    need(type(items[1]) is dict and items[1].get("role") == "user" and
         "type" not in items[1], "initial_task_message")
    previous_ids = set()
    for item in items[1:]:
        need(type(item) is dict, "input_item")
        if "type" not in item:
            keys(item, {"role", "content"}, "host_message_fields")
            need(item["role"] == "user" and type(item["content"]) is str, "host_plain_task_message")
        else:
            output_items([item], require_text=False)
            need(item["id"] not in previous_ids, "same_case_provider_item_replay")
            previous_ids.add(item["id"])

def validate(envelope):
    keys(envelope, ENVELOPE_KEYS, "provider_envelope_fields")
    need(envelope["schema"] == "n006-provider-request-v1", "provider_envelope_schema")
    need(type(envelope["request_id"]) is str and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", envelope["request_id"]),
         "operator_request_id")
    need(finite(envelope["deadline"]), "absolute_monotonic_deadline")
    config = envelope["config"]
    keys(config, EXPECTED_CONFIG_KEYS, "provider_config_fields")
    need(config["endpoint"] == ENDPOINT, "one_concrete_https_endpoint")
    selected_model(config["model"])
    keys(config["bindings"], BINDING_KEYS, "binding_fields")
    need(all(pin(value) for value in config["bindings"].values()), "selected_source_bindings")
    credential_metadata(config["credential"])
    limits = config["limits"]
    keys(limits, LIMIT_KEYS, "provider_limit_fields")
    for name in LIMIT_KEYS - {"timeout_seconds"}:
        integer(limits[name], 1)
    need(finite(limits["timeout_seconds"]) and 0 < limits["timeout_seconds"] <= 3600, "transport_timeout")
    need(limits["request_bytes"] <= 8 * 1024 * 1024 and
         limits["response_bytes"] <= MAX_RESPONSE_BYTES and
         limits["result_bytes"] <= MAX_RESULT_BYTES, "application_byte_caps")
    # Raw response, complete carried output and output text are retained together.
    # Reserve enough space before any credential or network operation.
    need(limits["result_bytes"] >= 6 * (limits["response_bytes"] + 1) + 131072, "complete_result_reservation")
    need(limits["input_tokens"] + limits["output_tokens"] <= limits["total_tokens"], "token_reservation_arithmetic")
    parameters = config["parameters"]
    need(type(parameters) is dict and "max_output_tokens" in parameters and
         set(parameters) <= {"max_output_tokens", "temperature", "top_p", "reasoning"}, "explicit_generation_parameters")
    need(type(parameters["max_output_tokens"]) is int and
         parameters["max_output_tokens"] == limits["output_tokens"], "exact_output_token_cap")
    for name, maximum in (("temperature", 2), ("top_p", 1)):
        if name in parameters:
            need(finite(parameters[name]) and 0 <= parameters[name] <= maximum, "sampling_parameter_range")
    if "reasoning" in parameters:
        need(type(parameters["reasoning"]) is dict and set(parameters["reasoning"]) <= {"effort", "summary", "mode", "context"},
             "reasoning_parameter_fields")
        need(all(type(value) is str and 0 < len(value) <= 64 for value in parameters["reasoning"].values()),
             "reasoning_parameter_values")
    bound = config["token_bound"]
    keys(bound, TOKEN_BOUND_KEYS, "qualified_token_bound_fields")
    need(bound["model"] == config["model"] and bound["source_sha256"] == config["bindings"]["source_sha256"] and
         bound["qualification_sha256"] == config["bindings"]["qualification_sha256"], "qualified_bound_binding")
    integer(bound["per_utf8_byte"], 1)
    integer(bound["overhead_tokens"])
    validate_input(envelope["input"], config["bindings"])
    remaining(envelope["deadline"], limits["timeout_seconds"])
    return config

def request_body(envelope, config):
    value = {"model": config["model"], "input": envelope["input"], "store": False, "stream": False,
             "include": ["reasoning.encrypted_content"], "truncation": "disabled",
             "tools": [], "tool_choice": "none", "parallel_tool_calls": False,
             "text": {"format": {"type": "text"}}, **config["parameters"]}
    body = canonical(value)
    limits = config["limits"]
    need(len(body) <= limits["request_bytes"], "complete_request_byte_cap")
    bound = config["token_bound"]
    input_bound = bound["overhead_tokens"] + bound["per_utf8_byte"] * len(body)
    need(input_bound <= limits["input_tokens"] and
         input_bound + limits["output_tokens"] <= limits["total_tokens"], "qualified_input_token_bound")
    return body, input_bound

def usage(value):
    need(type(value) is dict and type(value.get("usage")) is dict, "provider_usage_unavailable")
    row = value["usage"]
    keys(row, {"input_tokens", "output_tokens", "total_tokens", "input_tokens_details", "output_tokens_details"},
         "provider_usage_classes")
    for name in ("input_tokens", "output_tokens", "total_tokens"):
        integer(row[name])
    need(row["total_tokens"] == row["input_tokens"] + row["output_tokens"], "provider_usage_arithmetic")
    inp, out = row["input_tokens_details"], row["output_tokens_details"]
    need(type(inp) is dict and set(inp) in ({"cached_tokens"}, {"cached_tokens", "cache_write_tokens"}),
         "provider_input_token_classes")
    keys(out, {"reasoning_tokens"}, "provider_output_token_classes")
    for value in inp.values():
        integer(value)
        need(value <= row["input_tokens"], "input_token_subset")
    integer(out["reasoning_tokens"])
    need(out["reasoning_tokens"] <= row["output_tokens"], "reasoning_token_subset")
    return {"input_tokens": row["input_tokens"], "output_tokens": row["output_tokens"],
            "total_tokens": row["total_tokens"], "reasoning_tokens": out["reasoning_tokens"],
            "cached_input_tokens": inp["cached_tokens"],
            "cache_write_tokens": inp.get("cache_write_tokens"),
            "status": "provider_reported"}

def post_once(body, key, config, deadline, observation, errors):
    connection = None
    response = None
    prefix = bytearray()
    timeout = config["limits"]["timeout_seconds"]
    cap = config["limits"]["response_bytes"]
    try:
        observation["connection_create_attempted"] = True
        connection = http.client.HTTPSConnection(ENDPOINT["host"], ENDPOINT["port"],
            timeout=remaining(deadline, timeout), context=ssl.create_default_context())
        # The enclosing parent owns a hard process deadline even if platform DNS,
        # TLS or native I/O ignores this cooperative socket timeout.
        connection.timeout = remaining(deadline, timeout)
        observation["request_attempted"] = True
        observation["request_unknown_upper_bound"] = len(body)
        connection.request("POST", ENDPOINT["path"], body=body,
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json", "Accept": "application/json"})
        observation["request_complete"] = True
        observation["request_body_sent_bytes"] = len(body)
        observation["request_unknown_upper_bound"] = 0
        left = remaining(deadline, timeout)
        if connection.sock is not None:
            connection.sock.settimeout(left)
        response = connection.getresponse()
        observation["response_status"] = response.status
        headers = {}
        for name in ("content-type", "content-length", "x-request-id"):
            value = response.getheader(name)
            need(value is None or (type(value) is str and len(value.encode("utf-8")) <= 1024), "selected_header_cap")
            headers[name] = value
        observation["response_headers"] = headers
        length = headers["content-length"]
        if length is not None:
            need(length.isdecimal() and int(length) <= cap, "response_content_length_cap")
        while True:
            left = remaining(deadline, timeout)
            if connection.sock is not None:
                connection.sock.settimeout(left)
            need(len(observation["response_reads"]) < MAX_READ_OBSERVATIONS, "response_read_observation_cap")
            count = min(65536, cap - len(prefix) + 1)
            need(count > 0, "response_byte_cap")
            row = {"requested_bytes": count, "returned_bytes": None, "unknown_upper_bound": count}
            observation["response_reads"].append(row)
            try:
                block = response.read(count)
            except http.client.IncompleteRead as error:
                # http.client exposes body bytes already received even when the
                # declared body/chunk is cut short. Retain that bounded original
                # fragment before recording failure; never turn it into EOF.
                partial = error.partial
                need(type(partial) is bytes, "incomplete_read_partial_bytes")
                row["returned_bytes"] = len(partial)
                row["unknown_upper_bound"] = 0
                row["outcome"] = "incomplete_read_available_partial"
                row["partial_sha256"] = digest(partial)
                room = cap + 1 - len(prefix)
                kept = partial[:room]
                row["partial_retained_bytes"] = len(kept)
                row["partial_omitted_bytes"] = len(partial) - len(kept)
                observation["response_body_bytes"] = len(prefix) + len(partial)
                prefix.extend(kept)
                observation["response_retained_bytes"] = len(prefix)
                raise
            need(type(block) is bytes, "provider_body_bytes")
            row["returned_bytes"] = len(block)
            row["unknown_upper_bound"] = 0
            prefix.extend(block)
            observation["response_body_bytes"] = len(prefix)
            observation["response_retained_bytes"] = len(prefix)
            need(len(prefix) <= cap, "response_byte_cap")
            if not block:
                observation["response_eof"] = True
                break
        remaining(deadline, timeout)
        need(response.status == 200, "provider_http_failure_no_retry")
    except BaseException as error:
        opaque_error(errors, "transport", error)
    finally:
        key = None
        for owned, attempted, closed, phase in (
            (response, "response_close_attempted", "response_closed", "response_close"),
            (connection, "connection_close_attempted", "connection_closed", "connection_close")):
            if owned is not None:
                observation[attempted] = True
                try:
                    owned.close()
                    observation[closed] = True
                except BaseException as error:
                    opaque_error(errors, phase, error)
    return bytes(prefix)

def run(envelope, envelope_body):
    errors = []
    result = {"schema": "n006-provider-result-v1", "request_id": None,
        "envelope_sha256": digest(envelope_body), "request_sha256": None, "request_bytes": None,
        "model": None, "bindings": None, "status": "failed", "errors": errors,
        "raw_response_base64": "", "raw_response_sha256": digest(b""), "raw_response_bytes": 0,
        "provider_status": None, "usage": None, "usage_unknown": True,
        "usage_exceeds_reservation": None, "qualified_input_token_bound": None,
        "output_text": None, "output_history": None, "output_history_sha256": None,
        "provider_hardware": {"cpu_seconds": None, "gpu_seconds": None, "peak_memory_bytes": None,
            "status": "unknown_not_measured_not_zero"},
        "credential_io": {"read_attempted": False, "read_bytes": 0, "close_attempted": False, "closed": False},
        "transport": {"endpoint": dict(ENDPOINT), "original_deadline": None, "retries": 0,
            "connection_create_attempted": False, "request_attempted": False, "request_complete": False,
            "request_body_sent_bytes": None, "request_unknown_upper_bound": 0,
            "response_status": None, "response_headers": None, "response_body_bytes": 0, "response_retained_bytes": 0,
            "response_reads": [], "response_eof": False, "connection_close_attempted": False,
            "connection_closed": False, "response_close_attempted": False, "response_closed": False,
            "scope": "application bodies only; HTTP/TLS/DNS/kernel/provider internals not measured"}}
    config = None
    key = None
    raw = b""
    try:
        config = validate(envelope)
        result["request_id"] = envelope["request_id"]
        result["model"] = config["model"]
        result["bindings"] = dict(config["bindings"])
        result["transport"]["original_deadline"] = envelope["deadline"]
        body, bound = request_body(envelope, config)
        result["request_sha256"] = digest(body)
        result["request_bytes"] = len(body)
        result["qualified_input_token_bound"] = bound
        key = read_credential(config["credential"], envelope["deadline"], config["limits"]["timeout_seconds"],
                              result["credential_io"], errors)
        if key is not None and not errors:
            raw = post_once(body, key, config, envelope["deadline"], result["transport"], errors)
    except BaseException as error:
        opaque_error(errors, "admission_or_request", error)
    finally:
        key = None
    # Settle any valid usage BEFORE status/model/output checks, even for non-200
    # or incomplete responses. A failure never makes known tokens disappear.
    result["raw_response_base64"] = base64.b64encode(raw).decode("ascii")
    result["raw_response_sha256"] = digest(raw)
    result["raw_response_bytes"] = len(raw)
    decoded = None
    if raw:
        try:
            decoded = parse(raw)
            if type(decoded) is dict:
                status = decoded.get("status")
                if type(status) is str and len(status) <= 128:
                    result["provider_status"] = status
        except BaseException as error:
            opaque_error(errors, "response_json", error)
    if decoded is not None:
        try:
            result["usage"] = usage(decoded)
            result["usage_unknown"] = False
        except BaseException as error:
            opaque_error(errors, "usage", error)
    if result["usage"] is not None and config is not None:
        reported = result["usage"]
        limits = config["limits"]
        exceeded = any(reported[k] > limits[k] for k in ("input_tokens", "output_tokens", "total_tokens"))
        result["usage_exceeds_reservation"] = exceeded
        if exceeded:
            opaque_error(errors, "usage", Refusal("actual_usage_exceeds_reservation"))
        if reported["input_tokens"] > result["qualified_input_token_bound"]:
            opaque_error(errors, "usage", Refusal("qualified_input_bound_violated"))
    if decoded is not None and config is not None:
        try:
            need(type(decoded) is dict and decoded.get("object") == "response" and
                 type(decoded.get("id")) is str and decoded["id"], "responses_object_identity")
            need(decoded.get("model") == config["model"], "returned_exact_selected_model")
            need(decoded.get("status") == "completed" and decoded.get("error") is None and
                 decoded.get("incomplete_details") is None, "complete_provider_status")
            need(not decoded.get("input_transformations"), "provider_history_not_truncated")
            text = output_items(decoded.get("output"), require_text=True)
            result["output_text"] = text
            result["output_history"] = decoded["output"]
            result["output_history_sha256"] = digest(canonical(decoded["output"]))
        except BaseException as error:
            opaque_error(errors, "provider_completion", error)
    if config is not None:
        try:
            remaining(envelope["deadline"], config["limits"]["timeout_seconds"])
        except BaseException as error:
            opaque_error(errors, "final_original_deadline", error)
    if not errors and result["usage"] is not None and result["transport"]["response_eof"]:
        result["status"] = "complete"
    # This is application closure evidence, not proof that remote generation
    # stopped when the local connection closed or the parent killed this worker.
    result["remote_cancellation_confirmed"] = False
    return result, MAX_RESULT_BYTES if config is None else config["limits"]["result_bytes"]

def main():
    result = None
    try:
        need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode, "isolated_worker_required")
        body = sys.stdin.buffer.readline(MAX_ENVELOPE_BYTES + 1)
        need(len(body) <= MAX_ENVELOPE_BYTES and body.endswith(b"\n"), "one_bounded_envelope")
        need(sys.stdin.buffer.read(1) == b"", "exact_envelope_eof")
        envelope = parse(body)
        result, cap = run(envelope, body)
        encoded = canonical(result)
        need(len(encoded) <= cap, "complete_result_byte_cap")
        offset = 0
        while offset < len(encoded):
            count = os.write(1, encoded[offset:offset + 65536])
            need(count > 0, "result_short_write")
            offset += count
        return 0 if result["status"] == "complete" else 1
    except BaseException as error:
        # Never retry stdout or replace a partial/failed result with success.
        # Parent retains partial stdout and treats missing complete result as
        # unknown usage with the original full reservation still charged.
        packet = {"schema": "n006-provider-worker-terminal-failure-v1", "class": type(error).__name__,
                  "code": str(error) if type(error) is Refusal else "opaque_failure",
                  "remote_usage": "unknown_until_complete_retained_result"}
        try:
            body = canonical(packet)
            if len(body) <= 4096:
                os.write(2, body)
        except BaseException:
            pass
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
