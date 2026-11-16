"""Bounded arbitrary-summary scoring; stdlib only, no candidate imports.

This scores a declared numerical reconstruction target. It does not prove a
summary was produced by inference, calibrate a scientific pass threshold, or
adjudicate underidentified alternatives in the primary paper-only task.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat

CONDITIONS = ("ECG_not_rejected", "ECG_rejected", "ECG_components")
MODELS = tuple(scale + "__" + condition for scale in ("raw", "zscore") for condition in CONDITIONS)
VARIABLES = ("alpha_c", "beta", "sigma", "nu", "alpha")
FIELDS = {"mean", "sd_population", "hdi_94_low", "hdi_94_high", "mcse_mean_batch"}
MAX_BYTES = 200_000


def need(ok, message):
    if not ok:
        raise ValueError(message)


def unique(pairs):
    out = {}
    for key, value in pairs:
        need(key not in out, "duplicate JSON key")
        out[key] = value
    return out


def finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def read_json(path, cap=MAX_BYTES):
    """Snapshot a bounded regular single-link file; reject link/TOCTOU changes."""
    path = Path(path)
    need(not any(p.is_symlink() for p in (path, *path.parents)), "symlink path")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             "bounded regular single-link JSON")
        chunks, left = [], before.st_size
        while left:
            part = os.read(fd, min(left, 65536))
            need(part, "truncated JSON")
            chunks.append(part); left -= len(part)
        need(not os.read(fd, 1), "growing JSON")
        after, named = os.fstat(fd), path.lstat()
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
        need(identity(before) == identity(after) == identity(named), "JSON changed during snapshot")
    finally:
        os.close(fd)
    raw = b"".join(chunks)
    def bad_constant(value):
        raise ValueError("nonfinite JSON token: " + value)
    value = json.loads(raw.decode("utf8"), object_pairs_hook=unique, parse_constant=bad_constant)
    return value, {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def validate(value):
    need(type(value) is dict and set(value) == {"schema_version", "input_sha256", "target", "models"}, "exact summary root")
    need(type(value["schema_version"]) is int and value["schema_version"] == 1, "schema version")
    digest = value["input_sha256"]
    need(type(digest) is str and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), "input SHA256")
    need(value["target"] == "salzburg_bambi091_six_student_t_targets", "declared shared-spec target")
    need(type(value["models"]) is dict and set(value["models"]) == set(MODELS), "six unique model identities")
    for name in MODELS:
        model = value["models"][name]
        need(type(model) is dict and set(model) == {"summary", "diagnostics"}, "exact model fields")
        need(type(model["summary"]) is dict and set(model["summary"]) == set(VARIABLES), "five parameter summaries")
        for variable in VARIABLES:
            row = model["summary"][variable]
            need(type(row) is dict and set(row) == FIELDS, "exact summary fields")
            need(all(finite(row[k]) for k in FIELDS - {"mcse_mean_batch"}), "finite numerical summaries, not bool")
            need(row["sd_population"] > 0 and row["hdi_94_low"] <= row["hdi_94_high"], "positive SD and ordered interval")
            need(row["mcse_mean_batch"] is None or finite(row["mcse_mean_batch"]) and row["mcse_mean_batch"] >= 0, "optional finite nonnegative MCSE")
            if variable in ("sigma", "nu"):
                need(row["mean"] > 0 and row["hdi_94_low"] >= 0, "positive-parameter support")
            # For skew distributions the mean need not lie inside the shortest HDI.
        diagnostics = model["diagnostics"]
        need(type(diagnostics) is dict and set(diagnostics) == {"chains", "draws_per_chain", "tune_per_chain", "divergences", "max_rhat", "min_ess_bulk", "min_ess_tail"}, "exact diagnostic fields")
        for key in ("chains", "draws_per_chain", "tune_per_chain", "divergences"):
            need(diagnostics[key] is None or type(diagnostics[key]) is int and diagnostics[key] >= 0, "diagnostic count or explicit unavailable")
        for key in ("max_rhat", "min_ess_bulk", "min_ess_tail"):
            need(diagnostics[key] is None or finite(diagnostics[key]) and diagnostics[key] > 0, "diagnostic value or explicit unavailable")
    return value


def rope(row):
    low, high = row["hdi_94_low"], row["hdi_94_high"]
    if low >= -.1 and high <= .1:
        return "hdi_within_rope"
    if high < -.1:
        return "hdi_below_rope"
    if low > .1:
        return "hdi_above_rope"
    return "unresolved_by_hdi_rope_rule"


def _compute(candidate, reference):
    def ratio(numerator, denominator):
        value = numerator / denominator
        if numerator != 0 and value == 0:
            raise OverflowError("nonzero derived ratio underflowed")
        return value
    results, primary = {}, []
    for name in MODELS:
        parameters = {}
        for variable in VARIABLES:
            c, r = candidate["models"][name]["summary"][variable], reference["models"][name]["summary"][variable]
            scale = r["sd_population"]
            difference = c["mean"] - r["mean"]
            combined = None if c["mcse_mean_batch"] is None or r["mcse_mean_batch"] is None else math.hypot(c["mcse_mean_batch"], r["mcse_mean_batch"])
            parameters[variable] = {
                "mean_signed_difference": difference,
                "mean_difference_reference_sd": ratio(difference, scale),
                "sd_difference_reference_sd": ratio(c["sd_population"] - scale, scale),
                "hdi_endpoint_difference_reference_sd": [ratio(c[k] - r[k], scale) for k in ("hdi_94_low", "hdi_94_high")],
                "combined_batch_mcse_independence_approximation": combined,
                "mean_difference_over_combined_batch_mcse": ratio(difference, combined) if combined else None,
            }
        primary.append(parameters["beta"]["mean_difference_reference_sd"])
        results[name] = {"parameters": parameters, "candidate_diagnostics_as_reported": candidate["models"][name]["diagnostics"]}
        if name.startswith("zscore__"):
            results[name]["candidate_hdi_rope_disposition"] = rope(candidate["models"][name]["summary"]["beta"])
            results[name]["reference_hdi_rope_disposition"] = rope(reference["models"][name]["summary"]["beta"])
        else:
            c, r = candidate["models"][name]["summary"], reference["models"][name]["summary"]
            results[name]["location_mean_rmse_age18_through73_response_units"] = math.hypot(*[
                (c["alpha"]["mean"]-r["alpha"]["mean"]) + age*(c["beta"]["mean"]-r["beta"]["mean"])
                for age in range(18, 74)]) / math.sqrt(56)
    return {"status": "valid_summary_continuously_scored", "primary_beta_mean_rmse_reference_sd": math.hypot(*primary)/math.sqrt(6),
            "primary_direction": "lower", "models": results, "scientific_pass": None,
            "limitations": ["No calibrated scientific acceptance threshold; schema validity is not inference correctness.",
                "Candidate diagnostics/MCSE are self-reported unless separately audited against supplied draws.",
                "Combined MCSE assumes independent runs; source-reuse/transport and shared random paths violate that assumption.",
                "Fixed 100-draw batch MCSE is approximate; it does not calibrate HDI error or prove convergence.",
                "A raw/z paired difference is not a joint biological condition contrast; no improvement/generalization claim."]}


def score(candidate, reference):
    validate(candidate); validate(reference)
    need(candidate["input_sha256"] == reference["input_sha256"], "same exact input bytes")
    def finite_derived(value):
        if type(value) is float:
            return math.isfinite(value)
        if type(value) is dict:
            return all(finite_derived(v) for v in value.values())
        if type(value) is list:
            return all(finite_derived(v) for v in value)
        return True
    try:
        result = _compute(candidate, reference)
        if not finite_derived(result):
            raise OverflowError("nonfinite derived metric")
        return result
    except (OverflowError, ZeroDivisionError) as error:
        return {"status": "unsupported_derived_numerics", "primary_beta_mean_rmse_reference_sd": None,
                "scientific_pass": None, "schema_valid": True, "error_type": type(error).__name__,
                "reason": "Finite declared summaries exceed supported floating-point derived arithmetic; no clipping, cap, rank or scientific score assigned."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    candidate, candidate_pin = read_json(args.submission)
    validate(candidate)  # Must precede any private reference open.
    reference, reference_pin = read_json(args.reference)
    result = score(candidate, reference)
    result.update(submission_pin=candidate_pin, reference_pin=reference_pin)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False); stream.write("\n")


if __name__ == "__main__":
    main()
