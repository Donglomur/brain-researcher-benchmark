"""NEURAL-095 alternate stateful investigator actor; operator adoption pending.

Assemble a pinned decision callback into this one source file before execution.
This is an actor component, not a provider, process sandbox or execution grant.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys

# Replaced exactly once by assemble.py; the whole assembled source is frozen.
CALLBACK_BASE64 = None  # ASSEMBLED_CALLBACK_BYTES
CALLBACK_PIN = None  # ASSEMBLED_CALLBACK_PIN

CASE_COUNT = 258
TRAIN_COUNT = 748
MAX_TOOLS = 16
MAX_DECISIONS = CASE_COUNT + MAX_TOOLS
MAX_OPERATIONS = 292  # prepare + decisions + tools + export
SOURCE_CAP = 65536
REQUEST_CAP = 65536
RESPONSE_CAP = 262144
TOOL_OBSERVATION_CAP = 65536
CONTEXT_CAP = 3 * 1024**2  # All sixteen bounded arguments/results plus258 decisions.
MODES = ("case_adaptive__cue_only", "case_adaptive__neural")
SCHEMA = "dmfc-case-investigator/v1"
POLICY = "stateful_case_decisions/v1"


class ActorError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise ActorError(message)


def encode(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, OverflowError, RecursionError) as error:
        raise ActorError("Finite bounded JSON value required") from error


def decode(body, cap):
    need(type(body) is bytes and 0 < len(body) <= cap, "Bounded complete JSON body required")
    def unique(items):
        result = {}
        for key, value in items:
            need(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    try:
        value = json.loads(body, object_pairs_hook=unique,
                           parse_constant=lambda _: need(False, "Nonfinite JSON value"))
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ActorError("Invalid bounded JSON response") from error
    need(len(encode(value)) <= cap, "Expanded JSON exceeds cap")
    return value


def fingerprint(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def captured_source(path):
    path = Path(path).absolute()
    need(".." not in path.parts and all(not item.is_symlink() for item in (path, *path.parents)),
         "Ordinary unlinked source path required")
    before = path.stat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= SOURCE_CAP,
         "One bounded ordinary source file required")
    with path.open("rb") as stream:
        need(fingerprint(os.fstat(stream.fileno())) == fingerprint(before), "Source replaced before capture")
        body = stream.read(before.st_size + 1)
        need(fingerprint(os.fstat(stream.fileno())) == fingerprint(before), "Source changed during capture")
    need(len(body) == before.st_size and fingerprint(path.stat()) == fingerprint(before), "Stable source identity required")
    return body


def sha(body):
    return hashlib.sha256(body).hexdigest()


def callback_bytes(encoded, expected):
    need(type(encoded) is str and len(encoded) <= 4 * ((SOURCE_CAP + 2) // 3), "Assembled bounded callback required")
    need(type(expected) is dict and set(expected) == {"bytes", "sha256"}
         and type(expected["bytes"]) is int and 0 < expected["bytes"] <= SOURCE_CAP
         and type(expected["sha256"]) is str and re.fullmatch("[a-f0-9]{64}", expected["sha256"]),
         "Exact callback source pin required")
    try:
        body = base64.b64decode(encoded, validate=True)
    except ValueError as error:
        raise ActorError("Invalid callback encoding") from error
    need(len(body) == expected["bytes"] and sha(body) == expected["sha256"], "Callback source identity changed")
    return body


def configuration(value):
    need(type(value) is dict and set(value) == {"schema", "mode", "tool_id", "policy"}, "Exact four-field actor config required")
    need(value["schema"] == SCHEMA and value["policy"] == POLICY and value["mode"] in MODES,
         "Explicit case-adaptive investigator configuration required")
    need(type(value["tool_id"]) is str and re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}@[a-f0-9]{64}", value["tool_id"]),
         "One source-pinned admitted numerical tool required")
    return dict(value)


class Wire:
    """Original actor JSON-line envelopes. The external owner supplies deadlines."""
    def __init__(self, reader, writer):
        self.reader, self.writer = reader, writer
        self.closed = False

    def read(self, cap):
        body = self.reader.readline(cap + 1)
        need(type(body) is bytes and body.endswith(b"\n") and len(body) <= cap, "Truncated, missing or oversized response line")
        return decode(body, cap)

    def call(self, value):
        need(not self.closed, "Actor wire is single-use")
        body = encode(value) + b"\n"
        need(len(body) <= REQUEST_CAP, "Actor request exceeds original wire cap")
        self.writer.write(body)
        self.writer.flush()
        response = self.read(RESPONSE_CAP)
        need(type(response) is dict, "Exact host response object required")
        if value["op"] == "freeze":
            need(set(response) == {"status", "controller_sha256"} and response["status"] == "committed"
                 and response["controller_sha256"] == sha(value["source"].encode("utf-8")),
                 "Host did not commit the exact assembled actor source")
            return response["controller_sha256"]
        need(set(response) == {"status", "payload"} and response["status"] == "ok", "Exact successful public response required")
        return response["payload"]

    def public(self, request):
        return self.call({"op": "public", "request": request})

    def finish(self):
        need(not self.closed, "Actor already finished")
        self.closed = True
        self.writer.write(b'{"op":"finish"}\n')
        self.writer.flush()  # Existing relay sends no terminal response.


class _NoProtocolIO:
    """Prevent accidental callback use of protocol stdio; not a security sandbox."""
    def write(self, value):
        need(not value, "Callback must return actions, not write protocol stdout")
        return 0
    def read(self, *args):
        raise ActorError("Callback cannot consume protocol stdin")
    readline = read
    def flush(self):
        pass


def candidate_call(operation):
    old_in, old_out = sys.stdin, sys.stdout
    sys.stdin = sys.stdout = _NoProtocolIO()
    try:
        return operation()
    finally:
        sys.stdin, sys.stdout = old_in, old_out


def load_decision(body):
    # Called only within the first query decision, after TRAIN preparation and
    # source freeze. Arbitrary callback initialization is candidate computation.
    namespace = {"__name__": "_neural095_pinned_decision", "__file__": "<callback-" + sha(body) + ">"}
    candidate_call(lambda: exec(compile(body, namespace["__file__"], "exec"), namespace))
    decision = namespace.get("decide")
    need(callable(decision), "Pinned callback must define decide(context)")
    return decision


def finite_prediction(value):
    need(type(value) in (int, float), "Prediction must be a real scalar, not boolean")
    try:
        value = float(value)
    except (OverflowError, ValueError) as error:
        raise ActorError("Prediction cannot be represented as float64") from error
    need(math.isfinite(value), "Prediction must be finite")
    return value  # Negative finite values remain valid under the original ABI.


def investigate(wire, config, actor_source):
    config = configuration(config)
    need(type(actor_source) is bytes and 0 < len(actor_source) <= SOURCE_CAP, "Bounded assembled actor source required")
    callback_source = callback_bytes(CALLBACK_BASE64, CALLBACK_PIN)
    # Capture/self-hash and callback authentication precede candidate execution.
    actor_text = actor_source.decode("utf-8")
    wire.call({"op": "freeze", "source": actor_text})
    prepared = wire.public({"kind": "prepare"})
    need(type(prepared) is dict and set(prepared) == {"training_artifacts_sha256"}
         and type(prepared["training_artifacts_sha256"]) is str
         and re.fullmatch("[a-f0-9]{64}", prepared["training_artifacts_sha256"]), "Frozen TRAIN-only artifact commitment required")
    predictions, observations, seen = [], [], set()
    decision = None
    calls, tools = 0, 0
    for index in range(CASE_COUNT):
        current = None
        while True:
            received = wire.public({"kind": "next"})
            need(type(received) is dict and set(received) == {"case_id", "completed_cases", "full_query_batch_visible"}
                 and type(received["completed_cases"]) is int and received["completed_cases"] == index
                 and received["full_query_batch_visible"] is True, "Original full-batch ordered query context required")
            case_id = received["case_id"]
            need(type(case_id) is str and 0 < len(case_id) <= 11 and "\0" not in case_id
                 and case_id not in seen, "Unique current original-width case identity required")
            if current is None:
                current = dict(received)
            else:
                need(received == current, "A tool observation must not advance or replace the current case")
            need(calls < MAX_DECISIONS, "Whole-cell decision budget exhausted")
            calls += 1
            if decision is None:
                decision = load_decision(callback_source)
            context = {
                "schema": "neural095-investigator-context/v1", "mode": config["mode"],
                "view": config["mode"].split("__")[1], "training_count": TRAIN_COUNT,
                "query_count": CASE_COUNT, "training_artifacts_sha256": prepared["training_artifacts_sha256"],
                "current": current, "tool_id": config["tool_id"],
                "tool_observations": observations, "committed_predictions": predictions,
                "remaining_tool_calls": MAX_TOOLS - tools,
                "remaining_decision_calls": MAX_DECISIONS - calls,
                "query_fitting_allowed": False, "private_feedback_available": False,
            }
            # Candidate mutation cannot rewrite captured history or host identity.
            detached = decode(encode(context), CONTEXT_CAP)
            action = candidate_call(lambda: decision(detached))
            need(type(action) is dict, "Decision must be one typed action")
            need(len(encode(action)) + 128 <= REQUEST_CAP, "Bounded action envelope required")
            if action.get("action") == "predict":
                need(set(action) == {"action", "case_id", "prediction_ms"} and action["case_id"] == case_id,
                     "One prediction for the current case required")
                value = finite_prediction(action["prediction_ms"])
                exact = {"action": "predict", "case_id": case_id, "prediction_ms": value}
                acknowledgement = wire.public({"kind": "action", "action": exact})
                need(type(acknowledgement) is dict and set(acknowledgement) == {"accepted"}
                     and acknowledgement["accepted"] is True, "Prediction not accepted by host")
                predictions.append({"case_id": case_id, "prediction_ms": value})
                seen.add(case_id)
                break
            need(set(action) == {"action", "tool_id", "arguments"} and action["action"] == "tool"
                 and action["tool_id"] == config["tool_id"] and type(action["arguments"]) is dict,
                 "Only the admitted frozen-fit numerical tool may be requested")
            need(tools < MAX_TOOLS, "Whole-cell sixteen-tool-call budget exhausted")
            # Original prepare/decide/tool/export reservation arithmetic.
            need(1 + calls + tools + 1 + (CASE_COUNT - index) + 1 <= MAX_OPERATIONS,
                 "Tool would leave insufficient operations for complete predictions and export")
            action = decode(encode(action), REQUEST_CAP)
            acknowledgement = wire.public({"kind": "action", "action": action})
            need(type(acknowledgement) is dict and set(acknowledgement) == {"accepted"}
                 and acknowledgement["accepted"] is True, "Tool request not accepted by host")
            tools += 1  # Charged before awaiting a tool result; failures do not retry.
            observation = wire.public({"kind": "tool", "tool_id": action["tool_id"], "arguments": action["arguments"]})
            need(len(encode(observation)) <= TOOL_OBSERVATION_CAP, "Tool observation exceeds original state cap")
            observations.append({"case_id": case_id, "tool_id": action["tool_id"],
                                 "arguments": action["arguments"], "observation": observation})
    need(len(predictions) == len(seen) == CASE_COUNT and 1 + calls + tools + 1 <= MAX_OPERATIONS,
         "Complete original panel and operation budget required")
    wire.finish()
    return {"case_count": CASE_COUNT, "decision_calls": calls, "tool_calls": tools,
            "reserved_operation_count": 1 + calls + tools + 1,
            "actor_sha256": sha(actor_source), "callback_sha256": sha(callback_source),
            "private_feedback_requested": False, "provider_transport_supplied": False,
            "scope": "Actor protocol completion only; host commit, validation and grading remain external."}


def main():
    wire = Wire(sys.stdin.buffer, sys.stdout.buffer)
    try:
        config = wire.read(SOURCE_CAP)
        source = captured_source(__file__)
        investigate(wire, config, source)
        return 0
    except BaseException as error:
        print(type(error).__name__ + ": " + str(error)[:1600], file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
