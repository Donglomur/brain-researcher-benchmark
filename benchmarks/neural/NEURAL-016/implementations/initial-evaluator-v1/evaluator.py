"""Prospective NEURAL-016 evaluator for frozen, paired held-out predictions.

This module does not fit a native Brain Treebank reference or certify scientific
admission. The operator owns the private targets and all evaluation output.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

TASK_ID = "NEURAL-016"
SOURCE_PATH = Path(__file__).with_name("source_manifest.json")


class ContractError(ValueError):
    """Malformed or scientifically incompatible evaluation input."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def fields(value: Any, allowed: set[str], name: str) -> None:
    require(isinstance(value, dict), f"{name} must be an object")
    require(not (set(value) - allowed), f"unknown fields in {name}; public protocol must not carry target values")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def identifier(value: Any, name: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), f"{name} must be a nonempty string")
    return value


def number(value: Any, name: str) -> float:
    require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{name} must be numeric")
    require(bool(np.isfinite(value)), f"{name} must be finite")
    return float(value)


def unique(values: Any, name: str) -> list[str]:
    require(isinstance(values, list) and len(values) > 0, f"{name} must be a nonempty list")
    for value in values:
        identifier(value, name)
    require(len(set(values)) == len(values), f"duplicate {name}")
    return values


def keyed(values: Any, key: str, name: str) -> dict[str, dict]:
    require(isinstance(values, list) and len(values) > 0, f"{name} must be a nonempty list")
    out = {}
    for value in values:
        require(isinstance(value, dict), f"{name} item must be an object")
        item_id = identifier(value.get(key), key)
        require(item_id not in out, f"duplicate {name} {item_id}")
        out[item_id] = value
    return out


