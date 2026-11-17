"""Brain Treebank decoding curves, from operator-owned labels and frozen scores.

This computes a missing endpoint; it does not reconstruct the paper's unrecovered
examples, window grid, trained decoder or exact figure values. No fitting occurs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

TASK_ID = "PAPER-paper-method-replacement-011"
DECODING_TASKS = ("sentence_onset", "word_onset", "noun_verb")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, keys, context):
    require(isinstance(value, dict) and set(value) == set(keys),
            f"{context}: unexpected or missing fields")


def unique_strings(values, context):
    require(isinstance(values, list) and values and
            all(isinstance(x, str) and x.strip() == x and x for x in values),
            f"{context}: expected nonempty string list")
    require(len(values) == len(set(values)), f"{context}: duplicate identity")
    return values


def number(value):
    require(type(value) in (int, float), "scores must be finite real numbers")
    try:
        value = float(value)
    except OverflowError as error:
        raise ValueError("scores must be finite real numbers") from error
    require(math.isfinite(value), "scores must be finite real numbers")
    return value


def auc(labels, scores):
    """Mann-Whitney ROC AUC; exact score ties receive half credit."""
    require(len(labels) == len(scores) and len(labels) > 1, "AUC length mismatch")
    require(all(type(y) is int and y in (0, 1) for y in labels),
            "binary integer labels required")
    positives = sum(labels)
    negatives = len(labels) - positives
    require(positives and negatives, "AUC requires both classes")
    ranked = sorted(zip(map(number, scores), labels))
    credit = 0.0
    preceding_negatives = 0
    start = 0
    while start < len(ranked):
        stop = start + 1
        while stop < len(ranked) and ranked[stop][0] == ranked[start][0]:
            stop += 1
        pos = sum(label for _, label in ranked[start:stop])
        neg = stop - start - pos
        credit += pos * (preceding_negatives + neg / 2)
        preceding_negatives += neg
        start = stop
    return credit / (positives * negatives)


def examples(value, context):
    require(isinstance(value, list) and value, f"{context}: no examples")
    ids = []
    folds = {i: [] for i in range(5)}
    test = []
    for row in value:
        fields(row, ("id", "label", "fold"), context)
        ids.append(row["id"])
        require(type(row["label"]) is int and row["label"] in (0, 1),
                f"{context}: invalid label")
        fold = row["fold"]
        require(fold is None or (type(fold) is int and fold in folds),
                f"{context}: training fold must be 0..4; test must be null")
        (test if fold is None else folds[fold]).append(row)
    unique_strings(ids, context)
    for split in [test, *folds.values()]:
        require({row["label"] for row in split} == {0, 1},
                f"{context}: test and each of five CV folds need both classes")
    return folds, test


def score_rows(rows, expected, width, context):
    require(isinstance(rows, list), f"{context}: predictions must be a list")
    by_id = {}
    for row in rows:
        fields(row, ("id", "scores"), context)
        require(isinstance(row["id"], str), f"{context}: invalid prediction ID")
        require(row["id"] not in by_id, f"{context}: duplicate prediction ID")
        require(isinstance(row["scores"], list) and len(row["scores"]) == width,
                f"{context}: complete window grid required")
        by_id[row["id"]] = [number(v) for v in row["scores"]]
    require(set(by_id) == {row["id"] for row in expected},
            f"{context}: prediction/example identities differ")
    return [auc([row["label"] for row in expected],
                [by_id[row["id"]][window] for row in expected])
            for window in range(width)]


def mean_curves(curves):
    return [math.fsum(column) / len(curves) for column in zip(*curves)]


def evaluate(reference, prediction):
    """Score all declared tasks/contacts/windows; never choose on held-out AUC.

    The reference is trusted operator input, separate from candidate scores.
    Training predictions must be genuinely out-of-fold. This function can check
    their identities, but cannot prove how a candidate produced them.
    """
    fields(reference, ("schema", "task_id", "scope", "access_condition", "window_ids", "regions",
                       "subjects", "source_manifest_sha256"), "reference")
    require(reference["schema"] == "treebank-decoding-reference/v1" and
            reference["task_id"] == TASK_ID, "wrong reference schema/task")
    require(reference["scope"] in ("generated_control", "operator_declared_panel"),
            "invalid scope")
    require(reference["access_condition"] in ("paper_and_data", "paper_data_and_author_code"),
            "invalid paired paper access condition")
    source_hash = reference["source_manifest_sha256"]
    require(isinstance(source_hash, str) and len(source_hash) == 64 and
            all(c in "0123456789abcdef" for c in source_hash), "invalid source manifest hash")
    windows = unique_strings(reference["window_ids"], "window grid")
    require(len(windows) > 1, "time-resolved endpoint requires multiple windows")
    regions = unique_strings(reference["regions"], "regions")
    require(isinstance(reference["subjects"], list), "subjects must be a list")
    fields(prediction, ("schema", "task_id", "access_condition", "subjects"), "prediction")
    require(prediction["schema"] == "treebank-decoding-scores/v1" and
            prediction["task_id"] == TASK_ID, "wrong prediction schema/task")
    require(prediction["access_condition"] == reference["access_condition"],
            "prediction/reference access condition differs")
    require(isinstance(prediction["subjects"], list), "prediction subjects must be a list")
    supplied = {}
    for subject in prediction["subjects"]:
        fields(subject, ("id", "electrodes"), "prediction subject")
        require(type(subject["id"]) is int and subject["id"] in range(1, 11),
                "invalid subject ID")
        require(subject["id"] not in supplied, "duplicate prediction subject")
        require(isinstance(subject["electrodes"], list), "electrodes must be a list")
        supplied[subject["id"]] = subject["electrodes"]
    results = {task: [] for task in DECODING_TASKS}
    subject_ids = set()
    exclusion_count = 0
    for subject in reference["subjects"]:
        fields(subject, ("id", "examples", "electrodes", "corrupted_electrodes"),
               "reference subject")
        sid = subject["id"]
        require(type(sid) is int and sid in range(1, 11) and sid not in subject_ids,
                "duplicate/invalid reference subject")
        subject_ids.add(sid)
        require(sid in supplied, "missing prediction subject")
        fields(subject["examples"], DECODING_TASKS, "example tasks")
        splits = {task: examples(subject["examples"][task], task) for task in DECODING_TASKS}
        require(isinstance(subject["electrodes"], list) and subject["electrodes"],
                "no retained electrodes")
        retained = {}
        for electrode in subject["electrodes"]:
            fields(electrode, ("id", "regions"), "reference electrode")
            eid = electrode["id"]
            unique_strings([eid], "electrode")
            require(eid not in retained, "duplicate reference electrode")
            memberships = electrode["regions"]
            require(isinstance(memberships, list), "electrode regions must be a list")
            if memberships:
                unique_strings(memberships, "electrode regions")
            require(set(memberships) <= set(regions), "undeclared electrode region")
            retained[eid] = memberships
        excluded = subject["corrupted_electrodes"]
        require(isinstance(excluded, list), "corrupted electrodes must be a list")
        if excluded:
            unique_strings(excluded, "corrupted electrodes")
        require(not set(excluded) & set(retained), "corrupted contact retained")
        exclusion_count += len(excluded)
        predictions = {}
        for electrode in supplied[sid]:
            fields(electrode, ("id", "tasks"), "prediction electrode")
            eid = electrode["id"]
            unique_strings([eid], "prediction electrode")
            require(eid not in predictions, "duplicate prediction electrode")
            fields(electrode["tasks"], DECODING_TASKS, "prediction tasks")
            predictions[eid] = electrode["tasks"]
        require(set(predictions) == set(retained), "complete retained electrode inventory required")
        for eid, memberships in retained.items():
            for task in DECODING_TASKS:
                rows = predictions[eid][task]
                fields(rows, ("train_cv", "test"), "electrode task scores")
                folds, test = splits[task]
                train = [row for fold in folds.values() for row in fold]
                # Verify the complete training prediction inventory before slicing folds.
                score_rows(rows["train_cv"], train, len(windows), "training CV")
                fold_curves = []
                for fold in folds.values():
                    ids = {row["id"] for row in fold}
                    fold_curves.append(score_rows([row for row in rows["train_cv"]
                                                   if row["id"] in ids], fold,
                                                  len(windows), "CV fold"))
                cv_curve = mean_curves(fold_curves)
                test_curve = score_rows(rows["test"], test, len(windows), "held-out test")
                peak = max(test_curve)
                results[task].append({"subject_id": sid, "electrode_id": eid,
                    "regions": memberships, "test_auc": test_curve,
                    "train_cv_fold_auc": fold_curves, "train_cv_mean_auc": cv_curve,
                    "train_cv_peak_auc": max(cv_curve), "test_peak_auc": peak,
                    "test_peak_window_ids": [w for w, a in zip(windows, test_curve) if a == peak],
                    "test_example_count": len(test), "training_example_count": len(train)})
    require(subject_ids == set(supplied), "unexpected prediction subject")
    if reference["scope"] == "operator_declared_panel":
        require(subject_ids == set(range(1, 11)), "original ten-participant cohort required")
        require(exclusion_count == 114, "original 114 corrupted-contact exclusions required")
    regional = {}
    for task, electrodes in results.items():
        regional[task] = []
        for region in regions:
            pool = [e for e in electrodes if region in e["regions"] and e["subject_id"] != 5]
            require(len(pool) >= 10, f"{task}/{region}: ten eligible regional contacts required")
            pool.sort(key=lambda e: (-e["train_cv_peak_auc"], e["subject_id"], e["electrode_id"]))
            # Source tie order is unrecovered. Do not fabricate a historical selection.
            require(len(pool) == 10 or pool[9]["train_cv_peak_auc"] > pool[10]["train_cv_peak_auc"],
                    f"{task}/{region}: unresolved tie at ten-electrode selection boundary")
            selected = pool[:10]
            regional[task].append({"region": region,
                "selected_contacts": [{"subject_id": e["subject_id"],
                    "electrode_id": e["electrode_id"]} for e in selected],
                "test_mean_auc": mean_curves([e["test_auc"] for e in selected]),
                "selected_participant_ids": sorted({e["subject_id"] for e in selected}),
                "selection_basis": "peak of mean of five training-CV fold AUC curves"})
    return {"schema": "treebank-decoding-curves/v1", "task_id": TASK_ID,
        "scope": reference["scope"], "source_manifest_sha256": source_hash,
        "access_condition": reference["access_condition"],
        "window_ids": windows, "electrodes": results, "regional_top_ten": regional,
        "region_excluded_subject_ids": [5], "corrupted_contact_count": exclusion_count,
        "independent_uncertainty_unit": "participant; no inferential interval computed",
        "qualification": {"authentic_population_verified": False,
            "source_window_grid_verified": False, "author_baseline_reproduced": False,
            "paper_reproduction_established": False,
            "paper_improvement_established": False}}


def reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(args.output.resolve() not in (args.reference.resolve(), args.predictions.resolve()),
            "output must not overwrite an input")
    inputs = [p.read_bytes() for p in (args.reference, args.predictions)]
    result = evaluate(*(json.loads(blob, object_pairs_hook=reject_duplicates) for blob in inputs))
    result["input_sha256"] = dict(zip(("reference", "predictions"),
                                      (hashlib.sha256(blob).hexdigest() for blob in inputs)))
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
