#!/usr/bin/env python3
"""Matched seven-subject PopT/BrainBERT RMS evaluator; no model execution."""
from __future__ import annotations
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

TASK = "PAPER-paper-method-replacement-006"
REVISION = "d237755bbdea123c60bface0cecbb48bab6f42de"
PROFILE = "prospective-rms-matched-v1"
TRIALS = {"sub_1": "trial001", "sub_2": "trial006", "sub_3": "trial000",
          "sub_4": "trial000", "sub_6": "trial004", "sub_7": "trial000", "sub_10": "trial000"}
MOVIES = {"sub_1": "the_martian", "sub_2": "aquaman", "sub_3": "cars_2",
          "sub_4": "shrek_3", "sub_6": "coraline", "sub_7": "cars_2", "sub_10": "cars_2"}
COUNTS = (1, 10, 50, 90)  # prospective anchor grid, not the exact Figure 3 grid
RESOURCE_KEYS = ("brainbert_checkpoint_sha256", "feature_table_sha256", "preprocessing_sha256")
HOLDS = ["Authentic full word/subject/channel population and input provenance are not independently verified.",
         "BrainBERT archive member, content hash, and weight redistribution rights remain unqualified.",
         "Native model/checkpoint execution, validation-only model selection and emitted row order need independent audit.",
         "Historical random 80/10/10 splits are not reproduced by this prospective support-disjoint profile.",
         "Historical channel-ranking fit population and exact figure-specific references/tolerances remain unresolved.",
         "PopT and BrainBERT pretraining exposure, movie overlap, and BaRISTA/dataset-project contamination remain unqualified.",
         "Generated controls do not establish scientific qualification, competence, reproduction, or improvement."]

class ContractError(ValueError):
    """An input violates the fixed evaluation profile."""

def require(ok, message):
    if not ok:
        raise ContractError(message)

def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

def is_sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)

def number(value, name):
    require(type(value) in (int, float) and math.isfinite(value), f"{name} must be finite numeric")
    return float(value)

def identifier(value, name):
    require(isinstance(value, str) and bool(value.strip()), f"{name} must be nonempty text")
    return value

def rms_quartile_labels(rows):
    """Source floor-index lower/upper quartiles, with ambiguous cutoff ties rejected."""
    require(len(rows) >= 4, "at least four eligible words per session are required")
    ordered = sorted(rows, key=lambda r: (r["rms"], r["id"]))
    lo, hi = len(rows) // 4, (3 * len(rows)) // 4
    require(ordered[lo - 1]["rms"] != ordered[lo]["rms"], "ambiguous lower-quartile boundary tie")
    require(ordered[hi - 1]["rms"] != ordered[hi]["rms"], "ambiguous upper-quartile boundary tie")
    return {r["id"]: (0 if i < lo else 1 if i >= hi else None) for i, r in enumerate(ordered)}

def _check_support(rows):
    """Reject intersecting half-open neural supports in different splits, O(n log n)."""
    max_end = {s: -math.inf for s in ("train", "validation", "test")}
    for row in sorted(rows, key=lambda r: (r["start_s"], r["end_s"], r["id"])):
        for split, end in max_end.items():
            require(split == row["split"] or end <= row["start_s"], "cross-split neural support overlap")
        max_end[row["split"]] = max(max_end[row["split"]], row["end_s"])

