"""Independent, in-memory retrospective encoding reference.

Only primitive feature records and numeric arrays cross this API. No filesystem,
native reader, author code, target lookup, partition selection or scoring entry
point is provided. See API.md for the frozen numerical conventions.
"""

import copy
import hashlib
import json

import numpy as np


PROFILES = ("C", "M", "CM", "CM-shuffled")
CATEGORIES = ("planned_delay", "reinforcer", "first_reward_order", "delivered_outcome")
MOVEMENT_FEATURES = tuple(
    f"{channel}_tap_{tap}"
    for channel in ("position_0", "position_1", "velocity_0", "velocity_1", "speed")
    for tap in ("m4", "m3", "m2", "m1", "0", "p1", "p2", "p3", "p4")
) + ("movement_duration", "movement_length")
PENALTIES = (1e-6, 1e-4, 1e-2, 1.0, 1e2, 1e4, 1e6)
SOLVER_RESIDUAL_RTOL = 1e-9
MODEL_VERSION = "paper-program-i-reference-v1"


class ReferenceError(ValueError):
    """A complete fit/prediction is unavailable; callers retain the failure."""


def _require(ok, message):
    if not ok:
        raise ReferenceError(message)


def configs(profile):
    """Return the exact family in deterministic exact-tie preference order."""
    _require(profile in PROFILES, "unknown profile")
    out = []
    if profile != "M":
        out.append({"id": "context_average", "representation": "context_average",
                    "penalty": None, "profile": profile})
    for representation in ("raw", "spline"):
        for penalty in reversed(PENALTIES):
            out.append({"id": f"{representation}_ridge_{penalty:.0e}",
                        "representation": representation, "penalty": penalty,
                        "profile": profile})
    return out


def configuration_rank(profile, configuration_id):
    """Tie rank only; the caller must pool complete inner held-out errors."""
    for index, configuration in enumerate(configs(profile)):
        if configuration["id"] == configuration_id:
            return index
    raise ReferenceError("configuration not in exact profile family")


def _finite_array(value, ndim, name):
    _require(isinstance(value, np.ndarray), f"{name} must be a primitive ndarray")
    _require(value.dtype.kind in "fiu" and value.ndim == ndim,
             f"{name} dtype/dimensions invalid")
    result = np.asarray(value, dtype=np.float64)
    _require(np.isfinite(result).all(), f"{name} must be finite")
    return result


def _weights(value, n):
    weights = _finite_array(value, 1, "sample_weights")
    _require(weights.shape == (n,) and np.all(weights > 0),
             "all complete-support sample weights must be positive")
    total = weights.sum()
    _require(np.isfinite(total) and total > 0, "invalid weight total")
    return weights / total


def _schema(schema):
    _require(type(schema) is dict and schema.get("profile") in PROFILES,
             "invalid schema/profile")
    profile = schema["profile"]
    expected = {"profile"}
    if profile != "C":
        expected.add("movement_features")
        _require(schema.get("movement_features") == list(MOVEMENT_FEATURES),
                 "movement feature order must be the full declared 47 columns")
    if profile != "M":
        expected.update(("categorical_vocabulary", "target_time_grid"))
        vocab = schema.get("categorical_vocabulary")
        _require(type(vocab) is dict and set(vocab) == set(CATEGORIES),
                 "four complete frozen categorical vocabularies required")
        for name in CATEGORIES:
            values = vocab[name]
            _require(type(values) is list and len(values) > 0 and
                     all(type(x) is str and x for x in values) and
                     len(values) == len(set(values)), "invalid categorical vocabulary")
        grid = schema.get("target_time_grid")
        _require(type(grid) is list and len(grid) >= 2 and
                 all(type(x) in (int, float) and np.isfinite(x) for x in grid),
                 "actual full source-selected time grid required")
        _require(all(b > a for a, b in zip(grid, grid[1:])),
                 "time grid must be strictly increasing")
    _require(set(schema) == expected, "illegal profile schema fields")
    return copy.deepcopy(schema)


