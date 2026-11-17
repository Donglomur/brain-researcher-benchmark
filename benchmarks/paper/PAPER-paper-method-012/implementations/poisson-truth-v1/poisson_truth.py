#!/usr/bin/env python3
"""Analytical reference for MINT S1 Appendix Fig C(B), not an author rerun.

Only the source's N=1..4, equal-prior, conditionally independent Poisson(1/2)
process is implemented. No random data, models, or source estimates are made.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics

BRANCH = "MINT-S1-Appendix-Fig-C-B"
SOURCE_METHODS = ("plugin", "qe", "shuffSub", "ksg")
REPETITIONS = 25


def _integer(value, name, minimum=1):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _population(n):
    _integer(n, "n_neurons")
    if n > 4:
        raise ValueError("The original Figure C(B) covers N=1,2,3,4")
    return n


def _information_contribution(p, q):
    """Equal-prior binary-stimulus MI contribution for one response outcome."""
    mixture = (p + q) / 2
    if not mixture:
        return 0.0
    return math.fsum(0.5 * x * math.log2(x / mixture) for x in (p, q) if x)


def _five_bins(mean):
    """P(min(Poisson(mean),4)=k), k=0,1,2,3,4; last bin is >=4."""
    probabilities = [math.exp(-mean)]
    for k in range(1, 4):
        probabilities.append(probabilities[-1] * mean / k)
    return tuple(probabilities + [1.0 - math.fsum(probabilities)])


def binned_truth(n_neurons):
    """Exact finite-sum information of the source's five-bin response vectors."""
    n = _population(n_neurons)
    first, second = _five_bins(1.0), _five_bins(2.0)
    terms = []
    for response in itertools.product(range(5), repeat=n):
        p = math.prod(first[k] for k in response)
        q = math.prod(second[k] for k in response)
        terms.append(_information_contribution(p, q))
    return math.fsum(terms)


def unbinned_truth(n_neurons, tolerance=1e-13):
    """Use the sufficient statistic sum(counts) ~ Poisson(N*lambda).

    Beyond K, Poisson's consecutive pmf ratio decreases. The geometric tail
    bound p(K+1)/(1-lambda/(K+2)) bounds the discarded probability. Binary
    stimulus information from those outcomes is no larger than their mixture
    mass. This is a truncation bound; ordinary float roundoff is separate.
    """
    n = _population(n_neurons)
    if (isinstance(tolerance, bool) or not isinstance(tolerance, (int, float))
            or not math.isfinite(tolerance) or not 1e-15 <= tolerance <= 1e-6):
        raise ValueError("tolerance must be finite and between 1e-15 and 1e-6 bits")
    means = (float(n), float(2 * n))
    pmfs = [math.exp(-mean) for mean in means]
    terms = []
    for k in range(1000):
        terms.append(_information_contribution(*pmfs))
        following = [p * mean / (k + 1) for p, mean in zip(pmfs, means)]
        if k + 2 > means[1]:
            tail_bound = math.fsum(
                0.5 * p / (1 - mean / (k + 2))
                for p, mean in zip(following, means))
            if tail_bound <= tolerance:
                return {"information_bits": math.fsum(terms),
                        "truncation_bound_bits": tail_bound,
                        "maximum_total_count_in_sum": k}
        pmfs = following
    raise ArithmeticError("Poisson information tail did not converge")


def truth_table():
    rows = []
    for n in range(1, 5):
        binned = binned_truth(n)
        raw = unbinned_truth(n)
        rows.append({"n_neurons": n, "binned_information_bits": binned,
                     "unbinned_information": raw,
                     "binning_information_loss_bits": raw["information_bits"] - binned})
    return {"branch": BRANCH, "role": "analytical_source_process_reference",
            "units": "bits", "floating_point": "binary64; tail bound excludes roundoff",
            "rows": rows}


def _sha256(value):
    return (isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))


