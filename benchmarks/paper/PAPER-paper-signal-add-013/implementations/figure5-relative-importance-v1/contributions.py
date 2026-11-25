"""Baseline Figure 5 contribution arithmetic, not physiological improvement.

Reuses the accepted baseline row constructor. The historical source requests
Pingouin relimp and relimp_perc. This independent all-subset OLS implementation
keeps absolute explained-variance shares separate from percentages of total R2.
It does not execute the author's notebook or establish historical package parity.
"""
from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path

import numpy as np

BASELINE_SHA256 = "756b79d3db68ae8041f71fead2559d7227b80fe927a4c6ef7a8cad1eb3e5a75a"
NOTEBOOK_SHA256 = "b0badd997e88c9a602b7405a1f06cb53ffb78bae76f7556e1f68b4812a619e84"
PREDICTORS = ("oef", "cbf", "cbv")
ROUND_OFF = 1e-10  # numerical self-consistency, never a reproduction tolerance


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _baseline(path=None):
    path = (Path(path) if path is not None else
            Path(__file__).resolve().parents[1] / "figure5-baseline-v1" / "baseline.py")
    body = path.read_bytes()
    _require(hashlib.sha256(body).hexdigest() == BASELINE_SHA256,
             "accepted baseline implementation identity changed")
    spec = importlib.util.spec_from_file_location("bold_baseline_contribution_dependency", path)
    module = importlib.util.module_from_spec(spec)
    # Execute the authenticated snapshot, not a second read of its pathname.
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def decompose_baseline_r_squared(subsets):
    """Average increments over all six predictor orders, on one fixed support.

    Input maps a canonical predictor tuple to its intercept-model centered R2.
    All eight subsets, including the intercept-only empty tuple, are required.
    The caller must establish common observations; this arithmetic alone cannot.
    """
    expected = {tuple(combination) for size in range(4)
                for combination in itertools.combinations(PREDICTORS, size)}
    _require(isinstance(subsets, dict) and set(subsets) == expected,
             "all eight canonical baseline predictor subsets required")
    for value in subsets.values():
        _require(type(value) in (int, float) and math.isfinite(value), "finite numeric R2 required")
        _require(-ROUND_OFF <= value <= 1 + ROUND_OFF, "invalid fitted intercept-model R2")
    _require(subsets[()] == 0, "intercept-only centered R2 must be zero")
    accumulated = {name: [] for name in PREDICTORS}
    orders = []
    for order in itertools.permutations(PREDICTORS):
        selected = set()
        previous = 0.0
        increments = []
        for name in order:
            selected.add(name)
            key = tuple(item for item in PREDICTORS if item in selected)
            value = float(subsets[key])
            delta = value - previous
            _require(delta >= -ROUND_OFF,
                     "nested subset R2 decreased: inconsistent support or unstable fit")
            accumulated[name].append(delta)
            increments.append({"predictor": name, "r_squared_increment": delta})
            previous = value
        orders.append({"order": list(order), "increments": increments})
    shares = {name: math.fsum(values) / 6 for name, values in accumulated.items()}
    full = float(subsets[PREDICTORS])
    _require(math.isclose(math.fsum(shares.values()), full, abs_tol=ROUND_OFF, rel_tol=0),
             "contribution additivity failed")
    share_sum = math.fsum(shares.values())
    percentages = ({name: 100 * value / share_sum for name, value in shares.items()}
                   if share_sum > 0 else {name: None for name in PREDICTORS})
    return {"relimp": shares, "relimp_perc": percentages,
            "percent_denominator": "sum_of_relative_contributions",
            "percent_denominator_value": share_sum,
            "percentage_undefined_reason": None if share_sum > 0 else "nonpositive_full_r_squared",
            "full_model_centered_r_squared": full, "order_count": 6,
            "ordered_increments": orders,
            "roundoff_tolerance": ROUND_OFF,
            "raw_contributions_clipped": False,
            "printed_percentages_repaired_or_normalized": False}


