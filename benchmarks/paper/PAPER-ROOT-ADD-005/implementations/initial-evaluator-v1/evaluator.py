"""Prospective grouped image encoding for PAPER-ROOT-ADD-005.

This is a construction evaluator, not the author's session-CV reproduction or an
admission grader. Only NumPy is required; input NPZ archives never allow pickle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

TASK_ID = "PAPER-ROOT-ADD-005"
PARTICIPANTS = ("01", "02", "03")
ALPHAS = np.array([0.01, 0.1, 1.0, 10.0, 100.0, 1000.0])
OUTER_FOLDS = 5
INNER_FOLDS = 4
POLICY = "prospective-image-family-category-nested-ridge-v1"
GATES = [
    "Authentic full-population acquisition and metadata binding are unverified.",
    "Native 12-session CV, global predictor scaling, and 30-dimension source variance partition are not reproduced.",
    "No independent empirical reference, numeric target, candidate replay, or scientific qualification is established.",
    "Protected evaluation, equal access budgets, image rights, and cross-task image overlap require qualification.",
    "Three participant-specific analyses do not establish population or cross-subject voxel generalization.",
    "Native 52-category identities/completeness, exact shape descriptor recipe, and scientific suitability of operator-supplied holdout labels remain unverified; arbitrary descriptor blocks do not establish comparator completeness.",
    "Full-cohort memory, runtime, subset access, and native table conversion remain unmeasured.",
]


def _strings(value: Any, name: str, *, unique: bool = False) -> np.ndarray:
    x = np.asarray(value)
    if x.ndim != 1 or x.size == 0 or x.dtype.kind not in "US":
        raise ValueError(f"{name} must be a nonempty one-dimensional string array")
    x = x.astype(str)
    if any(not item or item != item.strip() for item in x):
        raise ValueError(f"{name} contains blank or whitespace-padded identifiers")
    if unique and len(set(x.tolist())) != len(x):
        raise ValueError(f"{name} contains duplicate identifiers")
    return x


def _matrix(value: Any, name: str, rows: int, columns: int | None = None) -> np.ndarray:
    raw = np.asarray(value)
    if raw.dtype.kind not in "fiu" or raw.ndim != 2:
        raise ValueError(f"{name} must be a numeric matrix")
    x = raw.astype(np.float64)
    if x.shape[0] != rows or x.shape[1] < 1 or (columns is not None and x.shape[1] != columns):
        raise ValueError(f"{name} has wrong shape {x.shape}")
    if not np.isfinite(x).all():
        raise ValueError(f"{name} contains nonfinite values")
    return x


def bind_rows(catalog_ids: Any, query_ids: Any) -> np.ndarray:
    """Exact identity join; no basename matching, case folding, or positional zip."""
    catalog = _strings(catalog_ids, "catalog_ids", unique=True)
    query = _strings(query_ids, "query_ids")
    lookup = {item: i for i, item in enumerate(catalog)}
    missing = sorted(set(query) - set(lookup))
    if missing:
        raise ValueError(f"Unknown stimulus identifiers: {missing[:5]}")
    return np.array([lookup[item] for item in query], dtype=np.int64)


def group_components(family_ids: Any, category_ids: Any) -> np.ndarray:
    """Transitive components join any shared family OR category holdout label.

    Category labels identify the prospective partition, not the possibly
    overlapping category descriptor columns. No fallback splits a component.
    """
    families = _strings(family_ids, "image_family_id")
    categories = _strings(category_ids, "category_group_id")
    if families.shape != categories.shape:
        raise ValueError("Family and category holdout arrays differ in length")
    parent = list(range(len(families)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for labels in (families, categories):
        first: dict[str, int] = {}
        for i, label in enumerate(labels):
            if label in first:
                a, b = find(i), find(first[label])
                parent[max(a, b)] = min(a, b)
            else:
                first[label] = i
    # Hash component memberships, making assignments independent of row order.
    members: dict[int, set[tuple[str, str]]] = {}
    for i in range(len(families)):
        members.setdefault(find(i), set()).add((families[i], categories[i]))
    names = {
        key: hashlib.sha256(json.dumps(sorted(value), separators=(",", ":")).encode()).hexdigest()
        for key, value in members.items()
    }
    return np.array([names[find(i)] for i in range(len(families))])


def grouped_folds(groups: Any, n_splits: int) -> list[tuple[np.ndarray, np.ndarray]]:
    groups = _strings(groups, "groups")
    names, counts = np.unique(groups, return_counts=True)
    if len(names) < n_splits:
        raise ValueError(f"Need at least {n_splits} independent components; found {len(names)}")
    # Largest first; hash identity settles ties, and lowest fold ID settles load ties.
    ranked = sorted(zip(names.tolist(), counts.tolist()), key=lambda item: (-item[1], item[0]))
    loads = [0] * n_splits
    assignment: dict[str, int] = {}
    for group, count in ranked:
        fold = min(range(n_splits), key=lambda k: (loads[k], k))
        assignment[group] = fold
        loads[fold] += count
    labels = np.array([assignment[group] for group in groups])
    return [(np.flatnonzero(labels != k), np.flatnonzero(labels == k)) for k in range(n_splits)]


def ridge_predict(x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray, alpha: Any) -> np.ndarray:
    """Train-only z-scoring, unpenalized intercept, SVD ridge, per-voxel alpha."""
    x_train, y_train, x_test = (np.asarray(value, dtype=float) for value in (x_train, y_train, x_test))
    if x_train.ndim != 2 or y_train.ndim != 2 or x_test.ndim != 2:
        raise ValueError("Ridge inputs must be matrices")
    if len(x_train) != len(y_train) or x_train.shape[1] != x_test.shape[1] or len(x_train) < 2:
        raise ValueError("Ridge input dimensions do not agree")
    if not all(np.isfinite(x).all() for x in (x_train, y_train, x_test)):
        raise ValueError("Ridge inputs must be finite")
    penalties = np.broadcast_to(np.asarray(alpha, dtype=float), (y_train.shape[1],))
    if not np.isfinite(penalties).all() or (penalties <= 0).any():
        raise ValueError("Ridge penalties must be positive and finite")
    mean = x_train.mean(axis=0)
    scale = x_train.std(axis=0, ddof=0)
    scale[scale == 0] = 1.0
    train = (x_train - mean) / scale
    test = (x_test - mean) / scale
    y_mean = y_train.mean(axis=0)
    u, singular, vt = np.linalg.svd(train, full_matrices=False)
    factors = singular[:, None] / (singular[:, None] ** 2 + penalties[None, :])
    return (test @ vt.T) @ (factors * (u.T @ (y_train - y_mean))) + y_mean


def nested_predict(x: np.ndarray, y: np.ndarray, groups: np.ndarray) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Every voxel selects alpha by pooled inner-validation MSE; ties use first alpha."""
    prediction = np.empty_like(y, dtype=float)
    audit: list[dict[str, Any]] = []
    for outer, (train, test) in enumerate(grouped_folds(groups, OUTER_FOLDS)):
        losses = np.zeros((len(ALPHAS), y.shape[1]))
        count = 0
        inner_audit = []
        for fit_local, valid_local in grouped_folds(groups[train], INNER_FOLDS):
            fit, valid = train[fit_local], train[valid_local]
            inner_audit.append({"train_indices": fit.tolist(), "validation_indices": valid.tolist()})
            for a, alpha in enumerate(ALPHAS):
                residual = y[valid] - ridge_predict(x[fit], y[fit], x[valid], alpha)
                losses[a] += np.sum(residual ** 2, axis=0)
            count += len(valid)
        losses /= count
        selected = np.argmin(losses, axis=0)
        penalties = ALPHAS[selected]
        prediction[test] = ridge_predict(x[train], y[train], x[test], penalties)
        audit.append({"outer_fold": outer, "train_indices": train.tolist(), "test_indices": test.tolist(),
                      "inner_folds": inner_audit, "selected_alpha_per_voxel": penalties.tolist(),
                      "inner_mse_per_alpha_per_voxel": losses.tolist()})
    return prediction, audit


