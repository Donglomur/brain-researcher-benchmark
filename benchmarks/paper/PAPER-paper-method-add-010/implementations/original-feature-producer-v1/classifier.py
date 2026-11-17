"""Source-style grouped OOF classification for the selected MEG FC endpoint.

Reimplements the pinned author's four-category QC, MixedSigmoidScaler and L1
logistic recipe while preserving an explicitly supplied feature-row order.
This is not proof of the author's original glob order, folds, or fitted result.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import importlib.metadata
import importlib.util
import json
import math
from pathlib import Path
import warnings

import numpy as np

HERE = Path(__file__).resolve().parent
SOURCE_REVISION = "cab648bbe2eab7093f9ab7b9a5fcddabf28e60a0"
CLASSES = ("face", "false", "letter", "object")
PAIR = ("face", "object")
SCORER_PATH = HERE.parent / "original-fold-score-v1" / "score.py"


class ClassifierError(ValueError):
    """Source support, QC or numerical procedure cannot be evaluated."""


def require(condition, message):
    if not condition:
        raise ClassifierError(message)


def _scorer():
    specification = importlib.util.spec_from_file_location("fc_original_fold_score", SCORER_PATH)
    require(specification is not None and specification.loader is not None, "original scorer unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _vector(values, name):
    array = np.asarray(values, dtype=np.float64)
    require(array.ndim == 1 and array.size > 0, f"{name} must be a nonempty vector")
    require(bool(np.isfinite(array).all()), f"{name} contains nonfinite values")
    return array


def _digest(value):
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _evidence(value, name):
    require(isinstance(value, str) and 0 < len(value.strip()) <= 4096,
            f"explicit {name} description required")
    return value


def mixed_sigmoid_fit(values):
    """Training-fold location/scale, matching the author's NumPy defaults."""
    values = _vector(values, "training feature")
    q25, q75 = np.percentile(values, (25, 75))
    result = {
        "mean": float(np.mean(values)), "sd_ddof0": float(np.std(values)),
        "median": float(np.median(values)), "q25": float(q25), "q75": float(q75),
        "iqr": float(q75 - q25), "training_rows": len(values),
    }
    require(all(math.isfinite(v) for v in result.values()), "source scaler statistics are nonfinite")
    return result


def mixed_sigmoid_transform(values, fitted):
    """Apply source expression then min/max *this transform batch*.

    The source's left-associative division is (x-median)/IQR/1.35, not
    (x-median)/(IQR/1.35). Its final unit-range extrema are recomputed for each
    transform call, including all held-out rows together. Do not replace this
    transductive convention with training extrema in a reproduction route.
    """
    values = _vector(values, "transform feature")
    require(isinstance(fitted, dict), "source scaler fit record required")
    required = {"mean", "sd_ddof0", "median", "q25", "q75", "iqr", "training_rows"}
    require(set(fitted) == required, "invalid source scaler fit record")
    require(all(type(v) in (int, float) and math.isfinite(v) for v in fitted.values()),
            "nonfinite or invalid source scaler statistics")
    require(fitted["iqr"] >= 0 and fitted["sd_ddof0"] >= 0, "negative source scale")
    if fitted["iqr"] == 0:
        require(fitted["sd_ddof0"] > 0, "source mean/SD branch divides by zero")
        standardized = (values - fitted["mean"]) / fitted["sd_ddof0"]
        branch = "mean_sd"
    else:
        standardized = (values - fitted["median"]) / fitted["iqr"] / 1.35
        branch = "median_iqr_then_1.35"
    # The source uses math.e**(-x); overflow yields limiting sigmoid zero.
    # Preserve that result but refuse any nonfinite transformed value.
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        sigmoid = 1 / (1 + np.power(math.e, -standardized))
    require(bool(np.isfinite(sigmoid).all()), "source sigmoid output is nonfinite")
    minimum, span = float(np.min(sigmoid)), float(np.ptp(sigmoid))
    transformed = sigmoid if span == 0 else (sigmoid - minimum) / span
    require(bool(np.isfinite(transformed).all()), "source unit-range transform is nonfinite")
    return transformed, {
        "branch": branch, "batch_rows": len(values), "sigmoid_minimum": minimum,
        "sigmoid_range": span, "range_scope": "this_transform_batch",
    }