def _panel_contributions(panel, baseline):
    # In the notebook a new DataFrame begins with target.dropna(), then aligned
    # predictor series are assigned. x.dropna() must preserve y.dropna() indices.
    # The accepted statsmodels companion instead allows joint complete cases.
    # Do not silently substitute that companion's behavior for the source's
    # separate-dropna contribution branch when predictor-only missingness exists.
    names = ("cmro2",) + PREDICTORS
    raw = np.column_stack([np.asarray(panel["columns"][name], dtype=float) for name in names])
    threshold = (raw[:, 0] > 350) | (raw[:, 1] > 1)
    raw[threshold] = np.nan
    target_rows = ~np.isnan(raw[:, 0])
    predictor_rows = np.all(~np.isnan(raw[:, 1:]), axis=1)
    _require(not np.any(target_rows & ~predictor_rows),
             "source separate-dropna x/y row sets differ; contribution branch is unqualified")
    full_fit = baseline.fit_baseline_panel(panel)
    centers = np.array([full_fit["predictor_means_before_joint_exclusion"][name]
                        for name in PREDICTORS])
    x = raw[target_rows, 1:] - centers
    y = raw[target_rows, 0]
    row_ids = [list(panel["row_ids"][i]) for i in np.flatnonzero(target_rows)]
    sst = float(np.sum((y - y.mean()) ** 2))
    _require(sst > 0 and math.isfinite(sst), "nonconstant finite target variance required")
    subsets = {(): 0.0}
    fits = [{"predictors": [], "r_squared": 0.0, "sse": sst,
             "coefficients": {"intercept": float(y.mean())}, "rank": 1}]
    for size in range(1, 4):
        for columns in itertools.combinations(range(3), size):
            features = tuple(PREDICTORS[i] for i in columns)
            design = np.column_stack([np.ones(len(y)), x[:, columns]])
            coef, _, rank, _ = np.linalg.lstsq(design, y, rcond=None)
            _require(rank == size + 1, "rank-deficient source subset")
            residuals = y - design @ coef
            sse = float(np.dot(residuals, residuals))
            r2 = 1 - sse / sst
            _require(math.isfinite(r2), "nonfinite subset fit")
            subsets[features] = r2
            fits.append({"predictors": list(features), "r_squared": r2,
                         "sse": sse, "rank": int(rank),
                         "coefficients": dict(zip(("intercept",) + features, coef.tolist()))})
    _require(math.isclose(subsets[PREDICTORS], full_fit["r_squared_centered_with_intercept"],
                         abs_tol=ROUND_OFF, rel_tol=0), "accepted full-fit reconciliation failed")
    return {"fit_support": {"n_source_rows": len(panel["row_ids"]), "n_fit_rows": len(y),
                            "fitted_row_ids": row_ids,
                            "fitted_row_ids_sha256": hashlib.sha256(
                                json.dumps(row_ids, separators=(",", ":")).encode()).hexdigest(),
                            "physical_voxels_may_repeat_across_source_tasks": True,
                            "source_separate_dropna_indices_match": True},
            "predictor_means_before_joint_exclusion": dict(zip(PREDICTORS, centers.tolist())),
            "centered_predictor_rows": x.tolist(), "target_rows": y.tolist(),
            "subset_fits": fits, "contributions": decompose_baseline_r_squared(subsets),
            "reference_full_fit": full_fit}


def evaluate_baseline_contributions(subject_ids, voxel_indices, maps, masks, *, baseline_path=None):
    """Both baseline strata and every subset; no task-change or aggregate reward.

    Input arrays must already satisfy the accepted source preparation contract.
    This function does not authenticate maps, masks or original fitted membership.
    """
    baseline = _baseline(baseline_path)
    panels = baseline.prepare_baseline(subject_ids, voxel_indices, maps, masks)
    return {"schema_version": "bold-baseline-relative-importance/v1",
            "source_notebook_sha256": NOTEBOOK_SHA256,
            "baseline_code_sha256": BASELINE_SHA256,
            "baseline_cells": {name: _panel_contributions(panels[name], baseline)
                               for name in baseline.STRATA},
            "historical_pingouin_version_parity_established": False,
            "full_figure5_reproduction_established": False,
            "paper_improvement_established": False,
            "scientific_interpretation": "Fitted decomposition of a derived CMRO2 target; not independent metabolic accuracy"}