def validate_protocol(protocol: dict) -> dict:
    """Validate declared provenance, roster, support and person/movie separation.

    Declared fit rows cannot prove that an external model actually respected them.
    That execution-verification gate remains open even after this check succeeds.
    """
    fields(protocol, {"schema_version", "task_id", "protocol_id", "frozen_before_outcomes", "data_scope", "recipe", "source_files", "population", "blocks", "rows", "folds"}, "protocol")
    require(protocol.get("schema_version") == 1 and protocol.get("task_id") == TASK_ID,
            "unsupported protocol schema or task")
    identifier(protocol.get("protocol_id"), "protocol_id")
    require(protocol.get("frozen_before_outcomes") is True, "protocol must be frozen before outcomes")
    require(protocol.get("data_scope") == "public_development_only", "protected admission is not implemented")
    recipe = protocol.get("recipe", {})
    fields(recipe, {"primary_metric", "constant_prediction_policy", "response_definition", "anatomy_selection", "preprocessing", "split_policy", "nuisance_features", "linguistic_features", "feature_lags_seconds", "response_window_seconds", "guard_seconds", "bootstrap_repetitions", "bootstrap_seed"}, "recipe")
    require(recipe.get("primary_metric") in {"delta_explained_variance", "delta_r2"}, "freeze primary metric convention")
    require(recipe.get("constant_prediction_policy") in {"report", "reject_full"}, "freeze constant prediction policy")
    identifier(recipe.get("response_definition"), "response_definition")
    require(recipe.get("anatomy_selection") == "training_only", "anatomy selection must be training only")
    require(recipe.get("preprocessing") == "training_only", "preprocessing must be training only")
    require(recipe.get("split_policy") == "outer_person_and_whole_movie", "person and whole-movie holdout required")
    nuisance = recipe.get("nuisance_features", {})
    fields(nuisance, {"speaker", "acoustic", "visual_motion", "word_timing"}, "nuisance_features")
    nuisance_names = []
    for role in ("speaker", "acoustic", "visual_motion", "word_timing"):
        nuisance_names.extend(unique(nuisance.get(role), f"{role} features"))
    require(len(nuisance_names) == len(set(nuisance_names)), "nuisance feature roles must be unambiguous")
    linguistic = unique(recipe.get("linguistic_features"), "linguistic features")
    require(not set(linguistic) & set(nuisance_names), "linguistic features also occur in nuisance comparator")
    lags = recipe.get("feature_lags_seconds")
    require(isinstance(lags, list) and len(lags) > 0, "feature lags required")
    lags = [number(x, "feature lag") for x in lags]
    require(max(lags) <= 0, "future-valued predictors are not permitted")
    window = recipe.get("response_window_seconds")
    require(isinstance(window, list) and len(window) == 2, "response window requires two bounds")
    window = [number(x, "response window") for x in window]
    require(window[0] < window[1], "empty response window")
    guard = number(recipe.get("guard_seconds"), "guard_seconds")
    require(guard >= max(abs(x) for x in lags + window), "guard does not cover every lag and response window")
    repetitions = recipe.get("bootstrap_repetitions")
    require(isinstance(repetitions, int) and not isinstance(repetitions, bool) and 100 <= repetitions <= 100000,
            "bootstrap repetitions must be an integer from 100 to 100000")
    seed = recipe.get("bootstrap_seed")
    require(isinstance(seed, int) and not isinstance(seed, bool) and 0 <= seed < 2**32, "invalid bootstrap seed")
    pins = keyed(protocol.get("source_files"), "role", "source pins")
    require({"neural", "timing", "transcripts", "electrodes"} <= set(pins), "missing selected-payload source pins")
    for pin in pins.values():
        fields(pin, {"role", "sha256", "bytes", "identity"}, "source pin")
        digest = pin.get("sha256")
        require(isinstance(digest, str) and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), "invalid source hash")
        require(isinstance(pin.get("bytes"), int) and not isinstance(pin["bytes"], bool) and pin["bytes"] > 0, "invalid source byte count")
        identifier(pin.get("identity"), "source identity")
    source = json.loads(SOURCE_PATH.read_text())
    roster = {r["recording_id"]: r for r in source["recordings"]}
    population = keyed(protocol.get("population"), "recording_id", "population")
    require(set(population) == set(roster), "population must account for all 26 canonical recordings")
    for item in population.values():
        fields(item, {"recording_id", "disposition", "reason"}, "population record")
        require(item.get("disposition") in {"included", "excluded"}, "invalid population disposition")
        identifier(item.get("reason"), "population selection/exclusion reason")
    blocks = keyed(protocol.get("blocks"), "block_id", "blocks")
    for block in blocks.values():
        fields(block, {"block_id", "recording_id", "start_seconds", "end_seconds"}, "block")
        recording = block.get("recording_id")
        require(recording in roster and population[recording]["disposition"] == "included", "block recording is unknown or excluded")
        start = number(block.get("start_seconds"), "block start")
        end = number(block.get("end_seconds"), "block end")
        require(0 <= start < end, "invalid block bounds")
    # Named continuous blocks may not overlap within the same recording.
    per_recording = defaultdict(list)
    for block in blocks.values():
        per_recording[block["recording_id"]].append(block)
    for group in per_recording.values():
        ordered = sorted(group, key=lambda b: b["start_seconds"])
        for left, right in zip(ordered, ordered[1:]):
            require(left["end_seconds"] <= right["start_seconds"], "overlapping continuous blocks")
    rows = keyed(protocol.get("rows"), "row_id", "rows")
    observation_keys = set()
    for row in rows.values():
        fields(row, {"row_id", "recording_id", "participant_id", "movie_id", "electrode_id", "block_id", "time_seconds"}, "row")
        block = blocks.get(row.get("block_id"))
        require(block is not None, "unknown row block")
        source_row = roster[block["recording_id"]]
        for field in ("recording_id", "participant_id", "movie_id"):
            require(row.get(field) == source_row[field], f"row {field} does not match canonical roster")
        electrode = identifier(row.get("electrode_id"), "electrode_id")
        t = number(row.get("time_seconds"), "row time")
        require(block["start_seconds"] + guard <= t <= block["end_seconds"] - guard,
                "row violates temporal guard band")
        key = (row["recording_id"], electrode, t)
        require(key not in observation_keys, "duplicate biological observation under different IDs")
        observation_keys.add(key)
    represented = {r["recording_id"] for r in rows.values()}
    require(represented == {r for r, p in population.items() if p["disposition"] == "included"},
            "included recordings must be represented; no silent population loss")
    require({r["block_id"] for r in rows.values()} == set(blocks), "unused declared block")
    folds = keyed(protocol.get("folds"), "fold_id", "folds")
    evaluation_ids, used_ids, evaluated_blocks = set(), set(), set()
    for fold in folds.values():
        fields(fold, {"fold_id", "fit_row_ids", "evaluation_row_ids"}, "fold")
        fit = unique(fold.get("fit_row_ids"), "fit rows")
        test = unique(fold.get("evaluation_row_ids"), "evaluation rows")
        require(set(fit + test) <= set(rows), "fold has unknown row IDs")
        require(not set(fit) & set(test), "fit/evaluation row overlap")
        require(not evaluation_ids & set(test), "an evaluation row appears in multiple folds")
        test_blocks = {rows[r]["block_id"] for r in test}
        require(not evaluated_blocks & test_blocks, "an evaluation block appears in multiple folds")
        evaluated_blocks.update(test_blocks)
        require({r for r, row in rows.items() if row["block_id"] in test_blocks} == set(test),
                "evaluation must include every declared row of each held-out block")
        evaluation_ids.update(test)
        used_ids.update(fit + test)
        for field in ("participant_id", "movie_id", "recording_id", "block_id"):
            require(not {rows[r][field] for r in fit} & {rows[r][field] for r in test},
                    f"fit/evaluation {field} leakage")
    require(used_ids == set(rows), "unused protocol rows")
    return {"rows": rows, "folds": folds, "evaluation_ids": evaluation_ids,
            "source": source, "recipe": recipe, "population": population}


