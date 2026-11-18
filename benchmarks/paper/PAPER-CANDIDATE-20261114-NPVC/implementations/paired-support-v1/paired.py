#!/usr/bin/env python3
"""Pair complete *declared* NPvC operand support; no paper-win decision.

This is operator-side construction. It cannot authenticate historical membership,
split provenance, density admissibility, exposure or an original author fit.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

EQUATIONS_SHA256 = "cf9b47bf26146120888d4ccfce81c9b02f8301211a73e7eb3bb2355e18ec79ca"
MAX_INPUT_BYTES = 64 * 1024 * 1024
ROW_FIELDS = ("trial_id", "frame_id", "fold_id", "trial_type", "activity")
IDENTITY_FIELDS = ("animal_id", "session_id", "neuron_id", "projection", "epoch")


class Invalid(ValueError):
    """The two bundles do not implement the same declared observation panel."""


def require(condition, message):
    if not condition:
        raise Invalid(message)


def equations():
    """Load the existing reviewed arithmetic, refusing an unreviewed replacement."""
    path = Path(__file__).resolve().parents[1] / "fde-equations-v1" / "fde.py"
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == EQUATIONS_SHA256,
            "FDE dependency changed; review the equation binding before use")
    spec = importlib.util.spec_from_file_location("npvc_bound_equations", path)
    module = importlib.util.module_from_spec(spec)
    # Execute the bytes that were checked, rather than letting a path loader
    # reopen a potentially replaced dependency after the identity check.
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def exact_keys(value, fields, name):
    require(type(value) is dict and set(value) == set(fields), name + " has incorrect fields")


def unit_identity(value, fde):
    exact_keys(value, IDENTITY_FIELDS, "identity")
    key = tuple(fde.token(value[k], k) for k in IDENTITY_FIELDS)
    require(value["epoch"] in fde.EPOCHS, "unknown source epoch")
    return key


def row_identity(row, bounds, fde):
    for key in ("trial_id", "frame_id"):
        fde.token(row[key], key)
    require(type(row["fold_id"]) is int and 1 <= row["fold_id"] <= 5,
            "fold_id must be an integer from 1 to 5")
    require(type(row["trial_type"]) is int and 1 <= row["trial_type"] <= 8,
            "trial_type must be an integer from 1 to 8")
    # Validate the numerical domain without rounding correspondence identities.
    # In particular, unequal integers above2**53 must not become equal floats.
    fde.finite(row["activity"], "activity")
    activity = row["activity"]
    require(bounds[0] <= activity <= bounds[1], "activity outside source bounds")
    return (row["trial_id"], row["frame_id"]), (
        row["fold_id"], row["trial_type"], activity)


def index(document, *, support, fde):
    exact_keys(document, ("schema", "units"), "document")
    expected_schema = "npvc-declared-support-v1" if support else "npvc-fde-operands-v1"
    require(document["schema"] == expected_schema, "wrong input schema")
    require(type(document["units"]) is list and document["units"], "nonempty units required")
    units, order, sessions, cells = {}, [], {}, {}
    for unit in document["units"]:
        exact_keys(unit, ("identity", "activity_bounds", "observations"), "unit")
        key = unit_identity(unit["identity"], fde)
        require(key not in units, "duplicate unit identity")
        fde.source_grid(unit["activity_bounds"])
        bounds = tuple(unit["activity_bounds"])
        session, animal, neuron, projection = key[1], key[0], key[2], key[3]
        require(sessions.setdefault(session, animal) == animal,
                "session maps to different animals")
        require(cells.setdefault((session, neuron), (projection, bounds)) == (projection, bounds),
                "projection or activity bounds changed across epochs")
        require(type(unit["observations"]) is list and unit["observations"], "nonempty observations required")
        rows, trial_types = {}, {}
        for row in unit["observations"]:
            exact_keys(row, ROW_FIELDS if support else ROW_FIELDS + ("npvc", "glm"), "observation")
            row_key, metadata = row_identity(row, bounds, fde)
            require(row_key not in rows, "duplicate trial/frame identity")
            require(trial_types.setdefault(row_key[0], metadata[1]) == metadata[1],
                    "trial type changed within a trial")
            if not support:
                exact_keys(row["npvc"], ("log_joint_grid", "log_joint_observed", "log_marginal_observed"), "NPvC operands")
                exact_keys(row["glm"], ("mean", "null_mean"), "GLM operands")
            rows[row_key] = metadata
        units[key] = {"bounds": bounds, "rows": rows, "unit": unit}
        order.append(key)
    return units, order


def compare_support(expected, actual, label):
    require(set(expected) == set(actual), label + " has missing or extra neuron/epoch units")
    for key, item in expected.items():
        found = actual[key]
        require(found["bounds"] == item["bounds"], label + " changes activity coordinates")
        require(set(found["rows"]) == set(item["rows"]), label + " has missing or extra trial/frame observations")
        require(found["rows"] == item["rows"],
                label + " changes held-out fold, trial type or observed activity")


def compare(support, author, candidate):
    """Recompute the full paired vector without choosing a superiority rule.