def prepare_source_block(rows):
    """Validate all94 people/all4 classes, then perform source pre-pair QC.

    Missing values denote numerical failures for existing observations; omitted
    source conditions are refused. Mean imputation and feature screening use the
    complete four-category block before face/object filtering or CV, as released.
    """
    require(isinstance(rows, (list, tuple)) and rows, "ordered feature rows required")
    roster = set(_scorer().published_participants())
    support, seen, captured, values = {}, set(), [], []
    for row in rows:
        require(isinstance(row, dict) and set(row) == {"id", "participant", "label", "value"},
                "feature rows require exactly id,participant,label,value")
        rid, participant, label, value = row["id"], row["participant"], row["label"], row["value"]
        require(isinstance(rid, str) and 0 < len(rid.strip()) <= 512, "invalid observation ID")
        require(rid not in seen, "duplicate observation ID")
        require(isinstance(participant, str) and participant in roster, "unknown participant")
        require(isinstance(label, str) and label in CLASSES, "unknown source class")
        require(value is None or type(value) in (int, float), "feature must be a real scalar or null")
        number = np.nan if value is None else float(value)
        require(not math.isinf(number), "infinite source feature")
        seen.add(rid)
        support.setdefault(participant, set()).add(label)
        captured.append({"id": rid, "participant": participant, "label": label,
                         "value": None if math.isnan(number) else number})
        values.append(number)
    require(set(support) == roster and all(labels == set(CLASSES) for labels in support.values()),
            "complete four-category support for all94 published participants required")
    array = np.asarray(values, dtype=np.float64)
    missing = np.isnan(array)
    n_missing = int(missing.sum())
    proportion = n_missing / len(array)
    finite = array[~missing]
    # pandas Series.value_counts excludes NaNs; Series.std uses ddof=1.
    mode_count = max(Counter(float(x) for x in finite).values(), default=0)
    with np.errstate(over="ignore", invalid="ignore"):
        sd = float(np.std(finite, ddof=1)) if len(finite) >= 2 else None
    require(sd is None or math.isfinite(sd), "source block SD is nonfinite")
    reasons = []
    if proportion > 0.1:
        reasons.append("missing_fraction_above_0.1")
    if mode_count / len(array) > 0.9:
        reasons.append("mode_fraction_above_0.9")
    if sd is not None and sd < 1e-10:
        reasons.append("sample_sd_below_1e-10")
    imputed_mean = float(np.mean(finite)) if 0 < proportion < 0.1 else None
    if imputed_mean is not None:
        require(math.isfinite(imputed_mean), "source imputation mean is nonfinite")
        array[missing] = imputed_mean
    qc = {
        "source_block_rows": len(rows), "participants": len(support),
        "categories": list(CLASSES), "missing_count": n_missing,
        "missing_fraction": proportion, "mode_count_before_imputation": mode_count,
        "sample_sd_before_imputation": sd, "imputed_mean": imputed_mean,
        "imputed_observation_ids": [r["id"] for r, absent in zip(captured, missing) if absent],
        "excluded_by_source_qc": bool(reasons), "source_qc_exclusion_reasons": reasons,
        "screening_and_imputation_scope": "all_four_category_rows_before_pair_selection_and_CV",
        "ordered_source_block_sha256": _digest(captured),
        "source_multiplicity": "all_supplied_distinct_rows_preserved",
    }
    if reasons:
        raise ClassifierError("source QC excludes selected endpoint: " + json.dumps(qc, allow_nan=False))
    # Exactly10% NaNs is neither imputed nor excluded by the source inequalities.
    # sklearn then refuses NaNs; preserve failure rather than silently repair.
    require(bool(np.isfinite(array).all()), "source QC leaves nonfinite values; no silent imputation at10percent boundary")
    selected = [i for i, row in enumerate(captured) if row["label"] in PAIR]
    observations = [{key: captured[i][key] for key in ("id", "participant", "label")} for i in selected]
    return observations, array[selected].copy(), qc


