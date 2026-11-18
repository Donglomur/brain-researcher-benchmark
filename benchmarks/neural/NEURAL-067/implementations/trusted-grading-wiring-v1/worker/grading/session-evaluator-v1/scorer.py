"""Complete NEURAL-067 held-out trajectory scorer; Python standard library only.

The operator owns targets. This module never executes a participant program and
cannot establish causal access, transport isolation, or scientific performance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

ARMS = ("neural", "clock", "neural_clock", "shifted_neural_clock")
COLUMNS = ("tx", "ty", "tz", "rx", "g1", "g2", "g3")
# Exact existing public design; official config.py provides the S6..S12 map.
QUERY = (
    ("19250126T113454", "S6", 2376),
    ("19250126T114029", "S6", 2408),
    ("19250127T120333", "S7", 2454),
    ("19250127T120826", "S7", 2647),
    ("19250129T112555", "S8", 2469),
    ("19250129T113059", "S8", 2347),
    ("19250202T113958", "S9", 2406),
    ("19250202T114452", "S9", 2496),
    ("19250203T113515", "S10", 2369),
    ("19250203T114018", "S10", 2303),
    ("19250206T112219", "S11", 2470),
    ("19250206T112712", "S11", 2442),
    ("19250209T111826", "S12", 2713),
    ("19250209T112327", "S12", 2590),
)
SESSIONS = tuple(dict.fromkeys(row[1] for row in QUERY))
CONTRACT = {
    "task_id": "NEURAL-067",
    "arms": list(ARMS),
    "columns": list(COLUMNS),
    "query": [{"run": r, "session": s, "n_rows": n} for r, s, n in QUERY],
    "row_identity": "zero-based full-run bin index in source order",
    "aggregation": "mask; pool runs within session; variance weight outputs; equal sessions",
    "constant_target_policy": "undefined per channel; zero variance weight; all-constant session undefined",
    "undefined_session_policy": "retain every session and return undefined aggregate",
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


CONTRACT_SHA256 = hashlib.sha256(canonical(CONTRACT)).hexdigest()


def need(condition, message):
    if not condition:
        raise ValueError(message)


def keys(value, expected, message):
    need(type(value) is dict and set(value) == set(expected), message)


def rows(value, count, name):
    need(type(value) is list and len(value) == count, f"{name}: complete row count")
    frozen = []
    for row in value:
        need(type(row) is list and len(row) == 7, f"{name}: seven ordered columns")
        converted = []
        for x in row:
            need(type(x) in (int, float), f"{name}: numeric values, not booleans")
            try:
                x = float(x)
            except (OverflowError, ValueError) as exc:
                raise ValueError(f"{name}: representable finite values") from exc
            need(math.isfinite(x), f"{name}: finite values")
            converted.append(x)
        frozen.append(tuple(converted))
    return tuple(frozen)


def identity(value, run, session, count):
    need(value["run"] == run and value["session"] == session, "exact run/session order")
    ids = value["row_ids"]
    need(type(ids) is list and len(ids) == count, "complete row IDs")
    need(all(type(x) is int and x == i for i, x in enumerate(ids)), "exact ordered row IDs")


def admit(submission):
    """Validate and capture every arm/run before calling an operator target loader."""
    keys(submission, ("schema", "contract_sha256", "columns", "entries"), "submission fields")
    need(submission["schema"] == "neural067_session_predictions_v1", "submission schema")
    need(submission["contract_sha256"] == CONTRACT_SHA256, "exact scorer contract")
    need(submission["columns"] == list(COLUMNS), "exact source coordinate order")
    entries = submission["entries"]
    need(type(entries) is list and len(entries) == len(ARMS) * len(QUERY), "complete 56 blocks")
    captured = {}
    for index, (arm, run, session, count) in enumerate(
        (a, r, s, n) for a in ARMS for r, s, n in QUERY
    ):
        entry = entries[index]
        keys(entry, ("arm", "run", "session", "row_ids", "prediction"), "entry fields")
        need(entry["arm"] == arm, "exact ordered information arms")
        identity(entry, run, session, count)
        captured[(arm, run)] = rows(entry["prediction"], count, "prediction")
    return captured


def metric(target, prediction):
    """Variance-weighted seven-output R² with explicit undefined constants.

    Pooling happens before this call. Constant coordinates carry zero weight,
    as in the source multichannel metric; their own R² remains undefined. If
    all seven coordinates are constant, no numeric session score is invented.
    """
    need(len(target) == len(prediction) and len(target) >= 2, "at least two masked rows")
    y = rows([list(row) for row in target], len(target), "masked target")
    p = rows([list(row) for row in prediction], len(prediction), "masked prediction")
    sse, sst, r2, dispositions = [], [], [], []
    try:
        for channel in range(7):
            values = [row[channel] for row in y]
            errors = [(truth[channel] - pred[channel]) ** 2 for truth, pred in zip(y, p)]
            residual = math.fsum(errors)
            constant = all(x == values[0] for x in values)
            # Anchor the mean to avoid false positive variance in repeated 0.1.
            center = values[0] + math.fsum(x - values[0] for x in values) / len(values)
            variance = 0.0 if constant else math.fsum((x - center) ** 2 for x in values)
            need(math.isfinite(residual) and math.isfinite(variance), "representable SSE/SST")
            need(constant or variance > 0, "nonconstant target variance underflow")
            sse.append(residual)
            sst.append(variance)
            r2.append(None if constant else 1.0 - residual / variance)
            dispositions.append("undefined_constant_target" if constant else "defined")
        varying = [i for i in range(7) if sst[i] > 0]
        weighted = (
            1.0 - math.fsum(sse[i] for i in varying) / math.fsum(sst[i] for i in varying)
            if varying else None
        )
    except (OverflowError, ZeroDivisionError) as exc:
        raise ValueError("unrepresentable metric arithmetic") from exc
    need(all(x is None or math.isfinite(x) for x in r2 + [weighted]), "finite defined metrics")
    return {
        "variance_weighted_r2": weighted,
        "status": "defined" if varying else "undefined_all_targets_constant",
        "scored_rows": len(y),
        "per_channel_r2": r2,
        "per_channel_disposition": dispositions,
        "constant_target_channels": [i for i in range(7) if i not in varying],
        "sse": sse,
        "sst": sst,
        "mse": [x / len(y) for x in sse],
    }


def summary(values):
    if any(x is None for x in values):
        return {"mean": None, "std": None, "status": "undefined_session_retained"}
    try:
        mean = math.fsum(values) / len(values)
        std = math.sqrt(math.fsum((x - mean) ** 2 for x in values) / len(values))
    except (OverflowError, ZeroDivisionError) as exc:
        raise ValueError("unrepresentable session aggregation") from exc
    need(math.isfinite(mean) and math.isfinite(std), "finite session aggregation")
    return {"mean": mean, "std": std, "status": "defined"}


def grade(submission, load_target):
    prediction = admit(submission)
    targets = {}
    masks = {}
    for run, session, count in QUERY:
        target = load_target(run)
        keys(target, ("run", "session", "row_ids", "velocity", "eval_mask"), "target fields")
        identity(target, run, session, count)
        targets[run] = rows(target["velocity"], count, "target")
        mask = target["eval_mask"]
        need(type(mask) is list and len(mask) == count and all(type(x) is bool for x in mask),
             "complete boolean source mask")
        masks[run] = tuple(mask)
    scores = {}
    for arm in ARMS:
        by_session = {}
        for session in SESSIONS:
            pooled_y, pooled_p = [], []
            for run, source_session, _ in QUERY:
                if source_session == session:
                    for i, selected in enumerate(masks[run]):
                        if selected:
                            pooled_y.append(targets[run][i])
                            pooled_p.append(prediction[(arm, run)][i])
            by_session[session] = metric(pooled_y, pooled_p)
        scores[arm] = {
            "by_session": by_session,
            "held_out_session_r2": summary([by_session[s]["variance_weighted_r2"] for s in SESSIONS]),
        }
    effects = {}
    for name, arm, baseline in (
        ("neural_clock_minus_clock", "neural_clock", "clock"),
        ("neural_clock_minus_shifted", "neural_clock", "shifted_neural_clock"),
    ):
        differences = {}
        for session in SESSIONS:
            a = scores[arm]["by_session"][session]["variance_weighted_r2"]
            b = scores[baseline]["by_session"][session]["variance_weighted_r2"]
            differences[session] = None if a is None or b is None else a - b
        effects[name] = {"by_session": differences, "session_difference": summary(list(differences.values()))}
    return {
        "schema": "neural067_session_grade_v1",
        "contract_sha256": CONTRACT_SHA256,
        "biological_people": 1,
        "query_runs": len(QUERY),
        "query_sessions": len(SESSIONS),
        "full_rows_per_arm": sum(n for _, _, n in QUERY),
        "masked_rows_per_arm": sum(sum(mask) for mask in masks.values()),
        "held_in": {"status": "not_in_declared_query_panel"},
        "arms": scores,
        "paired_session_differences": effects,
        "causal_program_execution_verified": False,
        "access_mode_verified": False,
        "official_hidden_test_score": False,
        "population_generalization": False,
    }


def read_json(path):
    def unique_pairs(pairs):
        value = {}
        for name, item in pairs:
            need(name not in value, "duplicate JSON key")
            value[name] = item
        return value

    def invalid_constant(value):
        raise ValueError("nonfinite JSON literal: " + value)

    return json.loads(Path(path).read_text(), object_pairs_hook=unique_pairs, parse_constant=invalid_constant)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True, help="operator-owned target JSON; never participant-facing")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    need(not args.output.exists(), "output must be new")
    submission = read_json(args.submission)
    bundle = None

    def load_target(run):
        nonlocal bundle
        if bundle is None:
            bundle = read_json(args.targets)
            keys(bundle, ("schema", "contract_sha256", "runs"), "target bundle fields")
            need(bundle["schema"] == "neural067_session_targets_v1", "target bundle schema")
            need(bundle["contract_sha256"] == CONTRACT_SHA256, "target contract join")
            keys(bundle["runs"], (r for r, _, _ in QUERY), "complete target run roster")
        return bundle["runs"][run]

    result = grade(submission, load_target)
    with args.output.open("xb") as stream:
        stream.write(canonical(result) + b"\n")


if __name__ == "__main__":
    main()
