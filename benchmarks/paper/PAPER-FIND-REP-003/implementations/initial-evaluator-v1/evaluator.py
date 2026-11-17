"""Strict normalized-artifact scoring for PAPER-FIND-REP-003; no native fitting.

The source variance metric and prospective phase comparator are intentionally
separate. Input values are already event locked; this module never interprets
MAT files, fits neural models, or asserts empirical qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np

TASK_ID = "PAPER-FIND-REP-003"
REVISION = "815b610b3beddfed5a3abf611d3a465ab9e4ce5c"
MICE = ("cfa17", "cfa19", "cfa20", "cfa22", "cfa24")
SESSIONS = {
    ("cfa17", "200825"): "M1", ("cfa17", "200827"): "S1",
    ("cfa19", "200820"): "M1", ("cfa19", "200826"): "S1",
    ("cfa20", "201114"): "M1", ("cfa20", "201118"): "S1",
    ("cfa22", "220605"): "M1", ("cfa22", "220611"): "S1",
    ("cfa24", "220727"): "M1", ("cfa24", "220724"): "S1",
}
JOINT_NAMES = ["SHDRf", "SHDRa", "SHDRr", "ELBOf", "WRSTf", "WRSTd", "WRSTr",
               "MCP1f", "MCP2f", "MCP3f", "MCP4f", "MCP1a", "MCP2a", "MCP3a",
               "MCP4a", "MCP1o", "MCP4o", "P1P2", "P2P3", "P3P4", "PIP1f",
               "PIP2f", "PIP3f", "PIP4f"]
TIME_MS = list(range(-100, 401, 10))
HOLDS = [
    "Native MAT schema, complete raw population and event-lock bridge unqualified",
    "Neural model provenance, top-100 cell selection, PCA and native ridge reference unqualified",
    "Protected reference provisioning and candidate information boundary unqualified",
    "No authentic empirical execution, independent native reference parity or grading threshold",
    "Intervention trajectory and other full-paper endpoints remain outstanding",
    "Paper/data/code exposure and source-specific redistribution terms remain applicable",
    "Five imaging mice and two optogenetic mice do not establish population generalization",
]


class ContractError(ValueError):
    """An artifact cannot be scored without changing its declared estimand."""


def require(ok, message):
    if not ok:
        raise ContractError(message)


def integer(value, name, minimum=0):
    require(type(value) is int and value >= minimum, f"{name} must be an integer >= {minimum}")
    return value


def number(value, name):
    require(type(value) in (int, float) and math.isfinite(value), f"{name} must be finite numeric")
    return float(value)


def binary(value, name):
    require(type(value) in (bool, int) and value in (0, 1), f"{name} must be binary")
    return bool(value)


def matrix(value, name):
    # Explicitly reject booleans, numeric strings, ragged rows and NaN/Infinity.
    require(isinstance(value, list) and len(value) == len(TIME_MS), f"{name}: expected 51 time rows")
    for row in value:
        require(isinstance(row, list) and len(row) == len(JOINT_NAMES), f"{name}: expected 24 joints")
        for x in row:
            number(x, name)
    return np.asarray(value, dtype=float)


def indexed(records, key, name):
    require(isinstance(records, list), f"{name} must be a list")
    out = {}
    for record in records:
        require(isinstance(record, dict), f"{name}: expected object")
        identity = key(record)
        require(identity not in out, f"{name}: duplicate identity {identity}")
        out[identity] = record
    return out


def eligibility(record):
    """Source loadLock4Decode predicates; null grabTimeC denotes MATLAB NaN."""
    e = record["eligibility"]
    predicates = {
        "success": binary(e["success"], "success"),
        "grabTimeC_present": e["grabTimeC"] is not None,
        "liftRT_lt_500": number(e["liftRT"], "liftRT") < 500,
        "goodDLC": binary(e["goodDLC"], "goodDLC"),
        "wrongZoneFirst_false": not binary(e["wrongZoneFirst"], "wrongZoneFirst"),
        "movementTime_lt_500": number(e["movementTime"], "movementTime") < 500,
        "timeToContact_lt_1000": number(e["timeToContact"], "timeToContact") < 1000,
        "has_radical": binary(e["has_radical"], "has_radical"),
    }
    if e["grabTimeC"] is not None:
        number(e["grabTimeC"], "grabTimeC")
    return [name for name, passed in predicates.items() if not passed]


def join_trials(neural_trials, kinematic_trials):
    """Join within ONE independently identified session, never by row position."""
    key = lambda r: integer(r["trial_number"], "trial_number", 1)
    neural = indexed(neural_trials, key, "neural_trials")
    kinematic = indexed(kinematic_trials, key, "kinematic_trials")
    require(neural.keys() == kinematic.keys(), "neural/kinematic trial identity mismatch")
    eligible, excluded = {}, []
    for trial in sorted(kinematic):
        n, k = neural[trial], kinematic[trial]
        nlocked = binary(n["locked"], "neural locked")
        klocked = binary(k["locked"], "kinematic locked")
        require(nlocked == klocked, f"trial {trial}: neural/kinematic lock mismatch")
        reasons = eligibility(k)
        if not nlocked:
            reasons.append("unlocked")
        if reasons:
            excluded.append({"trial_number": trial, "reasons": reasons})
            continue
        require(k["LR"] in ("L", "R"), "LR must use explicit L/R normalization")
        eligible[trial] = {"LR": k["LR"], "angles": matrix(k["joint_angles"], "joint_angles")}
    require(len(eligible) >= 10, "at least ten eligible trials required for ten-fold partition")
    return eligible, excluded


def validate_folds(folds, eligible):
    keyed = indexed(folds, lambda f: (integer(f["repeat"], "repeat"), integer(f["fold"], "fold")), "folds")
    require(set(keyed) == set(itertools.product(range(5), range(10))), "exactly five repetitions of ten folds required")
    population = set(eligible)
    seen = {r: [] for r in range(5)}
    for (repeat, _), f in keyed.items():
        train = [integer(t, "train trial", 1) for t in f["train_trials"]]
        test = [integer(t, "test trial", 1) for t in f["test_trials"]]
        require(len(train) == len(set(train)) and len(test) == len(set(test)), "duplicate fold trial")
        require(train and test, "empty train/test fold")
        require(set(train).isdisjoint(test), "train/test trial leakage")
        require(set(train) | set(test) == population, "fold must partition complete eligible population")
        require({eligible[t]["LR"] for t in train} == {"L", "R"}, "phase template needs both train directions")
        seen[repeat].extend(test)
    for trials in seen.values():
        require(len(trials) == len(population) and set(trials) == population, "each trial must be held out once per repetition")
    for repeat in range(5):
        sizes = [len(keyed[(repeat, fold)]["test_trials"]) for fold in range(10)]
        require(max(sizes) - min(sizes) <= 1, "source modulo partition requires balanced test fold sizes")
    return keyed


def score_arrays(actual, predicted):
    """Source VE plus bias-sensitive R²; constant actual features are undefined."""
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    require(actual.ndim == 2 and actual.shape == predicted.shape and actual.shape[0] >= 2, "score shape mismatch")
    require(np.isfinite(actual).all() and np.isfinite(predicted).all(), "nonfinite score input")
    residual = actual - predicted
    denominator = np.sum((actual - actual.mean(axis=0)) ** 2, axis=0)
    require(np.isfinite(denominator).all() and np.all(denominator > 0), "constant/overflow heldout target: VE is undefined; no silent joint omission")
    ve = 1 - np.sum((residual - residual.mean(axis=0)) ** 2, axis=0) / denominator
    r2 = 1 - np.sum(residual ** 2, axis=0) / denominator
    require(np.isfinite(ve).all() and np.isfinite(r2).all(), "score overflow")
    return {"source_ve": ve.tolist(), "r2_diagnostic": r2.tolist(),
            "mean_error": residual.mean(axis=0).tolist()}


def phase_template(eligible, train):
    """Prospective phase baseline: same direction/time-bin training mean only."""
    return {d: np.stack([eligible[t]["angles"] for t in train if eligible[t]["LR"] == d]).mean(axis=0)
            for d in ("L", "R")}


def animal_summary(values):
    """Equal-mouse mean, exact sign-flip test and exhaustive percentile bootstrap.

    Both are prospective descriptive inference, not source-paper tests. The
    sign-flip test assumes sign exchangeability; five mice limit resolution.
    """
    x = np.asarray(values, dtype=float)
    require(x.shape == (5,) and np.isfinite(x).all(), "animal summary requires exactly five finite mouse effects")
    observed = float(x.mean())
    null = [float(np.mean(x * signs)) for signs in itertools.product((-1, 1), repeat=5)]
    boot = [float(x[list(indices)].mean()) for indices in itertools.product(range(5), repeat=5)]
    tolerance = np.finfo(float).eps * float(np.mean(np.abs(x))) * 16
    p = sum(abs(v) >= abs(observed) - tolerance for v in null) / 32
    return {"n_mice": 5, "mean": observed, "mouse_values": x.tolist(),
            "two_sided_exact_signflip_p": p, "signflip_assignments": 32,
            "bootstrap_percentile_95": np.quantile(boot, [0.025, 0.975]).tolist(),
            "bootstrap_assignments": 3125, "inference_policy": "prospective_equal_mouse_descriptive"}


def evaluate(reference, submission):
    require(reference["task_id"] == TASK_ID and submission["task_id"] == TASK_ID, "wrong task")
    require(reference["schema_version"] == 1 and submission["schema_version"] == 1, "schema version")
    require(reference["source_revision"] == REVISION, "source revision mismatch")
    require(reference["artifact_kind"] in ("generated_engineering_control", "normalized_empirical_unqualified"), "artifact kind")
    require(reference["joint_names"] == JOINT_NAMES and reference["time_ms"] == TIME_MS, "exact joint/time grid required")
    sessions = indexed(reference["sessions"], lambda s: (s["mouse"], s["session"]), "sessions")
    require(sessions.keys() == SESSIONS.keys(), "all ten source imaging sessions are required")
    pkey = lambda p: (p["mouse"], p["session"], integer(p["repeat"], "prediction repeat"),
                      integer(p["fold"], "prediction fold"), integer(p["trial_number"], "prediction trial", 1))
    predictions = indexed(submission["predictions"], pkey, "predictions")
    expected, reports, effects = set(), [], {}
    for identity in sorted(sessions):
        session = sessions[identity]
        region = SESSIONS[identity]
        require(session["region"] == region, "source session/region assignment mismatch")
        eligible, excluded = join_trials(session["neural_trials"], session["kinematic_trials"])
        folds = validate_folds(session["folds"], eligible)
        fold_reports = []
        for (repeat, fold), f in sorted(folds.items()):
            baseline = phase_template(eligible, f["train_trials"])
            actual, predicted, phase = [], [], []
            for trial in sorted(f["test_trials"]):
                key = (*identity, repeat, fold, trial)
                expected.add(key)
                require(key in predictions, f"missing heldout prediction {key}")
                actual.append(eligible[trial]["angles"])
                predicted.append(matrix(predictions[key]["joint_angles"], "prediction"))
                phase.append(baseline[eligible[trial]["LR"]])
            neural_score = score_arrays(np.concatenate(actual), np.concatenate(predicted))
            phase_score = score_arrays(np.concatenate(actual), np.concatenate(phase))
            delta = np.array(neural_score["source_ve"]) - phase_score["source_ve"]
            fold_reports.append({"repeat": repeat, "fold": fold, "n_test_trials": len(actual),
                                 "neural_prediction": neural_score, "phase_baseline": phase_score,
                                 "delta_ve_per_joint": delta.tolist(), "median_joint_delta_ve": float(np.median(delta))})
        effect = float(np.mean([f["median_joint_delta_ve"] for f in fold_reports]))
        effects[(identity[0], region)] = effect
        reports.append({"mouse": identity[0], "session": identity[1], "region": region,
                        "eligible_trials": len(eligible), "excluded_trials": excluded,
                        "mean_fold_median_joint_delta_ve": effect, "folds": fold_reports})
    require(set(predictions) == expected, "unexpected predictions outside the protected heldout plan")
    m1 = [effects[(m, "M1")] for m in MICE]
    s1 = [effects[(m, "S1")] for m in MICE]
    return {"task_id": TASK_ID, "component": "normalized_joint_angle_phase_contrast_v1",
            "artifact_kind": reference["artifact_kind"], "scientifically_qualified": False,
            "full_contract_complete": False, "source_model_reproduced": False, "holds": HOLDS,
            "effect_direction": "neural prediction VE minus train-only phase template VE",
            "aggregation": "median of 24 joint delta VE values per model; mean of 50 models per session; equal mouse",
            "sessions": reports, "animal_order": list(MICE), "M1_phase_advantage": animal_summary(m1),
            "S1_phase_advantage": animal_summary(s1),
            "paired_M1_minus_S1_phase_advantage": animal_summary(np.array(m1) - np.array(s1))}


def optogenetic_timing(records):
    """Source Fig1H selection and cue-relative contact histogram, separate cohort.

    Normalization divides by all selected observations, retaining out-of-window
    mass. 30 edges give 29 bins; contact time is NOT grabTimeC-liftTimeC.
    """
    keyed = indexed(records, lambda r: (r["mouse"], r["session"], integer(r["trial_number"], "opto trial", 1)), "opto trials")
    require({k[0] for k in keyed} == {"cfaVG1", "cfaVG4"}, "both separate optogenetic mice are required")
    selected = {(m, g): [] for m in ("cfaVG1", "cfaVG4") for g in (0, 1)}
    excluded = []
    for key, r in keyed.items():
        group = int(binary(r["optoTrial"], "optoTrial"))
        good = binary(r["success"], "success") and not binary(r["optoProblem"], "optoProblem")
        # Validate all fields even when another predicate would exclude a row.
        problem = binary(r["optoProblem"], "optoProblem")
        wrong = binary(r["wrongGrabFirst"], "wrongGrabFirst")
        grab = None if r["grabTimeC"] is None else number(r["grabTimeC"], "grabTimeC")
        lift = None if r["liftTimeC"] is None else number(r["liftTimeC"], "liftTimeC")
        if good and not problem and not wrong and grab is not None and lift is not None and grab > lift:
            selected[(key[0], group)].append(grab / 1000.0)
        else:
            excluded.append(list(key))
    edges = np.linspace(0, 9, 30)
    by_mouse = []
    for m in ("cfaVG1", "cfaVG4"):
        require(all(selected[(m, g)] for g in (0, 1)), "each optogenetic mouse needs selected control and opto trials")
        control, opto = selected[(m, 0)], selected[(m, 1)]
        by_mouse.append({"mouse": m, "n_control": len(control), "n_opto": len(opto),
                         "mean_contact_delay_seconds": float(np.mean(opto) - np.mean(control))})
    histograms = {}
    for group, name in ((0, "control"), (1, "opto")):
        values = sum((selected[(m, group)] for m in ("cfaVG1", "cfaVG4")), [])
        counts = np.histogram(values, bins=edges)[0]
        histograms[name] = {"selected_trials": len(values), "counts": counts.tolist(),
                            "probability": (counts / len(values)).tolist(),
                            "outside_display_window": len(values) - int(counts.sum())}
    return {"task_id": TASK_ID, "component": "separate_opto_cue_contact_timing_v1",
            "scientifically_qualified": False, "full_contract_complete": False, "holds": HOLDS,
            "source_histogram_edges_seconds": edges.tolist(), "histograms": histograms,
            "excluded_trial_keys": excluded, "mouse_effects": by_mouse,
            "prospective_equal_mouse_mean_delay_seconds": float(np.mean([r["mean_contact_delay_seconds"] for r in by_mouse])),
            "limit": "Descriptive timing conditional on source successful-trial selection; no causal/population inference or trajectory endpoint"}


def read_json(path):
    raw = Path(path).read_bytes()
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"duplicate JSON member {key}")
            result[key] = value
        return result
    def invalid(value):
        raise ContractError(f"invalid JSON numeric constant {value}")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid), hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("decode", "opto"))
    parser.add_argument("reference")
    parser.add_argument("--submission")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    reference, ref_hash = read_json(args.reference)
    if args.mode == "decode":
        require(args.submission is not None, "decode requires --submission")
        submission, sub_hash = read_json(args.submission)
        result = evaluate(reference, submission)
        result["submission_sha256"] = sub_hash
    else:
        require(args.submission is None, "opto has no prediction submission")
        require(reference["task_id"] == TASK_ID and reference["schema_version"] == 1, "opto task/schema mismatch")
        require(reference["source_revision"] == REVISION, "opto source revision mismatch")
        require(reference["artifact_kind"] in ("generated_engineering_control", "normalized_empirical_unqualified"), "opto artifact kind")
        result = optogenetic_timing(reference["opto_trials"])
        result["artifact_kind"] = reference["artifact_kind"]
    result["reference_sha256"] = ref_hash
    Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
