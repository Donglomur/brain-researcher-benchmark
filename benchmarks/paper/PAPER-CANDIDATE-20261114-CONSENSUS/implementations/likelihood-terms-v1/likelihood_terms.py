"""Recompute supplied Consensus occurrence LL terms, without a paper score.

Inputs are evaluator-private observations and expected counts, already expressed
per bin. This component does not authenticate their origin or derive the PSTH.
"""
from __future__ import annotations

import json
import math
import sys

MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_RECORDS = 10000
MAX_TOTAL_BINS = 200000
EXACT_INTEGER_LIMIT = 2**53
KEY_FIELDS = ("animal_id", "fold_id", "model_variant", "condition_id",
              "target_neuron_id", "source_trial_index", "occurrence_index")
RECORD_FIELDS = ("key", "time_bin_ids", "target_counts", "model_expected_counts",
                 "psth_expected_counts", "reported_model_ll_terms",
                 "reported_psth_ll_terms")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def exact_keys(value, fields, label):
    require(type(value) is dict and set(value) == set(fields), label + ": fields")


def finite_number(value, label):
    require(type(value) in (int, float), label + ": numeric value required")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(label + ": finite representable value required") from exc
    require(math.isfinite(result), label + ": finite representable value required")
    return result


def context(value):
    exact_keys(value, KEY_FIELDS, "occurrence key")
    for field in ("animal_id", "condition_id", "target_neuron_id"):
        require(type(value[field]) is str and 0 < len(value[field]) <= 256,
                field + ": nonempty bounded identifier required")
    require(type(value["fold_id"]) is int and value["fold_id"] in (0, 1, 2),
            "fold_id: original fold 0, 1 or 2 required")
    require(value["model_variant"] in ("constrained", "unconstrained"),
            "model_variant: original model family required")
    for field in ("source_trial_index", "occurrence_index"):
        require(type(value[field]) is int and 0 <= value[field] <= EXACT_INTEGER_LIMIT,
                field + ": nonnegative exact integer required")
    return tuple(value[field] for field in KEY_FIELDS)


def vector(value, size, label):
    require(type(value) is list and len(value) == size, label + ": aligned extent required")
    return [finite_number(item, label) for item in value]


def prepare(record):
    exact_keys(record, RECORD_FIELDS, "record")
    identity = context(record["key"])
    bins = record["time_bin_ids"]
    require(type(bins) is list and 0 < len(bins) <= MAX_TOTAL_BINS,
            "nonempty bounded time-bin support required")
    require(all(type(x) is int and 0 <= x <= EXACT_INTEGER_LIMIT for x in bins),
            "time-bin IDs must be nonnegative exact integers")
    require(all(left < right for left, right in zip(bins, bins[1:])),
            "time-bin IDs must retain strictly increasing supplied order")
    n = len(bins)
    counts = record["target_counts"]
    require(type(counts) is list and len(counts) == n, "target_counts: aligned extent required")
    clean_counts = []
    for count in counts:
        require(type(count) in (int, float), "target_counts: exact nonnegative counts required")
        # Check integer values before conversion so uint-like large integers cannot round down.
        require(0 <= count <= EXACT_INTEGER_LIMIT, "target_counts: exact numeric range")
        value = finite_number(count, "target_counts")
        require(value.is_integer(), "target_counts: exact nonnegative counts required")
        clean_counts.append(int(count))
    model = vector(record["model_expected_counts"], n, "model_expected_counts")
    psth = vector(record["psth_expected_counts"], n, "psth_expected_counts")
    require(all(x > 0 for x in model + psth),
            "nonpositive expected counts: native zero-rate policy unresolved")
    reported = []
    for field in ("reported_model_ll_terms", "reported_psth_ll_terms"):
        supplied = record[field]
        reported.append(None if supplied is None else vector(supplied, n, field))
    return identity, clean_counts, model, psth, reported


def term(count, expected_count):
    value = count * math.log(expected_count) - expected_count
    require(math.isfinite(value), "nonfinite computed LL term; no clipping or replacement")
    return value


def finite_sum(values):
    try:
        value = math.fsum(values)
    except OverflowError as exc:
        raise ValueError("nonfinite LL sum; no clipping or replacement") from exc
    require(math.isfinite(value), "nonfinite LL sum; no clipping or replacement")
    return value


def comparison(calculated, supplied):
    if supplied is None:
        return None
    difference = [right - left for left, right in zip(calculated, supplied)]
    require(all(math.isfinite(x) for x in difference), "nonfinite reported-term difference")
    return {"reported_minus_calculated": difference,
            "max_abs_difference": max(abs(x) for x in difference),
            "exact_float_equal": all(x == 0 for x in difference),
            "acceptance_tolerance": None}


def calculate(document):
    exact_keys(document, ("schema", "units", "bin_width_seconds", "records"), "input")
    require(document["schema"] == "consensus_supplied_likelihood_terms_v1", "input schema")
    require(document["units"] == "expected_spikes_per_bin", "expected-count units required")
    width = finite_number(document["bin_width_seconds"], "bin_width_seconds")
    require(width == 0.005, "explicit original 5 ms bin width required")
    records = document["records"]
    require(type(records) is list and 0 < len(records) <= MAX_RECORDS, "bounded supplied records required")
    prepared, seen, total_bins = [], set(), 0
    for record in records:
        values = prepare(record)
        require(values[0] not in seen, "duplicate occurrence key")
        seen.add(values[0])
        total_bins += len(values[1])
        require(total_bins <= MAX_TOTAL_BINS, "total time-bin limit")
        prepared.append(values)
    outputs = []
    for record, (_, counts, model, psth, reported) in zip(records, prepared):
        model_terms = [term(y, mu) for y, mu in zip(counts, model)]
        psth_terms = [term(y, mu) for y, mu in zip(counts, psth)]
        model_sum, psth_sum = finite_sum(model_terms), finite_sum(psth_terms)
        residual = model_sum - psth_sum
        require(math.isfinite(residual), "nonfinite residual LL; no replacement")
        outputs.append({
            "key": dict(record["key"]), "time_bin_ids": list(record["time_bin_ids"]),
            "model_ll_terms": model_terms, "psth_ll_terms": psth_terms,
            "model_ll_sum": model_sum, "psth_ll_sum": psth_sum,
            "residual_ll_sum": residual, "num_spikes": sum(counts), "num_time_bins": len(counts),
            "reported_model_comparison": comparison(model_terms, reported[0]),
            "reported_psth_comparison": comparison(psth_terms, reported[1]),
        })
    return {"schema": "consensus_supplied_likelihood_terms_result_v1", "records": outputs,
            "record_count": len(outputs), "total_time_bins": total_bins,
            "units": "natural_log_likelihood_without_factorial_constants",
            "bin_width_seconds": width, "expected_counts_scaled_again": False,
            "psth_constructed_or_authenticated": False, "source_identity_authenticated": False,
            "full_panel_coverage_verified": False, "native_numerical_parity": False,
            "paper_figure2b_score": None, "scientific_qualification": False}


def parse_input(raw):
    require(type(raw) is bytes and len(raw) <= MAX_INPUT_BYTES, "input byte limit")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    def constant(_):
        raise ValueError("nonfinite JSON constant")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def main():
    try:
        result = calculate(parse_input(sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)))
        body = json.dumps(result, sort_keys=True, allow_nan=False, separators=(",", ":"))
        sys.stdout.write(body + "\n")
    except (ValueError, UnicodeError, OverflowError) as exc:
        print("likelihood terms refused: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
