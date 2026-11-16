"""DFINE grid-reaching numeric component; no fitting or inference authorization."""

import argparse
import hashlib
import json
import math
from pathlib import Path

TASK = "PAPER-CANDIDATE-20261114-DFINE"
CONTRACT_SHA256 = "1ef29d2543e0fb1c6b707b2ae6206baaf1b79fc36a728020f7dea3ac181622cc"
DIMENSIONS = ["position_x", "position_y", "velocity_x", "velocity_y"]
METHODS = ("dfine_filter", "dfine_smooth", "ldm_smooth", "sae_zero_smooth", "sae_average_smooth")
KEY_FIELDS = ("session_id", "fold", "observed_percent", "replicate_id")
MAX_FILE_BYTES = 64 * 1024 * 1024


class Invalid(ValueError):
    pass


def require(test, message):
    if not test:
        raise Invalid(message)


def exact_keys(obj, keys):
    require(type(obj) is dict and set(obj) == set(keys), "unexpected or missing fields")


def named(value):
    require(type(value) is str and 0 < len(value) <= 128, "invalid identifier")
    require(all(32 <= ord(c) < 127 for c in value), "identifier must be printable ASCII")
    return value


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value):
    return (json.dumps(value, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode()


def finite(value):
    require(type(value) in (int, float), "numeric value must not be boolean/string")
    try:
        x = float(value)
    except (OverflowError, ValueError):
        raise Invalid("nonfinite numeric value") from None
    require(math.isfinite(x), "nonfinite numeric value")
    return x


def matrix(values, n):
    require(type(values) is list and len(values) == n, "wrong time support")
    for row in values:
        require(type(row) is list and len(row) == 4, "expected four behavior dimensions")
        for x in row:
            finite(x)


def validate_mask(bits, observed_percent):
    """The paper fixes a count in each100-step block, not independent Bernoulli draws.

    An incomplete trailing block is unresolved by the inspected sources. Refuse
    it here; never trim it, invent its count, or reinterpret an observed ratio.
    """
    require(type(observed_percent) is int and 20 <= observed_percent <= 100, "invalid observed percent")
    require(type(bits) is str and len(bits) >= 100 and len(bits) % 100 == 0, "unresolved partial100-step block")
    require(set(bits) <= {"0", "1"}, "mask must use1=observed and0=missing")
    for start in range(0, len(bits), 100):
        require(bits[start:start + 100].count("1") == observed_percent, "wrong observed count in100-step block")
    return digest(bits.encode("ascii"))


def admit_profile(profile):
    exact_keys(profile, ["schema", "task_id", "contract_sha256", "sessions", "folds", "dimensions", "observed_percents", "replicate_ids", "supports", "masks"])
    require(profile["schema"] == "dfine_missing_observation_profile_v1", "wrong profile schema")
    require(profile["task_id"] == TASK and profile["contract_sha256"] == CONTRACT_SHA256, "wrong task/contract")
    sessions = profile["sessions"]
    require(type(sessions) is list and len(sessions) == 7, "complete seven-session population required")
    require(len({named(x) for x in sessions}) == 7, "duplicate session")
    require(profile["folds"] == [0, 1, 2, 3, 4] and all(type(x) is int for x in profile["folds"]), "complete fivefold population required")
    require(profile["dimensions"] == DIMENSIONS, "wrong behavior dimensions/order")
    ratios = profile["observed_percents"]
    require(type(ratios) is list and ratios and all(type(r) is int and 20 <= r <= 100 for r in ratios), "invalid ratio grid")
    require(ratios == sorted(set(ratios)) and {20, 30, 60, 100} <= set(ratios), "missing required endpoint/comparator ratios")
    reps = profile["replicate_ids"]
    require(type(reps) is list and 0 < len(reps) <= 100, "invalid replicate roster")
    require(len({named(x) for x in reps}) == len(reps), "duplicate replicate")
    require(type(profile["supports"]) is list and len(profile["supports"]) == 35, "complete35 session-fold supports required")
    support = {}
    session_ids = {s: set() for s in sessions}
    session_lengths = {}
    for row in profile["supports"]:
        exact_keys(row, ["session_id", "fold", "sample_ids"])
        require(type(row["fold"]) is int, "invalid fold")
        key = (row["session_id"], row["fold"])
        require(key[0] in sessions and key[1] in profile["folds"] and key not in support, "wrong/duplicate support")
        ids = row["sample_ids"]
        require(type(ids) is list and len(ids) >= 100 and len(ids) % 100 == 0, "unresolved partial100-step support")
        require(all(type(i) is int and i >= 0 for i in ids) and ids == sorted(set(ids)), "invalid/duplicate/unordered sample identities")
        require(not session_ids[key[0]].intersection(ids), "test folds overlap within session")
        session_ids[key[0]].update(ids)
        require(session_lengths.setdefault(key[0], len(ids)) == len(ids), "fold sizes differ within session")
        support[key] = (len(ids), digest(json_bytes(ids)), ids)
    # Fixed population cardinality and membership imply the complete7x5 product.
    expected_masks = {(s, f, r, rep) for s in sessions for f in profile["folds"] for r in ratios for rep in reps}
    require(type(profile["masks"]) is list and len(profile["masks"]) == len(expected_masks), "incomplete mask population")
    masks = {}
    for row in profile["masks"]:
        exact_keys(row, [*KEY_FIELDS, "bits"])
        require(type(row["fold"]) is int and type(row["observed_percent"]) is int, "invalid mask key")
        key = tuple(row[k] for k in KEY_FIELDS)
        require(key in expected_masks and key not in masks, "wrong/duplicate mask")
        require(type(row["bits"]) is str and len(row["bits"]) == support[key[:2]][0], "mask/support length mismatch")
        masks[key] = validate_mask(row["bits"], row["observed_percent"])
    expected = {}
    for key, mask_sha in masks.items():
        methods = METHODS if key[2] in (30, 60, 100) else METHODS[:2]
        for method in methods:
            expected[key + (method,)] = (mask_sha, support[key[:2]])
    return support, expected


def admit_predictions(records, expected):
    require(type(records) is list and len(records) == len(expected), "incomplete prediction population")
    result = {}
    for row in records:
        exact_keys(row, [*KEY_FIELDS, "method", "mask_sha256", "sample_ids_sha256", "values"])
        require(type(row["fold"]) is int and type(row["observed_percent"]) is int, "invalid prediction key")
        key = tuple(row[k] for k in KEY_FIELDS) + (row["method"],)
        require(key in expected and key not in result, "wrong/duplicate prediction cell")
        mask_sha, (n, ids_sha, _) = expected[key]
        require(row["mask_sha256"] == mask_sha and row["sample_ids_sha256"] == ids_sha, "prediction/mask/time identity mismatch")
        matrix(row["values"], n)
        result[key] = row["values"]
    return result


def pearson_cc(x, y):
    """Pearson r in scaled float64 arithmetic; constant columns contribute zero.

    Zero is the current author's NaN-to-zero convention, not an estimated r.
    This is not a claim of Torch/SciPy float32 reduction bitwise parity.
    """
    require(len(x) == len(y) and len(x) >= 2, "Pearson support mismatch")
    def center(v):
        v = [finite(a) for a in v]
        scale = max(map(abs, v))
        if scale == 0:
            return [0.0] * len(v)
        v = [a / scale for a in v]
        mean = math.fsum(v) / len(v)
        return [a - mean for a in v]
    a, b = center(x), center(y)
    na, nb = math.hypot(*a), math.hypot(*b)
    if na == 0 or nb == 0:
        return 0.0, True
    value = math.fsum((u / na) * (v / nb) for u, v in zip(a, b))
    return max(-1.0, min(1.0, value)), False


def grade(profile, candidate_records, reference_records, target_loader):
    """Validate BOTH complete submissions before invoking trusted private loader."""
    support, expected = admit_profile(profile)
    candidate = admit_predictions(candidate_records, expected)
    reference = admit_predictions(reference_records, expected)
    targets = target_loader()
    require(type(targets) is list and len(targets) == 35, "complete private35-cell target support required")
    truth = {}
    for row in targets:
        exact_keys(row, ["session_id", "fold", "sample_ids", "values"])
        require(type(row["fold"]) is int, "invalid target fold")
        key = (row["session_id"], row["fold"])
        require(key in support and key not in truth, "wrong/duplicate private support")
        n, _, ids = support[key]
        require(row["sample_ids"] == ids and all(type(i) is int for i in row["sample_ids"]), "private time alignment mismatch")
        matrix(row["values"], n)
        truth[key] = row["values"]
    cells, grouped = [], {}
    for key in sorted(expected):
        t = truth[key[:2]]
        row = dict(zip((*KEY_FIELDS, "method"), key))
        for label, records in (("candidate", candidate), ("reference", reference)):
            cols = [pearson_cc([r[d] for r in t], [r[d] for r in records[key]]) for d in range(4)]
            row[label + "_dimension_cc"] = [x[0] for x in cols]
            row[label + "_constant_dimensions"] = [d for d, x in enumerate(cols) if x[1]]
            row[label + "_cc"] = math.fsum(x[0] for x in cols) / 4
        row["delta_cc"] = row["candidate_cc"] - row["reference_cc"]
        cells.append(row)
        grouped.setdefault((key[4], key[2]), []).append(row)
    curves = []
    for (method, ratio), rows in sorted(grouped.items()):
        # Replicates receive equal weight within each of the fixed35 session-folds.
        by_cell = {}
        for row in rows:
            by_cell.setdefault((row["session_id"], row["fold"]), []).append(row)
        require(len(by_cell) == 35, "internal incomplete curve")
        result = {"method": method, "observed_percent": ratio, "session_fold_count": 35}
        for label in ("candidate", "reference"):
            values = [math.fsum(x[label + "_cc"] for x in rs) / len(rs) for rs in by_cell.values()]
            result[label + "_cc"] = math.fsum(values) / 35
        result["delta_cc"] = result["candidate_cc"] - result["reference_cc"]
        curves.append(result)
    return {"schema": "dfine_missing_observation_scores_v1", "task_id": TASK,
            "declared_prediction_cells": len(cells), "cells": cells, "curves": curves,
            "population": {"sessions": 7, "folds_per_session": 5, "behavior_dimensions": 4, "biological_animals": 1},
            "claims": {"numeric_component_only": True, "authentic_population_verified": False,
                       "historical_grid_verified": False, "candidate_execution_verified": False,
                       "causal_information_boundary_verified": False, "scientific_qualification": False},
            "overall_scalar": None, "overall_scalar_reason": "No source-defined pooling over methods/ratios or prospective integrated loss has been frozen."}


def load_json(path, expected_sha256=None):
    with Path(path).open("rb") as f:
        body = f.read(MAX_FILE_BYTES + 1)
    require(len(body) <= MAX_FILE_BYTES, "file exceeds component limit")
    if expected_sha256 is not None:
        require(digest(body) == expected_sha256, "owner-profile identity mismatch")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    def bad_constant(value):
        raise Invalid("nonfinite JSON literal")
    return json.loads(body, object_pairs_hook=pairs, parse_constant=bad_constant)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--profile", required=True)
    p.add_argument("--profile-sha256", required=True)
    p.add_argument("--candidate", required=True)
    p.add_argument("--reference", required=True)
    p.add_argument("--private-targets", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    profile = load_json(a.profile, a.profile_sha256)
    candidate, reference = load_json(a.candidate), load_json(a.reference)
    result = grade(profile, candidate, reference, lambda: load_json(a.private_targets))
    with Path(a.output).open("x", encoding="utf-8") as f:
        json.dump(result, f, allow_nan=False, sort_keys=True)
        f.write("\n")


if __name__ == "__main__":
    main()