def freeze(plan):
    """Freeze full submitted word roster, source RMS labels, saved splits and nested ensembles."""
    require(isinstance(plan, dict), "plan must be an object")
    require(plan.get("schema_version") == 1, "schema_version must be 1")
    require(plan.get("profile") == PROFILE, "unsupported profile")
    require(plan.get("source_revision") == REVISION, "wrong upstream source revision")
    require(plan.get("endpoint") == "rms", "this package evaluates RMS volume only")
    require(plan.get("support_units") == "seconds", "neural support units must be seconds")
    resources = plan.get("shared_resources", {})
    require(set(resources) == set(RESOURCE_KEYS), "shared resource hashes are incomplete or unexpected")
    require(all(is_sha(v) for v in resources.values()), "shared resources require SHA256 digests")
    for key in ("population_manifest_sha256", "saved_split_file_sha256", "pretraining_exposure_manifest_sha256"):
        require(is_sha(plan.get(key)), f"{key} is required")
    words = plan.get("words")
    require(isinstance(words, list) and words, "words must contain the full eligible submitted roster")
    groups, seen = defaultdict(list), set()
    clean = []
    for row in words:
        require(isinstance(row, dict), "each word must be an object")
        r = {k: row.get(k) for k in ("id", "subject", "trial", "movie", "start_s", "end_s", "split", "rms")}
        identifier(r["id"], "word id")
        require(r["id"] not in seen, "duplicate word id")
        seen.add(r["id"])
        subject = r["subject"]
        require(subject in TRIALS and r["trial"] == TRIALS[subject], "subject/trial outside official seven-subject roster")
        require(r["movie"] == MOVIES[subject], "movie identity does not match paper held-out movie")
        require(r["split"] in ("train", "validation", "test"), "saved split must be train, validation, or test")
        r["start_s"], r["end_s"] = number(r["start_s"], "start_s"), number(r["end_s"], "end_s")
        require(r["start_s"] >= 0 and r["end_s"] > r["start_s"], "invalid half-open neural support")
        r["rms"] = number(r["rms"], "RMS")
        require(r["rms"] >= 0, "RMS cannot be negative")
        groups[subject].append(r)
        clean.append(r)
    require(set(groups) == set(TRIALS), "complete official seven-subject population is required")
    for subject, rows in groups.items():
        _check_support(rows)
        labels = rms_quartile_labels(rows)
        for r in rows:
            r["label_high_rms"] = labels[r["id"]]
        for split in ("train", "validation", "test"):
            require({r["label_high_rms"] for r in rows if r["split"] == split and r["label_high_rms"] is not None} == {0, 1},
                    f"{subject}/{split} requires both retained RMS classes")
    rankings = plan.get("channel_rankings", {})
    require(set(rankings) == set(TRIALS), "channel rankings must cover all seven subjects")
    ensembles = []
    for subject in sorted(TRIALS):
        ranking = rankings[subject]
        channels = ranking.get("channels", [])
        require(isinstance(channels, list) and len(channels) >= max(COUNTS), "at least 90 submitted ranked channels required per subject")
        require(all(isinstance(c, str) and c.strip() for c in channels) and len(set(channels)) == len(channels), "channel IDs must be unique nonempty strings")
        require(ranking.get("selection_rule") == "training_only_linear_decodability", "channel ranking must use training-only linear decodability")
        require(is_sha(ranking.get("ranking_evidence_sha256")), "ranking evidence SHA256 required")
        require(is_sha(ranking.get("eligibility_evidence_sha256")), "submitted channel eligibility evidence SHA256 required")
        fit_ids = ranking.get("fit_word_ids")
        training_ids = {r["id"] for r in groups[subject] if r["split"] == "train" and r["label_high_rms"] is not None}
        require(isinstance(fit_ids, list) and len(set(fit_ids)) == len(fit_ids) and set(fit_ids) == training_ids, "ranking fit IDs must equal all retained training words")
        feature_order = ranking.get("feature_channel_order")
        require(isinstance(feature_order, list) and len(feature_order) == len(set(feature_order))
                and set(feature_order) == set(channels), "feature channel order must cover the submitted ranked channel set exactly")
        require(is_sha(ranking.get("channel_order_evidence_sha256")), "feature channel-order evidence SHA256 required")
        for count in COUNTS:
            selected = set(channels[:count])
            ensembles.append({"subject": subject, "electrode_count": count,
                              "channels": [channel for channel in feature_order if channel in selected]})
    result = {"schema_version": 1, "task_id": TASK, "profile": PROFILE, "source_revision": REVISION,
              "endpoint": "rms", "shared_resources": resources,
              "population_manifest_sha256": plan["population_manifest_sha256"],
              "saved_split_file_sha256": plan["saved_split_file_sha256"],
              "pretraining_exposure_manifest_sha256": plan["pretraining_exposure_manifest_sha256"],
              "words": sorted(clean, key=lambda r: r["id"]), "channel_rankings": rankings, "ensembles": ensembles,
              "policy": {"quartiles": "session_floor_rank_extremes_reject_cutoff_ties", "channel_counts": list(COUNTS),
                         "ranking": "training_only_linear_decodability", "ensemble_order": "submitted_feature_channel_order", "support": "cross_split_disjoint_half_open_seconds",
                         "block_seconds": 60, "threshold_high_rms": "probability_strictly_greater_than_0.5"}}
    result["reference_sha256"] = canonical_sha(result)
    return result