def contrast(target: Any, nuisance: Any, full: Any) -> dict:
    """Population-variance EV and SSE-based R² on identical held-out rows.

    EV = 1 - Var(y-prediction)/Var(y), R² = 1 - SSE/SST. Negative values
    and negative increments are retained. A constant target is undefined.
    """
    arrays = [np.asarray(x, dtype=float) for x in (target, nuisance, full)]
    y, n, f = arrays
    require(y.ndim == 1 and len(y) >= 2, "each scored block needs at least two observations")
    require(all(a.shape == y.shape and bool(np.isfinite(a).all()) for a in arrays), "nonfinite or mismatched score arrays")
    with np.errstate(over="ignore", invalid="ignore"):
        sst = float(np.sum((y - y.mean()) ** 2))
    require(np.isfinite(sst) and sst > 0, "constant or numerically invalid target block")
    result = {"n_observations": len(y), "target_sst": sst}
    for label, predicted in (("nuisance", n), ("full", f)):
        with np.errstate(over="ignore", invalid="ignore"):
            residual = y - predicted
            sse = float(np.sum(residual**2))
            # Center operands first: centering y-predicted can erase tiny target
            # variation in the presence of a large constant prediction bias.
            centered_residual = (y - y.mean()) - (predicted - predicted.mean())
            centered = float(np.sum(centered_residual**2))
        require(np.isfinite(sse) and np.isfinite(centered), "numerically invalid prediction residuals")
        result[label + "_sse"] = sse
        result[label + "_r2"] = 1.0 - sse / sst
        result[label + "_explained_variance"] = 1.0 - centered / sst
        require(np.isfinite(result[label + "_r2"]) and np.isfinite(result[label + "_explained_variance"]),
                "numerically nonfinite metric")
        result[label + "_constant"] = bool(np.all(predicted == predicted[0]))
    for metric in ("r2", "explained_variance"):
        result["delta_" + metric] = result["full_" + metric] - result["nuisance_" + metric]
        require(np.isfinite(result["delta_" + metric]), "numerically nonfinite contrast")
    return result


