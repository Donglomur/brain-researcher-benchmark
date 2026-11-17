"""Independent prospective PAPER-ROOT-ADD-020 reference source.

Pure supplied-array functions: no loaders, acquisition, command line or authentic
execution entry. All arithmetic is float64. Scientific/runtime/numerical
qualification remains false. An engineering fit is not an admission decision.

X is (rows, features); time targets/support are (rows, neurons, times); static
targets/support are (rows, neurons). False source-support entries are retained as
metadata and excluded only according to that supplied mask. Every fold, output
and required stratum needs support; no family/output/cell is silently omitted.
The caller authenticates masks, grouping, provenance, the 20-feature schema and
the complete original workload before using this otherwise dimension-general
library. No query operand is accepted by any fit or selection function.
"""

from __future__ import annotations

import hashlib
import json
import platform
from typing import Any

import numpy as np


CALIBRATED = "calibrated_held_face"
TRANSFER = "unfamiliar_to_familiar_transfer"
LAMBDAS = (1e-6, 1e-4, 1e-2, 1.0, 1e2, 1e4, 1e6)
MULTIPLIERS = (0.1, 1.0, 10.0)
WIDTHS = (1.0, 0.1, 10.0)
FAMILIES = (
    "training_mean", "OLS_intercept", "ridge_shared_axis",
    "ridge_familiarity_interaction", "axis_gain_and_monotone_output",
    "RBF_kernel_ridge",
)
SCHEMA = "paper020_independent_reference_artifact_v1"
INDEPENDENT_QUALIFICATION = False
NUMERICAL_CONTRACT = {
    "dtype": "float64",
    "weights": "calibrated: 1/(2*n_stratum); transfer: 1/n_unfamiliar",
    "transform": "training-weighted population mean/SD; exact constant columns zero",
    "objective": "sum(w*(y-b-X@beta)^2)+lambda*sum(beta^2); sum(w)=1",
    "OLS_rank": "s > eps(float64)*max(n_train,d+1)*s_max; full-design SVD minimum norm",
    "ridge_solver": "row-ordered weighted normal equations; numpy.linalg.solve",
    "OLS_solver": "numpy.linalg.svd(full_matrices=False)",
    "kernel_solver": "training-weight-centered kernel; symmetric weighted dual solve",
    "kernel_width": "median of i<j squared distances; exact zero gives constant kernel",
    "reductions": "float64 left-to-right row order; feature order for squared distance; time order for risk",
    "risk": "OOF row means within strata, equal strata, equal all time outputs; per neuron",
    "ties": "exact float64 equality; listed family, descending lambda, descending interaction multiplier, width 1/0.1/10, increasing before decreasing",
    "remaining_ties": "common mean before group mean; affine before isotonic; increasing before decreasing",
    "support": "fixed supplied source masks; each validation/training fold, output and required stratum supported",
    "scope": "no cross-runtime bitwise equivalence, native MATLAB parity or empirical competence established",
}


class ReferenceError(ValueError):
    """Stable fail-closed error; partial candidates never become a portfolio."""

    def __init__(self, code: str, message: str, **details: Any):
        self.code, self.details = code, details
        super().__init__(f"{code}: {message}")


def _fail(code: str, message: str, **details: Any) -> None:
    raise ReferenceError(code, message, **details)


def _array(value: Any, ndim: int, name: str, *, finite: bool = True) -> np.ndarray:
    try:
        a = np.array(value, dtype=np.float64, copy=True)
    except (TypeError, ValueError, OverflowError) as exc:
        _fail("invalid_array", f"{name} is not a float64 array", error=str(exc))
    if a.ndim != ndim:
        _fail("invalid_shape", f"{name} needs {ndim} dimensions", shape=list(a.shape))
    if finite and not np.isfinite(a).all():
        _fail("nonfinite_input", f"{name} has a nonfinite value")
    return a


def _regime(regime: str) -> None:
    if regime not in (CALIBRATED, TRANSFER):
        _fail("invalid_regime", "unknown prediction regime")


def _familiarity(value: Any, n: int, regime: str, *, training: bool) -> np.ndarray:
    _regime(regime)
    f = _array(value, 1, "familiarity")
    if f.shape != (n,) or not np.isin(f, (0.0, 1.0)).all():
        _fail("invalid_familiarity", "familiarity must have one binary value per row")
    if training and regime == TRANSFER and np.any(f == 1):
        _fail("forbidden_familiar_training", "transfer fitting cannot receive familiar targets")
    return f.astype(np.int8)


def _sum(a: np.ndarray) -> np.ndarray:
    """Frozen float64 reduction along row dimension, without reassociation."""
    total = np.zeros(a.shape[1:], dtype=np.float64)
    for row in a:
        total = np.add(total, row)
    return total


