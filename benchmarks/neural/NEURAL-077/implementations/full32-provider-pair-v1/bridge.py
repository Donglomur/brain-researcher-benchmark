"""Full32 Responses adapter with injected transport; no HTTP or credentials.

serve() connects the numerical-waveform pipe to exactly one independent Responses
request. The trusted operator supplies send_json(bytes)->bytes and a private
receipt sink. This module does not install an SDK or execute network requests.
"""
from __future__ import annotations

import hashlib
from functools import lru_cache
import os
import stat
import types
import json
from pathlib import Path
import re
import struct

PREFIX = struct.Struct("!I")
PROMPT_CAP = 2097152
PROVIDER_RESPONSE_CAP = 524288
RESPONSE_CAP = 4096
NO_TOOLS = "Do not use tools, code execution, external retrieval, files, or memory from other query trials."
CONSUMER_PIN = {"bytes": 21146, "sha256": "6825dc00428b64c20cf23e1ac82068c891c4dd121fd980e0076b0ce89cb7629d"}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def decode(body):
    return json.loads(body.decode("utf-8"), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


def query_identity(prompt):
    require(type(prompt) is str and 0 < len(prompt.encode("utf-8")) <= PROMPT_CAP,
            "Complete bounded prompt required")
    require(prompt.count(NO_TOOLS) == 1, "Only complete direct no-tools condition accepted")
    identifiers = set(re.findall(r"(?<![A-Za-z0-9_-])q-[0-9a-f]{32}(?![A-Za-z0-9_-])", prompt))
    require(len(identifiers) == 1, "Exactly one full32 opaque query identity required")
    require(re.search(r"development-00[12]-[0-9a-f]{24}", prompt) is None,
            "Legacy development identities cannot enter the full32 bridge")
    return next(iter(identifiers))


def request_body(prompt, model, max_output_tokens):
    identifier = query_identity(prompt)
    require(type(model) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}", model),
            "Explicit bounded model identifier required")
    require(type(max_output_tokens) is int and 1 <= max_output_tokens <= 32768, "Explicit bounded output token limit required")
    schema = {"type": "object", "properties": {"trial_id": {"type": "string", "enum": [identifier]},
                                                "target_probability": {"type": "number"}},
              "required": ["trial_id", "target_probability"], "additionalProperties": False}
    return encode({"model": model, "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
                   "tools": [], "tool_choice": "none", "parallel_tool_calls": False,
                   "store": False, "stream": False, "background": False, "truncation": "disabled",
                   "max_output_tokens": max_output_tokens,
                   "text": {"format": {"type": "json_schema", "name": "neural077_probability",
                                        "strict": True, "schema": schema}}})


@lru_cache(maxsize=1)
def _consumer_parser():
    """Capture the immutable adjacent full32 parser once, never import candidates."""
    path = Path(__file__).absolute().parent.parent / "full32-paired-benchmark-v1/consumer.py"
    require(".." not in path.parts and all(not p.is_symlink() for p in (path, *path.parents)),
            "Ordinary fixed full32 consumer path required")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and before.st_size == CONSUMER_PIN["bytes"], "Exact full32 consumer source required")
        source = stream.read(CONSUMER_PIN["bytes"] + 1)
        after = os.fstat(stream.fileno())
    fields = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns,
                            value.st_ctime_ns, value.st_nlink)
    require(fields(before) == fields(after) == fields(path.lstat()) and pin(source) == CONSUMER_PIN,
            "Full32 consumer source changed")
    module = types.ModuleType("erp_full32_provider_scalar_contract")
    module.__file__ = str(path)
    exec(compile(source, str(path), "exec"), module.__dict__)
    return module.parse_response


def parse_scalar(body, identifier):
    require(type(body) is bytes and type(identifier) is str
            and re.fullmatch(r"q-[0-9a-f]{32}", identifier), "Full32 scalar identity required")
    return _consumer_parser()(body.decode("utf-8"), identifier)


