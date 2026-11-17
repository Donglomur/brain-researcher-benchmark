"""PAPER-FIND-004: safe native-prediction scoring and regional null inference.

This module does not load pickle, fit a model, generate pseudo-sessions, or claim
authentic reproduction. Source semantics and remaining gates are in provenance.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

TASK_ID = "PAPER-FIND-004"
SOURCE_REVISION = "380e7e68f31f9b55ec20e3f4863abec9eec25d30"
CONTRACT_SHA256 = "ac5ceceab1a9d99e37d891694395298a8f6da246f67cbe6ba982083174e255f8"
SOURCE_PROTOCOL = {
    "release": "2023_12_bwm_release",
    "source_revision": SOURCE_REVISION,
    "model": "optBay",
    "target": "pLeft",
    "align_event": "stimOn_times",
    "time_window_seconds": [-0.6, -0.1],
    "min_reaction_time_seconds": 0.08,
    "max_reaction_time_seconds": None,
    "exclude_nochoice": True,
    "exclude_unbiased": False,
    "region_mapping": "Beryl",
    "unit_qc": 1,
    "loader_min_units": 10,
    "estimator": "Ridge",
    "balanced_weighting": True,
    "native_sklearn_hyperparameter_estimation": True,
    "alpha_grid": [0.00001, 0.0001, 0.001, 0.01, 0.1],
    "shuffle": True,
    "outer_folds": 50,
    "runs": 10,
    "pseudo_sessions": 200,
}
MOTOR_FEATURES = [
    "normalized_absolute_wheel_velocity", "binned_lick_count",
    "left_nose_tip_x", "left_whisker_motion_energy",
    "right_whisker_motion_energy", "left_paw_position_norm",
    "right_paw_position_norm",
]
GATES = [
    "Pinned generic script defaults differ materially from journal methods; paper protocol reconciliation is open.",
    "Authentic release/session/probe/cluster selection and input byte receipts are not independently qualified.",
    "Native Bayesian targets, pseudo-session generation, fitting and source parity require authentic execution.",
    "Exported predictions and declared fold lineage are evidence supplied by the operator, not proof of training isolation.",
    "Protected assessment, public exposure exclusions, data/stimulus rights and submission packets remain unqualified.",
    "Paper-wide coverage, widefield mapping, reference targets/tolerances and meaningful difficulty remain unqualified.",
    "Source within-session trial CV is not a mouse/session-held-out improvement or independent biological replication.",
    "Movement comparison is descriptive; decodability and neural-minus-motor R-squared are not causal attribution.",
]


class EvaluationError(ValueError):
    """Malformed, incomplete, or semantically incompatible evidence."""


def require(condition, message):
    if not condition:
        raise EvaluationError(message)


def digest(value):
    """Digest of UTF-8 JSON with sorted keys, compact separators, no NaN."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def finite_vector(values, name):
    require(isinstance(values, list) and len(values) >= 2, f"{name}: at least two values required")
    require(all(type(x) in (int, float) and math.isfinite(x) for x in values),
            f"{name}: finite numbers required")
    return values


def pooled_r2(target, prediction):
    """sklearn R² for nonconstant scalar targets, pooled across all outer folds.

    Degenerate constant targets are rejected, rather than hiding undefined science
    behind sklearn's version-dependent force_finite substitution.
    """
    target = finite_vector(target, "target")
    prediction = finite_vector(prediction, "prediction")
    require(len(target) == len(prediction), "target/prediction length mismatch")
    mean = statistics.fmean(target)
    denominator = math.fsum((x - mean) ** 2 for x in target)
    require(denominator > 0, "constant target has undefined R-squared")
    return 1.0 - math.fsum((x - y) ** 2 for x, y in zip(target, prediction)) / denominator


