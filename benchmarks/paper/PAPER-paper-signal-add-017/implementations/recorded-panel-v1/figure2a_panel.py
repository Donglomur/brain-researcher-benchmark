"""Figure 2A/S7A support and trial-vote arithmetic, without model execution.

Operator-side construction only. A supplied frozen manifest is not authenticated
by this module. Original windows, labels, online outputs and models still require
independent source qualification. Ties fail closed rather than borrow the older
prospective evaluator's smallest-class rule.
"""
from collections import Counter
import hashlib
import json
import re
from statistics import median

SUBJECTS = tuple(f"S{i:02d}" for i in range(1, 22))
CLASSES = {2: (1, 4), 3: (1, 2, 4)}
REPLAY_MODELS = ("S1-B", "S1-F", "S2-B")
MODELS = REPLAY_MODELS + ("S2-F",)
SCHEMA = "finger017-recorded-panel-assessment/v1"
PREDICTIONS_SCHEMA = "finger017-recorded-panel-predictions/v1"



def _units():
    # Numeric outputs remain fractions. Canonical reproduction uses percent.
    return {"accuracy": "fraction_correct_trials",
            "subject_median_accuracy": "fraction_correct_trials",
            "author_accuracy": "fraction_correct_trials",
            "candidate_accuracy": "fraction_correct_trials",
            "candidate_minus_author": "fraction_correct_trials_difference",
            "canonical_accuracy_binding": {"field": "participant_trial_accuracy",
                                           "units": "percent correct trials", "multiply_by": 100},
            "canonical_difference_binding": {"units": "percentage_points", "multiply_by": 100},
            "conversion_applied_to_output": False}

def require(condition, message):
    if not condition:
        raise ValueError(message)


def keys(value, expected, name):
    require(type(value) is dict and set(value) == set(expected),
            f"{name}: exact fields required")


def sha(value, name):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value),
            f"{name}: SHA256 required")
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def integer(value, low, high, name):
    require(type(value) is int and low <= value <= high, f"{name}: invalid integer")


def member(subject, nclass, run, condition="MI"):
    kind = {"MI": "Imagery", "ME": "Movement"}[condition]
    folder = f"Online{kind}_Sess02_{nclass}class_Finetune"
    return f"{subject}/{folder}/{subject}_{folder}_R{run:02d}.mat"


def validate_assessment(assessment, *, expected_sha256, expected_condition="MI"):
    """Validate all 336 run roles and 8,400 declared source trials.

    Windows are all complete 1,024-sample windows at a 128-sample step in the
    supplied source-preparation extent. No actual source extent is inferred from
    a nominal three-second cue. Declared extents remain source-unqualified.
    """
    sha(expected_sha256, "external assessment pin")
    keys(assessment, ("schema", "condition", "source_receipt_sha256",
                      "recorded_control_receipt_sha256", "runs"), "assessment")
    require(expected_condition in ("MI", "ME") and assessment["schema"] == SCHEMA
            and assessment["condition"] == expected_condition, "condition/source route mismatch")
    sha(assessment["source_receipt_sha256"], "source receipt")
    sha(assessment["recorded_control_receipt_sha256"], "recorded control receipt")
    require(digest(assessment) == expected_sha256, "assessment differs from external frozen pin")
    require(type(assessment["runs"]) is list and len(assessment["runs"]) == 336,
            "all21 subjects, both class conditions and eight runs required")
    expected_runs = {(s, nc, r) for s in SUBJECTS for nc in CLASSES for r in range(1, 9)}
    seen, trials, windows, run_hashes = set(), {}, {}, {}
    for run in assessment["runs"]:
        keys(run, ("subject", "nclass", "run", "member", "source_sha256", "trials"), "run")
        s, nc, number = run["subject"], run["nclass"], run["run"]
        require(type(s) is str and s in SUBJECTS, "unknown subject")
        integer(nc, 2, 3, "class condition")
        integer(number, 1, 8, "run")
        role = (s, nc, number)
        require(role in expected_runs and role not in seen, "repeated/unexpected run role")
        seen.add(role)
        require(run["member"] == member(s, nc, number, expected_condition), "wrong source assessment member")
        pin = sha(run["source_sha256"], "source member")
        # One original file cannot be silently re-labelled as multiple runs.
        require(pin not in run_hashes, "source bytes reused under different run identities")
        run_hashes[pin] = role
        require(type(run["trials"]) is list and len(run["trials"]) == 10 * nc,
                "complete20/30-trial source run required")
        targets, previous_end = [], -1
        for index, trial in enumerate(run["trials"]):
            keys(trial, ("id", "target", "start_sample_zero_based", "length_samples",
                         "recorded_prediction"), "trial")
            tid = f"{run['member']}#trial{index:04d}"
            require(trial["id"] == tid and tid not in trials, "trial identity/order mismatch")
            integer(trial["target"], 1, 4, "target")
            integer(trial["recorded_prediction"], 1, 4, "recorded prediction")
            require(trial["target"] in CLASSES[nc] and trial["recorded_prediction"] in CLASSES[nc],
                    "label outside source class condition")
            start, length = trial["start_sample_zero_based"], trial["length_samples"]
            integer(start, 0, 2**53 - 1, "trial start")
            integer(length, 1024, 5120, "source-preparation trial extent")
            require(start >= previous_end, "overlapping or reordered original trials")
            previous_end = start + length
            target = trial["target"]
            targets.append(target)
            ids = tuple(f"{tid}#sample{offset:05d}" for offset in range(0, length - 1024 + 1, 128))
            trials[tid] = {"subject": s, "nclass": nc, "run": number,
                           "target": target, "recorded_prediction": trial["recorded_prediction"],
                           "window_ids": ids}
            for wid in ids:
                require(wid not in windows, "duplicate window")
                windows[wid] = nc
        require(Counter(targets) == Counter({label: 10 for label in CLASSES[nc]}),
                "each source class needs ten original trials per run")
    require(seen == expected_runs and len(trials) == 8400, "incomplete recorded-session assessment")
    return trials, windows