def validate_reference(reference):
    require(isinstance(reference, dict), "reference must be an object")
    body = dict(reference)
    expected = body.pop("reference_sha256", None)
    require(is_sha(expected) and canonical_sha(body) == expected, "reference content hash mismatch")
    plan = dict(reference)
    plan["support_units"] = "seconds"
    require(freeze(plan) == reference, "reference is not a canonical frozen RMS plan")

def auc(labels, probabilities):
    """Mann–Whitney ROC-AUC with half credit for equal scores, O(n log n)."""
    require(len(labels) == len(probabilities) and bool(labels), "metric arrays must be nonempty and aligned")
    require(all(type(y) is int and y in (0, 1) for y in labels), "binary integer labels required")
    require(all(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1 for p in probabilities), "finite probabilities in [0,1] required")
    positives = sum(labels)
    negatives = len(labels) - positives
    if not positives or not negatives:
        return None
    pairs = sorted(zip(probabilities, labels))
    neg_below, wins, i = 0, 0.0, 0
    while i < len(pairs):
        j = i + 1
        while j < len(pairs) and pairs[j][0] == pairs[i][0]:
            j += 1
        pos_tied = sum(y for _, y in pairs[i:j])
        neg_tied = j - i - pos_tied
        wins += pos_tied * (neg_below + 0.5 * neg_tied)
        neg_below += neg_tied
        i = j
    return wins / (positives * negatives)

def f1(labels, predictions):
    tp = sum(y == 1 and p == 1 for y, p in zip(labels, predictions))
    fp = sum(y == 0 and p == 1 for y, p in zip(labels, predictions))
    fn = sum(y == 1 and p == 0 for y, p in zip(labels, predictions))
    return 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0

def _metrics(labels, probabilities, high_index):
    # AUC is invariant to jointly complementing source labels and probabilities.
    native_labels = [y if high_index == 1 else 1 - y for y in labels]
    native_probs = [p if high_index == 1 else 1 - p for p in probabilities]
    return {"roc_auc": auc(labels, probabilities),
            "f1_high_rms": f1(labels, [int(p > 0.5) for p in probabilities]),
            "f1_native_index1": f1(native_labels, [int(p > 0.5) for p in native_probs])}

