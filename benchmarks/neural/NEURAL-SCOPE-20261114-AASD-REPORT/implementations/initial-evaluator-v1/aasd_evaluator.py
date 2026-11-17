"""Independent, evaluator-side AASD construction evaluator (standard library only).

This implements the registered prospective report-decoding endpoint, not native
MAT conversion, an official model, a protected execution service, or qualification.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
from typing import Any

NS = 1_000_000_000
SAMPLE_NS = 7_812_500  # exactly 128 Hz
TASK_ID = "NEURAL-SCOPE-20261114-AASD-REPORT"
EPS = 1e-15
HOLDS = [
    "Native all-18 active/passive census and documented quality exclusions unverified.",
    "Native key/state, trigger/audio alignment, channel identity and processing order unverified.",
    "Stimulus overlap components and three-family fold assignment require independent census.",
    "Source reuse permission and stimulus/HRTF rights chain unresolved; no author code copied.",
    "Protected tensor delivery, train-only model fitting, baselines and leakage challenges not run.",
    "No authentic data execution, independent native reference or scientific qualification.",
]


class ContractError(ValueError):
    """The input violates the frozen construction interface."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def integer(value: Any, name: str, minimum: int | None = None) -> int:
    require(type(value) is int, f"{name} must be an integer (not bool)")
    require(minimum is None or value >= minimum, f"{name} below minimum")
    return value


def identifier(value: Any, name: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), f"{name} must be nonempty text")
    return value


def strict_load(path: str | Path) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def bad_constant(value):
        raise ContractError(f"nonfinite JSON number: {value}")
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs, parse_constant=bad_constant)


def validate_inventory(inventory: dict) -> dict:
    require(isinstance(inventory, dict), "inventory must be an object")
    require(inventory.get("schema") == "aasd-inventory-v1", "unknown inventory schema")
    people = inventory.get("participants")
    require(isinstance(people, list) and len(people) == 18, "exactly 18 participants required")
    for p in people:
        identifier(p, "participant")
    require(len(set(people)) == 18, "participants must be unique")
    families = inventory.get("mixture_folds")
    require(isinstance(families, dict) and families, "frozen mixture_folds required")
    for family, fold in families.items():
        identifier(family, "family")
        integer(fold, "mixture fold")
        require(fold in (0, 1, 2), "folds must be 0, 1, 2")
    require(set(families.values()) == {0, 1, 2}, "all three folds required")
    identifier(inventory.get("mixture_map_provenance"), "mixture_map_provenance")
    trials = inventory.get("trials")
    require(isinstance(trials, list) and len(trials) == 1260, "all 1,260 trial slots required")
    seen = set()
    per_person = defaultdict(list)
    for trial in trials:
        require(isinstance(trial, dict), "trial must be an object")
        tid = identifier(trial.get("trial_id"), "trial_id")
        require(tid not in seen, f"duplicate trial_id {tid}")
        seen.add(tid)
        person = trial.get("participant")
        require(person in people, f"unknown participant in {tid}")
        per_person[person].append(trial)
        identifier(trial.get("block_id"), "block_id")
        integer(trial.get("trial_in_block"), "trial_in_block", 1)
        integer(trial.get("order"), "order", 1)
        require(trial.get("condition") in ("active", "passive"), f"invalid condition in {tid}")
        require(trial.get("status") in ("available", "missing", "excluded"), f"invalid status in {tid}")
        require(trial.get("mixture_family") in families, f"unknown mixture in {tid}")
        duration = integer(trial.get("duration_ns"), "duration_ns", NS)
        if duration != 60 * NS:
            identifier(trial.get("duration_discrepancy_reason"), "duration_discrepancy_reason")
        if trial["status"] != "available":
            identifier(trial.get("reason"), f"missing/excluded reason in {tid}")
            continue
        integer(trial.get("sample_count"), "sample_count", 1)
        integer(trial.get("sample_origin_ns"), "sample_origin_ns")
        spans = trial.get("valid_spans")
        require(isinstance(spans, list), f"valid_spans required in {tid}")
        previous_end = 0
        for span in spans:
            require(isinstance(span, list) and len(span) == 2, "span must be [start,end)")
            a, b = (integer(v, "span index", 0) for v in span)
            require(previous_end <= a < b <= trial["sample_count"], "invalid/overlapping validity span")
            previous_end = b
        require("initial_state" in trial and (trial["initial_state"] is None or type(trial["initial_state"]) is int and trial["initial_state"] in (0, 1)), "initial_state must be null, 0 (left), or 1 (right)")
        identifier(trial.get("state_mapping_provenance"), "state_mapping_provenance")
        events = trial.get("key_events")
        require(isinstance(events, list), "key_events required")
        prior = -1
        for event in events:
            require(isinstance(event, dict), "event must be an object")
            time = integer(event.get("time_ns"), "key time", 0)
            require(prior < time <= duration, "key times must be strictly increasing within trial")
            prior = time
            require(type(event.get("state")) is int and event["state"] in (0, 1), "key state must be 0 or 1")
    for person in people:
        rows = per_person[person]
        require(len(rows) == 70, f"{person}: require 70 trial slots")
        require(sorted(row["order"] for row in rows) == list(range(1, 71)), f"{person}: order must be complete 1..70")
        blocks = defaultdict(list)
        for row in rows:
            blocks[row["block_id"]].append(row)
        require(len(blocks) == 7, f"{person}: require seven blocks")
        conditions = []
        for block in blocks.values():
            require(len(block) == 10 and sorted(t["trial_in_block"] for t in block) == list(range(1, 11)), f"{person}: require ten distinct trial slots per block")
            kinds = {t["condition"] for t in block}
            require(len(kinds) == 1, "mixed conditions in block")
            conditions.append(next(iter(kinds)))
        require(Counter(conditions) == {"active": 6, "passive": 1}, f"{person}: require six active + one passive block")
    return inventory