def completed_text(body, expected_id, model, max_output_tokens):
    require(type(body) is bytes and 0 < len(body) <= PROVIDER_RESPONSE_CAP, "Bounded raw provider JSON required")
    value = decode(body)
    require(type(value) is dict and value.get("object") == "response" and value.get("status") == "completed"
            and value.get("error") is None and value.get("incomplete_details") is None,
            "Provider response failed, incomplete or unrecognized")
    # These echoed settings prevent accepting a response for a different policy.
    require(value.get("tools") == [] and value.get("tool_choice") == "none"
            and value.get("parallel_tool_calls") is False and value.get("store") is False
            and value.get("truncation") == "disabled" and value.get("previous_response_id") is None
            and value.get("conversation") is None, "Provider response policy/history mismatch")
    require(type(value.get("model")) is str and value["model"] == model,
            "Provider must return the explicitly selected model identifier")
    require(type(value.get("max_output_tokens")) is int and value["max_output_tokens"] == max_output_tokens,
            "Provider output allocation mismatch")
    require(type(value.get("id")) is str and re.fullmatch(r"resp_[A-Za-z0-9_-]{1,160}", value["id"]),
            "Bounded provider response identity required")
    output = value.get("output")
    require(type(output) is list and 1 <= len(output) <= 32, "Bounded response output inventory required")
    messages = []
    for item in output:
        require(type(item) is dict and item.get("type") in ("reasoning", "message"),
                "Tools and other output item types are forbidden")
        if item["type"] == "message":
            messages.append(item)
    require(len(messages) == 1, "Exactly one final assistant message required")
    message = messages[0]
    require(message.get("role") == "assistant" and message.get("status") == "completed"
            and type(message.get("content")) is list and len(message["content"]) == 1,
            "Complete single-content assistant message required")
    content = message["content"][0]
    require(type(content) is dict and content.get("type") == "output_text" and type(content.get("text")) is str,
            "Refusal or non-text output cannot become a scalar")
    text = content["text"].encode("utf-8")
    parse_scalar(text, expected_id)
    usage = value.get("usage")
    require(type(usage) is dict, "Provider token accounting required")
    counts = {}
    for name in ("input_tokens", "output_tokens", "total_tokens"):
        require(type(usage.get(name)) is int and 0 <= usage[name] <= 100000000, "Bounded integral token counts required")
        counts[name] = usage[name]
    require(counts["total_tokens"] == counts["input_tokens"] + counts["output_tokens"], "Inconsistent provider token totals")
    require(counts["output_tokens"] <= max_output_tokens, "Provider output exceeded declared allocation")
    return text, {"provider_response_id": value["id"], "model": value["model"], "usage": counts}


def exchange(prompt, *, model, max_output_tokens, send_json, record):
    """Exactly one injected send; preserve success/failure receipt, never retry.

    send_json owns authenticated HTTP, endpoint and timeout. It must return only
    bounded response-body bytes and must not attach Authorization/header material.
    record receives only bounded metadata and hashes, never credentials or headers.
    The caller must retain provider bodies separately under its reviewed protocol.
    """
    require(callable(send_json) and callable(record), "Trusted sender and receipt sink required")
    request = request_body(prompt, model, max_output_tokens)
    identifier = query_identity(prompt)
    receipt = {"schema": "erp_full32_responses_bridge_v1", "condition": "numeric_direct_four_demo",
               "prompt": pin(prompt.encode("utf-8")), "request": pin(request), "requested_model": model,
               "max_output_tokens": max_output_tokens, "sender_calls_attempted": 0,
               "status": "not_sent", "response": None, "answer": None,
               "retry_count": 0, "provider_execution_qualified": False,
               "provider_capacity_qualified": False, "provider_context_qualified": False,
               "provider_tool_policy_qualified": False, "scientific_qualification": False}
    try:
        receipt["sender_calls_attempted"] = 1
        raw = send_json(request)
        require(type(raw) is bytes and 0 < len(raw) <= PROVIDER_RESPONSE_CAP, "Bounded provider response body required")
        receipt["response"] = pin(raw)
        answer, metadata = completed_text(raw, identifier, model, max_output_tokens)
        receipt.update(metadata)
        receipt["answer"] = pin(answer)
        receipt["status"] = "complete_unscored_answer"
        return answer
    except Exception:
        # Never record exception text: it may embed a URL, header or credential.
        receipt["status"] = "failed_no_answer"
        raise ValueError("Provider exchange failed; no answer admitted") from None
    finally:
        record(receipt)


def serve(input_stream, output_stream, *, model, max_output_tokens, send_json, record):
    """Consume one complete full32 prompt frame and emit its first scalar frame.

    Streams are binary. Caller runs this once in each trusted provider bridge
    process; no previous response, conversation, tools or additional input exists.
    """
    def take(size):
        body = bytearray()
        while len(body) < size:
            part = input_stream.read(size - len(body))
            require(type(part) is bytes and 0 < len(part) <= size - len(body), "Incomplete prompt frame")
            body.extend(part)
        return bytes(body)
    size = PREFIX.unpack(take(PREFIX.size))[0]
    require(0 < size <= PROMPT_CAP, "Prompt framing exceeds cap")
    prompt = take(size).decode("utf-8")
    require(input_stream.read(1) == b"", "Only one prompt frame permitted")
    answer = exchange(prompt, model=model, max_output_tokens=max_output_tokens,
                      send_json=send_json, record=record)
    frame = PREFIX.pack(len(answer)) + answer
    written = 0
    while written < len(frame):
        count = output_stream.write(frame[written:])
        require(type(count) is int and 0 < count <= len(frame) - written, "Incomplete response write")
        written += count
    output_stream.flush()
