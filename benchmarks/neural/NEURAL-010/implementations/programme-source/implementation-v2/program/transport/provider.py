"""Concrete non-streaming Chat Completions transport; no call on import.

Protocol basis: official create-chat-completion reference, inspected2026-11-08.
The selected model/API/account billing and retention behavior still require
external qualification. Failed requests retain their full reservation; there is
no retry and no claim that local socket close cancels remote computation.
"""
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import time

from .common import AdapterError, canonical, integer, need, positive, write_fresh, sync_directory


ENDPOINT = "https://api.openai.com/v1/chat/completions"
TOOL = {"type": "function", "function": {"name": "python", "description": "Run Python in this context's isolated permitted workspace; no other context or protected grading access.",
        "parameters": {"type": "object", "properties": {"code": {"type": "string"}},
                       "required": ["code"], "additionalProperties": False}}}


def parse_completion(body):
    need(isinstance(body, dict) and isinstance(body.get("id"), str), "provider response identity required")
    usage = body.get("usage")
    need(isinstance(usage, dict), "complete provider usage required; unknown cost refuses")
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        integer(usage.get(key), "provider " + key)
    need(usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"], "provider token-total mismatch")
    choices = body.get("choices")
    need(type(choices) is list and len(choices) == 1 and type(choices[0].get("index")) is int
         and choices[0]["index"] == 0, "one provider choice required")
    choice = choices[0]; message = choice.get("message")
    need(isinstance(message, dict) and message.get("role") == "assistant" and not message.get("refusal"), "assistant response/refusal admission")
    finish = choice.get("finish_reason")
    need(finish in ("stop", "tool_calls"), "truncation/filter/unfinished provider response refused")
    calls = message.get("tool_calls") or []
    if finish == "tool_calls":
        need(type(calls) is list and len(calls) == 1, "exactly one serial training tool call")
        call = calls[0]
        need(call.get("type") == "function" and type(call.get("id")) is str and call["id"], "tool call identity required")
        function = call.get("function", {})
        need(function.get("name") == "python" and type(function.get("arguments")) is str, "only training Python tool admitted")
        args = json.loads(function["arguments"])
        need(isinstance(args, dict) and set(args) == {"code"} and type(args["code"]) is str and args["code"], "exact tool argument schema")
    else:
        need(not calls and type(message.get("content")) is str, "natural final text required")
    normalized = {"role": "assistant", "content": message.get("content")}
    if calls:
        normalized["tool_calls"] = [{"id": calls[0]["id"], "type": "function",
                                      "function": {"name": "python", "arguments": calls[0]["function"]["arguments"]}}]
    return normalized, finish, usage


class ChatCompletionTransport:
    def __init__(self, config, budget, evidence_root=None):
        expected = {"endpoint", "model", "api_key_env", "max_completion_tokens", "prompt_token_reservation",
                    "request_cap_bytes", "response_cap_bytes", "request_timeout_seconds", "seed"}
        need(isinstance(config, dict) and set(config) == expected and config["endpoint"] == ENDPOINT, "exact supported provider configuration")
        need(type(config["model"]) is str and config["model"], "preselected model identity required")
        need(re.fullmatch(r"[A-Z][A-Z0-9_]{1,127}", config["api_key_env"]) is not None, "named credential environment variable")
        for key in expected - {"endpoint", "model", "api_key_env", "request_timeout_seconds", "seed"}:
            integer(config[key], key, 1)
        positive(config["request_timeout_seconds"], "request timeout")
        need(config["prompt_token_reservation"] >= config["request_cap_bytes"] + 4096,
             "conservative qualified prompt-token reservation must cover request bytes plus overhead")
        need(config["seed"] is None or type(config["seed"]) is int and 0 <= config["seed"] < 2**31, "explicit seed or unsupported-provider null")
        self.config, self.budget, self.records = dict(config), budget, []
        self.evidence_root = None if evidence_root is None else Path(evidence_root)
        if self.evidence_root is not None:
            self.evidence_root.mkdir(mode=0o700); sync_directory(self.evidence_root); sync_directory(self.evidence_root.parent)

    def complete(self, messages, *, allow_tools):
        self.budget.check_clock()
        need(self.evidence_root is not None, "operator-owned transcript destination required")
        payload = {"model": self.config["model"], "messages": messages, "n": 1,
                   "store": False, "stream": False,
                   "max_completion_tokens": self.config["max_completion_tokens"]}
        if self.config["seed"] is not None: payload["seed"] = self.config["seed"]
        if allow_tools:
            payload.update({"tools": [TOOL], "tool_choice": "auto", "parallel_tool_calls": False})
        request = canonical(payload)
        need(len(request) <= self.config["request_cap_bytes"], "provider request/context byte cap exceeded")
        reservation = self.config["prompt_token_reservation"] + self.config["max_completion_tokens"]
        self.budget.charge("provider_calls")
        self.budget.charge("provider_tokens", reservation)
        # Debit the bounded read before the network operation, including EOF probe.
        self.budget.charge("source_read", self.config["response_cap_bytes"] + 1)
        self.budget.charge("artifact_write", self.config["response_cap_bytes"] + 1)
        ordinal = len(self.records) + 1
        request_pin = write_fresh(self.evidence_root / f"request-{ordinal:04d}.json", request, self.budget)
        key = os.environ.get(self.config["api_key_env"])
        need(type(key) is str and key, "provider credential unavailable; no prompt or retry")
        start = time.monotonic()
        deadline = min(self.budget.deadline_monotonic, start + self.config["request_timeout_seconds"])
        connection = http.client.HTTPSConnection("api.openai.com", timeout=max(0.001, deadline - start))
        response = None; raw = bytearray()
        record = {"request_sha256": hashlib.sha256(request).hexdigest(), "request_bytes": len(request),
                  "model": self.config["model"], "started_monotonic": start, "deadline_monotonic": deadline,
                  "token_reservation": reservation, "stream_mode": False, "status": "attempted",
                  "requested_seed": self.config["seed"], "determinism": "unknown; seed is not deterministic execution evidence",
                  "request_artifact": request_pin,
                  "remote_retirement_on_failure": "unknown; local close is not cancellation"}
        self.records.append(record)
        try:
            connection.request("POST", "/v1/chat/completions", body=request,
                               headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
            response = connection.getresponse()
            record["http_status"] = response.status
            record["provider_request_id"] = response.getheader("x-request-id")
            need(response.status == 200, "provider HTTP failure; body not exposed as a successful result")
            need(response.getheader("content-encoding") in (None, "identity"), "compressed provider body not admitted")
            while True:
                self.budget.check_clock(); remaining = deadline - time.monotonic()
                need(remaining > 0, "provider request deadline expired")
                if connection.sock is not None: connection.sock.settimeout(remaining)
                block = response.read(min(65536, self.config["response_cap_bytes"] + 1 - len(raw)))
                if not block: break
                raw.extend(block)
                need(len(raw) <= self.config["response_cap_bytes"], "provider response byte cap exceeded")
            body = json.loads(raw)
            need(body.get("model") == self.config["model"], "provider returned a different model identity")
            message, finish, usage = parse_completion(body)
            need(usage["prompt_tokens"] <= self.config["prompt_token_reservation"] and
                 usage["completion_tokens"] <= self.config["max_completion_tokens"], "provider exceeded reserved token domain")
            need(allow_tools or finish == "stop", "fixed data-free author cannot invoke training tools")
            record.update({"status": "complete", "response_id": body["id"], "finish_reason": finish,
                           "usage": usage, "system_fingerprint": body.get("system_fingerprint")})
            return message, finish
        except BaseException as exc:
            record.update({"status": "failed", "failure_type": type(exc).__name__, "failure": str(exc)})
            raise AdapterError("provider attempt failed; reservation retained, no automatic retry", dict(record)) from exc
        finally:
            record.update({"ended_monotonic": time.monotonic(), "response_bytes": len(raw),
                           "response_sha256": hashlib.sha256(raw).hexdigest()})
            if response is not None: response.close()
            connection.close(); record["response_stream_closed"] = True
            response_path = self.evidence_root / f"response-{ordinal:04d}.json"
            with response_path.open("xb") as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            sync_directory(self.evidence_root)
            record["response_artifact"] = {"path": str(response_path), "bytes": len(raw),
                                           "sha256": hashlib.sha256(raw).hexdigest()}
            if record["status"] == "complete":
                try:
                    self.budget.check_clock()
                except BaseException:
                    record["status"] = "failed_after_response_deadline"
                    raise
            # Credentials are never placed in receipts, arguments, mounts or messages.
            del key
