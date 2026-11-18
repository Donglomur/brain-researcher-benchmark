"""Condition-matched constant count baseline over complete permitted training.

This pure operand API never loads scientific files or receives test responses.
Sibling code is hash-checked once at import. Source authenticity, complete native
census, freezing chronology and protected execution remain external obligations.
"""
import hashlib
import importlib.util
import math
from pathlib import Path
import struct


def _dependency(name, relative, expected):
    path = Path(__file__).resolve().parent.parent / relative
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("constant baseline dependency identity mismatch: " + relative)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TRAIN = _dependency("retina_constant_train", "training-response/train_only.py",
    "ddae29d684b1c808156529538dd9f1153697023c82f4fc523b1af0edc06521ce")
SCORE = _dependency("retina_constant_score", "protected-scoring-v1/scorer.py",
    "2c61c9c04657ab4a63dc5fabe0540b671c73ec413b499a0f11b33c3ae4f3c51b")
SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
InputError = SCORE.InputError
need, exact = SCORE.need, SCORE.exact


def _key(stream):
    need(type(stream["dataset"]) is str and type(stream["stimulus"]) is str and
         (stream["seed"] is None or type(stream["seed"]) is int), "primitive stream identity")
    return (stream["dataset"], stream["stimulus"], stream["seed"])


def _positive_integer(value):
    need(type(value) is int and value > 0, "positive whole-operation byte allocation")


