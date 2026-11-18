"""Independent fixed calibration-rate candidate for NEURAL-024.

Future invocation: python -I -B /program/program.py
The only data file opened is /training/calibration_counts.npz.  The supplied
source_counts.npz is intentionally unused.  No optimizer or online update is
performed: every prediction is (sum(calibration[10:3000]) + .5) / (2990 + .5),
in counts per bin, separately for each of the 96 physical electrode channels.
NumPy is imported only by main when this candidate is eventually executed.
"""

import json
import math
import sys


PROTOCOL = "NEURAL024-causal-v1"
CALIBRATION_PATH = "/training/calibration_counts.npz"
CALIBRATION_ROWS = 3000
CHANNELS = 96
ROUNDS = 22100
WARMUP_ROUNDS = 10
SCORED_ROUNDS = 22090
UINT32_MAX = 4294967295
MAX_REQUEST_BYTES = 4096
MAX_REPLY_BYTES = 4096  # Includes the terminating newline.
INITIALIZE = {
    "protocol": PROTOCOL,
    "status": "initialize",
    "rounds": ROUNDS,
    "warmup_rounds": WARMUP_ROUNDS,
    "scored_rounds": SCORED_ROUNDS,
    "channels": CHANNELS,
    "mean_unit": "count_per_bin",
}


class ProtocolError(ValueError):
    """Invalid data or protocol input; the process must fail without retry."""


def require(condition, message):
    if not condition:
        raise ProtocolError(message)


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def calibration_model(np, counts, edges):
    """Validate the declared calibration arrays and return a fixed model.

    uint64 sums cannot overflow: 2990 * (2**32 - 1) < 2**53.  Conversion to
    float64 therefore preserves the integer sum before adding the half-count.
    Native absolute edges remain unmodified.  The wire clock is relative to
    their first value, so the first prediction begins at edges[-1]-edges[0].
    """
    require(counts.shape == (CALIBRATION_ROWS, CHANNELS), "calibration shape")
    require(counts.dtype == np.dtype("uint32"), "calibration count dtype")
    require(edges.shape == (CALIBRATION_ROWS + 1,), "calibration edge shape")
    require(edges.dtype == np.dtype("float64"), "calibration edge dtype")
    require(bool(np.all(np.isfinite(edges))), "nonfinite calibration edge")
    require(bool(np.all(edges[1:] > edges[:-1])), "unordered calibration edges")
    sums = counts[WARMUP_ROUNDS:CALIBRATION_ROWS].sum(axis=0, dtype=np.uint64)
    rates = (sums.astype(np.float64) + 0.5) / (
        CALIBRATION_ROWS - WARMUP_ROUNDS + 0.5
    )
    means = rates.tolist()
    require(all(finite_number(x) and x > 0 for x in means), "invalid mean")
    first_begin = float(edges[-1] - edges[0])
    require(finite_number(first_begin) and first_begin > 0, "calibration duration")
    return means, first_begin


def load_calibration(np):
    """Read the one permitted training file, without opening source_counts."""
    with np.load(CALIBRATION_PATH, allow_pickle=False) as archive:
        require(
            len(archive.files) == 2
            and set(archive.files) == {"counts", "bin_edges_seconds"},
            "calibration members",
        )
        return calibration_model(np, archive["counts"], archive["bin_edges_seconds"])


def exact_keys(value, keys, message):
    require(type(value) is dict and set(value) == set(keys), message)


def validate_observation(value, target_bin):
    exact_keys(value, ("target_bin", "counts"), "observation keys")
    require(type(value["target_bin"]) is int and value["target_bin"] == target_bin,
            "observation target bin")
    counts = value["counts"]
    require(type(counts) is list and len(counts) == CHANNELS, "observation channels")
    require(all(type(x) is int and 0 <= x <= UINT32_MAX for x in counts),
            "observation uint32 counts")


