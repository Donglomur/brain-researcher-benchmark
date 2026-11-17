"""Original ED2c,d SOM quantization-error arithmetic; no fitting or admission.

Source locators and qualification limits are recorded in SOURCE_AUDIT.md.
The operator supplies a hash-frozen packet, not participant-supplied features.
Only the candidate's node prototype values may differ from the source map.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re


FEATURES = ["B_mean", "M_mean", "rate_mean"]
PFC_ORDER = ["MOs", "ACAd", "ACAv", "PL", "ILA", "ORBm", "ORBvl",
             "ORBl", "FRP", "AId", "AIv"]
PARENT_ORDER = ["PFC", "MO", "AUD", "SS", "VIS", "DP", "TT", "AON",
                "PIR", "HPF", "ACB", "CP", "LS", "EPd", "TH"]
PARENTS = {
    "PFC": ["MOs", "ACAd", "ACAv", "PL", "ILA", "FRP", "ACA", "ORBl",
            "ORBvl", "ORBm", "ORB", "AId", "AIv"],
    "DP": ["DP"], "TT": ["TTd", "TTv"], "LS": ["LSr", "SH", "LSv", "LSc"],
    "CP": ["CP"], "ACB": ["ACB"],
    "HPF": ["CA1", "CA2", "CA3", "DG-mo", "DG-po", "DG-sg", "HPF"],
    "MO": ["MOp"], "AON": ["AON"], "PIR": ["PIR"],
    "SS": ["SSp-bfd", "SSp-m", "SSs", "SSp-tr", "SSp-n", "SSp-ul",
           "SSp-ll", "SSp-un"],
    "VIS": ["VISa", "VISal", "VISli", "VISp", "VISpm", "VISam",
            "VISpor", "VISpl", "VISl", "VISrl"],
    "AUD": ["AUDpo", "AUDd", "AUDp"], "EPd": ["EPd"],
    "TH": ["RT", "VPM", "LP", "LGv", "LD", "VPL", "Eth", "PO", "LGd-co"],
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def keys(obj, expected, name):
    require(isinstance(obj, dict) and set(obj) == set(expected),
            f"{name}: unexpected or missing fields")


def vector(value, name):
    require(isinstance(value, list) and len(value) == 3, f"{name}: need three features")
    require(all(type(v) in (int, float) and math.isfinite(v) for v in value),
            f"{name}: require finite numeric features")
    return tuple(float(v) for v in value)


def area_of(region):
    # unitloader.Unit.area uses settings.decompose_area_layer, not prefix guesses.
    if region in {"CA1", "CA2", "CA3"}:
        return region
    match = re.search(r"\d", region)
    return region[:match.start()] if match else region


def parent_of(area):
    return next((name for name, areas in PARENTS.items() if area in areas), "na")


def percentile(values, probability):
    """SciPy scoreatpercentile default fractional interpolation, p in [0,1]."""
    ordered = sorted(values)
    require(bool(ordered), "empty region")
    rank = (len(ordered) - 1) * probability
    lower, upper = math.floor(rank), math.ceil(rank)
    fraction = rank - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def describe(values):
    return {"n_units": len(values), "median": percentile(values, .5),
            "q25": percentile(values, .25), "q75": percentile(values, .75)}


def validate_map(value, name):
    keys(value, ["topology", "kshape", "prototypes"], name)
    require(value["topology"] == "hex", f"{name}: require source hexagonal topology")
    shape = value["kshape"]
    require(isinstance(shape, list) and len(shape) == 2 and
            all(type(x) is int and 1 <= x <= 1000 for x in shape),
            f"{name}: invalid grid shape")
    nodes = value["prototypes"]
    require(isinstance(nodes, list) and len(nodes) == math.prod(shape),
            f"{name}: prototype count differs from grid capacity")
    require(len(nodes) >= 2, f"{name}: grid must contain at least two nodes")
    return [vector(row, f"{name} node") for row in nodes]


def validate_packet(packet, *, require_source_population=True):
    keys(packet, ["schema", "task_id", "source_run", "feature_names", "feature_space",
                  "reference_mean", "reference_std", "feature_weights", "source_map",
                  "units", "panel_counts"], "packet")
    require(packet["schema"] == "pfc-source-qerror-packet/v1", "wrong packet schema")
    require(packet["task_id"] == "PAPER-EXP-20261113-005", "wrong task")
    require(packet["source_run"] == "runC00dMP3_brain", "wrong source population")
    require(packet["feature_names"] == FEATURES, "source feature order differs")
    require(packet["feature_space"] == "author-loader-output-before-standardization",
            "features must already have the author's upstream transformations")
    mean = vector(packet["reference_mean"], "source mean")
    std = vector(packet["reference_std"], "source std")
    require(all(s > 0 for s in std), "source standard deviations must be positive")
    require(vector(packet["feature_weights"], "feature weights") == (1., 1., 1.),
            "source feature weights differ")
    source_nodes = validate_map(packet["source_map"], "source map")
    units = packet["units"]
    require(isinstance(units, list) and units, "empty population")
    ids, records, recording_animals, standardized = set(), set(), {}, []
    for unit in units:
        keys(unit, ["unit_id", "recording_id", "animal_id", "region", "area", "features"], "unit")
        require(all(isinstance(unit[k], str) and unit[k] for k in
                    ("unit_id", "recording_id", "animal_id", "region", "area")),
                "unit identities/anatomy must be nonempty strings")
        require(unit["unit_id"] not in ids, "duplicate unit identity")
        ids.add(unit["unit_id"])
        record, animal = unit["recording_id"], unit["animal_id"]
        require(recording_animals.setdefault(record, animal) == animal,
                "recording assigned to multiple animals")
        records.add(record)
        require(unit["area"] == area_of(unit["region"]), "source area/region join differs")
        values = vector(unit["features"], "unit features")
        z = tuple((v - m) / s for v, m, s in zip(values, mean, std))
        require(all(math.isfinite(x) for x in z), "standardization overflow")
        standardized.append(z)
    unique_areas = {u["area"] for u in units}
    # Reproduce the two distinct original selectors, including substring behavior
    # of plot_SOM.py, rather than substituting the fixed-map ROI cohort.
    groups = {"ED2c": {reg: [i for i, u in enumerate(units) if reg in u["region"]]
                       for reg in PFC_ORDER if reg in unique_areas},
              "ED2d": {reg: [i for i, u in enumerate(units)
                              if parent_of(u["area"]) == reg]
                       for reg in PARENT_ORDER
                       if any(parent_of(u["area"]) == reg for u in units)}}
    counts = {panel: {reg: len(rows) for reg, rows in regions.items()}
              for panel, regions in groups.items()}
    require(packet["panel_counts"] == counts, "frozen complete region panel/counts differ")
    require(all(type(n) is int and n > 0 for panel in packet["panel_counts"].values()
                for n in panel.values()), "panel counts must be positive integers")
    if require_source_population:
        require(len(units) == 19186, "original pool must contain 19,186 units")
        require(len(records) == 99, "original pool must contain 99 recording probes")
        require(counts["ED2d"].get("PFC") == 10413,
                "original PFC panel must contain 10,413 units; resolve source discrepancy")
        require(sum(counts["ED2c"].values()) == 10413,
                "original ED2c subregion count must be 10,413; resolve source discrepancy")
    return standardized, source_nodes, groups


def distances(points, prototypes):
    """Unit-wise nearest Euclidean distance, preserving first-index BMU ties."""
    errors, bmus = [], []
    for point in points:
        norms = [math.dist(point, node) for node in prototypes]
        bmu = min(range(len(norms)), key=norms.__getitem__)
        require(math.isfinite(norms[bmu]), "quantization distance overflow")
        errors.append(norms[bmu])
        bmus.append(bmu)
    return errors, bmus


def score(packet, candidate, *, require_source_population=True):
    points, source_nodes, groups = validate_packet(
        packet, require_source_population=require_source_population)
    candidate_nodes = validate_map(candidate, "candidate map")
    require(candidate["kshape"] == packet["source_map"]["kshape"],
            "candidate changes original grid shape/capacity")
    source_error, _ = distances(points, source_nodes)
    candidate_error, _ = distances(points, candidate_nodes)
    panels = {}
    for panel, regions in groups.items():
        panels[panel] = {}
        for region, rows in regions.items():
            reference = describe([source_error[i] for i in rows])
            result = describe([candidate_error[i] for i in rows])
            panels[panel][region] = {
                "source": reference, "candidate": result,
                "candidate_minus_source_median": result["median"] - reference["median"],
                "median_paired_unit_difference": percentile(
                    [candidate_error[i] - source_error[i] for i in rows], .5),
                "n_recordings": len({packet["units"][i]["recording_id"] for i in rows}),
                "n_animals": len({packet["units"][i]["animal_id"] for i in rows}),
            }
    assigned = {i for rows in groups["ED2d"].values() for i in rows}
    return {
        "schema": "pfc-source-qerror-score/v1", "evaluation_condition": "in_sample",
        "qualification": "arithmetic_component_only", "paper_win": None,
        "n_units": len(points), "node_count": len(source_nodes),
        "n_units_without_source_parent": len(points) - len(assigned),
        "panels": panels,
        "diagnostic_all_unit_mean": {
            "source": math.fsum(source_error) / len(points),
            "candidate": math.fsum(candidate_error) / len(points)},
    }


def strict_json(data):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    def reject_constant(value):
        raise ValueError(f"nonfinite JSON constant: {value}")
    return json.loads(data, object_pairs_hook=object_pairs, parse_constant=reject_constant)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--packet-sha256", required=True)
    parser.add_argument("--candidate", required=True, type=Path)
    args = parser.parse_args()
    require(re.fullmatch(r"[0-9a-f]{64}", args.packet_sha256), "invalid packet SHA256")
    body = args.packet.read_bytes()
    require(hashlib.sha256(body).hexdigest() == args.packet_sha256, "packet SHA256 differs")
    candidate_body = args.candidate.read_bytes()
    result = score(strict_json(body), strict_json(candidate_body))
    result["packet_sha256"] = args.packet_sha256
    result["candidate_sha256"] = hashlib.sha256(candidate_body).hexdigest()
    print(json.dumps(result, allow_nan=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
