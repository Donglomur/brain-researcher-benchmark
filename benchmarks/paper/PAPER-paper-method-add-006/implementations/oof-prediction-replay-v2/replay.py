"""Replay paired out-of-fold 500-ms count predictions on the original rat panel.

This is an operator scorer, not a candidate runner or proof of out-of-fold
training. No fit, alpha selection, native preparation or download occurs here.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys

import numpy as np


# Reuse the retained, independently reviewed input/panel contract. It does not
# authenticate NWB provenance; the operator still owns that separate bridge.
_PATH = Path(__file__).resolve().parents[1] / "initial-evaluator-v1" / "evaluator.py"
_SPEC = importlib.util.spec_from_file_location("rat_replay_source_contract", _PATH)
source = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = source
_SPEC.loader.exec_module(source)
ContractError = source.ContractError


def source_fold_ids(nrows):
    """Original unshuffled KFold(10), after strict recorded-speed masking."""
    if isinstance(nrows, bool) or not isinstance(nrows, (int, np.integer)) or nrows < 10:
        raise ContractError("source ten-fold replay requires at least ten retained rows")
    sizes = np.full(10, nrows // 10, dtype=int)
    sizes[:nrows % 10] += 1
    return np.repeat(np.arange(10), sizes)


def _ids(value, length, label):
    value = np.asarray(value)
    if value.shape != (length,) or value.dtype.kind not in "US":
        raise ContractError(f"{label} requires an aligned vector of string identities")
    if np.any(np.char.str_len(value) == 0) or len(np.unique(value)) != length:
        raise ContractError(f"{label} must be nonempty and unique")
    return value.astype(str)


def prepare_reference(arrays):
    """Select original source rows/units without candidate-controlled masks."""
    z = source.latents(arrays["latents"])
    counts = source.counts_array(arrays["counts"], len(z))
    bins = _ids(arrays["bin_ids"], len(z), "bin_ids")
    units = _ids(arrays["unit_ids"], counts.shape[1], "unit_ids")
    locations = np.asarray(arrays["locations"])
    if locations.shape != (counts.shape[1],) or locations.dtype.kind not in "US":
        raise ContractError("locations must align to original unit identities")
    locations = locations.astype(str)
    rows = z[:, 2] > 4.0
    folds = source_fold_ids(int(rows.sum()))
    unit_mask = (counts[rows].mean(axis=0) / source.DT > 0.1) & np.isin(locations, source.REGIONS)
    if any(not np.any(unit_mask & (locations == r)) for r in source.REGIONS):
        raise ContractError("every source session must retain eligible CA1 and PFC units")
    return {"counts": counts[rows][:, unit_mask], "bin_ids": bins[rows],
            "unit_ids": units[unit_mask], "locations": locations[unit_mask],
            "fold_ids": folds, "original_rows": np.flatnonzero(rows),
            "original_units": np.flatnonzero(unit_mask)}


def validate_predictions(arrays, reference, role):
    """Reject omission, reordering, pooling and changed source fold assignments."""
    prediction = np.asarray(arrays["predictions"])
    if prediction.dtype.kind not in "fiu" or prediction.shape != reference["counts"].shape:
        raise ContractError(f"{role} predictions must match every retained bin and unit")
    prediction = prediction.astype(float)
    if not np.isfinite(prediction).all() or np.any(prediction <= 0):
        raise ContractError(f"{role} predictions must be finite positive 500-ms expected counts")
    for key in ("bin_ids", "unit_ids"):
        supplied = _ids(arrays[key], len(reference[key]), f"{role} {key}")
        if not np.array_equal(supplied, reference[key]):
            raise ContractError(f"{role} {key} differs from original retained order")
    folds = np.asarray(arrays["fold_ids"])
    if folds.dtype.kind not in "iu" or not np.array_equal(folds, reference["fold_ids"]):
        raise ContractError(f"{role} fold_ids differ from original unshuffled ten-fold assignment")
    return prediction


def _mean_deviance(y, mu):
    mu = np.broadcast_to(mu, y.shape)
    term = mu.copy()
    positive = y > 0
    y_pos, mu_pos = y[positive], mu[positive]
    relative_error = (mu_pos - y_pos) / y_pos
    near = np.abs(relative_error) < 0.5
    # log1p avoids subtracting two almost equal logarithms near a perfect fit.
    values = np.empty_like(y_pos)
    values[near] = y_pos[near] * (relative_error[near] - np.log1p(relative_error[near]))
    values[~near] = (mu_pos[~near] - y_pos[~near]
                     + y_pos[~near] * (np.log(y_pos[~near]) - np.log(mu_pos[~near])))
    term[positive] = values
    with np.errstate(over="ignore", invalid="ignore"):
        result = 2 * term.mean(axis=0)
    if not np.isfinite(result).all() or np.any(result < 0):
        raise ContractError("Poisson deviance arithmetic overflowed or became negative")
    return result


def fold_deviances(counts, predictions, folds):
    """Retain numerator/denominator, including zero-null-deviance folds.

    Values use each test fold's mean count for the intercept-only null model,
    not a training mean or a population mean. No clipping or finite replacement
    is used when the original ratio is undefined or negative-infinite.
    """
    model, null = np.empty((counts.shape[1], 10)), np.empty((counts.shape[1], 10))
    for fold in range(10):
        mask = folds == fold
        y, mu = counts[mask], predictions[mask]
        model[:, fold] = _mean_deviance(y, mu)
        null[:, fold] = _mean_deviance(y, y.mean(axis=0))
    # A constant target has exactly zero mathematical null deviance; numerical
    # cancellation must not turn it into a finite score.
    for fold in range(10):
        y = counts[folds == fold]
        null[np.all(y == y[0], axis=0), fold] = 0.0
    return model, null


def _fold_record(model, null):
    if null == 0:
        return {"d2": None, "status": "undefined_zero_over_zero" if model == 0 else "negative_infinity",
                "model_deviance": float(model), "null_deviance": 0.0}
    value = float(1 - model / null)
    if not np.isfinite(value):
        raise ContractError("nonfinite fold arithmetic; replay cannot silently discard it")
    return {"d2": value, "status": "finite", "model_deviance": float(model), "null_deviance": float(null)}


def score_session(reference_arrays, author_arrays, candidate_arrays):
    reference = prepare_reference(reference_arrays)
    predictions = {role: validate_predictions(arrays, reference, role)
                   for role, arrays in (("author", author_arrays), ("candidate", candidate_arrays))}
    deviances = {role: fold_deviances(reference["counts"], value, reference["fold_ids"])
                 for role, value in predictions.items()}
    regions = {}
    for region in source.REGIONS:
        units = []
        for u in np.flatnonzero(reference["locations"] == region):
            arms = {role: [_fold_record(m[u, f], n[u, f]) for f in range(10)]
                    for role, (m, n) in deviances.items()}
            comparable = [a["status"] == b["status"] == "finite"
                          for a, b in zip(arms["author"], arms["candidate"])]
            units.append({"unit_id": reference["unit_ids"][u],
                          "source_unit_index": int(reference["original_units"][u]),
                          "author": arms["author"], "candidate": arms["candidate"],
                          "paired_fold_d2_difference": [b["d2"] - a["d2"] if ok else None
                              for a, b, ok in zip(arms["author"], arms["candidate"], comparable)],
                          "finite_paired_fold_count": sum(comparable)})
        regions[region] = {"units": units, "eligible_unit_count": len(units)}
    return {"regions": regions, "retained_bin_count": len(reference["bin_ids"]),
            "fold_bin_counts": np.bincount(reference["fold_ids"], minlength=10).tolist(),
            "source_row_indices": reference["original_rows"].tolist(),
            "ordered_bin_ids_sha256": hashlib.sha256(json.dumps(reference["bin_ids"].tolist(),
                ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()}


def _load_pinned(row, directory):
    raw = (Path(directory) / row["path"]).read_bytes()
    if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
        raise ContractError("input content differs from frozen session manifest")
    with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
        return {key: archive[key].copy() for key in archive.files}


def replay_panel(reference_manifest, author_manifest, candidate_manifest, directories):
    """Require all 64 source sessions and both regions; emit no invented scalar."""
    manifests = [reference_manifest, author_manifest, candidate_manifest]
    rows = [source.validate_panel_manifest(manifest) for manifest in manifests]
    if len(directories) != 3:
        raise ContractError("reference, author and candidate manifest directories required")
    sessions = []
    for reference_row, author_row, candidate_row in zip(*rows):
        matching = (reference_row, author_row, candidate_row)
        if any(row["epoch_id"] != reference_row["epoch_id"] for row in matching):
            raise ContractError("paired arms have different native epoch identities")
        arrays = [_load_pinned(row, directory) for row, directory in zip(matching, directories)]
        result = score_session(*arrays)
        result.update({key: reference_row[key] for key in ("animal", "session_index", "epoch_id")})
        result["input_sha256"] = {role: row["sha256"]
                                  for role, row in zip(("reference", "author", "candidate"), matching)}
        sessions.append(result)
    return {"schema_version": "rat-oof-replay/v2", "task_id": source.TASK_ID,
            "source_revision": source.SOURCE_REVISION, "prediction_units": "expected_spikes_per_500_ms",
            "fold_policy": "unshuffled_KFold_10_after_recorded_speed_strictly_above_4_cm_s",
            "null_policy": "test_fold_mean_count_per_unit", "sessions": sessions,
            "population_d2": None,
            "population_aggregation_status": "author_nesting_and_invalid_fold_policy_unresolved",
            "qualification": {"native_source_preparation_attested": False,
                              "out_of_fold_training_attested": False,
                              "author_calibration_established": False,
                              "paper_reproduction_established": False,
                              "paper_improvement_established": False}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference_manifest", type=Path)
    parser.add_argument("author_manifest", type=Path)
    parser.add_argument("candidate_manifest", type=Path)
    parser.add_argument("output", type=Path, help="operator-only JSON; contains unit-level evaluation results")
    args = parser.parse_args(argv)
    paths = [args.reference_manifest, args.author_manifest, args.candidate_manifest]
    result = replay_panel(*(json.loads(path.read_text()) for path in paths),
                          directories=[path.parent for path in paths])
    payload = json.dumps(result, indent=2, allow_nan=False) + "\n"
    with args.output.open("x") as stream:
        stream.write(payload)


if __name__ == "__main__":
    main()