def _bind(reference, prediction, arm):
    require(isinstance(prediction, dict), "prediction must be an object")
    require(prediction.get("reference_sha256") == reference["reference_sha256"], "prediction reference hash mismatch")
    require(prediction.get("arm") == arm, "wrong comparison arm")
    require(arm in ("candidate", "baseline"), "arm must be candidate or baseline")
    allowed = ("pretrained_popt",) if arm == "candidate" else ("linear_concatenation", "deep_nn_concatenation")
    require(prediction.get("method") in allowed, "unsupported PopT/BrainBERT aggregation method")
    require(prediction.get("shared_resources") == reference["shared_resources"], "unmatched BrainBERT features/checkpoint/preprocessing")
    require(prediction.get("saved_split_file_sha256") == reference["saved_split_file_sha256"], "unmatched saved split file")
    require(prediction.get("pretraining_exposure_manifest_sha256") == reference["pretraining_exposure_manifest_sha256"], "unmatched declared exposure ledger")
    require(is_sha(prediction.get("model_artifact_sha256")), "model artifact hash required")
    require(prediction.get("selection_split") == "validation", "model selection must be validation-only")
    require(prediction.get("probability_semantics") == "canonical_high_rms", "probabilities must be explicitly canonicalized to high RMS")
    high_indices = prediction.get("native_high_rms_index", {})
    require(set(high_indices) == set(TRIALS), "explicit native high-RMS class index required for each subject/count run")
    for subject in TRIALS:
        mapping = high_indices[subject]
        require(isinstance(mapping, dict) and set(mapping) == {str(c) for c in COUNTS}
                and all(type(x) is int and x in (0, 1) for x in mapping.values()),
                "native high-RMS class index must cover every subject/count run")
    test_rows = {r["id"]: r for r in reference["words"] if r["split"] == "test" and r["label_high_rms"] is not None}
    ensemble_map = {(r["subject"], r["electrode_count"]): r["channels"] for r in reference["ensembles"]}
    wanted = {(row_id, count) for row_id in test_rows for count in COUNTS}
    got = {}
    rows = prediction.get("predictions")
    require(isinstance(rows, list), "predictions must be a list")
    for row in rows:
        require(isinstance(row, dict), "each prediction must be an object")
        key = (row.get("word_id"), row.get("electrode_count"))
        require(type(key[1]) is int and key in wanted, "prediction outside retained test population/ensemble grid")
        require(key not in got, "duplicate prediction")
        subject = test_rows[key[0]]["subject"]
        require(row.get("channels") == ensemble_map[(subject, key[1])], "electrode membership/order differs from frozen ensemble")
        p = number(row.get("probability_high_rms"), "probability_high_rms")
        require(0 <= p <= 1, "probability outside [0,1]")
        got[key] = p
    require(set(got) == wanted, "missing test words/electrode counts/subjects")
    return got, high_indices

def _summary(values):
    return {"n_subjects": len(values), "mean": statistics.mean(values),
            "sem_descriptive": statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else None}

def _percentile(values, q):
    ordered = sorted(values)
    at = (len(ordered) - 1) * q
    lo, hi = math.floor(at), math.ceil(at)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (at - lo)

def _blocked_ci(rows, candidate, baseline, replicates, seed):
    # Prospective 60-second elapsed-time bins. Merge bins crossed by any window;
    # no neural support is divided between resampling units.
    bins = defaultdict(list)
    intervals = []
    for i, row in enumerate(rows):
        first = math.floor(row["start_s"] / 60)
        last = math.ceil(row["end_s"] / 60) - 1
        intervals.append((first, last, i))
    intervals.sort()
    group, stop = -1, -1
    for first, last, i in intervals:
        if first > stop:
            group += 1
        stop = max(stop, last)
        bins[group].append(i)
    base = {"block_count": len(bins), "requested_replicates": replicates, "valid_replicates": 0,
            "undefined_replicates": 0, "candidate_auc_95": None, "baseline_auc_95": None, "paired_auc_delta_95": None}
    if len(bins) < 2:
        base["status"] = "insufficient_temporal_blocks"
        return base
    rng = random.Random(seed)
    blocks = list(bins.values())
    cs, bs, ds = [], [], []
    for _ in range(replicates):
        idx = [i for _ in blocks for i in rng.choice(blocks)]
        labels = [rows[i]["label_high_rms"] for i in idx]
        ca, ba = auc(labels, [candidate[i] for i in idx]), auc(labels, [baseline[i] for i in idx])
        if ca is None or ba is None:
            base["undefined_replicates"] += 1
        else:
            cs.append(ca); bs.append(ba); ds.append(ca - ba)
    base["valid_replicates"] = len(ds)
    base["status"] = "conditional_on_two_class_replicates" if ds else "all_replicates_undefined"
    for name, values in (("candidate_auc_95", cs), ("baseline_auc_95", bs), ("paired_auc_delta_95", ds)):
        if values:
            base[name] = [_percentile(values, 0.025), _percentile(values, 0.975)]
    return base