def predict(training_policy, training_result, score_policy, *, training_policy_sha256,
            training_result_sha256, score_policy_sha256, training_count_byte_budget,
            prediction_byte_budget):
    """Return fixed source-training means on all declared protected updates.

The output uses the existing scorer's prediction schema. It is a constant-rate
diagnostic, NOT the condition-matched spatial-contrast reference required for an
improvement claim. Its Pearson correlation is intentionally undefined. Its
individual-repeat Poisson NLL is a meaningful registered diagnostic.

Budgets cover immutable count/prediction buffers, not Python peak memory.
Operands are already in owner memory; no scientific file or target input occurs.
"""
    for value in (training_count_byte_budget, prediction_byte_budget):
        _positive_integer(value)
    try:
        preparations, source_streams = TRAIN.validate_policy(training_policy, training_policy_sha256)
    except (TRAIN.InputError, TypeError, KeyError) as exc:
        raise InputError("training policy: " + str(exc)) from None
    SCORE.pinned(training_result, training_result_sha256)
    SCORE.pinned(score_policy, score_policy_sha256)
    score_preps, target_streams = SCORE.validate_policy(score_policy)
    need(score_policy["training_policy_sha256"] == training_policy_sha256 and
         score_policy["condition"] == training_policy["condition"], "same frozen training policy and condition")
    for field in ("cohort_evidence_sha256", "complete_stream_census_sha256"):
        need(score_policy[field] == training_policy[field], "same declared original census: " + field)
    by_preparation = {p["dataset"]: p["cells"] for p in training_policy["preparations"]}
    need(score_preps == by_preparation, "same complete classified cell identities/order")
    source_by_key = {_key(s): s for s in source_streams}
    target_domain = SCORE.TARGET_DOMAIN[training_policy["condition"]]
    expected_target_keys = {key for key in source_by_key if key[1] == target_domain}
    need({_key(s) for s in target_streams.values()} == expected_target_keys,
         "all declared target-domain preparation/seed streams required")
    for stream in target_streams.values():
        need(len(stream["frame_ids"]) <= source_by_key[_key(stream)]["test_frames_per_trial"],
             "eligible target updates cannot exceed frozen original extent")
    allowed = TRAIN.CONDITIONS[training_policy["condition"]]
    selected = {key: s for key, s in source_by_key.items() if key[1] in allowed}
    exact(training_result, "schema task_id policy_sha256 condition packets selected_cells preparations "
          "source_body_bytes output_count_bytes protected_response_reads original_sta_reads "
          "historical_test_selected_cohort scientific_qualification limits", "training result")
    need(training_result["schema"] == "marmoset-train-only-response-result-v1" and
         training_result["task_id"] == TRAIN.TASK and
         training_result["policy_sha256"] == training_policy_sha256 and
         training_result["condition"] == training_policy["condition"], "exact prepared response route")
    need(type(training_result["selected_cells"]) is int and training_result["selected_cells"] == 170 and
         type(training_result["preparations"]) is int and training_result["preparations"] == 2 and
         training_result["historical_test_selected_cohort"] is True and
         training_result["scientific_qualification"] is False, "unchanged complete conditional scope")
    for field in ("protected_response_reads", "original_sta_reads"):
        need(type(training_result[field]) is int and training_result[field] == 0,
             "incompatible response-loader declaration")
    need(type(training_result["limits"]) is list and
         all(type(v) is str for v in training_result["limits"]), "prepared response limitations")
    required_counts = sum(len(preparations[s["dataset"]]) * len(s["train_trial_ids"]) *
                          s["train_frames_per_trial"] * TRAIN.DTYPES[s["artifact"]["dtype"]][1]
                          for s in selected.values())
    required_predictions = sum(len(score_preps[s["dataset"]]) * len(s["frame_ids"]) * 8
                               for s in target_streams.values())
    need(training_count_byte_budget >= required_counts and prediction_byte_budget >= required_predictions,
         "complete buffer allocation required; no stream/cell/frame subset")
    need(type(training_result["output_count_bytes"]) is int and
         training_result["output_count_bytes"] == required_counts and
         type(training_result["source_body_bytes"]) is int and
         training_result["source_body_bytes"] == sum(s["artifact"]["bytes"] for s in selected.values()),
         "complete permitted source/output extent declaration")
    need(type(training_result["packets"]) is list and len(training_result["packets"]) == len(selected),
         "all and only condition-permitted prepared packets")
    sums = {dataset: [0] * len(cells) for dataset, cells in preparations.items()}
    observations = dict.fromkeys(preparations, 0)
    fit_streams, calibration_streams, seen = [], [], set()
    for packet in training_result["packets"]:
        exact(packet, "dataset stimulus seed response_access cell_ids train_trial_ids shape dtype unit order "
              "counts counts_sha256 source_sha256 test_frames_per_trial extent_source "
              "timing_evidence_sha256 independent_extent_evidence_sha256", "prepared count packet")
        key = _key(packet)
        need(key in selected and key not in seen, "unknown or duplicate prepared stream")
        seen.add(key)
        stream, cells = selected[key], preparations[packet["dataset"]]
        shape = [len(cells), len(stream["train_trial_ids"]), stream["train_frames_per_trial"]]
        need(type(packet["shape"]) is list and all(type(v) is int for v in packet["shape"]),
             "primitive prepared shape")
        for field, expected in {
            "response_access": allowed[packet["stimulus"]], "cell_ids": cells,
            "train_trial_ids": stream["train_trial_ids"], "shape": shape,
            "dtype": stream["artifact"]["dtype"], "unit": SCORE.UNIT, "order": "C",
            "source_sha256": stream["artifact"]["sha256"],
            "test_frames_per_trial": stream["test_frames_per_trial"],
            "extent_source": "externally frozen target-independent metadata; not a test-response read",
            "timing_evidence_sha256": stream["timing_evidence_sha256"],
            "independent_extent_evidence_sha256": stream["independent_extent_evidence_sha256"],
        }.items():
            need(packet[field] == expected, "prepared count metadata mismatch: " + field)
        body = packet["counts"]
        code, width = TRAIN.DTYPES[packet["dtype"]]
        per_cell = shape[1] * shape[2]
        need(type(body) is bytes and len(body) == shape[0] * per_cell * width and
             hashlib.sha256(body).hexdigest() == packet["counts_sha256"], "full prepared count identity/extent")
        used = packet["response_access"] == "fit"
        for flat, (value,) in enumerate(struct.iter_unpack("<" + code, body)):
            need(math.isfinite(value) and value >= 0 and
                 (type(value) is int or value.is_integer()), "finite nonnegative integral training counts")
            if used:
                sums[packet["dataset"]][flat // per_cell] += int(value)
        info = {"dataset": key[0], "stimulus": key[1], "seed": key[2],
                "source_observations_per_cell": per_cell, "counts_sha256": packet["counts_sha256"]}
        if used:
            observations[key[0]] += per_cell
            fit_streams.append(info)
        else:
            calibration_streams.append(info)
    need(seen == set(selected) and all(v > 0 for v in observations.values()), "complete fit-domain support")
    fit_cells, means = [], {}
    for dataset, cells in preparations.items():
        means[dataset] = []
        for cell, total in zip(cells, sums[dataset]):
            value = total / observations[dataset]
            need(math.isfinite(value) and value >= 0, "representable mean count")
            means[dataset].append(value)
            fit_cells.append({"dataset": dataset, "cell_id": cell, "count_sum": total,
                              "source_observations": observations[dataset], "mean_count": value})
    fitted = {"schema": "marmoset-constant-fit-v1", "task_id": TRAIN.TASK,
              "source_sha256": SOURCE_SHA256, "training_policy_sha256": training_policy_sha256,
              "training_result_sha256": training_result_sha256,
              "condition": training_policy["condition"], "unit": SCORE.UNIT,
              "fit_streams": fit_streams, "calibration_streams_excluded_from_mean": calibration_streams,
              "cells": fit_cells, "historical_test_selected_cohort": True}
    predictions = {"schema": "marmoset-predictions-v1", "task_id": TRAIN.TASK,
                   "condition": training_policy["condition"], "training_policy_sha256": training_policy_sha256,
                   "unit": SCORE.UNIT, "model_sha256": SCORE.fingerprint(fitted), "streams": []}
    for stream in target_streams.values():
        frames = len(stream["frame_ids"])
        body = b"".join(struct.pack("<d", mean) * frames for mean in means[stream["dataset"]])
        predictions["streams"].append({"stream_id": stream["stream_id"],
            "cell_ids": list(preparations[stream["dataset"]]), "frame_ids": list(stream["frame_ids"]),
            "dtype": "<f8", "values": body})
    SCORE.validate_bundle(predictions, score_policy, score_preps, target_streams)
    return {"schema": "marmoset-constant-baseline-v1", "fit": fitted, "predictions": predictions,
            "score_policy_sha256": score_policy_sha256, "prediction_bytes": required_predictions,
            "scientifically_qualified": False, "reference_role": "constant_rate_diagnostic_not_sc_reference",
            "limits": ["Constant predictions have undefined Pearson; do not replace undefined values with zero.",
                       "Individual-repeat Poisson scoring remains owner-only and requires protected targets.",
                       "Integer sums/denominators are exact; mean predictions are rounded to binary64.",
                       "Declared full support and hash identity do not authenticate native census, calibration or timing.",
                       "No stimulus reconstruction, RF fitting, competent spatial-contrast comparator or process isolation.",
                       "Historical test-selected cohort and unestablished animal independence remain unchanged."]}
