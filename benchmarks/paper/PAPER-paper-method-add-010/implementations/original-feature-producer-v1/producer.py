"""Original selected CS↔PFC maximum-squared DTW barycenter and OOF path.

Native tslearn0.6.3 is required for feature computation. Input preparation,
feature extraction, and classifier fitting are separate commands/operations.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import warnings

import numpy as np

import inputs

FEATURE = "bary-sq_dtw_max"
SOURCE_REVISION = "cab648bbe2eab7093f9ab7b9a5fcddabf28e60a0"


def native_dba():
    """No fallback solver, shortened signal, approximation, or package install."""
    try:
        version = importlib.metadata.version("tslearn")
    except importlib.metadata.PackageNotFoundError as exc:
        raise RuntimeError("Native feature extraction requires existing tslearn==0.6.3; no feature was computed") from exc
    if version != "0.6.3":
        raise RuntimeError(f"Source feature route requires tslearn==0.6.3, found {version}")
    from tslearn.barycenters import dtw_barycenter_averaging
    return dtw_barycenter_averaging


def preprocess(values):
    """PySPI1.1.0/1.1.1 Data defaults, preserving all four original ROIs."""
    from scipy.signal import detrend
    from scipy.stats import zscore

    array = np.asarray(values)
    inputs.require(array.dtype.kind in "fiu" and array.ndim == 2 and array.shape[0] == 4
                   and array.shape[1] >= 3, "four-ROI numeric process×time matrix required")
    inputs.require(bool(np.isfinite(array).all()), "nonfinite original signal")
    # Data loading is outside the author's per-SPI error boundary. A constant
    # ROI cannot be dropped or repaired merely because this pair does not use it.
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        standardized = zscore(np.asarray(array, dtype=np.float64), axis=1, nan_policy="omit", ddof=1)
    inputs.require(bool(np.isfinite(standardized).all()), "source Data standardization failed (for example a constant ROI)")
    normalized = detrend(standardized, axis=1)
    inputs.require(bool(np.isfinite(normalized).all()), "source Data detrending failed")
    return normalized


def feature(values, *, dba=None):
    """Return selected scalar plus numerical diagnostics for one complete block.

    ``dba`` is a dependency seam for analytical generated controls. Production
    commands obtain the exact native tslearn implementation via native_dba().
    Input/Data errors abort. Solver errors match Calculator.compute's per-SPI
    NaN boundary and are returned as explicit nulls for original QC to handle.
    """
    normalized = preprocess(values)
    solver = native_dba() if dba is None else dba
    messages = []
    pair_calls = 0
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            # Directed.multivariate traverses j outer/i inner. Six unique
            # pairs are cached symmetrically; compute all six to preserve the
            # original whole-SPI failure boundary, including unused ROI pairs.
            # (i=2,j=0) supplies both CS↔PFC directions. An unrelated pair's
            # NaN statistic is not an exception and does not erase this value.
            value = None
            for j in range(4):
                for i in range(j + 1, 4):
                    pair_calls += 1
                    barycenter = np.asarray(solver(normalized[[i, j]]), dtype=np.float64)
                    inputs.require(barycenter.shape == (normalized.shape[1], 1), "unexpected native DBA output shape")
                    statistic = float(np.nanmax(barycenter ** 2))
                    if (i, j) == (2, 0):
                        value = statistic
            messages = [str(w.message) for w in caught]
        inputs.require(np.isfinite(value), "selected SPI is nonfinite")
        return value, {"status": "finite", "native_pair_calls": pair_calls, "warnings": messages}
    except Exception as exc:
        return None, {"status": "source_SPI_failure", "exception_type": type(exc).__name__,
                      "message": str(exc), "native_pair_calls": pair_calls, "warnings": messages}


def versions():
    result = {}
    for name in ("numpy", "scipy", "tslearn", "scikit-learn"):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = None
    return result


def observation_id(participant, stimulus):
    return f"{participant}|{stimulus.lower()}|Irrelevant|1000ms|on|Raw|CS-PFC|{FEATURE}"


def produce(prepared, output):
    """Compute all376 source-category features; never select a convenient subset."""
    prepared = Path(prepared)
    binding, binding_pin = inputs.prepared_binding(prepared, with_pin=True)
    solver = native_dba()  # fail missing/mismatched environment before output
    output = inputs.fresh_directory(output)
    rows, details = [], []
    for record in binding["files"]:
        values = inputs.load_prepared(prepared, record)
        participant = record["participant"]
        for stimulus in record["category_first_occurrence"]:
            matrix = values[inputs.STIMULI.index(stimulus)]
            value, diagnostic = feature(matrix, dba=solver)
            rid = observation_id(participant, stimulus)
            rows.append({"id": rid, "participant": participant, "label": stimulus.lower(), "value": value})
            details.append({"id": rid, "source_array_pin": record["pin"],
                            "input_matrix_float64_C_sha256": hashlib.sha256(matrix.tobytes(order="C")).hexdigest(),
                            **diagnostic})
    # Recheck complete input bindings; errors leave a visible partial attempt.
    inputs.require(inputs.pin_file(prepared / "INPUT_BINDING.json", 262144) == binding_pin,
                   "prepared binding changed while computing features")
    result = {"schema": "meg_original_bary_sq_dtw_max_v1", "task_id": inputs.TASK,
              "source_revision": SOURCE_REVISION, "archive": inputs.ARCHIVE,
              "prepared_binding_pin": binding_pin, "feature": FEATURE,
              "relevance": "Irrelevant", "data_type": "Raw", "phase": "on",
              "time_ms_inclusive": [0, 999], "regions": list(inputs.REGIONS),
              "selected_pair": ["Category_Selective", "Prefrontal_Cortex"],
              "rows": rows, "numerical_diagnostics": details,
              "row_order_evidence": binding["row_order"],
              "computation": "sample-SD zscore each ROI, then linear detrend; six source-ordered native dtw_barycenter_averaging pairs and mirrored cache; CS-PFC uses [PFC,CS]; nanmax(barycenter**2)",
              "native_versions": versions(), "historical_environment_authenticated": False,
              "historical_row_order_authenticated": False, "historical_folds_authenticated": False,
              "model_fits": 0, "feature_calls": len(rows),
              "native_pair_calls": sum(d["native_pair_calls"] for d in details),
              "interpretation": "same selected source feature; neither a candidate improvement nor verified reproduction of the historical result"}
    inputs.write_json(output / "FEATURES.json", result)
    return {"participants": 94, "feature_calls": 376,
            "numerical_failures": sum(r["value"] is None for r in rows),
            "features": inputs.pin_file(output / "FEATURES.json", 2 * 1024**2), "model_fits": 0}


def source_feature_rows(packet):
    """Require the selected producer's complete94×4 geometry at the fit boundary."""
    inputs.require(packet.get("schema") == "meg_original_bary_sq_dtw_max_v1" and packet.get("task_id") == inputs.TASK,
                   "wrong selected feature packet")
    required = {"feature": FEATURE, "relevance": "Irrelevant", "data_type": "Raw", "phase": "on",
                "time_ms_inclusive": [0, 999], "regions": list(inputs.REGIONS),
                "selected_pair": ["Category_Selective", "Prefrontal_Cortex"], "archive": inputs.ARCHIVE}
    inputs.require(all(packet.get(k) == v for k, v in required.items()), "selected source condition changed")
    rows = packet.get("rows")
    inputs.require(isinstance(rows, list) and len(rows) == 376, "complete94×4 source feature rows required")
    expected = {observation_id(p, s) for p in inputs.roster() for s in inputs.STIMULI}
    seen = set()
    for row in rows:
        inputs.require(isinstance(row, dict) and set(row) == {"id", "participant", "label", "value"}, "wrong feature row fields")
        inputs.require(row["participant"] in inputs.roster() and row["label"] in ("false", "face", "letter", "object"), "wrong participant or category")
        rid = observation_id(row["participant"], row["label"])
        inputs.require(row["id"] == rid and rid not in seen, "changed/duplicate source feature identity")
        seen.add(rid)
        inputs.require(row["value"] is None or (type(row["value"]) in (float, int) and np.isfinite(row["value"])),
                       "feature must be finite or explicit null")
    inputs.require(seen == expected, "incomplete selected feature coverage")
    return rows


