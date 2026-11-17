"""Rat GLM reconstruction and covariance geometry, independently implemented.

The source reconstruction deliberately retains its full-session preprocessing.
The train-only recipe is a prospective extension and is never labeled reproduction.
No download, native NWB ingestion, or benchmark qualification is performed here.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import io
import json
from pathlib import Path
import warnings

import numpy as np

TASK_ID = "PAPER-paper-method-add-006"
SOURCE_REVISION = "9674a6cb0c39926d70746024ce17de35f87df8f9"
ANIMALS = ("KL8", "ER1", "JS34", "JS14", "JS17", "JS21", "JS15", "ZT2")
REGIONS = ("CA1", "PFC")
DT = 0.5
HOLDS = [
    "native_NWB_ingestion_and_exact_epoch_mapping_unverified",
    "full_empirical_population_and_independent_reference_unexecuted",
    "paper_numeric_targets_tolerances_and_primary_region_contrast_unfrozen",
    "animal_session_holdout_improvement_not_qualified",
    "source_code_and_data_rights_require_separate_release_review",
    "protected_assessment_and_public_result_exposure_policy_unfrozen",
    "whole_paper_simulations_non_rat_comparisons_and_optimality_not_established",
    "published_CA1_24_units_vs_pinned_raw_geometry_19_units_unreconciled",
    "mixed_effect_quadratic_session_trends_and_nonlinear_readouts_not_implemented",
]


class ContractError(ValueError):
    """A numerical or scientific precondition was violated."""


def matrix(value, name, columns=None):
    a = np.asarray(value, dtype=float)
    if a.ndim != 2 or min(a.shape) == 0 or not np.isfinite(a).all():
        raise ContractError(f"{name} must be a nonempty finite matrix")
    if columns is not None and a.shape[1] != columns:
        raise ContractError(f"{name} requires {columns} columns")
    return a


def latents(value):
    z = matrix(value, "latents", 7)
    if not np.isin(z[:, 6], [0, 1]).all():
        raise ContractError("trajectory type must be binary 0/1")
    return z


def counts_array(value, nrows):
    x = matrix(value, "counts")
    if x.shape[0] != nrows or (x < 0).any() or not np.equal(x, np.floor(x)).all():
        raise ContractError("counts must be nonnegative integers aligned to latent rows")
    return x


@dataclass(frozen=True)
class BasisParameters:
    position_bin: float
    velocity_bin: float
    position_variance: float
    velocity_variance: float
    min_count: int = 20

    def __post_init__(self):
        values = [self.position_bin, self.velocity_bin,
                  self.position_variance, self.velocity_variance]
        if not all(np.isfinite(v) and v > 0 for v in values):
            raise ContractError("basis bins and variances must be finite and positive")
        if isinstance(self.min_count, bool) or int(self.min_count) != self.min_count or self.min_count < 0:
            raise ContractError("min_count must be a nonnegative integer")


def fit_basis(z_centered, params):
    """Freeze rounded centers with STRICT count > min_count, as in rat_utils."""
    z = latents(z_centered)
    result = {}
    for name, values, size in [("position", z[:, :2], params.position_bin),
                               ("vx", z[:, 3], params.velocity_bin),
                               ("vy", z[:, 4], params.velocity_bin)]:
        centers, counts = np.unique(np.round(values / size) * size, axis=0, return_counts=True)
        result[name] = centers[counts > params.min_count]
        if len(result[name]) == 0:
            raise ContractError(f"no {name} centers survive strict occupancy threshold")
    return result


def design_matrix(z, basis, params):
    """Normalized Gaussian x/y, vx, vy bases; trajectory gates spatial bases only."""
    z = latents(z)
    position = matrix(basis["position"], "position centers", 2)
    vx, vy = (np.asarray(basis[k], dtype=float) for k in ("vx", "vy"))
    if any(a.ndim != 1 or not len(a) or not np.isfinite(a).all() for a in (vx, vy)):
        raise ContractError("velocity centers must be finite nonempty vectors")
    spatial = np.exp(-np.sum((z[:, None, :2] - position[None]) ** 2, axis=2)
                     / (2 * params.position_variance)) / (2 * np.pi * params.position_variance)
    velocity = [np.exp(-(z[:, j, None] - centers[None]) ** 2 / (2 * params.velocity_variance))
                / np.sqrt(2 * np.pi * params.velocity_variance)
                for j, centers in ((3, vx), (4, vy))]
    return np.column_stack([spatial * (z[:, 6, None] == 0),
                            spatial * (z[:, 6, None] == 1), *velocity])


def standardize_train(train, test):
    """Train-only population standard deviation; constant columns are rejected."""
    train, test = matrix(train, "train design"), matrix(test, "test design")
    if train.shape[1] != test.shape[1]:
        raise ContractError("design column mismatch")
    mean, std = train.mean(axis=0), train.std(axis=0)
    if (std == 0).any():
        raise ContractError("constant basis column; source standardization would be undefined")
    return (train - mean) / std, (test - mean) / std, mean, std


def prepare_glm_session(z, counts):
    """Author GLM mask uses recorded speed, then centers positions per session."""
    z = latents(z)
    x = counts_array(counts, len(z))
    row_mask = z[:, 2] > 4.0
    if row_mask.sum() < 2:
        raise ContractError("insufficient locomotion rows")
    out = z[row_mask].copy()
    out[:, :2] -= out[:, :2].mean(axis=0)
    x = x[row_mask]
    unit_mask = x.mean(axis=0) / DT > 0.1
    if not unit_mask.any():
        raise ContractError("no units pass strict 0.1 Hz cutoff")
    return out, x[:, unit_mask], row_mask, unit_mask


def prepare_geometry_session(z, counts, locations, region):
    """Author raw geometry path: velocity norm, rate filter, response regularization."""
    z = latents(z)
    x = counts_array(counts, len(z))
    loc = np.asarray(locations)
    if region not in REGIONS or loc.shape != (x.shape[1],):
        raise ContractError("region or unit-location alignment invalid")
    row_mask = np.linalg.norm(z[:, 3:5], axis=1) > 4.0
    if row_mask.sum() < 2:
        raise ContractError("insufficient vector-velocity locomotion rows")
    x, selected_z = x[row_mask], z[row_mask][:, [0, 1, 3, 4]]
    unit_mask = (loc == region) & (x.mean(axis=0) / DT > 0.1)
    x = x[:, unit_mask]
    if not x.shape[1] or (selected_z.std(axis=0) == 0).any():
        raise ContractError("no eligible units or constant geometry latent")
    x = (x - x.mean(axis=0)) / (x.std(axis=0) + 0.01)
    selected_z = (selected_z - selected_z.mean(axis=0)) / selected_z.std(axis=0)
    return x, selected_z, row_mask, unit_mask


def participation_ratio(x, epsilon=0.01):
    x = matrix(x, "responses")
    if not np.isfinite(epsilon) or epsilon <= 0:
        raise ContractError("epsilon must be positive")
    x = (x - x.mean(axis=0)) / (x.std(axis=0) + epsilon)
    covariance = x.T @ x / len(x)
    denominator = np.sum(covariance ** 2)
    return float(np.trace(covariance) ** 2 / denominator) if denominator else 0.0


def geometry_from_covariance(psi, phi, omega, training_samples=300):
    """Author eight geometric measures plus independent direct theoretical error.

    Infinite noise/signal factors are legitimate exact zero-noise limits. Singular
    latent covariance and zero total alignment are rejected, never regularized away.
    """
    psi, phi, omega = matrix(psi, "psi"), matrix(phi, "phi"), matrix(omega, "omega")
    n, d = phi.shape
    if psi.shape != (n, n) or omega.shape != (d, d):
        raise ContractError("covariance block shapes do not agree")
    if isinstance(training_samples, bool) or int(training_samples) != training_samples or training_samples <= 0:
        raise ContractError("training_samples must be a positive integer")
    joint = np.block([[psi, phi], [phi.T, omega]])
    scale = float(np.linalg.norm(joint, ord=2))
    if not np.isfinite(scale) or scale == 0:
        raise ContractError("covariance scale is zero or nonfinite")
    if not np.allclose(joint / scale, joint.T / scale, rtol=1e-10, atol=1e-12):
        raise ContractError("covariance must be symmetric")
    tol = scale * 1e-10
    if np.linalg.eigvalsh(joint).min() < -tol:
        raise ContractError("joint covariance must be positive semidefinite")
    if np.linalg.eigvalsh(omega).min() <= np.linalg.norm(omega, ord=2) * 1e-12:
        raise ContractError("latent covariance is singular or ill conditioned")
    trace_x, trace_z = float(np.trace(psi)), float(np.trace(omega))
    gram = phi.T @ phi
    signal = float(np.trace(gram))
    if min(trace_x, trace_z, signal) <= 0:
        raise ContractError("nonzero neural variance, latent variance, and alignment required")
    task_covariance = phi @ np.linalg.solve(omega, phi.T)
    noise_denominator = float(np.trace(phi.T @ (psi - task_covariance) @ phi))
    signal_denominator = float(np.trace(gram @ np.linalg.solve(omega, gram)))
    noise_tol = 1e-10 * abs(float(np.trace(phi.T @ psi @ phi)))
    if noise_denominator < -noise_tol:
        raise ContractError("negative residual covariance contribution")
    noise_denominator = max(noise_denominator, 0.0)
    dimension = trace_x ** 2 / np.sum(psi ** 2)
    alignment = signal / (trace_x * trace_z)
    inv_snf = trace_z * noise_denominator / signal ** 2
    inv_ssf = trace_z * signal_denominator / signal ** 2
    square_error = np.pi / (2 * training_samples * alignment ** 2 * dimension) + inv_snf + inv_ssf - 1
    if square_error < -1e-10:
        raise ContractError("negative theoretical error radicand")
    direct = trace_z * (np.pi / training_samples * np.sum(psi ** 2) * trace_z
                       + 2 * (np.trace(phi.T @ psi @ phi) - signal ** 2 / trace_z))
    if direct < -1e-10 * signal ** 2:
        raise ContractError("negative direct theory radicand")
    return {
        "dimensionality": float(dimension), "alignment": float(alignment),
        "signal_noise_factor": float(1 / inv_snf) if inv_snf else float("inf"),
        "signal_signal_factor": float(1 / inv_ssf),
        "normalized_task_dimension": float(np.trace(task_covariance) ** 2 / np.sum(task_covariance ** 2) / d),
        "normalized_latent_dimension": float(trace_z ** 2 / np.sum(omega ** 2) / d),
        "weighted_factorization": float(np.sum(gram ** 2) / signal ** 2),
        "generalization_error": float(np.arctan(np.sqrt(max(square_error, 0))) / np.pi),
        "theory_error": float(np.arctan(np.sqrt(max(direct, 0)) / (np.sqrt(2) * signal)) / np.pi),
    }


def covariance_geometry(x, z, training_samples=300):
    x, z = matrix(x, "responses"), matrix(z, "geometry latents")
    if len(x) != len(z) or len(x) < 2:
        raise ContractError("response/latent alignment or sample count invalid")
    joined = np.column_stack([x, z])
    joined -= joined.mean(axis=0)
    covariance = joined.T @ joined / len(joined)
    n = x.shape[1]
    return geometry_from_covariance(covariance[:n, :n], covariance[:n, n:], covariance[n:, n:], training_samples)


def poisson_deviance(y, prediction):
    y, prediction = np.asarray(y, dtype=float), np.asarray(prediction, dtype=float)
    if y.shape != prediction.shape or not y.size or not np.isfinite(y).all() or not np.isfinite(prediction).all() or (y < 0).any() or (prediction <= 0).any():
        raise ContractError("Poisson score requires aligned nonnegative outcomes and positive predictions")
    term = prediction - y
    positive = y > 0
    term[positive] += y[positive] * np.log(y[positive] / prediction[positive])
    return float(2 * np.mean(term))


def poisson_d2(y, prediction):
    y = np.asarray(y, dtype=float)
    model_deviance = poisson_deviance(y, prediction)
    if y.mean() == 0:
        return float("nan")
    null = poisson_deviance(y, np.full_like(y, y.mean(), dtype=float))
    return float(1 - model_deviance / null) if null > 0 else float("nan")


def _fit_poisson(design, y, alpha):
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.linear_model import PoissonRegressor
    # Author default solver/tolerance/iteration limit; fail visibly on nonconvergence.
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        return PoissonRegressor(alpha=float(alpha)).fit(design, y)


def source_glm_fit(z, counts, pooled_latents, params, alphas=None, folds=10):
    """Fit author-style per-unit Poisson GLM to ONE already area-selected session.

    pooled_latents must be all eight separately speed-filtered, position-centered
    sessions for the SAME animal. This entrypoint does not attest that provenance.
    Alpha selection uses mean finite D2 over unshuffled KFold, as source GridSearchCV.
    """
    from sklearn.model_selection import KFold
    z, x, rows, units = prepare_glm_session(z, counts)
    basis = fit_basis(pooled_latents, params)
    design = design_matrix(z, basis, params)
    design, _, mean, std = standardize_train(design, design)
    alphas = np.asarray(np.logspace(-0.5, 2, 10) if alphas is None else alphas, dtype=float)
    if alphas.ndim != 1 or not len(alphas) or not np.isfinite(alphas).all() or (alphas <= 0).any() or len(np.unique(alphas)) != len(alphas):
        raise ContractError("distinct positive regularization strengths required")
    if isinstance(folds, bool) or not isinstance(folds, (int, np.integer)) or not 2 <= folds <= len(z):
        raise ContractError("invalid number of CV folds")
    scores = np.full((x.shape[1], len(alphas), folds), np.nan)
    splits = list(KFold(n_splits=folds, shuffle=False).split(design))
    fitted = np.empty_like(x, dtype=float)
    chosen = []
    for unit in range(x.shape[1]):
        for a, alpha in enumerate(alphas):
            for f, (train, test) in enumerate(splits):
                if x[train, unit].sum() == 0:
                    raise ContractError("all-zero training unit cannot fit author Poisson GLM")
                model = _fit_poisson(design[train], x[train, unit], alpha)
                scores[unit, a, f] = poisson_d2(x[test, unit], model.predict(design[test]))
        valid = np.isfinite(scores[unit]).sum(axis=1)
        sums = np.nansum(scores[unit], axis=1)
        means = np.divide(sums, valid, out=np.full(len(alphas), -np.inf), where=valid > 0)
        if not np.isfinite(means).any():
            raise ContractError("all CV scores undefined; no defensible alpha selection")
        best = int(np.argmax(means))
        chosen.append(best)
        fitted[:, unit] = _fit_poisson(design, x[:, unit], alphas[best]).predict(design)
    return {"recipe": "author_source_session_reconstruction", "counts": x,
            "predictions": fitted, "cv_scores": scores, "selected_alpha_indices": np.array(chosen),
            "alphas": alphas, "row_mask": rows, "unit_mask": units,
            "basis": basis, "design_mean": mean, "design_std": std,
            "parameters": asdict(params), "folds": folds}


def glm_geometry_summary(counts, predictions, cv_scores, selected_alpha_indices,
                         subsets, minimum_valid_fraction=0.9):
    """Source GLM PR with explicit, paired unit subsets instead of hidden RNG draws.

    The source samples raw and fitted subsets independently; supplied subsets are
    therefore pairs [raw_indices, fitted_indices], not silently coupled indices.
    """
    x = matrix(counts, "counts")
    x = counts_array(x, len(x))
    fitted = matrix(predictions, "predictions")
    scores = np.asarray(cv_scores, dtype=float)
    selected = np.asarray(selected_alpha_indices)
    if (fitted < 0).any() or x.shape != fitted.shape or scores.ndim != 3 or min(scores.shape) == 0 or scores.shape[0] != x.shape[1] or np.isinf(scores).any():
        raise ContractError("GLM result dimensions or scores invalid")
    if selected.shape != (x.shape[1],) or not np.issubdtype(selected.dtype, np.integer) or (selected < 0).any() or (selected >= scores.shape[1]).any():
        raise ContractError("selected alpha indices invalid")
    if not 0 < minimum_valid_fraction <= 1:
        raise ContractError("minimum_valid_fraction outside (0,1]")
    selected_scores = scores[np.arange(x.shape[1]), selected]
    valid = np.isfinite(selected_scores).sum(axis=1)
    means = np.divide(np.nansum(selected_scores, axis=1), valid,
                      out=np.full(x.shape[1], np.nan), where=valid > 0)
    suppress = (means <= 0) | (valid < minimum_valid_fraction * scores.shape[2]) | ~np.isfinite(means)
    fitted = fitted.copy()
    fitted[:, suppress] = 0
    prs = []
    for pair in subsets:
        if len(pair) != 2:
            raise ContractError("each subset must provide raw and fitted unit indices")
        checked = []
        for indices in pair:
            ind = np.asarray(indices)
            if ind.ndim != 1 or not len(ind) or not np.issubdtype(ind.dtype, np.integer) or len(np.unique(ind)) != len(ind) or (ind < 0).any() or (ind >= x.shape[1]).any():
                raise ContractError("unit subsets require distinct in-range integer indices")
            checked.append(ind)
        if len(checked[0]) != len(checked[1]):
            raise ContractError("raw/fitted subset sizes must match")
        prs.append([participation_ratio(x[:, checked[0]]), participation_ratio(fitted[:, checked[1]])])
    if not prs:
        raise ContractError("at least one explicitly recorded subset required")
    return {"raw_pr": float(np.mean(prs, axis=0)[0]), "fitted_pr": float(np.mean(prs, axis=0)[1]),
            "mean_selected_cv_d2": float(means.mean()), "suppressed_units": np.flatnonzero(suppress),
            "selected_valid_folds": valid, "subset_pr": np.asarray(prs)}


def fit_train_only(z, counts, train_indices, test_indices, params, alpha):
    """Prospective fixed-alpha within-session adaptation with strict train-only transforms.

    It is not animal transfer: different animals need not have aligned neurons.
    Alpha and partitions must be externally frozen without assessment access.
    """
    z = latents(z)
    x = counts_array(counts, len(z))
    if not np.isfinite(alpha) or alpha <= 0:
        raise ContractError("alpha must be positive")
    indices = []
    for value in (train_indices, test_indices):
        a = np.asarray(value)
        if a.ndim != 1 or not len(a) or not np.issubdtype(a.dtype, np.integer) or len(np.unique(a)) != len(a) or (a < 0).any() or (a >= len(z)).any():
            raise ContractError("partitions require distinct in-range integer row indices")
        indices.append(a)
    train, test = indices
    if np.intersect1d(train, test).size:
        raise ContractError("train/test overlap")
    train, test = (a[z[a, 2] > 4] for a in (train, test))
    if len(train) < 2 or not len(test):
        raise ContractError("locomotion filter empties train or test")
    position_mean = z[train, :2].mean(axis=0)
    centered = z.copy()
    centered[:, :2] -= position_mean
    basis = fit_basis(centered[train], params)
    a, b, mean, std = standardize_train(design_matrix(centered[train], basis, params),
                                       design_matrix(centered[test], basis, params))
    unit_mask = x[train].mean(axis=0) / DT > 0.1
    if not unit_mask.any():
        raise ContractError("no training-eligible units")
    y_train, y_test = x[train][:, unit_mask], x[test][:, unit_mask]
    predictions = np.column_stack([_fit_poisson(a, y_train[:, u], alpha).predict(b)
                                   for u in range(y_train.shape[1])])
    deviance = [poisson_deviance(y_test[:, u], predictions[:, u]) for u in range(y_test.shape[1])]
    return {"recipe": "prospective_train_only_fixed_alpha", "predictions": predictions,
            "poisson_deviance_per_unit": np.asarray(deviance), "train_indices": train,
            "test_indices": test, "unit_mask": unit_mask, "basis": basis,
            "position_mean": position_mean, "design_mean": mean, "design_std": std,
            "alpha": float(alpha)}


def paired_region_contrast(rows, expected_sessions, metric):
    """CA1 minus PFC, equal session weight within animal then equal animal weight.

    Caller must declare all session identities before seeing results. This new
    reporting estimand is prospective; it is not a paper figure significance test.
    """
    expected = [(str(a), str(s)) for a, s in expected_sessions]
    if len(set(expected)) != len(expected) or not expected:
        raise ContractError("duplicate or empty expected session manifest")
    found = {}
    for row in rows:
        key = (str(row["animal"]), str(row["session"]), row["region"])
        value = row[metric]
        if key in found or key[2] not in REGIONS or not np.isfinite(value):
            raise ContractError("duplicate, nonfinite, or invalid region observation")
        found[key] = float(value)
    required = {(a, s, r) for a, s in expected for r in REGIONS}
    if set(found) != required:
        raise ContractError("missing or unexpected animal/session/region observations")
    by_animal = {}
    for animal, session in expected:
        by_animal.setdefault(animal, []).append(found[animal, session, "CA1"] - found[animal, session, "PFC"])
    means = {a: float(np.mean(v)) for a, v in by_animal.items()}
    return {"estimand": "prospective_equal_animal_CA1_minus_PFC", "metric": metric,
            "animal_contrasts": means, "mean_contrast": float(np.mean(list(means.values()))),
            "animals": len(means), "sessions": len(expected)}


def validate_panel_manifest(manifest):
    """Require every author animal and first eight processed-session positions.

    Session labels and epoch identity are explicit caller declarations; this does
    not turn an unverified NPZ into authenticated NWB data.
    """
    if manifest.get("source_revision") != SOURCE_REVISION or manifest.get("dandiset_version") != "0.240511.0307":
        raise ContractError("panel source or dataset version mismatch")
    rows = manifest.get("sessions", [])
    found, epoch_ids, paths = set(), set(), set()
    for row in rows:
        key = (row.get("animal"), row.get("session_index"))
        if isinstance(key[1], bool) or not isinstance(key[1], int) or key in found:
            raise ContractError("duplicate or invalid animal/session index")
        found.add(key)
        if not isinstance(row.get("epoch_id"), str) or not row["epoch_id"]:
            raise ContractError("explicit epoch identity required")
        epoch_key = (key[0], row["epoch_id"])
        if epoch_key in epoch_ids:
            raise ContractError("same animal epoch declared twice")
        epoch_ids.add(epoch_key)
        for k in ("path", "sha256"):
            if not isinstance(row.get(k), str) or not row[k]:
                raise ContractError(f"session {k} is required")
        if row["path"] in paths:
            raise ContractError("session input path reused")
        paths.add(row["path"])
        if len(row["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in row["sha256"]):
            raise ContractError("session sha256 must be lowercase hex")
        if isinstance(row.get("bytes"), bool) or not isinstance(row.get("bytes"), int) or row["bytes"] <= 0:
            raise ContractError("positive session byte length required")
    if found != {(a, s) for a in ANIMALS for s in range(8)}:
        raise ContractError("source GLM panel requires all 8 animals x first 8 sessions")
    return sorted(rows, key=lambda r: (ANIMALS.index(r["animal"]), r["session_index"]))


def run_source_glm_panel(manifest, manifest_directory, seed):
    """Run the figure's frozen GLM basis on all declared 8x8 sessions and both regions.

    This executes 128 session/region fits with ten alphas and ten CV folds per
    eligible unit. It never reduces the population or subset count on failure.
    It does not repeat the source's preceding 108-configuration selection search.
    """
    rows = validate_panel_manifest(manifest)
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ContractError("an explicit nonnegative RNG seed is required")
    params = BasisParameters(10, 3, 100, 40)
    rng = np.random.default_rng(seed)
    output = []
    for animal in ANIMALS:
        sessions = []
        for row in (r for r in rows if r["animal"] == animal):
            path = Path(manifest_directory) / row["path"]
            raw = path.read_bytes()
            if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
                raise ContractError(f"session content pin mismatch: {animal}/{row['session_index']}")
            with np.load(io.BytesIO(raw), allow_pickle=False) as data:
                z = latents(data["latents"])
                x = counts_array(data["counts"], len(z))
                locations = np.asarray(data["locations"])
                if locations.shape != (x.shape[1],) or locations.dtype.kind not in "US" or not np.all(np.char.str_len(locations) > 0):
                    raise ContractError("panel requires aligned nonempty location strings")
                sessions.append((row, z.copy(), x.copy(), locations.copy()))
        centered = []
        for _, z, _, _ in sessions:
            eligible = z[z[:, 2] > 4].copy()
            if len(eligible) < 2:
                raise ContractError("session has insufficient locomotion rows")
            eligible[:, :2] -= eligible[:, :2].mean(axis=0)
            centered.append(eligible)
        pooled = np.concatenate(centered)
        for region in REGIONS:
            for row, z, x, locations in sessions:
                result = source_glm_fit(z, x[:, locations == region], pooled, params)
                n = result["counts"].shape[1]
                if n < 19:
                    raise ContractError("fewer than 19 eligible units; source subset cannot be weakened")
                subsets = [[rng.choice(n, 19, replace=False), rng.choice(n, 19, replace=False)] for _ in range(500)]
                summary = glm_geometry_summary(result["counts"], result["predictions"], result["cv_scores"],
                                               result["selected_alpha_indices"], subsets)
                output.append({"animal": animal, "session": row["epoch_id"], "session_index": row["session_index"],
                               "region": region, "raw_pr": summary["raw_pr"], "fitted_pr": summary["fitted_pr"],
                               "mean_selected_cv_d2": summary["mean_selected_cv_d2"],
                               "eligible_units": n, "suppressed_units": summary["suppressed_units"],
                               "alphas": result["alphas"][result["selected_alpha_indices"]],
                               "input_sha256": row["sha256"], "unit_subsets": subsets})
    expected = [(r["animal"], r["epoch_id"]) for r in rows]
    return {"recipe": "author_GLM_frozen_figure_basis",
            "parameters": asdict(params), "alpha_grid": np.logspace(-0.5, 2, 10),
            "folds": 10, "neuron_subset": 19, "subset_repetitions": 500,
            "rng": "numpy.default_rng", "seed": seed,
            "original_basis_search_reexecuted": False, "rows": output,
            "prospective_descriptive_contrasts": [paired_region_contrast(output, expected, m)
                                                  for m in ("raw_pr", "fitted_pr", "mean_selected_cv_d2")]}


def json_safe(value):
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return {"value": None, "status": "positive_infinity" if value == float("inf") else "undefined"}
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["geometry", "source-glm", "source-panel", "train-only", "contrast"])
    parser.add_argument("input", type=Path, help="NPZ arrays, or JSON for contrast")
    parser.add_argument("output", type=Path)
    parser.add_argument("--parameters", type=Path, help="JSON basis parameters; required for GLMs")
    parser.add_argument("--training-samples", type=int, default=300)
    parser.add_argument("--alpha", type=float)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args(argv)
    if args.mode == "source-panel":
        if args.seed is None:
            parser.error("source-panel requires an explicit --seed")
        result = run_source_glm_panel(json.loads(args.input.read_text()), args.input.parent, args.seed)
    elif args.mode == "contrast":
        payload = json.loads(args.input.read_text())
        result = paired_region_contrast(payload["rows"], payload["expected_sessions"], payload["metric"])
    else:
        with np.load(args.input, allow_pickle=False) as data:
            if args.mode == "geometry":
                result = covariance_geometry(data["responses"], data["latents"], args.training_samples)
            else:
                if args.parameters is None:
                    parser.error("GLM modes require --parameters")
                params = BasisParameters(**json.loads(args.parameters.read_text()))
                if args.mode == "source-glm":
                    result = source_glm_fit(data["latents"], data["counts"], data["pooled_latents"], params)
                else:
                    if args.alpha is None:
                        parser.error("train-only requires externally frozen --alpha")
                    result = fit_train_only(data["latents"], data["counts"], data["train_indices"], data["test_indices"], params, args.alpha)
    envelope = {"task_id": TASK_ID, "source_revision": SOURCE_REVISION,
                "construction_status": "implemented_engineering_components_not_scientifically_qualified",
                "research_qualified": False, "full_contract_complete": False,
                "holds": HOLDS, "result": result}
    args.output.write_text(json.dumps(json_safe(envelope), indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
