"""Feature-level evaluation for PAPER-FIND-ADD-009; no model or waveform execution.

All acoustic feature extraction and training provenance are externally supplied.
This implementation freezes prospective, deterministic DTW details; it does not
claim numerical equivalence to the unavailable historical grading implementation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

TASK_ID = "PAPER-FIND-ADD-009"
CODE_REVISION = "cff4875decd35ff0f98a944035377a25b43ba79c"
DTW_POLICY = "squared-euclidean-full-path-diagonal-up-left-v1"
TRAIN_SESSIONS = tuple("t15_day" + s for s in (
    "025", "027", "032", "034", "039", "041", "046", "048", "067", "069",
    "074", "076", "081", "088", "090", "095", "097", "102", "104", "109",
    "110", "123", "132", "137", "139", "144", "146", "153", "165", "172",
    "174", "179", "181", "186", "188", "193"))
SIGNALS = {"neural", "microphone", "stethoscope", "imu", "combined_biosignals"}
HOLDS = [
    "Scientific qualification and authentic cohort completeness are unknown.",
    "No model training, pretrained inference, waveform extraction, or authentic evaluation was run.",
    "Feature extraction, silence masks, DTW equivalence, MCD conventions and historical references require qualification.",
    "The 2025 closed-loop populations (956 main trials; 240 biosignal control trials; 30 paired listening controls) are not reconstructed by this scorer.",
    "One participant T15 cannot establish new-person generalization or closed-loop clinical benefit.",
    "Official-code redistribution rights and data/vocoder/external speech resource terms remain separate gates.",
]


class ContractError(ValueError):
    """A declared cohort or metric input violates this implementation contract."""


def require(value, message):
    if not value:
        raise ContractError(message)


def text(value, name):
    require(isinstance(value, str) and value.strip() == value and bool(value), name + " must be a nonempty trimmed string")
    return value


def ids(values, name, nonempty=True):
    require(isinstance(values, list) and (bool(values) or not nonempty), name + " must be a list")
    for value in values:
        text(value, name)
    require(len(set(values)) == len(values), name + " contains duplicates")
    return set(values)


def finite(value, name):
    require(isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value), name + " must be finite numeric")
    return float(value)


def summary(values):
    require(bool(values), "cannot summarize an empty population")
    return {"n": len(values), "mean": statistics.fmean(values),
            "sd_sample": statistics.stdev(values) if len(values) > 1 else None,
            "median": statistics.median(values)}


def validate_manifest(manifest):
    require(isinstance(manifest, dict), "manifest must be an object")
    require(manifest.get("schema_version") == 1, "unsupported manifest schema")
    require(manifest.get("task_id") == TASK_ID, "wrong task identity")
    require(manifest.get("data_release") == "441124", "requires declared Dryad release 441124")
    require(manifest.get("official_code_revision") == CODE_REVISION, "wrong source revision")
    require(manifest.get("mode") in {"offline_retrained", "pretrained_inference"}, "declare synthesis mode")
    require(manifest.get("split_policy") in {"author_day195", "prospective_session_holdout"}, "unsupported split policy")
    profile = manifest.get("acoustic_profile", {})
    require(isinstance(profile, dict), "acoustic_profile must be an object")
    for key, value in {"representation": "mel_power_db", "bands": 40, "sample_rate_hz": 16000,
                       "window_ms": 50, "window": "hann", "dtw_policy": DTW_POLICY}.items():
        require(profile.get(key) == value, "acoustic_profile mismatch: " + key)
    # The article says '10 ms overlap'; hop interpretation is not silently inferred.
    require(profile.get("hop_ms") in {10, 40}, "explicit hop_ms must be 10 or 40; historical interpretation unresolved")
    for key in ("mel_filterbank_id", "db_reference_id", "silence_policy_id"):
        text(profile.get(key), "acoustic_profile." + key)
    rows = manifest.get("trials")
    require(isinstance(rows, list) and bool(rows), "trials must enumerate declared population")
    trials = {}
    group_partition = {}
    session_partition = {}
    sentence_partition = {}
    for row in rows:
        require(isinstance(row, dict), "trial must be an object")
        tid = text(row.get("trial_id"), "trial_id")
        require(tid not in trials, "duplicate trial_id")
        require(row.get("participant_id") == "T15", "this task is single-participant T15")
        part = row.get("partition")
        require(part in {"train", "validation", "test"}, "invalid trial partition")
        session = text(row.get("session_id"), "session_id")
        original = text(row.get("original_trial_id"), "original_trial_id")
        sentence = text(row.get("sentence_id"), "sentence_id")
        # Augmentation copies and repeat renders cannot cross selection boundaries.
        require(group_partition.setdefault(original, part) == part, "original trial crosses partitions")
        session_partition.setdefault(session, set()).add(part)
        sentence_partition.setdefault(sentence, set()).add(part)
        if manifest["split_policy"] == "author_day195":
            require((part == "test" and session == "t15_day195") or
                    (part != "test" and session in TRAIN_SESSIONS), "author day195 split violated")
        trials[tid] = row
    if manifest["split_policy"] == "author_day195":
        require({r["session_id"] for r in rows if r["partition"] != "test"} == set(TRAIN_SESSIONS),
                "author day195 profile requires all 36 declared training/validation sessions")
    require(any(r["partition"] == "test" for r in rows), "test cohort is empty")
    require(any(r["partition"] == "train" for r in rows), "training provenance is empty")
    for parts in session_partition.values():
        require("test" not in parts or len(parts) == 1, "test session exposed to training or validation")
    require(manifest.get("sentence_policy") in {"disjoint", "overlap_declared"}, "declare sentence overlap policy")
    if manifest["sentence_policy"] == "disjoint":
        for parts in sentence_partition.values():
            require("test" not in parts or len(parts) == 1, "test sentence exposed to fitting or selection")
    conditions = manifest.get("conditions")
    require(isinstance(conditions, list) and bool(conditions), "conditions must enumerate all methods")
    test_originals = [r["original_trial_id"] for r in rows if r["partition"] == "test"]
    require(len(set(test_originals)) == len(test_originals), "test cohort repeats an original trial")
    condition_map = {}
    train_ids = {k for k, r in trials.items() if r["partition"] == "train"}
    validation_ids = {k for k, r in trials.items() if r["partition"] == "validation"}
    for condition in conditions:
        require(isinstance(condition, dict), "condition must be an object")
        cid = text(condition.get("condition_id"), "condition_id")
        require(cid not in condition_map, "duplicate condition_id")
        require(condition.get("signal") in SIGNALS, "unknown neural/biosignal condition")
        for key in ("decoder_id", "vocoder_id", "training_provenance_id"):
            text(condition.get(key), key)
        require(ids(condition.get("training_trial_ids"), "training_trial_ids") == train_ids,
                "each condition must declare the full matched training-trial population")
        require(ids(condition.get("selection_trial_ids"), "selection_trial_ids", False) == validation_ids,
                "each condition must declare the full matched selection-trial population")
        resources = condition.get("external_speech_resources")
        require(isinstance(resources, list), "declare external speech/model resource exposure, even if empty")
        for resource in resources:
            require(isinstance(resource, dict), "resource must be an object")
            text(resource.get("resource_id"), "resource_id")
            text(resource.get("version"), "resource version")
            text(resource.get("role"), "resource role")
        condition_map[cid] = condition
    # Matched comparisons cannot silently change the waveform renderer or language prior.
    comparability = {(c["vocoder_id"], json.dumps(c["external_speech_resources"], sort_keys=True)) for c in conditions}
    require(len(comparability) == 1, "condition comparison requires matched vocoder and speech-resource exposure")
    baseline = text(manifest.get("neural_condition_id"), "neural_condition_id")
    require(baseline in condition_map and condition_map[baseline]["signal"] == "neural", "neural baseline missing")
    return trials, condition_map


def speech_frames(row, label):
    require(isinstance(row, dict), label + " must be an object")
    matrix = row.get("mel_db")
    mask = row.get("speech_mask")
    require(isinstance(matrix, list) and len(matrix) >= 2, label + " needs at least two frames")
    require(isinstance(mask, list) and len(mask) == len(matrix) and all(type(x) is bool for x in mask),
            label + " speech_mask must contain one explicit boolean per frame")
    result = []
    for keep, frame in zip(mask, matrix):
        require(isinstance(frame, list) and len(frame) == 40, label + " requires 40 Mel bands")
        parsed = [finite(v, label + " Mel value") for v in frame]
        if keep:
            result.append(parsed)
    require(len(result) >= 2, label + " has fewer than two speech frames")
    return result


def dtw_path(reference, prediction, max_cells=2_000_000):
    """Endpoint-constrained full DTW, squared Euclidean cost, fixed tie order.

    A cell's predecessor ties prefer diagonal, then up, then left. There is no
    fitted offset, path window, normalization, or hidden exclusion of frames.
    Cost memory is linear and backpointers use one byte per cell.
    """
    n, m = len(reference), len(prediction)
    require(type(max_cells) is int and max_cells >= 1, "max_cells must be a positive integer")
    require(n > 0 and m > 0 and n * m <= max_cells, "DTW exceeds explicit cell budget or is empty")
    back = bytearray(n * m)
    previous = [math.inf] * (m + 1)
    previous[0] = 0.0
    for i in range(1, n + 1):
        current = [math.inf] * (m + 1)
        for j in range(1, m + 1):
            choices = (previous[j - 1], previous[j], current[j - 1])
            step = min(range(3), key=choices.__getitem__)
            try:
                local = math.fsum((a - b) ** 2 for a, b in zip(reference[i - 1], prediction[j - 1]))
            except OverflowError as error:
                raise ContractError("DTW numeric overflow") from error
            current[j] = choices[step] + local
            require(math.isfinite(current[j]), "DTW numeric overflow")
            back[(i - 1) * m + j - 1] = step
        previous = current
    i, j = n - 1, m - 1
    path = []
    while True:
        path.append((i, j))
        if i == 0 and j == 0:
            break
        step = back[i * m + j]
        if step == 0:
            i -= 1
            j -= 1
        elif step == 1:
            i -= 1
        else:
            j -= 1
    path.reverse()
    return path, previous[m]


def pearson(x, y):
    mx, my = statistics.fmean(x), statistics.fmean(y)
    dx, dy = [v - mx for v in x], [v - my for v in y]
    xx, yy = math.fsum(v * v for v in dx), math.fsum(v * v for v in dy)
    require(xx > 0 and yy > 0 and math.isfinite(xx) and math.isfinite(yy), "constant or overflowed Mel band: correlation undefined")
    value = math.fsum(a * b for a, b in zip(dx, dy)) / math.sqrt(xx) / math.sqrt(yy)
    require(math.isfinite(value), "correlation overflow")
    return min(1.0, max(-1.0, value))


def score_trial(reference_row, prediction_row, max_cells=2_000_000):
    reference = speech_frames(reference_row, "reference")
    prediction = speech_frames(prediction_row, "prediction")
    path, cost = dtw_path(reference, prediction, max_cells)
    bands = [pearson([reference[i][b] for i, _ in path], [prediction[j][b] for _, j in path]) for b in range(40)]
    return {"mean_band_pearson_r": statistics.fmean(bands), "band_pearson_r": bands,
            "reference_speech_frames": len(reference), "prediction_speech_frames": len(prediction),
            "dtw_path_length": len(path), "dtw_total_squared_cost": cost}


def evaluate_acoustic(manifest, references, predictions, max_cells=2_000_000):
    trials, conditions = validate_manifest(manifest)
    test_ids = {tid for tid, r in trials.items() if r["partition"] == "test"}
    require(isinstance(references, list) and isinstance(predictions, list), "references and predictions must be lists")
    ref_map, pred_map = {}, {}
    for row in references:
        require(isinstance(row, dict), "reference row must be an object")
        tid = text(row.get("trial_id"), "reference trial_id")
        require(tid not in ref_map, "duplicate reference trial")
        ref_map[tid] = row
    require(set(ref_map) == test_ids, "reference coverage must equal every declared test trial")
    for row in predictions:
        require(isinstance(row, dict), "prediction row must be an object")
        key = (text(row.get("trial_id"), "prediction trial_id"), text(row.get("condition_id"), "prediction condition_id"))
        require(key not in pred_map, "duplicate prediction trial/condition")
        pred_map[key] = row
    require(set(pred_map) == {(t, c) for t in test_ids for c in conditions}, "predictions must cover every test trial and condition exactly")
    records = []
    for tid in sorted(test_ids):
        for cid in sorted(conditions):
            result = score_trial(ref_map[tid], pred_map[tid, cid], max_cells)
            records.append({"trial_id": tid, "session_id": trials[tid]["session_id"],
                            "sentence_id": trials[tid]["sentence_id"], "condition_id": cid, **result})
    by_condition = {}
    for cid in sorted(conditions):
        selected = [r for r in records if r["condition_id"] == cid]
        sessions = {s: summary([r["mean_band_pearson_r"] for r in selected if r["session_id"] == s])
                    for s in sorted({r["session_id"] for r in selected})}
        by_condition[cid] = {"sentence_weighted": summary([r["mean_band_pearson_r"] for r in selected]),
                             "per_session": sessions,
                             "session_equal_weighted": summary([s["mean"] for s in sessions.values()])}
    lookup = {(r["trial_id"], r["condition_id"]): r["mean_band_pearson_r"] for r in records}
    neural = manifest["neural_condition_id"]
    paired = {cid: summary([lookup[t, neural] - lookup[t, cid] for t in sorted(test_ids)])
              for cid in sorted(conditions) if cid != neural}
    return {"schema_version": 1, "task_id": TASK_ID, "scope": "declared-cohort-offline-feature-evaluation",
            "mode": manifest["mode"], "scientific_qualification": "unknown", "authentic_population_verified": False,
            "dtw_policy": DTW_POLICY, "acoustic_profile": manifest["acoustic_profile"],
            "declared_test_trials": len(test_ids), "condition_summaries": by_condition,
            "paired_neural_minus_condition_r": paired, "trials": records, "holds": HOLDS}


def edit_distance(reference, hypothesis):
    """Unit-cost Levenshtein; tokens must be frozen upstream, with no text model."""
    require(isinstance(reference, list) and bool(reference), "reference tokens must be nonempty")
    require(isinstance(hypothesis, list), "hypothesis tokens must be a list")
    for token in reference + hypothesis:
        text(token, "token")
    previous = list(range(len(hypothesis) + 1))
    for i, ref in enumerate(reference, 1):
        current = [i]
        for j, hyp in enumerate(hypothesis, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ref != hyp)))
        previous = current
    return previous[-1]


def evaluate_transcriptions(plan, references, predictions):
    """Two frozen sentences per pair, seven fixed listeners, pairwise median WER/PER.

    This is a separate designated listening cohort, never inferred from acoustic
    output or replaced by speech-recognition model transcripts.
    """
    require(isinstance(plan, dict), "transcription plan must be an object")
    require(plan.get("schema_version") == 1 and plan.get("task_id") == TASK_ID, "wrong transcription plan")
    for key in ("tokenization_policy_id", "phonemization_policy_id", "pairing_policy_id"):
        text(plan.get(key), key)
    cohort_sizes = {"prospective": None, "paper_main_90": 90, "paper_video_38": 38,
                    "paper_residual_20": 20, "paper_biosignal_30": 30}
    cohort_label = plan.get("cohort_label")
    require(cohort_label in cohort_sizes, "declare one distinct listening cohort_label")
    cohort = ids(plan.get("trial_ids"), "transcription trial_ids")
    expected_size = cohort_sizes[cohort_label]
    require(expected_size is None or len(cohort) == expected_size, "named paper listening cohort size mismatch")
    conditions = ids(plan.get("condition_ids"), "transcription condition_ids")
    require(isinstance(plan.get("pairs"), list) and bool(plan["pairs"]), "sentence pairs required")
    used, pair_ids = set(), set()
    ref_map = {}
    require(isinstance(references, list) and isinstance(predictions, list), "transcription rows must be lists")
    for row in references:
        require(isinstance(row, dict), "transcription reference must be object")
        tid = text(row.get("trial_id"), "trial_id")
        require(tid not in ref_map, "duplicate transcription reference")
        for key in ("words", "phonemes"):
            edit_distance(row.get(key), [])
        ref_map[tid] = row
    require(set(ref_map) == cohort, "transcription reference coverage mismatch")
    pred_map = {}
    for row in predictions:
        require(isinstance(row, dict), "transcription prediction must be object")
        key = tuple(text(row.get(k), k) for k in ("trial_id", "condition_id", "listener_id"))
        require(key not in pred_map, "duplicate listener response")
        for field in ("words", "phonemes"):
            require(isinstance(row.get(field), list), "response tokens must be lists")
            for token in row[field]:
                text(token, "response token")
        pred_map[key] = row
    expected, output = set(), []
    for pair in plan["pairs"]:
        require(isinstance(pair, dict), "pair must be object")
        pair_id = text(pair.get("pair_id"), "pair_id")
        require(pair_id not in pair_ids, "duplicate pair ID")
        pair_ids.add(pair_id)
        tids = pair.get("trial_ids")
        require(len(ids(tids, "pair trial_ids")) == 2, "each pair requires exactly two distinct ordered trials")
        require(not (set(tids) & used), "trial reused across sentence pairs")
        used.update(tids)
        listeners = pair.get("listener_ids")
        require(len(ids(listeners, "listener_ids")) == 7, "each pair requires seven distinct fixed listeners")
        require(set(tids) <= cohort, "pair trial outside listening cohort")
        for cid in sorted(conditions):
            values = {"wer": [], "per": []}
            listener_rows = []
            for listener in listeners:
                keys = [(tid, cid, listener) for tid in tids]
                expected.update(keys)
                require(all(k in pred_map for k in keys), "incomplete paired listener responses")
                errors = {}
                for field, metric in (("words", "wer"), ("phonemes", "per")):
                    ref = sum((ref_map[t][field] for t in tids), [])
                    hyp = sum((pred_map[k][field] for k in keys), [])
                    count = edit_distance(ref, hyp)
                    rate = count / len(ref)
                    values[metric].append(rate)
                    errors[metric] = {"edit_count": count, "reference_tokens": len(ref), "rate": rate}
                listener_rows.append({"listener_id": listener, **errors})
            output.append({"pair_id": pair_id, "condition_id": cid, "trial_ids": tids,
                           "median_wer": statistics.median(values["wer"]), "median_per": statistics.median(values["per"]),
                           "listeners": listener_rows})
    require(used == cohort, "pairs must exhaust designated transcription cohort")
    require(set(pred_map) == expected, "extra or missing transcription responses")
    aggregate = {cid: {metric: summary([r["median_" + metric] for r in output if r["condition_id"] == cid])
                      for metric in ("wer", "per")} for cid in sorted(conditions)}
    return {"schema_version": 1, "task_id": TASK_ID, "scope": "declared-human-transcription-pairs",
            "cohort_label": cohort_label, "rate_units": "fraction; insertions may produce values above one", "pairs": output,
            "condition_summaries": aggregate, "scientific_qualification": "unknown",
            "authentic_population_verified": False, "holds": HOLDS}


def parse_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON object key: " + key)
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ContractError("nonfinite JSON: " + value)))


def load_json(path):
    return parse_json(Path(path).read_bytes())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("acoustic", "transcriptions"))
    parser.add_argument("--plan", required=True, help="acoustic manifest or transcription pairing plan")
    parser.add_argument("--reference", required=True, help="operator-side reference JSON; never a model input")
    parser.add_argument("--prediction", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-dtw-cells", type=int, default=2_000_000)
    args = parser.parse_args(argv)
    try:
        paths = [Path(args.plan), Path(args.reference), Path(args.prediction)]
        require(Path(args.output).resolve() not in {p.resolve() for p in paths}, "output must not overwrite an input")
        raw_inputs = [p.read_bytes() for p in paths]
        values = [parse_json(raw) for raw in raw_inputs]
        result = (evaluate_acoustic(*values, args.max_dtw_cells) if args.mode == "acoustic"
                  else evaluate_transcriptions(*values))
        result["input_sha256"] = {name: hashlib.sha256(raw).hexdigest()
                                  for name, raw in zip(("plan", "reference", "prediction"), raw_inputs)}
        Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    except (ContractError, OSError, json.JSONDecodeError, UnicodeError, OverflowError, TypeError, KeyError) as error:
        parser.exit(2, "evaluation rejected: " + str(error) + "\n")


if __name__ == "__main__":
    main()