def summarize(packet):
    """Summarize complete, paired estimate rows on an explicitly supplied grid.

    Grid/sample-source recovery remains external: this computes paper-style
    mean/SEM plus signed errors, never certifies original source provenance.
    """
    if not isinstance(packet, dict) or packet.get("branch") != BRANCH:
        raise ValueError("Wrong source branch")
    if packet.get("input_role") not in {"generated_software_control", "operator_estimates_unqualified"}:
        raise ValueError("Input role must distinguish controls from unqualified estimates")
    sizes = packet.get("trials_per_stimulus_grid")
    if not isinstance(sizes, list) or not sizes:
        raise ValueError("An explicit nonempty trials-per-stimulus grid is required")
    for size in sizes:
        _integer(size, "trials_per_stimulus")
    if sorted(set(sizes)) != sizes:
        raise ValueError("Sample grid must be strictly increasing without duplicates")
    candidates = packet.get("candidate_methods", [])
    if (not isinstance(candidates, list)
            or any(not isinstance(x, str) or not x.strip() for x in candidates)
            or len(set(candidates)) != len(candidates)
            or set(candidates) & set(SOURCE_METHODS)):
        raise ValueError("Candidate method IDs must be unique and separate from source methods")
    methods = list(SOURCE_METHODS) + candidates
    expected = set(itertools.product(range(1, 5), sizes, range(1, REPETITIONS + 1), methods))
    rows = packet.get("estimates")
    if not isinstance(rows, list):
        raise ValueError("estimates must be an array")
    seen, draws, values = set(), {}, defaultdict(list)
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each estimate must be an object")
        n = _population(row.get("n_neurons"))
        size = _integer(row.get("trials_per_stimulus"), "trials_per_stimulus")
        repeat = _integer(row.get("repeat"), "repeat")
        method = row.get("method")
        if not isinstance(method, str):
            raise ValueError("method must be a string")
        key = n, size, repeat, method
        if key not in expected or key in seen:
            raise ValueError("Unexpected or duplicated source cell/repetition/method")
        seen.add(key)
        value = row.get("estimate_bits")
        if (isinstance(value, bool) or not isinstance(value, (float, int))
                or not math.isfinite(value)):
            raise ValueError("Information estimates must be finite numbers in bits")
        # Negative bias-corrected estimates are valid and must not be clamped.
        draw = row.get("draw_sha256")
        if not _sha256(draw):
            raise ValueError("Each estimate must identify its sampled observations by SHA256")
        draw_key = n, size, repeat
        if draw_key in draws and draws[draw_key] != draw:
            raise ValueError("Methods must use the same draw for each source repetition")
        draws[draw_key] = draw
        values[n, size, method].append((repeat, float(value)))
    if seen != expected:
        raise ValueError("Missing estimates: require all four populations, methods, and 25 repeats per cell")
    # Reusing one draw under multiple repeat IDs is not replication. Nested
    # sample sizes/populations may share source draws; only within-cell reuse
    # is rejected. Hash declarations cannot prove statistical independence.
    for n, size in itertools.product(range(1, 5), sizes):
        if len({draws[n, size, r] for r in range(1, 26)}) != REPETITIONS:
            raise ValueError("Repeated observation hash within a cell is not 25 repetitions")
    result = []
    for n, size, method in itertools.product(range(1, 5), sizes, methods):
        estimates = [value for _, value in sorted(values[n, size, method])]
        binned, raw = binned_truth(n), unbinned_truth(n)["information_bits"]
        mean = statistics.fmean(estimates)
        result.append({"n_neurons": n, "trials_per_stimulus": size,
                       "total_observations": 2 * size, "method": method,
                       "repetitions": REPETITIONS, "mean_estimate_bits": mean,
                       "sem_estimate_bits": statistics.stdev(estimates) / math.sqrt(REPETITIONS),
                       "signed_error_vs_binned_truth_bits": mean - binned,
                       "signed_error_vs_unbinned_truth_bits": mean - raw,
                       "per_repeat_estimate_bits": estimates})
    input_hash = hashlib.sha256(json.dumps(packet, sort_keys=True, separators=(",", ":"),
                                          allow_nan=False).encode()).hexdigest()
    return {"branch": BRANCH, "role": "supplied_grid_diagnostic_not_paper_win",
            "input_role": packet["input_role"], "input_sha256": input_hash,
            "original_sample_grid_verified": False, "source_estimator_parity_verified": False,
            "repetitions_are_declared_not_authenticated": True,
            "truth": truth_table(), "cells": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--estimates", type=Path,
                        help="Optional complete-grid estimate JSON; omit to print analytical truth")
    args = parser.parse_args()
    result = summarize(json.loads(args.estimates.read_text())) if args.estimates else truth_table()
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