def evaluate(reference, candidate, baseline, replicates=1000, seed=20261117):
    validate_reference(reference)
    require(type(replicates) is int and 20 <= replicates <= 10000, "replicates must be an integer from 20 to 10000")
    require(type(seed) is int, "seed must be an integer")
    cp, ci = _bind(reference, candidate, "candidate")
    bp, bi = _bind(reference, baseline, "baseline")
    results = []
    for subject in sorted(TRIALS):
        rows = sorted((r for r in reference["words"] if r["subject"] == subject and r["split"] == "test" and r["label_high_rms"] is not None), key=lambda r: (r["start_s"], r["id"]))
        for count in COUNTS:
            labels = [r["label_high_rms"] for r in rows]
            c = [cp[(r["id"], count)] for r in rows]
            b = [bp[(r["id"], count)] for r in rows]
            cm, bm = _metrics(labels, c, ci[subject][str(count)]), _metrics(labels, b, bi[subject][str(count)])
            local_seed = int(hashlib.sha256(f"{seed}:{subject}:{count}".encode()).hexdigest()[:16], 16)
            results.append({"subject": subject, "trial": TRIALS[subject], "movie": MOVIES[subject],
                            "electrode_count": count, "n_test": len(rows), "n_positive": sum(labels),
                            "candidate": cm, "baseline": bm, "paired_auc_delta": cm["roc_auc"] - bm["roc_auc"],
                            "paired_f1_high_rms_delta": cm["f1_high_rms"] - bm["f1_high_rms"],
                            "native_high_rms_indices": {"candidate": ci[subject][str(count)], "baseline": bi[subject][str(count)]},
                            "temporal_block_bootstrap": _blocked_ci(rows, c, b, replicates, local_seed)})
    summaries = []
    for count in COUNTS:
        rs = [r for r in results if r["electrode_count"] == count]
        summaries.append({"electrode_count": count,
                          "candidate_auc": _summary([r["candidate"]["roc_auc"] for r in rs]),
                          "baseline_auc": _summary([r["baseline"]["roc_auc"] for r in rs]),
                          "paired_auc_delta": _summary([r["paired_auc_delta"] for r in rs]),
                          "paired_f1_high_rms_delta": _summary([r["paired_f1_high_rms_delta"] for r in rs])})
    scaling = []
    for count in COUNTS[1:]:
        for arm in ("candidate", "baseline"):
            differences = []
            for subject in sorted(TRIALS):
                current = next(r for r in results if r["subject"] == subject and r["electrode_count"] == count)
                one = next(r for r in results if r["subject"] == subject and r["electrode_count"] == 1)
                differences.append(current[arm]["roc_auc"] - one[arm]["roc_auc"])
                current[f"{arm}_auc_change_from_1"] = differences[-1]
            scaling.append({"arm": arm, "electrode_count": count, "auc_change_from_1": _summary(differences)})
    return {"schema_version": 1, "task_id": TASK, "profile": PROFILE, "reference_sha256": reference["reference_sha256"],
            "classification": "tested_construction_evaluator_no_native_reproduction", "scientific_qualification": "unknown",
            "full_contract_complete": False, "empirical_reference_established": False,
            "estimand": "equal_subject_mean_paired_ROC_AUC_difference_at_each_frozen_nested_electrode_count",
            "per_subject": results, "subject_macro": summaries, "electrode_scaling": scaling,
            "comparison_provenance": {arm: {"method": pred["method"], "model_artifact_sha256": pred["model_artifact_sha256"],
                                            "prediction_content_sha256": canonical_sha(pred),
                                            "native_high_rms_index": pred["native_high_rms_index"],
                                            "native_binding_sha256": pred.get("native_binding_sha256"),
                                            "native_outputs_sha256": pred.get("native_outputs_sha256"),
                                            "shared_resources": pred["shared_resources"],
                                            "saved_split_file_sha256": pred["saved_split_file_sha256"],
                                            "pretraining_exposure_manifest_sha256": pred["pretraining_exposure_manifest_sha256"]}
                                      for arm, pred in (("candidate", candidate), ("baseline", baseline))},
            "dependence": {"shared_test_movie": {"cars_2": ["sub_3", "sub_7", "sub_10"]},
                           "sem_is_descriptive": True, "subject_mean_has_no_claim_of_independent_movies": True},
            "bootstrap_policy": {"seconds": 60, "seed": seed, "replicates": replicates,
                                 "scope": "paired_within_subject_temporal_blocks_conditional_on_this_saved_test_population",
                                 "limitation": "60 seconds is prospective; block-length sensitivity and authentic autocorrelation audit remain required."},
            "holds": HOLDS}