def session_statistics(actual_runs, pseudo_runs):
    """Stage 2: mean runs first; one pseudo session is one null draw."""
    finite_vector(actual_runs, "actual run scores")
    require(isinstance(pseudo_runs, list) and pseudo_runs, "pseudo sessions required")
    for scores in pseudo_runs:
        finite_vector(scores, "pseudo run scores")
        require(len(scores) == len(actual_runs), "unequal repeat counts")
    actual = statistics.fmean(actual_runs)
    null = [statistics.fmean(scores) for scores in pseudo_runs]
    return {
        "score": actual,
        "median_null": statistics.median(null),
        "p_value": (1 + sum(x >= actual for x in null)) / (len(null) + 1),
        "n_pseudo": len(null),
    }


def fisher_combined(pvalues):
    """Fisher upper tail, using the exact finite sum for even chi-square df."""
    require(pvalues and all(type(p) in (int, float) and math.isfinite(p) and 0 < p <= 1
                            for p in pvalues), "Fisher requires p in (0, 1]")
    s = -math.fsum(math.log(p) for p in pvalues)
    if s == 0:
        return 1.0
    logs = [j * math.log(s) - math.lgamma(j + 1) for j in range(len(pvalues))]
    top = max(logs)
    return min(1.0, math.exp(-s + top) * math.fsum(math.exp(x - top) for x in logs))


def benjamini_hochberg(pvalues):
    require(all(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1 for p in pvalues),
            "BH requires p in [0, 1]")
    order = sorted(range(len(pvalues)), key=pvalues.__getitem__)
    out = [0.0] * len(order)
    running = 1.0
    for i in range(len(order) - 1, -1, -1):
        running = min(running, pvalues[order[i]] * len(order) / (i + 1))
        out[order[i]] = running
    return out


def region_statistics(sessions):
    """Stage 3 source filters and summaries; all declared regions stay visible."""
    groups = defaultdict(list)
    for row in sessions:
        groups[row["region"]].append(row)
    result = []
    for region, rows in sorted(groups.items()):
        included = [r for r in rows if r["n_units"] >= 5 and r["n_trials"] >= 250]
        item = {"region": region, "n_sessions": len(included),
                "excluded_sessions": [{"subject": r["subject"], "eid": r["eid"],
                                       "reason": "stage3_min_units_or_trials"}
                                      for r in rows if r not in included]}
        if len(included) < 2:
            item.update({"status": "insufficient_sessions", "combined_p": None,
                         "corrected_p": None, "significant_fdr": False})
        else:
            scores = [r["score"] for r in included]
            pvalues = [r["p_value"] for r in included]
            null = [r["median_null"] for r in included]
            significant_scores = [s for s, p in zip(scores, pvalues) if p < .05]
            item.update({
                "status": "evaluated", "combined_p": fisher_combined(pvalues),
                "n_units_mean": statistics.fmean(r["n_units"] for r in included),
                "values_std": statistics.pstdev(scores),
                "values_median": statistics.median(scores),
                "null_median_of_medians": statistics.median(null),
                "valuesminusnull_median": statistics.median(scores) - statistics.median(null),
                "fraction_significant_sessions": statistics.fmean(p < .05 for p in pvalues),
                "values_median_significant": statistics.median(significant_scores) if significant_scores else None,
            })
        result.append(item)
    valid = [r for r in result if r["combined_p"] is not None]
    for row, corrected in zip(valid, benjamini_hochberg([r["combined_p"] for r in valid])):
        row["corrected_p"] = corrected
        row["significant_fdr"] = corrected < .01
    return result


def cell_key(cell):
    require(isinstance(cell, dict), "cell must be an object")
    fields = ("subject", "eid", "region", "predictor")
    require(all(isinstance(cell.get(k), str) and cell[k] for k in fields), "missing cell identity")
    require(cell["predictor"] in ("neural", "motor"), "unsupported predictor")
    return tuple(cell[k] for k in fields)


def check_sha(value, name):
    require(isinstance(value, str) and len(value) == 64 and
            all(c in "0123456789abcdef" for c in value), f"{name}: lowercase SHA-256 required")