def _number(value, name, allow_missing):
    if value is None:
        _require(allow_missing, f"missing {name}")
        return np.nan
    _require(type(value) in (int, float, np.float64, np.float32, np.int64, np.int32),
             f"{name} must be a number, not an object or boolean")
    value = float(value)
    _require(not np.isinf(value) and (allow_missing or np.isfinite(value)),
             f"nonfinite {name}")
    return value


def _records(records, schema):
    _require(type(records) in (list, tuple) and len(records) > 0,
             "nonempty feature-record sequence required")
    profile = schema["profile"]
    has_c, has_m = profile != "M", profile != "C"
    required = ({"time", "measured_delay", "categories"} if has_c else set())
    if has_m:
        required.add("movement")
    rows, cats, strata, time_indices = [], [], [], []
    grid_lookup = ({float(t): i for i, t in enumerate(schema["target_time_grid"])}
                   if has_c else {})
    for record in records:
        _require(type(record) is dict and set(record) == required,
                 "record exposes missing or forbidden profile fields")
        row, indicator, stratum = [], [], []
        if has_c:
            time = _number(record["time"], "time", False)
            _require(time in grid_lookup, "time is not an exact source-grid coordinate")
            time_indices.append(grid_lookup[time])
            row += [time, _number(record["measured_delay"], "measured_delay", True)]
            categories = record["categories"]
            _require(type(categories) is dict and set(categories) == set(CATEGORIES),
                     "invalid context fields")
            for name in CATEGORIES:
                value = categories[name]
                vocab = schema["categorical_vocabulary"][name]
                _require(type(value) is str and value in vocab,
                         "category absent from frozen structural vocabulary")
                stratum.append(vocab.index(value))
                indicator.extend(float(value == level) for level in vocab)
        if has_m:
            movement = record["movement"]
            _require(type(movement) is dict and set(movement) == set(MOVEMENT_FEATURES),
                     "full 47-feature movement view required")
            row += [_number(movement[name], name, True) for name in MOVEMENT_FEATURES]
        rows.append(row)
        cats.append(indicator)
        strata.append(tuple(stratum))
    return (np.asarray(rows, dtype=np.float64),
            np.asarray(cats, dtype=np.float64), strata,
            np.asarray(time_indices, dtype=np.int64))


def _mean_scale(x, weights):
    mean = weights @ x
    # Exactly constant inputs have zero variance even when normalized-weight
    # summation rounds away from one. Do not amplify that rounding to unit size.
    constant = np.all(x == x[0], axis=0)
    mean[constant] = x[0, constant]
    centered = x - mean
    variance = weights @ (centered * centered)
    variance[constant] = 0.0
    _require(np.isfinite(mean).all() and np.isfinite(variance).all(),
             "nonfinite feature moments")
    scale = np.sqrt(variance)
    scale[scale == 0] = 1.0
    return mean, scale


def _type7(values, fraction):
    """Linear empirical order statistic; observed training values only."""
    ordered = np.sort(values)
    index = (len(ordered) - 1) * fraction
    lo, hi = int(np.floor(index)), int(np.ceil(index))
    return float(ordered[lo] + (index - lo) * (ordered[hi] - ordered[lo]))


def _knot_vector(values):
    if len(values) == 0 or np.min(values) == np.max(values):
        return None
    low, high = float(np.min(values)), float(np.max(values))
    interior = sorted(set(_type7(values, q) for q in (1 / 3, 2 / 3)))
    interior = [x for x in interior if low < x < high]
    return [low] * 4 + interior + [high] * 4


def _bspline(x, knots):
    """Cubic Cox-de Boor basis, clipped; right endpoint is last basis=1."""
    knots = np.asarray(knots, dtype=np.float64)
    x = np.clip(x, knots[0], knots[-1])
    basis = ((x[:, None] >= knots[:-1]) & (x[:, None] < knots[1:])).astype(float)
    for degree in range(1, 4):
        new = np.zeros((len(x), len(knots) - degree - 1), dtype=np.float64)
        for j in range(new.shape[1]):
            left = knots[j + degree] - knots[j]
            right = knots[j + degree + 1] - knots[j + 1]
            if left > 0:
                new[:, j] += (x - knots[j]) / left * basis[:, j]
            if right > 0:
                new[:, j] += (knots[j + degree + 1] - x) / right * basis[:, j + 1]
        basis = new
    at_right = x == knots[-1]
    basis[at_right] = 0
    basis[at_right, -1] = 1
    return basis


