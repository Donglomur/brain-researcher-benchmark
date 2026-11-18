"""Operator-side sealed-journal conversion; no candidate execution or grading.

Preserves every finite binary64 action and original panel identity. Caller-supplied
pins are consistency assertions, not evidence of provenance or causal execution.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import struct
import types

SCORER_BYTES = 11283
SCORER_SHA256 = "91dbec46a088e807ebdbf243c478ea6f9e8a3ea0cb5f7747837673d499279b51"
HEADER_BYTES = 4096
RECORD = struct.Struct("<Q7d32s32s32s")


def need(condition, message):
    if not condition:
        raise ValueError(message)


def exact(value, fields, message):
    need(type(value) is dict and set(value) == set(fields), message)


def digest(value):
    return type(value) is str and re.fullmatch("[0-9a-f]{64}", value) is not None


def input_pin(value):
    exact(value, ("bytes", "sha256"), "exact original input pin fields")
    need(type(value["bytes"]) is int and value["bytes"] > 0 and digest(value["sha256"]),
         "positive original input extent and lowercase SHA256")
    return dict(value)


def load_scorer(path=None):
    """Load only the already published, byte-pinned operator scorer source."""
    path = Path(path) if path is not None else (
        Path(__file__).resolve().parent.parent / "session-evaluator-v1" / "scorer.py"
    )
    with path.open("rb") as stream:
        body = stream.read(SCORER_BYTES + 1)
    need(len(body) == SCORER_BYTES and hashlib.sha256(body).hexdigest() == SCORER_SHA256,
         "exact unchanged current session scorer source")
    module = types.ModuleType("neural067_pinned_session_scorer")
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def parse_header(raw):
    head, separator, tail = raw[:HEADER_BYTES].partition(b"\x00")
    need(separator and not any(tail) and head.endswith(b"\n"), "padded journal header")

    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, "duplicate journal header field")
            value[key] = item
        return value

    header = json.loads(head, object_pairs_hook=pairs,
                        parse_constant=lambda _: need(False, "nonfinite journal header"))
    return header


def prediction(raw, descriptor, run, arm, count, source_input):
    need(type(raw) is bytes and len(raw) == descriptor["bytes"], "complete immutable journal bytes")
    need(hashlib.sha256(raw).hexdigest() == descriptor["sha256"], "captured journal SHA256")
    header = parse_header(raw)
    expected = {
        "schema": "neural067_action_journal_v1", "run": run, "arm": arm,
        "rows": count, "input": source_input, "encoding": RECORD.format,
        "record_bytes": RECORD.size, "header_bytes": HEADER_BYTES,
    }
    need(type(header) is dict and header == expected, "exact full-run journal identity and input")
    # The accepted Journal writes this canonical newline-terminated form.
    canonical = (json.dumps(expected, sort_keys=True, separators=(",", ":"),
                            allow_nan=False) + "\n").encode()
    need(raw[:HEADER_BYTES] == canonical + bytes(HEADER_BYTES - len(canonical)),
         "unchanged accepted journal header encoding")
    previous = bytes(32)
    result = []
    for ordinal in range(count):
        offset = HEADER_BYTES + ordinal * RECORD.size
        values = RECORD.unpack_from(raw, offset)
        need(values[0] == ordinal, "exact committed row ordinal")
        need(all(math.isfinite(x) for x in values[1:8]), "seven finite committed actions")
        need(values[9] == previous, "unbroken journal predecessor chain")
        need(values[10] == hashlib.sha256(raw[offset:offset + 128]).digest(),
             "journal record checksum")
        previous = values[10]
        result.append(list(values[1:8]))
    need(previous.hex() == descriptor["final_chain"], "selected complete final chain")
    return result


def convert(descriptors, load_journal, source_inputs, *, scorer_path=None):
    """Convert the complete original 56-journal panel to current scorer JSON.

    descriptors: exact run-major host entries (run, arm, file, bytes, sha256,
    final_chain). source_inputs: operator-supplied original input pins keyed by
    every query run, not the separately prepared 368-byte-row cache pins.
    load_journal(filename) returns already captured immutable bytes. It is a
    trusted operator callback, never a participant callback. No target callback
    exists. The caller owns filesystem capture, deadlines and source custody.
    """
    scorer = load_scorer(scorer_path)
    runs = {run for run, _, _ in scorer.QUERY}
    need(type(source_inputs) is dict and set(source_inputs) == runs, "all and only original query input pins")
    inputs = {run: input_pin(source_inputs[run]) for run in runs}
    need(type(descriptors) is list and len(descriptors) == len(scorer.QUERY) * len(scorer.ARMS),
         "complete 56 journal descriptors")
    expected = [(r, s, n, a) for r, s, n in scorer.QUERY for a in scorer.ARMS]
    captured_descriptors = []
    for desc, (run, _, count, arm) in zip(descriptors, expected):
        exact(desc, ("run", "arm", "file", "bytes", "sha256", "final_chain"), "journal descriptor fields")
        need(desc["run"] == run and desc["arm"] == arm and desc["file"] == f"{run}__{arm}.bin",
             "exact original run-major journal order and filename")
        need(type(desc["bytes"]) is int and desc["bytes"] == HEADER_BYTES + count * RECORD.size,
             "complete full-run journal extent")
        need(digest(desc["sha256"]) and digest(desc["final_chain"]), "journal byte pin and final chain")
        captured_descriptors.append(dict(desc))
    need(callable(load_journal), "operator journal loader")
    captured = {}
    # All descriptor and input identities are snapshotted before any callback.
    for desc, (run, session, count, arm) in zip(captured_descriptors, expected):
        raw = load_journal(desc["file"])
        captured[(arm, run)] = {
            "arm": arm, "run": run, "session": session,
            "row_ids": list(range(count)),
            "prediction": prediction(raw, desc, run, arm, count, inputs[run]),
        }
    submission = {
        "schema": "neural067_session_predictions_v1", "contract_sha256": scorer.CONTRACT_SHA256,
        "columns": list(scorer.COLUMNS),
        "entries": [captured[(arm, run)] for arm in scorer.ARMS for run, _, _ in scorer.QUERY],
    }
    scorer.admit(submission)
    return submission
