"""Complete-support private hierarchical encoding grading; no I/O or fitting."""
import math

import numpy as np

from reference.encoder import ReferenceError


def _require(condition, message):
    if not condition:
        raise ReferenceError(message)


def _vector(value, n, name):
    _require(isinstance(value, np.ndarray) and value.dtype.kind in "fiu" and
             value.shape == (n,) and np.isfinite(value).all(),
             f"{name} must be a finite complete ordered cell vector")
    return np.asarray(value, dtype=np.float64)


def _mean(values):
    values = list(values)
    _require(values, "empty hierarchy denominator")
    result = math.fsum(values) / len(values)
    _require(math.isfinite(result), "unscorable hierarchy arithmetic")
    return result


def _hierarchy(acquisitions, metric, diagnostic=False):
    sessions, animals = {}, {}
    unavailable = []
    acquisition_values = {}
    for acquisition, row in acquisitions.items():
        values = row[metric]
        if any(value is None for value in values.values()):
            unavailable.append(acquisition)
            acquisition_values[acquisition] = None
        else:
            acquisition_values[acquisition] = _mean(values.values())
        sessions.setdefault(row["session"], []).append(acquisition)
        animals.setdefault(row["animal"], set()).add(row["session"])
    session_values = {}
    for session, keys in sessions.items():
        session_values[session] = (None if any(acquisition_values[key] is None for key in keys)
                                   else _mean(acquisition_values[key] for key in keys))
    animal_values = {}
    for animal, keys in animals.items():
        animal_values[animal] = (None if any(session_values[key] is None for key in keys)
                                 else _mean(session_values[key] for key in sorted(keys)))
    available = bool(animal_values) and all(value is not None for value in animal_values.values())
    if not diagnostic:
        _require(available, "complete primary hierarchy unavailable")
    return {"available": available, "value": _mean(animal_values.values()) if available else None,
            "acquisitions": acquisition_values, "sessions": session_values,
            "animals": animal_values, "unavailable_acquisitions": unavailable}


def _summarize(query_rows, truths, predictions, baselines):
    trials, acquisitions = {}, {}
    for row in query_rows:
        token, acquisition, trial = row["token"], row["acquisition"], row["physical_trial"]
        key = (acquisition, trial)
        target = _vector(truths[token], len(row["cell_tokens"]), "truth")
        predicted = _vector(predictions[token], len(row["cell_tokens"]), "prediction")
        squared = (predicted - target) ** 2
        _require(np.isfinite(squared).all(), "unscorable squared-error arithmetic")
        if key not in trials:
            trials[key] = {"errors": [], "denominator": [], "row": row}
        trials[key]["errors"].append(squared)
        if baselines is not None:
            baseline = _vector(baselines[token], len(row["cell_tokens"]), "training mean baseline")
            denominator = (target - baseline) ** 2
            _require(np.isfinite(denominator).all(), "unscorable R2 denominator arithmetic")
            trials[key]["denominator"].append(denominator)
    for (acquisition, trial), values in trials.items():
        row = values["row"]
        if acquisition not in acquisitions:
            acquisitions[acquisition] = {"session": row["session"], "animal": row["animal"],
                "cell_tokens": row["cell_tokens"], "trials": {}, "cell_mse": {}, "cell_r2": {}}
        _require(len(values["errors"]) == row["time_count"], "incomplete trial time support")
        # Native grid is common per acquisition: each complete trial has equal time weight.
        per_cell_mse = np.mean(np.stack(values["errors"]), axis=0)
        acquisitions[acquisition]["trials"][trial] = {
            "mse": per_cell_mse.tolist(),
            "squared_error_sum": np.sum(np.stack(values["errors"]), axis=0).tolist(),
            "training_baseline_squared_error_sum": (np.sum(np.stack(values["denominator"]), axis=0).tolist()
                                                     if baselines is not None else None),
            "time_count": row["time_count"], "fold": row["fold"]}
    for acquisition, row in acquisitions.items():
        trial_values = list(row["trials"].values())
        for cell_index, cell in enumerate(row["cell_tokens"]):
            row["cell_mse"][cell] = _mean(trial["mse"][cell_index] for trial in trial_values)
            if baselines is not None:
                sse = math.fsum(trial["squared_error_sum"][cell_index] for trial in trial_values)
                denominator = math.fsum(trial["training_baseline_squared_error_sum"][cell_index]
                                        for trial in trial_values)
                value = None if denominator == 0 else 1.0 - sse / denominator
                _require(value is None or math.isfinite(value), "unscorable signed R2 arithmetic")
                row["cell_r2"][cell] = value
    mse = _hierarchy(acquisitions, "cell_mse")
    r2 = _hierarchy(acquisitions, "cell_r2", diagnostic=True) if baselines is not None else None
    return {"mse": mse["value"], "rmse": math.sqrt(mse["value"]),
            "mse_hierarchy": mse, "r2_diagnostic": r2, "acquisition_details": acquisitions,
            "counts": {"queries": len(query_rows), "trials": len(trials),
                       "cells_within_acquisitions": sum(len(a["cell_tokens"]) for a in acquisitions.values()),
                       "acquisitions": len(acquisitions), "sessions": len(mse["sessions"]),
                       "animals": len(mse["animals"])}}


