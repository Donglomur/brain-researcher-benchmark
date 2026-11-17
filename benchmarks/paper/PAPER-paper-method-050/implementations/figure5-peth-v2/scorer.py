"""Figure 5E PETH safeguard kernel, not the Figure 5D improvement endpoint.

Input is an operator-owned population and complete frozen track assignments.
This module performs no matching, source retrieval, fitting or admission.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

BASELINES = ("DANT", "UnitMatch", "EMD")
PETH_BINS = 3000
MIN_PAIRS = 100
ENDPOINT_TOLERANCE = 8 * sys.float_info.epsilon


class InputError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InputError(message)


def integer(value, label):
    require(type(value) is int and value >= 0, f"{label}: nonnegative integer required")
    return value


def identifier(value, label):
    require(isinstance(value, str) and bool(value.strip()), f"{label}: nonempty text required")
    return value


def number(value, label):
    require(type(value) in (int, float) and math.isfinite(value), f"{label}: finite number required")
    return float(value)


def encoded(value):
    if value is None or math.isnan(value):
        return None
    if math.isinf(value):
        return "positive_infinity" if value > 0 else "negative_infinity"
    return value


def median(values):
    # An even sample with central -inf and +inf has no numeric midpoint.
    return encoded(statistics.median(values)) if values else None


def fisher_z(left, right):
    """Pearson correlation then Fisher transform; constants remain undefined.

    Pre-scaling prevents overflow. The endpoint snap is an explicit numerical
    policy inherited from v1, not an author-specified correlation tolerance.
    """
    require(len(left) == len(right) and len(left) > 1, "PETH dimensions differ")
    centered = []
    for vector in (left, right):
        scale = max(abs(x) for x in vector)
        if scale == 0:
            return None
        scaled = [x / scale for x in vector]
        mean = math.fsum(scaled) / len(scaled)
        residual = [x - mean for x in scaled]
        norm = math.sqrt(math.fsum(x * x for x in residual))
        if norm == 0:
            return None
        centered.append([x / norm for x in residual])
    r = math.fsum(a * b for a, b in zip(*centered))
    require(abs(r) <= 1 + ENDPOINT_TOLERANCE, "invalid computed correlation")
    if abs(r) >= 1 - ENDPOINT_TOLERANCE:
        return math.copysign(math.inf, r)
    return math.atanh(r)


def friedman_three(rows):
    """Tie-corrected Friedman statistic for three paired baseline columns.

    The chi-square(df=2) survival probability is exp(-Q/2). It is explicitly
    asymptotic, not an exact small-sample p-value or a superiority decision.
    """
    if len(rows) < 2:
        return {"statistic": None, "p_asymptotic": None, "reason": "fewer_than_two_datasets"}
    sums, tie_sum = [0.0] * 3, 0
    for row in rows:
        require(len(row) == 3 and all(x is not None and not math.isnan(x) for x in row),
                "Friedman requires three defined dataset medians")
        order = sorted(range(3), key=lambda i: row[i])
        start = 0
        while start < 3:
            stop = start + 1
            while stop < 3 and row[order[stop]] == row[order[start]]:
                stop += 1
            rank = (start + 1 + stop) / 2
            for i in order[start:stop]:
                sums[i] += rank
            ties = stop - start
            tie_sum += ties ** 3 - ties
            start = stop
    n = len(rows)
    correction = 1 - tie_sum / (24 * n)
    if correction == 0:
        return {"statistic": None, "p_asymptotic": None, "reason": "all_methods_tied_in_every_dataset"}
    statistic = max(0.0, (sum(x * x for x in sums) / n - 12 * n) / correction)
    return {"statistic": statistic, "p_asymptotic": math.exp(-statistic / 2),
            "degrees_of_freedom": 2, "dataset_count": n, "tie_correction": correction,
            "method_order": list(BASELINES), "reason": None}


def _decode_median(value):
    if value == "positive_infinity":
        return math.inf
    if value == "negative_infinity":
        return -math.inf
    return value


def _population(packet):
    require(packet.get("peth_schema") == "press_release_poke_3x1000_bins_1ms_plus_minus_500ms",
            "the source 3000-bin PETH schema is required")
    require(packet.get("rate_unit") == "Hz", "rate metadata must be in Hz")
    identifier(packet.get("rate_measurement_provenance"), "rate_measurement_provenance")
    identifier(packet.get("population_provenance"), "population_provenance")
    units = packet.get("units")
    require(isinstance(units, list) and units, "nonempty operator unit population required")
    lookup, sessions, datasets = {}, {}, defaultdict(list)
    for row in units:
        dataset = identifier(row.get("dataset"), "dataset")
        key = (dataset, integer(row.get("unit_id"), "unit_id"))
        require(key not in lookup, "duplicate unit identity")
        session = integer(row.get("session_id"), "session_id")
        require(session > 0, "session IDs must be positive")
        shank = integer(row.get("shank"), "shank")
        text = row.get("recording_date")
        require(isinstance(text, str), "recording_date must be ISO calendar date")
        try:
            day = date.fromisoformat(text)
        except ValueError as error:
            raise InputError("invalid recording_date") from error
        require(day.isoformat() == text, "recording_date must use YYYY-MM-DD")
        previous = sessions.setdefault((dataset, session), day)
        require(previous == day, "one session maps to multiple calendar dates")
        peth = row.get("peth")
        require(isinstance(peth, list) and len(peth) == PETH_BINS, "exactly 3000 PETH bins required")
        vector = [number(x, "PETH") for x in peth]
        require(min(vector) >= 0, "PETH firing rates cannot be negative")
        mean = number(row.get("mean_rate_hz"), "mean_rate_hz")
        # The paper explicitly places the peak-rate threshold in the PETH.
        # Compute it from the actual vector, not a caller-supplied assertion.
        peak = max(vector)
        require(mean >= 0, "firing-rate metadata cannot be negative")
        item = {"key": key, "session": session, "day": day, "shank": shank,
                "peth": vector, "eligible": mean >= 1 and peak >= 5}
        lookup[key] = item
        datasets[dataset].append(item)
    for dataset in datasets:
        ordered = sorted((session, day) for (name, session), day in sessions.items() if name == dataset)
        require(all(a[1] <= b[1] for a, b in zip(ordered, ordered[1:])),
                "session order contradicts calendar dates")
    return lookup, datasets


def _method(method, population, datasets):
    # An assertion is needed to avoid an accidental circular analysis; it is
    # not executable proof that PETH was excluded during external matching.
    require(method.get("peth_excluded_from_matching_and_selection") is True,
            "PETH must be excluded from all matching and selection stages")
    identifier(method.get("execution_provenance"), "execution_provenance")
    assignments = method.get("assignments")
    require(isinstance(assignments, list), "complete track assignments required")
    seen, tracks = set(), defaultdict(list)
    for row in assignments:
        key = (identifier(row.get("dataset"), "assignment dataset"), integer(row.get("unit_id"), "assignment unit_id"))
        require(key in population and key not in seen, "unknown or duplicate assignment unit")
        seen.add(key)
        track = row.get("track_id")
        require(type(track) is int and (track == -1 or track > 0), "track_id must be -1 or positive integer")
        if track > 0:
            tracks[(key[0], track)].append(population[key])
    require(seen == set(population), "assignments must cover the same complete unit population")
    reports = {dataset: {"all_track_pairs": 0, "not_consecutive_day_pairs": 0,
                         "rate_ineligible_pairs": 0, "constant_peth_pairs": 0,
                         "valid_pairs": 0, "median_fisher_z": None} for dataset in datasets}
    scores = defaultdict(list)
    for (dataset, _), members in tracks.items():
        require(len({u["session"] for u in members}) == len(members), "track contains two units from one session")
        require(len({u["shank"] for u in members}) == 1, "track crosses shanks")
        # Inspect only adjacent calendar days. Count every other unordered
        # pair algebraically to avoid constructing quadratic pair collections.
        by_day = defaultdict(list)
        for unit in members:
            by_day[unit["day"].toordinal()].append(unit)
        total = len(members) * (len(members) - 1) // 2
        consecutive = 0
        for day, first in by_day.items():
            for left in first:
                for right in by_day.get(day + 1, []):
                    consecutive += 1
                    if not (left["eligible"] and right["eligible"]):
                        reports[dataset]["rate_ineligible_pairs"] += 1
                        continue
                    z = fisher_z(left["peth"], right["peth"])
                    if z is None:
                        reports[dataset]["constant_peth_pairs"] += 1
                    else:
                        scores[dataset].append(z)
        reports[dataset]["all_track_pairs"] += total
        reports[dataset]["not_consecutive_day_pairs"] += total - consecutive
    for dataset, report in reports.items():
        report["valid_pairs"] = len(scores[dataset])
        report["median_fisher_z"] = median(scores[dataset])
    return reports


def score(packet):
    require(packet.get("schema_version") == "figure5-peth/v2", "unsupported packet schema")
    require(packet.get("source_kind") in ("generated_engineering_control", "operator_prepared_source"),
            "explicit source kind required")
    population, datasets = _population(packet)
    methods = packet.get("methods")
    require(isinstance(methods, dict) and set(methods) in (set(BASELINES), set(BASELINES) | {"candidate"}),
            "DANT, UnitMatch and EMD are mandatory; only an optional candidate may be added")
    reports = {name: _method(method, population, datasets) for name, method in methods.items()}
    retained, excluded = [], {}
    for dataset in sorted(datasets):
        failing = [name for name in BASELINES if reports[name][dataset]["valid_pairs"] < MIN_PAIRS]
        if failing:
            excluded[dataset] = {"reason": "fewer_than_100_valid_pairs_in_original_method", "methods": failing}
        else:
            retained.append(dataset)
    rows, undefined = [], []
    for dataset in retained:
        row = [_decode_median(reports[name][dataset]["median_fisher_z"]) for name in BASELINES]
        if any(value is None for value in row):
            undefined.append(dataset)
        else:
            rows.append(row)
    friedman = ({"statistic": None, "p_asymptotic": None,
                 "reason": "undefined_dataset_median", "datasets": undefined}
                if undefined else friedman_three(rows))
    result = {"schema_version": "figure5-peth-result/v2", "task_id": "PAPER-paper-method-050",
              "source_kind": packet["source_kind"], "endpoint": "Figure5E_PETH_fidelity_component",
              "units": len(population), "input_dataset_count": len(datasets),
              "original_method_common_support": retained, "excluded_datasets": excluded,
              "methods": reports, "original_three_method_friedman": friedman,
              "qualification": "software_component_only_original_population_and_execution_unverified"}
    if "candidate" in methods:
        result["candidate_on_original_support"] = {
            dataset: {"valid_pairs": reports["candidate"][dataset]["valid_pairs"],
                      "meets_100_pair_support": reports["candidate"][dataset]["valid_pairs"] >= MIN_PAIRS,
                      "median_fisher_z": reports["candidate"][dataset]["median_fisher_z"]}
            for dataset in retained}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    raw = args.packet.read_bytes()
    result = score(json.loads(raw))
    result["input_sha256"] = hashlib.sha256(raw).hexdigest()
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
