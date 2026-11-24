"""Participant-side NEURAL-067 framing; no decoder, targets or evaluator.

Bundle this source with a participant method using bundle.py. The submitted
program is one file and uses only this standard-library transport helper.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys

ARMS = ("neural", "clock", "neural_clock", "shifted_neural_clock")
STATE_CAP = 33_554_432
INPUT_CAP = 4096
ACTION_CAP = 1024


def need(ok, message):
    if not ok:
        raise ValueError(message)


def parse(body):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, "duplicate JSON member")
            result[key] = value
        return result

    def invalid(_):
        raise ValueError("nonfinite JSON literal")

    return json.loads(body, object_pairs_hook=unique, parse_constant=invalid)


def frame(value):
    raw = (json.dumps(value, allow_nan=False, separators=(",", ":")) + "\n").encode("ascii")
    need(len(raw) <= ACTION_CAP, "action exceeds host line limit")
    return raw


def write_all(output, body):
    view = memoryview(body)
    while view:
        count = output.write(view)
        need(type(count) is int and 0 < count <= len(view), "complete protocol write")
        view = view[count:]
    output.flush()


def write_state(body, output):
    """Write the host's opaque state frame, not a pickled object or JSON line."""
    need(type(body) is bytes and 0 < len(body) <= STATE_CAP, "nonempty bounded byte state")
    header = b"N067STATE1\n" + struct.pack("<Q", len(body)) + hashlib.sha256(body).digest()
    write_all(output, header)
    write_all(output, body)


class Query:
    """One fresh run; each call accepts one current observation or the end frame."""

    def __init__(self, arm, step):
        need(arm in ARMS and callable(step), "declared arm and prediction callback")
        self.arm, self.step = arm, step
        self.ordinal, self.token, self.closed = 0, None, False

    def ready(self):
        return frame({"schema": "neural067_ready_v1", "arm": self.arm})

    def accept(self, body):
        need(not self.closed, "no input after stopped acknowledgement")
        need(type(body) is bytes and 0 < len(body) <= INPUT_CAP and body.endswith(b"\n"),
             "one bounded complete host line")
        need(body.count(b"\n") == 1, "one host frame per call")
        value = parse(body.decode("ascii"))
        need(type(value) is dict, "host frame object")
        if value.get("schema") == "neural067_end_v1":
            need(set(value) == {"schema", "token"} and self.ordinal > 0
                 and value["token"] == self.token, "matching nonempty-run end")
            self.closed = True
            return frame({"schema": "neural067_stopped_v1", "token": self.token})
        need(set(value) == {"schema", "token", "ordinal", "observation"}
             and value["schema"] == "neural067_observation_v1", "exact observation frame")
        token, ordinal, observation = value["token"], value["ordinal"], value["observation"]
        need(type(token) is str and re.fullmatch("[a-f0-9]{32,64}", token) is not None
             and (self.token is None or token == self.token), "one opaque run token")
        need(type(ordinal) is int and ordinal == self.ordinal, "ordered current ordinal")
        fields = set()
        if self.arm != "clock":
            fields.add("spikes")
        if self.arm != "neural":
            fields.update(("elapsed_run_s", "observed_segment_age_s", "segment_started_now"))
        need(type(observation) is dict and set(observation) == fields, "exact arm observation fields")
        if "spikes" in observation:
            counts = observation["spikes"]
            need(type(counts) is list and len(counts) == 176
                 and all(type(x) is int and 0 <= x <= 255 for x in counts), "176 source counts")
        for key in ("elapsed_run_s", "observed_segment_age_s"):
            if key in observation:
                x = observation[key]
                need(type(x) in (int, float) and math.isfinite(x) and x >= 0, "finite elapsed clock")
        if "segment_started_now" in observation:
            need(type(observation["segment_started_now"]) is bool, "segment boundary boolean")
        prediction = self.step(observation)
        need(type(prediction) is list and len(prediction) == 7
             and all(type(x) in (int, float) and math.isfinite(x) for x in prediction),
             "prediction must be a list of seven finite Python numbers")
        response = frame({"schema": "neural067_action_v1", "token": token,
                          "ordinal": ordinal, "prediction": prediction})
        self.token, self.ordinal = token, self.ordinal + 1
        return response


def query(arm, step, source, output):
    """Flush one action before reading another frame; EOF without end is failure."""
    session = Query(arm, step)
    write_all(output, session.ready())
    while not session.closed:
        body = source.readline(INPUT_CAP + 1)
        need(body != b"", "host EOF before complete end handshake")
        write_all(output, session.accept(body))
    # The host waits for stopped, then closes stdin. Waiting for EOF here would
    # deadlock that handshake. Return and let the program exit naturally.
    return session.ordinal


def entry(fit, start, argv=None, source=None, output=None):
    """Dispatch the existing host CLI to participant fit/start callbacks.

    fit(train_descriptor_path, arm) -> nonempty bytes.
    start(state_bytes, arm) -> step(observation) -> list of seven finite numbers.
    start is called afresh for every process/run. This helper neither enforces
    a scientific fitting recipe nor certifies a participant method's behavior.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    phases = parser.add_subparsers(dest="phase", required=True)
    train = phases.add_parser("train")
    train.add_argument("--arm", choices=ARMS, required=True)
    train.add_argument("--train", type=Path, required=True)
    train.add_argument("--state-stdout", action="store_true", required=True)
    predict = phases.add_parser("predict")
    predict.add_argument("--arm", choices=ARMS, required=True)
    predict.add_argument("--state", type=Path, required=True)
    predict.add_argument("--protocol", choices=("neural067_causal_v1",), required=True)
    args = parser.parse_args(argv)
    source = sys.stdin.buffer if source is None else source
    output = sys.stdout.buffer if output is None else output
    if args.phase == "train":
        need(callable(fit), "fit callback")
        write_state(fit(args.train, args.arm), output)
    else:
        need(callable(start), "start callback")
        with args.state.open("rb") as stream:
            state = stream.read(STATE_CAP + 1)
        need(0 < len(state) <= STATE_CAP, "bounded saved state body")
        query(args.arm, start(state, args.arm), source, output)