def source_oof(rows, *, row_order_evidence, folds=None, fold_evidence=None):
    """Fit the exact source recipe on supplied ordered values and score OOF rows.

    ``folds`` is an optional participant-ID→fold0..9 declaration. Its associated
    evidence is recorded, not authenticated. Otherwise this realizes a new
    source-style StratifiedGroupKFold(shuffle=True, random_state=127) partition.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import StratifiedGroupKFold

    row_order_evidence = _evidence(row_order_evidence, "row-order evidence")
    observations, values, qc = prepare_source_block(rows)
    labels = np.asarray([row["label"] for row in observations])
    groups = np.asarray([row["participant"] for row in observations])
    roster = set(groups.tolist())
    fold_for_row = np.full(len(observations), -1, dtype=int)
    if folds is None:
        require(fold_evidence is None, "fold evidence without supplied folds is ambiguous")
        splitter = StratifiedGroupKFold(n_splits=10, shuffle=True, random_state=127)
        for fold, (_, held) in enumerate(splitter.split(values[:, None], labels, groups=groups)):
            require(bool((fold_for_row[held] == -1).all()), "generated folds overlap")
            fold_for_row[held] = fold
        fold_origin = "new_source_style_StratifiedGroupKFold_realization"
        fold_description = "Generated from the supplied ordered rows with random_state127; original historical realization unverified."
    else:
        require(isinstance(folds, dict) and set(folds) == roster, "supplied folds require exact94-person coverage")
        require(all(type(v) is int and 0 <= v < 10 for v in folds.values()), "folds must be integer0..9")
        require(set(folds.values()) == set(range(10)), "all ten folds must be represented")
        fold_description = _evidence(fold_evidence, "fold evidence")
        fold_for_row = np.asarray([folds[row["participant"]] for row in observations], dtype=int)
        fold_origin = "externally_supplied_unverified_realization"
    require(bool((fold_for_row >= 0).all()), "incomplete fold assignment")
    participant_folds = {}
    for row, fold in zip(observations, fold_for_row):
        require(participant_folds.get(row["participant"], int(fold)) == fold,
                "participant crosses held-out folds")
        participant_folds[row["participant"]] = int(fold)
        row["fold"] = int(fold)
    probabilities, fold_records, fold_auc = {}, [], []
    for fold in range(10):
        train, held = np.flatnonzero(fold_for_row != fold), np.flatnonzero(fold_for_row == fold)
        require(len(train) > 0 and len(held) > 0, "empty training or held-out fold")
        require(set(labels[train]) == set(PAIR) and set(labels[held]) == set(PAIR),
                "both source classes required in every train/test split")
        fitted = mixed_sigmoid_fit(values[train])
        transformed_train, train_range = mixed_sigmoid_transform(values[train], fitted)
        transformed_held, held_range = mixed_sigmoid_transform(values[held], fitted)
        model = LogisticRegression(penalty="l1", C=1, solver="liblinear", class_weight="balanced", random_state=127)
        with warnings.catch_warnings(record=True) as observed_warnings:
            warnings.simplefilter("always")
            model.fit(transformed_train[:, None], labels[train])
        require(tuple(model.classes_) == PAIR, "unexpected logistic probability orientation")
        prediction = model.predict_proba(transformed_held[:, None])[:, 1]
        predicted_labels = model.predict(transformed_held[:, None])
        require(bool(np.isfinite(prediction).all()) and bool(((prediction >= 0) & (prediction <= 1)).all()),
                "invalid source probabilities")
        require(np.array_equal(predicted_labels, np.asarray(PAIR)[(prediction > 0.5).astype(int)]),
                "probability rounding disagrees with original logistic decision")
        auc = float(roc_auc_score(labels[held] == "object", prediction))
        require(math.isfinite(auc), "source fold AUC is nonfinite")
        fold_auc.append(auc)
        for row_index, probability in zip(held, prediction):
            identifier = observations[row_index]["id"]
            require(identifier not in probabilities, "duplicate OOF prediction")
            probabilities[identifier] = float(probability)
        fold_records.append({
            "fold": fold, "training_observation_ids": [observations[i]["id"] for i in train],
            "held_out_observation_ids": [observations[i]["id"] for i in held],
            "source_scaler_fit": fitted, "training_transform": train_range,
            "held_out_transform": held_range,
            "coefficient": model.coef_.tolist(), "intercept": model.intercept_.tolist(),
            "iterations": model.n_iter_.tolist(),
            "AUC": auc,
            "warnings": [{"category": w.category.__name__, "message": str(w.message)} for w in observed_warnings],
        })
    scored = _scorer().score_cell(observations, probabilities, PAIR)
    scored.update(AUC=float(np.mean(fold_auc)), AUC_SD=float(np.std(fold_auc, ddof=0)),
                  fold_AUC=fold_auc)
    versions = {}
    for distribution in ("numpy", "pandas", "scikit-learn", "scipy", "tslearn"):
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = None
    return {
        "schema": "meg-fc-source-style-oof/v1", "author_revision": SOURCE_REVISION,
        "endpoint": {"measure": "bary-sq_dtw_max", "roi_pair": ["Category_Selective", "Prefrontal_Cortex"],
                     "relevance": "Irrelevant", "period": "on", "classes": list(PAIR)},
        "row_order_evidence": row_order_evidence, "block_qc": qc,
        "fold_origin": fold_origin, "fold_evidence": fold_description,
        "participant_to_fold": participant_folds, "observations": observations,
        "probabilities_object": probabilities, "fold_records": fold_records,
        "score": scored, "dependency_versions": versions,
        "classifier_parameters": model.get_params(deep=False),
        "source_environment_parity": "unverified",
        "original_row_order_and_fold_authentication": "not_established_by_this_function",
        "scientific_qualification": "unestablished",
        "normalization_exposure": [
            "Four-category QC and mean imputation occur across all participants before CV.",
            "Training-fold location/scale statistics are fit only on training rows.",
            "Each held-out batch determines its own unit-range extrema during transform.",
            "Known-category averaged regional inputs are not label-independent single trials.",
        ],
    }
