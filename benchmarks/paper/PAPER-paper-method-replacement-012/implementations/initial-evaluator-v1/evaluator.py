"""Owner-side NuCLR Bugeon readout; no dataset, pickle or model loading.

Equations and readout hyperparameters follow nuclr 0fa409b304147ace00507063d44f03155691af62.
This module is an initial construction component, not a qualified paper benchmark.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import time
import warnings

TASK_ID = "PAPER-paper-method-replacement-012"
SOURCE_COMMIT = "0fa409b304147ace00507063d44f03155691af62"
CONTRACT_SHA256 = "f754a7dba9f43a270143fe1bcd0654a29d4d660626724a07e81593d50dde1bff"
SB028_SESSIONS = frozenset(f"sb028_{day}" for day in
                         ("20191106", "20191107", "20191108", "20191112", "20191113"))
INDUCTIVE_TEST_SESSIONS = SB028_SESSIONS - {"sb028_20191106"}
DEV_SESSIONS = frozenset(("sb025_20191004", "sb026_20191011", "sb028_20191106", "sb030_20200108"))
SOURCE_SESSIONS = frozenset((
    "sb025_20191007", "sb025_20191004", "sb025_20191008", "sb025_20191009", "sb025_20191023", "sb025_20191024",
    "sb026_20191011", "sb026_20191014", "sb026_20191016",
    "sb028_20191106", "sb028_20191107", "sb028_20191108", "sb028_20191112", "sb028_20191113",
    "sb030_20200108", "sb030_20200110", "sb030_20200128"))
SOURCE_LABELS = {
    "ei": frozenset(("EC", "IN")),
    "subclass": frozenset(("Lamp5", "Pvalb", "Vip", "Sncg", "Sst")),
    "11class": frozenset(("Lamp5-Chrna7", "Lamp5-Npy", "Lamp5-Tmem182", "Pvalb-Tac1", "Pvalb-Vipr2",
                          "Sncg-Pdzrn3", "Sncg-Vip", "Sst-Reln", "Sst-Tac1", "Vip-Cp", "Vip-Reln")),
}
HOLDS = [
    "Author split/metadata archive bytes, neuron identities and calcium/transcriptomic joins require authentic acquisition validation.",
    "The December 2025 split pack is not established equivalent to the paper-era split protocol.",
    "Cross-session repeated-cell linkage remains unresolved; session-local unit IDs do not prove biological independence.",
    "Native NuCLR representation and context-ablation runs, competent reference outputs and numeric tolerances remain unqualified.",
    "Author metadata/split redistribution terms remain unresolved separately from Apache-2.0 code and CC-BY-4.0 Bugeon data.",
    "A protected process and independent final panel, matched noncode resources, paired improvement inference and native resource envelope remain required.",
]


class ContractError(ValueError):
    """Reject malformed, incomplete or incompatible owner-side evaluation input."""


def _need(condition, message):
    if not condition:
        raise ContractError(message)


def _ids(value, name, nonempty=True):
    _need(isinstance(value, list) and (bool(value) or not nonempty), f"{name}: expected list")
    _need(all(isinstance(v, str) and v for v in value), f"{name}: IDs must be nonempty strings")
    _need(len(value) == len(set(value)), f"{name}: duplicate IDs")
    return set(value)


def _digest(value, name):
    _need(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), f"{name}: expected sha256")


def canonical_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def session_metadata(session_id, ttypes, activity_neuron_count):
    """Reproduce source session-local identity and EI/subclass derivation.

    This validates the array-to-neuron count join but does not resolve repeated cells
    or produce the author split-file 11-class label map.
    """
    _need(isinstance(session_id, str) and re.fullmatch(r"sb[0-9]+_[0-9]{8}", session_id), "invalid session_id")
    _need(isinstance(ttypes, list) and ttypes and all(isinstance(t, str) and t for t in ttypes), "invalid ttypes")
    _need(type(activity_neuron_count) is int and activity_neuron_count == len(ttypes), "activity/neuron count mismatch")
    return [{"id": f"{session_id}_u{i}", "session_id": session_id,
             "subject_id": session_id.split("_")[0], "source_neuron_index": i,
             "ttype": t, "ei_class": t if t in ("IN", "EC") else "IN",
             "subclass": "unknown" if t in ("IN", "EC") else t.split("-")[0]}
            for i, t in enumerate(ttypes)]


def classification_metrics(true, pred, vocabulary=None):
    """Source sklearn defaults: balanced accuracy over true-present labels;
    macro F1 over union(true, pred), including predicted-only labels with zero F1.
    Missing vocabulary classes are reported, not silently scored as source classes.
    """
    _need(isinstance(true, list) and true and isinstance(pred, list) and len(true) == len(pred), "nonempty matched labels required")
    _need(all(isinstance(x, str) and x for x in true + pred), "labels must be nonempty strings")
    observed = sorted(set(true) | set(pred))
    if vocabulary is not None:
        vocab = _ids(vocabulary, "vocabulary")
        _need(set(observed) <= vocab, "label outside frozen vocabulary")
    else:
        vocab = set(observed)
    confusion = {a: {b: 0 for b in sorted(vocab)} for a in sorted(vocab)}
    for a, b in zip(true, pred):
        confusion[a][b] += 1
    per_class = {}
    for label in sorted(vocab):
        tp = confusion[label][label]
        support = sum(confusion[label].values())
        predicted = sum(confusion[a][label] for a in vocab)
        per_class[label] = {"support": support, "predicted": predicted,
                            "precision": tp / predicted if predicted else 0.0,
                            "recall": tp / support if support else None,
                            "f1": 2 * tp / (support + predicted) if support + predicted else None}
    recalls = [v["recall"] for v in per_class.values() if v["support"]]
    f1s = [per_class[label]["f1"] for label in observed]
    return {"n": len(true), "accuracy": sum(a == b for a, b in zip(true, pred)) / len(true),
            "balanced_accuracy": sum(recalls) / len(recalls), "macro_f1": sum(f1s) / len(f1s),
            "observed_metric_labels": observed, "absent_true_labels": sorted(vocab - set(true)),
            "per_class": per_class, "confusion": confusion}


def _metadata(packet, all_ids):
    rows = packet.get("metadata")
    _need(isinstance(rows, list), "metadata required")
    _need(all(isinstance(r, dict) for r in rows), "metadata rows must be objects")
    row_ids = _ids([r.get("id") for r in rows], "metadata IDs")
    _need(row_ids == all_ids, "metadata must cover exactly all labeled IDs")
    result = {r["id"]: r for r in rows}
    for uid, row in result.items():
        session = row.get("session_id")
        _need(isinstance(session, str) and re.fullmatch(r"sb[0-9]+_[0-9]{8}", session), "invalid metadata session")
        _need(isinstance(row.get("subject_id"), str) and row["subject_id"].lower() == session.split("_")[0], "subject/session mismatch")
        idx = row.get("source_neuron_index")
        _need(type(idx) is int and idx >= 0 and uid == f"{session}_u{idx}", "source neuron identity mismatch")
        _need(row.get("repeated_cell_id") is None or isinstance(row["repeated_cell_id"], str) and row["repeated_cell_id"], "invalid repeated_cell_id")
    return result


def validate_packet(packet):
    """Validate frozen owner-side JSON projection before any readout fit.

    The projection is not an authenticator of archive acquisition, legal rights or
    representation exposure. Those gates remain open even when declared hashes exist.
    """
    _need(isinstance(packet, dict), "packet must be an object")
    _need(type(packet.get("schema_version")) is int and packet["schema_version"] == 1 and packet.get("task_id") == TASK_ID, "packet identity/version mismatch")
    _need(packet.get("source_commit") == SOURCE_COMMIT, "source revision mismatch")
    _need(packet.get("input_role") in ("generated_engineering_control", "authentic_candidate"), "input role must be explicit")
    _need(packet.get("label_level") in ("ei", "subclass", "11class"), "unsupported label level")
    panel = packet.get("panel")
    _need(panel in ("inductive_zero_shot", "transductive", "transductive_zero_shot"), "one of the three source evaluation panels required")
    _need(packet.get("context_variant") in ("population_context", "ablated_context"), "context variant required")
    _need(packet.get("class_balance") in ("weight", "resample"), "class balance must be explicit")
    provenance = packet.get("provenance", {})
    _need(isinstance(provenance, dict), "provenance object required")
    for key in ("split_sha256", "metadata_sha256", "data_receipt_sha256"):
        _digest(provenance.get(key), key)
    _need(provenance.get("split_release") in ("paper_era_candidate", "december_2025_current", "other_explicit"), "split release must be distinguished")
    _need(isinstance(provenance.get("split_release_detail"), str) and provenance["split_release_detail"].strip(), "split release detail required")
    suffix = {"inductive_zero_shot": "inductive_zs", "transductive": "transductive", "transductive_zero_shot": "transductive_zs"}[panel]
    members = [f"{packet['label_level']}_{suffix}.pkl"]
    _need(provenance.get("split_member") in members, "author split member/panel/label mismatch")
    vocabulary = packet.get("label_vocabulary")
    vocab = _ids(vocabulary, "label_vocabulary")
    _need(len(vocab) >= 2, "at least two label classes required")
    _need(len(vocab) == {"ei": 2, "subclass": 5, "11class": 11}[packet["label_level"]], "label vocabulary cardinality mismatch")
    label_encoding = packet.get("source_label_mapping")
    _need(isinstance(label_encoding, dict) and set(label_encoding) == vocab, "source label mapping must cover exact vocabulary")
    _need(all(isinstance(v, str) for v in label_encoding.values()), "source labels must be strings")
    _need(set(label_encoding.values()) == SOURCE_LABELS[packet["label_level"]], "source label mapping must be bijective to published label family")
    label_map = packet.get("label_map")
    _need(isinstance(label_map, dict) and label_map, "author label_map required")
    all_ids = _ids(list(label_map), "label_map IDs")
    _need(all(isinstance(v, str) and v in vocab for v in label_map.values()), "label outside frozen vocabulary")
    metadata = _metadata(packet, all_ids)
    source_sessions = _ids(packet.get("source_session_manifest"), "source session manifest")
    _need({r["session_id"] for r in metadata.values()} <= source_sessions, "labeled unit session absent from source manifest")
    if packet["input_role"] == "authentic_candidate":
        _need(source_sessions == SOURCE_SESSIONS, "authentic candidate requires complete 17-session source manifest; acquisition still unverified")
    training_sessions = _ids(packet.get("representation_training_sessions"), "representation training sessions")
    _need(all(re.fullmatch(r"sb[0-9]+_[0-9]{8}", s) for s in training_sessions | source_sessions), "invalid session manifest")
    _need(training_sessions <= source_sessions, "training session absent from source manifest")
    if panel == "inductive_zero_shot":
        _need(all(s.split("_")[0] != "sb028" for s in training_sessions), "inductive representation training includes SB028")
    if packet["input_role"] == "authentic_candidate":
        expected_training = SOURCE_SESSIONS - SB028_SESSIONS if panel == "inductive_zero_shot" else SOURCE_SESSIONS
        _need(training_sessions == expected_training, "representation training session manifest must retain source population")
    checkpoints = packet.get("checkpoints")
    _need(isinstance(checkpoints, list) and checkpoints, "ordered checkpoints required")
    _ids([c.get("id") for c in checkpoints if isinstance(c, dict)], "checkpoint IDs")
    _need(all(isinstance(c, dict) for c in checkpoints), "checkpoint object required")
    previous_epoch = -1
    ordered_ids = None
    dimensions = None
    for checkpoint in checkpoints:
        epoch = checkpoint.get("epoch")
        _need(type(epoch) is int and epoch >= 0 and epoch > previous_epoch, "checkpoint epochs must be strictly increasing")
        previous_epoch = epoch
        _need(_ids(checkpoint.get("ids"), "checkpoint unit IDs") == all_ids, "checkpoint must cover complete author label_map")
        if ordered_ids is None:
            ordered_ids = checkpoint["ids"]
        _need(checkpoint["ids"] == ordered_ids, "checkpoint ID order mismatch")
        values = checkpoint.get("embeddings")
        _need(isinstance(values, list) and len(values) == len(ordered_ids), "embedding row mismatch")
        _need(all(isinstance(row, list) and row for row in values), "nonempty embedding rows required")
        width = len(values[0])
        _need(all(len(row) == width for row in values), "ragged embeddings")
        _need(all(type(v) in (int, float) and math.isfinite(v) for row in values for v in row), "embeddings must be finite numbers")
        if dimensions is None:
            dimensions = width
        _need(width == dimensions, "checkpoint embedding dimensions differ")
    splits = packet.get("splits")
    _need(isinstance(splits, list) and splits, "complete author splits required")
    _ids([s.get("id") for s in splits if isinstance(s, dict)], "split IDs")
    normalized = []
    for split in splits:
        _need(isinstance(split, dict), "split object required")
        test = _ids(split.get("test"), "test IDs")
        _need(test <= all_ids, "unknown test ID")
        _need(("train_cv" in split) != ("val" in split), "exactly one author CV form required")
        train = _ids(split["train"], "train IDs") if "train" in split else all_ids - test
        _need(train and train <= all_ids and not train & test, "train/test overlap or unknown IDs")
        if "train_cv" in split:
            folds = split["train_cv"]
            _need(isinstance(folds, list) and folds, "nonempty train_cv required")
            cv = []
            for fold in folds:
                _need(isinstance(fold, dict), "CV fold object required")
                fit_ids = _ids(fold.get("train"), "CV train IDs")
                val_ids = _ids(fold.get("val"), "CV val IDs")
                _need(fit_ids <= train and val_ids <= train and not fit_ids & val_ids, "CV crosses test/train boundary or overlaps")
                cv.append((fit_ids, val_ids))
            final_train = train
            coverage = train | test
        else:
            _need("train" in split, "single-val split needs explicit train IDs")
            val = _ids(split["val"], "val IDs")
            _need(val <= all_ids and not val & (train | test), "val overlaps train/test or has unknown IDs")
            cv = [(train, val)]
            final_train = train | val
            coverage = final_train | test
        excluded = split.get("excluded", {})
        _need(isinstance(excluded, dict) and all(isinstance(reason, str) and reason.strip() for reason in excluded.values()), "excluded IDs need explicit source reasons")
        excluded_ids = _ids(list(excluded), "excluded IDs", nonempty=False)
        _need(not excluded_ids & coverage and coverage | excluded_ids == all_ids, "split must account for every labeled ID, including source exclusions")
        if panel.endswith("zero_shot"):
            _need("train_cv" in split and len(cv) == 3, "zero-shot panel requires three subject CV folds")
            train_subjects = {metadata[i]["subject_id"].lower() for i in final_train}
            test_subjects = {metadata[i]["subject_id"].lower() for i in test}
            _need(len(train_subjects) == 3 and len(test_subjects) == 1 and not train_subjects & test_subjects, "zero-shot outer subject leakage/topology mismatch")
            val_subjects_seen = []
            for fit_ids, val_ids in cv:
                fit_subjects = {metadata[i]["subject_id"].lower() for i in fit_ids}
                val_subjects = {metadata[i]["subject_id"].lower() for i in val_ids}
                _need(len(fit_subjects) == 2 and len(val_subjects) == 1 and not fit_subjects & val_subjects, "zero-shot CV subject leakage/topology mismatch")
                _need(fit_ids | val_ids == final_train, "subject CV must cover full outer train population")
                val_subjects_seen.extend(val_subjects)
            _need(len(set(val_subjects_seen)) == 3 and set(val_subjects_seen) == train_subjects, "CV must validate each training subject once")
        else:
            _need("val" in split, "neuron-wise transductive panel requires train/val/test split")
        for fit_ids, _ in cv:
            _need(len({label_map[i] for i in fit_ids}) >= 2, "CV training needs at least two classes")
        if panel == "inductive_zero_shot":
            _need(all(metadata[i]["session_id"] in INDUCTIVE_TEST_SESSIONS for i in test), "inductive test must use held-out SB028 evaluation sessions")
            _need(all(metadata[i]["subject_id"].lower() != "sb028" for i in final_train), "inductive supervised fit includes held-out SB028")
        else:
            _need(all(metadata[i]["session_id"] not in DEV_SESSIONS for i in test), "transductive evaluation contains source dev session")
            _need({metadata[i]["session_id"] for i in test} <= training_sessions, "transductive test-population exposure missing from training manifest")
        normalized.append({"id": split["id"], "cv": cv, "train": final_train, "test": test})
    if panel == "transductive_zero_shot":
        subjects = [{metadata[i]["subject_id"].lower() for i in s["test"]} for s in normalized]
        _need(len(subjects) == 4 and len(set.union(*subjects)) == 4, "transductive zero-shot requires all four held-out subject folds")
    elif panel == "inductive_zero_shot":
        _need(len(normalized) == 1, "inductive zero-shot requires one SB028 outer split")
    return {"metadata": metadata, "label_map": label_map, "ordered_ids": ordered_ids,
            "splits": normalized, "vocabulary": vocabulary}


def _fit_predict(embeddings, ids, label_map, train, test, class_balance):
    import numpy as np
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    with np.errstate(over="ignore", invalid="ignore"):
        X = np.asarray(embeddings, dtype=np.float32)  # source load_emb uses Tensor.float()
    _need(bool(np.isfinite(X).all()), "embeddings not finite in source float32 representation")
    train_index = [i for i, uid in enumerate(ids) if uid in train]
    test_index = [i for i, uid in enumerate(ids) if uid in test]
    X_train = X[train_index]
    y_train = np.asarray([label_map[ids[i]] for i in train_index])
    if class_balance == "resample":
        try:
            from imblearn.over_sampling import RandomOverSampler
        except ImportError as exc:
            raise ContractError("resample needs existing imbalanced-learn; no fallback to weight is allowed") from exc
        sampled, _ = RandomOverSampler(random_state=42).fit_resample(np.arange(len(y_train)).reshape(-1, 1), y_train)
        X_train, y_train = X_train[sampled.ravel()], y_train[sampled.ravel()]
    scaler = StandardScaler()
    clf = LogisticRegression(max_iter=1000, tol=1e-4, C=1.0, solver="newton-cg",
                             class_weight="balanced" if class_balance == "weight" else None)
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        try:
            clf.fit(scaler.fit_transform(X_train), y_train)
        except ConvergenceWarning as exc:
            raise ContractError("readout failed to converge; report invalid instead of silently scoring") from exc
    prediction = clf.predict(scaler.transform(X[test_index])).tolist()
    result_ids = [ids[i] for i in test_index]
    return result_ids, [label_map[uid] for uid in result_ids], prediction


def evaluate(packet):
    """Run source readout with test fitting deferred until CV selects a checkpoint."""
    started = time.perf_counter()
    spec = validate_packet(packet)
    all_true, all_pred, records, selected = [], [], [], []
    fit_count = 0
    for split in spec["splits"]:
        cv_scores = []
        for index, checkpoint in enumerate(packet["checkpoints"]):
            fold_true, fold_pred = [], []
            for train, val in split["cv"]:
                _, true, pred = _fit_predict(checkpoint["embeddings"], spec["ordered_ids"], spec["label_map"], train, val, packet["class_balance"])
                fit_count += 1
                fold_true.extend(true)
                fold_pred.extend(pred)
            cv_scores.append(classification_metrics(fold_true, fold_pred, spec["vocabulary"]))
        best = max(range(len(cv_scores)), key=lambda i: cv_scores[i]["macro_f1"])
        checkpoint = packet["checkpoints"][best]
        test_ids, true, pred = _fit_predict(checkpoint["embeddings"], spec["ordered_ids"], spec["label_map"], split["train"], split["test"], packet["class_balance"])
        fit_count += 1
        all_true.extend(true)
        all_pred.extend(pred)
        for uid, target, prediction in zip(test_ids, true, pred):
            records.append({"split_id": split["id"], "unit_id": uid, "subject_id": spec["metadata"][uid]["subject_id"].lower(),
                            "true": target, "pred": prediction})
        selected.append({"split_id": split["id"], "checkpoint_id": checkpoint["id"], "checkpoint_index": best,
                         "epoch": checkpoint["epoch"], "cv_metrics": cv_scores,
                         "test_metrics": classification_metrics(true, pred, spec["vocabulary"])})
    grouped = {}
    for subject in sorted({r["subject_id"] for r in records}):
        subject_records = [r for r in records if r["subject_id"] == subject]
        grouped[subject] = classification_metrics([r["true"] for r in subject_records], [r["pred"] for r in subject_records], spec["vocabulary"])
    repeated = {}
    for uid, row in spec["metadata"].items():
        if row.get("repeated_cell_id"):
            repeated.setdefault(row["repeated_cell_id"], []).append(uid)
    import numpy
    import sklearn
    return {"schema_version": 1, "task_id": TASK_ID, "component": "initial-evaluator-v1",
            "status": "engineering_readout_only", "input_role": packet["input_role"], "research_qualified": False, "full_contract_complete": False,
            "source_commit": SOURCE_COMMIT, "contract_sha256": CONTRACT_SHA256,
            "packet_sha256": canonical_sha256(packet), "provenance": copy.deepcopy(packet["provenance"]),
            "panel": packet["panel"], "label_level": packet["label_level"], "source_label_mapping": copy.deepcopy(packet["source_label_mapping"]), "context_variant": packet["context_variant"],
            "exposure": "test-population neural observations available" if packet["panel"].startswith("transductive") else "declared representation training excludes SB028; authentic exposure not verified",
            "metrics": classification_metrics(all_true, all_pred, spec["vocabulary"]),
            "selected": selected, "records": records, "subject_diagnostics": grouped,
            "aggregation": "concatenated selected test predictions; repeated split appearances retain source weight",
            "repeated_cell_groups_declared": {k: v for k, v in repeated.items() if len(v) > 1},
            "holds": list(HOLDS), "resources": {"wall_seconds": time.perf_counter() - started,
              "readout_fits": fit_count, "numpy": numpy.__version__, "sklearn": sklearn.__version__,
              "scope": "this supplied-embedding readout only; not native model resource envelope"}}


def compare_context(context, ablated):
    """Paired descriptive comparison on identical labels/splits/provenance/exposure.

    No significance claim: authentic independent animals and repeated-cell linkage
    are still required. Each arm selects checkpoints solely by its own CV labels.
    """
    _need(context.get("context_variant") == "population_context" and ablated.get("context_variant") == "ablated_context", "comparison arm identities wrong")
    def matched(p):
        q = copy.deepcopy(p)
        q.pop("context_variant", None)
        for checkpoint in q.get("checkpoints", []):
            checkpoint.pop("embeddings", None)
        return q
    _need(matched(context) == matched(ablated), "arms must match identities, split release, labels, exposure and checkpoints")
    a, b = evaluate(context), evaluate(ablated)
    delta = {metric: a["metrics"][metric] - b["metrics"][metric]
             for metric in ("accuracy", "balanced_accuracy", "macro_f1")}
    subjects = {s: {m: a["subject_diagnostics"][s][m] - b["subject_diagnostics"][s][m]
                   for m in delta} for s in a["subject_diagnostics"]}
    return {"task_id": TASK_ID, "status": "descriptive_matched_context_comparison_only",
            "research_qualified": False, "panel": a["panel"], "label_level": a["label_level"],
            "context": a, "ablated": b, "context_minus_ablated": delta,
            "subject_differences": subjects, "holds": list(HOLDS)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--ablated", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.packet.open() as stream:
        packet = json.load(stream)
    if args.ablated:
        with args.ablated.open() as stream:
            result = compare_context(packet, json.load(stream))
    else:
        result = evaluate(packet)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
