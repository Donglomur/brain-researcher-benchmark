#!/usr/bin/env python3
"""Independent fixed-bin CA1 pair-MI construction reference; no native parity claim."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import statistics
from typing import Sequence

TASK_ID = "PAPER-paper-method-012"
CANONICAL_SHA256 = "549d5de7931e1cd6fc3b651b3084052e566dc054cf38662bc7d8995a70358ca2"
MINT_COMMIT = "f0d43b68a6e8541f56b3ca67d9af5a7a0e76acbb"
FIGURE_COMMIT = "a90eb535205c2df668e4e59c8f8d748c37fa815e"
METHODS = ("plugin_bits", "qe_bits", "shuffle_subtracted_bits", "qe_shuffle_subtracted_bits")
HOLDS = [
    "Authentic supplement bytes, schema, identities and complete 11-session/7-animal population unverified.",
    "Article/appendix spatial binning disagreement and pre-binned fluorescence provenance unresolved.",
    "Discovered CA1.m has a commented MI call; this independent repair is not historical execution.",
    "Exact native MINT parity, figure reference values and numerical grading tolerances unverified.",
    "Protected assessment, grouped improvement panel, rights/exposure review and scientific qualification unresolved.",
]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _integer(value, label, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def _ids(values, label):
    if not isinstance(values, list) or not values or any(not isinstance(x, str) or not x.strip() for x in values):
        raise ValueError(f"{label} requires nonempty string identifiers")
    if len(set(values)) != len(values):
        raise ValueError(f"{label} contains duplicate identifiers")
    return values


def mutual_information(response: Sequence, stimulus: Sequence) -> float:
    """Empirical discrete MI in bits, using occupied cells without pseudocounts."""
    if len(response) != len(stimulus) or not response:
        raise ValueError("MI requires equally sized, nonempty observations")
    for state in itertools.chain(response, stimulus):
        coordinates = state if isinstance(state, tuple) else (state,)
        if not coordinates or any(isinstance(x, bool) or not isinstance(x, int) for x in coordinates):
            raise ValueError("MI states must be integers or nonempty tuples of integers")
    joint, nr, ns = Counter(zip(response, stimulus)), Counter(response), Counter(stimulus)
    n = len(response)
    return math.fsum(c / n * math.log2(c * n / (nr[r] * ns[s])) for (r, s), c in joint.items())


def qe_intercept(full: float, half: float, quarter: float) -> float:
    """Quadratic inverse-N intercept for exactly balanced full/half/quarter sizes."""
    return (8.0 * full + quarter) / 3.0 - 2.0 * half


def quadratic_extrapolation(response, stimulus, permutations):
    n = len(response)
    if n < 8 or n % 4:
        raise ValueError("Balanced QE requires sample count >=8 divisible by four")
    if not permutations:
        raise ValueError("QE requires at least one partition repetition")
    full = mutual_information(response, stimulus)
    values = []
    for order in permutations:
        if len(order) != n or sorted(order) != list(range(n)):
            raise ValueError("QE partition must be a complete permutation")
        means = []
        for k in (2, 4):
            width = n // k
            parts = (order[start:start + width] for start in range(0, n, width))
            means.append(statistics.fmean(mutual_information([response[i] for i in part], [stimulus[i] for i in part]) for part in parts))
        values.append(qe_intercept(full, means[0], means[1]))
    return statistics.fmean(values)


def _rng(seed, *coordinates):
    return random.Random(int(digest([seed, *coordinates]), 16))


def make_schedule(n, size, repeats, null_count, qe_repeats, seed, session_id, null_mode):
    """Schedules shared by every neuron pair and estimator in one session."""
    schedule = []
    for rep in range(repeats):
        rng = _rng(seed, session_id, size, rep, "selection")
        indices = list(range(n)) if size == n else sorted(rng.sample(range(n), size))
        partitions = []
        if size >= 8 and size % 4 == 0:
            rng = _rng(seed, session_id, size, rep, "qe")
            for _ in range(qe_repeats):
                order = list(range(size)); rng.shuffle(order); partitions.append(order)
        nulls = []
        rng = _rng(seed, session_id, size, rep, null_mode)
        for _ in range(null_count):
            if null_mode == "iid_permutation":
                selected = indices.copy(); rng.shuffle(selected)
                order = list(range(n))
                for destination, source in zip(indices, selected):
                    order[destination] = source
            else:
                shift = rng.randrange(1, n)
                order = [(i + shift) % n for i in range(n)]
            nulls.append(order)
        schedule.append({"indices": indices, "qe_partitions": partitions, "null_orders": nulls})
    return schedule


def validate_packet(packet):
    if packet.get("schema_version") != 1 or packet.get("task_id") != TASK_ID:
        raise ValueError("Wrong packet schema or task identity")
    if packet.get("data_kind") not in {"generated_engineering_control", "operator_prepared_unqualified"}:
        raise ValueError("Input must explicitly identify generated or unqualified prepared observations")
    provenance = packet.get("provenance", {})
    if not isinstance(provenance.get("source"), str) or not provenance["source"].strip():
        raise ValueError("Source attribution is required")
    if provenance.get("binning_status") != "fixed_input_labels_native_provenance_unverified":
        raise ValueError("Fixed-bin input provenance must remain explicitly unverified")
    expected = _ids(packet.get("expected_session_ids"), "expected_session_ids")
    sessions = packet.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        raise ValueError("sessions must be nonempty")
    actual = _ids([s.get("session_id") for s in sessions], "session_ids")
    if set(expected) != set(actual):
        raise ValueError("Session roster mismatch; silently dropping sessions is prohibited")
    for s in sessions:
        _ids([s.get("animal_id")], "animal_id")
        neurons = _ids(s.get("neuron_ids"), "neuron_ids")
        if len(neurons) < 2:
            raise ValueError("Each session requires at least two neurons")
        trials = _ids(s.get("sample_ids"), "sample_ids")
        stimulus, neural = s.get("stimulus"), s.get("neural")
        if not isinstance(stimulus, list) or not isinstance(neural, list) or len(stimulus) != len(trials) or len(neural) != len(trials):
            raise ValueError("Sample IDs, neural rows and stimulus labels must align")
        if len(trials) < 2:
            raise ValueError("Each session requires at least two observations")
        for label in stimulus:
            _integer(label, "stimulus label")
        if len(set(stimulus)) > 12:
            raise ValueError("CA1 scope permits no more than 12 stimulus states")
        for row in neural:
            if not isinstance(row, list) or len(row) != len(neurons):
                raise ValueError("Neural data must be samples by the complete neuron roster")
            for value in row:
                _integer(value, "neural bin label")
        if s.get("ordering") != "acquisition_order":
            raise ValueError("Acquisition order must be declared; shuffled arrays cannot support temporal diagnostics")
    return sessions


def _estimate(response, stimulus, schedule):
    idx = schedule["indices"]
    r, s = [response[i] for i in idx], [stimulus[i] for i in idx]
    observed = mutual_information(r, s)
    partitions = schedule["qe_partitions"]
    qe = quadratic_extrapolation(r, s, partitions) if partitions else None
    null_plugin, null_qe = [], []
    for order in schedule["null_orders"]:
        # IID maps permute within selected samples; temporal maps shift the full trajectory.
        shuffled = [stimulus[order[i]] for i in idx]
        null_plugin.append(mutual_information(r, shuffled))
        if partitions:
            null_qe.append(quadratic_extrapolation(r, shuffled, partitions))
    return {
        "plugin_bits": observed,
        "qe_bits": qe,
        "shuffle_subtracted_bits": observed - statistics.fmean(null_plugin),
        "qe_shuffle_subtracted_bits": qe - statistics.fmean(null_qe) if partitions else None,
        "null_plugin_bits": null_plugin,
        "null_qe_bits": null_qe,
        "plugin_exceedance_fraction": (1 + sum(v >= observed for v in null_plugin)) / (1 + len(null_plugin)),
        "qe_exceedance_fraction": (1 + sum(v >= qe for v in null_qe)) / (1 + len(null_qe)) if partitions else None,
    }


def evaluate(packet, *, sample_sizes, repeats=2, null_count=30, qe_repeats=4, seed=0, null_mode="circular_shift"):
    sessions = validate_packet(packet)
    _integer(seed, "seed"); _integer(repeats, "repeats", 1)
    _integer(null_count, "null_count", 1); _integer(qe_repeats, "qe_repeats", 1)
    if null_mode not in {"iid_permutation", "circular_shift"}:
        raise ValueError("null_mode must be iid_permutation or circular_shift")
    if not isinstance(sample_sizes, list) or not sample_sizes or len(set(sample_sizes)) != len(sample_sizes):
        raise ValueError("sample_sizes must be a nonempty list of distinct counts")
    for size in sample_sizes:
        _integer(size, "sample_size", 8)
        if size % 4:
            raise ValueError("Finite-sample QE counts must be divisible by four")
    if any(max(sample_sizes) > len(s["sample_ids"]) for s in sessions):
        raise ValueError("Sample counts exceed a session; all sessions must remain included")
    rows, schedule_receipts, session_summaries = [], [], []
    for session in sorted(sessions, key=lambda s: s["session_id"]):
        sid, n = session["session_id"], len(session["sample_ids"])
        sizes = sorted(set(sample_sizes + [n]))  # Always retains full-recording estimates.
        counts = Counter()
        values_by_size = {size: {name: [] for name in METHODS} for size in sizes}
        for size in sizes:
            schedule = make_schedule(n, size, 1 if size == n else repeats, null_count, qe_repeats, seed, sid, null_mode)
            schedule_receipts.append({"session_id": sid, "n": size, "sha256": digest(schedule), "repeats": len(schedule), "full_n": n})
            for a, b in itertools.combinations(range(len(session["neuron_ids"])), 2):
                # Exact explicit cap found in discovered CA1.m; no rank/rebin operation.
                response = [(min(row[a], 4), min(row[b], 4)) for row in session["neural"]]
                for rep, plan in enumerate(schedule):
                    result = _estimate(response, session["stimulus"], plan)
                    rows.append({"session_id": sid, "animal_id": session["animal_id"], "neurons": [session["neuron_ids"][a], session["neuron_ids"][b]], "n": size, "full_n": n, "repeat": rep, "qe_status": "balanced_partitions" if plan["qe_partitions"] else "not_computed_full_count_not_balanced_or_below_eight", **result})
                    for name in METHODS:
                        if result[name] is not None:
                            values_by_size[size][name].append(result[name])
                    counts[size] += 1
        for size in sizes:
            session_summaries.append({"session_id": sid, "animal_id": session["animal_id"], "n": size, "rows": counts[size], "pair_count": math.comb(len(session["neuron_ids"]), 2), "means": {k: statistics.fmean(v) if v else None for k, v in values_by_size[size].items()}})
    # Equal session weighting within animal, then equal animal weighting, never pair pseudoreplication.
    grouped = []
    for size in sorted({s["n"] for s in session_summaries}):
        matched = [s for s in session_summaries if s["n"] == size]
        if len(matched) != len(sessions):
            continue  # Unequal full lengths are reported separately, never silently pooled.
        animals = sorted({s["animal_id"] for s in matched})
        per_animal = []
        for animal in animals:
            own = [s for s in matched if s["animal_id"] == animal]
            per_animal.append({"animal_id": animal, "means": {name: statistics.fmean([s["means"][name] for s in own]) if all(s["means"][name] is not None for s in own) else None for name in METHODS}})
        grouped.append({"n": size, "animal_count": len(animals), "session_count": len(matched), "animals": per_animal, "means": {name: statistics.fmean([a["means"][name] for a in per_animal]) if all(a["means"][name] is not None for a in per_animal) else None for name in METHODS}})
    return {
        "schema_version": 1, "task_id": TASK_ID, "status": "construction_reference_only", "scientific_qualification": "unknown", "native_equivalence": "unverified",
        "input_sha256": digest(packet), "input_data_kind": packet["data_kind"], "canonical_sha256": CANONICAL_SHA256,
        "source_commits": {"MINT": MINT_COMMIT, "MINT_figures_discovered": FIGURE_COMMIT},
        "protocol": {"sample_sizes": sorted(sample_sizes), "subsample_repeats": repeats, "null_count": null_count, "qe_repeats": qe_repeats, "seed": seed, "null_mode": null_mode, "response_cap": 4, "fixed_input_bins": True, "protocol_status": "prospective_not_frozen_scientific_grading", "null_interpretation": "Diagnostic exceedance fractions only; no calibrated p-value or false-positive guarantee. IID exchangeability or temporal stationarity has not been established.", "multiple_comparisons": "No familywise or FDR significance decisions are made."},
        "population": {"sessions": len(sessions), "animals": len({s["animal_id"] for s in sessions}), "total_pairs": sum(math.comb(len(s["neuron_ids"]), 2) for s in sessions), "canonical_population_match": "unverified"},
        "schedule_receipts": schedule_receipts, "rows": rows, "session_summaries": session_summaries, "animal_balanced_summaries": grouped, "preserved_holds": HOLDS,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path); parser.add_argument("output", type=Path)
    parser.add_argument("--sample-sizes", nargs="+", type=int, required=True)
    parser.add_argument("--repeats", type=int, default=2); parser.add_argument("--null-count", type=int, default=30)
    parser.add_argument("--qe-repeats", type=int, default=4); parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--null-mode", choices=("iid_permutation", "circular_shift"), default="circular_shift")
    args = parser.parse_args()
    packet = json.loads(args.input.read_text())
    result = evaluate(packet, sample_sizes=args.sample_sizes, repeats=args.repeats, null_count=args.null_count, qe_repeats=args.qe_repeats, seed=args.seed, null_mode=args.null_mode)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