def evaluate_panel(assessment, predictions, *, expected_assessment_sha256, expected_condition="MI"):
    """Recompute the full panel; refuse missing windows and unresolved vote ties.

    Predictions contain hard source-class window outputs from three replayed
    models, and immutable operator-recorded trial outputs for the online column.
    This does not implement probability argmax/tie conventions or model fitting.
    """
    trials, windows = validate_assessment(assessment, expected_sha256=expected_assessment_sha256,
                                            expected_condition=expected_condition)
    keys(predictions, ("schema", "assessment_sha256", "models"), "predictions")
    require(predictions["schema"] == PREDICTIONS_SCHEMA, "wrong prediction schema")
    require(predictions["assessment_sha256"] == expected_assessment_sha256,
            "prediction assessment pin mismatch")
    keys(predictions["models"], MODELS, "complete source model panel")
    trial_outputs = {}
    for model in REPLAY_MODELS:
        row = predictions["models"][model]
        keys(row, ("role", "model_artifact_sha256", "window_predictions"), model)
        require(row["role"] == "replayed_decoder", "replay/recorded source role confused")
        sha(row["model_artifact_sha256"], "model artifact")
        supplied = row["window_predictions"]
        require(type(supplied) is dict and set(supplied) == set(windows),
                "exact common assessment windows required for every replay model")
        for wid, label in supplied.items():
            require(type(label) is int and label in CLASSES[windows[wid]], "invalid hard-window class")
        result = {}
        for tid, trial in trials.items():
            votes = Counter(supplied[wid] for wid in trial["window_ids"])
            maximum = max(votes.values())
            winners = [label for label, count in votes.items() if count == maximum]
            require(len(winners) == 1, "unresolved source trial-vote tie; cannot silently break/drop")
            result[tid] = winners[0]
        trial_outputs[model] = result
    recorded = predictions["models"]["S2-F"]
    keys(recorded, ("role", "recorded_control_receipt_sha256", "trial_predictions"), "S2-F")
    require(recorded["role"] == "recorded_online_control", "S2-F must remain recorded control")
    require(recorded["recorded_control_receipt_sha256"] == assessment["recorded_control_receipt_sha256"],
            "recorded control provenance changed")
    require(type(recorded["trial_predictions"]) is dict
            and set(recorded["trial_predictions"]) == set(trials), "complete recorded trial roster required")
    for tid, label in recorded["trial_predictions"].items():
        require(type(label) is int and label == trials[tid]["recorded_prediction"],
                "recorded online output changed")
    trial_outputs["S2-F"] = dict(recorded["trial_predictions"])
    counts = {(s, nc, model): [0, 0] for s in SUBJECTS for nc in CLASSES for model in MODELS}
    for tid, trial in trials.items():
        for model in MODELS:
            cell = counts[(trial["subject"], trial["nclass"], model)]
            cell[0] += int(trial_outputs[model][tid] == trial["target"])
            cell[1] += 1
    cells = [{"subject": s, "nclass": nc, "model": model, "correct_trials": count[0],
              "trials": count[1], "accuracy": count[0] / count[1]}
             for (s, nc, model), count in counts.items()]
    summaries = [{"nclass": nc, "model": model,
                  "subject_median_accuracy": median(c["accuracy"] for c in cells
                                                     if c["nclass"] == nc and c["model"] == model)}
                 for nc in CLASSES for model in MODELS]
    return {"schema": "finger017-recorded-panel-result/v1", "condition": expected_condition,
            "panel": {"MI": "Figure2A", "ME": "S7A"}[expected_condition],
            "assessment_sha256": expected_assessment_sha256,
            "prediction_sha256": digest(predictions), "source_trial_count": len(trials),
            "source_window_count": len(windows), "cells": cells, "summaries": summaries,
            "units": _units(),
            "paper_win": None, "scientific_outcome": "unknown", "readiness_promoted": False,
            "scope": "complete declared single-condition support and hard-vote arithmetic only"}