def check_folds(assignments, n_trials):
    """Compact native KFold partition: each trial's test fold, train=complement.

    This validates the supplied partition, not that a model obeyed it. The safe
    native adapter below additionally checks original train/test index arrays.
    """
    n_folds = SOURCE_PROTOCOL["outer_folds"]
    require(isinstance(assignments, list) and len(assignments) == n_trials,
            "one held-out fold assignment per trial required")
    require(all(type(f) is int and 0 <= f < n_folds for f in assignments), "invalid held-out fold ID")
    counts = [assignments.count(f) for f in range(n_folds)]
    require(min(counts) > 0 and max(counts) - min(counts) <= 1,
            "source default requires 50 balanced outer folds")


def native_integer(value, name):
    """Normalize NumPy-like integer scalars only at the trusted native boundary."""
    if hasattr(value, "item"):
        value = value.item()
    require(type(value) is int, f"native {name} must be an integer scalar")
    return value


def export_native_run(fit):
    """Convert one already-loaded trusted native fit dictionary to safe JSON data.

    Never unpickles. The caller controls any native loading outside this package.
    One scalar prior/prediction per trial is required; time-binned targets are not
    silently flattened into a different estimand. Native arrays may use tolist().
    """
    def plain(value):
        return value.tolist() if hasattr(value, "tolist") else value

    def scalars(values):
        result = []
        for value in plain(values):
            value = plain(value)
            require(isinstance(value, (list, tuple)) and len(value) == 1,
                    "native prior export requires exactly one scalar per trial")
            result.append(value[0])
        return result

    target = scalars(fit["target"])
    prediction = scalars(fit["predictions_test"])
    score = pooled_r2(target, prediction)
    require(math.isclose(score, fit["scores_test_full"], rel_tol=1e-10, abs_tol=1e-12),
            "native reported score disagrees with pooled prediction score")
    tests = plain(fit["idxes_test"])
    trains = plain(fit["idxes_train"])
    require(len(tests) == len(trains) == SOURCE_PROTOCOL["outer_folds"], "wrong native fold count")
    assignment = [-1] * len(target)
    universe = set(range(len(target)))
    for fold_id, (train, test) in enumerate(zip(trains, tests)):
        train, test = plain(train), plain(test)
        require(all(type(i) is int for i in train + test), "native indices must be integers")
        require(len(set(train)) == len(train) and len(set(test)) == len(test), "duplicate native indices")
        require(set(test) <= universe and set(train) == universe - set(test), "native train is not test complement")
        for i in test:
            require(assignment[i] == -1, "native trial appears in multiple test folds")
            assignment[i] = fold_id
    check_folds(assignment, len(target))
    return target, {"pseudo_id": native_integer(fit["pseudo_id"], "pseudo_id"),
                    "run_id": native_integer(fit["run_id"], "run_id"),
                    "predictions": prediction, "test_fold": assignment}


def export_native_ephys(native, trial_ids_by_pseudo, *, input_objects_sha256,
                        target_generator_sha256):
    """Convert a trusted single-Beryl-region native result without loading files.

    Explicit per-pseudo trial IDs must be derived from original trial identities
    and the corresponding pseudo mask, not from the native stage1 mask[0] shortcut.
    This version rejects changing masks; it never silently intersects populations.
    """
    require(isinstance(native.get("region"), list) and len(native["region"]) == 1,
            "one Beryl region required; composite region groups are outside scope")
    required = {str(p) for p in [-1, *range(1, 201)]}
    require(isinstance(trial_ids_by_pseudo, dict) and set(trial_ids_by_pseudo) == required,
            "explicit trial IDs for every real/pseudo mask required")
    trials = trial_ids_by_pseudo["-1"]
    require(all(ids == trials for ids in trial_ids_by_pseudo.values()),
            "varying real/pseudo masks are outside this component scope")
    targets, runs = {}, []
    for fit in native["fit"]:
        target, run = export_native_run(fit)
        key = str(run["pseudo_id"])
        require(key in required, "unknown native pseudo ID")
        require(len(target) == len(trials), "native target differs from retained trial identity count")
        require(key not in targets or targets[key] == target, "target changes across repeated fits")
        targets[key] = target
        runs.append(run)
    cell = {"subject": native["subject"], "eid": native["eid"], "region": native["region"][0],
            "predictor": "neural", "n_units": native_integer(native["N_units"], "N_units"), "trial_ids": trials,
            "input_objects_sha256": input_objects_sha256,
            "target_generator_sha256": target_generator_sha256, "targets": targets, "runs": runs}
    expected = {k: cell[k] for k in ("subject", "eid", "region", "predictor", "n_units", "trial_ids",
                                    "input_objects_sha256", "target_generator_sha256")}
    expected["targets_sha256"] = digest(targets)
    evaluate_cell(cell, expected)
    return cell


