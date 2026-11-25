"""Score original Table 10 decoder incidence beside the complete NEDS panel.

Operator-only JSON component; no source model execution or provenance attestation.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import math
from pathlib import Path
import json

METHODS = ("RRR", "NDT2", "POYO+")
BRIDGE_SHA256 = "51f023b92851520bff34120f8909a90cb12b5427adb7984cc83b1d05330f34ad"
FIELDS = ("choice", "block", "wheel", "whisker")
ENDPOINTS = ("choice:accuracy", "block:accuracy", "wheel:r2", "whisker:r2")


def load_bridge(implementations=None):
    directory = Path(implementations) if implementations else Path(__file__).resolve().parent.parent
    path = directory / "native-output-bridge-v1" / "native_output_bridge.py"
    if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != BRIDGE_SHA256:
        raise ValueError("regular pinned native output bridge required")
    spec = importlib.util.spec_from_file_location("neds_table10_bridge", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, directory / "initial-evaluator-v1"


def score_comparators(bundle, export, *, implementations=None):
    """Require all three original decoder roles on all ten held-out sessions.

    Raw-label predictions deliberately do not guess the native output layout of
    any comparator. The producer must recover and declare the exact trial order.
    """
    bridge, evaluator_directory = load_bridge(implementations)
    evaluator = bridge.load_evaluator(evaluator_directory)
    sessions = evaluator.validate_bundle(bundle, engineering_subset=False)
    roster = evaluator.load_roster()
    bridge.exact_fields(export, {"schema", "source_commit", "evidence_kind", "records"}, "comparator export")
    bridge.require(export["schema"] == "neds-table10-decoder-export/v1" and
                   export["source_commit"] == bridge.COMMIT, "comparator schema/source mismatch")
    bridge.require(export["evidence_kind"] == bundle["evidence_kind"], "comparator evidence-kind mismatch")
    expected = {(eid, method) for eid in roster["heldout_eids"] for method in METHODS}
    bridge.require(type(export["records"]) is list and len(export["records"]) == len(expected),
                   "all 30 original held-out comparator records required")
    indexed = {}
    for row in export["records"]:
        bridge.exact_fields(row, bridge.RECEIPT_METADATA | {"predictions"}, "comparator record")
        bridge.require(type(row["eid"]) is str and type(row["method"]) is str, "string EID/method required")
        key = (row["eid"], row["method"])
        bridge.require(key in expected and key not in indexed, "unknown or duplicate held-out comparator")
        session = sessions[row["eid"]]
        for field, values in (("trial_ids", session["test"]["trial_ids"]),
                              ("unit_ids", session["unit_ids"]),
                              ("fit_trial_ids", session["train"]["trial_ids"]),
                              ("validation_trial_ids", session["validation"]["trial_ids"])):
            bridge.require(row[field] == values, "comparator identity mismatch: " + field)
        pretraining = row["pretrained_eids"]
        bridge.require(type(pretraining) is list and all(type(x) is str for x in pretraining) and
                       len(pretraining) == 74 and set(pretraining) == set(roster["training_eids"]),
                       "Table 10 requires all 74 pretraining EIDs without duplicates")
        bridge.require(type(row["budget_contract"]) is str and bool(row["budget_contract"]),
                       "comparator resource declaration required")
        bridge.require(row["packet_sha256"] == {"decode_all": evaluator.digest(
            evaluator.input_packet(session, "test", "decode_all"))}, "comparator decoding packet mismatch")
        predictions = row["predictions"]
        bridge.exact_fields(predictions, FIELDS, "decoder predictions (no encoding cells)")
        scores, endpoints = {}, {}
        for field, endpoint in zip(FIELDS, ENDPOINTS):
            bridge.numeric_tree(predictions[field], field)
            rank = 1 if field in evaluator.CLASSES else 2
            actual = evaluator.array(predictions[field], field, rank)
            shape = (len(session["test"]["trial_ids"]),) + (() if rank == 1 else (100,))
            bridge.require(actual.shape == shape, field + ": complete ordered trial/time shape required")
            if rank == 1:
                scores[field] = evaluator.classification(session["test"][field], predictions[field], field)
                endpoints[endpoint] = scores[field]["accuracy"]
            else:
                scores[field] = evaluator.r_squared(session["test"][field], predictions[field])
                endpoints[endpoint] = scores[field]["r2"]
        indexed[key] = {"eid": row["eid"], "method": row["method"], "metrics": scores,
                        "endpoints": endpoints,
                        "declared_exposure_and_budget": {name: bridge.json_copy(row[name]) for name in
                            ("fit_trial_ids", "validation_trial_ids", "pretrained_eids", "budget_contract")}}
    rows = [indexed[(eid, method)] for eid in roster["heldout_eids"] for method in METHODS]
    means = {method: {endpoint: finite_mean([indexed[(eid, method)]["endpoints"][endpoint]
                                           for eid in roster["heldout_eids"]])
                      for endpoint in ENDPOINTS} for method in METHODS}
    return {"schema": "neds-table10-decoder-scores/v1", "source_commit": bridge.COMMIT,
            "bundle_sha256": evaluator.digest(bundle), "export_sha256": evaluator.digest(export),
            "evidence_kind": bundle["evidence_kind"], "session_results": rows, "session_macro": means,
            "coverage": {"required_operator_sessions": 84, "heldout_sessions": 10,
                         "comparator_records": 30, "decoding_cells": 120, "encoding_cells": 0},
            "scientific_qualification": "unknown", "readiness_promoted": False,
            "limitations": ["producer_identity_and_native_output_provenance_unqualified",
                            "resource_declarations_not_measured_or_required_equal_across_author_methods",
                            "SEM_historical_convention_and_animal_join_unresolved",
                            "no_joint_superiority_policy_or_scientific_result"]}


def finite_mean(values):
    # Scaling first avoids overflow for representable means of extreme R2 values.
    result = math.fsum(value / len(values) for value in values)
    if not math.isfinite(result):
        raise ValueError("session aggregate exceeds finite numeric range")
    return result


def evaluate_panel(bundle, paired_export, comparator_export, methods, *, implementations=None, draws=1000, seed=0):
    """Keep all 84 paired sessions/nine endpoints, then add actual decoder cells."""
    bridge, evaluator_directory = load_bridge(implementations)
    bridge.require(not set(methods).intersection(METHODS), "paired method names collide with comparator roles")
    comparators = score_comparators(bundle, comparator_export, implementations=implementations)
    paired = bridge.evaluate_export(bundle, paired_export, methods, evaluator_directory=evaluator_directory,
                                    draws=draws, seed=seed)
    evaluator = bridge.load_evaluator(evaluator_directory)
    roster = evaluator.load_roster()
    for row in paired_export["records"]:
        if row["eid"] in roster["heldout_eids"]:
            bridge.require(set(row["pretrained_eids"]) == set(roster["training_eids"]),
                           "paired Table 10 methods must declare all 74 pretraining EIDs")
    heldout = {row["eid"]: row for row in paired["evaluation"]["session_results"] if row["cohort"] == "heldout"}
    # Summarize matched per-session differences; never select a baseline by its test score.
    differences = {method: {comparator: {} for comparator in METHODS} for method in methods}
    for method in methods:
        for comparator in METHODS:
            for endpoint in ENDPOINTS:
                values = [heldout[row["eid"]]["scores"][method]["endpoints"][endpoint] - row["endpoints"][endpoint]
                          for row in comparators["session_results"] if row["method"] == comparator]
                differences[method][comparator][endpoint] = finite_mean(values)
    return {"schema": "neds-table1-table10-panel/v1", "paired_nine_endpoint_evaluation": paired,
            "original_decoder_comparators": comparators, "paired_minus_comparator_session_macro": differences,
            "scientific_qualification": "unknown", "readiness_promoted": False,
            "joint_superiority": "not_assessed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("paired_export", type=Path)
    parser.add_argument("comparator_export", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--methods", nargs=2, required=True)
    parser.add_argument("--implementations", type=Path)
    args = parser.parse_args()
    bridge, _ = load_bridge(args.implementations)
    result = evaluate_panel(bridge.read_json(args.bundle), bridge.read_json(args.paired_export),
                            bridge.read_json(args.comparator_export), args.methods,
                            implementations=args.implementations)
    with args.output.open("x") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