def state_label(trial: dict, start: int, end: int) -> tuple[int | None, str | None]:
    """Integrate exact reported state duration over [start,end), never across trials."""
    state = trial["initial_state"]
    for event in trial["key_events"]:
        if event["time_ns"] <= start:
            state = event["state"]
        else:
            break
    if state is None:
        return None, "uninitialized_state"
    durations = [0, 0]
    cursor = start
    for event in trial["key_events"]:
        time = event["time_ns"]
        if start < time < end:
            durations[state] += time - cursor
            cursor, state = time, event["state"]
    durations[state] += end - cursor
    if durations[0] == durations[1]:
        return None, "majority_tie"
    return int(durations[1] > durations[0]), None


def context_span(trial: dict, start: int) -> tuple[list[int] | None, str | None]:
    left, right = start - NS // 2, start + 3 * NS // 2
    if left < 0 or right > trial["duration_ns"]:
        return None, "trial_edge"
    offset_left = left - trial["sample_origin_ns"]
    offset_right = right - trial["sample_origin_ns"]
    if offset_left % SAMPLE_NS or offset_right % SAMPLE_NS:
        return None, "unaligned_context"
    a, b = offset_left // SAMPLE_NS, offset_right // SAMPLE_NS
    if a < 0 or b > trial["sample_count"]:
        return None, "missing_context"
    cursor = a
    for x, y in trial["valid_spans"]:
        if x <= cursor < y:
            cursor = y
        if cursor >= b:
            return [a, b], None
    return None, "invalid_context"


def case_id(trial_id: str, start: int) -> str:
    return hashlib.sha256(json.dumps([TASK_ID, trial_id, start], separators=(",", ":")).encode()).hexdigest()


