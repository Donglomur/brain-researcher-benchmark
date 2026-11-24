"""Replay the retained first-experiment decoder scores, without fitting."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

SOURCE_COMMIT = "130f5e64f86bd63980f70bb839c02cd264782aef"
SOURCE_DECODER_SHA256 = "c1b9008ecdd5d2c6bbd5c10b93e0285e4f7baf4fe1fff0ba77b1c4e6428e3179"
EXCLUDED_VARIABLES = {"trial_nr", "reward_duration", "saccade_amplitude",
                      "condition_code", "past_condition", "past_C", "C_location"}


class ReplayError(ValueError):
    """The supplied source export is incomplete, ambiguous or inconsistent."""


def require(condition, message):
    if not condition:
        raise ReplayError(message)


def number(value, name):
    require(type(value) in (int, float) and math.isfinite(value), name + " must be finite numeric")
    return value


def vector(value, name, allow_empty=False):
    require(isinstance(value, list) and (allow_empty or bool(value)), name + " must be a list of required extent")
    return [number(x, name) for x in value]


def labels(value, name):
    require(isinstance(value, list) and bool(value), name + " must be a nonempty list")
    require(all(type(x) is str and x.strip() for x in value), name + " must contain strings")
    require(len(value) == len(set(value)), name + " contains duplicates")
    return value


def indices(value, name, maximum=None, allow_empty=False):
    result = vector(value, name, allow_empty)
    require(all(type(x) is int and x > 0 for x in result), name + " must be positive integer indices")
    require(result == sorted(set(result)), name + " must preserve unique source order")
    require(maximum is None or not result or result[-1] <= maximum, name + " contains unknown trial indices")
    return result


def matrix(value, rows, cols, name):
    require(isinstance(value, list) and len(value) == rows, name + " row count differs")
    result = [vector(row, name) for row in value]
    require(all(len(row) == cols for row in result), name + " column count differs")
    return result


def key(cell):
    require(isinstance(cell, dict), "cell must be an object")
    result = (cell.get("monkey"), cell.get("cell_id"))
    require(all(type(x) is str and x.strip() for x in result), "missing monkey/cell identity")
    return result


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def weighted_accuracy(target, prediction, weights):
    """Source sum(weight * equality), with source-normalized trial weights."""
    target = vector(target, "target")
    prediction = vector(prediction, "prediction")
    weights = vector(weights, "trial weights")
    require(len(target) == len(prediction) == len(weights), "trial lengths differ")
    require(all(w > 0 for w in weights), "trial weights must be positive")
    require(math.isclose(math.fsum(weights), 1.0, rel_tol=1e-12, abs_tol=1e-12),
            "source trial weights must already sum to one")
    return math.fsum(w for y, p, w in zip(target, prediction, weights) if y == p)


def replay(document, candidate=None):
    require(isinstance(document, dict), "export must be an object")
    require(document.get("schema") == "dentate-decoder-score-export-v1", "wrong export schema")
    require(document.get("source_commit") == SOURCE_COMMIT, "wrong source commit")
    require(document.get("source_decoder_sha256") == SOURCE_DECODER_SHA256, "wrong decoder hash")
    cfg = document.get("configuration")
    require(isinstance(cfg, dict), "missing configuration")
    for field, expected in (("n_cv_folds", 3), ("requested_n_shuffles", 50),
                            ("time_bin_ms", 200), ("minimum_trials", 10)):
        require(type(cfg.get(field)) is int and cfg[field] == expected, "wrong pinned configuration: " + field)
    variables = labels(cfg.get("behavior_variables"), "behavior variables")
    require(not set(variables) & EXCLUDED_VARIABLES, "variable excluded by this pinned decoder")
    events = labels(cfg.get("behavior_events"), "behavior events")
    require(all(not event.endswith("_stop") for event in events), "stop event excluded by pinned decoder")
    cells = document.get("cells")
    require(isinstance(cells, list) and bool(cells), "missing source cells")
    seen, reports, exclusions = set(), [], []
    support = {}
    for cell in cells:
        cell_key = key(cell)
        require(cell_key not in seen, "duplicate cell identity")
        seen.add(cell_key)
        selected = indices(cell.get("selected_prefiltered_trial_indices"), "prefiltered trial indices", allow_empty=True)
        trial_numbers = vector(cell.get("source_trial_numbers"), "source trial numbers", allow_empty=True)
        require(len(trial_numbers) == len(set(trial_numbers)) == len(selected), "invalid source trial mapping")
        if cell.get("status") == "insufficient_cell_trials":
            require(len(selected) < cfg["minimum_trials"], "incorrect insufficient-cell exclusion")
            exclusions.append({"monkey": cell_key[0], "cell_id": cell_key[1],
                               "status": cell["status"], "n_trials": len(selected)})
            continue
        require(cell.get("status") == "fitted", "unknown cell status")
        require(len(selected) >= cfg["minimum_trials"], "fitted cell below source trial minimum")
        groups = cell.get("groups")
        require(isinstance(groups, list) and bool(groups), "missing decoder groups")
        expected_groups = {name: [] for name in variables}
        for group in groups:
            require(isinstance(group, dict), "group must be an object")
            variable = group.get("variable")
            require(variable in expected_groups, "unknown decoder variable")
            unfitted = group.get("status") == "insufficient_group_trials"
            values = vector(group.get("values"), "decoded values", allow_empty=unfitted)
            require(values == sorted(set(values)) and (len(values) >= 2 or (unfitted and not values)),
                    "invalid decoded value set")
            subgroup = group.get("subgroup_index")
            require(type(subgroup) is int and subgroup == len(expected_groups[variable]) + 1,
                    "subgroups must preserve complete source order per variable")
            require(not any(set(values) & set(previous) for previous in expected_groups[variable]),
                    "overlapping decoded-value subgroups")
            expected_groups[variable].append(values)
            trial_indices = indices(group.get("selected_experiment_trial_indices"),
                                    "group trial indices", len(selected), allow_empty=unfitted)
            target = vector(group.get("target"), "target", allow_empty=unfitted)
            weights = vector(group.get("trial_weights"), "trial weights", allow_empty=unfitted)
            require(len(target) == len(weights) == len(trial_indices), "group trial lengths differ")
            require(set(target) == set(values), "target values differ from group values")
            if target:
                weighted_accuracy(target, target, weights)
            if group.get("status") == "insufficient_group_trials":
                require(len(target) < cfg["minimum_trials"], "incorrect insufficient-group exclusion")
                require(group.get("models") == [], "unfitted group has model outputs")
                exclusions.append({"monkey": cell_key[0], "cell_id": cell_key[1],
                                   "variable": variable, "values": values, "subgroup_index": subgroup,
                                   "status": group["status"],
                                   "n_trials": len(target)})
                continue
            require(group.get("status") == "fitted", "unknown group status")
            require(len(target) >= cfg["minimum_trials"], "fitted group below source trial minimum")
            models = group.get("models")
            require(isinstance(models, list) and len(models) == len(events), "incomplete event models")
            event_seen = set()
            for model in models:
                require(isinstance(model, dict), "model must be an object")
                event = model.get("alignment")
                require(event in events and event not in event_seen, "unknown or repeated event model")
                event_seen.add(event)
                times = vector(model.get("aligned_time_ms"), "aligned time")
                require(times == sorted(set(times)), "time coordinates must preserve source order")
                require(all(math.isclose(b - a, cfg["time_bin_ms"], rel_tol=0, abs_tol=1e-9)
                            for a, b in zip(times, times[1:])), "time coordinates do not retain source bin width")
                predictions = matrix(model.get("first_experiment_prediction"), len(target), len(times),
                                     "first experiment predictions")
                require(all(p in values for row in predictions for p in row), "unknown predicted label")
                accuracies = model.get("retained_accuracy")
                require(isinstance(accuracies, list) and bool(accuracies)
                        and isinstance(accuracies[0], list) and len(accuracies[0]) >= 2,
                        "missing retained permutation accuracy columns")
                accuracies = matrix(accuracies, len(times), len(accuracies[0]), "retained accuracy")
                require(all(0 <= a <= 1 for row in accuracies for a in row), "accuracy outside [0,1]")
                replayed = [weighted_accuracy(target, [row[i] for row in predictions], weights)
                            for i in range(len(times))]
                require(all(math.isclose(a, row[0], rel_tol=1e-10, abs_tol=1e-10)
                            for a, row in zip(replayed, accuracies)), "first-experiment accuracy does not replay")
                family_key = (*cell_key, variable, tuple(values), event)
                descriptor = {"monkey": cell_key[0], "cell_id": cell_key[1], "variable": variable,
                              "values": values, "alignment": event, "aligned_time_ms": times,
                              "source_trial_numbers": [trial_numbers[i - 1] for i in trial_indices],
                              "target": target, "trial_weights": weights}
                support_hash = digest(descriptor)
                support[family_key] = (support_hash, descriptor)
                reports.append({"monkey": cell_key[0], "cell_id": cell_key[1], "variable": variable,
                                "values": values, "alignment": event, "aligned_time_ms": times,
                                "n_trials": len(target), "support_sha256": support_hash,
                                "first_experiment_accuracy": replayed,
                                "retained_accuracy_column_count": len(accuracies[0]),
                                "remaining_accuracy_columns_replayed": False})
        require(all(expected_groups.values()), "missing behavior-variable group")
    require(bool(reports), "no fitted model outputs to replay")
    if candidate is not None:
        require(isinstance(candidate, dict) and candidate.get("schema") == "dentate-decoder-predictions-v1",
                "wrong candidate schema")
        rows = candidate.get("models")
        require(isinstance(rows, list), "candidate models must be a list")
        lookup = {}
        for row in rows:
            cell_key = key(row)
            values = vector(row.get("values"), "candidate values")
            family_key = (*cell_key, row.get("variable"), tuple(values), row.get("alignment"))
            require(family_key in support and family_key not in lookup, "unknown or duplicate candidate model")
            lookup[family_key] = row
        require(set(lookup) == set(support), "candidate model support is incomplete")
        for report in reports:
            family_key = (*key(report), report["variable"], tuple(report["values"]), report["alignment"])
            row, (support_hash, descriptor) = lookup[family_key], support[family_key]
            require(row.get("support_sha256") == support_hash, "candidate support hash differs")
            require(row.get("aligned_time_ms") == descriptor["aligned_time_ms"], "candidate time coordinates differ")
            require(row.get("source_trial_numbers") == descriptor["source_trial_numbers"],
                    "candidate trial order differs")
            predictions = matrix(row.get("prediction"), len(descriptor["target"]),
                                 len(descriptor["aligned_time_ms"]), "candidate predictions")
            require(all(p in descriptor["values"] for values in predictions for p in values),
                    "candidate predicted unknown label")
            scores = [weighted_accuracy(descriptor["target"], [values[i] for values in predictions],
                                        descriptor["trial_weights"])
                      for i in range(len(descriptor["aligned_time_ms"]))]
            report["candidate_accuracy"] = scores
            report["candidate_minus_retained_first_experiment"] = [a - b for a, b in
                zip(scores, report["first_experiment_accuracy"])]
    return {"schema": "dentate-decoder-score-replay-report-v1", "models": reports,
            "source_exclusions": exclusions, "source_commit": SOURCE_COMMIT,
            "requested_n_shuffles": cfg["requested_n_shuffles"],
            "scope": "retained_first_experiment_prediction_replay_only",
            "permutation_predictions_available": False, "permutation_scores_replayed": False,
            "first_experiment_is_unshuffled_verified": False, "fit_recipe_verified": False,
            "original_folds_verified": False, "complete_original_cohort_verified": False,
            "paper_figure4_mapping_verified": False, "population_significance_fraction": None,
            "paper_reproduction_established": False, "paper_improvement_established": False}


def compare_conditions(document, paper_data, paper_data_author_code):
    """Pair both candidate arms on every fitted model in one supplied export.

    Condition names are operator assignments, not verified exposure provenance.
    Accuracy differences retain model/time axes; no population scalar is defined.
    """
    require(paper_data is not None and paper_data_author_code is not None,
            "both information-condition predictions are required")
    data_report = replay(document, paper_data)
    code_report = replay(document, paper_data_author_code)
    reports = []
    for data, code in zip(data_report["models"], code_report["models"]):
        # Both replays enumerate the same source export, independent of submission order.
        model = {name: value for name, value in data.items()
                 if name not in ("candidate_accuracy", "candidate_minus_retained_first_experiment")}
        model["condition_scores"] = {
            "paper_data": {
                "accuracy": data["candidate_accuracy"],
                "minus_retained_first_experiment": data["candidate_minus_retained_first_experiment"],
            },
            "paper_data_author_code": {
                "accuracy": code["candidate_accuracy"],
                "minus_retained_first_experiment": code["candidate_minus_retained_first_experiment"],
            },
        }
        model["paper_data_author_code_minus_paper_data"] = [
            code_score - data_score for data_score, code_score in
            zip(data["candidate_accuracy"], code["candidate_accuracy"])]
        reports.append(model)
    return {**data_report, "schema": "dentate-decoder-paired-conditions-report-v1",
            "models": reports,
            "information_conditions": ["paper_data", "paper_data_author_code"],
            "comparison_scope": "complete_supplied_decoder_support_per_model_per_time",
            "information_condition_assignment_verified": False,
            "condition_resource_exposure_comparability_verified": False}


def read_json(path):
    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, "duplicate JSON key: " + k)
            result[k] = v
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ReplayError("nonfinite JSON")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--author-export", required=True)
    parser.add_argument("--candidate")
    parser.add_argument("--paper-data", help="Predictions assigned to the paper+data condition")
    parser.add_argument("--paper-data-author-code", help="Predictions assigned to the paper+data+code condition")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    paired = args.paper_data is not None or args.paper_data_author_code is not None
    if paired and (args.paper_data is None or args.paper_data_author_code is None):
        parser.error("--paper-data and --paper-data-author-code must be supplied together")
    if paired and args.candidate is not None:
        parser.error("--candidate cannot be combined with paired information-condition inputs")
    sources = {"author_export": Path(args.author_export).resolve()}
    if paired:
        sources.update(paper_data=Path(args.paper_data).resolve(),
                       paper_data_author_code=Path(args.paper_data_author_code).resolve())
    elif args.candidate is not None:
        sources["candidate"] = Path(args.candidate).resolve()
    output = Path(args.output).resolve()
    require(output not in sources.values(), "output cannot overwrite an input")
    document = read_json(sources["author_export"])
    if paired:
        result = compare_conditions(document, read_json(sources["paper_data"]),
                                    read_json(sources["paper_data_author_code"]))
    else:
        result = replay(document, read_json(sources["candidate"]) if "candidate" in sources else None)
    for name, path in sources.items():
        result[name + "_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    with output.open("x") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