def _completed(raw, impute, observed_training=None):
    missing = np.isnan(raw)
    completed = np.where(missing, impute, raw)
    if observed_training is not None:
        completed[:, ~np.asarray(observed_training, dtype=bool)] = 0.0
    return completed, missing.astype(np.float64)


def _expanded(raw, categorical, transform):
    completed, missing = _completed(raw, np.asarray(transform["impute"]),
                                    transform["observed_training"])
    basic = np.concatenate((completed, missing, categorical), axis=1)
    basic = (basic - np.asarray(transform["raw_mean"])) / np.asarray(transform["raw_scale"])
    if transform["representation"] == "raw":
        return basic
    columns = [basic]
    time_basis = None
    if transform["time_knots"] is not None:
        time_basis = _bspline(completed[:, 0], transform["time_knots"])
        columns.append(time_basis)
    for index, knots in enumerate(transform["continuous_knots"]):
        if knots is not None:
            columns.append(_bspline(completed[:, index], knots))
    if time_basis is not None:
        columns.append((time_basis[:, :, None] * categorical[:, None, :]).reshape(len(raw), -1))
    if transform["profile"] in ("CM", "CM-shuffled"):
        n_continuous = raw.shape[1]
        m_indices = list(range(2, n_continuous)) + list(range(n_continuous + 2, 2 * n_continuous))
        movement = basic[:, m_indices]
        columns.append((time_basis[:, :, None] * movement[:, None, :]).reshape(len(raw), -1))
        columns.append((categorical[:, :, None] * movement[:, None, :]).reshape(len(raw), -1))
    result = np.concatenate(columns, axis=1)
    _require(np.isfinite(result).all(), "nonfinite completed design matrix")
    return result


def _fit_transform(raw, categorical, weights, schema, representation):
    impute = []
    for col in raw.T:
        observed = ~np.isnan(col)
        impute.append(float(weights[observed] @ col[observed] / weights[observed].sum())
                      if observed.any() else 0.0)
    completed, missing = _completed(raw, np.asarray(impute))
    basic = np.concatenate((completed, missing, categorical), axis=1)
    raw_mean, raw_scale = _mean_scale(basic, weights)
    knots = [None] * raw.shape[1]
    time_knots = None
    if representation == "spline":
        for index in range(raw.shape[1]):
            if schema["profile"] != "M" and index == 0:
                low, high = schema["target_time_grid"][0], schema["target_time_grid"][-1]
                time_knots = [low] * 4 + np.linspace(low, high, 10)[1:-1].tolist() + [high] * 4
            else:
                observed = raw[:, index][~np.isnan(raw[:, index])]
                knots[index] = _knot_vector(observed)
    transform = {"profile": schema["profile"], "representation": representation,
                 "observed_training": (~np.isnan(raw)).any(axis=0).tolist(),
                 "impute": impute, "raw_mean": raw_mean.tolist(),
                 "raw_scale": raw_scale.tolist(), "continuous_knots": knots,
                 "time_knots": time_knots}
    expanded = _expanded(raw, categorical, transform)
    mean, scale = _mean_scale(expanded, weights)
    transform.update(expanded_mean=mean.tolist(), expanded_scale=scale.tolist())
    return transform, (expanded - mean) / scale


def _attestation(profile, label_provenance):
    if profile == "CM-shuffled":
        _require(type(label_provenance) is dict and
                 set(label_provenance) == {"kind", "receipt_sha256"} and
                 label_provenance["kind"] == "whole_training_trajectory_reassignment" and
                 type(label_provenance["receipt_sha256"]) is str and
                 len(label_provenance["receipt_sha256"]) == 64 and
                 all(x in "0123456789abcdef" for x in label_provenance["receipt_sha256"]),
                 "CM-shuffled requires operator-private permutation receipt attestation")
        return copy.deepcopy(label_provenance)
    _require(label_provenance is None, "unshuffled profiles cannot carry shuffle provenance")
    return None