def classify(feature_path, output, *, folds_path=None, fold_evidence=None):
    from classifier import source_oof
    packet, feature_pin = inputs.read_json(feature_path, 2 * 1024**2, with_pin=True)
    rows = source_feature_rows(packet)
    folds = inputs.read_json(folds_path, 131072) if folds_path else None
    # Preserve failed attempts by creating the output before numerical fitting.
    output = inputs.fresh_directory(output)
    result = source_oof(rows, row_order_evidence=packet["row_order_evidence"], folds=folds,
                        fold_evidence=fold_evidence)
    inputs.require(inputs.pin_file(feature_path, 2 * 1024**2) == feature_pin, "feature file changed while fitting")
    result["source_features_pin"] = feature_pin
    result["source_feature_row_count"] = 376
    inputs.write_json(output / "OOF.json", result)
    return {"result": inputs.pin_file(output / "OOF.json", 2 * 1024**2),
            "model_fits": 10, "historical_result_reproduced": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    prepare_parser = sub.add_parser("prepare", help="authenticate full original ZIP and prepare all94 source windows; no numerical analysis")
    prepare_parser.add_argument("--archive", required=True)
    prepare_parser.add_argument("--output", required=True)
    feature_parser = sub.add_parser("features", help="compute all376 source-category DTW-barycenter features")
    feature_parser.add_argument("--prepared", required=True)
    feature_parser.add_argument("--output", required=True)
    fit_parser = sub.add_parser("classify", help="fit original source-style ten grouped folds, preserving source preprocessing")
    fit_parser.add_argument("--features", required=True)
    fit_parser.add_argument("--output", required=True)
    fit_parser.add_argument("--folds")
    fit_parser.add_argument("--fold-evidence")
    args = parser.parse_args()
    if args.operation == "prepare":
        result = inputs.prepare(args.archive, args.output)
    elif args.operation == "features":
        result = produce(args.prepared, args.output)
    else:
        result = classify(args.features, args.output, folds_path=args.folds, fold_evidence=args.fold_evidence)
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
