"""Exact selected ordinary mathematical source from vendor/context.py.
No CLI/file/provider entrypoint; imported only inside separately authorized methods.
Native/numerical equivalence remains unqualified. Original source and notices
remain in the immutable vendor closure. See SOURCE_EXTRACTIONS.json.
"""
import math
import numpy as np


BIN_COUNT = 140

HYPOTHESIS_SPECS = (
    ("psth_sigma10_kappa1", 10, 1.0),
    ("psth_sigma0_kappa0p25", 0, .25),
    ("psth_sigma0_kappa1p0", 0, 1.0),
    ("psth_sigma0_kappa4p0", 0, 4.0),
    ("psth_sigma5_kappa0p25", 5, .25),
    ("psth_sigma5_kappa1p0", 5, 1.0),
    ("psth_sigma5_kappa4p0", 5, 4.0),
    ("psth_sigma10_kappa0p25", 10, .25),
    ("psth_sigma10_kappa4p0", 10, 4.0),
    ("psth_sigma20_kappa0p25", 20, .25),
    ("psth_sigma20_kappa1p0", 20, 1.0),
    ("psth_sigma20_kappa4p0", 20, 4.0),
    ("training_constant", None, None),
)

def require(condition, message):
    if not condition:
        raise ValueError(message)

def ordered_hypotheses():
    return [{"id": name, "sigma_bins": sigma,
             "sigma_ms": None if sigma is None else sigma * 5,
             "pseudotrials": kappa,
             "kernel_length": None if sigma is None else (1 if sigma == 0 else 6 * sigma),
             "fixed_comparator_formula": position == 0}
            for position, (name, sigma, kappa) in enumerate(HYPOTHESIS_SPECS)]

def kernel(sigma_bins):
    require(type(sigma_bins) is int and sigma_bins in (0, 5, 10, 20), "Fixed bandwidth required")
    if sigma_bins == 0:
        return np.ones(1, dtype=np.float64)
    length = 6 * sigma_bins
    coordinates = np.arange(length, dtype=np.float64) - (length - 1) / 2.0
    weights = np.exp(-.5 * (coordinates / sigma_bins) ** 2)
    weights /= weights.sum(dtype=np.float64)
    require(np.isfinite(weights).all() and (weights > 0).all(), "Invalid kernel")
    return weights

def smooth_profiles(profiles, sigma_bins):
    profiles = np.asarray(profiles, dtype=np.float64)
    require(profiles.ndim == 3 and profiles.shape[0] > 0 and
            profiles.shape[1] == BIN_COUNT and profiles.shape[2] > 0 and
            np.isfinite(profiles).all(), "Finite condition x140 xunit profiles required")
    weights = kernel(sigma_bins)
    denominator = np.convolve(np.ones(BIN_COUNT, dtype=np.float64), weights, mode="same")
    result = np.empty_like(profiles, dtype=np.float64)
    for condition in range(profiles.shape[0]):
        for unit in range(profiles.shape[2]):
            result[condition, :, unit] = np.convolve(profiles[condition, :, unit], weights, mode="same") / denominator
    require(np.isfinite(result).all(), "Nonfinite smoothed profiles")
    return result

def validate_targets(y, conditions):
    y = np.asarray(y)
    conditions = np.asarray(conditions)
    require(y.ndim == 3 and y.shape[0] > 0 and y.shape[1] == BIN_COUNT and y.shape[2] > 0,
            "Nonempty trial x140 xunit targets required")
    require(y.dtype.kind in "uif" and np.isfinite(y).all() and (y >= 0).all() and
            (y == np.floor(y)).all(), "Nonnegative finite integer training targets required")
    require(conditions.ndim == 1 and conditions.shape == (len(y),) and conditions.dtype.kind == "U" and
            all(bool(x) for x in conditions.tolist()), "Unicode training conditions required")
    return y, conditions

def fit_statistics(y, conditions):
    y, conditions = validate_targets(y, conditions)
    names, inverse, counts = np.unique(conditions, return_inverse=True, return_counts=True)
    sums = np.stack([y[inverse == index].sum(axis=0, dtype=np.float64)
                     for index in range(len(names))])
    mu = (y.sum(axis=(0, 1), dtype=np.float64) + .5) / (len(y) * BIN_COUNT + 1)
    require(np.isfinite(sums).all() and np.isfinite(mu).all() and (mu > 0).all(), "Invalid fitting statistics")
    return {"mu": mu, "group_sums": sums, "condition_names": names,
            "condition_counts": counts, "n_trials": len(y)}

def profiles_for_hypothesis(stats, hypothesis):
    require(hypothesis in ordered_hypotheses(), "Exact fixed hypothesis required")
    mu = stats["mu"]
    if hypothesis["id"] == "training_constant":
        profiles = np.broadcast_to(mu, stats["group_sums"].shape).copy()
    else:
        kappa = hypothesis["pseudotrials"]
        raw = (stats["group_sums"] + kappa * mu[None, None, :]) / (stats["condition_counts"][:, None, None] + kappa)
        profiles = smooth_profiles(raw, hypothesis["sigma_bins"])
    require(np.isfinite(profiles).all() and (profiles > 0).all(), "Invalid condition model; no clipping allowed")
    return {"hypothesis_id": hypothesis["id"], "condition_names": stats["condition_names"].copy(),
            "profiles": profiles, "fallback": mu.copy(), "n_trials": stats["n_trials"]}