def balanced_weights(familiarity: Any, regime: str) -> np.ndarray:
    """Normalized original-row weights; not identity-averaged weights."""
    f = _array(familiarity, 1, "familiarity")
    f = _familiarity(f, len(f), regime, training=True)
    strata = (0, 1) if regime == CALIBRATED else (0,)
    if len(f) == 0 or any(not np.any(f == s) for s in strata):
        _fail("insufficient_stratum_support", "each required training stratum needs rows")
    w = np.empty(len(f), dtype=np.float64)
    for s in strata:
        w[f == s] = np.float64(1.0) / np.float64(len(strata) * np.count_nonzero(f == s))
    return w


def _support(y: np.ndarray, supplied: Any, name: str) -> np.ndarray:
    if supplied is None:
        m = np.ones(y.shape, dtype=bool)
    else:
        try:
            m = np.asarray(supplied)
        except (ValueError, TypeError) as exc:
            _fail("invalid_support", f"{name} is not a rectangular boolean mask", error=str(exc))
        if m.dtype != np.dtype(bool) or m.shape != y.shape:
            _fail("invalid_support", f"{name} must be a boolean mask of target shape")
        m = m.copy()
    if not np.isfinite(y[m]).all():
        _fail("nonfinite_target", f"{name} marks nonfinite targets as required")
    return m


def _transform_fit(x: np.ndarray, f: np.ndarray, regime: str) -> dict:
    w = balanced_weights(f, regime)
    mean = _sum(w[:, None] * x)
    constant = np.all(x == x[0], axis=0)
    # Exact constants must remain exact even if weighted summation rounded.
    mean[constant] = x[0, constant]
    variance = _sum(w[:, None] * (x - mean) ** 2)
    if np.any((~constant) & (variance <= 0)):
        _fail("unsupported_feature_variance", "nonconstant feature has nonpositive computed variance")
    scale = np.sqrt(variance)
    scale[constant] = 1.0
    if not np.isfinite(mean).all() or not np.isfinite(scale).all():
        _fail("nonfinite_transform", "training transform is not finite")
    return {"mean": mean.tolist(), "scale": scale.tolist(), "constant": constant.tolist()}


def _transform_apply(x: np.ndarray, transform: dict) -> np.ndarray:
    mean, scale = np.asarray(transform["mean"]), np.asarray(transform["scale"])
    constant = np.asarray(transform["constant"], dtype=bool)
    if mean.shape != (x.shape[1],) or scale.shape != mean.shape or constant.shape != mean.shape:
        _fail("invalid_artifact", "transform dimension mismatch")
    if not np.isfinite(mean).all() or not np.isfinite(scale).all() or np.any(scale <= 0):
        _fail("invalid_artifact", "invalid frozen transform")
    z = (x - mean) / scale
    z[:, constant] = 0.0
    if not np.isfinite(z).all():
        _fail("nonfinite_transform", "query or training row cannot be transformed")
    return z


def reference_specs(regime: str) -> list[dict]:
    """Complete allowed portfolio; enumeration order is the exact tie order."""
    _regime(regime)
    specs = [{"family": "training_mean", "variant": "common"}]
    if regime == CALIBRATED:
        specs.append({"family": "training_mean", "variant": "familiarity"})
    specs.append({"family": "OLS_intercept", "lambda": 0.0})
    for lam in LAMBDAS:
        specs.append({"family": "ridge_shared_axis", "lambda": lam})
        if regime == CALIBRATED:
            for multiplier in MULTIPLIERS:
                specs.append({"family": "ridge_familiarity_interaction", "lambda": lam,
                              "interaction_multiplier": multiplier})
        for mapping in ("affine", "isotonic_increasing", "isotonic_decreasing"):
            specs.append({"family": "axis_gain_and_monotone_output", "lambda": lam, "mapping": mapping})
        for width in WIDTHS:
            specs.append({"family": "RBF_kernel_ridge", "lambda": lam, "width_multiplier": width})
    return sorted(specs, key=_tie_key)


def _tie_key(spec: dict) -> tuple:
    return (FAMILIES.index(spec["family"]), -spec.get("lambda", 0.0),
            -spec.get("interaction_multiplier", 0.0),
            WIDTHS.index(spec["width_multiplier"]) if "width_multiplier" in spec else -1,
            ("affine", "isotonic_increasing", "isotonic_decreasing").index(spec["mapping"])
            if "mapping" in spec else -1,
            0 if spec.get("variant", "common") == "common" else 1)


def _check_spec(spec: Any, regime: str) -> dict:
    if not isinstance(spec, dict) or spec not in reference_specs(regime):
        _fail("invalid_specification", "specification is outside the complete declared portfolio")
    return dict(spec)