class FixedRateSession:
    """Protocol state only; observations are checked and then discarded."""

    def __init__(self, mean_counts, first_begin):
        require(type(mean_counts) in (list, tuple) and len(mean_counts) == CHANNELS,
                "model channels")
        require(all(finite_number(x) and x > 0 for x in mean_counts), "model means")
        require(finite_number(first_begin) and first_begin > 0, "model first begin")
        self.mean_counts = tuple(float(x) for x in mean_counts)
        self.previous_end = float(first_begin)
        self.next_sequence = 0
        self.phase = "initialize"

    def handle(self, request):
        if self.phase == "initialize":
            exact_keys(request, INITIALIZE, "initialize keys")
            require(all(type(request[k]) is type(v) and request[k] == v
                        for k, v in INITIALIZE.items()), "initialize contract")
            self.phase = "predict"
            return {"status": "initialized", "protocol": PROTOCOL}

        if self.phase == "stop":
            exact_keys(request, ("protocol", "status", "observation"), "stop keys")
            require(request["protocol"] == PROTOCOL and request["status"] == "stop",
                    "stop contract")
            validate_observation(request["observation"], CALIBRATION_ROWS + ROUNDS - 1)
            self.phase = "stopped"
            return {"status": "stopped"}

        require(self.phase == "predict", "session already stopped")
        exact_keys(request, ("protocol", "status", "sequence", "target_bin",
                             "interval", "scored", "nonce", "observation"),
                   "prediction keys")
        require(request["protocol"] == PROTOCOL and request["status"] == "predict",
                "prediction contract")
        seq = self.next_sequence
        require(type(request["sequence"]) is int and request["sequence"] == seq,
                "prediction sequence")
        require(type(request["target_bin"]) is int
                and request["target_bin"] == CALIBRATION_ROWS + seq, "target bin")
        require(type(request["scored"]) is bool
                and request["scored"] == (seq >= WARMUP_ROUNDS), "scoring flag")
        nonce = request["nonce"]
        require(type(nonce) is str and len(nonce) == 32
                and all(c in "0123456789abcdefABCDEF" for c in nonce), "nonce")
        interval = request["interval"]
        require(type(interval) is list and len(interval) == 2
                and all(finite_number(x) for x in interval), "interval numbers")
        begin, end = interval
        require(begin == self.previous_end and end > begin, "interval continuity")
        if seq == 0:
            require(request["observation"] is None, "first observation must be null")
        else:
            validate_observation(request["observation"], CALIBRATION_ROWS + seq - 1)
        # The revealed previous row cannot alter the fixed calibration estimate.
        response = {"sequence": seq, "nonce": nonce,
                    "mean_counts": list(self.mean_counts)}
        self.previous_end = end
        self.next_sequence += 1
        if self.next_sequence == ROUNDS:
            self.phase = "stop"
        return response


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ProtocolError("nonstandard JSON constant")


def read_message(stream):
    line = stream.readline(MAX_REQUEST_BYTES + 1)
    require(bool(line), "EOF before stop")
    require(len(line) <= MAX_REQUEST_BYTES and line.endswith(b"\n"),
            "request framing or byte cap")
    value = json.loads(line.decode("utf-8"), object_pairs_hook=_unique_object,
                       parse_constant=_reject_constant)
    require(type(value) is dict, "request must be an object")
    return value


def encode_message(value):
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")
    require(len(payload) <= MAX_REPLY_BYTES, "reply byte cap")
    return payload


def write_message(stream, value):
    stream.write(encode_message(value))
    stream.flush()


def run_session(input_stream, output_stream, mean_counts, first_begin):
    session = FixedRateSession(mean_counts, first_begin)
    write_message(output_stream, {"status": "ready"})
    while session.phase != "stopped":
        write_message(output_stream, session.handle(read_message(input_stream)))
    return 0


def main():
    try:
        require(len(sys.argv) == 1, "unexpected command arguments")
        import numpy as np
        means, first_begin = load_calibration(np)
        return run_session(sys.stdin.buffer, sys.stdout.buffer, means, first_begin)
    except Exception as error:
        # No fallback, partial-rate replacement, retry or additional file access.
        print("calibration_rate: " + type(error).__name__ + ": " + str(error),
              file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