def evaluate_cell(cell, expected):
    require(cell_key(cell) == cell_key(expected), "cell identity mismatch")
    for field in ("n_units", "trial_ids", "input_objects_sha256", "target_generator_sha256"):
        require(cell.get(field) == expected.get(field), f"cell {field} differs from frozen manifest")
    trials = cell["trial_ids"]
    require(isinstance(trials, list) and len(trials) >= 50 and
            all(isinstance(t, str) and t for t in trials) and len(set(trials)) == len(trials),
            "unique trial IDs for all source outer folds required")
    require(type(cell["n_units"]) is int and cell["n_units"] >= 1, "invalid feature/unit count")
    if cell["predictor"] == "neural":
        require(cell["n_units"] >= SOURCE_PROTOCOL["loader_min_units"], "below pinned loader unit minimum")
        require(cell["region"] not in ("root", "void"), "non-anatomical Beryl region")
    else:
        require(cell["n_units"] == 7 and cell.get("feature_names") == MOTOR_FEATURES,
                "motor comparator must preserve all seven source features")
    for field in ("input_objects_sha256", "target_generator_sha256"):
        check_sha(cell[field], field)
    targets = cell.get("targets", {})
    required_ids = {-1, *range(1, SOURCE_PROTOCOL["pseudo_sessions"] + 1)}
    require(isinstance(targets, dict) and set(targets) == {str(p) for p in required_ids},
            "complete real and 200 pseudo targets required")
    for target in targets.values():
        finite_vector(target, "prior target")
        require(len(target) == len(trials) and all(0 <= p <= 1 for p in target), "invalid prior target")
    require(digest(targets) == expected.get("targets_sha256"), "targets differ from frozen manifest")
    require(isinstance(cell.get("runs"), list), "runs must be a list")
    scores = defaultdict(dict)
    required_runs = set(range(SOURCE_PROTOCOL["runs"]))
    for run in cell["runs"]:
        require(isinstance(run, dict), "run must be an object")
        pseudo, repeat = run.get("pseudo_id"), run.get("run_id")
        require(type(pseudo) is int and pseudo in required_ids and type(repeat) is int and repeat in required_runs,
                "unknown pseudo or run ID")
        require(repeat not in scores[pseudo], "duplicate pseudo/run result")
        check_folds(run.get("test_fold"), len(trials))
        scores[pseudo][repeat] = pooled_r2(targets[str(pseudo)], run.get("predictions"))
    require(set(scores) == required_ids and all(set(runs) == required_runs for runs in scores.values()),
            "incomplete pseudo-session by repeat grid")
    ordered = lambda p: [scores[p][r] for r in sorted(required_runs)]
    summary = session_statistics(ordered(-1), [ordered(p) for p in sorted(required_ids - {-1})])
    summary.update({k: cell[k] for k in ("subject", "eid", "region", "predictor", "n_units")})
    summary.update({"n_trials": len(trials), "runs": len(required_runs),
                    "actual_target_sha256": digest(targets["-1"]),
                    "trial_ids_sha256": digest(trials)})
    return summary