def _linear_fit(design: np.ndarray, y: np.ndarray, w: np.ndarray,
                penalty: np.ndarray, *, ols: bool = False) -> dict:
    if ols:
        a, b = np.sqrt(w)[:, None] * design, np.sqrt(w) * y
        u, singular, vt = np.linalg.svd(a, full_matrices=False)
        threshold = np.finfo(np.float64).eps * max(design.shape) * singular[0]
        keep = singular > threshold
        coef = vt[keep].T @ ((u[:, keep].T @ b) / singular[keep])
        diagnostics = {"rank": int(np.count_nonzero(keep)), "rank_threshold": float(threshold),
                       "singular_values": singular.tolist(), "rank_dimension": list(design.shape)}
    else:
        gram = np.zeros((design.shape[1], design.shape[1]), dtype=np.float64)
        rhs = np.zeros(design.shape[1], dtype=np.float64)
        for i in range(len(y)):
            gram += w[i] * np.outer(design[i], design[i])
            rhs += (w[i] * y[i]) * design[i]
        gram[np.diag_indices_from(gram)] += penalty
        coef = np.linalg.solve(gram, rhs)
        diagnostics = {"penalty_diagonal": penalty.tolist()}
    if not np.isfinite(coef).all():
        _fail("nonfinite_fit", "linear coefficients are nonfinite")
    return {"coefficients": coef.tolist(), "diagnostics": diagnostics}


def _affine_fit(axis: np.ndarray, y: np.ndarray, w: np.ndarray) -> dict:
    mean_x, mean_y = float(_sum(w * axis)), float(_sum(w * y))
    constant = bool(np.all(axis == axis[0]))
    if constant:
        return {"kind": "affine", "offset": mean_y, "gain": 0.0, "constant_axis": True}
    var = float(_sum(w * (axis - mean_x) ** 2))
    if var <= 0:
        _fail("unsupported_axis_variance", "nonconstant axis has nonpositive variance")
    gain = float(_sum(w * (axis - mean_x) * (y - mean_y))) / var
    return {"kind": "affine", "offset": mean_y - gain * mean_x,
            "gain": gain, "constant_axis": False}


def _isotonic_fit(axis: np.ndarray, y: np.ndarray, w: np.ndarray, increasing: bool) -> dict:
    order = np.argsort(axis, kind="stable")
    knots, weights, sums = [], [], []
    sign = 1.0 if increasing else -1.0
    for i in order:
        value = float(axis[i])
        if knots and value == knots[-1]:
            weights[-1] = float(np.float64(weights[-1]) + w[i])
            sums[-1] = float(np.float64(sums[-1]) + w[i] * y[i] * sign)
        else:
            knots.append(value); weights.append(float(w[i])); sums.append(float(w[i] * y[i] * sign))
    blocks = []
    for j in range(len(knots)):
        blocks.append([j, j + 1, weights[j], sums[j]])
        while len(blocks) > 1 and blocks[-2][3] / blocks[-2][2] > blocks[-1][3] / blocks[-1][2]:
            right, left = blocks.pop(), blocks.pop()
            blocks.append([left[0], right[1], float(np.float64(left[2]) + right[2]),
                           float(np.float64(left[3]) + right[3])])
    fitted = np.empty(len(knots), dtype=np.float64)
    for start, stop, mass, total in blocks:
        fitted[start:stop] = sign * total / mass
    return {"kind": "isotonic", "increasing": increasing, "knots": knots,
            "values": fitted.tolist(), "constant_axis": len(knots) == 1,
            "interpolation": "linear; constant endpoint extrapolation"}


def _mapping_predict(mapping: dict, axis: np.ndarray) -> np.ndarray:
    if mapping["kind"] == "affine":
        return mapping["offset"] + mapping["gain"] * axis
    return np.interp(axis, mapping["knots"], mapping["values"])