def bind_native(reference, binding, native_outputs):
    """Bind author predicts/labels arrays to audited test order and per-run class maps."""
    validate_reference(reference)
    require(isinstance(native_outputs, dict), "native outputs must be keyed by subject/count")
    runs = binding.get("runs")
    require(isinstance(runs, list), "binding must list all subject/count runs")
    expected_runs = {f"{subject}/{count}" for subject in TRIALS for count in COUNTS}
    require(set(native_outputs) == expected_runs, "native outputs must cover the complete run grid")
    output = {k: binding.get(k) for k in ("reference_sha256", "arm", "method", "shared_resources",
              "saved_split_file_sha256", "pretraining_exposure_manifest_sha256", "selection_split")}
    output.update({"probability_semantics": "canonical_high_rms", "predictions": [],
                   "native_high_rms_index": {subject: {} for subject in TRIALS},
                   "native_binding_sha256": canonical_sha(binding), "native_outputs_sha256": canonical_sha(native_outputs)})
    seen, artifacts = set(), []
    ensembles = {(e["subject"], e["electrode_count"]): e["channels"] for e in reference["ensembles"]}
    for run in runs:
        subject, count = run.get("subject"), run.get("electrode_count")
        key = f"{subject}/{count}"
        require(type(count) is int and key in expected_runs and key not in seen, "invalid or duplicate native run")
        seen.add(key)
        require(run.get("channels") == ensembles[(subject, count)], "native channel membership/order differs from frozen ensemble")
        require(run.get("channel_order_evidence_sha256") == reference["channel_rankings"][subject]["channel_order_evidence_sha256"],
                "native feature channel-order evidence differs from frozen reference")
        high_index = run.get("high_rms_index")
        require(type(high_index) is int and high_index in (0, 1), "native high RMS index must be 0 or 1")
        require(is_sha(run.get("model_sha256")) and is_sha(run.get("order_evidence_sha256")), "model/order evidence SHA256 required")
        truth = {r["id"]: r["label_high_rms"] for r in reference["words"]
                 if r["subject"] == subject and r["split"] == "test" and r["label_high_rms"] is not None}
        order = run.get("ordered_word_ids")
        require(isinstance(order, list) and len(order) == len(set(order)) and set(order) == set(truth), "native order must exactly cover subject test words")
        native = native_outputs[key]
        require(isinstance(native, dict) and isinstance(native.get("predicts"), list) and isinstance(native.get("labels"), list), "native predicts/labels arrays required")
        require(len(native["predicts"]) == len(native["labels"]) == len(order), "native arrays/order length mismatch")
        native_probabilities = [number(p, "native probability") for p in native["predicts"]]
        require(all(0 <= p <= 1 for p in native_probabilities), "native probability outside [0,1]")
        if high_index == 0:
            complements = [1 - p for p in native_probabilities]
            require(len(set(complements)) == len(set(native_probabilities)), "floating-point class inversion collapses distinct scores")
            require(all((q > 0.5) == (p < 0.5) for p, q in zip(native_probabilities, complements)),
                    "floating-point class inversion changes threshold classification")
        for word_id, probability, label in zip(order, native["predicts"], native["labels"]):
            require(type(label) is int and label in (0, 1), "native labels must be integer class indices")
            expected = high_index if truth[word_id] else 1 - high_index
            require(label == expected, "native labels disagree with bound RMS truth/order/class map")
            probability = number(probability, "native probability")
            require(0 <= probability <= 1, "native probability outside [0,1]")
            output["predictions"].append({"word_id": word_id, "electrode_count": count,
                "channels": ensembles[(subject, count)],
                "probability_high_rms": probability if high_index == 1 else 1 - probability})
        output["native_high_rms_index"][subject][str(count)] = high_index
        artifacts.append({"run": key, "model_sha256": run["model_sha256"], "order_evidence_sha256": run["order_evidence_sha256"], "channels": run["channels"], "channel_order_evidence_sha256": run["channel_order_evidence_sha256"]})
    require(seen == expected_runs, "incomplete native run binding")
    output["model_artifact_sha256"] = canonical_sha(sorted(artifacts, key=lambda r: r["run"]))
    _bind(reference, output, output["arm"])
    return output

