"""iSTTC full empirical Figure 7C preparation and source-defined reduction.
Stdlib only. Public metadata is not proof of original cohort/QC authority.
No estimator fitting, scientific data acquisition, or native execution.
"""
import argparse
import hashlib
import json
import math
import random
import statistics
from pathlib import Path

METHODS = ("acf_full", "isttc_full", "pearsonr_trial_avg", "sttc_trial_concat")
TRIAL_METHODS = METHODS[2:]
REFERENCES = dict(zip(TRIAL_METHODS, METHODS[:2]))
FS = 30000
SIGNAL_TICKS = 30 * 60 * FS
TRIAL_TICKS = FS
N_TRIALS = 40
N_UNITS = 5775
N_MICE = 26
THRESHOLDS = (100, 75, 50, 25)

def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON")))

def finite(value, nullable=False):
    if nullable and value is None:
        return None
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("expected finite real number")
    return value

def finite_summary(function, values):
    try:
        result = function(values)
    except (OverflowError, ValueError) as exc:
        raise ValueError("numeric summary cannot be represented") from exc
    return finite(result)

def identifier(value):
    if type(value) is not str or not value or len(value) > 128:
        raise ValueError("invalid identifier")
    return value

def cohort(document):
    if type(document) is not dict or set(document) != {"schema", "source_sha256", "units"}:
        raise ValueError("cohort keys")
    if document["schema"] != "isttc_empirical_cohort_v1":
        raise ValueError("cohort schema")
    digest = document["source_sha256"]
    if type(digest) is not str or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("cohort source pin")
    rows = document["units"]
    if type(rows) is not list or len(rows) != N_UNITS:
        raise ValueError("complete 5775-unit cohort required")
    ids, mice = set(), set()
    for row in rows:
        if type(row) is not dict or set(row) != {"unit_id", "mouse_id", "session_id", "area", "fr_hz", "lv"}:
            raise ValueError("cohort row keys")
        uid = identifier(row["unit_id"])
        if uid in ids:
            raise ValueError("duplicate cohort unit")
        ids.add(uid)
        mice.add(identifier(row["mouse_id"]))
        identifier(row["session_id"])
        identifier(row["area"])
        for field in ("fr_hz", "lv"):
            value = finite(row[field], nullable=True)
            if value is not None and value < 0:
                raise ValueError("negative cohort covariate")
    if len(mice) != N_MICE:
        raise ValueError("complete 26-mouse cohort required")
    return rows

def draw_windows(rng, signal_ticks=SIGNAL_TICKS, trial_ticks=TRIAL_TICKS, n_trials=N_TRIALS):
    # Exact get_trials integer start support; overlaps/repeats are intentional.
    for value in (signal_ticks, trial_ticks, n_trials):
        if type(value) is not int or value <= 0:
            raise ValueError("positive integer sampling parameters required")
    if trial_ticks > signal_ticks:
        raise ValueError("trial exceeds signal")
    return [[start, start + trial_ticks] for start in
            (rng.randrange(0, signal_ticks - trial_ticks + 1) for _ in range(n_trials))]

def slice_trials(spike_ticks, windows):
    """Generated controls / future one-unit bridge, [start,end), then realign."""
    if any(type(v) is not int or v < 0 for v in spike_ticks):
        raise ValueError("spike ticks must be nonnegative integers")
    if any(a > b for a, b in zip(spike_ticks, spike_ticks[1:])):
        raise ValueError("spikes must be sorted")
    out = []
    for pair in windows:
        if type(pair) is not list or len(pair) != 2:
            raise ValueError("window pair")
        start, end = pair
        if type(start) is not int or type(end) is not int or start < 0 or end <= start:
            raise ValueError("invalid window")
        out.append([value - start for value in spike_ticks if start <= value < end])
    return out

def window_rows(document, seed):
    rows = cohort(document)
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError("seed must be uint64")
    rng = random.Random(seed)
    for row in rows:
        yield {"unit_id": row["unit_id"], "replicate": 0,
               "windows_ticks": draw_windows(rng),
               "fs_hz": FS, "signal_ticks": SIGNAL_TICKS,
               "draw_scope": "prospective_published_protocol_not_historical_rng_recovery",
               "seed": seed}

def estimate_rows(document, units):
    if type(document) is not dict or set(document) != {"schema", "rows"} or document["schema"] != "isttc_empirical_estimates_v1":
        raise ValueError("estimates schema")
    rows = document["rows"]
    if type(rows) is not list or len(rows) != len(units) * len(METHODS):
        raise ValueError("every unit and all four methods required, including failures")
    by_key = {}
    ids = {row["unit_id"] for row in units}
    for row in rows:
        if type(row) is not dict or set(row) != {"unit_id", "method", "tau_bins", "r_squared", "failure_reason"}:
            raise ValueError("estimate row keys")
        key = (row["unit_id"], row["method"])
        if key[0] not in ids or key[1] not in METHODS or key in by_key:
            raise ValueError("unknown/duplicate estimate coordinate")
        tau, r2 = finite(row["tau_bins"], True), finite(row["r_squared"], True)
        if tau is not None:
            finite(tau * 50)  # Every reported millisecond value must remain finite.
        reason = row["failure_reason"]
        if reason is not None and (type(reason) is not str or not reason or len(reason) > 1024):
            raise ValueError("failure reason")
        if (tau is None or r2 is None) != (reason is not None):
            raise ValueError("explicit failure reason required exactly for missing fit fields")
        by_key[key] = row
    return by_key