def _distances(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    # Avoid the cancellation-prone ||a||²+||b||²-2a.b identity or epsilon repairs.
    distance = np.zeros((len(a), len(b)), dtype=np.float64)
    for j in range(a.shape[1]):
        distance += (a[:, j, None] - b[None, :, j]) ** 2
    return distance


def _kernel_fit(z: np.ndarray, y: np.ndarray, w: np.ndarray, spec: dict) -> dict:
    if len(z) < 2:
        _fail("insufficient_kernel_support", "kernel median requires at least two training rows")
    distance = _distances(z, z)
    pairs = np.sort(distance[np.triu_indices(len(z), k=1)], kind="stable")
    middle = len(pairs) // 2
    median = float(pairs[middle]) if len(pairs) % 2 else float(pairs[middle - 1] / 2 + pairs[middle] / 2)
    mean_y = float(_sum(w * y))
    if median == 0:
        return {"kind": "kernel_constant", "median_squared_distance": 0.0,
                "mean": mean_y, "reason": "zero_training_median", "training_rows": len(z)}
    k = np.exp(-distance / (2 * spec["width_multiplier"] * median))
    row_mean = np.array([float(_sum(row * w)) for row in k])
    grand_mean = float(_sum(w * row_mean))
    centered = k - row_mean[:, None] - row_mean[None, :] + grand_mean
    root_w = np.sqrt(w)
    system = root_w[:, None] * centered * root_w[None, :]
    system[np.diag_indices_from(system)] += spec["lambda"]
    alpha = root_w * np.linalg.solve(system, root_w * (y - mean_y))
    return {"kind": "kernel", "train_features": z.tolist(), "weights": w.tolist(),
            "alpha": alpha.tolist(), "row_mean": row_mean.tolist(), "grand_mean": grand_mean,
            "mean": mean_y, "median_squared_distance": median}


def _fit_output(z: np.ndarray, y: np.ndarray, f: np.ndarray, regime: str, spec: dict) -> dict:
    w = balanced_weights(f, regime)
    family, d = spec["family"], z.shape[1]
    if family == "training_mean":
        if spec["variant"] == "common":
            return {"kind": "mean", "mean": float(_sum(w * y))}
        return {"kind": "group_mean", "means": {str(s): float(_sum(y[f == s] / np.count_nonzero(f == s))) for s in (0, 1)}}
    if family == "RBF_kernel_ridge":
        return _kernel_fit(z, y, w, spec)
    if family == "ridge_familiarity_interaction":
        design = np.column_stack((np.ones(len(z)), f, z, f[:, None] * z))
        penalty = np.r_[0.0, 0.0, np.full(d, spec["lambda"]),
                        np.full(d, spec["lambda"] * spec["interaction_multiplier"])]
        return {"kind": "interaction", **_linear_fit(design, y, w, penalty)}
    design = np.column_stack((np.ones(len(z)), z))
    penalty = np.r_[0.0, np.full(d, spec["lambda"])]
    linear = _linear_fit(design, y, w, penalty, ols=family == "OLS_intercept")
    if family != "axis_gain_and_monotone_output":
        return {"kind": "linear", **linear}
    axis = design @ np.asarray(linear["coefficients"])
    mappings = {}
    for s in ((0, 1) if regime == CALIBRATED else (0,)):
        use = f == s
        sw = np.full(np.count_nonzero(use), 1.0 / np.count_nonzero(use))
        if spec["mapping"] == "affine":
            mappings[str(s)] = _affine_fit(axis[use], y[use], sw)
        else:
            mappings[str(s)] = _isotonic_fit(axis[use], y[use], sw, spec["mapping"] == "isotonic_increasing")
    return {"kind": "axis_map", "axis": linear, "mappings": mappings}


def _predict_output(model: dict, z: np.ndarray, f: np.ndarray, regime: str, spec: dict) -> np.ndarray:
    kind = model["kind"]
    if kind in ("mean", "kernel_constant"):
        return np.full(len(z), model["mean"], dtype=np.float64)
    if kind == "group_mean":
        return np.array([model["means"][str(s)] for s in f], dtype=np.float64)
    if kind == "kernel":
        train, w = np.asarray(model["train_features"]), np.asarray(model["weights"])
        k = np.exp(-_distances(z, train) / (2 * spec["width_multiplier"] * model["median_squared_distance"]))
        query_row_mean = np.array([float(_sum(row * w)) for row in k])
        # This is row-local evaluation against the frozen TRAINING distribution.
        # Neither query-batch moments nor query-query kernels are used.
        centered = k - query_row_mean[:, None] - np.asarray(model["row_mean"])[None, :] + model["grand_mean"]
        return model["mean"] + centered @ np.asarray(model["alpha"])
    if kind == "interaction":
        design = np.column_stack((np.ones(len(z)), f, z, f[:, None] * z))
        return design @ np.asarray(model["coefficients"])
    design = np.column_stack((np.ones(len(z)), z))
    if kind == "linear":
        return design @ np.asarray(model["coefficients"])
    if kind == "axis_map":
        axis = design @ np.asarray(model["axis"]["coefficients"])
        out = np.empty(len(z), dtype=np.float64)
        for s in ((0, 1) if regime == CALIBRATED else (0,)):
            use = f == s if regime == CALIBRATED else np.ones(len(z), dtype=bool)
            out[use] = _mapping_predict(model["mappings"][str(s)], axis[use])
        return out
    _fail("invalid_artifact", "unknown fitted model kind")


def _finite_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=False)
    except (TypeError, ValueError, OverflowError) as exc:
        _fail("invalid_artifact", "artifact is not finite JSON", error=str(exc))


def _seal(value: dict) -> dict:
    value["seal_sha256"] = hashlib.sha256(_finite_json(value).encode("utf-8")).hexdigest()
    return value


def _check_seal(value: Any) -> None:
    if not isinstance(value, dict) or not isinstance(value.get("seal_sha256"), str):
        _fail("invalid_artifact", "missing artifact seal")
    body = {k: v for k, v in value.items() if k != "seal_sha256"}
    digest = hashlib.sha256(_finite_json(body).encode("utf-8")).hexdigest()
    if digest != value["seal_sha256"]:
        _fail("artifact_changed", "frozen artifact digest mismatch")
    if value.get("independent_qualification") is not False:
        _fail("invalid_artifact", "this source cannot claim independent qualification")