def fit(train_X, train_Y, sample_weights, schema, configuration, *, label_provenance=None):
    """One configuration, all cells, training-only fit; no model selection."""
    schema = _schema(schema)
    _require(type(configuration) is dict and configuration in configs(schema["profile"]),
             "configuration must exactly match configs(profile)")
    provenance = _attestation(schema["profile"], label_provenance)
    raw, categorical, strata, times = _records(train_X, schema)
    y = _finite_array(train_Y, 2, "train_Y")
    _require(y.shape[0] == len(train_X) and y.shape[1] > 0, "target shape mismatch")
    weights = _weights(sample_weights, len(train_X))
    metadata = {"version": MODEL_VERSION, "schema": schema,
                "configuration": copy.deepcopy(configuration), "n_cells": y.shape[1],
                "n_training_examples": len(train_X), "label_provenance": provenance}
    if configuration["representation"] == "context_average":
        n_time = len(schema["target_time_grid"])
        unique = sorted(set(strata))
        global_mean = np.empty((n_time, y.shape[1]))
        stratum_mean = np.empty((len(unique), n_time, y.shape[1]))
        for t in range(n_time):
            selected = times == t
            _require(selected.any(), "training support omits a required time bin")
            global_mean[t] = np.average(y[selected], weights=weights[selected], axis=0)
            for s, stratum in enumerate(unique):
                selected_s = selected & np.array([row == stratum for row in strata])
                _require(selected_s.any(), "observed stratum has incomplete trajectory support")
                stratum_mean[s, t] = np.average(y[selected_s], weights=weights[selected_s], axis=0)
        _require(np.isfinite(global_mean).all() and np.isfinite(stratum_mean).all(),
                 "nonfinite context-average fit")
        metadata["strata"] = [list(s) for s in unique]
        return {"metadata": metadata, "arrays": {"global_mean": global_mean,
                                                  "stratum_mean": stratum_mean}}
    transform, x = _fit_transform(raw, categorical, weights, schema, configuration["representation"])
    target_mean = weights @ y
    centered_y = y - target_mean
    root_w = np.sqrt(weights)
    weighted_x = x * root_w[:, None]
    weighted_y = centered_y * root_w[:, None]
    try:
        u, singular, vt = np.linalg.svd(weighted_x, full_matrices=False)
        penalty = configuration["penalty"]
        coefficients = vt.T @ ((singular / (singular * singular + penalty))[:, None] * (u.T @ weighted_y))
    except np.linalg.LinAlgError as error:
        raise ReferenceError("stable ridge SVD failed") from error
    residual = weighted_x.T @ (weighted_x @ coefficients - weighted_y) + penalty * coefficients
    rhs = weighted_x.T @ weighted_y
    denominator = max(1.0, float(np.linalg.norm(rhs)))
    relative_residual = float(np.linalg.norm(residual) / denominator)
    _require(np.isfinite(coefficients).all() and np.isfinite(target_mean).all() and
             np.isfinite(relative_residual) and relative_residual <= SOLVER_RESIDUAL_RTOL,
             "ridge solver failed finite/residual tolerance")
    metadata.update(transform=transform, solver={"name": "normalized_weight_centered_svd_ridge",
                    "normal_equation_residual": relative_residual,
                    "residual_rtol": SOLVER_RESIDUAL_RTOL,
                    "weighted_design_rank": int(np.count_nonzero(singular >
                        np.finfo(float).eps * max(weighted_x.shape) * singular[0]))})
    return {"metadata": metadata, "arrays": {"coefficients": coefficients,
                                              "intercept": target_mean}}


