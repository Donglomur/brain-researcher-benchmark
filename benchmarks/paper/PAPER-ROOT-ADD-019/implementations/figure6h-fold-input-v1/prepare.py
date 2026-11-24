#!/usr/bin/env python3
"""Conditional Figure 6h fold inputs; no fitting, folds or secure execution."""
import argparse
from functools import lru_cache
import hashlib
import importlib.util
import json
from pathlib import Path

TASK = "PAPER-ROOT-ADD-019"
PINS = {
    "score": ("figure6h-oof-score-v1/score.py",
              "8a325fb671bd86f15f0e1c949483a27a58d98a6c277adc3fbc37114baffa43c0"),
    "project": ("figure6h-source-projection-v1/project.py",
                "95b5c3917e52dbe4c5039d5e4ef2ef12447a342fc3be2dd3b567f08a07c01f08"),
}


def need(value, message):
    if not value:
        raise ValueError(message)


@lru_cache(maxsize=1)
def dependencies():
    result = {}
    for name, (relative, expected) in PINS.items():
        path = Path(__file__).resolve().parents[1] / relative
        body = path.read_bytes()
        need(hashlib.sha256(body).hexdigest() == expected,
             name + " dependency changed; review before adoption")
        spec = importlib.util.spec_from_file_location("ach_fold_" + name, path)
        module = importlib.util.module_from_spec(spec)
        exec(compile(body, str(path), "exec"), module.__dict__)
        result[name] = module
    return result["score"], result["project"]


def prepare_fold(source_panel, manifest, fold):
    """Return (participant input, private receipt) for one captured source fold.

    The operator must isolate each fold's execution; multiple fold inputs let a
    persistent participant recover withheld labels from other training sets.
    Hashes/counts/joins here do not authenticate native observations or folds.
    """
    need(type(fold) is int and 1 <= fold <= 10, "fold must be an integer from 1 to 10")
    score, projection = dependencies()
    sessions = score.validate_manifest(manifest)
    panel = projection.project_complete_panel(source_panel)
    participant = {"schema": "ach_fig6h_fold_input_v1", "task": TASK,
                   "held_out_fold": fold, "sessions": []}
    mappings = []
    for i, (projected, session) in enumerate(zip(panel["sessions"], sessions), 1):
        need(projected["session_id"] == session["session_id"], "session identity/order mismatch")
        need(projected["rat_id"] == session["rat_id"], "rat identity mismatch")
        need(len(projected["unit_ids"]) == session["unit_count"], "unit count mismatch")
        need(projected["trial_ids"] == session["trial_ids"], "trial identity/order mismatch")
        need(projected["source_label_audit"]["literal_native_labels"] == session["labels"],
             "manifest labels differ from literal captured source labels")
        alias = "session_%02d" % i
        public_session = {"session_id": alias,
                          "feature_columns": [
                              {"unit_index_one_based": projected["unit_ids"].index(c["unit_id"]) + 1,
                               "time_s": c["time_s"]}
                              for c in projected["feature_columns"]],
                          "training": [], "held_out": []}
        mapping = {"session_id": alias, "source_session_id": session["session_id"],
                   "source_rat_id": session["rat_id"], "training": [], "held_out": []}
        for row, (trial, assigned, label, values) in enumerate(zip(
                session["trial_ids"], session["folds"], session["labels"],
                projected["trial_by_predictor_matrix"])):
            role = "held_out" if assigned == fold else "training"
            # Role-local aliases do not expose original trial names or indices,
            # nor permit joining a test row to another fold's training alias.
            trial_alias = role + "_%06d" % (len(public_session[role]) + 1)
            record = {"trial_id": trial_alias, "predictors": list(values)}
            if role == "training":
                record["label"] = label
            public_session[role].append(record)
            mapping[role].append({"trial_id": trial_alias, "source_trial_id": trial,
                                  "source_retained_row_zero_based": row})
        participant["sessions"].append(public_session)
        mappings.append(mapping)
    receipt = {"schema": "ach_fig6h_fold_input_receipt_v1", "task": TASK,
               "held_out_fold": fold, "participant_input_sha256": score.digest(participant),
               "operator_manifest_sha256": score.digest(manifest),
               "source_panel_sha256": score.digest(source_panel),
               "source_projection_sha256": score.digest(panel),
               "source_cohort_manifest_sha256": panel["source_cohort_manifest_sha256"],
               "sessions": mappings, "source_admission_established": False,
               "secure_execution_established": False, "readiness_promoted": False,
               "limits": [
                   "Operator private: never deliver this receipt, source panel or manifest to a participant.",
                   "Fresh isolated workers per fold and no shared state/artifact access require external enforcement.",
                   "No original cohort, native fold realization, source labels, model run or paper outcome is qualified.",
                   "Source preprocessing ambiguities and selected-CV bias are unchanged."]}
    return participant, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-panel", required=True, help="operator-only neutral source export JSON")
    parser.add_argument("--manifest", required=True, help="operator-only original OOF manifest JSON")
    parser.add_argument("--fold", type=int, required=True)
    parser.add_argument("--participant-output", required=True, help="fresh participant-input JSON")
    parser.add_argument("--operator-receipt", required=True, help="fresh private receipt in a separate directory")
    args = parser.parse_args()
    public_path = Path(args.participant_output)
    private_path = Path(args.operator_receipt)
    need(public_path.resolve().parent != private_path.resolve().parent,
         "participant output and operator receipt require separate directories")
    need(not public_path.exists() and not private_path.exists(), "output already exists")
    score, _ = dependencies()
    public, private = prepare_fold(score.load_json(args.source_panel),
                                   score.load_json(args.manifest), args.fold)
    # Preflight both files before writing. Exclusive creation also refuses a
    # path that appears after preflight. External permissions remain required.
    for path, value in ((private_path, private), (public_path, public)):
        with path.open("x", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, allow_nan=False)
            handle.write("\n")


if __name__ == "__main__":
    main()
