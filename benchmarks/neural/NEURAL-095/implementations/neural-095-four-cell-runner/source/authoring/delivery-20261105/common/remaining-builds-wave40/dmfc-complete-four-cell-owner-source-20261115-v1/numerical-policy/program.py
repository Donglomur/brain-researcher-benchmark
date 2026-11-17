"""Independent public-contract candidate for both NEURAL-095 observation views.

No reference model or private score code is imported. All fit choices use only
the five supplied training folds. Query rows enter prediction after final fit.
"""
import argparse
import json
import math
import os
from pathlib import Path

import numpy as np


LAMBDAS = (0.01, 0.1, 1.0, 10.0, 100.0)
TRAIN_N = 748
QUERY_N = 258
BASE_QUERY = {"case_id", "condition", "context", "nominal_ts_ms", "clock_seconds"}
BASE_TRAIN = BASE_QUERY | {"tp_ms", "fold"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def read_packet(path, expected, n, training):
    with np.load(path, allow_pickle=False) as archive:
        require(len(archive.files) == len(expected) and set(archive.files) == expected,
                "Exact public NPZ members required")
        packet = {name: archive[name] for name in expected}
    ids = packet["case_id"]
    require(ids.shape == (n,) and ids.dtype.kind == "U", "Unicode case IDs")
    require(np.unique(ids).size == n and bool(np.all(np.char.str_len(ids) <= 11)),
            "Unique case IDs fit the declared U11 output")
    for name in ("condition", "context"):
        values = packet[name]
        require(values.shape == (n,) and values.dtype.kind in "iuU", "Category vector")
    for name in ("nominal_ts_ms", "clock_seconds") + (("tp_ms",) if training else ()):
        values = packet[name]
        require(values.shape == (n,) and values.dtype.kind in "fiu"
                and bool(np.isfinite(values).all()), "Finite public scalar vector")
        packet[name] = values.astype(np.float64, copy=False)
    if training:
        folds = packet["fold"]
        require(folds.shape == (n,) and folds.dtype.kind in "iu", "Integer training folds")
        unique = np.unique(folds)
        require(unique.size == 5, "Exactly five provided training groups")
        for fold in unique:
            locations = np.flatnonzero(folds == fold)
            require(locations.size > 0 and locations[-1] - locations[0] + 1 == locations.size,
                    "Each provided chronological fold is contiguous")
    if "counts" in expected:
        values = packet["counts"]
        require(values.shape == (n, 4, 40) and values.dtype == np.dtype("<u4"),
                "All four by forty native count features required")
    return packet


def rows(packet, indices):
    return {name: values[indices] for name, values in packet.items()}


def raw_features(packet, categories):
    """Same cue columns in both views; the only view branch appends spikes."""
    n = len(packet["case_id"])
    nominal = packet["nominal_ts_ms"]
    clock = packet["clock_seconds"]
    condition_columns = [np.asarray(packet["condition"] == key, dtype=np.float64)
                         for key in categories["condition"]]
    context_columns = [np.asarray(packet["context"] == key, dtype=np.float64)
                       for key in categories["context"]]
    columns = condition_columns + context_columns + [nominal, clock]
    columns += [clock * indicator for indicator in context_columns]
    cue = np.column_stack(columns)
    if "counts" in packet:
        neural = np.log1p(packet["counts"].astype(np.float64)).reshape(n, 160)
        result = np.concatenate((cue, neural), axis=1)
    else:
        result = cue
    require(bool(np.isfinite(result).all()), "Finite feature matrix")
    return result


def fitting_state(packet):
    categories = {name: np.unique(packet[name]) for name in ("condition", "context")}
    raw = raw_features(packet, categories)
    inactive = np.all(raw == raw[:1], axis=0)
    center = np.mean(raw, axis=0, dtype=np.float64)
    center[inactive] = raw[0, inactive]
    centered = raw - center
    scale = np.sqrt(np.mean(centered * centered, axis=0, dtype=np.float64))
    scale[inactive] = 1.0
    require(bool(np.isfinite(scale).all()) and bool(np.all(scale > 0)), "Positive finite scales")
    x = centered / scale
    x[:, inactive] = 0.0
    residual_target = packet["tp_ms"] - packet["nominal_ts_ms"]
    intercept = float(np.mean(residual_target, dtype=np.float64))
    centered_target = residual_target - intercept
    n = raw.shape[0]
    gram = (x.T @ x) / n
    rhs = (x.T @ centered_target) / n
    require(bool(np.isfinite(gram).all()) and bool(np.isfinite(rhs).all())
            and math.isfinite(intercept), "Finite fitting sufficient statistics")
    return {"categories": categories, "center": center, "scale": scale,
            "inactive": inactive, "intercept": intercept, "gram": gram, "rhs": rhs,
            "training_rows": n, "feature_count": raw.shape[1]}


def solve(state, regularization):
    # Mean squared residual loss plus lambda * sum(beta**2); intercept unpenalized.
    lhs = state["gram"].copy()
    lhs.flat[:: lhs.shape[0] + 1] += regularization
    coefficients = np.linalg.solve(lhs, state["rhs"])
    coefficients[state["inactive"]] = 0.0
    require(bool(np.isfinite(coefficients).all()), "Finite ridge solution")
    return coefficients


def predict(packet, state, coefficients):
    raw = raw_features(packet, state["categories"])
    x = (raw - state["center"]) / state["scale"]
    x[:, state["inactive"]] = 0.0
    result = packet["nominal_ts_ms"] + state["intercept"] + x @ coefficients
    require(bool(np.isfinite(result).all()), "Finite untruncated predictions")
    return np.asarray(result, dtype=np.float64)


def select_and_fit(training):
    absolute_error_sums = [0.0] * len(LAMBDAS)
    fold_records = []
    fit_count = 0
    for fold in np.unique(training["fold"]):
        held = training["fold"] == fold
        fit = rows(training, ~held)
        validation = rows(training, held)
        state = fitting_state(fit)
        errors = []
        for index, regularization in enumerate(LAMBDAS):
            coefficients = solve(state, regularization)
            fit_count += 1
            error_sum = float(np.sum(np.abs(predict(validation, state, coefficients)
                                           - validation["tp_ms"]), dtype=np.float64))
            require(math.isfinite(error_sum), "Finite fold absolute error sum")
            absolute_error_sums[index] += error_sum
            errors.append(error_sum / len(validation["case_id"]))
        fold_records.append({"fold": int(fold), "fit_rows": len(fit["case_id"]),
                             "validation_rows": len(validation["case_id"]),
                             "feature_count": state["feature_count"],
                             "constant_columns": int(np.count_nonzero(state["inactive"])),
                             "mae_ms_by_lambda": errors})
    require(sum(item["validation_rows"] for item in fold_records) == TRAIN_N,
            "Every training row contributes once to selection")
    losses = [value / TRAIN_N for value in absolute_error_sums]
    best = min(range(len(LAMBDAS)), key=lambda index: (losses[index], -LAMBDAS[index]))
    final = fitting_state(training)
    coefficients = solve(final, LAMBDAS[best])
    fit_count += 1
    provenance = {"schema_version": 1, "status": "fit_provenance",
                  "candidate_id": "NEURAL-095", "method_id": "independent_residual_ridge_v1",
                  "view": "neural" if "counts" in training else "cue_only",
                  "training_rows": TRAIN_N, "query_rows_expected": QUERY_N,
                  "lambda_grid": list(LAMBDAS), "pooled_training_cv_mae_ms": losses,
                  "selected_lambda": LAMBDAS[best], "ridge_fits_completed": fit_count,
                  "training_preprocessing_fits": 6, "folds": fold_records,
                  "final_feature_count": final["feature_count"],
                  "final_constant_columns": int(np.count_nonzero(final["inactive"])),
                  "neural_columns": 160 if "counts" in training else 0,
                  "query_rows_used_for_preprocessing_or_selection": 0,
                  "assessment_targets_read": 0, "predictions_clipped": False,
                  "fit_extent_is_candidate_self_report": True}
    return final, coefficients, provenance



# Protocol-only successor. Every numerical helper above is unchanged.
import base64
import re

MODEL_SCHEMA = "dmfc-independent-ridge-fitted/v1"
ORIGINAL_NUMERIC_SHA = "c4c70e79e47f17a667d533159ec6755e39926f26b5b1b5712271f0a13406e104"
ARTIFACT_CAP = 65536


def unique_json(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON field")
        result[key] = value
    return result


def bounded_json(body, cap):
    require(type(body) is bytes and 0 < len(body) <= cap, "Bounded complete JSON")
    value = json.loads(body, object_pairs_hook=unique_json,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
    json.dumps(value, allow_nan=False)
    return value


def validate_record(record):
    require(type(record) is dict and set(record) == {
        "schema", "numeric_source_sha256", "view", "training_rows", "feature_count",
        "categories", "center", "scale", "inactive", "intercept", "coefficients", "provenance"},
        "Exact fitted artifact schema")
    require(record["schema"] == MODEL_SCHEMA and record["numeric_source_sha256"] == ORIGINAL_NUMERIC_SHA
            and record["view"] in ("cue_only", "neural") and type(record["training_rows"]) is int
            and record["training_rows"] == TRAIN_N, "Original method and complete training support")
    categories = record["categories"]
    require(type(categories) is dict and set(categories) == {"condition", "context"}, "Original category groups")
    for value in categories.values():
        require(type(value) is dict and set(value) == {"dtype", "values"}
                and type(value["dtype"]) is str and type(value["values"]) is list
                and 1 <= len(value["values"]) <= TRAIN_N, "Bounded category vocabulary")
        match = re.fullmatch(r"[<>=|]([iuU])([1-9][0-9]*)", value["dtype"])
        require(match is not None, "Original integer or Unicode category dtype")
        kind, width = match[1], int(match[2])
        if kind == "U":
            require(width <= ARTIFACT_CAP and all(type(x) is str and len(x) <= width for x in value["values"]),
                    "Lossless Unicode categories")
        else:
            require(width in (1, 2, 4, 8), "Native integer category width")
            low = 0 if kind == "u" else -(2 ** (8 * width - 1))
            high = 2 ** (8 * width) - 1 if kind == "u" else 2 ** (8 * width - 1) - 1
            require(all(type(x) is int and low <= x <= high for x in value["values"]), "Lossless integer categories")
        require(value["values"] == sorted(set(value["values"])), "Original sorted unique categories")
    count = len(categories["condition"]["values"]) + 2 * len(categories["context"]["values"]) + 2
    count += 160 if record["view"] == "neural" else 0
    require(type(record["feature_count"]) is int and record["feature_count"] == count,
            "Complete original feature map")
    for key in ("center", "scale", "coefficients"):
        values = record[key]
        require(type(values) is list and len(values) == count
                and all(type(x) is str for x in values), "Exact float64 vector extent")
        decoded = [float.fromhex(x) for x in values]
        require(all(math.isfinite(x) for x in decoded), "Finite fitted parameters")
        require(all(x.hex() == encoded for x, encoded in zip(decoded, values)), "Canonical lossless float spelling")
        if key == "scale":
            require(all(x > 0 for x in decoded), "Original positive RMS scales")
    require(type(record["inactive"]) is list and len(record["inactive"]) == count
            and all(type(x) is bool for x in record["inactive"]), "Exact inactive mask")
    require(all(not inactive or float.fromhex(coefficient) == 0.0
                for inactive, coefficient in zip(record["inactive"], record["coefficients"])),
            "Original inactive coefficients remain zero")
    require(type(record["intercept"]) is str and math.isfinite(float.fromhex(record["intercept"]))
            and float.fromhex(record["intercept"]).hex() == record["intercept"], "Lossless finite intercept")
    require(type(record["provenance"]) is dict, "Candidate-self-reported fit provenance")
    return record


def model_record(state, coefficients, provenance, view):
    return validate_record({"schema": MODEL_SCHEMA, "numeric_source_sha256": ORIGINAL_NUMERIC_SHA,
        "view": view, "training_rows": state["training_rows"], "feature_count": state["feature_count"],
        "categories": {key: {"dtype": value.dtype.str, "values": value.tolist()}
                       for key, value in state["categories"].items()},
        "center": [float(x).hex() for x in state["center"]],
        "scale": [float(x).hex() for x in state["scale"]],
        "inactive": [bool(x) for x in state["inactive"]],
        "intercept": state["intercept"].hex(),
        "coefficients": [float(x).hex() for x in coefficients], "provenance": provenance})


def artifact_bytes(record):
    body = json.dumps(validate_record(record), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    require(0 < len(body) <= ARTIFACT_CAP, "Complete fitted artifact fits frozen bound")
    return body


def artifact_record(body):
    return validate_record(bounded_json(body, ARTIFACT_CAP))


def restored_state(record):
    # Exactly the prediction-relevant state. Gram/rhs belong only to training.
    validate_record(record)
    state = {"categories": {key: np.asarray(value["values"], dtype=np.dtype(value["dtype"]))
                            for key, value in record["categories"].items()},
             "center": np.asarray([float.fromhex(x) for x in record["center"]], dtype=np.float64),
             "scale": np.asarray([float.fromhex(x) for x in record["scale"]], dtype=np.float64),
             "inactive": np.asarray(record["inactive"], dtype=np.bool_),
             "intercept": float.fromhex(record["intercept"]),
             "training_rows": record["training_rows"], "feature_count": record["feature_count"]}
    coefficients = np.asarray([float.fromhex(x) for x in record["coefficients"]], dtype=np.float64)
    return state, coefficients


def public_view(input_path):
    schema = read_json(input_path / "schema.json")
    contract = read_json(input_path / "contract.json")
    units = read_json(input_path / "units.json")
    require(schema["candidate_id"] == contract["candidate_id"] == "NEURAL-095", "Correct public task")
    require(schema["train_n"] == TRAIN_N and schema["query_n"] == QUERY_N
            and schema["shape_counts"] == ["case", 4, 40]
            and len(units["unit_id"]) == len(set(units["unit_id"])) == 40, "Original full assignment support")
    view = schema["paired_observation_view"]
    require(view in ("cue_only", "neural") and type(schema["counts_available"]) is bool
            and schema["counts_available"] == (view == "neural"), "Explicit paired input view")
    additional = {"counts"} if view == "neural" else set()
    require(set(schema["public_keys"]["train"]) == BASE_TRAIN | additional
            and set(schema["public_keys"]["query"]) == BASE_QUERY | additional, "Exact declared public member sets")
    return view, additional


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    operation = bounded_json((args.input / "operation.json").read_bytes(), 262144)
    require(type(operation) is dict and set(operation) == {
        "schema", "operation", "payload", "state", "tool_observation"}
        and operation["schema"] == "dmfc-offline-policy-call-v1"
        and operation["operation"] in ("prepare", "tool") and operation["state"] is None,
        "Exact stateless fixed numerical policy call")
    view, additional = public_view(args.input)
    if operation["operation"] == "prepare":
        require(operation["payload"] is None, "Training-only preparation request")
        require(not (args.input / "query.npz").exists() and not (args.input / "fitted.bin").exists(),
                "No query or prior fitted artifact during preparation")
        training = read_packet(args.input / "train.npz", BASE_TRAIN | additional, TRAIN_N, True)
        final, coefficients, provenance = select_and_fit(training)
        body = artifact_bytes(model_record(final, coefficients, provenance, view))
        payload = {"artifact_base64": base64.b64encode(body).decode("ascii")}
    else:
        record = artifact_record((args.input / "fitted.bin").read_bytes())
        require(record["view"] == view, "Frozen fit belongs to this observation view")
        final, coefficients = restored_state(record)
        query = read_packet(args.input / "query.npz", BASE_QUERY | additional, QUERY_N, False)
        prediction = predict(query, final, coefficients)
        ids = np.asarray(query["case_id"], dtype="<U11")
        require(bool(np.array_equal(ids, query["case_id"])), "No case ID truncation")
        payload = {"case_id": ids.tolist(), "prediction_ms": prediction.tolist()}
    result = json.dumps({"payload": payload, "state": None}, sort_keys=True,
                        separators=(",", ":"), allow_nan=False).encode()
    require(len(result) <= 262144, "Bounded complete numerical response")
    args.out.mkdir(parents=False, exist_ok=True)
    with (args.out / "result.json").open("xb") as stream:
        require(stream.write(result) == len(result), "Complete response")
        stream.flush(); os.fsync(stream.fileno())


if __name__ == "__main__":
    main()