def _validate_model(model: dict) -> None:
    """Validate the numerical graph as well as its envelope before inference."""
    try:
        if model["schema"] != "paper020_reference_model_v1" or model["independent_qualification"] is not False:
            _fail("invalid_artifact", "invalid model schema/qualification")
        spec = _check_spec(model["specification"], model["regime"])
        for name in ("features", "outputs", "training_rows"):
            if type(model[name]) is not int or model[name] <= 0:
                _fail("invalid_artifact", "invalid model dimension", dimension=name)
        d, outputs, n = model["features"], model["outputs"], model["training_rows"]
        if len(model["models"]) != outputs:
            _fail("invalid_artifact", "incomplete fitted outputs")
        counts = model["support_counts"]
        if len(counts) != outputs or any(type(v) is not int or not 0 < v <= n for v in counts):
            _fail("invalid_artifact", "invalid fitted support counts")
        transform = model["transform"]
        if (len(transform["constant"]) != d or any(type(v) is not bool for v in transform["constant"])):
            _fail("invalid_artifact", "constant-column mask must be boolean")
        _transform_apply(np.zeros((0, d), dtype=np.float64), transform)
        family = spec["family"]
        expected = {"training_mean": ("mean",) if spec.get("variant") == "common" else ("group_mean",),
                    "OLS_intercept": ("linear",), "ridge_shared_axis": ("linear",),
                    "ridge_familiarity_interaction": ("interaction",),
                    "axis_gain_and_monotone_output": ("axis_map",),
                    "RBF_kernel_ridge": ("kernel", "kernel_constant")}[family]
        for index, output in enumerate(model["models"]):
            kind = output["kind"]
            if kind not in expected:
                _fail("invalid_artifact", "fitted graph disagrees with selected family")
            if kind in ("linear", "interaction", "axis_map"):
                linear = output["axis"] if kind == "axis_map" else output
                coefficients = _array(linear["coefficients"], 1, "coefficients")
                if coefficients.shape != ((2+2*d) if kind == "interaction" else (d+1),):
                    _fail("invalid_artifact", "coefficient shape mismatch")
                if family == "OLS_intercept":
                    diag = linear["diagnostics"]
                    singular = _array(diag["singular_values"], 1, "singular_values")
                    threshold = np.finfo(np.float64).eps * max(counts[index], d+1) * singular[0]
                    if (singular.shape != (min(counts[index], d+1),) or np.any(singular < 0) or
                        np.any(np.diff(singular) > 0) or diag["rank_threshold"] != float(threshold) or
                        diag["rank"] != int(np.count_nonzero(singular > threshold)) or
                        diag["rank_dimension"] != [counts[index], d+1]):
                        _fail("invalid_artifact", "OLS rank record disagrees with frozen rule")
                else:
                    penalty = [0.0] + [spec["lambda"]]*d
                    if kind == "interaction":
                        penalty = [0.0, 0.0] + [spec["lambda"]]*d + [spec["lambda"]*spec["interaction_multiplier"]]*d
                    if linear["diagnostics"]["penalty_diagonal"] != penalty:
                        _fail("invalid_artifact", "penalty record differs from selected objective")
            if kind == "axis_map":
                strata = ("0", "1") if model["regime"] == CALIBRATED else ("0",)
                if set(output["mappings"]) != set(strata):
                    _fail("invalid_artifact", "missing or forbidden familiarity output map")
                for s in strata:
                    mapping = output["mappings"][s]
                    if type(mapping["constant_axis"]) is not bool:
                        _fail("invalid_artifact", "missing explicit constant-axis state")
                    if spec["mapping"] == "affine":
                        if mapping["kind"] != "affine" or (mapping["constant_axis"] and mapping["gain"] != 0):
                            _fail("invalid_artifact", "invalid affine axis map")
                        _array([mapping["offset"], mapping["gain"]], 1, "affine_parameters")
                    else:
                        knots, values = _array(mapping["knots"], 1, "knots"), _array(mapping["values"], 1, "values")
                        increasing = spec["mapping"] == "isotonic_increasing"
                        if (mapping["kind"] != "isotonic" or mapping["increasing"] is not increasing or
                            not len(knots) or knots.shape != values.shape or np.any(np.diff(knots) <= 0) or
                            np.any(np.diff(values) * (1 if increasing else -1) < 0) or
                            mapping["constant_axis"] != (len(knots) == 1)):
                            _fail("invalid_artifact", "invalid isotonic map")
            if kind == "group_mean":
                if set(output["means"]) != {"0", "1"}:
                    _fail("invalid_artifact", "incomplete group means")
                _array(list(output["means"].values()), 1, "group_means")
            if kind in ("mean", "kernel", "kernel_constant"):
                _array([output["mean"]], 1, "mean")
            if kind == "kernel_constant":
                if output["median_squared_distance"] != 0 or output["reason"] != "zero_training_median" or output["training_rows"] != counts[index]:
                    _fail("invalid_artifact", "invalid constant-kernel state")
            if kind == "kernel":
                train = _array(output["train_features"], 2, "kernel_training_features")
                if train.shape != (counts[index], d) or output["median_squared_distance"] <= 0:
                    _fail("invalid_artifact", "invalid frozen kernel support/width")
                for name in ("weights", "alpha", "row_mean"):
                    vector = _array(output[name], 1, name)
                    if vector.shape != (counts[index],):
                        _fail("invalid_artifact", "kernel vector shape mismatch", vector=name)
                    if name == "weights" and np.any(vector <= 0):
                        _fail("invalid_artifact", "nonpositive kernel weight")
                _array([output["grand_mean"]], 1, "kernel_grand_mean")
    except (KeyError, TypeError, IndexError, ValueError) as exc:
        if isinstance(exc, ReferenceError):
            raise
        _fail("invalid_artifact", "malformed model graph", error=str(exc))