def summarize(block_results: list[dict], repetitions: int, seed: int) -> dict:
    """Equal blocks within electrode, equal electrodes within participant.

    Participant resampling is paired across the two prediction arms and both
    metrics. It does not imply independent random sampling of clinical subjects
    or account for cross-participant shared stimulus dependence.
    """
    groups = defaultdict(list)
    for block in block_results:
        groups[(block["participant_id"], block["electrode_id"])].append(block)
    electrodes = []
    metrics = ("delta_explained_variance", "delta_r2")

    def checked_mean(values):
        with np.errstate(over="ignore", invalid="ignore"):
            value = float(np.mean(values))
        require(np.isfinite(value), "numerically nonfinite aggregate")
        return value

    for (participant, electrode), group in sorted(groups.items()):
        entry = {"participant_id": participant, "electrode_id": electrode, "n_blocks": len(group)}
        entry.update({m: checked_mean([r[m] for r in group]) for m in metrics})
        electrodes.append(entry)
    participants = []
    for participant in sorted({e["participant_id"] for e in electrodes}):
        group = [e for e in electrodes if e["participant_id"] == participant]
        entry = {"participant_id": participant, "n_electrodes": len(group)}
        entry.update({m: checked_mean([r[m] for r in group]) for m in metrics})
        participants.append(entry)
    require(len(participants) > 0, "no participant summaries")
    estimates = {m: checked_mean([p[m] for p in participants]) for m in metrics}
    intervals = None
    if len(participants) > 1:
        rng = np.random.default_rng(seed)
        values = np.array([[p[m] for m in metrics] for p in participants])
        # Bounded by participant count, not electrode or word count.
        draws = np.empty((repetitions, len(metrics)))
        for index in range(repetitions):
            with np.errstate(over="ignore", invalid="ignore"):
                draws[index] = values[rng.integers(0, len(values), len(values))].mean(axis=0)
        require(bool(np.isfinite(draws).all()), "numerically nonfinite bootstrap draws")
        with np.errstate(over="ignore", invalid="ignore"):
            bounds = np.quantile(draws, [0.025, 0.975], axis=0)
        require(bool(np.isfinite(bounds).all()), "numerically nonfinite bootstrap interval")
        intervals = {m: [float(bounds[0, i]), float(bounds[1, i])] for i, m in enumerate(metrics)}
    return {"electrodes": electrodes, "participants": participants, "estimate": estimates,
            "participant_paired_bootstrap_95_percentile": intervals,
            "uncertainty_scope": "descriptive clinical-participant resampling; shared-movie dependence is not removed",
            "n_participants": len(participants)}


def _prediction_map(values: Any, expected: set[str]) -> dict:
    prediction_map = keyed(values, "row_id", "predictions")
    require(set(prediction_map) == expected, "prediction IDs must exactly match all evaluation rows")
    for prediction in prediction_map.values():
        number(prediction.get("nuisance"), "nuisance prediction")
        number(prediction.get("full"), "full prediction")
    return prediction_map


def _fit_provenance(values: Any, context: dict, recipe: dict) -> dict:
    provenance = keyed(values, "fold_id", "fit provenance")
    require(set(provenance) == set(context["folds"]), "fit provenance must cover every fold")
    for fold_id, fold in context["folds"].items():
        item = provenance[fold_id]
        require(set(unique(item.get("fit_row_ids"), "declared fit rows")) == set(fold["fit_row_ids"]), "declared fit rows differ from frozen fold")
        require(item.get("recipe_sha256") == canonical_hash(recipe), "fit recipe hash mismatch")
        for arm in ("nuisance", "full"):
            identifier(item.get(arm + "_artifact_sha256"), arm + " artifact hash")
            require(len(item[arm + "_artifact_sha256"]) == 64 and all(c in "0123456789abcdef" for c in item[arm + "_artifact_sha256"]), "invalid fitted artifact hash")
    return provenance


def _score_rows(context: dict, targets: dict, predictions: dict) -> tuple[list[dict], dict]:
    groups = defaultdict(list)
    for fold in context["folds"].values():
        for row_id in fold["evaluation_row_ids"]:
            row = context["rows"][row_id]
            groups[(fold["fold_id"], row["participant_id"], row["electrode_id"],
                    row["recording_id"], row["block_id"])].append(row_id)
    block_results = []
    for key, row_ids in sorted(groups.items()):
        row_ids.sort(key=lambda r: (context["rows"][r]["time_seconds"], r))
        metrics = contrast([targets[r]["value"] for r in row_ids],
                           [predictions[r]["nuisance"] for r in row_ids],
                           [predictions[r]["full"] for r in row_ids])
        if context["recipe"]["constant_prediction_policy"] == "reject_full":
            require(not metrics["full_constant"], "constant full prediction under reject_full policy")
        block_results.append(dict(zip(("fold_id", "participant_id", "electrode_id", "recording_id", "block_id"), key), **metrics))
    summary = summarize(block_results, context["recipe"]["bootstrap_repetitions"], context["recipe"]["bootstrap_seed"])
    return block_results, summary


