#!/usr/bin/env python3
"""Figure 6h OOF endpoint arithmetic; no fitting, split generation or admission.

The operator owns labels/manifest. Native author kfoldLoss values must agree
with independently counted out-of-fold errors for *every* ridge setting.
This parity check prevents silently replacing MATLAB weighting semantics.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

TASK = "PAPER-ROOT-ADD-019"
AUTHOR_SETTINGS = ["ridge_%02d" % i for i in range(11)]
LAMBDAS = [10 ** (-4 + 3.8 * i / 10) for i in range(11)]


def need(condition, message):
    if not condition:
        raise ValueError(message)


def exact_keys(value, names, where):
    need(isinstance(value, dict) and set(value) == set(names),
         where + ": unexpected or missing fields")


def identifiers(values, where):
    need(isinstance(values, list) and all(isinstance(x, str) and x for x in values),
         where + ": expected nonempty string identifiers")
    need(len(set(values)) == len(values), where + ": duplicate identifiers")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode("utf-8")).hexdigest()


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_manifest(manifest):
    exact_keys(manifest, ["schema", "task", "preparation_sha256", "sessions"], "manifest")
    need(manifest["schema"] == "ach_fig6h_oof_manifest_v1" and manifest["task"] == TASK,
         "wrong manifest schema or task")
    pin = manifest["preparation_sha256"]
    need(isinstance(pin, str) and len(pin) == 64 and
         all(c in "0123456789abcdef" for c in pin), "invalid preparation evidence digest")
    sessions = manifest["sessions"]
    need(isinstance(sessions, list) and len(sessions) == 18,
         "Figure 6h requires all 18 sessions; a reduced panel is not this endpoint")
    session_ids, rats = [], set()
    for session in sessions:
        exact_keys(session, ["session_id", "rat_id", "unit_count", "trial_ids", "folds", "labels"],
                   "session")
        session_ids.append(session["session_id"])
        need(isinstance(session["rat_id"], str) and session["rat_id"], "invalid rat ID")
        rats.add(session["rat_id"])
        need(type(session["unit_count"]) is int and session["unit_count"] >= 5,
             "source eligibility requires at least five simultaneously recorded units")
        identifiers(session["trial_ids"], "trial IDs")
        n = len(session["trial_ids"])
        folds, labels = session["folds"], session["labels"]
        need(isinstance(folds, list) and len(folds) == n and
             all(type(f) is int and 1 <= f <= 10 for f in folds) and
             set(folds) == set(range(1, 11)), "complete tenfold assignment required")
        need(isinstance(labels, list) and len(labels) == n and
             all(type(y) is int and y in (0, 1) for y in labels) and set(labels) == {0, 1},
             "both fast=1 and slow=0 classes required; do not repair labels here")
    identifiers(session_ids, "session IDs")
    need(len(rats) == 8, "Figure 6h requires the original eight rats")
    return sessions


def score_bundle(manifest, bundle, role):
    """Count one OOF prediction per retained trial and setting, then source min."""
    sessions = validate_manifest(manifest)
    fields = ["schema", "role", "manifest_sha256", "program_sha256", "setting_ids", "sessions"]
    if role == "author":
        fields += ["lambdas"]
    exact_keys(bundle, fields, role + " bundle")
    need(bundle["schema"] == "ach_fig6h_oof_predictions_v1" and bundle["role"] == role,
         "wrong predictions schema or role")
    need(bundle["manifest_sha256"] == digest(manifest), "bundle is bound to a different manifest")
    pin = bundle["program_sha256"]
    need(isinstance(pin, str) and len(pin) == 64 and
         all(c in "0123456789abcdef" for c in pin), "invalid frozen program digest")
    settings = bundle["setting_ids"]
    identifiers(settings, "setting IDs")
    need(len(settings) == 11, "all 11 predeclared selection settings required")
    if role == "author":
        need(settings == AUTHOR_SETTINGS, "author ridge order changed")
        need(isinstance(bundle["lambdas"], list) and len(bundle["lambdas"]) == 11 and
             all(finite(x) and math.isclose(x, y, rel_tol=1e-12, abs_tol=0)
                 for x, y in zip(bundle["lambdas"], LAMBDAS)), "author lambda grid changed")
    records = bundle["sessions"]
    need(isinstance(records, list) and len(records) == 18, "incomplete prediction session panel")
    results = []
    for session, record in zip(sessions, records):
        keys = ["session_id", "trial_ids", "folds", "predictions"]
        if role == "author":
            keys += ["native_kfold_losses"]
        exact_keys(record, keys, "prediction session")
        need(record["session_id"] == session["session_id"], "session order or identity mismatch")
        need(record["trial_ids"] == session["trial_ids"], "trial order or identity mismatch")
        need(record["folds"] == session["folds"], "fold assignment mismatch")
        predictions = record["predictions"]
        need(isinstance(predictions, list) and len(predictions) == 11,
             "missing setting predictions")
        labels = session["labels"]
        n = len(labels)
        errors, fold_errors = [], []
        for predicted in predictions:
            need(isinstance(predicted, list) and len(predicted) == n and
                 all(type(p) is int and p in (0, 1) for p in predicted),
                 "predictions must contain exactly one binary OOF class per trial")
            wrong = [int(a != b) for a, b in zip(predicted, labels)]
            errors.append(sum(wrong))
            fold_errors.append([sum(e for e, f in zip(wrong, session["folds"]) if f == fold)
                                for fold in range(1, 11)])
        losses = [e / n for e in errors]
        if role == "author":
            native = record["native_kfold_losses"]
            need(isinstance(native, list) and len(native) == 11 and
                 all(finite(v) and 0 <= v <= 1 for v in native), "invalid native loss panel")
            need(all(math.isclose(a, b, rel_tol=0, abs_tol=1e-12)
                     for a, b in zip(losses, native)),
                 "OOF error differs from native kfoldLoss; weighting/label parity unresolved")
        # MATLAB min chooses the first setting on ties.
        best = min(range(11), key=lambda i: errors[i])
        results.append({"session_id": session["session_id"], "rat_id": session["rat_id"],
                        "trial_count": n, "fast_count": sum(labels), "slow_count": n - sum(labels),
                        "fold_sizes": [session["folds"].count(f) for f in range(1, 11)],
                        "errors_by_setting": errors, "errors_by_setting_and_fold": fold_errors,
                        "losses_by_setting": losses, "selected_setting_id": settings[best],
                        "selected_index_zero_based": best, "accuracy_percent": 100 * (1 - losses[best])})
    accuracy = [s["accuracy_percent"] for s in results]
    return {"role": role, "program_sha256": bundle["program_sha256"], "sessions": results,
            "mean_session_accuracy_percent": statistics.mean(accuracy),
            "session_sample_sd_percent": statistics.stdev(accuracy),
            "session_sem_percent_descriptive_only": statistics.stdev(accuracy) / math.sqrt(18),
            "sessions_above_50_percent": sum(x > 50 for x in accuracy)}


def compare(manifest, author, candidate):
    reference = score_bundle(manifest, author, "author")
    proposal = score_bundle(manifest, candidate, "candidate")
    deltas, by_rat = [], {}
    for a, b in zip(reference["sessions"], proposal["sessions"]):
        delta = b["accuracy_percent"] - a["accuracy_percent"]
        deltas.append({"session_id": a["session_id"], "rat_id": a["rat_id"],
                       "accuracy_delta_percentage_points": delta})
        by_rat.setdefault(a["rat_id"], []).append(delta)
    return {"schema": "ach_fig6h_oof_comparison_v1", "task": TASK,
            "manifest_sha256": digest(manifest), "author": reference, "candidate": proposal,
            "mean_session_delta_percentage_points": statistics.mean(
                x["accuracy_delta_percentage_points"] for x in deltas),
            "paired_session_deltas": deltas,
            "rat_clusters": [{"rat_id": rat, "session_count": len(values),
                              "mean_session_delta_percentage_points": statistics.mean(values)}
                             for rat, values in sorted(by_rat.items())],
            "interpretation": {
                "estimand": "equal-weight mean of 18 within-session best-of-11 CV accuracies",
                "selection_bias": "The same CV outcomes select settings and report accuracy.",
                "uncertainty": "SD and SEM are descriptive; no independent-rat CI or significance claim.",
                "scope": "Figure 6h endpoint arithmetic only; not whole-paper demixing or improvement qualification.",
                "provenance": "Hashes bind supplied records; external custody and authentic source admission remain required."}}


def audit_source_labels(is_fast, is_slow):
    """Literal MATLAB lines 79-81 versus intended mask labels; never auto-repair.

    Membership in the second assignment operates on y after the first mutation.
    Thus a slow original trial index 1 can change fast labels from 1 to 0.
    """
    need(isinstance(is_fast, list) and isinstance(is_slow, list) and
         len(is_fast) == len(is_slow) and
         all(type(x) is bool for x in is_fast + is_slow), "boolean masks required")
    fast = {i + 1 for i, yes in enumerate(is_fast) if yes}
    slow = {i + 1 for i, yes in enumerate(is_slow) if yes}
    trials = sorted(fast | slow)
    native = [1 if i in fast else i for i in trials]
    native = [0 if value in slow else value for value in native]
    intended = [0 if i in slow else 1 for i in trials]
    return {"trial_indices_one_based": trials, "literal_native_labels": native,
            "mask_semantic_labels_slow_precedence": intended,
            "mismatched_trial_indices_one_based": [i for i, a, b in zip(trials, native, intended) if a != b],
            "overlapping_quartile_trial_indices_one_based": sorted(fast & slow)}


def load_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    def invalid(value):
        raise ValueError("nonfinite JSON number: " + value)
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique,
                      parse_constant=invalid)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="operator-owned target/identity JSON")
    parser.add_argument("--author", required=True, help="frozen author OOF panel with native losses")
    parser.add_argument("--candidate", required=True, help="frozen candidate OOF panel")
    parser.add_argument("--output", required=True, help="fresh operator-private result JSON")
    args = parser.parse_args()
    result = compare(load_json(args.manifest), load_json(args.author), load_json(args.candidate))
    with Path(args.output).open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
