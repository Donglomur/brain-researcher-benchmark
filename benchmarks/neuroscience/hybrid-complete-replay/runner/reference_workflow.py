"""Complete trusted TRAIN-only reference path; no fitting on import."""
import hashlib
import json
import math
import os
import time
from collections import defaultdict
from pathlib import Path
from consumer import GROUPS, ContractError, outer_fold, training_view
from reference import Uniform, ContextCounts, RidgeSoftmax, select_reference, fit_ridge
from scoring import score_complete, paired_comparison
from model_artifact import from_model, encode_artifact, predict_artifact

NAMES = ("uniform", "context_counts", "ridge_train_selected", "family_train_selected")


def emit(path, value, cap=1048576):
    b = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    if len(b) > cap:
        raise ContractError("complete reference artifact bound")
    with Path(path).open("xb") as f:
        f.write(b); f.flush(); os.fsync(f.fileno())
    return {"path": str(path), "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}


def fit_all_references(decisions, output, deadline, *, expected_decisions=163135, expected_trials=4884):
    """Exactly720 inner plus80 final ridge fits; no held selection or omission."""
    output = Path(output); output.mkdir(mode=0o700)
    artifacts = output / "artifacts"; artifacts.mkdir(mode=0o700)
    ledgers = output / "ledgers"; ledgers.mkdir(mode=0o700)
    predictions = {name: [] for name in NAMES}; folds = []; scalar_error = 0.; inner_fits = 0; final_fits = 0
    for subject, session in sorted(GROUPS):
        if time.monotonic() >= deadline:
            raise ContractError("complete reference original deadline")
        train, test = outer_fold(decisions, subject, session)
        # The selector receives no test object, observation, target or summary.
        selected, trace = select_reference(train); inner_fits += 9
        ridge_spec = min((x for x in trace["ledger"] if x["family"] == "ridge"), key=lambda x: (x["mean"], x["penalty"]))
        if isinstance(selected, RidgeSoftmax):
            ridge = selected
            if ridge.fit_trace["penalty"] != ridge_spec["penalty"]:
                raise ContractError("selected ridge identity")
        else:
            ridge = fit_ridge(train, ridge_spec["penalty"])
        final_fits += 1
        models = {"uniform": Uniform(), "context_counts": ContextCounts(train),
                  "ridge_train_selected": ridge, "family_train_selected": selected}
        artifact_map = {}
        for name, model in models.items():
            artifact = from_model(model); body = encode_artifact(artifact)
            # Opaque host filenames avoid exposing source fold keys in mountinfo.
            path = artifacts / (os.urandom(16).hex() + ".json")
            with path.open("xb") as f: f.write(body)
            path.chmod(0o400)
            artifact_map[name] = {"path": str(path), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
            for d in test:
                host = model.predict(d.observation()); scalar = predict_artifact(artifact, d.observation())
                error = max(abs(a - b) for a, b in zip(host, scalar)); scalar_error = max(scalar_error, error)
                if error > 1e-11:
                    raise ContractError("whole artifact inference differs from admitted host reference")
                predictions[name].append((d.source_row, host))
        training = training_view(train)
        training_hash = hashlib.sha256(json.dumps(training, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        record = {"subject_private": subject, "held_session_private": session, "training_decisions": len(train),
            "held_decisions_private": len(test), "training_projection_sha256": training_hash,
            "selection": trace, "ridge_final_fit": ridge.fit_trace, "artifacts": artifact_map,
            "training_only": True, "outer_test_available_to_selector": False}
        folds.append(record)
        emit(ledgers / ("fold-%02d.json" % len(folds)), record, 65536)
    if len(folds) != 80 or inner_fits != 720 or final_fits != 80:
        raise ContractError("complete80-fold fitting workload")
    scores = {}
    submission_pins = {}
    for name in NAMES:
        scores[name] = score_complete(decisions, predictions[name], expected_decisions=expected_decisions, expected_trials=expected_trials)
        path = output / (name + ".predictions.jsonl"); digest = hashlib.sha256(); size = 0
        with path.open("xb") as f:
            for row, probs in predictions[name]:
                b = (json.dumps({"source_row": row, "probabilities": probs}, separators=(",", ":"), allow_nan=False) + "\n").encode()
                if len(b) > 512: raise ContractError("complete fixed-reference probability record bound")
                size += len(b)
                if size > 64 * 1024**2: raise ContractError("complete reference submission extent")
                f.write(b); digest.update(b)
        submission_pins[name] = {"path": str(path), "bytes": size, "sha256": digest.hexdigest()}
    comparisons = {name: paired_comparison(scores["family_train_selected"], scores[name]) for name in NAMES if name != "family_train_selected"}
    result = {"schema": "hybrid-complete-train-only-reference-v1", "complete_outer_folds": 80,
        "inner_ridge_fits": inner_fits, "final_ridge_fits": final_fits,
        "artifact_host_max_abs_probability_difference": scalar_error, "scores": scores,
        "comparisons_descriptive_not_frontier_claim": comparisons, "submissions": submission_pins,
        "artifact_manifest_private": folds, "authentic_counts": {"decisions": expected_decisions, "trials": expected_trials},
        "published_Julia_or_Float32_parity": False, "scientific_count_delta": 0}
    emit(output / "REFERENCE_RESULT.json", result, 2 * 1024**2)
    return result


def group_complete_trials(decisions):
    groups = []
    previous = None
    for d in decisions:
        key = (d.subject, d.session, d.trial)
        if key != previous:
            groups.append([]); previous = key
        groups[-1].append(d)
    return groups
