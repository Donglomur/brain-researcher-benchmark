"""NEDS binned-trial reference and complete-cohort paired evaluator.

Constructed implementation; native author model/data qualification remains unknown.
Only NumPy and the Python standard library are required. No network operations.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
import numpy as np

COMMIT = "61d2ef65556dbbc2b828d542f19bd4e7134c92f3"
FIELDS = ("spike", "choice", "block", "wheel", "whisker")
BEHAVIORS = FIELDS[1:]
ENCODING = ("encode_all",) + tuple("encode_" + x for x in BEHAVIORS)
TASKS = ENCODING + ("decode_all",)
CLASSES = {"choice": [-1, 1], "block": [0.2, 0.5, 0.8]}
GATES = ["exact_ONE_objects_revisions_checksums", "EID_PID_animal_identity_join",
         "paper_2Hz_vs_source_greater_than_5Hz_unit_eligibility", "camera_selection_and_preprocessing_parity",
         "native_author_model_and_task_specific_training_recipes", "full_cohort_authentic_execution",
         "protected_reference_outputs_numeric_tolerances", "data_code_weight_rights_and_exposure",
         "matched_training_resource_measurement"]

class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def array(value, name, ndim=None):
    try:
        x = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"{name}: numeric array required") from exc
    require(x.size > 0 and np.isfinite(x).all(), f"{name}: empty/nonfinite array")
    require(ndim is None or x.ndim == ndim, f"{name}: wrong rank")
    return x


def unique_ids(values, name):
    require(isinstance(values, list) and values and
            all(isinstance(x, str) and x for x in values), f"{name}: nonempty string IDs required")
    require(len(set(values)) == len(values), f"{name}: duplicate IDs")
    return values


def load_roster():
    return json.loads(Path(__file__).with_name("cohort.json").read_text())


def validate_session(session):
    require(isinstance(session, dict), "session must be object")
    require(set(session) == {"eid", "animal_id", "bin_width_seconds", "unit_ids", "source_identity", "train", "validation", "test"},
            "session fields differ from closed schema (auxiliary target aliases prohibited)")
    require(isinstance(session["animal_id"], str) and session["animal_id"], "animal_id required")
    require(session["bin_width_seconds"] == 0.02, "source bin width must be 0.02 seconds")
    require(isinstance(session["source_identity"], dict) and session["source_identity"], "source identity declaration required")
    units = unique_ids(session["unit_ids"], "unit_ids")
    seen = set()
    for split in ("train", "validation", "test"):
        d = session[split]
        require(isinstance(d, dict) and set(d) == {"trial_ids", *FIELDS}, f"{split}: closed fields required")
        ids = unique_ids(d["trial_ids"], split + " trial_ids")
        require(not seen.intersection(ids), "trial identity overlap across train/validation/test")
        seen.update(ids)
        spike = array(d["spike"], split + ".spike", 3)
        require(spike.shape == (len(ids), 100, len(units)), "spikes must be trial x 100 bins x unit")
        require((spike >= 0).all() and np.equal(spike, np.floor(spike)).all(), "spikes must be nonnegative counts")
        for field in ("wheel", "whisker"):
            require(array(d[field], field, 2).shape == spike.shape[:2], field + ": wrong shape")
        for field, classes in CLASSES.items():
            x = array(d[field], field, 1)
            require(len(x) == len(ids) and np.isin(x, classes).all(), field + ": invalid source labels")
    return session


def validate_bundle(bundle, engineering_subset=False):
    require(set(bundle) == {"schema", "source_commit", "evidence_kind", "sessions"}, "bundle fields differ from schema")
    require(bundle["schema"] == "neds-binned-panel-v1" and bundle["source_commit"] == COMMIT, "schema/source commit mismatch")
    require(bundle["evidence_kind"] in ("generated_engineering", "operator_supplied_unqualified"), "evidence_kind invalid")
    require(isinstance(bundle["sessions"], list) and bundle["sessions"], "sessions required")
    roster = load_roster()
    training, heldout = set(roster["training_eids"]), set(roster["heldout_eids"])
    ids = unique_ids([s["eid"] for s in bundle["sessions"]], "session eids")
    require(set(ids) <= training | heldout, "unknown source session EID")
    if engineering_subset:
        require(bundle["evidence_kind"] == "generated_engineering", "subset mode is only for generated engineering controls")
    else:
        require(set(ids) == training | heldout, "complete 74 training + 10 heldout session roster required")
    subject_splits = {}
    for s in bundle["sessions"]:
        validate_session(s)
        cohort = "training" if s["eid"] in training else "heldout"
        require(subject_splits.setdefault(s["animal_id"], cohort) == cohort,
                "animal crosses source training/heldout cohorts")
    return {s["eid"]: s for s in bundle["sessions"]}


def allowed_fields(task):
    require(task in TASKS, "unknown task mask")
    if task == "decode_all":
        return ("spike",)
    if task == "encode_all":
        return BEHAVIORS
    return (task.removeprefix("encode_"),)


def input_packet(session, split, task):
    """Only observable modalities, no target arrays, null rates or aliases."""
    require(split in ("train", "validation", "test"), "unknown split")
    d = session[split]
    # Deep-copy through JSON; callers cannot mutate operator targets by aliasing.
    packet = {"eid": session["eid"], "trial_ids": d["trial_ids"], "task": task,
              "unit_ids": session["unit_ids"], "bin_width_seconds": 0.02,
              "inputs": {f: d[f] for f in allowed_fields(task)}}
    return json.loads(json.dumps(packet, allow_nan=False))


def bits_per_spike(counts, rates, train_counts=None):
    """Source metric: per-neuron eval-mean null, then unweighted valid-unit mean.

    train_counts changes ONLY a separately labeled supplemental null. Values are
    expected counts per 20ms bin, never Hz. Zero-rate floor follows pinned source.
    The factorial terms cancel in the log-likelihood difference.
    """
    y, p = array(counts, "counts", 3), array(rates, "rates", 3)
    require(y.shape == p.shape and (p >= 0).all(), "rate shape/negative rates")
    require((y >= 0).all() and (y == np.floor(y)).all(), "invalid spike counts")
    null_source = y if train_counts is None else array(train_counts, "train_counts", 3)
    require(null_source.shape[-1] == y.shape[-1] and (null_source >= 0).all(), "null neuron mismatch/counts")
    null = null_source.mean(axis=(0, 1))
    null = np.where(null == 0, 1e-9, null)
    safe = np.where(p == 0, 1e-9, p)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        gain = (null - safe + y * (np.log(safe) - np.log(null))).sum(axis=(0, 1))
    require(np.isfinite(gain).all(), "Poisson score exceeds finite numeric range")
    totals = y.sum(axis=(0, 1))
    values = [float(gain[i] / totals[i] / np.log(2)) if totals[i] > 0 else None for i in range(len(totals))]
    valid = [v for v in values if v is not None]
    require(all(np.isfinite(v) for v in valid), "bits-per-spike exceeds finite numeric range")
    # Sum scaled values to avoid overflowing a representable mean.
    session_mean = float(np.sum(np.asarray(valid) / len(valid))) if valid else None
    require(session_mean is None or np.isfinite(session_mean), "bits-per-spike mean exceeds finite numeric range")
    return {"per_unit": values, "session_mean": session_mean,
            "zero_spike_unit_indices": np.flatnonzero(totals == 0).tolist(),
            "null": "evaluation_mean_source" if train_counts is None else "training_mean_prospective"}


def r_squared(y, prediction):
    y, p = array(y, "continuous target"), array(prediction, "continuous prediction")
    require(y.shape == p.shape and y.size >= 2, "continuous target/prediction shape or support")
    with np.errstate(over="ignore", invalid="ignore"):
        residual = float(np.sum((y - p) ** 2))
        variance = float(np.sum((y - y.mean()) ** 2))
    require(np.isfinite(residual) and np.isfinite(variance), "R2 exceeds finite numeric range")
    # sklearn's force_finite default: explicit and visible, never hide degeneracy.
    value = float(1 - residual / variance) if variance else float(residual == 0)
    require(np.isfinite(value), "R2 result exceeds finite numeric range")
    return {"r2": value,
            "constant_target": variance == 0, "sample_count": int(y.size)}


def classification(y, prediction, field):
    y, p = array(y, field, 1), array(prediction, field + " prediction", 1)
    require(y.shape == p.shape and np.isin(y, CLASSES[field]).all() and np.isin(p, CLASSES[field]).all(), "invalid class predictions")
    recalls = {str(c): float(np.mean(p[y == c] == c)) for c in CLASSES[field] if np.any(y == c)}
    return {"accuracy": float(np.mean(y == p)), "balanced_accuracy": float(np.mean(list(recalls.values()))),
            "class_recalls": recalls, "absent_classes": [c for c in CLASSES[field] if not np.any(y == c)]}


def _features(packet, static=False):
    inputs = packet["inputs"]
    n, t = len(packet["trial_ids"]), 100
    features = []
    for field in allowed_fields(packet["task"]):
        x = np.asarray(inputs[field], dtype=float)
        if field in CLASSES:
            x = (x[:, None] == np.asarray(CLASSES[field])[None, :]).astype(float)
            x = np.repeat(x[:, None, :], t, axis=1)
        elif x.ndim == 2:
            x = x[:, :, None]
        features.append(x)
    x = np.concatenate(features, axis=2)
    return x.mean(axis=1) if static else x.reshape(n * t, -1)


def _ridge(train_x, train_y, apply_x, regularization):
    mean, sd = train_x.mean(axis=0), train_x.std(axis=0)
    sd[sd == 0] = 1
    x = (train_x - mean) / sd
    z = (apply_x - mean) / sd
    target_mean = train_y.mean(axis=0)
    w = np.linalg.solve(x.T @ x + regularization * np.eye(x.shape[1]), x.T @ (train_y - target_mean))
    prediction = z @ w + target_mean
    require(np.isfinite(mean).all() and np.isfinite(sd).all() and np.isfinite(w).all() and np.isfinite(prediction).all(), "ridge exceeds finite numeric range")
    return prediction


def reference_predictions(session):
    """Prospective train-only ridge; validation selects lambda, test never fits.

    Encoding fits log1p counts. Decoding fits continuous behavior or one-hot
    class scores. This is NOT the paper's undocumented classical baseline.
    """
    predictions, recipes = {}, {}
    for task in TASKS:
        fields = ("spike",) if task in ENCODING else BEHAVIORS
        packets = {s: input_packet(session, s, task) for s in ("train", "validation", "test")}
        outputs = {}
        for field in fields:
            static = field in CLASSES
            xs = {s: _features(packets[s], static) for s in packets}
            ys = {s: np.asarray(session[s][field], dtype=float) for s in packets}
            original_shape = ys["test"].shape
            if static:
                targets = (ys["train"][:, None] == np.asarray(CLASSES[field])[None, :]).astype(float)
            elif field == "spike":
                targets = np.log1p(ys["train"].reshape(-1, ys["train"].shape[-1]))
            else:
                targets = ys["train"].reshape(-1, 1)
            def convert(z, shape):
                if static:
                    return np.asarray(CLASSES[field])[z.argmax(axis=1)]
                if field == "spike":
                    # Prospective clipping bounds prevent numerical overflow, not source model semantics.
                    return np.maximum(np.expm1(np.clip(z, -20, 20)), 0).reshape(shape)
                return z.reshape(shape)
            scored = []
            for regularization in (0.1, 1.0, 10.0):
                pred = convert(_ridge(xs["train"], targets, xs["validation"], regularization), ys["validation"].shape)
                if static:
                    loss = float(np.mean(pred != ys["validation"]))
                elif field == "spike":
                    loss = float(np.mean(pred - ys["validation"] * np.log(np.maximum(pred, 1e-9))))
                else:
                    loss = float(np.mean((pred - ys["validation"]) ** 2))
                require(np.isfinite(loss), "reference validation loss exceeds finite numeric range")
                scored.append((loss, regularization))
            selected = min(scored)[1]
            outputs[field] = convert(_ridge(xs["train"], targets, xs["test"], selected), original_shape).tolist()
            recipes[task + ":" + field] = {"lambda": selected, "validation_loss": min(scored)[0]}
        predictions[task] = outputs
    return predictions, recipes


def score_session(session, predictions):
    require(isinstance(predictions, dict) and set(predictions) == set(TASKS), "all six exact task masks required")
    report, endpoint = {}, {}
    for task in TASKS:
        fields = ("spike",) if task in ENCODING else BEHAVIORS
        require(set(predictions[task]) == set(fields), "task output fields mismatch")
        if task in ENCODING:
            score = bits_per_spike(session["test"]["spike"], predictions[task]["spike"])
            score["training_null_diagnostic"] = bits_per_spike(session["test"]["spike"], predictions[task]["spike"], session["train"]["spike"])
            report[task] = score
            endpoint[task + ":bits_per_spike"] = score["session_mean"]
        else:
            report[task] = {}
            for field in BEHAVIORS:
                if field in CLASSES:
                    s = classification(session["test"][field], predictions[task][field], field)
                    endpoint[field + ":accuracy"] = s["accuracy"]
                else:
                    s = r_squared(session["test"][field], predictions[task][field])
                    endpoint[field + ":r2"] = s["r2"]
                report[task][field] = s
    return {"metrics": report, "endpoints": endpoint}


def make_receipt(session, method, predictions, budget_contract, pretrained_eids=None):
    """Build a declaration for integration; does not prove native training or isolation."""
    return {"eid": session["eid"], "method": method, "predictions": predictions,
            "trial_ids": session["test"]["trial_ids"], "unit_ids": session["unit_ids"],
            "fit_trial_ids": session["train"]["trial_ids"], "validation_trial_ids": session["validation"]["trial_ids"],
            "pretrained_eids": sorted(pretrained_eids or []), "budget_contract": budget_contract,
            "packet_sha256": {task: digest(input_packet(session, "test", task)) for task in TASKS}}


def _validate_receipt(session, row, methods, training_eids):
    require(set(row) == {"eid", "method", "predictions", "trial_ids", "unit_ids", "fit_trial_ids", "validation_trial_ids", "pretrained_eids", "budget_contract", "packet_sha256"}, "prediction receipt fields mismatch")
    require(row["method"] in methods, "unexpected method")
    for key, expected in (("trial_ids", session["test"]["trial_ids"]), ("unit_ids", session["unit_ids"]),
                          ("fit_trial_ids", session["train"]["trial_ids"]), ("validation_trial_ids", session["validation"]["trial_ids"])):
        require(row[key] == expected, "prediction receipt identity mismatch: " + key)
    require(isinstance(row["pretrained_eids"], list) and all(isinstance(x, str) for x in row["pretrained_eids"]), "pretraining EIDs must be list")
    require(len(set(row["pretrained_eids"])) == len(row["pretrained_eids"]) and set(row["pretrained_eids"]) <= training_eids, "pretraining leaks heldout/unknown EIDs")
    require(isinstance(row["budget_contract"], str) and row["budget_contract"], "budget declaration required")
    require(row["packet_sha256"] == {task: digest(input_packet(session, "test", task)) for task in TASKS}, "input packet hash/mask mismatch")


def summarize(rows, methods, draws=1000, seed=0):
    require(isinstance(draws, int) and 1 <= draws <= 100000, "bootstrap draw count invalid")
    rng = np.random.default_rng(seed)
    result = {}
    for cohort in ("training", "heldout"):
        group = [r for r in rows if r["cohort"] == cohort]
        if not group:
            continue
        endpoints = sorted(group[0]["scores"][methods[0]]["endpoints"])
        animals = sorted({r["animal_id"] for r in group})
        summary = {"sessions": len(group), "declared_animal_clusters": len(animals), "endpoints": {}}
        for endpoint in endpoints:
            values = {m: [r["scores"][m]["endpoints"][endpoint] for r in group] for m in methods}
            missing = [r["eid"] for i, r in enumerate(group) if any(values[m][i] is None for m in methods)]
            item = {"session_macro": {m: float(np.mean(values[m])) if not missing else None for m in methods},
                    "unscoreable_session_eids": missing}
            # No implicit complete-case removal; an undefined session blocks aggregate inference.
            if len(methods) == 2 and not missing:
                differences = np.array(values[methods[0]]) - np.array(values[methods[1]])
                item["paired_session_macro_difference"] = float(differences.mean())
                cluster_means = np.array([np.mean([differences[i] for i, r in enumerate(group) if r["animal_id"] == a]) for a in animals])
                item["paired_animal_macro_difference"] = float(cluster_means.mean())
                if len(animals) >= 2:
                    boot = cluster_means[rng.integers(0, len(animals), size=(draws, len(animals)))].mean(axis=1)
                    item["conditional_animal_bootstrap_95pct"] = np.quantile(boot, [0.025, 0.975]).tolist()
                else:
                    item["conditional_animal_bootstrap_95pct"] = None
            summary["endpoints"][endpoint] = item
        if len(methods) == 2:
            ds = [v.get("paired_session_macro_difference") for v in summary["endpoints"].values()]
            summary["pareto_relation"] = "undefined" if None in ds else (
                "first_dominates" if all(x >= 0 for x in ds) and any(x > 0 for x in ds) else
                "second_dominates" if all(x <= 0 for x in ds) and any(x < 0 for x in ds) else
                "tie" if all(x == 0 for x in ds) else "tradeoff")
        result[cohort] = summary
    return result


def evaluate(bundle, submissions=None, methods=("multitask", "task_specific"), engineering_subset=False, draws=1000, seed=0):
    sessions = validate_bundle(bundle, engineering_subset)
    roster = load_roster()
    training = set(roster["training_eids"])
    records = {}
    reference_recipes = {}
    if submissions is None:
        methods = ("prospective_ridge_reference",)
        for eid, session in sessions.items():
            preds, reference_recipes[eid] = reference_predictions(session)
            records[(eid, methods[0])] = preds
    else:
        require(len(methods) == 2 and len(set(methods)) == 2 and all(isinstance(x, str) and x for x in methods), "two distinct method names required")
        require(isinstance(submissions, list), "submissions must be list")
        paired_budget = {}
        paired_pretraining = {}
        for row in submissions:
            require(row["eid"] in sessions, "submission unknown session")
            session = sessions[row["eid"]]
            _validate_receipt(session, row, methods, training)
            key = (row["eid"], row["method"])
            require(key not in records, "duplicate method/session prediction")
            require(paired_budget.setdefault(row["eid"], row["budget_contract"]) == row["budget_contract"], "paired budget declarations differ")
            require(paired_pretraining.setdefault(row["eid"], sorted(row["pretrained_eids"])) == sorted(row["pretrained_eids"]), "paired pretraining exposure differs")
            records[key] = row["predictions"]
        require(set(records) == {(eid, m) for eid in sessions for m in methods}, "missing paired session/method outputs")
    rows = []
    for eid, session in sessions.items():
        rows.append({"eid": eid, "animal_id": session["animal_id"], "cohort": "training" if eid in training else "heldout",
                     "evaluation_regime": "seen_session_heldout_trials" if eid in training else "heldout_session_within_session_finetune",
                     "scores": {m: score_session(session, records[(eid, m)]) for m in methods}})
    return {"task_id": "PAPER-paper-method-replacement-005", "implementation": "initial-evaluator-v1",
            "source_commit": COMMIT, "bundle_sha256": digest(bundle), "evidence_kind": bundle["evidence_kind"],
            "scope": "engineering_subset" if engineering_subset else "complete_84_source_session_membership",
            "scientific_qualification": "unknown", "unresolved_gates": GATES,
            "mask_isolation": "closed_array_packets_and_hash_binding_only_not_process_or_training_proof",
            "animal_inference": "conditional_on_declared_join_unverified_no_qualified_confidence_claim",
            "methods": list(methods), "submission_sha256": digest(submissions) if submissions is not None else None,
            "declared_exposure_and_budget": [{k: r[k] for k in ("eid", "method", "fit_trial_ids", "validation_trial_ids", "pretrained_eids", "budget_contract")} for r in submissions] if submissions is not None else [],
            "session_results": rows,
            "summaries": summarize(rows, methods, draws, seed), "reference_recipes": reference_recipes,
            "bootstrap": {"draws": draws, "seed": seed, "unit": "declared_animal", "estimand": "equal_animal_mean_of_within_animal_session_differences"},
            "source_departures": ["all_trials_scored_not_final_dataloader_batch", "complete_support_required_no_silent_session_nanmean", "prospective_ridge_and_validation_selection", "unverified_declared_animal_bootstrap"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--submissions", type=Path)
    parser.add_argument("--methods", nargs=2, default=["multitask", "task_specific"])
    parser.add_argument("--engineering-subset", action="store_true")
    parser.add_argument("--bootstrap-draws", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    bundle = json.loads(args.bundle.read_text())
    submissions = json.loads(args.submissions.read_text()) if args.submissions else None
    result = evaluate(bundle, submissions, tuple(args.methods), args.engineering_subset, args.bootstrap_draws, args.seed)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")

if __name__ == "__main__":
    main()