def fit_scores(observed: np.ndarray, predicted: np.ndarray) -> dict[str, np.ndarray]:
    """Signed pooled held-out R2 and Pearson r; undefined values are NaN internally."""
    if observed.shape != predicted.shape or observed.ndim != 2 or len(observed) < 2:
        raise ValueError("Score arrays must be aligned image-by-voxel matrices")
    if not np.isfinite(observed).all() or not np.isfinite(predicted).all():
        raise ValueError("Scores require finite observations and predictions")
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        yc = observed - observed.mean(axis=0)
        pc = predicted - predicted.mean(axis=0)
        sst = np.sum(yc ** 2, axis=0)
        sse = np.sum((observed - predicted) ** 2, axis=0)
        prediction_ss = np.sum(pc ** 2, axis=0)
    # Raw SSE/SST are output diagnostics. Reject unrepresentable arithmetic rather
    # than mislabeling an overflowing/underflowing nonconstant target as undefined.
    if not all(np.isfinite(v).all() for v in (yc, pc, sst, sse, prediction_ss)):
        raise ValueError("Score arithmetic overflow; response units exceed float64 diagnostics")
    nonconstant_y = np.any(observed != observed[:1], axis=0)
    nonconstant_p = np.any(predicted != predicted[:1], axis=0)
    nonzero_error = np.any(observed != predicted, axis=0)
    if np.any((sst == 0) & nonconstant_y) or np.any((prediction_ss == 0) & nonconstant_p) or np.any((sse == 0) & nonzero_error):
        raise ValueError("Score arithmetic underflow; response units exceed float64 diagnostics")
    r2 = np.full(observed.shape[1], np.nan)
    with np.errstate(over="ignore", invalid="ignore"):
        np.divide(sse, sst, out=r2, where=sst > 0)
    if not np.isfinite(r2[sst > 0]).all():
        raise ValueError("Score ratio overflow")
    r2 = 1.0 - r2
    # Normalize each centered vector before its dot product. Forming SST*PSS
    # would overflow for otherwise representable arrays at a scale of 1e80.
    ynorm = np.zeros_like(yc)
    pnorm = np.zeros_like(pc)
    np.divide(yc, np.sqrt(sst), out=ynorm, where=sst[None, :] > 0)
    np.divide(pc, np.sqrt(prediction_ss), out=pnorm, where=prediction_ss[None, :] > 0)
    pearson = np.full_like(r2, np.nan)
    defined = (sst > 0) & (prediction_ss > 0)
    pearson[defined] = np.sum(ynorm * pnorm, axis=0)[defined]
    return {"r2": r2, "pearson_r": pearson, "sse": sse, "sst": sst}


