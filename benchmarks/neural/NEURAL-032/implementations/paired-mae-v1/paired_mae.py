"""Source-compatible support and paired, whole-mouse retrospective MAE.

This component does not fit models or grade the primary conditional estimands.
Only the CLI authenticates the complete historical observation export. The pure
functions also accept generated fixtures for software controls.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

MICE = (
    "JW082", "JW083", "JW090", "JW092", "JW129", "JW130", "JW150",
    "JW153", "JW154", "JW167", "JW168", "JW169", "JW193", "JW202",
    "JW205", "JW206", "JW213", "JW215", "JW270", "JW306",
)
INPUT_SHA256 = "4f095339e7b60f647f0d977d3713e72e373a2e397ce579fa451ba04ed23164a6"
INPUT_BYTES = 477396
PROTOCOL = "NEURAL032-paired-retrospective-mae-v1"
NUMERIC = ("baseline_volume", "followup_volume", "event_rate",
           "movement_amplitude", "local", "coincident")
ROW_FIELDS = {"row_id", "mouse_id", "compartment", "member_index0", "source_row0",
              "baseline_flag", "followup_flag", "movement_spine", *NUMERIC}
FLAG_NAMES = ("New Spine", "Eliminated Spine", "Absent", "Shaft Spine")


class Invalid(ValueError):
    """Malformed input, incomplete support or unrepresentable arithmetic."""


def require(condition, message):
    if not condition:
        raise Invalid(message)


def exact_fields(value, fields):
    require(type(value) is dict and set(value) == set(fields), "exact object fields required")


def finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def parse_json(body):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def number(token):
        value = float(token)
        require(math.isfinite(value) and (value != 0 or Decimal(token) == 0),
                "finite binary64 without nonzero underflow required")
        return value

    def bad(_):
        raise Invalid("nonfinite JSON token")

    try:
        return json.loads(body.decode("utf-8"), object_pairs_hook=pairs,
                          parse_float=number, parse_constant=bad)
    except (ValueError, OverflowError, UnicodeError, RecursionError) as exc:
        raise Invalid("invalid strict JSON") from exc


def flag_state(flag):
    """Preserve the source's string versus list/tuple membership semantics."""
    exact_fields(flag, ("kind", "value"))
    kind, value = flag["kind"], flag["value"]
    require(kind in ("str", "list", "tuple"), "typed flag kind required")
    if kind == "str":
        require(type(value) is str, "flag string required")
        entries = [value]
    else:
        require(type(value) is list and all(type(x) is str for x in value),
                "flag sequence required")
        entries = value
    state = {name: name in value for name in FLAG_NAMES}
    admissible = all(entry in ("", *FLAG_NAMES) for entry in entries)
    admissible &= not (state["New Spine"] and
                       (state["Absent"] or state["Eliminated Spine"]))
    return state, admissible


def validate_rows(rows):
    require(type(rows) is list and bool(rows), "nonempty source rows required")
    seen, members, indices = set(), {}, defaultdict(list)
    for row in rows:
        exact_fields(row, ROW_FIELDS)
        require(type(row["mouse_id"]) is str and bool(row["mouse_id"]), "mouse identity required")
        require(row["compartment"] in ("apical", "basal"), "source compartment required")
        for field in ("member_index0", "source_row0"):
            require(type(row[field]) is int and row[field] >= 0, "nonnegative source index required")
        member, index = row["member_index0"], row["source_row0"]
        require(row["row_id"] == f"m{member:02d}r{index:04d}", "source row identity mismatch")
        require(row["row_id"] not in seen, "duplicate source row")
        seen.add(row["row_id"])
        identity = (row["mouse_id"], row["compartment"])
        require(members.setdefault(member, identity) == identity, "source member identity changed")
        indices[member].append(index)
        require(type(row["movement_spine"]) is bool, "movement boolean required")
        require(all(row[key] is None or finite(row[key]) for key in NUMERIC),
                "numeric source field must be finite or null")
        flag_state(row["baseline_flag"])
        flag_state(row["followup_flag"])
    for values in indices.values():
        require(sorted(values) == list(range(len(values))), "complete source-member row sequence required")
    return members