def _fit_model(x: np.ndarray, y: np.ndarray, f: np.ndarray, regime: str,
               spec: dict, mask: np.ndarray, transform: dict | None = None) -> dict:
    transform = _transform_fit(x, f, regime) if transform is None else transform
    z = _transform_apply(x, transform)
    outputs = []
    for j in range(y.shape[1]):
        use = mask[:, j]
        outputs.append(_fit_output(z[use], y[use, j], f[use], regime, spec))
    return {"schema": "paper020_reference_model_v1", "regime": regime,
            "specification": dict(spec), "features": x.shape[1], "outputs": y.shape[1],
            "training_rows": len(x), "support_counts": np.count_nonzero(mask, axis=0).tolist(),
            "transform": transform, "models": outputs, "independent_qualification": False}


def fit_reference_model(X_train: Any, targets: Any, familiarity: Any, *, regime: str,
                        specification: dict, support: Any = None) -> dict:
    """Fit one declared family on training only; targets are (rows, outputs)."""
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            x, y = _array(X_train, 2, "X_train"), _array(targets, 2, "targets", finite=False)
            if not all(x.shape) or not all(y.shape) or len(x) != len(y):
                _fail("invalid_shape", "nonempty aligned feature/target axes required")
            f = _familiarity(familiarity, len(x), regime, training=True)
            mask = _support(y, support, "support")
            return _seal(_fit_model(x, y, f, regime, _check_spec(specification, regime), mask))
    except (np.linalg.LinAlgError, FloatingPointError, OverflowError) as exc:
        _fail("numerical_fit_failure", "declared fit failed without a fallback", error=str(exc))


def _model_predict(model: dict, x: np.ndarray, f: np.ndarray) -> np.ndarray:
    if model.get("schema") != "paper020_reference_model_v1" or x.shape[1] != model["features"]:
        _fail("invalid_artifact", "model schema or query feature count mismatch")
    _check_spec(model["specification"], model["regime"])
    z = _transform_apply(x, model["transform"])
    out = np.column_stack([_predict_output(m, z, f, model["regime"], model["specification"])
                           for m in model["models"]])
    if out.shape != (len(x), model["outputs"]) or not np.isfinite(out).all():
        _fail("invalid_prediction", "complete finite model prediction required")
    return out


def predict_reference_model(model: dict, X_query: Any, familiarity: Any) -> np.ndarray:
    """Evaluate sealed one-family model; never update normalization or parameters."""
    _check_seal(model)
    _validate_model(model)
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            x = _array(X_query, 2, "X_query")
            f = _familiarity(familiarity, len(x), model["regime"], training=False)
            return _model_predict(model, x, f)
    except (np.linalg.LinAlgError, FloatingPointError, OverflowError) as exc:
        _fail("numerical_prediction_failure", "frozen inference failed without repair", error=str(exc))
    except (KeyError, TypeError, IndexError, ValueError) as exc:
        if isinstance(exc, ReferenceError):
            raise
        _fail("invalid_artifact", "invalid model structure", error=str(exc))


def _folds(groups: Any, folds: Any, n: int) -> np.ndarray:
    if not isinstance(groups, (list, tuple, np.ndarray)) or len(groups) != n:
        _fail("invalid_groups", "one opaque identity handle required per training row")
    handles = list(groups)
    if any(not isinstance(g, str) or not g for g in handles):
        _fail("invalid_groups", "opaque identity handles must be nonempty strings")
    ids = _array(folds, 1, "inner_folds")
    if ids.shape != (n,) or not np.isin(ids, (0, 1, 2, 3)).all() or set(ids.tolist()) != {0, 1, 2, 3}:
        _fail("invalid_inner_folds", "all four precommitted inner folds are required")
    seen = {}
    for group, fold in zip(handles, ids):
        if group in seen and seen[group] != fold:
            _fail("identity_fold_leakage", "one identity crosses inner folds", identity=group)
        seen[group] = fold
    return ids.astype(np.int8)


def _require_support(mask: np.ndarray, f: np.ndarray, regime: str, *, fold: int, stage: str) -> None:
    for s in ((0, 1) if regime == CALIBRATED else (0,)):
        if not np.all(np.any(mask[f == s], axis=0)):
            _fail("insufficient_stratum_support", "every fold/output/stratum must retain source support",
                  fold=fold, stage=stage, stratum=s)