def prepare(inventory: dict) -> dict:
    """Build evaluator-only windows, labels, exclusions and common EEG slice plan."""
    validate_inventory(inventory)
    cases, exclusions, trials_out = [], [], []
    for trial in inventory["trials"]:
        stats = {"trial_id": trial["trial_id"], "participant": trial["participant"], "condition": trial["condition"], "status": trial["status"], "grid_windows": trial["duration_ns"] // NS, "eligible_windows": 0, "excluded_windows": 0, "trailing_ns": trial["duration_ns"] % NS, "reason_counts": Counter()}
        events = trial.get("key_events", []) if trial["status"] == "available" else []
        # Repeated same-key reports are keypresses, but not state transitions.
        last = trial.get("initial_state")
        transitions = []
        for event in events:
            if last is not None and event["state"] != last:
                transitions.append(event["time_ns"])
            last = event["state"]
        for second in range(stats["grid_windows"]):
            start, end = second * NS, (second + 1) * NS
            reasons = []
            label, span = None, None
            if trial["status"] != "available":
                reasons.append("trial_" + trial["status"])
            else:
                label, reason = state_label(trial, start, end)
                if reason:
                    reasons.append(reason)
                span, reason = context_span(trial, start)
                if reason:
                    reasons.append(reason)
            row = {"case_id": case_id(trial["trial_id"], start), "trial_id": trial["trial_id"], "participant": trial["participant"], "condition": trial["condition"], "fold": inventory["mixture_folds"][trial["mixture_family"]], "mixture_family": trial["mixture_family"], "block_id": trial["block_id"], "order": trial["order"], "start_ns": start}
            if reasons:
                row["reasons"] = reasons
                row["defined_label"] = label
                exclusions.append(row)
                stats["excluded_windows"] += 1
                stats["reason_counts"].update(reasons)
            else:
                distances = [max(start-e["time_ns"], e["time_ns"]-end, 0) for e in events]
                transition_distances = [max(start-t, t-end, 0) for t in transitions]
                distance = min(distances) if distances else None
                row.update({"label": label, "eeg_sample_span": span, "keypress_distance_ns": distance, "guard_2s": distance is None or distance >= 2*NS, "transition_distance_ns": min(transition_distances) if transition_distances else None, "switches_in_target": sum(start <= t < end for t in transitions)})
                cases.append(row)
                stats["eligible_windows"] += 1
        stats["reason_counts"] = dict(stats["reason_counts"])
        trials_out.append(stats)
    return {"schema": "aasd-prepared-evaluator-only-v1", "participants": inventory["participants"], "cases": cases, "exclusions": exclusions, "trials": trials_out, "holds": HOLDS}


def split_plan(inventory: dict) -> list[dict]:
    """54 outer cells, excluding held person AND held mixture-fold from training."""
    prepared = prepare(inventory)
    cells = []
    active = [t for t in inventory["trials"] if t["condition"] == "active" and t["status"] == "available"]
    for person in inventory["participants"]:
        for fold in range(3):
            train = [t["trial_id"] for t in active if t["participant"] != person and inventory["mixture_folds"][t["mixture_family"]] != fold]
            test = [c["case_id"] for c in prepared["cases"] if c["condition"] == "active" and c["participant"] == person and c["fold"] == fold]
            passive = [c["case_id"] for c in prepared["cases"] if c["condition"] == "passive" and c["participant"] == person and c["fold"] == fold]
            cells.append({"participant": person, "held_mixture_fold": fold, "train_trial_ids": train, "test_case_ids": test, "passive_diagnostic_case_ids": passive, "passive_training_allowed": False})
    return cells


def validate_predictions(cases: list[dict], predictions: list[dict]) -> dict[str, float]:
    require(isinstance(predictions, list), "predictions must be a list")
    expected = {c["case_id"] for c in cases}
    result = {}
    for row in predictions:
        require(isinstance(row, dict) and set(row) == {"case_id", "p_right"}, "prediction fields must be case_id and p_right only")
        cid, p = row["case_id"], row["p_right"]
        identifier(cid, "prediction case_id")
        require(cid in expected and cid not in result, "unexpected or duplicate prediction case")
        require(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1, "probability must be finite and in [0,1]")
        result[cid] = float(p)
    require(set(result) == expected, f"predictions must cover every eligible active AND passive case: expected {len(expected)}, got {len(result)}")
    return result


def metrics(rows: list[dict], predictions: dict[str, float]) -> dict:
    matrix = [[0, 0], [0, 0]]
    bins = [[0, 0.0, 0.0] for _ in range(10)]
    losses, briers = [], []
    for row in rows:
        y, p = row["label"], predictions[row["case_id"]]
        matrix[y][int(p >= 0.5)] += 1
        q = min(max(p, EPS), 1-EPS)
        losses.append(-math.log(q if y else 1-q))
        briers.append((p-y)**2)
        b = bins[min(int(p * 10), 9)]
        b[0] += 1
        b[1] += p
        b[2] += y
    counts = [sum(row) for row in matrix]
    recalls = [matrix[y][y]/counts[y] if counts[y] else None for y in (0, 1)]
    n = len(rows)
    calibration = [{"lower": i/10, "upper": (i+1)/10, "n": b[0], "mean_p_right": b[1]/b[0] if b[0] else None, "fraction_right": b[2]/b[0] if b[0] else None} for i, b in enumerate(bins)]
    return {"n": n, "confusion_true_by_predicted": matrix, "label_counts": counts, "recall_left": recalls[0], "recall_right": recalls[1], "balanced_accuracy": sum(recalls)/2 if all(v is not None for v in recalls) else None, "log_loss": sum(losses)/n if n else None, "brier": sum(briers)/n if n else None, "ece_10": sum(abs(b[1]-b[2]) for b in bins)/n if n else None, "calibration_bins": calibration}


def population_metrics(rows: list[dict], people: list[str], predictions: dict) -> dict:
    participants = [{"participant": p, **metrics([r for r in rows if r["participant"] == p], predictions)} for p in people]
    macro = {}
    for metric in ("balanced_accuracy", "log_loss", "brier", "ece_10"):
        values = [p[metric] for p in participants if p[metric] is not None]
        macro[metric] = {"all_18": sum(values)/18 if len(values) == 18 else None, "eligible_participant_mean": sum(values)/len(values) if values else None, "eligible_participants": len(values), "required_participants": 18}
    return {"participants": participants, "macro": macro}


def paired_uncertainty(rows: list[dict], people: list[str], predictions: dict, comparator: dict, bootstrap_replicates: int = 2000, seed: int = 1729) -> dict:
    integer(bootstrap_replicates, "bootstrap_replicates", 100)
    require(bootstrap_replicates <= 100_000, "bootstrap_replicates exceeds construction bound")
    integer(seed, "seed")
    a = population_metrics(rows, people, predictions)["participants"]
    b = population_metrics(rows, people, comparator)["participants"]
    effects = [{"participant": p["participant"], "balanced_accuracy_difference": p["balanced_accuracy"]-q["balanced_accuracy"] if p["balanced_accuracy"] is not None and q["balanced_accuracy"] is not None else None} for p, q in zip(a, b)]
    if any(e["balanced_accuracy_difference"] is None for e in effects):
        return {"status": "all_18_not_estimable", "participant_effects": effects, "bootstrap_ci_95": None, "exact_sign_flip_p_two_sided": None}
    deltas = [e["balanced_accuracy_difference"] for e in effects]
    mean = sum(deltas)/18
    rng = random.Random(seed)
    boot = sorted(sum(deltas[rng.randrange(18)] for _ in range(18))/18 for _ in range(bootstrap_replicates))
    def quantile(q):
        index = q * (len(boot)-1)
        low = math.floor(index)
        return boot[low] + (boot[math.ceil(index)]-boot[low])*(index-low)
    signed_sums = [0.0]
    for delta in deltas:
        signed_sums = [s+delta for s in signed_sums] + [s-delta for s in signed_sums]
    extreme = sum(abs(s/18) >= abs(mean)-1e-14 for s in signed_sums)
    return {"status": "estimable", "participant_effects": effects, "mean_difference": mean, "bootstrap_ci_95": [quantile(.025), quantile(.975)], "bootstrap_replicates": bootstrap_replicates, "seed": seed, "exact_sign_flip_p_two_sided": extreme/len(signed_sums), "sign_flip_assignments": len(signed_sums), "assumption": "Paired participants are sampling units; sign-flip test requires symmetric/exchangeable null differences."}


def score(inventory: dict, predictions: list[dict], comparator: list[dict] | None = None, bootstrap_replicates: int = 2000, seed: int = 1729) -> dict:
    prepared = prepare(inventory)
    pred = validate_predictions(prepared["cases"], predictions)
    people = prepared["participants"]
    active = [c for c in prepared["cases"] if c["condition"] == "active"]
    passive = [c for c in prepared["cases"] if c["condition"] == "passive"]
    primary = population_metrics(active, people, pred)
    primary["status"] = "estimable" if primary["macro"]["balanced_accuracy"]["all_18"] is not None else "all_18_not_estimable"
    folds = [{"participant": p, "fold": f, **metrics([c for c in active if c["participant"] == p and c["fold"] == f], pred)} for p in people for f in range(3)]
    strata = {}
    strata["at_least_2s_from_keypress"] = population_metrics([c for c in active if c["guard_2s"]], people, pred)
    for name, select in {
        "transition_none": lambda c: c["transition_distance_ns"] is None,
        "transition_under_2s": lambda c: c["transition_distance_ns"] is not None and c["transition_distance_ns"] < 2*NS,
        "transition_at_least_2s": lambda c: c["transition_distance_ns"] is not None and c["transition_distance_ns"] >= 2*NS,
        "zero_switches": lambda c: c["switches_in_target"] == 0,
        "one_switch": lambda c: c["switches_in_target"] == 1,
        "multiple_switches": lambda c: c["switches_in_target"] >= 2,
    }.items():
        strata[name] = population_metrics([c for c in active if select(c)], people, pred)
    block_order = []
    for p in people:
        groups = defaultdict(list)
        for trial in inventory["trials"]:
            if trial["participant"] == p and trial["condition"] == "active":
                groups[(trial["block_id"], (trial["order"]-1)//10)].append(trial)
        for (block, order_bin), trials in sorted(groups.items()):
            tids = {t["trial_id"] for t in trials}
            rows = [c for c in active if c["trial_id"] in tids]
            excluded = [c for c in prepared["exclusions"] if c["trial_id"] in tids]
            block_order.append({"participant": p, "block_id": block, "order_decile": order_bin+1, "trial_slots": len(trials), "trial_status_counts": dict(Counter(t["status"] for t in trials)), "grid_windows": sum(t["duration_ns"]//NS for t in trials), "excluded_windows": len(excluded), "excluded_undefined_labels": sum(c["defined_label"] is None for c in excluded), "excluded_defined_label_counts": [sum(c["defined_label"] == y for c in excluded) for y in (0, 1)], "reason_counts": dict(Counter(reason for c in excluded for reason in c["reasons"])), **metrics(rows, pred)})
    coverage = []
    for p in people:
        for condition in ("active", "passive"):
            trials = [t for t in prepared["trials"] if t["participant"] == p and t["condition"] == condition]
            included = [c for c in prepared["cases"] if c["participant"] == p and c["condition"] == condition]
            excluded = [c for c in prepared["exclusions"] if c["participant"] == p and c["condition"] == condition]
            coverage.append({"participant": p, "condition": condition, "trial_status_counts": dict(Counter(t["status"] for t in trials)), "expected_trials": 60 if condition == "active" else 10, "grid_windows": sum(t["grid_windows"] for t in trials), "eligible_windows": len(included), "excluded_windows": len(excluded), "eligible_label_counts": [sum(c["label"] == y for c in included) for y in (0, 1)], "excluded_defined_label_counts": [sum(c["defined_label"] == y for c in excluded) for y in (0, 1)], "excluded_undefined_labels": sum(c["defined_label"] is None for c in excluded), "reason_counts": dict(Counter(reason for c in excluded for reason in c["reasons"]))})
    result = {"schema": "aasd-score-v1", "task_id": TASK_ID, "scientific_qualification": "unknown", "native_data_validated": False, "primary": primary, "per_mixture_fold": folds, "passive_motor_report_diagnostic": {"interpretation": "Key-report decoding only; not passive attention ground truth and not proof of motor-free active decoding.", **population_metrics(passive, people, pred)}, "secondary_strata": strata, "block_order_strata": block_order, "coverage": coverage, "trial_accounting": prepared["trials"], "holds": HOLDS}
    if comparator is not None:
        reference = validate_predictions(prepared["cases"], comparator)
        result["paired_comparison"] = paired_uncertainty(active, people, pred, reference, bootstrap_replicates, seed)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "split", "score"))
    parser.add_argument("inventory")
    parser.add_argument("--predictions")
    parser.add_argument("--comparator")
    parser.add_argument("--bootstrap-replicates", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=1729)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        inventory = strict_load(args.inventory)
        if args.operation == "prepare":
            result = prepare(inventory)
        elif args.operation == "split":
            result = {"schema": "aasd-split-v1", "cells": split_plan(inventory), "holds": HOLDS}
        else:
            require(args.predictions is not None, "score requires --predictions")
            result = score(inventory, strict_load(args.predictions), strict_load(args.comparator) if args.comparator else None, args.bootstrap_replicates, args.seed)
        Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    except (ContractError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"aasd evaluator: {exc}\n")


if __name__ == "__main__":
    main()
