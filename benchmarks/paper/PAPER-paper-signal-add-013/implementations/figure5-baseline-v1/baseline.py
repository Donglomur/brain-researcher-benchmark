"""Figure 5 baseline row construction and fitted OLS, not a paper-win evaluator.

Original implementation derived from pinned author F_Fig4_5.ipynb cells 4, 9–10,
13–17. Arrays are operator inputs; this module does not acquire or authenticate
NIfTI files, execute author notebooks, or substitute a new validation split.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import warnings

import numpy as np


SUBJECTS = tuple(f"sub-p{number:03d}" for number in (
    19, 20, 21, 23, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38,
    39, 40, 43, 44, 46, 47, 48, 49, 50, 51, 52, 54, 55,
    58, 59, 60, 61, 63, 64, 65, 66, 67, 68))
PARAMETERS = ("cmro2", "oef", "cbf", "cbv")
PREDICTORS = PARAMETERS[1:]
STRATA = ("concordant", "discordant")
BLOCKS = ("calc.negative", "calc.positive", "mem.negative", "mem.positive")
SOURCE_SHA256 = "b0badd997e88c9a602b7405a1f06cb53ffb78bae76f7556e1f68b4812a619e84"


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def prepare_baseline(subject_ids, voxel_indices, maps, masks):
    """Build source baseline rows from aligned extracted CTRL arrays.

    `maps` has four arrays (40, V); CBF is the unscaled source map. `masks`
    has eight boolean arrays (V,) keyed '<stratum>.<task>.<BOLD sign>'.
    Voxel indices are C-order positions on the common MNI152 2-mm grid.
    The exact source block concatenation intentionally retains a physical voxel
    once per selected task; it must not be replaced by a spatial union.
    """
    _require(tuple(subject_ids) == SUBJECTS, "exact ordered primary40 required")
    indices = np.asarray(voxel_indices)
    _require(indices.ndim == 1 and indices.dtype.kind in "iu" and indices.size > 0,
             "voxel_indices must be a nonempty integer vector")
    _require(np.all(indices >= 0) and np.all(indices < 91 * 109 * 91)
             and np.all(indices[1:] > indices[:-1]), "voxel indices must be sorted and unique")
    _require(set(maps) == set(PARAMETERS), "all four source baseline maps required")
    expected_masks = {f"{stratum}.{block}" for stratum in STRATA for block in BLOCKS}
    _require(set(masks) == expected_masks, "all eight source stratum/task/sign masks required")
    checked_masks = {}
    for key, values in masks.items():
        array = np.asarray(values)
        _require(array.dtype.kind == "b" and array.shape == indices.shape,
                 f"{key}: expected aligned boolean mask")
        checked_masks[key] = array
    # These four masks classify one task's BOLD/metabolic sign combination.
    # A voxel can validly recur under the other task with another response type.
    for task in ("calc", "mem"):
        membership = sum(checked_masks[f"{s}.{task}.{sign}"].astype(int)
                         for s in STRATA for sign in ("negative", "positive"))
        _require(np.all(membership <= 1), f"overlapping sign classifications within {task}")
    median = {}
    support = {}
    for name in PARAMETERS:
        values = np.asarray(maps[name], dtype=float)
        _require(values.shape == (40, len(indices)), f"{name}: expected primary40 × voxels")
        _require(not np.isinf(values).any(), f"{name}: infinite source values")
        # Author cell 9 divides each subject's CBF by .75 before nanmedian.
        if name == "cbf":
            values = values / .75
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN columns retained below
            median[name] = np.nanmedian(values, axis=0)
        support[name] = np.sum(~np.isnan(values), axis=0)
    panels = {}
    for stratum in STRATA:
        positions = np.concatenate([np.flatnonzero(checked_masks[f"{stratum}.{block}"])
                                    for block in BLOCKS])
        _require(len(positions) > 0, f"empty {stratum} support")
        row_ids = [(block, int(indices[position])) for block in BLOCKS
                   for position in np.flatnonzero(checked_masks[f"{stratum}.{block}"])]
        panels[stratum] = {
            "row_ids": row_ids,
            "columns": {name: median[name][positions] for name in PARAMETERS},
            "subject_support": {name: support[name][positions] for name in PARAMETERS},
        }
    return panels


def fit_baseline_panel(panel):
    """Match the source statsmodels formula branch with pre-drop centering.

    Source cell 10 first invalidates whole rows with CMRO2 > 350 or OEF > 1.
    Predictor means then use each column's available values before joint complete
    case exclusion, exactly as cells 13/16 then 14/17. This matters when columns
    have different missingness. Row identities and exclusion counts are retained.
    No voxel-level inferential p-value or biological-independent N is reported.
    """
    columns = panel["columns"]
    _require(set(columns) == set(PARAMETERS), "baseline column set changed")
    row_ids = panel["row_ids"]
    arrays = [np.asarray(columns[name], dtype=float) for name in PARAMETERS]
    _require(all(array.ndim == 1 and array.shape == (len(row_ids),) for array in arrays),
             "each baseline column must be one-dimensional with one value per row identity")
    raw = np.column_stack(arrays)
    _require(not np.isinf(raw).any(), "infinite regression value")
    _require(len(set((str(block), int(index)) for block, index in row_ids)) == len(row_ids),
             "duplicate mask/voxel row identity")
    excluded_threshold = (raw[:, 0] > 350) | (raw[:, 1] > 1)
    raw[excluded_threshold] = np.nan
    _require(np.all(np.any(~np.isnan(raw[:, 1:]), axis=0)), "all-missing predictor")
    centers = np.nanmean(raw[:, 1:], axis=0)
    retained = np.all(~np.isnan(raw), axis=1)
    x = raw[retained, 1:] - centers
    y = raw[retained, 0]
    _require(len(y) > 4, "baseline fit requires positive residual degrees of freedom")
    design = np.column_stack([np.ones(len(y)), x])
    coefficients, _, rank, _ = np.linalg.lstsq(design, y, rcond=None)
    _require(rank == 4, "rank-deficient baseline model cannot match source F(3, df)")
    prediction = design @ coefficients
    sse = float(np.sum((y - prediction) ** 2))
    sst = float(np.sum((y - y.mean()) ** 2))
    _require(sst > 0, "constant CMRO2 target has undefined source R-squared")
    r2 = 1 - sse / sst
    n = len(y)
    kept_ids = [row_ids[i] for i in np.flatnonzero(retained)]
    digest = hashlib.sha256(json.dumps(kept_ids, separators=(",", ":")).encode()).hexdigest()
    counts = Counter(index for _, index in kept_ids)
    return {
        "n_source_rows": len(row_ids), "n_fit_rows": n,
        "n_excluded_source_threshold": int(excluded_threshold.sum()),
        "n_excluded_other_joint_missing": int((~retained & ~excluded_threshold).sum()),
        "n_excluded_total": int((~retained).sum()),
        "unique_physical_voxels": len(counts),
        "repeated_task_voxel_rows": n - len(counts),
        "retained_row_ids_sha256": digest,
        "predictor_means_before_joint_exclusion": dict(zip(PREDICTORS, centers.tolist())),
        "coefficients": dict(zip(("intercept",) + PREDICTORS, coefficients.tolist())),
        "r_squared_centered_with_intercept": r2,
        "adjusted_r_squared": 1 - (1 - r2) * (n - 1) / (n - 4),
        "df_model": 3, "df_residual": n - 4,
        "f_statistic": ((sst - sse) / 3) / (sse / (n - 4)) if sse > 0 else None,
        "f_statistic_nonfinite": None if sse > 0 else "positive_infinity_perfect_fit",
        "sse": sse, "centered_sst": sst,
        "interpretation": "source-selected voxel-row fitted statistic, not independent physiological accuracy",
    }


def evaluate_baseline(subject_ids, voxel_indices, maps, masks):
    """Two baseline cells, separately reported; task-change is not substituted."""
    panels = prepare_baseline(subject_ids, voxel_indices, maps, masks)
    return {
        "component": "figure5_baseline_fitted_regression",
        "source_notebook_sha256": SOURCE_SHA256,
        "baseline_cells": {stratum: fit_baseline_panel(panels[stratum]) for stratum in STRATA},
        "published_baseline_r_squared": {"concordant": .91, "discordant": .91},
        "published_baseline_df_residual": {"concordant": 21809, "discordant": 14544},
        "full_figure5_reproduction_established": False,
        "paper_improvement_established": False,
    }