def _risk(prediction: np.ndarray, y: np.ndarray, mask: np.ndarray, f: np.ndarray, regime: str) -> float:
    # y/prediction have one neuron's complete time axis. Each source-supported
    # original row is weighted equally within its stratum and time output.
    strata = (0, 1) if regime == CALIBRATED else (0,)
    risk = np.float64(0.0)
    for t in range(y.shape[1]):
        time_risk = np.float64(0.0)
        for s in strata:
            use = mask[:, t] & (f == s)
            if not np.any(use):
                _fail("insufficient_stratum_support", "OOF risk has an unsupported output/stratum")
            error = (prediction[use, t] - y[use, t]) ** 2
            time_risk += _sum(error) / np.float64(len(error))
        risk += time_risk / np.float64(len(strata))
    risk = risk / np.float64(y.shape[1])
    if not np.isfinite(risk):
        _fail("nonfinite_risk", "complete OOF risk is not finite")
    return float(risk)


def select_fit_reference(X_train: Any, time_targets: Any, static_targets: Any,
                         familiarity: Any, identity_groups: Any, inner_folds: Any, *,
                         regime: str, time_support: Any = None, static_support: Any = None) -> dict:
    """Select every neuron's family/spec on complete OOF TIME risk, then full-fit.

    Four grouped folds are supplied by the trusted owner, never chosen from
    outcomes here. The same selected spec fits that neuron's static companion.
    All declared specs run in every fold; any failure invalidates the complete
    selection. The returned plain finite-JSON object has an integrity seal.
    """
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            x = _array(X_train, 2, "X_train")
            time = _array(time_targets, 3, "time_targets", finite=False)
            static = _array(static_targets, 2, "static_targets", finite=False)
            if not all(x.shape) or not all(time.shape) or static.shape != time.shape[:2] or len(x) != len(time):
                _fail("invalid_shape", "features and full static/time target axes must align and be nonempty")
            f = _familiarity(familiarity, len(x), regime, training=True)
            folds = _folds(identity_groups, inner_folds, len(x))
            tm, sm = _support(time, time_support, "time_support"), _support(static, static_support, "static_support")
            n, neurons, times = time.shape
            all_mask = np.concatenate((tm.reshape(n, -1), sm), axis=1)
            specs = reference_specs(regime)
            risks = np.empty((len(specs), neurons), dtype=np.float64)
            # Preflight all support before the first numerical fit.
            for fold in range(4):
                for stage, use in (("training", folds != fold), ("validation", folds == fold)):
                    _require_support(all_mask[use], f[use], regime, fold=fold, stage=stage)
            transforms = {fold: _transform_fit(x[folds != fold], f[folds != fold], regime) for fold in range(4)}
            for index, spec in enumerate(specs):
                oof = np.empty(time.shape, dtype=np.float64)
                for fold in range(4):
                    train, valid = folds != fold, folds == fold
                    try:
                        fitted = _fit_model(x[train], time[train].reshape(np.count_nonzero(train), -1),
                                            f[train], regime, spec,
                                            tm[train].reshape(np.count_nonzero(train), -1), transforms[fold])
                        oof[valid] = _model_predict(fitted, x[valid], f[valid]).reshape(np.count_nonzero(valid), neurons, times)
                    except ReferenceError as exc:
                        _fail("portfolio_fit_failed", "a declared family failed; no family omission permitted",
                              specification=spec, fold=fold, cause=exc.code, cause_details=exc.details)
                for neuron in range(neurons):
                    risks[index, neuron] = _risk(oof[:, neuron], time[:, neuron], tm[:, neuron], f, regime)
            selected = []
            full_transform = _transform_fit(x, f, regime)
            for neuron in range(neurons):
                # np.argmin chooses first EXACT minimum: specs already carry the
                # complete frozen tie order. No tolerance or query criterion.
                index = int(np.argmin(risks[:, neuron]))
                spec = specs[index]
                target = np.column_stack((time[:, neuron], static[:, neuron]))
                support = np.column_stack((tm[:, neuron], sm[:, neuron]))
                fitted = _fit_model(x, target, f, regime, spec, support, full_transform)
                selected.append({"neuron_index": neuron, "specification_index": index,
                                 "specification": dict(spec), "time_OOF_risk": float(risks[index, neuron]),
                                 "model": fitted})
            families = [{"family": family,
                         "specification_indices": [i for i, s in enumerate(specs) if s["family"] == family],
                         "minimum_time_OOF_risk_per_neuron": [float(min(risks[i, j] for i, s in enumerate(specs) if s["family"] == family)) for j in range(neurons)]}
                        for family in FAMILIES if any(s["family"] == family for s in specs)]
            artifact = {"schema": SCHEMA, "state": "complete_fit_frozen", "regime": regime,
                        "independent_qualification": False, "features": x.shape[1], "neurons": neurons,
                        "time_outputs": times, "static_outputs_per_neuron": 1, "training_rows": n,
                        "inner_folds": 4, "specifications": specs, "time_OOF_risks": risks.tolist(),
                        "family_diagnostics": families, "selected": selected,
                        "support_counts": {"time": np.count_nonzero(tm, axis=0).tolist(), "static": np.count_nonzero(sm, axis=0).tolist()},
                        "numerical_contract": dict(NUMERICAL_CONTRACT),
                        "runtime": {"python": platform.python_version(), "numpy": np.__version__,
                                    "solver": "numpy.linalg.svd/solve", "runtime_qualified": False},
                        "query_access_during_fit": False,
                        "caller_obligations": "authenticate source masks/groups/feature schema/full scope; independently admit runtime and exposure"}
            return _seal(artifact)
    except (np.linalg.LinAlgError, FloatingPointError, OverflowError) as exc:
        _fail("numerical_fit_failure", "complete portfolio failed without fallback", error=str(exc))