def compare_movement(summaries):
    """Exact matched-trial comparisons; no intersection or resampling is implicit."""
    by_key = {tuple(r[k] for k in ("subject", "eid", "region", "predictor")): r for r in summaries}
    comparisons = []
    for key, neural in sorted(by_key.items()):
        if key[-1] != "neural":
            continue
        motor = by_key.get(key[:-1] + ("motor",))
        require(motor is not None, "missing region-matched motor comparator")
        require(neural["trial_ids_sha256"] == motor["trial_ids_sha256"] and
                neural["actual_target_sha256"] == motor["actual_target_sha256"],
                "neural/motor histories or retained trial identities differ")
        comparisons.append({"subject": key[0], "eid": key[1], "region": key[2],
                            "neural_r2": neural["score"], "motor_r2": motor["score"],
                            "neural_minus_motor_r2": neural["score"] - motor["score"],
                            "neural_null_p": neural["p_value"], "motor_null_p": motor["p_value"]})
    return comparisons


def evaluate(manifest, payload):
    require(isinstance(manifest, dict) and isinstance(payload, dict), "manifest and predictions must be objects")
    require(manifest.get("task_id") == TASK_ID and manifest.get("contract_sha256") == CONTRACT_SHA256,
            "wrong task contract")
    require(digest(manifest.get("protocol")) == digest(SOURCE_PROTOCOL),
            "only the explicitly pinned native default protocol is supported")
    require(manifest.get("evidence_kind") in ("generated_engineering_control", "native_prediction_export"),
            "evidence kind must distinguish generated control from native export")
    require(manifest.get("population_scope") == "declared_subset_not_paperwide", "paper-wide coverage has not been qualified")
    for field in ("population_manifest_sha256", "exposure_policy_sha256"):
        check_sha(manifest.get(field), field)
    require(digest(payload) == manifest.get("prediction_payload_sha256"), "prediction payload digest mismatch")
    expected = manifest.get("expected_cells")
    cells = payload.get("cells")
    require(isinstance(expected, list) and expected and isinstance(cells, list), "nonempty frozen cell roster required")
    expected_keys = [cell_key(c) for c in expected]
    actual_keys = [cell_key(c) for c in cells]
    require(len(set(expected_keys)) == len(expected_keys) and len(set(actual_keys)) == len(actual_keys), "duplicate cell")
    require(set(actual_keys) == set(expected_keys), "cell population differs from frozen roster")
    exposed = manifest.get("excluded_exposed_subjects")
    require(isinstance(exposed, list) and all(isinstance(s, str) and s for s in exposed), "explicit exposed-subject exclusions required")
    require(not (set(exposed) & {k[0] for k in actual_keys}), "excluded exposed subject appears in evaluation")
    # An eid has a single biological owner; duplicated names cannot inflate the session count.
    ownership = {}
    for subject, eid, _, _ in actual_keys:
        require(eid not in ownership or ownership[eid] == subject, "session assigned to multiple subjects")
        ownership[eid] = subject
    lookup = dict(zip(expected_keys, expected))
    summaries = [evaluate_cell(c, lookup[cell_key(c)]) for c in cells]
    comparisons = compare_movement(summaries)
    require(len(comparisons) * 2 == len(summaries), "unmatched motor cell")
    return {"task_id": TASK_ID, "implementation": "initial-evaluator-v1",
            "evidence_kind": manifest["evidence_kind"], "population_scope": manifest["population_scope"],
            "protocol_scope": "pinned_generic_script_defaults_not_journal_reconstruction",
            "manifest_sha256": digest(manifest), "source_revision": SOURCE_REVISION,
            "sessions": summaries,
            "neural_regions": region_statistics([r for r in summaries if r["predictor"] == "neural"]),
            "movement_comparisons": comparisons,
            "scientific_qualification": False, "source_reproduction_established": False,
            "protected_submission_ready": False, "remaining_gates": GATES}


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value):
        raise EvaluationError(f"nonfinite JSON number: {value}")

    return json.loads(path.read_text(), object_pairs_hook=pairs, parse_constant=reject_constant)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        manifest = read_json(args.manifest)
        predictions = read_json(args.predictions)
        result = evaluate(manifest, predictions)
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, f"Evaluation rejected: {exc}\n")


if __name__ == "__main__":
    main()
