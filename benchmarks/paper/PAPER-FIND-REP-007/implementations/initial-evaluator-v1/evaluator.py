"""Source-derived Zhong et al. 2025 selectivity/reward/lick endpoint evaluator.

No downloads, model fitting, numeric grading target, or scientific qualification.
The safe NPZ boundary retains every neuron and explicit source stimulus identities.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import warnings

import numpy as np

TASK = "PAPER-FIND-REP-007"
REVISION = "ba64ac697f5d9914926baac79399e80707a5f3a6"
AREAS = {"V1": (8,), "mHV": (0, 1, 2, 9), "lHV": (5, 6), "aHV": (3, 4)}
THRESHOLDS = np.arange(1, 11, dtype=float) / 10
SELECTIVITY_RECIPES = {
    "unsup_train1_before_learning": ((2, 0),),
    "unsup_train1_after_learning": ((2, 0),),
    "sup_train1_before_learning": ((2, 0),),
    "sup_train1_after_learning": ((2, 0),),
    "train1_before_grating": ((2, 0),),
    "train1_after_grating": ((2, 0),),
    "naive_test1": ((3, 0), (2, 3)),
    "unsup_train2_before_learning": ((3, 0),),
    "sup_train2_before_learning": ((3, 0),),
    "unsup_train2_after_learning": ((3, 0), (2, 3)),
    "sup_train2_after_learning": ((3, 0), (2, 3)),
    "test1_after_grating": ((2, 3),),
}
REWARD_EXPERIMENTS = frozenset(list(SELECTIVITY_RECIPES)[:4])
GATES = [
    "Authentic all-cell Figshare v2 population and longitudinal panel not executed or independently verified.",
    "Exact figure numeric targets, tolerances and protected reference remain unfrozen.",
    "Sequence similarity uses the pinned top5-percent code variant; conflicting paper cell-threshold/trial-split policy requires adjudication.",
    "Coding-direction indices and spatial density maps are not implemented by this component.",
    "Animal stage/condition assignments require experiment-info and exposure-history reconciliation.",
    "Trial-count, recording-yield, stimulus and area matching controls require scientific qualification before learning attribution.",
    "Native source environment, interpolation and complete all-session replay require empirical validation.",
    "Public paper/data exposure, component rights, equal access and isolated candidate replay remain unresolved.",
]


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def numeric(value, name, ndim=None, integer=False, allow_nan=False):
    arr = np.asarray(value)
    if arr.dtype.kind not in "biuf":
        raise ValueError(f"{name}: numeric array required")
    if ndim is not None and arr.ndim != ndim:
        raise ValueError(f"{name}: expected {ndim} dimensions")
    if np.isinf(arr).any() or (not allow_nan and np.isnan(arr).any()):
        raise ValueError(f"{name}: invalid nonfinite input")
    if integer and (not np.isfinite(arr).all() or not np.equal(arr, np.floor(arr)).all()):
        raise ValueError(f"{name}: integral values required")
    return arr.astype(np.int64 if integer else float, copy=False)


def text_vector(value, name):
    arr = np.asarray(value)
    if arr.ndim != 1 or arr.dtype.kind not in "US" or not np.all(arr != ""):
        raise ValueError(f"{name}: nonempty string vector required")
    return arr.astype(str)


def source_dprime(first, second):
    """Author equation: 2*(nanmean(first)-nanmean(second))/(nanstd1+nanstd2).

    Axis 1 samples; population standard deviations (ddof=0). NaN and +/-inf
    outputs retain the author's comparison semantics; report diagnostics expose
    them rather than substituting a pooled-variance formula or silently deleting cells.
    """
    first = numeric(first, "first", 2, allow_nan=True)
    second = numeric(second, "second", 2, allow_nan=True)
    if first.shape[0] != second.shape[0] or not min(first.shape[1], second.shape[1]):
        raise ValueError("dprime requires nonempty groups with the same cell count")
    with warnings.catch_warnings(), np.errstate(invalid="ignore", divide="ignore"):
        warnings.simplefilter("ignore", RuntimeWarning)
        return 2 * (np.nanmean(first, axis=1) - np.nanmean(second, axis=1)) / (
            np.nanstd(first, axis=1) + np.nanstd(second, axis=1)
        )


def value_diagnostics(values):
    values = np.asarray(values)
    return {"finite": int(np.isfinite(values).sum()), "nan": int(np.isnan(values).sum()),
            "positive_infinity": int(np.isposinf(values).sum()),
            "negative_infinity": int(np.isneginf(values).sum())}


def area_fractions(dp, area_ids):
    """All area cells form each denominator, including NaN-dprime cells."""
    area_ids = numeric(area_ids, "area_ids", 1, integer=True)
    dp = np.asarray(dp, dtype=float)
    if dp.ndim != 1 or dp.shape != area_ids.shape:
        raise ValueError("dprime and area_ids must share the cell axis")
    result = {}
    for area, ids in AREAS.items():
        chosen = dp[np.isin(area_ids, ids)]
        n = len(chosen)
        result[area] = {
            "cell_count": n, "dprime_diagnostics": value_diagnostics(chosen),
            "fractions": [{"threshold": float(t),
                           "either": float(np.count_nonzero(abs(chosen) >= t) / n) if n else None,
                           "positive": float(np.count_nonzero(chosen >= t) / n) if n else None,
                           "negative": float(np.count_nonzero(chosen <= -t) / n) if n else None}
                          for t in THRESHOLDS],
        }
    return result


def validate_bundle(bundle):
    """Validate a safe, full-cell normalized imaging-session boundary."""
    x = {k: np.asarray(v) for k, v in bundle.items()}
    spks = numeric(x["spks"], "spks", 2, allow_nan=True)
    ncell, nframe = spks.shape
    if ncell < 1 or nframe < 1:
        raise ValueError("empty neural recording")
    x["spks"] = spks
    x["area_ids"] = numeric(x["area_ids"], "area_ids", 1, integer=True)
    if len(x["area_ids"]) != ncell:
        raise ValueError("all-cell area axis mismatch")
    for key in ("frame_wall", "trial_wall", "stimulus_names"):
        x[key] = text_vector(x[key], key)
    x["stimulus_ids"] = numeric(x["stimulus_ids"], "stimulus_ids", 1, integer=True)
    if len(x["stimulus_names"]) != len(x["stimulus_ids"]) or len(set(x["stimulus_ids"])) != len(x["stimulus_ids"]) or len(set(x["stimulus_names"])) != len(x["stimulus_names"]):
        raise ValueError("stimulus identity map must be bijective")
    if not set(x["trial_wall"]).issubset(set(x["stimulus_names"])):
        raise ValueError("unmapped trial stimulus")
    if len(x["trial_wall"]) == 0:
        raise ValueError("empty trial population")
    if len(x["frame_wall"]) != nframe:
        raise ValueError("frame_wall alignment mismatch")
    for key in ("frame_move", "frame_corridor"):
        x[key] = numeric(x[key], key, 1)
        if len(x[key]) != nframe:
            raise ValueError(f"{key}: frame alignment mismatch")
    if not np.isin(x["frame_corridor"], [0, 1]).all():
        raise ValueError("frame_corridor must be boolean")
    used = (x["frame_move"] > 0) & x["frame_corridor"].astype(bool)
    if not set(x["frame_wall"][used]).issubset(set(x["stimulus_names"])):
        raise ValueError("unmapped moving texture frame stimulus")
    if "interp_spks" in x:
        x["interp_spks"] = numeric(x["interp_spks"], "interp_spks", 3, allow_nan=True)
        if x["interp_spks"].shape != (ncell, len(x["trial_wall"]), 60):
            raise ValueError("interp_spks requires all cells x trials x 60 positions")
    if "sound_delay_position" in x:
        x["sound_delay_position"] = numeric(x["sound_delay_position"], "sound_delay_position", 1)
        if len(x["sound_delay_position"]) != len(x["trial_wall"]):
            raise ValueError("sound/trial alignment mismatch")
    return x


def stimulus_name(bundle, code):
    index = np.flatnonzero(bundle["stimulus_ids"] == code)
    if len(index) != 1:
        raise ValueError(f"required source stimulus ID {code} unavailable")
    return bundle["stimulus_names"][index[0]]


def selectivity(bundle, first_id=2, second_id=0):
    first, second = stimulus_name(bundle, first_id), stimulus_name(bundle, second_id)
    valid = (bundle["frame_move"] > 0) & bundle["frame_corridor"].astype(bool)
    masks = [valid & (bundle["frame_wall"] == name) for name in (first, second)]
    dp = source_dprime(*(bundle["spks"][:, mask] for mask in masks))
    return dp, {"stimulus_ids": [first_id, second_id], "stimulus_names": [str(first), str(second)],
                "moving_texture_frame_counts": [int(mask.sum()) for mask in masks],
                "trial_counts": [int((bundle["trial_wall"] == name).sum()) for name in (first, second)],
                "dprime": finite_json(dp), "dprime_diagnostics": value_diagnostics(dp),
                "areas": area_fractions(dp, bundle["area_ids"])}


def reward_prediction(bundle, stimulus_dp):
    """Source positive reward-predictive fraction; late minus early cue trials."""
    if "interp_spks" not in bundle or "sound_delay_position" not in bundle:
        raise ValueError("reward endpoint requires interp_spks and sound_delay_position")
    stimulus_dp = np.asarray(stimulus_dp, dtype=float)
    if stimulus_dp.shape != bundle["area_ids"].shape:
        raise ValueError("stimulus dprime cell alignment mismatch")
    cue = bundle["sound_delay_position"] % 60
    mean_cue = float(cue.mean())  # ALL trials, not only the rewarded stimulus.
    reward_trials = bundle["trial_wall"] == stimulus_name(bundle, 2)
    late = reward_trials & (cue > mean_cue)
    early = reward_trials & (cue <= mean_cue)
    activity = bundle["interp_spks"][:, :, 5:40].mean(axis=2)
    dp = source_dprime(activity[:, late], activity[:, early])
    chosen = (dp >= 0.3) & (stimulus_dp >= 0)
    areas = {}
    for name, ids in AREAS.items():
        mask = np.isin(bundle["area_ids"], ids)
        n = int(mask.sum())
        areas[name] = {"cell_count": n, "selected_count": int((chosen & mask).sum()),
                       "fraction": float((chosen & mask).sum() / n) if n else None}
    return {"late_trial_count": int(late.sum()), "early_trial_count": int(early.sum()),
            "cue_split_all_trials_mean": mean_cue, "threshold": 0.3,
            "dprime": finite_json(dp), "dprime_diagnostics": value_diagnostics(dp), "areas": areas}


def lick_learning(trial_wall, stimulus_names, stimulus_ids, lick_position, lick_trial):
    """First 200 TOTAL trials, any lick in [20,40], source IDs 2 and 0."""
    wall = text_vector(trial_wall, "trial_wall")
    names = text_vector(stimulus_names, "stimulus_names")
    ids = numeric(stimulus_ids, "stimulus_ids", 1, integer=True)
    if len(names) != len(ids) or len(set(ids)) != len(ids) or len(set(names)) != len(names):
        raise ValueError("stimulus identity map must be bijective")
    if not set(wall).issubset(set(names)):
        raise ValueError("unmapped trial stimulus")
    position = numeric(lick_position, "lick_position", 1)
    trials = numeric(lick_trial, "lick_trial", 1, integer=True)
    if len(position) != len(trials) or np.any(trials < 0) or np.any(trials >= len(wall)):
        raise ValueError("lick/trial alignment mismatch")
    response = np.zeros(len(wall), dtype=bool)
    response[trials[(position >= 20) & (position <= 40)]] = True
    result = {"n_trials": len(wall), "trial_limit": 200, "reward_zone_inclusive": [20, 40]}
    for label, code in (("rewarded", 2), ("nonrewarded", 0)):
        name = stimulus_name({"stimulus_ids": ids, "stimulus_names": names}, code)
        mask = (wall == name) & (np.arange(len(wall)) < 200)
        n = int(mask.sum())
        result[label] = {"stimulus_name": str(name), "trial_count": n,
                         "response_count": int(response[mask].sum()),
                         "probability": float(response[mask].mean()) if n else None}
    a, b = result["rewarded"]["probability"], result["nonrewarded"]["probability"]
    result["reward_minus_nonreward"] = a - b if a is not None and b is not None else None
    return result


def finite_json(value):
    if isinstance(value, dict):
        return {str(k): finite_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [finite_json(v) for v in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value


def analyze_session(bundle, experiment, analysis="source_selectivity"):
    if analysis == "source_sequence":
        from sequence import sequence_similarity
        if experiment not in {"naive_test1", "unsup_test1", "sup_test1", "naive_test3", "unsup_test3", "sup_test3"}:
            raise ValueError("experiment not in pinned sequence-processing list")
        bundle = validate_bundle(bundle)
        return {"experiment": experiment, "cell_count": len(bundle["area_ids"]),
                "frame_count": bundle["spks"].shape[1], "trial_count": len(bundle["trial_wall"]),
                "sequence_similarity": sequence_similarity(bundle)}
    if analysis != "source_selectivity":
        raise ValueError("unknown source analysis")
    if experiment not in SELECTIVITY_RECIPES:
        raise ValueError(f"no pinned selectivity recipe for experiment {experiment}")
    bundle = validate_bundle(bundle)
    results = {}
    dp20 = None
    for first, second in SELECTIVITY_RECIPES[experiment]:
        dp, result = selectivity(bundle, first, second)
        results[f"{first}_vs_{second}"] = result
        if (first, second) == (2, 0):
            dp20 = dp
    out = {"experiment": experiment, "cell_count": len(bundle["area_ids"]),
           "frame_count": bundle["spks"].shape[1], "trial_count": len(bundle["trial_wall"]),
           "outside_named_visual_area_count": int((~np.isin(bundle["area_ids"], sum(AREAS.values(), ()))).sum()),
           "selectivity": results}
    if experiment in REWARD_EXPERIMENTS:
        out["reward_prediction"] = reward_prediction(bundle, dp20)
    return out


def summary(values):
    """Prospective equal-animal descriptive summary, not a paper numeric target."""
    good = [float(v) for v in values if v is not None and np.isfinite(v)]
    n = len(good)
    return {"n_animals": n, "missing_animals": len(values) - n,
            "mean": float(np.mean(good)) if n else None,
            "sem": float(np.std(good, ddof=1) / np.sqrt(n)) if n > 1 else None}


def session_metrics(report):
    out = {}
    if "selectivity" in report:
        for contrast, result in report["selectivity"].items():
            for area, ar in result["areas"].items():
                for row in ar["fractions"]:
                    for polarity in ("either", "positive", "negative"):
                        out[f"selectivity/{contrast}/{area}/{row['threshold']:.1f}/{polarity}"] = row[polarity]
    for area, ar in report.get("reward_prediction", {}).get("areas", {}).items():
        out[f"reward_prediction/{area}"] = ar["fraction"]
    for area, ar in report.get("sequence_similarity", {}).get("areas", {}).items():
        for code in range(7):
            out[f"sequence_similarity/{area}/{code}"] = ar.get("targets", {}).get(str(code), {}).get("correlation")
    if "lick_learning" in report:
        for kind in ("rewarded", "nonrewarded"):
            out[f"lick_learning/{kind}"] = report["lick_learning"][kind]["probability"]
        out["lick_learning/reward_minus_nonreward"] = report["lick_learning"]["reward_minus_nonreward"]
    return out


def evaluate_panel(plan_path):
    """Execute every declared session; aggregate repeated sessions within animals.

    The owner supplies immutable experiment-info-derived expected sessions and
    stage identities. Agreement with those declarations does not prove coverage
    of the 297-file release or independence from historically exposed results.
    """
    plan_path = Path(plan_path).resolve()
    plan = json.loads(plan_path.read_text())
    if plan.get("schema_version") != 1 or plan.get("task_id") != TASK:
        raise ValueError("unknown panel schema/task")
    stages = plan["stages"]
    if len(stages) < 2 or len(set(stages)) != len(stages) or not all(isinstance(s, str) and s for s in stages):
        raise ValueError("at least two distinct ordered stages are required")
    sessions = plan["sessions"]
    ids = [s["session_id"] for s in sessions]
    expected = plan["expected_session_ids"]
    if not ids or len(ids) != len(set(ids)) or len(expected) != len(set(expected)) or set(ids) != set(expected):
        raise ValueError("session inventory must exactly match unique expected session IDs")
    if not plan.get("population_evidence"):
        raise ValueError("population_evidence must identify the source of the panel selection")
    groups = defaultdict(list)
    animal_conditions, animal_stages, hashes = {}, defaultdict(set), set()
    reports = []
    for session in sessions:
        animal, condition, stage = session["animal_id"], session["condition"], session["stage"]
        if not all(isinstance(x, str) and x for x in (session["session_id"], animal, condition)) or stage not in stages:
            raise ValueError("invalid animal/condition/stage identity")
        if animal in animal_conditions and animal_conditions[animal] != condition:
            raise ValueError("one animal cannot occur in multiple exposure conditions")
        animal_conditions[animal] = condition
        animal_stages[animal].add(stage)
        file = (plan_path.parent / session["npz_path"]).resolve()
        actual_hash = digest(file)
        if actual_hash != session["sha256"]:
            raise ValueError(f"input hash mismatch for {session['session_id']}")
        if actual_hash in hashes:
            raise ValueError("identical input reused as distinct sessions")
        hashes.add(actual_hash)
        with np.load(file, allow_pickle=False) as npz:
            arrays = {key: npz[key] for key in npz.files}
        kind = session["kind"]
        if kind == "imaging":
            report = analyze_session(arrays, session["experiment"], session.get("analysis", "source_selectivity"))
            for key in ("cell_count", "frame_count", "trial_count"):
                if report[key] != session["expected_counts"][key]:
                    raise ValueError(f"declared full-session {key} mismatch")
        elif kind == "behavior":
            result = lick_learning(*(arrays[k] for k in ("trial_wall", "stimulus_names", "stimulus_ids", "lick_position", "lick_trial")))
            if result["n_trials"] != session["expected_counts"]["trial_count"]:
                raise ValueError("declared full-session trial_count mismatch")
            report = {"lick_learning": result, "trial_count": result["n_trials"]}
        else:
            raise ValueError("kind must be imaging or behavior")
        report.update({key: session[key] for key in ("session_id", "animal_id", "condition", "stage", "kind")})
        report["input_sha256"] = actual_hash
        reports.append(report)
        groups[(animal, condition, stage)].append(session_metrics(report))
    if any(value != set(stages) for value in animal_stages.values()):
        raise ValueError("each animal must retain both declared endpoints and all intermediate longitudinal stages")
    animal_rows = []
    for (animal, condition, stage), metric_rows in sorted(groups.items()):
        metric_keys = set(metric_rows[0])
        if any(set(row) != metric_keys for row in metric_rows):
            raise ValueError("sessions within an animal-stage must have identical endpoint families")
        metrics = {}
        for key in sorted(metric_keys):
            values = [row[key] for row in metric_rows]
            # Preserve missing-session evidence; do not improve a mean by omission.
            metrics[key] = float(np.mean(values)) if all(v is not None for v in values) else None
        animal_rows.append({"animal_id": animal, "condition": condition, "stage": stage,
                            "n_sessions": len(metric_rows), "metrics": metrics})
    by_animal = defaultdict(dict)
    for row in animal_rows:
        by_animal[(row["animal_id"], row["condition"])][row["stage"]] = row["metrics"]
    stage_metrics = defaultdict(lambda: defaultdict(list))
    for row in animal_rows:
        for key, value in row["metrics"].items():
            stage_metrics[(row["condition"], row["stage"])][key].append(value)
    changes, condition_metrics = [], defaultdict(lambda: defaultdict(list))
    for (animal, condition), rows in sorted(by_animal.items()):
        before, after = rows[stages[0]], rows[stages[-1]]
        if set(before) != set(after):
            raise ValueError("longitudinal endpoint/stimulus contrast mismatch")
        delta = {key: after[key] - before[key] if after[key] is not None and before[key] is not None else None for key in before}
        changes.append({"animal_id": animal, "condition": condition, "after_minus_before": delta})
        for key, value in delta.items():
            condition_metrics[condition][key].append(value)
    return {"task_id": TASK, "component": "initial-evaluator-v1", "source_revision": REVISION,
            "panel_sha256": digest(plan_path), "scientific_qualification": "unknown",
            "full_contract_complete": False, "numeric_grading_target_registered": False,
            "scope": "source-derived selectivity, pinned-code sequence similarity, reward-prediction and behavior endpoint component",
            "population_coverage": "complete against declared expected sessions; empirical source completeness unverified",
            "population_evidence": plan["population_evidence"], "stages": stages,
            "aggregation_policy": "prospective: equal-session mean within animal/stage, paired changes, equal-animal descriptive means and SEM",
            "sessions": reports, "animal_stage_means": animal_rows, "animal_changes": changes,
            "change_endpoints": [stages[0], stages[-1]],
            "condition_stage_means": [{"condition": condition, "stage": stage,
                                       "metrics": {key: summary(values) for key, values in rows.items()}}
                                      for (condition, stage), rows in sorted(stage_metrics.items())],
            "condition_changes": {condition: {key: summary(values) for key, values in rows.items()} for condition, rows in condition_metrics.items()},
            "preserved_gates": GATES}


def normalize_author_behavior(behavior):
    """Resolve the source two-stimulus training categories from actual reward labels.

    Source get_cat_id selects the first rewarded wall then the unassigned wall.
    This bridge refuses ambiguous multi-reward or multi-stimulus training input.
    """
    wall = text_vector(behavior["WallName"], "WallName")
    count = numeric(behavior["ntrials"], "ntrials", 0, integer=True)
    reward = numeric(behavior["isRew"], "isRew", 1)
    if count < 1 or int(count) != len(wall) or len(reward) != len(wall) or not np.isin(reward, [0, 1]).all():
        raise ValueError("source behavioral trial/reward alignment mismatch")
    names = np.unique(wall)
    rewarded = np.unique(wall[reward.astype(bool)])
    if len(names) != 2 or len(rewarded) != 1:
        raise ValueError("two-stimulus training category identity is ambiguous")
    ids = np.where(names == rewarded[0], 2, 0)
    # Preserve the author's family-category assignment before selecting its
    # ID2/ID0 training route; a *2 companion must not be relabeled ID0.
    if rewarded[0].endswith("1"):
        ids[names == rewarded[0][:-1] + "2"] = 3
    unassigned = names[ids == 0]
    if not len(unassigned):
        raise ValueError("two-stimulus source category identity is ambiguous")
    if unassigned[0].endswith("1"):
        ids[names == unassigned[0][:-1] + "2"] = 1
    if set(ids) != {0, 2}:
        raise ValueError("two-stimulus source category identity is ambiguous")
    result = {"trial_wall": wall, "stimulus_names": names, "stimulus_ids": ids,
              "lick_position": behavior["LickPos"], "lick_trial": behavior["LickTrind"]}
    lick_learning(*(result[k] for k in ("trial_wall", "stimulus_names", "stimulus_ids", "lick_position", "lick_trial")))
    return {k: np.asarray(v) for k, v in result.items()}


def normalize_author_imaging(neural, retinotopy, behavior):
    """In-memory native-source bridge, including all spks planes and interpolation.

    Inputs are the decoded official dictionaries. File deserialization is an
    explicit owner responsibility because original NPY dictionaries use pickle.
    This function itself never deserializes pickle or selects a neuron subsample.
    """
    planes = neural["spks"]
    if not isinstance(planes, (list, tuple, np.ndarray)) or len(planes) == 0:
        raise ValueError("author neural spks must contain nonempty plane arrays")
    arrays = [numeric(plane, "spks plane", 2, allow_nan=True) for plane in planes]
    if len({plane.shape[1] for plane in arrays}) != 1:
        raise ValueError("source planes disagree in frame count")
    spks = np.concatenate(arrays, axis=0)
    nfr = spks.shape[1]
    declared_trials = numeric(behavior["ntrials"], "ntrials", 0, integer=True)
    if declared_trials < 1 or int(declared_trials) != len(behavior["WallName"]):
        raise ValueError("source trial count mismatch")
    if float(behavior["Corridor_Length"]) != 60:
        raise ValueError("pinned 60-bin position recipe requires a 60-unit corridor")
    frame = {}
    for target, source in (("frame_wall", "ft_WallID"), ("frame_move", "ft_move"), ("frame_corridor", "ft_CorrSpc"), ("frame_trial", "ft_trInd"), ("frame_gray", "ft_GraySpc")):
        arr = np.asarray(behavior[source])
        if arr.ndim != 1 or len(arr) < nfr:
            raise ValueError(f"source {source} shorter than neural recording")
        frame[target] = arr[:nfr]
    cumulative = numeric(behavior["ft_PosCum"], "ft_PosCum", 1)
    if len(cumulative) < nfr:
        raise ValueError("source position shorter than neural recording")
    moving = frame["frame_move"] > 0
    position = cumulative[:nfr][moving] / 60
    if len(position) < 2 or np.any(np.diff(position) <= 0):
        raise ValueError("moving position must be strictly increasing; duplicate/reset source positions require reconciliation")
    ntrial = int(behavior["ntrials"])
    grid = np.arange(0, ntrial, 1 / 60)
    # Piecewise-linear interpolation and endpoint extrapolation, equivalent to
    # the pinned scipy.interp1d recipe for strictly increasing finite x.
    right = np.clip(np.searchsorted(position, grid, side="right"), 1, len(position) - 1)
    left = right - 1
    weight = (grid - position[left]) / (position[right] - position[left])
    values = spks[:, moving]
    interpolated = (values[:, left] + (values[:, right] - values[:, left]) * weight).reshape(len(spks), ntrial, 60)
    bundle = {"spks": spks, "area_ids": retinotopy["iarea"], **frame,
              "trial_wall": behavior["WallName"], "stimulus_names": behavior["UniqWalls"],
              "stimulus_ids": behavior["stim_id"], "sound_delay_position": behavior["SoundDelPos"],
              "interp_spks": interpolated}
    return validate_bundle(bundle)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("panel", type=Path, help="owner-pinned full declared longitudinal panel JSON")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = evaluate_panel(args.panel)
    args.output.write_text(json.dumps(finite_json(result), indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