def select_support(rows):
    """Retain source-defined positive followup/baseline ratios, never impute outcomes."""
    validate_rows(rows)
    counts = {"all_rows": len(rows), "baseline_excluded": 0,
              "followup_unavailable": 0, "observed_rows": 0}
    selected = []
    dispositions = []
    by_group = defaultdict(Counter)
    for row in rows:
        baseline, baseline_ok = flag_state(row["baseline_flag"])
        followup, followup_ok = flag_state(row["followup_flag"])
        v, u = row["baseline_volume"], row["followup_volume"]
        ratio = None
        if (not baseline_ok or any(baseline[key] for key in
                                 ("Absent", "Eliminated Spine", "Shaft Spine"))
                or not finite(v) or v <= 0):
            disposition = "baseline_excluded"
        else:
            if followup_ok and not any(followup.values()) and finite(u) and u > 0:
                try:
                    ratio = u / v
                except (OverflowError, ZeroDivisionError):
                    pass
            if not finite(ratio) or ratio <= 0:
                disposition = "followup_unavailable"
            else:
                disposition = "observed_rows"
                selected.append({"row_id": row["row_id"], "mouse_id": row["mouse_id"],
                                 "compartment": row["compartment"], "target": ratio})
        counts[disposition] += 1
        group = by_group[(row["mouse_id"], row["compartment"])]
        group["all_rows"] += 1
        group[disposition] += 1
        dispositions.append({"row_id": row["row_id"], "disposition": disposition})
    source_mice = {row["mouse_id"] for row in rows}
    require({row["mouse_id"] for row in selected} == source_mice,
            "every source mouse must retain an observed outcome; no cohort subset")
    support = {**counts, "by_mouse_compartment": [
        {"mouse_id": mouse, "compartment": compartment,
         **{key: group[key] for key in counts}}
        for (mouse, compartment), group in sorted(by_group.items())
    ], "row_dispositions": dispositions}
    return selected, support


def folds_for(selected):
    """Group all compartments of each mouse into a single held-out fold."""
    mice = sorted({row["mouse_id"] for row in selected})
    require(len(mice) >= 2, "at least two whole mice required")
    return [{"heldout_mouse": mouse,
             "training_mice": [other for other in mice if other != mouse],
             "train_row_ids": [row["row_id"] for row in selected if row["mouse_id"] != mouse],
             "query_row_ids": [row["row_id"] for row in selected if row["mouse_id"] == mouse]}
            for mouse in mice]


def finite_mean(values):
    """Round the complete arithmetic mean once, preserving subnormal losses."""
    return float(sum((Fraction(value) for value in values), Fraction()) / len(values))


