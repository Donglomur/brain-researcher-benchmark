"""Source-only NeuralFlow row adapter, grouped split planner and choice scorer.

Raw row names follow the official Figshare description. No Parquet reader, model,
network intake, historical split recovery or scientific qualification is supplied.
The same pure row path is exercised by invented development fixtures.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import hmac
import json
import math


class ContractError(ValueError):
    pass


def _integer(value, name):
    if type(value) is not int or value < 0:
        raise ContractError(f"{name} must be a nonnegative integer")
    return value


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{name} must be numeric")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ContractError(f"{name} is not finite") from exc
    if not math.isfinite(result):
        raise ContractError(f"{name} is not finite")
    return result


def _side(value):
    if value not in ("Left", "Right"):
        raise ContractError("side must be Left or Right")
    return value


def _session(row):
    subject = _integer(row["subject_id"], "subject_id")
    if subject not in (0, 1):
        raise ContractError("subject_id must be 0 (T) or 1 (O)")
    return subject, _integer(row["session_id"], "session_id")


def _trial(row):
    return (*_session(row), _integer(row["trial_id"], "trial_id"))


def _unit_ids(values):
    if not isinstance(values, list) or not values:
        raise ContractError("uids must be a nonempty list")
    result = tuple(_integer(x, "unit_id") for x in values)
    if len(set(result)) != len(result):
        raise ContractError("duplicate unit ID")
    return result


def validate_roster(roster):
    """Validate a supplied evaluator roster, never derive it from predictions.

    Real membership has not been resolved. Thirty attempts and fifteen per animal
    are immutable scope constraints; IDs must later come from authentic intake.
    """
    if not isinstance(roster, list) or len(roster) != 30:
        raise ContractError("full roster must contain all 30 population attempts")
    populations, compositions, counts = {}, set(), Counter()
    for row in roster:
        pid = row["population_id"]
        if not isinstance(pid, str) or not pid or len(pid) > 100 or pid in populations:
            raise ContractError("invalid or duplicate population_id")
        session = _session(row)
        units = _unit_ids(row["uids"])
        if len(units) < 3:
            raise ContractError("historical population requires at least 3 selected units")
        # Membership defines population identity, but original order defines the
        # reversible package row map and must survive in the stored roster.
        composition = (*session, frozenset(units))
        if composition in compositions:
            raise ContractError("same population composition counted more than once")
        compositions.add(composition)
        counts[session[0]] += 1
        populations[pid] = {"population_id": pid, "subject_id": session[0],
                            "session_id": session[1], "uids": units}
    if counts != {0: 15, 1: 15}:
        raise ContractError("full roster requires 15 attempted populations per monkey")
    return populations


def adapt_rows(units_rows, trial_rows, spike_rows, roster, *, source_clock, endpoint_policy):
    """Map official rows into population/trial windows without fitting or dropping.

    Caller must supply a source-clock declaration independently established from
    authentic source. Unknown clocks and endpoint conventions are refused.
    Missing rows differ from explicit empty spike arrays. Trial eligibility is a
    caller-prepared complete historical selection, never guessed here.
    """
    if source_clock not in ("absolute_seconds", "stimulus_relative_seconds"):
        raise ContractError("source spike clock is unresolved")
    if endpoint_policy not in ("closed", "left_closed_right_open"):
        raise ContractError("source window endpoint convention is unresolved")
    populations = validate_roster(roster)
    source_populations = set()
    for row in units_rows:
        if row["analysis_type"] == "population":
            composition = (*_session(row), _unit_ids(row["uids"]))
            if composition in source_populations:
                raise ContractError("duplicate population metadata row")
            source_populations.add(composition)
        elif row["analysis_type"] != "single_neuron":
            raise ContractError("unknown analysis_type")
    expected = {(*_session(p), p["uids"]) for p in populations.values()}
    if source_populations != expected:
        raise ContractError("source population rows differ from complete frozen roster")
    trials = {}
    for row in trial_rows:
        key = _trial(row)
        if key in trials:
            raise ContractError("duplicate trial key")
        onset = _number(row["stim_onset"], "stim_onset")
        reaction = _number(row["reaction_times"], "reaction_times")
        if reaction <= 0.120:
            raise ContractError("nonpositive analysis duration requires an explicit exclusion ledger")
        if row["stim_difficulty"] not in ("easy", "hard"):
            raise ContractError("unresolved trial selection: difficulty outside easy/hard")
        recorded = _unit_ids(row["recorded_units"])
        trials[key] = {"subject_id": key[0], "session_id": key[1], "trial_id": key[2],
                       "stim_onset": onset, "reaction_times": reaction,
                       "chosen_side": _side(row["chosen_side"]),
                       "correct_response": _side(row["correct_response"]),
                       "stim_difficulty": row["stim_difficulty"], "recorded_units": recorded}
    spikes = {}
    for row in spike_rows:
        trial_key = _trial(row)
        unit = _integer(row["unit_id"], "unit_id")
        key = (*trial_key, unit)
        if key in spikes:
            raise ContractError("duplicate spike row")
        if trial_key not in trials or unit not in trials[trial_key]["recorded_units"]:
            raise ContractError("orphan spike row or unit absent from trial recorded_units")
        values = row["spike_times"]
        if not isinstance(values, list):
            raise ContractError("spike_times must be an array, including explicit [] for silence")
        values = [_number(x, "spike_time") for x in values]
        if any(a > b for a, b in zip(values, values[1:])):
            raise ContractError("spike times must already be nondecreasing")
        spikes[key] = values
    by_session = defaultdict(list)
    for key in trials:
        by_session[key[:2]].append(key)
    if set(by_session) != {_session(p) for p in populations.values()}:
        raise ContractError("trial sessions differ from complete declared population sessions")
    episodes, excluded_spikes = [], 0
    for pid, population in sorted(populations.items()):
        session = _session(population)
        conditions = set()
        for trial_index, key in enumerate(sorted(by_session[session])):
            trial = trials[key]
            offset = trial["stim_onset"] if source_clock == "absolute_seconds" else 0.0
            # Compare in the original timestamp clock before subtracting. In
            # particular 10.12 - 10.0 can round below the declared 0.12 boundary.
            window_start = _number(offset + 0.120, "source window start")
            window_end = _number(offset + trial["reaction_times"], "source window end")
            duration = _number(window_end - window_start, "resolved window duration")
            if duration <= 0:
                raise ContractError("source-clock precision cannot resolve a positive window")
            if not set(population["uids"]).issubset(trial["recorded_units"]):
                raise ContractError("population unit missing on a selected trial; no silent exclusion")
            unit_spikes = []
            for dense_index, unit in enumerate(population["uids"]):
                spike_key = (*key, unit)
                if spike_key not in spikes:
                    raise ContractError("missing spike row cannot be interpreted as zero spikes")
                original_times = spikes[spike_key]
                included = [time - window_start for time in original_times if window_start <= time and
                            (time < window_end or (endpoint_policy == "closed" and time == window_end))]
                excluded_spikes += len(original_times) - len(included)
                unit_spikes.append({"unit_id": unit, "dense_neuron_index": dense_index,
                                    "spike_seconds_from_window_start": included})
            # Stimulus direction defines the condition, never the animal's choice.
            condition = f"{trial['correct_response']}_{trial['stim_difficulty']}"
            conditions.add(condition)
            episodes.append({"population_id": pid, "subject_id": key[0], "session_id": key[1],
                             "trial_id": key[2], "stimulus_condition": condition,
                             "trial_index_within_population": trial_index,
                             "chosen_side": trial["chosen_side"],
                             "duration_seconds": duration,
                             "spikes": unit_spikes})
        if conditions != {f"{side}_{difficulty}" for side in ("Left", "Right") for difficulty in ("easy", "hard")}:
            raise ContractError("every population requires all four stimulus conditions")
    return {"schema": "neuralflow-row-projection-v1", "source_clock": source_clock,
            "window_start_seconds_after_stimulus": 0.120, "window_end": "movement",
            "endpoint_policy": endpoint_policy, "populations": 30,
            "population_unit_maps": [{"population_id": p["population_id"],
                                      "subject_id": p["subject_id"], "session_id": p["session_id"],
                                      "dense_index_to_source_unit_id": list(p["uids"])}
                                     for _, p in sorted(populations.items())],
            "episodes": episodes, "window_excluded_spike_occurrences": excluded_spikes,
            "scientific_qualification": False}


def choice_feature_view(projection):
    """Make a whitelisted choice-input view from an evaluator-owned projection.

    The full projection contains target choices. Never send it directly to the
    contestant. This helper omits choices and all undeclared metadata recursively;
    train labels must be supplied separately for declared training cases only.
    It is not a held-neuron/LONO view, which requires masking scored neuron spikes.
    """
    if projection.get("schema") != "neuralflow-row-projection-v1":
        raise ContractError("expected evaluator row projection")
    episodes = []
    for episode in projection["episodes"]:
        clean = {key: episode[key] for key in ("population_id", "subject_id", "session_id",
                 "trial_id", "stimulus_condition", "duration_seconds", "trial_index_within_population")}
        clean["spikes"] = [{"unit_id": unit["unit_id"],
                            "dense_neuron_index": unit["dense_neuron_index"],
                            "spike_seconds_from_window_start": list(unit["spike_seconds_from_window_start"])}
                           for unit in episode["spikes"]]
        episodes.append(clean)
    return {"schema": "neuralflow-choice-feature-view-v1", "episodes": episodes,
            "contains_choice_targets": False, "lono_safe": False}


def protected_split_plan(trial_rows, *, evaluator_secret):
    """Deterministic grouped 60/20/20-ish split; a prospective proposal only.

    Group by (subject,session,trial) across all populations, stratify within session
    by stimulus direction/difficulty and choice. Each stratum needs >=3 trials.
    The private secret and assignments are evaluator artifacts, not submissions.
    """
    if not isinstance(evaluator_secret, bytes) or len(evaluator_secret) < 32:
        raise ContractError("evaluator secret must contain at least 32 private bytes")
    strata, seen = defaultdict(list), set()
    for row in trial_rows:
        key = _trial(row)
        if key in seen:
            raise ContractError("duplicate trial in source split table")
        seen.add(key)
        difficulty = row["stim_difficulty"]
        if difficulty not in ("easy", "hard"):
            raise ContractError("split requires declared easy/hard eligibility")
        stratum = (*key[:2], _side(row["correct_response"]), difficulty, _side(row["chosen_side"]))
        strata[stratum].append(key)
    if not strata:
        raise ContractError("empty split input")
    assignments = []
    for stratum, keys in sorted(strata.items()):
        if len(keys) < 3:
            raise ContractError("insufficient stratum for train/validation/test; do not drop it")
        def rank(key):
            payload = json.dumps(key, separators=(",", ":")).encode()
            return hmac.new(evaluator_secret, payload, hashlib.sha256).digest(), key
        keys = sorted(keys, key=rank)
        n_test = max(1, len(keys) // 5)
        n_validation = max(1, (len(keys) - n_test) // 4)
        for index, key in enumerate(keys):
            partition = "test" if index < n_test else "validation" if index < n_test + n_validation else "train"
            assignments.append({"subject_id": key[0], "session_id": key[1], "trial_id": key[2],
                                "partition": partition})
    return sorted(assignments, key=lambda x: _trial(x))


def _case(row):
    pid = row["population_id"]
    if not isinstance(pid, str):
        raise ContractError("population_id must be text")
    return pid, *_trial(row)


def score_choices(target_rows, prediction_rows, roster):
    """Score exact complete evaluator cases, with failed fits retained via fallback.

    A fit failure must still emit a finite training-only fallback prediction.
    This component never declares full scientific reproduction or qualification.
    """
    populations = validate_roster(roster)
    targets = {}
    for row in target_rows:
        key = _case(row)
        if key in targets or key[0] not in populations:
            raise ContractError("duplicate or unknown evaluator case")
        if key[1:3] != _session(populations[key[0]]):
            raise ContractError("case population/session mismatch")
        targets[key] = int(_side(row["chosen_side"]) == "Right")
    if {key[0] for key in targets} != set(populations):
        raise ContractError("evaluator targets must include all 30 populations")
    predictions = {}
    statuses = defaultdict(set)
    for row in prediction_rows:
        key = _case(row)
        if key in predictions:
            raise ContractError("duplicate prediction case")
        p = _number(row["probability_right"], "probability_right")
        if not 0.0 <= p <= 1.0:
            raise ContractError("probability outside [0,1]")
        status = row["fit_status"]
        if status not in ("fit", "fallback_after_fit_failure"):
            raise ContractError("explicit fitted or failure-fallback status is required")
        statuses[key[0]].add(status)
        predictions[key] = p
    if set(predictions) != set(targets):
        raise ContractError("predictions must exactly cover evaluator cases; no omissions or extras")
    per_population = []
    for pid, population in sorted(populations.items()):
        pairs = [(targets[k], predictions[k]) for k in targets if k[0] == pid]
        recalls = []
        for label in (0, 1):
            subset = [(y, p) for y, p in pairs if y == label]
            if not subset:
                raise ContractError("balanced accuracy requires both choices in every population")
            recalls.append(sum(int(p >= 0.5) == y for y, p in subset) / len(subset))
        eps = 1e-15
        clipped = [(y, min(1.0 - eps, max(eps, p))) for y, p in pairs]
        log_loss = -math.fsum(y * math.log(p) + (1 - y) * math.log1p(-p) for y, p in clipped) / len(pairs)
        per_population.append({"population_id": pid, "subject_id": population["subject_id"],
                               "session_id": population["session_id"], "n_cases": len(pairs),
                               "balanced_accuracy": math.fsum(recalls) / 2,
                               "log_loss": log_loss,
                               "brier_score": math.fsum((p - y) ** 2 for y, p in pairs) / len(pairs),
                               "contains_fit_failure": "fallback_after_fit_failure" in statuses[pid]})
    per_animal = []
    for subject in (0, 1):
        selected = [r for r in per_population if r["subject_id"] == subject]
        per_animal.append({"subject_id": subject, "n_populations": 15,
                           **{metric: math.fsum(r[metric] for r in selected) / 15
                              for metric in ("balanced_accuracy", "log_loss", "brier_score")}})
    return {"schema": "neuralflow-choice-component-score-v1", "n_populations": 30,
            "n_cases": len(targets), "per_population": per_population, "per_animal": per_animal,
            "animal_balanced_accuracy": math.fsum(r["balanced_accuracy"] for r in per_animal) / 2,
            "populations_with_fit_failure": sum(r["contains_fit_failure"] for r in per_population),
            "complete_contract_evaluation": False,
            "unimplemented_required_endpoints": ["matched_reference", "shared_geometry", "spike_likelihood", "held_neuron_prediction", "grouped_uncertainty"]}
