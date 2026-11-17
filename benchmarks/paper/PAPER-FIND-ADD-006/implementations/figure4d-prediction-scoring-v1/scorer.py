"""Operator-only Figure 4D prediction scoring; no fitting or private-target loading.

The paper's binary normalized absolute error equals the mismatch rate. Report
that error AND its complement, without choosing a convention for the unresolved
published ordinate. Conditional scores weight conditioning groups equally.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

REPEATS = 100
REPEAT_LABELS = frozenset(str(i) for i in range(REPEATS))
ROSTER = {
    "jc233": ("170220", "180220", "190220", "200220", "210220"),
    "jc243": ("240820", "260820", "270820", "280820", "310820"),
    "jc250": ("010221", "020221", "030221", "050221", "060221"),
    "jc253": ("160321", "170321", "180321", "190321", "210321"),
    "jc259": ("210421", "220421", "230421", "240421", "260421"),
}
ARMS = ("global", "global_context_shuffle", "conditional",
        "conditional_context_shuffle", "conditional_position_shuffle")


class ScoreError(ValueError):
    """An export cannot be scored without changing its declared support."""


def require(condition, message):
    if not condition:
        raise ScoreError(message)


def symbols(values, name, size=None):
    require(isinstance(values, (list, tuple)) and len(values) > 0,
            f"{name} must be an explicit nonempty list")
    require(all(type(x) is str and x and x == x.strip() for x in values),
            f"{name} must contain nonempty literal strings")
    require(len(set(values)) == len(values), f"duplicate {name}")
    require(size is None or len(values) == size, f"{name} requires {size} labels")
    return tuple(values)


def metrics(count, mismatches):
    if not count:
        return {"count": 0, "mismatches": 0, "exact_match_accuracy": None,
                "normalized_absolute_error": None}
    error = mismatches / count
    return {"count": count, "mismatches": mismatches,
            "exact_match_accuracy": 1.0 - error,
            "normalized_absolute_error": error}


def score_rows(rows, *, context_labels, condition_labels, condition_column,
               aggregation, selectors=None):
    """Score literal author export fields, retaining bootstrap multiplicities.

    No row identifier is inferred from CSV ordering. Boot_rep is a repetition
    number, not evidence that two exports share sampled PV identities.
    """
    context_labels = symbols(context_labels, "context_labels", 2)
    condition_labels = symbols(condition_labels, "condition_labels")
    require(type(condition_column) is str and bool(condition_column),
            "condition_column must name an explicit actual-position field")
    require(condition_column not in {"Real_label", "Pred_label", "Boot_rep"},
            "condition_column cannot be a target, prediction or repetition field")
    require(aggregation in {"global", "conditional"}, "unknown aggregation")
    selectors = {} if selectors is None else selectors
    require(type(selectors) is dict and all(type(k) is str and k and
            type(v) is str and v for k, v in selectors.items()),
            "selectors must map column names to literal strings")
    require(not (set(selectors) & {"Real_label", "Pred_label", "Boot_rep", condition_column}),
            "selectors cannot narrow targets, predictions, repeats or conditions")
    counts = [{label: [0, 0] for label in condition_labels} for _ in range(REPEATS)]
    selected = skipped = 0
    required = {"Real_label", "Pred_label", "Boot_rep", condition_column} | set(selectors)
    for line, row in enumerate(rows, 2):
        require(type(row) is dict and required <= set(row), f"row {line}: missing required fields")
        require(None not in row and all(value is not None for value in row.values()),
                f"row {line}: inconsistent CSV field count")
        if any(row[key] != value for key, value in selectors.items()):
            skipped += 1
            continue
        real, predicted = row["Real_label"], row["Pred_label"]
        condition, rep_text = row[condition_column], row["Boot_rep"]
        require(real in context_labels and predicted in context_labels,
                f"row {line}: missing or nonbinary context label")
        require(condition in condition_labels, f"row {line}: undeclared condition label")
        require(type(rep_text) is str and rep_text in REPEAT_LABELS,
                f"row {line}: Boot_rep must be a canonical integer in 0..99")
        count = counts[int(rep_text)][condition]
        count[0] += 1
        count[1] += int(real != predicted)
        selected += 1
    require(selected > 0, "no selected prediction rows")
    results = []
    for rep, by_condition in enumerate(counts):
        groups = [{"condition": label, **metrics(*by_condition[label])}
                  for label in condition_labels]
        count = sum(group["count"] for group in groups)
        require(count > 0, f"missing complete bootstrap repetition {rep}")
        pooled = metrics(count, sum(group["mismatches"] for group in groups))
        missing = [group["condition"] for group in groups if group["count"] == 0]
        # Missing groups cannot silently change the source equal-group estimand.
        group_error = (None if missing else math.fsum(
            group["normalized_absolute_error"] for group in groups) / len(groups))
        error = pooled["normalized_absolute_error"] if aggregation == "global" else group_error
        results.append({"Boot_rep": rep, "count": count, "conditions": groups,
                        "missing_conditions": missing,
                        "exact_match_accuracy": None if error is None else 1.0 - error,
                        "normalized_absolute_error": error,
                        "pooled_observation_diagnostic": pooled,
                        "equal_condition_error_diagnostic": group_error})
    complete = all(row["normalized_absolute_error"] is not None for row in results)
    mean_error = (math.fsum(row["normalized_absolute_error"] for row in results) / REPEATS
                  if complete else None)
    return {
        "aggregation": aggregation, "selected_rows": selected, "selector_excluded_rows": skipped,
        "repetitions": results,
        "repeat_summary": {
            "role": "descriptive_equal_repeat_mean; published session aggregation remains unverified",
            "repeat_slots": REPEATS, "all_repeat_scores_defined": complete,
            "exact_match_accuracy": None if mean_error is None else 1.0 - mean_error,
            "normalized_absolute_error": mean_error,
        },
        "pairing_verified": False,
    }


def score_csv(path, **kwargs):
    """Read one author-style CSV; duplicate headers and padded rows are errors."""
    path = Path(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        require(fields is not None and len(fields) == len(set(fields)) and all(fields),
                "CSV must have unique nonempty column names")
        report = score_rows(reader, **kwargs)
    return report


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_manifest(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=_unique_object)


def score_panel(manifest, base_directory):
    """Require the complete original roster and source comparison arms.

    This is an operator diagnostic, not a candidate-facing grader: exports
    contain their own targets. No authenticity, paired-draw or improvement
    claim follows from successful scoring.
    """
    require(type(manifest) is dict and set(manifest) == {
        "schema", "context_labels", "condition_labels", "sessions"}, "unexpected panel fields")
    require(manifest["schema"] == "hierarchy-figure4d-export-panel/v1", "unknown panel schema")
    contexts = symbols(manifest["context_labels"], "context_labels", 2)
    conditions = symbols(manifest["condition_labels"], "condition_labels")
    sessions = manifest["sessions"]
    require(type(sessions) is list and len(sessions) == 25, "all 25 source sessions required")
    expected = {(animal, date) for animal, dates in ROSTER.items() for date in dates}
    indexed = {}
    for session in sessions:
        require(type(session) is dict and set(session) == {"animal", "date", "exports"},
                "session needs animal, date, exports")
        require(type(session["animal"]) is str and type(session["date"]) is str,
                "literal source animal/date strings required")
        identity = (session["animal"], session["date"])
        require(identity in expected and identity not in indexed, "unknown or duplicate source session")
        require(type(session["exports"]) is dict and set(session["exports"]) == set(ARMS),
                "global/conditional and all three source shuffle controls required")
        indexed[identity] = session["exports"]
    require(set(indexed) == expected, "source session support changed")
    output = []
    # Refuse accidental reuse of one export/selector as multiple source arms or
    # sessions. Separate selectors in a combined author export remain allowed.
    used_exports = set()
    for animal, dates in ROSTER.items():
        for date in dates:
            reports = {}
            for arm in ARMS:
                spec = indexed[(animal, date)][arm]
                require(type(spec) is dict and set(spec) == {"path", "condition_column", "selectors"},
                        "each export needs path, condition_column, selectors")
                require(type(spec["path"]) is str and bool(spec["path"]), "export path required")
                require(type(spec["selectors"]) is dict, "selectors must be an object")
                path = (Path(base_directory) / spec["path"]).resolve(strict=True)
                signature = (str(path), json.dumps(spec["selectors"], sort_keys=True))
                require(signature not in used_exports, "same export/selector reused in the panel")
                used_exports.add(signature)
                reports[arm] = score_csv(
                    path, context_labels=contexts, condition_labels=conditions,
                    condition_column=spec["condition_column"], selectors=spec["selectors"],
                    aggregation="global" if arm.startswith("global") else "conditional")
            output.append({"animal": animal, "date": date, "arms": reports})
    return {
        "schema": "hierarchy-figure4d-prediction-diagnostics/v1",
        "task_id": "PAPER-FIND-ADD-006", "session_count": 25, "animal_count": 5,
        "context_labels": list(contexts), "declared_condition_labels": list(conditions),
        "sessions": output,
        "qualification": "operator_prediction_scoring_only",
        "published_metric_convention_selected": False,
        "condition_resolution_verified": False,
        "speed_equalization_verified": False,
        "paired_source_draws_verified": False,
        "cross_session_aggregate": None,
        "biological_uncertainty": None,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="operator-owned full25 export manifest")
    args = parser.parse_args(argv)
    try:
        report = score_panel(load_manifest(args.manifest), args.manifest.resolve().parent)
        print(json.dumps(report, indent=2, allow_nan=False))
    except (ScoreError, OSError, csv.Error, UnicodeError, json.JSONDecodeError) as exc:
        parser.exit(2, f"scorer: {exc}\n")


if __name__ == "__main__":
    main()