def grade(expected_support, truths, predictions, training_means=None):
    """Grade exactly the sealed complete vector-query support, separately GrC/CF.

    expected_support is a nonempty list of private query-coordinate records.
    Owner admission authenticates its completeness and source dispositions.
    Keys: token, modality, acquisition, session, animal, physical_trial, fold,
    time_index, time_count, cell_tokens. Optional stratum contains reinforcer,
    planned_delay, delivered_outcome. No neural data is present in support.
    """
    _require(type(expected_support) is list and expected_support, "complete sealed support required")
    required = {"token", "modality", "acquisition", "session", "animal", "physical_trial",
                "fold", "time_index", "time_count", "cell_tokens"}
    tokens, coordinates, acquisition_meta, session_animals, trial_acquisitions = set(), set(), {}, {}, {}
    trial_times, trial_meta, baseline_by_fold = {}, {}, {}
    global_acquisition_identity, global_trial_identity = {}, {}
    with_strata = "stratum" in expected_support[0]
    for row in expected_support:
        _require(type(row) is dict and set(row) == required | ({"stratum"} if with_strata else set()),
                 "malformed/inconsistent private support record")
        for name in ("token", "acquisition", "session", "animal", "physical_trial"):
            _require(type(row[name]) is str and row[name], f"missing opaque {name} key")
        _require(row["modality"] in ("GrC", "CF"), "unknown modality")
        _require(row["token"] not in tokens, "duplicate query token")
        tokens.add(row["token"])
        _require(type(row["fold"]) is int and 0 <= row["fold"] < 5 and
                 type(row["time_count"]) is int and row["time_count"] > 0 and
                 type(row["time_index"]) is int and 0 <= row["time_index"] < row["time_count"],
                 "invalid fold/native time coordinate")
        cells = row["cell_tokens"]
        _require(type(cells) is list and cells and all(type(c) is str and c for c in cells)
                 and len(set(cells)) == len(cells), "complete unique ordered cell tokens required")
        if with_strata:
            _require(type(row["stratum"]) is dict and set(row["stratum"]) ==
                     {"reinforcer", "planned_delay", "delivered_outcome"} and
                     all(type(v) is str and v for v in row["stratum"].values()), "invalid source stratum")
        modality, acquisition, trial = row["modality"], row["acquisition"], row["physical_trial"]
        akey, tkey = (modality, acquisition), (modality, trial)
        meta = (row["session"], row["animal"], tuple(cells), row["time_count"])
        _require(akey not in acquisition_meta or acquisition_meta[akey] == meta,
                 "acquisition cell/time/session/animal identity changed")
        acquisition_meta[akey] = meta
        global_identity = (row["session"], row["animal"])
        _require(acquisition not in global_acquisition_identity or
                 global_acquisition_identity[acquisition] == global_identity,
                 "paired modalities disagree on acquisition/session/animal identity")
        global_acquisition_identity[acquisition] = global_identity
        physical_identity = (acquisition, row["session"], row["animal"], row["fold"])
        _require(trial not in global_trial_identity or global_trial_identity[trial] == physical_identity,
                 "paired physical trial crosses acquisition, identity or fold")
        global_trial_identity[trial] = physical_identity
        _require(row["session"] not in session_animals or session_animals[row["session"]] == row["animal"],
                 "session mapped to multiple animals")
        session_animals[row["session"]] = row["animal"]
        _require(tkey not in trial_acquisitions or trial_acquisitions[tkey] == acquisition,
                 "same physical trial duplicated through acquisition/source aliases")
        trial_acquisitions[tkey] = acquisition
        coordinate = (modality, acquisition, trial, row["time_index"])
        _require(coordinate not in coordinates, "duplicate physical query coordinate/alias")
        coordinates.add(coordinate)
        trial_times.setdefault(tkey, set()).add(row["time_index"])
        tmeta = (row["fold"], row["time_count"], tuple(sorted(row.get("stratum", {}).items())))
        _require(tkey not in trial_meta or trial_meta[tkey] == tmeta,
                 "physical trial crosses folds or changes source stratum/grid")
        trial_meta[tkey] = tmeta
    for key, times in trial_times.items():
        _require(times == set(range(trial_meta[key][1])), "missing required query time bin")
    for name, mapping in (("truths", truths), ("predictions", predictions)):
        _require(type(mapping) is dict and set(mapping) == tokens, f"{name} support must match exactly")
    if training_means is not None:
        _require(type(training_means) is dict and set(training_means) == tokens,
                 "fold-training-mean baseline support must match exactly")
        for row in expected_support:
            value = _vector(training_means[row["token"]], len(row["cell_tokens"]), "training mean baseline")
            key = (row["modality"], row["acquisition"], row["fold"])
            _require(key not in baseline_by_fold or np.array_equal(baseline_by_fold[key], value),
                     "overall training cell mean varies within the same outer fold")
            baseline_by_fold[key] = value
    results = {}
    for modality in ("GrC", "CF"):
        rows = [row for row in expected_support if row["modality"] == modality]
        if not rows:
            results[modality] = {"available": False, "reason": "empty complete modality denominator"}
            continue
        results[modality] = {"available": True, **_summarize(rows, truths, predictions, training_means)}
        if with_strata:
            strata = sorted({tuple(sorted(row["stratum"].items())) for row in rows})
            results[modality]["strata"] = [{"stratum": dict(stratum),
                **_summarize([row for row in rows if tuple(sorted(row["stratum"].items())) == stratum],
                             truths, predictions, training_means)} for stratum in strata]
    return {"schema": "filio_i_hierarchical_grade_v1", "modalities": results,
            "complete_two_modality_primary_available": all(r["available"] for r in results.values()),
            "combined_modality_scalar": None, "query_count": len(tokens),
            "interpretation": "Released processed-target errors; no biological or execution qualification."}
