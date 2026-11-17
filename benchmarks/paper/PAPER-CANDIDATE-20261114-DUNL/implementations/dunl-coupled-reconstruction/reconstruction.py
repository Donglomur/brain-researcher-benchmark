"""Source-only DUNL constrained reconstruction evaluator; no prediction claim."""
import argparse
import hashlib
import json
import math
import os
import re
import stat
import sys

LINE_LIMIT = 262144
TOTAL_LIMIT = 134217728
VALUE_LIMIT = 1000000
MAX_CASES = 4096
ABS_TOL = 1e-7
REL_TOL = 1e-6
PROFILE = "unqualified_current_code_reconstruction_v1"
ARMS = {"paper_data", "paper_data_official_code"}
FIXED = {"profile": PROFILE, "kernel_samples": 25, "code_stride": 1,
         "padding": 0, "original_sample_period_us": 1000,
         "samples_per_bin": 5, "bin_period_us": 5000,
         "baseline_mode": "scalar_logit_per_case",
         "observation_units": "normalized_sum_of_five_samples"}


class Refusal(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Refusal(message)


def keys(value, wanted, label):
    require(type(value) is dict and set(value) == set(wanted), label + " fields")


def identifier(value):
    require(type(value) is str and re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", value),
            "opaque identifier")
    return value


def sha(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), "sha256")
    return value


def number(value, limit=1e12):
    require(type(value) in (int, float), "numeric value type")
    require(math.isfinite(value) and abs(value) <= limit, "numeric value range")
    return float(value)


def vector(value, length, *, nonnegative=False, probability=False):
    require(type(value) is list and len(value) == length, "vector length")
    result = [number(x) for x in value]
    if nonnegative:
        require(all(x >= 0 for x in result), "nonnegative code")
    if probability:
        require(all(0 <= x <= 1 for x in result), "normalized response range")
    return result


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def reject_constant(value):
    raise Refusal("nonfinite JSON constant")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


class Lines:
    def __init__(self, stream):
        self.stream = stream
        self.digest = hashlib.sha256()
        self.bytes_read = 0

    def read(self, *, eof=False):
        raw = self.stream.readline(LINE_LIMIT + 1)
        self.bytes_read += len(raw)
        self.digest.update(raw)
        require(len(raw) <= LINE_LIMIT and self.bytes_read <= TOTAL_LIMIT,
                "input capacity exceeded; complete population must not be reduced")
        if not raw:
            require(eof, "missing record")
            return None
        require(not eof, "extra record")
        require(raw.endswith(b"\n"), "newline-terminated JSONL required")
        try:
            return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                              parse_constant=reject_constant)
        except (UnicodeError, ValueError) as exc:
            raise Refusal("invalid JSON record") from exc


def owner_header(header):
    keys(header, set(FIXED) | {"schema", "cohort_id", "source_cohort_sha256",
                              "response_samples", "roster"}, "owner header")
    require(header["schema"] == "dunl_reconstruction_owner_v1", "owner schema")
    for key, expected in FIXED.items():
        require(type(header[key]) is type(expected) and header[key] == expected,
                "fixed scientific convention")
    identifier(header["cohort_id"])
    sha(header["source_cohort_sha256"])
    length = header["response_samples"]
    require(type(length) is int and 25 <= length <= 4096, "response samples")
    roster = header["roster"]
    require(type(roster) is list and 1 <= len(roster) <= MAX_CASES, "roster size")
    require(len(roster) * length <= VALUE_LIMIT, "complete convolution work ceiling")
    case_ids, identities = set(), set()
    for item in roster:
        keys(item, {"case_id", "neuron_id", "trial_id"}, "roster row")
        for value in item.values():
            identifier(value)
        pair = (item["neuron_id"], item["trial_id"])
        require(item["case_id"] not in case_ids and pair not in identities,
                "duplicate case or neuron/trial identity")
        case_ids.add(item["case_id"])
        identities.add(pair)
    return length, roster


def context_id(header):
    # Header only: target changes cannot modify the common context digest.
    return hashlib.sha256(canonical(header)).hexdigest()


def sigmoid(value):
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp = math.exp(value)
    return exp / (1.0 + exp)


def normalized_loss(logit, y):
    # Stable mathematical source loss; not bitwise torch.log1p(exp()) parity.
    return (1.0 - y) * logit + math.log1p(math.exp(-logit)) if logit >= 0 else (
        -y * logit + math.log1p(math.exp(logit)))


def decode(kernel, code, baseline):
    """One-channel conv_transpose1d: stride1, padding0, no kernel reversal."""
    return [baseline + math.fsum(kernel[k] * code[t - k]
            for k in range(max(0, t - len(code) + 1), min(25, t + 1)))
            for t in range(len(code) + 24)]


def close(actual, expected):
    return abs(actual - expected) <= ABS_TOL + REL_TOL * abs(expected)