def _validate_artifact(artifact: Any) -> None:
    _check_seal(artifact)
    try:
        if artifact["schema"] != SCHEMA or artifact["state"] != "complete_fit_frozen":
            _fail("invalid_artifact", "unknown or incomplete reference artifact")
        specs = reference_specs(artifact["regime"])
        if artifact["specifications"] != specs or artifact["numerical_contract"] != NUMERICAL_CONTRACT:
            _fail("invalid_artifact", "changed portfolio or numerical contract")
        for name in ("features", "neurons", "time_outputs", "training_rows"):
            if type(artifact[name]) is not int or artifact[name] <= 0:
                _fail("invalid_artifact", "positive integer dimensions required", dimension=name)
        risks = _array(artifact["time_OOF_risks"], 2, "time_OOF_risks")
        if risks.shape != (len(specs), artifact["neurons"]) or np.any(risks < 0):
            _fail("invalid_artifact", "incomplete risk panel")
        if len(artifact["selected"]) != artifact["neurons"] or artifact["query_access_during_fit"] is not False or artifact["inner_folds"] != 4:
            _fail("invalid_artifact", "incomplete selection or invalid fit boundary")
        for neuron, item in enumerate(artifact["selected"]):
            i = int(np.argmin(risks[:, neuron]))
            model = item["model"]
            _validate_model(model)
            if (item["neuron_index"] != neuron or item["specification_index"] != i or
                item["specification"] != specs[i] or model["specification"] != specs[i] or
                item["time_OOF_risk"] != float(risks[i, neuron]) or model["regime"] != artifact["regime"] or
                model["outputs"] != artifact["time_outputs"] + 1 or model["features"] != artifact["features"] or
                len(model["models"]) != model["outputs"] or model["independent_qualification"] is not False):
                _fail("invalid_artifact", "selected full fit does not match time-only selector")
    except (KeyError, TypeError, IndexError, ValueError) as exc:
        if isinstance(exc, ReferenceError):
            raise
        _fail("invalid_artifact", "malformed reference artifact", error=str(exc))


def predict_reference(artifact: dict, X_query: Any, familiarity: Any) -> dict[str, np.ndarray]:
    """Frozen row-local inference. No target, group, fit or batch-statistic input."""
    _validate_artifact(artifact)
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            x = _array(X_query, 2, "X_query")
            f = _familiarity(familiarity, len(x), artifact["regime"], training=False)
            time = np.empty((len(x), artifact["neurons"], artifact["time_outputs"]), dtype=np.float64)
            static = np.empty((len(x), artifact["neurons"]), dtype=np.float64)
            for neuron, selected in enumerate(artifact["selected"]):
                output = _model_predict(selected["model"], x, f)
                time[:, neuron], static[:, neuron] = output[:, :-1], output[:, -1]
            return {"time": time, "static": static}
    except (np.linalg.LinAlgError, FloatingPointError, OverflowError) as exc:
        _fail("numerical_prediction_failure", "frozen inference failed without repair", error=str(exc))
    except (KeyError, TypeError, IndexError, ValueError) as exc:
        if isinstance(exc, ReferenceError):
            raise
        _fail("invalid_artifact", "malformed selected model", error=str(exc))


def freeze_reference(artifact: dict) -> str:
    """Return canonical finite JSON for storage by an authorized caller."""
    _validate_artifact(artifact)
    return _finite_json(artifact)


def thaw_reference(serialized: str) -> dict:
    """Reject duplicate keys, nonfinite constants, altered or incomplete artifacts."""
    def pairs(items: list) -> dict:
        result = {}
        for key, value in items:
            if key in result:
                _fail("duplicate_json_key", "duplicate artifact JSON key", key=key)
            result[key] = value
        return result

    def constant(value: str) -> None:
        _fail("nonfinite_json", "nonfinite JSON constant", value=value)

    if not isinstance(serialized, str):
        _fail("invalid_json", "serialized artifact must be a string")
    try:
        artifact = json.loads(serialized, object_pairs_hook=pairs, parse_constant=constant)
    except (json.JSONDecodeError, OverflowError, RecursionError) as exc:
        _fail("invalid_json", "malformed artifact JSON", error=str(exc))
    _validate_artifact(artifact)
    return artifact