def compare_complete_panels(assessment, author, candidate, *, expected_assessment_sha256,
                            expected_condition="MI"):
    """Retain all126 paired replay-cell differences, not a victory threshold."""
    before = evaluate_panel(assessment, author, expected_assessment_sha256=expected_assessment_sha256,
                            expected_condition=expected_condition)
    after = evaluate_panel(assessment, candidate, expected_assessment_sha256=expected_assessment_sha256,
                           expected_condition=expected_condition)
    require(author["models"]["S2-F"] == candidate["models"]["S2-F"],
            "recorded control must be identical across comparison")
    deltas = []
    for b, a in zip(before["cells"], after["cells"]):
        require((b["subject"], b["nclass"], b["model"], b["trials"])
                == (a["subject"], a["nclass"], a["model"], a["trials"]), "paired cell support changed")
        if b["model"] in REPLAY_MODELS:
            deltas.append({"subject": b["subject"], "nclass": b["nclass"], "model": b["model"],
                           "author_accuracy": b["accuracy"], "candidate_accuracy": a["accuracy"],
                           "candidate_minus_author": a["accuracy"] - b["accuracy"]})
    return {"schema": "finger017-recorded-panel-comparison/v1", "author": before, "candidate": after,
            "paired_replay_cells": deltas, "units": _units(), "paper_win": None, "scientific_outcome": "unknown",
            "readiness_promoted": False,
            "limits": ["No source/model/exposure authenticity or independent biological replication established.",
                       "No qualified agreement/superiority rule, uncertainty calculation or SOTA assessment.",
                       "Recorded S2-F control is fixed; replay improvement is not new closed-loop human control.",
                       "Both condition-specific source inputs and human-learning attribution companions remain unqualified."]}


def compare_mi_me(assessments, authors, candidates, *, expected_assessment_sha256s):
    """Keep primary MI/Figure2A and companion ME/S7A complete and separate."""
    for label, obj in (("assessments", assessments), ("authors", authors),
                       ("candidates", candidates), ("external pins", expected_assessment_sha256s)):
        keys(obj, ("MI", "ME"), label)
    require(expected_assessment_sha256s["MI"] != expected_assessment_sha256s["ME"],
            "MI/ME assessment pins must remain distinct")
    return {"schema": "finger017-matched-mi-me-panels/v1", "units": _units(),
            "panels": {condition: compare_complete_panels(
                assessments[condition], authors[condition], candidates[condition],
                expected_assessment_sha256=expected_assessment_sha256s[condition],
                expected_condition=condition) for condition in ("MI", "ME")},
            "paper_win": None, "scientific_outcome": "unknown", "readiness_promoted": False,
            "scope": "two complete declared recorded-decoding panels, never pooled across MI/ME"}