The support is supplied by an operator, not inferred from either submission.
Ordering may differ, but every declared identity and observed value must match.
Model-specific null/saturated operands may differ: the differences are reported,
not silently equated or accepted as an improvement-admissibility policy.
"""
    fde = equations()
    expected, order = index(support, support=True, fde=fde)
    author_index, _ = index(author, support=False, fde=fde)
    candidate_index, _ = index(candidate, support=False, fde=fde)
    compare_support(expected, author_index, "author")
    compare_support(expected, candidate_index, "candidate")
    # Reorder observations before arithmetic so traversal differences cannot
    # produce spurious presentation or summation differences between bundles.
    def ordered_bundle(items):
        units = []
        for key in order:
            unit = items[key]["unit"]
            rows = {(row["trial_id"], row["frame_id"]): row for row in unit["observations"]}
            units.append({**unit, "observations": [rows[k] for k in expected[key]["rows"]]})
        return {"schema": "npvc-fde-operands-v1", "units": units}
    scored_author = fde.score(ordered_bundle(author_index))
    scored_candidate = fde.score(ordered_bundle(candidate_index))
    rows = []
    for key, left, right in zip(order, scored_author["units"], scored_candidate["units"]):
        model_rows = {}
        for model in ("npvc", "glm"):
            a, c = left[model], right[model]
            delta = None if a["fde"] is None or c["fde"] is None else fde.finite(c["fde"] - a["fde"], "FDE difference")
            model_rows[model] = {
                "author": a, "candidate": c,
                "candidate_minus_author_fde": delta,
                "difference_state": "undefined_operand" if delta is None else "finite",
                "null_log_likelihood_total_differs": a["log_likelihood_totals"]["null"] != c["log_likelihood_totals"]["null"],
                "saturated_log_likelihood_total_differs": a["log_likelihood_totals"]["saturated"] != c["log_likelihood_totals"]["saturated"],
            }
        rows.append({"identity": dict(zip(IDENTITY_FIELDS, key)),
                     "observations": len(expected[key]["rows"]),
                     "fold_ids_present": sorted({v[0] for v in expected[key]["rows"].values()}),
                     "trial_types_present": sorted({v[1] for v in expected[key]["rows"].values()}),
                     "models": model_rows})
    return {
        "schema": "npvc-paired-support-report-v1",
        "support_status": "all_declared_units_and_observations_paired",
        "source_membership_authenticated": False,
        "historical_split_authenticated": False,
        "density_admissibility": "unresolved",
        "complete_source_cohort": None,
        "paper_win": None,
        "scientific_outcome": "unknown",
        "readiness_promoted": False,
        "equations_sha256": EQUATIONS_SHA256,
        "units": rows,
        "recomputed_author": scored_author,
        "recomputed_candidate": scored_candidate,
        "scope": "Declared-support correspondence and source-equation arithmetic only; no pooled statistic, favorable subset, significance test, full-panel superiority policy or scientific admission.",
    }


def read_json(path):
    fde = equations()
    with path.open("rb") as stream:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    require(len(raw) <= MAX_INPUT_BYTES, "input exceeds 64 MiB per-file component limit")
    value = json.loads(raw, object_pairs_hook=fde.unique_object,
                       parse_constant=lambda _: (_ for _ in ()).throw(Invalid("nonfinite JSON")))
    return value, {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def run(support_path, author_path, candidate_path, output_path):
    require(not output_path.exists(), "fresh output destination required")
    documents, pins = {}, {}
    for role, path in (("support", support_path), ("author", author_path), ("candidate", candidate_path)):
        documents[role], pins[role] = read_json(path)
    result = compare(**documents)
    result["input_pins"] = pins
    with output_path.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("support", "author", "candidate", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    try:
        run(args.support, args.author, args.candidate, args.output)
    except (ValueError, OSError, TypeError, KeyError, OverflowError) as exc:
        parser.exit(2, str(exc) + "\n")