def predict_profiles(model, query_conditions):
    conditions = np.asarray(query_conditions)
    require(conditions.ndim == 1 and len(conditions) > 0 and conditions.dtype.kind == "U" and
            all(bool(x) for x in conditions.tolist()), "Nonempty Unicode query conditions required")
    mapping = {name: index for index, name in enumerate(model["condition_names"].tolist())}
    result = np.empty((len(conditions), BIN_COUNT, len(model["fallback"])), dtype=np.float64)
    for row, condition in enumerate(conditions.tolist()):
        index = mapping.get(condition)
        result[row] = model["fallback"] if index is None else model["profiles"][index]
    require(np.isfinite(result).all() and (result > 0).all(), "Nonpositive or nonfinite predictions")
    return result

def pooled_log_likelihood(y, prediction):
    y = np.asarray(y, dtype=np.float64)
    prediction = np.asarray(prediction, dtype=np.float64)
    require(y.shape == prediction.shape and y.size > 0 and np.isfinite(y).all() and
            (y >= 0).all() and (y == np.floor(y)).all(), "Finite aligned count labels required")
    require(np.isfinite(prediction).all() and (prediction > 0).all(), "Positive finite means required")
    terms = y * np.log(prediction) - prediction
    result = float(np.sum(terms.ravel(order="C"), dtype=np.float64))
    require(math.isfinite(result), "Nonfinite pooled likelihood")
    return result

def validate_selection_result(selection):
    """Scalar, standard-library gate before all-training refit; no numerical import needed."""
    require(type(selection) is dict and set(selection) == {"rows", "selected_hypothesis_id",
            "internal_validation_spikes", "hypotheses_attempted", "hypotheses_completed"}, "Selection schema")
    require(type(selection["hypotheses_attempted"]) is int and selection["hypotheses_attempted"] == 13 and
            type(selection["hypotheses_completed"]) is int and selection["hypotheses_completed"] == 13,
            "All thirteen hypotheses must return before refit")
    rows = selection["rows"]
    require(type(rows) is list and len(rows) == 13, "Thirteen ordered selection rows required")
    spikes = selection["internal_validation_spikes"]
    require(type(spikes) is int and spikes > 0, "Positive internal validation spike count required")
    best = 0
    for index, (row, spec) in enumerate(zip(rows, HYPOTHESIS_SPECS)):
        require(type(row) is dict and set(row) == {"hypothesis_id", "ll", "gain_bits_per_spike"} and
                row["hypothesis_id"] == spec[0], "Exact ordered hypothesis identity required")
        require(type(row["ll"]) is float and math.isfinite(row["ll"]) and
                type(row["gain_bits_per_spike"]) is float and math.isfinite(row["gain_bits_per_spike"]),
                "Finite float selection scores required")
        require(row["gain_bits_per_spike"] == (row["ll"] - rows[0]["ll"]) / (spikes * math.log(2.0)),
                "Internal pooled gain arithmetic changed")
        if row["ll"] > rows[best]["ll"]:
            best = index
    require(selection["selected_hypothesis_id"] == rows[best]["hypothesis_id"], "Strict first-wins selection changed")
    return selection

def select_model(y, conditions, fit_indices, val_indices, progress=None):
    y, conditions = validate_targets(y, conditions)
    fit_indices, val_indices = np.asarray(fit_indices), np.asarray(val_indices)
    for indices in (fit_indices, val_indices):
        require(indices.ndim == 1 and len(indices) > 0 and indices.dtype.kind in "iu" and
                (indices >= 0).all() and (indices < len(y)).all() and
                (np.diff(indices.astype(np.int64)) > 0).all(), "Ordered unique split rows required")
    require(np.array_equal(np.sort(np.concatenate((fit_indices, val_indices))), np.arange(len(y))), "Split must partition all training rows")
    stats = fit_statistics(y[fit_indices], conditions[fit_indices])
    validation_y = y[val_indices].astype(np.float64)
    spikes_float = float(validation_y.sum(dtype=np.float64))
    require(math.isfinite(spikes_float) and spikes_float > 0 and spikes_float.is_integer(), "Internal validation must contain spikes")
    spikes = int(spikes_float)
    rows = []
    best = 0
    for index, hypothesis in enumerate(ordered_hypotheses()):
        if progress:
            progress("hypothesis_started", {"index": index, "hypothesis_id": hypothesis["id"]})
        model = profiles_for_hypothesis(stats, hypothesis)
        prediction = predict_profiles(model, conditions[val_indices])
        ll = pooled_log_likelihood(validation_y, prediction)
        baseline_ll = ll if index == 0 else rows[0]["ll"]
        row = {"hypothesis_id": hypothesis["id"], "ll": ll,
               "gain_bits_per_spike": (ll - baseline_ll) / (spikes * math.log(2.0))}
        rows.append(row)
        if ll > rows[best]["ll"]:
            best = index
        if progress:
            progress("hypothesis_returned", {"index": index, "row": row.copy()})
    selection = {"rows": rows, "selected_hypothesis_id": rows[best]["hypothesis_id"],
                 "internal_validation_spikes": spikes, "hypotheses_attempted": 13, "hypotheses_completed": 13}
    return validate_selection_result(selection)

def refit_selected(y, conditions, selected_id):
    matching = [h for h in ordered_hypotheses() if h["id"] == selected_id]
    require(len(matching) == 1, "Selected hypothesis outside fixed family")
    return profiles_for_hypothesis(fit_statistics(y, conditions), matching[0])

def select_then_refit(y, conditions, fit_indices, val_indices, progress=None):
    if progress:
        progress("selection_started", {})
    selection = select_model(y, conditions, fit_indices, val_indices, progress=progress)
    validate_selection_result(selection)
    if progress:
        progress("selection_returned", selection)
        progress("refit_started", {"completed_hypotheses_before_refit": 13})
    model = refit_selected(y, conditions, selection["selected_hypothesis_id"])
    if progress:
        progress("refit_returned", {"refit_trials": len(y)})
    return selection, model
