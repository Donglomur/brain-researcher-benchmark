"""Validate and aggregate protected MindEye2 retrieval decisions for four subjects.

This standard-library component reads saved feature-scorer evidence. It does not
execute a model, verify feature provenance or establish the original training
condition. The reconstruction panel and Figure 5 comparison remain separate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import NormalDist, fmean
import sys

TASK = "PAPER-paper-method-032"
SUBJECTS = (1, 2, 5, 7)
DIRECTIONS = ("image_retrieval", "brain_retrieval")
SEMANTICS = {"image_retrieval": "brain_query_to_image_candidates",
             "brain_retrieval": "image_query_to_brain_candidates"}
CONTRACT_SHA256 = "97752be74ac2af84fbd8441f50e2f4e9ba1e2a518d0b90ec553f8d08d19890b0"
CODE_REVISION = "76a2609243ba1bacb450e47e3dc78de1f78a9c00"
DATA_REVISION = "26421f100e4c6012a35ecadb272a0ec1d999202d"
FEATURE_SPACE = "openclip:ViT-bigG-14:laion2b_s39b_b160k:256x1664-tokens"
INPUT_SCHEMA = "mindeye2-retrieval-cohort-input/v1"
ROUNDING_BOUND = 32 * sys.float_info.epsilon


def need(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def sha(value, name):
    need(type(value) is str and len(value) == 64
         and all(c in "0123456789abcdef" for c in value), name + ": canonical SHA256 required")
    return value


def ids(value, size, name):
    need(type(value) is list and len(value) == size
         and all(type(x) is str and x for x in value)
         and len(set(value)) == size, name + ": complete unique identities required")
    return value


def close(actual, expected, name):
    need(type(actual) in (int, float) and math.isfinite(actual)
         and math.isclose(actual, expected, rel_tol=0, abs_tol=ROUNDING_BOUND),
         name + ": inconsistent numerical summary")


def reference(ref):
    need(type(ref) is dict, "reference must be an object")
    for key, value in (("task_id", TASK), ("contract_sha256", CONTRACT_SHA256),
                       ("code_revision", CODE_REVISION), ("dataset_revision", DATA_REVISION),
                       ("feature_space", FEATURE_SPACE)):
        need(ref.get(key) == value, "unexpected reference " + key)
    need(type(ref.get("subject")) is int and ref["subject"] in SUBJECTS,
         "original subject 1, 2, 5 or 7 required")
    population = ids(ref.get("image_ids"), 1000, "reference population")
    pools = ref.get("retrieval_pools")
    need(type(pools) is list and len(pools) == 30, "exactly 30 retrieval pools required")
    allowed = set(population)
    for pool in pools:
        need(set(ids(pool, 300, "retrieval pool")) <= allowed,
             "pool identity outside the declared population")
    for key in ("image_features_sha256", "population_manifest_sha256", "feature_extraction_receipt_sha256"):
        sha(ref.get(key), key)
    return population, pools


def _summary(value, computed, name):
    need(type(value) is dict, name + ": metric summary required")
    draws = value.get("draw_values")
    need(type(draws) is list and len(draws) == 30, name + ": thirty draw values required")
    for actual, expected in zip(draws, computed):
        need(type(actual) in (int, float) and actual == expected,
             name + ": draw score does not match complete query decisions")
    mean = fmean(computed)
    sem = math.sqrt(fmean((x - mean) ** 2 for x in computed)) / math.sqrt(30)
    half = NormalDist().inv_cdf(.975) * sem
    close(value.get("mean"), mean, name + " mean")
    close(value.get("draw_sem"), sem, name + " draw SEM")
    interval = value.get("draw_normal_95_interval")
    need(type(interval) is list and len(interval) == 2, name + ": two interval endpoints required")
    close(interval[0], mean - half, name + " interval lower")
    close(interval[1], mean + half, name + " interval upper")
    need(value.get("uncertainty_unit") == "repeated retrieval subset; not independent subjects/images",
         "retrieval draws must retain their Monte Carlo uncertainty scope")
    # Retain the source scorer's supplied mean after verifying its floating
    # reduction against the integer-count-derived result. The tolerance here is
    # roundoff validation, not a scientific reproduction or improvement margin.
    return {"mean": value["mean"], "draw_values": list(computed),
            "recomputed_mean": mean}


def _subject(record):
    need(type(record) is dict and set(record) == {"reference", "result"},
         "each subject record requires exactly reference and result")
    ref, result = record["reference"], record["result"]
    population, pools = reference(ref)
    need(type(result) is dict, "scorer result must be an object")
    for key, expected in (("task_id", TASK), ("scope", "bounded_original_population_feature_retrieval"),
                          ("reference_manifest_digest", digest(ref)),
                          ("population_manifest_sha256", ref["population_manifest_sha256"]),
                          ("pool_digest", digest(pools))):
        need(result.get(key) == expected, "scorer result mismatch: " + key)
    need(type(result.get("subject")) is int and result["subject"] == ref["subject"]
         and type(result.get("n_images")) is int and result["n_images"] == 1000,
         "scorer result subject/population mismatch")
    sha(result.get("candidate_manifest_digest"), "candidate manifest digest")
    for key in ("scientific_qualification", "full_contract_complete", "native_parity_verified"):
        need(result.get(key) is False, "unqualified component flags must remain false")
    evidence = result.get("decision_evidence")
    need(type(evidence) is dict and evidence.get("schema") == "mindeye2-retrieval-query-evidence/v1",
         "complete protected query evidence required")
    need(sha(result.get("decision_evidence_digest"), "decision evidence digest") == digest(evidence),
         "query evidence digest mismatch")
    need(evidence.get("image_ids") == population and evidence.get("pool_digest") == digest(pools),
         "query evidence population/pool mismatch")
    need(evidence.get("direction_semantics") == SEMANTICS
         and evidence.get("tie_policy") == "reject_maximal_ties"
         and evidence.get("scope") == "protected_operator_feature_decisions_not_native_execution_attestation",
         "query evidence direction, tie or scope mismatch")
    draws = evidence.get("draws")
    need(type(draws) is list and len(draws) == 30, "all 30 query draws required")
    values = {key: [] for key in DIRECTIONS}
    for index, (draw, pool) in enumerate(zip(draws, pools)):
        need(type(draw) is dict and type(draw.get("draw_index_zero_based")) is int
             and draw["draw_index_zero_based"] == index and draw.get("candidate_ids") == pool,
             "ordered draw/pool commitment mismatch")
        directions = draw.get("directions")
        need(type(directions) is dict and set(directions) == set(DIRECTIONS),
             "both physical retrieval directions required")
        allowed = set(pool)
        for name in DIRECTIONS:
            decisions = directions[name]
            need(type(decisions) is list and len(decisions) == 300,
                 "all 300 query decisions required per direction/draw")
            correct = 0
            for expected_query, decision in zip(pool, decisions):
                need(type(decision) is dict and set(decision) == {"query_id", "predicted_id", "correct"},
                     "exact query decision fields required")
                need(decision["query_id"] == expected_query
                     and type(decision["predicted_id"]) is str and decision["predicted_id"] in allowed,
                     "query identity/order or predicted candidate mismatch")
                hit = decision["query_id"] == decision["predicted_id"]
                need(type(decision["correct"]) is bool and decision["correct"] == hit,
                     "correctness flag differs from query/predicted identity")
                correct += hit
            values[name].append(correct / 300)
    metrics = result.get("metrics")
    need(type(metrics) is dict and set(metrics) == set(DIRECTIONS), "both metric summaries required")
    return {"subject": ref["subject"], "reference_manifest_digest": digest(ref),
            "candidate_manifest_digest": result["candidate_manifest_digest"],
            "decision_evidence_digest": result["decision_evidence_digest"],
            "pool_digest": digest(pools),
            "metrics": {name: _summary(metrics[name], values[name], name) for name in DIRECTIONS}}


def aggregate(records):
    need(type(records) is list and len(records) == 4, "all four subject records required")
    subjects = [_subject(record) for record in records]
    need(sorted(row["subject"] for row in subjects) == list(SUBJECTS),
         "subjects 1, 2, 5, 7 exactly once required")
    common = set(records[0]["reference"]["image_ids"])
    need(all(set(record["reference"]["image_ids"]) == common for record in records),
         "four subjects must declare the same shared1000 stimulus set")
    by_subject = {row["subject"]: row for row in subjects}
    ordered = [by_subject[s] for s in SUBJECTS]
    return {"schema": "mindeye2-retrieval-cohort-result/v1", "task_id": TASK,
            "subjects": ordered, "shared_stimuli": 1000, "retrieval_queries_per_direction_per_subject": 9000,
            "metrics": {name: {"mean": fmean(row["metrics"][name]["mean"] for row in ordered),
                               "subject_values": [row["metrics"][name]["mean"] for row in ordered]}
                        for name in DIRECTIONS},
            "aggregation": "arithmetic mean of four subject means; no pooled interval",
            "condition_qualification": "training/adaptation exposure unresolved by feature evidence",
            "scientific_qualification": False, "full_contract_complete": False,
            "native_parity_verified": False, "reproduction": "unknown", "improvement": "unknown",
            "limits": ["Saved decision consistency does not attest feature generation or model execution.",
                       "Shared images and overlapping retrieval pools are dependent; no biological confidence interval or win decision is supplied.",
                       "One-hour exposure, original population custody, checkpoints and native numerical parity require independent qualification.",
                       "The complete reconstruction panel and Figure5 comparison remain outside this retrieval component."]}


def compare(candidate_records, baseline_records):
    candidate = aggregate(candidate_records)
    baseline = aggregate(baseline_records)
    deltas = {name: [] for name in DIRECTIONS}
    for new, old in zip(candidate["subjects"], baseline["subjects"]):
        need(new["subject"] == old["subject"]
             and new["reference_manifest_digest"] == old["reference_manifest_digest"]
             and new["pool_digest"] == old["pool_digest"],
             "paired cohorts require identical subject-specific references and retrieval pools")
        for name in DIRECTIONS:
            deltas[name].append(new["metrics"][name]["mean"] - old["metrics"][name]["mean"])
    return {"schema": "mindeye2-retrieval-cohort-comparison/v1", "task_id": TASK,
            "candidate": candidate, "baseline": baseline,
            "candidate_minus_baseline": {
                name: {"mean_difference": candidate["metrics"][name]["mean"] - baseline["metrics"][name]["mean"],
                       "subject_differences": deltas[name]} for name in DIRECTIONS},
            "scientific_improvement_claim_supported": False,
            "matched_exposure_or_compute_verified": False}


def _object(pairs):
    value = {}
    for key, item in pairs:
        need(key not in value, "duplicate JSON key")
        value[key] = item
    return value


def load(path, expected, limit):
    sha(expected, "cohort file SHA256")
    path = Path(path)
    need(type(limit) is int and limit > 0 and path.is_file() and path.stat().st_size <= limit,
         "cohort input exceeds the shared byte allowance or is not an ordinary file")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    need(len(raw) <= limit and hashlib.sha256(raw).hexdigest() == expected, "cohort input SHA256/size mismatch")
    packet = json.loads(raw, object_pairs_hook=_object,
                        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    need(type(packet) is dict and set(packet) == {"schema", "subjects"} and packet["schema"] == INPUT_SCHEMA,
         "exact cohort input schema and subjects required")
    return packet["subjects"], len(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--candidate-sha256", required=True)
    parser.add_argument("--baseline")
    parser.add_argument("--baseline-sha256")
    parser.add_argument("--max-input-bytes", type=int, required=True)
    args = parser.parse_args(argv)
    need(bool(args.baseline) == bool(args.baseline_sha256), "baseline path and SHA256 must be supplied together")
    candidate, used = load(args.candidate, args.candidate_sha256, args.max_input_bytes)
    if args.baseline:
        baseline, more = load(args.baseline, args.baseline_sha256, args.max_input_bytes - used)
        result = compare(candidate, baseline)
        used += more
    else:
        result = aggregate(candidate)
    result["input_read_bytes"] = used
    result["candidate_input_sha256"] = args.candidate_sha256
    if args.baseline:
        result["baseline_input_sha256"] = args.baseline_sha256
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