def predict_with_info(model, record):
    """Pure one-record evaluation; returns full cell vector and fallback flag."""
    _require(type(model) is dict and set(model) == {"metadata", "arrays"}, "invalid model")
    metadata, arrays = model["metadata"], model["arrays"]
    _require(metadata.get("version") == MODEL_VERSION, "wrong model version")
    schema = _schema(metadata["schema"])
    raw, categorical, strata, times = _records([record], schema)
    config = metadata["configuration"]
    _require(config in configs(schema["profile"]), "invalid model configuration")
    fallback = False
    if config["representation"] == "context_average":
        _require(set(arrays) == {"global_mean", "stratum_mean"}, "invalid context model arrays")
        global_mean = _finite_array(arrays["global_mean"], 2, "global_mean")
        stratum_mean = _finite_array(arrays["stratum_mean"], 3, "stratum_mean")
        known = metadata["strata"]
        _require(global_mean.shape == (len(schema["target_time_grid"]), metadata["n_cells"]) and
                 stratum_mean.shape == (len(known), *global_mean.shape), "context model shape mismatch")
        if list(strata[0]) in known:
            result = stratum_mean[known.index(list(strata[0])), times[0]].copy()
        else:
            result, fallback = global_mean[times[0]].copy(), True
    else:
        _require(set(arrays) == {"coefficients", "intercept"}, "invalid ridge model arrays")
        transform = metadata["transform"]
        x = _expanded(raw, categorical, transform)
        x = (x - np.asarray(transform["expanded_mean"])) / np.asarray(transform["expanded_scale"])
        coefficients = _finite_array(arrays["coefficients"], 2, "coefficients")
        intercept = _finite_array(arrays["intercept"], 1, "intercept")
        _require(coefficients.shape == (x.shape[1], metadata["n_cells"]) and
                 intercept.shape == (metadata["n_cells"],), "ridge model shape mismatch")
        result = (x @ coefficients)[0] + intercept
    _require(result.shape == (metadata["n_cells"],) and np.isfinite(result).all(),
             "prediction unavailable/nonfinite")
    return result, {"context_fallback": fallback}


def predict(model, record):
    return predict_with_info(model, record)[0]


def apply_training_permutation(target_blocks, source_for_destination, strata):
    """Operator-private whole-trajectory permutation across paired modalities.

    target_blocks[modality][opaque_training_trial] is [time,cell]. The caller
    supplies one previously frozen bijection, and strata keys must include the
    acquisition plus the four discrete context fields. This function generates
    no seeds and has no knowledge of held-out/query labels. Its return receipt
    is operator-private and must never be given to a candidate.
    """
    _require(type(target_blocks) is dict and len(target_blocks) > 0,
             "nonempty modality mapping required")
    _require(type(source_for_destination) is dict and type(strata) is dict,
             "explicit training permutation and strata required")
    ids = set(source_for_destination)
    _require(ids and all(type(t) is str and t for t in ids) and
             set(source_for_destination.values()) == ids and set(strata) == ids,
             "permutation must be a complete training-only bijection")
    for trial in ids:
        _require(type(strata[trial]) in (list, tuple) and len(strata[trial]) == 5 and
                 all(type(x) is str and x for x in strata[trial]),
                 "acquisition and four discrete context stratum keys required")
        _require(tuple(strata[trial]) == tuple(strata[source_for_destination[trial]]),
                 "permutation crosses acquisition/context stratum")
    output = {}
    for modality, blocks in target_blocks.items():
        _require(type(modality) is str and type(blocks) is dict and set(blocks) == ids,
                 "all paired modalities must share complete physical-trial support")
        checked = {trial: _finite_array(value, 2, "training trajectory")
                   for trial, value in blocks.items()}
        _require(all(value.shape[0] > 0 and value.shape[1] > 0 for value in checked.values()),
                 "empty training trajectory")
        _require(len({value.shape for value in checked.values()}) == 1,
                 "modality training trajectories must share full time/cell axes")
        output[modality] = {trial: checked[source_for_destination[trial]].copy()
                            for trial in sorted(ids)}
    groups = {}
    for trial in sorted(ids):
        groups.setdefault(tuple(strata[trial]), []).append(trial)
    receipt = {"kind": "whole_training_trajectory_reassignment",
               "source_for_destination": dict(sorted(source_for_destination.items())),
               "strata": {trial: list(strata[trial]) for trial in sorted(ids)},
               "paired_modalities": sorted(target_blocks),
               "singleton_ineffective_trials": [v[0] for v in groups.values() if len(v) == 1],
               "identity_permutation": all(k == v for k, v in source_for_destination.items()),
               "private_operator_only": True}
    receipt_bytes = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    attestation = {"kind": receipt["kind"], "receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest()}
    return output, receipt, attestation
