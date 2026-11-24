"""Assess the complete declared voice-synthesis biosignal control panel.

No model, waveform frontend, original membership recovery or scientific admission
is implemented here. The source's 240-trial panel is distinct from Fig. 2b.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import types


def load_acoustic_evaluator():
    path = Path(__file__).resolve().parents[1] / "initial-evaluator-v1/evaluator.py"
    raw = path.read_bytes()
    module = types.ModuleType("voice_feature_evaluator")
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module, hashlib.sha256(raw).hexdigest()


acoustic, ACOUSTIC_SHA256 = load_acoustic_evaluator()
require, text, ids = acoustic.require, acoustic.text, acoustic.ids
ContractError = acoustic.ContractError
SYSTEMS = ("author_baseline", "paper_data", "paper_data_author_code")
SIGNALS = ("neural", "microphone", "stethoscope", "imu", "combined_biosignals")
FEATURES = dict(zip(SIGNALS, (512, 40, 40, 240, 320)))
HOLDS = [
    "This is the secondary 240-trial biosignal panel, not the primary 956-trial result.",
    "Original trial/fold identities and authentic derivation are externally supplied and remain unverified.",
    "The prospective feature evaluator's frontend, masks and DTW parity with the historical procedure remain unqualified.",
    "Descriptive arm/baseline deltas do not establish reproduction, improvement, a rank-sum result or uncertainty.",
    "The 30-trial listening comparison, contamination analysis, nonspeech and fixed-decoder transfer remain separate requirements.",
    "No model training/inference, authentic evaluation, matched access enforcement or closed-loop intervention is performed.",
]


def digest(value, label):
    require(isinstance(value, str) and len(value) == 64 and
            all(c in "0123456789abcdef" for c in value), label + " must be a lowercase SHA-256")
    return value


def validate_plan(plan):
    require(isinstance(plan, dict), "plan must be an object")
    require(plan.get("schema_version") == "voice-biosignal-panel/v1", "wrong schema")
    require(plan.get("task_id") == acoustic.TASK_ID, "wrong task")
    require(plan.get("data_release") == "441124", "wrong declared data release")
    require(plan.get("source_panel") == "extended_data_5c_240", "wrong source panel")
    digest(plan.get("original_support_sha256"), "original_support_sha256")
    require(plan.get("source_input_features") == FEATURES, "source modality feature counts differ")
    require(plan.get("source_feature_bin_ms") == 10 and plan.get("source_context_ms") == 600,
            "source temporal feature contract differs")
    vocabulary = ids(plan.get("vocabulary"), "source vocabulary")
    require(len(vocabulary) == 50, "source control vocabulary must have 50 words")
    profile = plan.get("acoustic_profile")
    require(isinstance(profile, dict), "acoustic_profile must be an object")
    for key, value in {"representation": "mel_power_db", "bands": 40, "sample_rate_hz": 16000,
                       "window_ms": 50, "window": "hann", "dtw_policy": acoustic.DTW_POLICY}.items():
        require(profile.get(key) == value, "acoustic_profile mismatch: " + key)
    require(profile.get("hop_ms") in {10, 40}, "declare unresolved source hop interpretation as 10 or 40 ms")
    for key in ("mel_filterbank_id", "db_reference_id", "silence_policy_id"):
        text(profile.get(key), "acoustic_profile." + key)
    rows = plan.get("trials")
    require(isinstance(rows, list) and len(rows) == 240, "requires all 240 control trials")
    trials, original_ids = {}, set()
    for row in rows:
        require(isinstance(row, dict), "trial must be an object")
        tid = text(row.get("trial_id"), "trial_id")
        require(tid not in trials, "duplicate trial_id")
        require(row.get("participant_id") == "T15", "requires T15")
        oid = text(row.get("original_trial_id"), "original_trial_id")
        require(oid not in original_ids, "duplicate physical trial")
        original_ids.add(oid)
        for key in ("session_id", "sentence_id"):
            text(row.get(key), key)
        trials[tid] = row
    folds = plan.get("folds")
    require(isinstance(folds, list) and len(folds) == 10, "requires all ten declared original folds")
    fold_map, held_fold = {}, {}
    for row in folds:
        require(isinstance(row, dict), "fold must be an object")
        fid = text(row.get("fold_id"), "fold_id")
        require(fid not in fold_map, "duplicate fold_id")
        held = ids(row.get("test_trial_ids"), "fold test_trial_ids")
        train = ids(row.get("training_trial_ids"), "fold training_trial_ids")
        require(held <= set(trials), "fold includes unknown held trial")
        require(train == set(trials) - held, "fold training must be the other nine folds")
        for tid in held:
            require(tid not in held_fold, "trial held out in more than one fold")
            held_fold[tid] = fid
        fold_map[fid] = row
    require(set(held_fold) == set(trials), "folds must hold out every trial exactly once")
    systems = plan.get("systems")
    require(isinstance(systems, dict) and set(systems) == set(SYSTEMS), "requires baseline and both information arms")
    model_map, exposure = {}, []
    for sid in SYSTEMS:
        system = systems[sid]
        require(isinstance(system, dict), "system must be an object")
        digest(system.get("vocoder_sha256"), "vocoder_sha256")
        resources = system.get("external_speech_resources")
        require(isinstance(resources, list), "declare external speech resources, even if empty")
        for resource in resources:
            require(isinstance(resource, dict), "speech resource must be an object")
            text(resource.get("resource_id"), "resource_id")
            digest(resource.get("sha256"), "speech resource sha256")
        exposure.append((system["vocoder_sha256"], json.dumps(resources, sort_keys=True)))
        models = system.get("models")
        require(isinstance(models, list) and len(models) == 50, "requires five modality models for each of ten folds")
        for model in models:
            require(isinstance(model, dict), "model must be an object")
            fid, signal = model.get("fold_id"), model.get("signal")
            require(isinstance(fid, str) and fid in fold_map and isinstance(signal, str) and signal in SIGNALS,
                    "unknown model fold or modality")
            key = (sid, signal, fid)
            require(key not in model_map, "duplicate model system/modality/fold")
            digest(model.get("decoder_sha256"), "decoder_sha256")
            train = ids(model.get("training_trial_ids"), "model training_trial_ids")
            require(train == set(fold_map[fid]["training_trial_ids"]), "model training differs from original fold")
            selection = ids(model.get("selection_trial_ids"), "selection_trial_ids", False)
            require(selection <= train, "held trial or unknown trial exposed to selection")
            model_map[key] = model
    require(len(set(exposure)) == 1, "all systems require matched vocoder and external speech exposure")
    return trials, fold_map, held_fold, model_map


def descriptive(values):
    return {**acoustic.summary(values), "sd_population": statistics.pstdev(values)}


def assess(plan, references, predictions, max_cells=2_000_000):
    trials, folds, held_fold, models = validate_plan(plan)
    require(isinstance(references, list), "reference must enumerate all trials")
    ref_map = {}
    for row in references:
        require(isinstance(row, dict), "reference row must be an object")
        tid = text(row.get("trial_id"), "reference trial_id")
        require(tid not in ref_map, "duplicate reference trial")
        ref_map[tid] = row
    require(set(ref_map) == set(trials), "reference must cover every control trial exactly")
    require(isinstance(predictions, dict) and set(predictions) == set(SYSTEMS), "prediction systems must be complete")
    pred_map = {}
    for sid in SYSTEMS:
        require(isinstance(predictions[sid], list), "system predictions must be a list")
        for row in predictions[sid]:
            require(isinstance(row, dict), "prediction row must be an object")
            tid, signal = row.get("trial_id"), row.get("signal")
            require(isinstance(tid, str) and tid in trials and isinstance(signal, str) and signal in SIGNALS,
                    "unknown predicted trial or modality")
            key = (sid, signal, tid)
            require(key not in pred_map, "duplicate prediction system/modality/trial")
            fid = held_fold[tid]
            require(row.get("fold_id") == fid, "prediction is not from the trial's held-out fold")
            require(row.get("decoder_sha256") == models[sid, signal, fid]["decoder_sha256"],
                    "prediction decoder does not match declared fold model")
            pred_map[key] = row
    require(len(pred_map) == 3 * 5 * 240, "predictions must cover all 240 trials and five modalities in every system")
    records, lookup = [], {}
    for sid in SYSTEMS:
        for signal in SIGNALS:
            for tid in sorted(trials):
                value = acoustic.score_trial(ref_map[tid], pred_map[sid, signal, tid], max_cells)
                records.append({"system": sid, "signal": signal, "trial_id": tid,
                                "original_trial_id": trials[tid]["original_trial_id"],
                                "session_id": trials[tid]["session_id"], "fold_id": held_fold[tid], **value})
                lookup[sid, signal, tid] = value["mean_band_pearson_r"]
    summaries = {sid: {signal: {
        "trial_weighted": descriptive([lookup[sid, signal, t] for t in sorted(trials)]),
        "per_fold": {f: descriptive([lookup[sid, signal, t] for t in sorted(trials) if held_fold[t] == f])
                     for f in sorted(folds)},
        "per_session": {s: descriptive([lookup[sid, signal, t] for t in sorted(trials) if trials[t]["session_id"] == s])
                        for s in sorted({r["session_id"] for r in trials.values()})},
    } for signal in SIGNALS} for sid in SYSTEMS}
    contrasts = {}
    for left, right in (("paper_data", "author_baseline"), ("paper_data_author_code", "author_baseline"),
                        ("paper_data_author_code", "paper_data")):
        contrast = {}
        for signal in SIGNALS:
            rows = [{"trial_id": t, "fold_id": held_fold[t], "session_id": trials[t]["session_id"],
                     "delta_r": lookup[left, signal, t] - lookup[right, signal, t]} for t in sorted(trials)]
            contrast[signal] = {"trial_weighted": descriptive([r["delta_r"] for r in rows]),
                                "per_fold": {f: descriptive([r["delta_r"] for r in rows if r["fold_id"] == f])
                                             for f in sorted(folds)}, "trials": rows}
        contrasts[left + "_minus_" + right] = contrast
    return {"schema_version": "voice-biosignal-assessment/v1", "task_id": acoustic.TASK_ID,
            "scope": "declared-complete-biosignal-secondary-panel", "scientific_qualification": "unknown",
            "authentic_population_verified": False, "declared_trials": len(trials), "declared_folds": len(folds),
            "original_support_sha256": plan["original_support_sha256"], "acoustic_profile": plan["acoustic_profile"],
            "feature_evaluator_sha256": ACOUSTIC_SHA256, "summaries": summaries, "trials": records,
            "descriptive_paired_contrasts": contrasts, "holds": HOLDS}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "reference", "prediction", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--max-dtw-cells", type=int, default=2_000_000)
    args = parser.parse_args(argv)
    try:
        paths = [Path(getattr(args, name)) for name in ("plan", "reference", "prediction")]
        output = Path(args.output)
        require(output.resolve() not in {p.resolve() for p in paths}, "output would overwrite input")
        raw = [p.read_bytes() for p in paths]
        result = assess(*(acoustic.parse_json(value) for value in raw), args.max_dtw_cells)
        result["input_sha256"] = {name: hashlib.sha256(value).hexdigest()
                                  for name, value in zip(("plan", "reference", "prediction"), raw)}
        with output.open("x") as handle:
            json.dump(result, handle, indent=2, allow_nan=False)
            handle.write("\n")
    except (ContractError, OSError, ValueError, TypeError, KeyError, OverflowError) as error:
        parser.exit(2, "biosignal assessment rejected: " + str(error) + "\n")


if __name__ == "__main__":
    main()