def submission_interface(reference):
    """Export only permitted prediction coordinates; omit all RMS values and labels."""
    validate_reference(reference)
    return {"schema_version": 1, "task_id": TASK, "profile": PROFILE,
            "reference_sha256": reference["reference_sha256"], "endpoint": "rms",
            "shared_resources": reference["shared_resources"],
            "saved_split_file_sha256": reference["saved_split_file_sha256"],
            "pretraining_exposure_manifest_sha256": reference["pretraining_exposure_manifest_sha256"],
            "ensembles": reference["ensembles"],
            "test_words": [{k: row[k] for k in ("id", "subject", "trial", "movie", "start_s", "end_s")}
                           for row in reference["words"] if row["split"] == "test" and row["label_high_rms"] is not None],
            "restriction": "No private labels/RMS, operator verifier or cross-attempt history may be released in candidate packets."}

def read_json(path):
    def reject_constant(value):
        raise ContractError(f"nonfinite JSON constant {value}")
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key {key}")
            result[key] = value
        return result
    with open(path, encoding="utf-8") as handle:
        return json.load(handle, parse_constant=reject_constant, object_pairs_hook=unique_object)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    freeze_parser = sub.add_parser("freeze")
    freeze_parser.add_argument("plan")
    freeze_parser.add_argument("output")
    bind_parser = sub.add_parser("bind-native")
    bind_parser.add_argument("reference")
    bind_parser.add_argument("binding")
    bind_parser.add_argument("native_outputs")
    bind_parser.add_argument("output")
    interface_parser = sub.add_parser("interface")
    interface_parser.add_argument("reference")
    interface_parser.add_argument("output")
    score_parser = sub.add_parser("score")
    score_parser.add_argument("reference")
    score_parser.add_argument("candidate")
    score_parser.add_argument("baseline")
    score_parser.add_argument("output")
    score_parser.add_argument("--replicates", type=int, default=1000)
    score_parser.add_argument("--seed", type=int, default=20261117)
    args = parser.parse_args()
    try:
        if args.command == "freeze":
            result = freeze(read_json(args.plan))
        elif args.command == "bind-native":
            result = bind_native(read_json(args.reference), read_json(args.binding), read_json(args.native_outputs))
        elif args.command == "interface":
            result = submission_interface(read_json(args.reference))
        else:
            result = evaluate(read_json(args.reference), read_json(args.candidate), read_json(args.baseline), args.replicates, args.seed)
        Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    except (ContractError, KeyError, TypeError, json.JSONDecodeError) as error:
        parser.exit(2, f"invalid input: {error}\n")

if __name__ == "__main__":
    main()