def score_rows(rows, submission, input_sha256):
    selected, support = select_support(rows)
    expected = folds_for(selected)
    exact_fields(submission, ("schema_version", "task_id", "protocol", "input_sha256", "folds"))
    require(type(submission["schema_version"]) is int and submission["schema_version"] == 1,
            "schema version 1 required")
    require(submission["task_id"] == "NEURAL-032" and submission["protocol"] == PROTOCOL
            and submission["input_sha256"] == input_sha256, "task, protocol and input binding required")
    folds = submission["folds"]
    require(type(folds) is list and len(folds) == len(expected), "all whole-mouse folds required")
    by_mouse = {}
    for fold in folds:
        exact_fields(fold, ("heldout_mouse", "training_mice", "predictions"))
        mouse = fold["heldout_mouse"]
        require(type(mouse) is str and mouse not in by_mouse, "unique held-out mouse required")
        by_mouse[mouse] = fold
    require(set(by_mouse) == {fold["heldout_mouse"] for fold in expected}, "exact mouse roster required")
    targets = {row["row_id"]: row["target"] for row in selected}
    results = []
    for spec in expected:
        mouse = spec["heldout_mouse"]
        fold = by_mouse[mouse]
        require(fold["training_mice"] == spec["training_mice"], "training mice must exclude entire held-out mouse")
        predictions = fold["predictions"]
        require(type(predictions) is list and len(predictions) == len(spec["query_row_ids"]),
                "both arms must cover every observed query row")
        by_id = {}
        for prediction in predictions:
            exact_fields(prediction, ("row_id", "baseline", "neural"))
            row_id = prediction["row_id"]
            require(type(row_id) is str and row_id not in by_id, "unique prediction row required")
            require(finite(prediction["baseline"]) and finite(prediction["neural"]),
                    "both predictions must be finite numbers")
            by_id[row_id] = prediction
        require(set(by_id) == set(spec["query_row_ids"]), "exact query IDs required")
        losses = {}
        n = len(by_id)
        for arm in ("baseline", "neural"):
            errors = [abs(by_id[row_id][arm] - targets[row_id]) for row_id in spec["query_row_ids"]]
            require(all(finite(error) for error in errors), "absolute error exceeds binary64 range")
            losses[arm + "_mae"] = finite_mean(errors)
        results.append({"mouse_id": mouse, "n": n, **losses,
                        "baseline_minus_neural_mae": losses["baseline_mae"] - losses["neural_mae"]})
    metrics = ("baseline_mae", "neural_mae", "baseline_minus_neural_mae")
    return {"schema_version": 1, "task_id": "NEURAL-032", "protocol": PROTOCOL,
            "input_sha256": input_sha256, "evaluation_scope": "exposed_outcome_retrospective_loss_audit",
            "target": "followup_volume / baseline_volume", "units": "dimensionless volume ratio",
            "support": support, "per_mouse": results,
            "equal_mouse": {key: finite_mean([row[key] for row in results]) for key in metrics}}


def load_observations(path):
    with Path(path).open("rb") as source:
        body = source.read(INPUT_BYTES + 1)
    require(len(body) == INPUT_BYTES and hashlib.sha256(body).hexdigest() == INPUT_SHA256,
            "exact complete20 observation export required")
    value = parse_json(body)
    exact_fields(value, ("schema_version", "task_id", "source_release", "rows", "members", "nonfinite_encoding"))
    require(type(value["schema_version"]) is int and value["schema_version"] == 1
            and value["task_id"] == "NEURAL-032" and value["source_release"] == "Zenodo15047046",
            "source release identity required")
    rows, members = value["rows"], value["members"]
    identities = validate_rows(rows)
    require(len(rows) == 1143 and tuple(sorted({row["mouse_id"] for row in rows})) == MICE,
            "complete 1143-row, 20-mouse source cohort required")
    require(type(members) is list and len(members) == 27 and set(identities) == set(range(27)),
            "complete 27-member source cohort required")
    for index, member in enumerate(members):
        exact_fields(member, ("index0", "source_member", "source_pickle", "rows"))
        require(type(member["index0"]) is int and member["index0"] == index
                and type(member["rows"]) is int
                and member["rows"] == sum(row["member_index0"] == index for row in rows),
                "source member row counts disagree")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "score"))
    parser.add_argument("--observations", required=True, type=Path)
    parser.add_argument("--submission", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if (args.action == "score") != (args.submission is not None):
        parser.error("--submission is required exactly for score")
    rows = load_observations(args.observations)
    if args.action == "plan":
        selected, support = select_support(rows)
        result = {"task_id": "NEURAL-032", "protocol": PROTOCOL,
                  "input_sha256": INPUT_SHA256, "support": support, "folds": folds_for(selected)}
    else:
        with args.submission.open("rb") as source:
            body = source.read(262145)
        require(0 < len(body) <= 262144, "submission must be at most 262144 bytes")
        result = score_rows(rows, parse_json(body), INPUT_SHA256)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2, allow_nan=False)
        output.write("\n")


if __name__ == "__main__":
    main()