def score_streams(owner_stream, submission_stream, owner_sha256, expected_arm):
    """The evaluator selects both trust arguments, never the participant."""
    sha(owner_sha256)
    require(type(expected_arm) is str and expected_arm in ARMS, "trusted arm")
    own, sub = Lines(owner_stream), Lines(submission_stream)
    header = own.read()
    length, roster = owner_header(header)
    submission = sub.read()
    keys(submission, {"schema", "context_id", "arm", "kernel",
                      "method_manifest_sha256"}, "submission header")
    require(submission["schema"] == "dunl_reconstruction_submission_v1",
            "submission schema")
    require(submission["context_id"] == context_id(header), "context mismatch")
    require(type(submission["arm"]) is str and submission["arm"] in ARMS, "arm")
    require(submission["arm"] == expected_arm, "operator-selected arm mismatch")
    sha(submission["method_manifest_sha256"])
    kernel = vector(submission["kernel"], 25)
    norm = math.hypot(*kernel)
    require(abs(norm - 1.0) <= 1e-6, "signed discrete-unit-L2 kernel")
    neuron_sums = {}
    all_case_losses, all_case_mses = [], []
    max_eta_error, max_response_error = 0.0, 0.0
    code_entries, positive_entries, code_sum = 0, 0, 0.0
    for expected in roster:
        target, row = own.read(), sub.read()
        keys(target, {"case_id", "y"}, "owner case")
        keys(row, {"case_id", "code", "baseline", "eta", "p"}, "submission case")
        require(target["case_id"] == row["case_id"] == expected["case_id"],
                "complete ordered case identity")
        y = vector(target["y"], length, probability=True)
        code = vector(row["code"], length - 24, nonnegative=True)
        baseline = number(row["baseline"])
        eta = vector(row["eta"], length)
        response = vector(row["p"], length, probability=True)
        derived_eta = decode(kernel, code, baseline)
        require(all(math.isfinite(x) for x in derived_eta), "decoder arithmetic")
        derived_p = [sigmoid(x) for x in derived_eta]
        require(all(close(a, b) for a, b in zip(eta, derived_eta)), "uncoupled logits")
        require(all(close(a, b) for a, b in zip(response, derived_p)),
                "uncoupled inverse-link response")
        max_eta_error = max(max_eta_error, max(abs(a-b) for a,b in zip(eta, derived_eta)))
        max_response_error = max(max_response_error,
                                 max(abs(a-b) for a,b in zip(response, derived_p)))
        # Score recomputed values: tolerance cannot improve the score.
        loss = math.fsum(normalized_loss(a, b) for a,b in zip(derived_eta, y)) / length
        mse = math.fsum((a-b)**2 for a,b in zip(derived_p, y)) / length
        all_case_losses.append(loss)
        all_case_mses.append(mse)
        neuron = neuron_sums.setdefault(expected["neuron_id"], [[], []])
        neuron[0].append(loss)
        neuron[1].append(mse)
        code_entries += len(code)
        positive_entries += sum(x > 0 for x in code)
        code_sum += math.fsum(code)
    own.read(eof=True)
    sub.read(eof=True)
    require(own.digest.hexdigest() == owner_sha256, "owner file identity")
    neurons = [{"neuron_id": key, "cases": len(vals[0]),
                "normalized_response_loss": math.fsum(vals[0]) / len(vals[0]),
                "normalized_response_mse": math.fsum(vals[1]) / len(vals[1])}
               for key, vals in sorted(neuron_sums.items())]
    return {"schema": "dunl_coupled_reconstruction_score_v1",
            "profile": PROFILE, "context_id": context_id(header),
            "arm": submission["arm"], "owner_sha256": owner_sha256,
            "submission_sha256": sub.digest.hexdigest(),
            "source_cohort_sha256": header["source_cohort_sha256"],
            "method_manifest_sha256": submission["method_manifest_sha256"],
            "cases": len(roster), "neurons": len(neurons), "response_samples": length,
            "scored_values": len(roster)*length, "kernel_norm": norm,
            "normalized_response_loss": math.fsum(all_case_losses)/len(roster),
            "normalized_response_mse": math.fsum(all_case_mses)/len(roster),
            "equal_neuron_loss": math.fsum(n["normalized_response_loss"] for n in neurons)/len(neurons),
            "per_neuron": neurons, "code_entries_including_zeros": code_entries,
            "positive_code_entries": positive_entries, "coefficient_sum": code_sum,
            "maximum_submitted_eta_error": max_eta_error,
            "maximum_submitted_response_error": max_response_error,
            "complete_declared_roster": True,
            "authentic_population_completeness_verified": False,
            "method_training_lineage_verified": False,
            "historical_runtime_parity_verified": False,
            "protected_prediction_established": False,
            "scientific_qualification": False,
            "bytes_read": {"owner": own.bytes_read, "submission": sub.bytes_read}}


def identity(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def open_input(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_size > TOTAL_LIMIT:
        os.close(fd)
        raise Refusal("regular bounded input required")
    return os.fdopen(fd, "rb"), identity(st)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--owner-sha256", required=True)
    parser.add_argument("--submission", required=True)
    parser.add_argument("--arm", choices=sorted(ARMS), required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        owner, own_id = open_input(args.owner)
        with owner:
            submission, sub_id = open_input(args.submission)
            with submission:
                result = score_streams(owner, submission, args.owner_sha256, args.arm)
                require(identity(os.fstat(owner.fileno())) == own_id and
                        identity(os.fstat(submission.fileno())) == sub_id,
                        "input identity changed")
        encoded = canonical(result) + b"\n"
        require(len(encoded) <= LINE_LIMIT, "result capacity")
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        print('{"status":"complete","scientific_qualification":false}')
        return 0
    except (OSError, Refusal, OverflowError, RecursionError) as exc:
        # Do not emit target values, identifiers, numerical scores or input paths.
        print(json.dumps({"status": "refused", "error_type": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