def evaluate(protocol: dict, private_targets: dict, submission: dict) -> dict:
    """Score a complete paired prediction packet bound to a frozen protocol."""
    context = validate_protocol(protocol)
    digest = canonical_hash(protocol)
    for packet in (private_targets, submission):
        require(isinstance(packet, dict) and packet.get("protocol_sha256") == digest, "packet protocol hash mismatch")
    targets = keyed(private_targets.get("values"), "row_id", "private targets")
    expected = context["evaluation_ids"]
    require(set(targets) == expected, "private target IDs must exactly match all evaluation rows")
    for target in targets.values():
        number(target.get("value"), "private target")
    predictions = _prediction_map(submission.get("predictions"), expected)
    provenance = _fit_provenance(submission.get("fit_provenance"), context, protocol["recipe"])
    blocks, summary = _score_rows(context, targets, predictions)
    primary = context["recipe"]["primary_metric"]
    nulls = submission.get("null_predictions", [])
    require(isinstance(nulls, list), "null_predictions must be a list")
    null_results, null_ids = [], set()
    for null in nulls:
        require(isinstance(null, dict), "null control must be an object")
        null_id = identifier(null.get("permutation_id"), "permutation_id")
        require(null_id not in null_ids, "duplicate permutation_id")
        null_ids.add(null_id)
        require(null.get("control") == "joint_linguistic_circular_shift_uniform_time", "unsupported null control")
        require(null.get("refitted_recipe_sha256") == canonical_hash(protocol["recipe"]), "null refit recipe mismatch")
        shift_hash = null.get("shift_manifest_sha256")
        require(isinstance(shift_hash, str) and len(shift_hash) == 64 and all(c in "0123456789abcdef" for c in shift_hash),
                "null requires pinned per-block shift manifest")
        null_provenance = _fit_provenance(null.get("fit_provenance"), context, protocol["recipe"])
        require(all(item["nuisance_artifact_sha256"] == provenance[fold_id]["nuisance_artifact_sha256"]
                    for fold_id, item in null_provenance.items()), "null changed nuisance artifact")
        # Nuisance predictions are identical; only linguistic inputs may change.
        null_map = _prediction_map(null.get("predictions"), expected)
        require(all(null_map[r]["nuisance"] == predictions[r]["nuisance"] for r in expected), "null changed the nuisance comparator")
        _, null_summary = _score_rows(context, targets, null_map)
        null_results.append({"permutation_id": null_id, "shift_manifest_sha256": shift_hash,
                             "estimate": null_summary["estimate"]})
    null_control = {"status": "not_supplied" if not nulls else "supplied_unverified_exchangeability",
                    "replicates": null_results, "descriptive_upper_tail_rank": None}
    if null_results:
        # Not called a calibrated p-value: a conditional-null proof is absent.
        count = sum(n["estimate"][primary] >= summary["estimate"][primary] for n in null_results)
        null_control["descriptive_upper_tail_rank"] = (1 + count) / (1 + len(null_results))
    source_holds = context["source"]["holds"]
    return {"task_id": TASK_ID, "implementation": "initial-evaluator-v1", "protocol_sha256": digest,
            "private_targets_sha256": canonical_hash(private_targets), "submission_sha256": canonical_hash(submission),
            "status": "prospective_evaluator_output_public_development_only", "primary_metric": primary,
            "primary_estimate": summary["estimate"][primary], "blocks": blocks, "summary": summary,
            "null_control": null_control,
            "population_accounting": {"canonical_recordings": 26, "canonical_participants": 10, "canonical_movies": 21,
                                      "included_recordings": sum(p["disposition"] == "included" for p in context["population"].values()),
                                      "evaluation_rows": len(expected)},
            "admission": {"research_qualified": False, "submission_ready": False, "native_reference_executed": False},
            "preserved_source_holds": source_holds,
            "additional_holds": ["Primary metric convention and complete processing recipe require scientific freeze.",
                                 "Declared data pins, fit IDs, selection and artifact hashes require independent execution verification.",
                                 "Public protocol metadata require release review; allowlisted text fields cannot be proven free of encoded targets.",
                                 "Cross-person output correspondence for clinically distinct electrodes is not defined by this evaluator.",
                                 "Uniform-time circular shift requires stationarity; conditional-null exchangeability and common-movie uncertainty remain unresolved."]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--private-targets", type=Path, required=True)
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = [args.protocol, args.private_targets, args.submission]
    try:
        require(args.output.resolve() not in {p.resolve() for p in paths}, "output must not overwrite an input packet")
        raw = [p.read_bytes() for p in paths]
        packets = [json.loads(content) for content in raw]
        result = evaluate(*packets)
        result["input_file_sha256"] = {name: hashlib.sha256(content).hexdigest() for name, content in zip(("protocol", "private_targets", "submission"), raw)}
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(2, f"invalid NEURAL-016 input: {error}\n")


if __name__ == "__main__":
    main()