def variance_partition(dimensions_r2: np.ndarray, descriptors_r2: np.ndarray, combined_r2: np.ndarray) -> dict[str, np.ndarray]:
    """Predictive commonality; signed values are retained without clipping."""
    if dimensions_r2.shape != descriptors_r2.shape or dimensions_r2.shape != combined_r2.shape:
        raise ValueError("Partition score arrays must describe the identical voxels")
    return {"unique_dimensions": combined_r2 - descriptors_r2,
            "unique_category_shape": combined_r2 - dimensions_r2,
            "shared": dimensions_r2 + descriptors_r2 - combined_r2,
            "total": combined_r2.copy()}


def _summary(x: np.ndarray) -> dict[str, Any]:
    valid = np.isfinite(x)
    return {"values": [float(v) if np.isfinite(v) else None for v in x],
            "defined_voxels": int(valid.sum()), "total_voxels": int(len(x)),
            # Do not silently change the voxel population by dropping undefined scores.
            "mean_all_voxels": float(x.mean()) if valid.all() else None}


def validate_bundle(bundle: dict[str, Any], roster: dict[str, Any]) -> dict[str, Any]:
    """Validate a trusted operator roster independently of candidate/model outputs.

    Roster agreement proves internal completeness only, not authentic acquisition.
    An empirical release still needs independently verified full source rosters.
    """
    if roster.get("task_id") != TASK_ID or set(roster.get("participants", {})) != set(PARTICIPANTS):
        raise ValueError("Roster must bind this task and exactly participants 01, 02, 03")
    provenance = roster.get("feature_provenance", {})
    if set(provenance) != {"dimensions", "category", "shape", "holdout_labels"}:
        raise ValueError("Operator must declare provenance for dimensions, category, shape and holdout_labels")
    for name, record in provenance.items():
        for field in ("source_uri", "revision", "mapping_rule"):
            if not isinstance(record.get(field), str) or not record[field].strip():
                raise ValueError(f"Missing {name} provenance {field}")
        digest = record.get("sha256", "")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError(f"Invalid {name} provenance sha256")
    stimulus = _strings(bundle["stimulus_id"], "stimulus_id", unique=True)
    expected = _strings(roster["stimulus_ids"], "roster.stimulus_ids", unique=True)
    if set(stimulus) != set(expected):
        raise ValueError("Feature catalog differs from the complete operator stimulus roster")
    dimensions = _matrix(bundle["dimensions"], "dimensions", len(stimulus), 66)
    category = _matrix(bundle["category"], "category", len(stimulus))
    shape = _matrix(bundle["shape"], "shape", len(stimulus))
    family = _strings(bundle["image_family_id"], "image_family_id")
    category_groups = _strings(bundle["category_group_id"], "category_group_id")
    if len(family) != len(stimulus) or len(category_groups) != len(stimulus):
        raise ValueError("Holdout metadata must cover every feature row")
    groups = group_components(family, category_groups)
    # Validate all folds before any fitting. This fails closed if components collapse.
    for train, _ in grouped_folds(groups, OUTER_FOLDS):
        grouped_folds(groups[train], INNER_FOLDS)
    participants = {}
    known_keys = {"stimulus_id", "dimensions", "category", "shape", "image_family_id", "category_group_id"}
    for subject in PARTICIPANTS:
        prefix = f"sub_{subject}_"
        known_keys.update(prefix + k for k in ("trial_id", "stimulus_id", "voxel_id", "response"))
        trial = _strings(bundle[prefix + "trial_id"], prefix + "trial_id", unique=True)
        image = _strings(bundle[prefix + "stimulus_id"], prefix + "stimulus_id")
        voxel = _strings(bundle[prefix + "voxel_id"], prefix + "voxel_id", unique=True)
        if len(image) != len(trial):
            raise ValueError(f"Participant {subject} trial/stimulus length mismatch")
        response = _matrix(bundle[prefix + "response"], prefix + "response", len(trial), len(voxel))
        record = roster["participants"][subject]
        expected_trial = _strings(record["trial_ids"], "roster.trial_ids", unique=True)
        expected_image = _strings(record["stimulus_ids_by_trial"], "roster.stimulus_ids_by_trial")
        expected_voxel = _strings(record["voxel_ids"], "roster.voxel_ids", unique=True)
        if len(expected_image) != len(expected_trial):
            raise ValueError("Roster trial/image lengths differ")
        if set(trial) != set(expected_trial) or set(voxel) != set(expected_voxel):
            raise ValueError(f"Participant {subject} differs from complete trial/voxel roster")
        expected_lookup = dict(zip(expected_trial, expected_image))
        if any(expected_lookup[t] != i for t, i in zip(trial, image)):
            raise ValueError(f"Participant {subject} trial-to-stimulus identity mismatch")
        indices = bind_rows(stimulus, image)
        if set(image) != set(stimulus):
            raise ValueError(f"Participant {subject} must cover the entire declared stimulus population")
        counts = np.bincount(indices, minlength=len(stimulus))
        averaged = np.zeros((len(stimulus), len(voxel)))
        np.add.at(averaged, indices, response)
        averaged /= counts[:, None]
        participants[subject] = {"y": averaged, "voxel_ids": voxel, "trial_counts": counts,
                                 "input_trials": len(trial)}
    if set(bundle) != known_keys:
        raise ValueError(f"Unexpected/missing input arrays: {sorted(set(bundle) ^ known_keys)}")
    return {"stimulus": stimulus, "groups": groups, "dimensions": dimensions,
            "category": category, "shape": shape, "participants": participants}


