"""Figure 5H/I joint-sort fidelity component; no matching or source admission."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path
import statistics

BASELINES = ("DANT", "UnitMatch", "EMD")


class InputError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InputError(message)


def identifier(value, label):
    require(isinstance(value, str) and bool(value.strip()), f"{label}: nonempty text required")
    return value


def integer(value, label, minimum=0):
    require(type(value) is int and value >= minimum, f"{label}: integer >= {minimum} required")
    return value


def _population(packet):
    identifier(packet.get("population_provenance"), "population_provenance")
    require(packet.get("complete_selected_session_population") is True,
            "complete selected session population declaration required")
    rows = packet.get("units")
    require(isinstance(rows, list) and bool(rows), "nonempty complete unit population required")
    units, sessions = {}, {}
    for row in rows:
        dataset = identifier(row.get("dataset"), "dataset")
        key = (dataset, integer(row.get("unit_id"), "unit_id"))
        require(key not in units, "duplicate population unit")
        session = integer(row.get("session_id"), "session_id", 1)
        shank = integer(row.get("shank"), "shank")
        text = row.get("recording_date")
        require(isinstance(text, str), "ISO recording_date required")
        try:
            day = date.fromisoformat(text)
        except ValueError as error:
            raise InputError("invalid recording_date") from error
        require(day.isoformat() == text, "recording_date must use YYYY-MM-DD")
        require(sessions.setdefault((dataset, session), day) == day,
                "one session maps to multiple dates")
        units[key] = {"session_id": session, "shank": shank}
    datasets = {key[0] for key in units}
    rats = packet.get("dataset_to_rat")
    require(isinstance(rats, dict) and set(rats) == datasets, "complete dataset_to_rat required")
    for rat in rats.values():
        identifier(rat, "rat identity")
    for dataset in datasets:
        ordered = sorted((session, day) for (name, session), day in sessions.items() if name == dataset)
        require(all(a[1] <= b[1] for a, b in zip(ordered, ordered[1:])),
                "session order contradicts dates")
    return units, sessions, rats


def _assignments(method, population):
    for flag in ("full_session_tracking", "joint_reference_excluded_from_matching_and_selection",
                 "peth_excluded_from_matching_and_selection"):
        require(method.get(flag) is True, f"{flag}: explicit true declaration required")
    identifier(method.get("execution_provenance"), "execution_provenance")
    rows = method.get("assignments")
    require(isinstance(rows, list), "complete assignments required")
    labels, tracks = {}, defaultdict(list)
    for row in rows:
        key = (identifier(row.get("dataset"), "assignment dataset"),
               integer(row.get("unit_id"), "assignment unit_id"))
        require(key in population and key not in labels, "unknown or duplicate assignment unit")
        label = row.get("track_id")
        require(type(label) is int and (label == -1 or label > 0),
                "track_id must be -1 or a positive integer")
        labels[key] = label
        if label > 0:
            tracks[key[0], label].append(population[key])
    require(set(labels) == set(population), "assignments must cover the complete full-session population")
    for members in tracks.values():
        require(len({u["session_id"] for u in members}) == len(members),
                "track has multiple units in one session")
        require(len({u["shank"] for u in members}) == 1, "track crosses shanks")
    return labels


def _reference(row, population, sessions):
    pair_id = identifier(row.get("pair_id"), "pair_id")
    dataset = identifier(row.get("dataset"), "reference dataset")
    left = integer(row.get("left_session_id"), "left_session_id", 1)
    right = integer(row.get("right_session_id"), "right_session_id", 1)
    require(left < right, "reference sessions must be ordered and distinct")
    require((dataset, left) in sessions and (dataset, right) in sessions, "unknown reference session")
    require((sessions[dataset, right] - sessions[dataset, left]).days == 1,
            "Figure 5H/I reference sessions must be on consecutive calendar days")
    identifier(row.get("mapping_provenance"), "mapping_provenance")
    require(row.get("complete_overlap_mapping") is True, "complete overlap mapping declaration required")
    require(type(row.get("spike_time_tolerance_ms")) in (int, float)
            and row["spike_time_tolerance_ms"] == 1, "source coincidence tolerance is 1 ms inclusive")
    mappings = row.get("included_units")
    require(isinstance(mappings, list) and bool(mappings), "included_units mapping required")
    included, by_side = {}, {left: {}, right: {}}
    for mapping in mappings:
        uid = integer(mapping.get("unit_id"), "reference unit_id")
        key = dataset, uid
        require(key in population and uid not in included, "unknown or duplicate reference unit")
        session = population[key]["session_id"]
        require(session in by_side, "reference unit is outside selected session pair")
        cluster = integer(mapping.get("joint_cluster_id"), "joint_cluster_id")
        count = integer(mapping.get("individual_spike_count"), "individual_spike_count", 1)
        overlap = integer(mapping.get("coincident_individual_spike_count"), "coincident_individual_spike_count")
        require(overlap <= count and 2 * overlap > count,
                "included unit requires strictly more than half its individual spikes to coincide")
        included[uid] = dict(unit_id=uid, session_id=session, joint_cluster_id=cluster,
                             individual_spike_count=count, coincident_individual_spike_count=overlap)
        by_side[session][uid] = cluster
    require(all(by_side.values()), "both reference sessions need included units")
    # Several individual units may map to one joint cluster. The paper does
    # not specify a one-to-one mapping constraint; do not silently discard them.
    right_clusters = defaultdict(list)
    for uid, cluster in by_side[right].items():
        right_clusters[cluster].append(uid)
    edges = {(uid, other) for uid, cluster in by_side[left].items()
             for other in right_clusters[cluster]}
    excluded = sorted(uid for (name, uid), unit in population.items()
                      if name == dataset and unit["session_id"] in by_side and uid not in included)
    audit = dict(pair_id=pair_id, dataset=dataset, left_session_id=left, right_session_id=right,
                 left_recording_date=sessions[dataset, left].isoformat(),
                 right_recording_date=sessions[dataset, right].isoformat(),
                 included_units=[included[uid] for uid in sorted(included)],
                 excluded_unit_ids=excluded, reference_matches=sorted(edges))
    return audit, by_side, edges


def _summary(rows, metric):
    missing = [r["pair_id"] for r in rows if r[metric] is None]
    values = [r[metric] for r in rows]
    return {"pair_count": len(rows), "undefined_pair_ids": missing,
            "mean_percent": None if missing else statistics.mean(values),
            "sample_sd_percentage_points": (None if missing or len(rows) < 2 else statistics.stdev(values)),
            "sd_policy": "sample SD, denominator n-1; source ddof parity unverified",
            "aggregation": "equal weight per declared validation pair; no pooling or silent pair deletion"}


def score(packet):
    require(isinstance(packet, dict) and packet.get("schema_version") == "figure5-joint-sort/v1",
            "unsupported packet schema")
    require(packet.get("source_kind") in ("generated_engineering_control", "operator_prepared_source"),
            "explicit source_kind required")
    population, sessions, rats = _population(packet)
    methods = packet.get("methods")
    require(isinstance(methods, dict) and set(methods) in (set(BASELINES), set(BASELINES) | {"candidate"}),
            "DANT, UnitMatch and EMD required; only candidate may be added")
    assignments = {name: _assignments(method, population) for name, method in methods.items()}
    references = packet.get("references")
    require(isinstance(references, list) and bool(references), "nonempty reference panel required")
    panel, seen_ids, seen_pairs = [], set(), set()
    reports = {name: [] for name in methods}
    for row in references:
        audit, sides, truth = _reference(row, population, sessions)
        pair_id, dataset = audit["pair_id"], audit["dataset"]
        pair_key = dataset, audit["left_session_id"], audit["right_session_id"]
        require(pair_id not in seen_ids and pair_key not in seen_pairs, "duplicate validation pair")
        seen_ids.add(pair_id)
        seen_pairs.add(pair_key)
        audit["rat_id"] = rats[dataset]
        panel.append(audit)
        for name, labels in assignments.items():
            right_tracks = {labels[dataset, uid]: uid for uid in sides[audit["right_session_id"]]
                            if labels[dataset, uid] > 0}
            predicted = {(uid, right_tracks[labels[dataset, uid]]) for uid in sides[audit["left_session_id"]]
                         if labels[dataset, uid] > 0 and labels[dataset, uid] in right_tracks}
            tp, fp, fn = predicted & truth, predicted - truth, truth - predicted
            reports[name].append({"pair_id": pair_id, "tp": len(tp), "fp": len(fp), "fn": len(fn),
                "true_positive_matches": sorted(tp), "false_positive_matches": sorted(fp),
                "false_negative_matches": sorted(fn),
                "precision_percent": 100 * len(tp) / len(predicted) if predicted else None,
                "recall_percent": 100 * len(tp) / len(truth) if truth else None})
    panel.sort(key=lambda row: row["pair_id"])
    for rows in reports.values():
        rows.sort(key=lambda row: row["pair_id"])
    return {"schema_version": "figure5-joint-sort-result/v1", "task_id": "PAPER-paper-method-050",
            "source_kind": packet["source_kind"], "endpoint": "Figure5H_I_joint_sort_fidelity_component",
            "population_unit_count": len(population), "validation_pair_count": len(panel),
            "validation_rat_count": len({r["rat_id"] for r in panel}), "reference_panel": panel,
            "methods": {name: {"pairs": rows,
                "precision": _summary(rows, "precision_percent"),
                "recall": _summary(rows, "recall_percent")} for name, rows in reports.items()},
            "source_panel_dimensions": {"validation_pairs": 10, "rats": 5,
                "limit": "Matching counts do not authenticate the original selected identities."},
            "qualification": "software_component_only_source_population_mapping_and_execution_unverified",
            "limits": ["Joint sorting is an indirect reference, not observed neuron identity.",
                "Overlap counts, spike-clock alignment, chosen-cluster resolution and complete mapping require external verification.",
                "Many-to-one mappings are retained; source duplicate/tie handling remains unverified.",
                "Undefined ratios block their panel summary; zero-denominator and SD policies are not established source parity.",
                "No Friedman/Nemenyi comparison, Figure5D mixed model, equivalence tolerance or improvement decision is implemented."]}


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