def reduce_rows(units, estimates):
    """Core consumes already validated coordinates; no scientific qualification."""
    records, errors = [], {method: [] for method in TRIAL_METHODS}
    counts = {"original_units": len(units), "missing_fit_or_covariate": 0,
              "negative_r2_after_missing": 0, "complete_cases": 0,
              "undefined_reference": 0}
    for unit in units:
        uid = unit["unit_id"]
        fits = {method: estimates[(uid, method)] for method in METHODS}
        missing = [method for method, row in fits.items()
                   if row["tau_bins"] is None or row["r_squared"] is None]
        cov_missing = [key for key in ("fr_hz", "lv") if unit[key] is None]
        negative = [method for method, row in fits.items()
                    if row["r_squared"] is not None and row["r_squared"] < 0]
        status = "complete_case"
        if missing or cov_missing:
            status = "missing_fit_or_covariate"
            counts[status] += 1
        elif negative:
            status = "negative_r2_after_missing"
            counts[status] += 1
        else:
            counts["complete_cases"] += 1
        values = {}
        if status == "complete_case":
            for method in TRIAL_METHODS:
                denominator = fits[REFERENCES[method]]["tau_bins"]
                if denominator <= 0:
                    values[method] = None
                else:
                    value = abs(fits[method]["tau_bins"] - denominator) / denominator * 100.0
                    values[method] = value if math.isfinite(value) else None
                    if values[method] is not None:
                        errors[method].append(value)
            if any(value is None for value in values.values()):
                status = "undefined_reference"
                counts["undefined_reference"] += 1
        records.append({"unit_id": uid, "mouse_id": unit["mouse_id"],
                        "session_id": unit["session_id"], "area": unit["area"],
                        "status": status, "missing_methods": missing,
                        "missing_covariates": cov_missing, "negative_r2_methods": negative,
                        "tau_ms": {method: (None if fits[method]["tau_bins"] is None else fits[method]["tau_bins"] * 50) for method in METHODS},
                        "pseudo_ree_percent": values})
    summaries = {}
    for method, values in errors.items():
        support_complete = len(values) == counts["complete_cases"]
        summaries[method] = {"defined_count": len(values),
                            "complete_case_denominator": counts["complete_cases"],
                            "support_complete": support_complete,
                            "median_pseudo_ree_percent": finite_summary(statistics.median, values) if values and support_complete else None,
                            "known_within_count": {str(t): sum(0 <= value <= t for value in values) for t in THRESHOLDS},
                            "within_percent": {str(t): (100 * sum(0 <= value <= t for value in values) / counts["complete_cases"]
                                                       if values and support_complete else None)
                                               for t in THRESHOLDS}}
    return {"schema": "isttc_empirical_fig7c_reduction_v1",
            "counts": counts, "records": records, "summaries": summaries,
            "numeric_complete": counts["undefined_reference"] == 0,
            "published_complete_cases_3053_is_observation_not_forced_selection": True,
            "scientifically_qualified": False,
            "interpretation": "Full-recording method-specific estimates are pseudo references, not biological truth."}

def reduce_document(cohort_doc, estimates_doc):
    units = cohort(cohort_doc)
    return reduce_rows(units, estimate_rows(estimates_doc, units))

def compare_reproduction(cohort_doc, candidate_doc, reference_doc):
    """Compare all full-population coordinates; candidate failures never pick support."""
    units = cohort(cohort_doc)
    candidate, reference = estimate_rows(candidate_doc, units), estimate_rows(reference_doc, units)
    mismatches = []
    differences = {field: [] for field in ("tau_bins", "r_squared")}
    for key in reference:
        c, r = candidate[key], reference[key]
        for field in ("tau_bins", "r_squared"):
            if (c[field] is None) != (r[field] is None):
                mismatches.append({"unit_id": key[0], "method": key[1], "field": field})
            elif r[field] is not None:
                delta = abs(c[field] - r[field])
                if not math.isfinite(delta):
                    raise ValueError("difference overflow")
                differences[field].append(delta)
    return {"schema": "isttc_empirical_reproduction_comparison_v1",
            "units": len(units), "method_coordinates": len(reference),
            "availability_mismatches": mismatches,
            "full_output_support_matched": not mismatches,
            "errors_by_quantity": {
                field: {"expected_reference_values": sum(row[field] is not None for row in reference.values()),
                        "compared_values": len(values),
                        "comparable": not mismatches,
                        "mean_absolute_difference": finite_summary(statistics.fmean, values) if values and not mismatches else None,
                        "maximum_absolute_difference": max(values, default=None) if not mismatches else None}
                for field, values in differences.items()},
            "scientific_pass": None,
            "candidate_reduction": reduce_rows(units, candidate),
            "reference_reduction": reduce_rows(units, reference)}

def read_json(path, cap=16 * 1024 * 1024):
    with Path(path).open("rb") as handle:
        data = handle.read(cap + 1)
    if len(data) > cap:
        raise ValueError("input cap exceeded")
    return strict_json(data)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("windows", "reduce", "compare"))
    parser.add_argument("--cohort", required=True)
    parser.add_argument("--estimates")
    parser.add_argument("--reference")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    c = read_json(args.cohort)
    if args.operation == "windows":
        values = window_rows(c, args.seed)
    elif args.operation == "reduce":
        values = [reduce_document(c, read_json(args.estimates))]
    else:
        values = [compare_reproduction(c, read_json(args.estimates), read_json(args.reference))]
    # Fresh file; a failed stream remains visible and is never a success receipt.
    with Path(args.output).open("x", encoding="utf-8") as handle:
        total = 0
        for value in values:
            line = json.dumps(value, sort_keys=True, allow_nan=False) + "\n"
            total += len(line.encode())
            if total > 64 * 1024 * 1024:
                raise ValueError("output cap exceeded; partial file retained")
            handle.write(line)

if __name__ == "__main__":
    main()