def evaluate(bundle: dict[str, Any], roster: dict[str, Any]) -> dict[str, Any]:
    data = validate_bundle(bundle, roster)
    designs = {"dimensions66": data["dimensions"], "category": data["category"], "shape": data["shape"],
               "category_shape": np.column_stack((data["category"], data["shape"])),
               "combined": np.column_stack((data["dimensions"], data["category"], data["shape"]))}
    result: dict[str, Any] = {"task_id": TASK_ID, "policy": POLICY,
        "implementation_scope": "prospective_grouped_encoding_and_predictive_commonality",
        "scientific_qualified": False, "native_reproduction": False, "full_contract_complete": False,
        "gates": GATES, "stimulus_ids": data["stimulus"].tolist(),
        "operator_feature_provenance": roster["feature_provenance"],
        "group_ids": data["groups"].tolist(), "component_count": len(set(data["groups"])),
        "feature_counts": {name: value.shape[1] for name, value in designs.items()},
        "policy_details": {"outer_folds": OUTER_FOLDS, "inner_folds": INNER_FOLDS,
            "alphas": ALPHAS.tolist(), "selection": "per-voxel pooled inner MSE; smallest alpha breaks ties",
            "normalization": "training-only predictor z-score; unpenalized response intercept; no response z-score",
            "repeat_policy": "average all declared single-trial responses per image before fitting; equal image weight",
            "score": "pooled out-of-fold image R2 and Pearson r; signed values; no clipping",
            "partition": "R2 commonality of dimensions66 and category_shape with paired out-of-fold populations",
            "category_policy": "one operator-defined partition label per image; not derived from category predictor columns",
            "participant_aggregation": "none; each participant retains its own voxel coordinate system"},
        "participants": {}}
    for subject, info in data["participants"].items():
        y, groups = info["y"], data["groups"]
        mean_prediction = np.empty_like(y)
        for train, test in grouped_folds(groups, OUTER_FOLDS):
            mean_prediction[test] = y[train].mean(axis=0)
        predictions, audits = {"train_mean": mean_prediction}, {}
        for name, design in designs.items():
            predictions[name], audits[name] = nested_predict(design, y, groups)
        raw_scores = {name: fit_scores(y, p) for name, p in predictions.items()}
        partition = variance_partition(raw_scores["dimensions66"]["r2"], raw_scores["category_shape"]["r2"], raw_scores["combined"]["r2"])
        result["participants"][subject] = {"voxel_ids": info["voxel_ids"].tolist(),
            "input_trials": info["input_trials"], "image_count": len(y), "trial_counts_per_image": info["trial_counts"].tolist(),
            "scores": {name: {metric: _summary(values) for metric, values in metrics.items()} for name, metrics in raw_scores.items()},
            "predictive_commonality": {name: _summary(values) for name, values in partition.items()},
            "out_of_fold_predictions": {name: p.tolist() for name, p in predictions.items()},
            "fold_audit": audits}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="NPZ containing only documented numeric/string arrays")
    parser.add_argument("--roster", type=Path, required=True, help="Trusted operator JSON with complete trial/image/voxel identities")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() in {args.input.resolve(), args.roster.resolve()}:
        parser.error("Output must not overwrite the input or operator roster")
    with np.load(args.input, allow_pickle=False) as archive:
        bundle = {key: archive[key] for key in archive.files}
    roster = json.loads(args.roster.read_text())
    result = evaluate(bundle, roster)
    def file_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
    result["input_sha256"] = file_hash(args.input)
    result["roster_sha256"] = file_hash(args.roster)
    # Strict serialization refuses any accidental nonfinite numeric output.
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
