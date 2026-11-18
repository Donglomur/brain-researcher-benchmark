"""Named source-code coding-direction projections, without scientific grading.

Independent expression of the pinned Get_coding_direction calculation. This
consumes the existing safe in-memory imaging boundary; it never opens data files,
executes author code, selects an experiment cohort or estimates improvement.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import warnings

import numpy as np

INITIAL_SHA256 = "89a506fa5d9ad64644141e1da302810dcd7a7c3d94d365b5f4c35d40ecd0d331"
REVISION = "ba64ac697f5d9914926baac79399e80707a5f3a6"
PERCENTILE = 5
PREVIOUS_POSITIONS = 10


def _load_initial(path=None):
    path = Path(path) if path is not None else (
        Path(__file__).resolve().parents[1] / "initial-evaluator-v1" / "evaluator.py"
    )
    if hashlib.sha256(path.read_bytes()).hexdigest() != INITIAL_SHA256:
        raise ValueError("initial evaluator dependency identity changed")
    spec = importlib.util.spec_from_file_location("rep007_initial_coding_dependency", path)
    if spec is None or spec.loader is None:
        raise ValueError("initial evaluator dependency cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INITIAL = _load_initial()


def _trial_projection(interpolated, selected, reference_trials):
    """Average selected-cell normalized traces, retaining every source trial.

    Averaging before appending the previous trial's tail avoids allocating a
    second cell-by-trial-by-position tensor. It is the same linear operation;
    authentic native numerical parity is still unverified.
    """
    chosen = interpolated[selected]
    with warnings.catch_warnings(), np.errstate(invalid="ignore", divide="ignore"):
        warnings.simplefilter("ignore", RuntimeWarning)
        center = chosen[:, :, 42:52].reshape(len(selected), -1).mean(axis=1)
        scales = [chosen[:, indices, :40].reshape(len(selected), -1).std(axis=1)
                  for indices in reference_trials]
        denominator = scales[0] + scales[1]
        normalized = 2 * (chosen - center[:, None, None]) / denominator[:, None, None]
        current = normalized.mean(axis=0)
    previous = np.full((interpolated.shape[1], PREVIOUS_POSITIONS), np.nan)
    previous[1:] = current[:-1, -PREVIOUS_POSITIONS:]
    values = np.concatenate((previous, current), axis=1)
    return values, {
        "zero_scale_cells": int(np.count_nonzero(denominator == 0)),
        "nonfinite_scale_cells": int(np.count_nonzero(~np.isfinite(denominator))),
        "nonfinite_center_cells": int(np.count_nonzero(~np.isfinite(center))),
        "nonfinite_normalized_values": int(np.count_nonzero(~np.isfinite(normalized))),
        "gray_centers": INITIAL.finite_json(center),
        "reference_population_sd": [INITIAL.finite_json(v) for v in scales],
    }


def coding_direction(bundle, reference_ids=(2, 0)):
    """Return both percentile-defined populations for all seven source stimuli.

    The caller must bind the pair to a source experiment independently. Selection
    uses even zero-based frame-trial IDs. Reference stimuli are evaluated on odd
    zero-based trials; other stimuli retain ALL trials. Normalization intentionally
    uses all reference trials and all-session gray bins, as in this source variant.
    """
    if (not isinstance(reference_ids, (tuple, list)) or len(reference_ids) != 2
            or any(type(v) is not int or not 0 <= v <= 6 for v in reference_ids)
            or reference_ids[0] == reference_ids[1]):
        raise ValueError("two distinct source stimulus IDs in 0..6 are required")
    x = INITIAL.validate_bundle(bundle)
    for key in ("frame_trial", "frame_gray", "interp_spks"):
        if key not in x:
            raise ValueError("coding direction requires " + key)
    if not np.isin(x["stimulus_ids"], np.arange(7)).all():
        raise ValueError("unsupported source stimulus identity outside 0..6")
    names = [INITIAL.stimulus_name(x, value) for value in reference_ids]
    ncell, nframe = x["spks"].shape
    ntrial = len(x["trial_wall"])
    frame_trial = INITIAL.numeric(x["frame_trial"], "frame_trial", 1, integer=True)
    gray = INITIAL.numeric(x["frame_gray"], "frame_gray", 1)
    if len(frame_trial) != nframe or len(gray) != nframe:
        raise ValueError("coding-direction frame alignment mismatch")
    if np.any(frame_trial < 0) or np.any(frame_trial >= ntrial):
        raise ValueError("frame trial outside source trial range")
    if not np.isin(gray, [0, 1]).all():
        raise ValueError("frame_gray must be boolean")
    moving = x["frame_move"] > 0
    corridor = moving & x["frame_corridor"].astype(bool)
    if np.any(x["frame_wall"][corridor] != x["trial_wall"][frame_trial[corridor]]):
        raise ValueError("moving corridor frame/trial stimulus identity mismatch")
    selection = frame_trial % 2 == 0
    raw_groups = [selection & corridor & (x["frame_wall"] == name) for name in names]
    raw_gray = selection & moving & gray.astype(bool)
    if not raw_gray.any():
        raise ValueError("no moving gray frames in the selection trials")
    if any(not mask.any() for mask in raw_groups):
        raise ValueError("both reference stimuli need moving selection frames")
    dp = INITIAL.source_dprime(*(x["spks"][:, mask] for mask in raw_groups))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        gray_mean = x["spks"][:, raw_gray].mean(axis=1)
        responsive = np.logical_or.reduce([
            x["spks"][:, mask].mean(axis=1) > gray_mean for mask in raw_groups
        ])
    reference_trials = [np.flatnonzero(x["trial_wall"] == name) for name in names]
    trial_roles = {}
    for code in range(7):
        present = code in x["stimulus_ids"]
        name = str(INITIAL.stimulus_name(x, code)) if present else None
        indices = np.flatnonzero(x["trial_wall"] == name) if present else np.array([], dtype=int)
        if code in reference_ids:
            indices = indices[indices % 2 == 1]
        trial_roles[str(code)] = {
            "stimulus_name": name, "present_in_identity_map": bool(present),
            "trial_indices": indices.tolist(), "trial_count": len(indices),
            "trial_role": "odd_zero_based_reference_trials" if code in reference_ids else "all_trials",
        }
    areas = {}
    for area, area_ids in INITIAL.AREAS.items():
        members = np.isin(x["area_ids"], area_ids)
        eligible = members & responsive
        values = dp[eligible]
        if not len(values):
            selection_status = "no_eligible_cells"
            thresholds = None
        elif not np.isfinite(values).all():
            selection_status = "undefined_selection_nonfinite_dprime"
            thresholds = None
        else:
            selection_status = "defined"
            thresholds = np.percentile(values, [100 - PERCENTILE, PERCENTILE])
        populations = {}
        for index, polarity in enumerate(("first_reference", "second_reference")):
            if thresholds is None:
                selected = np.array([], dtype=int)
            else:
                cutoff = dp >= thresholds[0] if index == 0 else dp <= thresholds[1]
                selected = np.flatnonzero(eligible & cutoff)
            if len(selected):
                projected, normalization = _trial_projection(x["interp_spks"], selected, reference_trials)
                population_status = ("undefined_normalization" if normalization["zero_scale_cells"]
                                     or normalization["nonfinite_scale_cells"]
                                     or normalization["nonfinite_center_cells"]
                                     or normalization["nonfinite_normalized_values"] else "source_variant_evaluated")
            else:
                projected = np.full((ntrial, 60 + PREVIOUS_POSITIONS), np.nan)
                normalization = None
                population_status = selection_status
            stimuli = {}
            for code, role in trial_roles.items():
                rows = role["trial_indices"]
                output = projected[rows]
                stimuli[code] = {
                    **role, "values": INITIAL.finite_json(output),
                    "value_diagnostics": INITIAL.value_diagnostics(output),
                    "previous_trial_unavailable": [trial == 0 for trial in rows],
                    "status": ("not_present" if not role["present_in_identity_map"] else
                               "no_evaluation_trials" if not rows else population_status),
                }
            populations[polarity] = {
                "selected_cell_indices": selected.tolist(), "selected_cell_count": len(selected),
                "status": population_status, "normalization_diagnostics": normalization,
                "stimuli": stimuli,
            }
        areas[area] = {
            "source_cell_count": int(members.sum()), "eligible_cell_count": int(eligible.sum()),
            "eligible_dprime_diagnostics": INITIAL.value_diagnostics(values),
            "selection_status": selection_status,
            "upper_lower_percentile_thresholds": INITIAL.finite_json(thresholds),
            "populations": populations,
        }
    return {
        "schema": "rep007-coding-direction-source-variant/v1",
        "task_id": INITIAL.TASK, "source_revision": REVISION,
        "variant": "pinned_code_percentile5_mean_population_projection",
        "reference_ids": list(reference_ids), "percentile": PERCENTILE,
        "source_cell_count": ncell, "source_frame_count": nframe, "source_trial_count": ntrial,
        "selection_frame_counts": [int(mask.sum()) for mask in raw_groups],
        "selection_gray_frame_count": int(raw_gray.sum()),
        "normalization_reference_trial_indices": [v.tolist() for v in reference_trials],
        "normalization": {"gray_position_slice": [42, 52], "reference_position_slice": [0, 40],
                          "ddof": 0, "scope": "all_session_gray_and_all_reference_trials",
                          "prospective_train_only": False},
        "positions": {"previous_trial_tail": PREVIOUS_POSITIONS, "current_trial": 60},
        "areas": areas, "scientific_qualification": "unknown", "full_contract_complete": False,
        "original_cohort_verified": False, "native_source_parity_verified": False,
        "scientific_improvement_assessed": False,
    }
