"""Convert complete, declared NEDS exports to the pinned paired evaluator ABI.

Operator-only construction component. No native model, pickle, NPY, network,
source authentication, training attestation, or execution isolation is supplied.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

TASK_ID = "PAPER-paper-method-replacement-005"
COMMIT = "61d2ef65556dbbc2b828d542f19bd4e7134c92f3"
DEPENDENCIES = {
    "neds_evaluator.py": "6bd0b39102e8ea5afd6c5dad4e09830e0c13b3d29070d6e92f46892ad16f05d2",
    "cohort.json": "2f68e7934f7b7c5071c8e8e4763a0f3503669fe0671fd7a0ad3349fe8e0ecda5",
}
ENCODING = {
    "eval_spike": "encode_all",
    "eval_spike_choice": "encode_choice",
    "eval_spike_block": "encode_block",
    "eval_spike_wheel": "encode_wheel",
    "eval_spike_whisker": "encode_whisker",
}
CLASS_VALUES = {"choice": (-1, 1), "block": (0.2, 0.5, 0.8)}
RECEIPT_METADATA = {
    "eid", "method", "trial_ids", "unit_ids", "fit_trial_ids",
    "validation_trial_ids", "pretrained_eids", "budget_contract", "packet_sha256",
}


class BridgeError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise BridgeError(message)


def exact_fields(value, fields, name):
    require(type(value) is dict and set(value) == set(fields), name + ": exact fields required")


def numeric_tree(value, name):
    """Reject coercible strings, booleans, tuples, nonfinite and opaque objects."""
    if type(value) is list:
        require(bool(value), name + ": empty array")
        for item in value:
            numeric_tree(item, name)
    else:
        require(type(value) in (int, float), name + ": JSON numbers required")
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        require(finite, name + ": finite numbers required")


def json_copy(value):
    return json.loads(json.dumps(value, allow_nan=False))


def load_evaluator(directory=None):
    directory = (Path(directory) if directory is not None else
                 Path(__file__).resolve().parent.parent / "initial-evaluator-v1")
    for name, expected in DEPENDENCIES.items():
        path = directory / name
        require(path.is_file() and not path.is_symlink(), "regular pinned dependency required: " + name)
        require(hashlib.sha256(path.read_bytes()).hexdigest() == expected,
                "pinned dependency changed: " + name)
    spec = importlib.util.spec_from_file_location("neds_bridge_pinned_evaluator", directory / "neds_evaluator.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def decode_classes(indices, field, n_trials):
    values = CLASS_VALUES[field]
    require(type(indices) is list and len(indices) == n_trials, field + ": one index per ordered trial required")
    require(all(type(i) is int and 0 <= i < len(values) for i in indices),
            field + ": source integer class indices required, not raw labels/probabilities")
    return [values[i] for i in indices]


def convert_outputs(session, outputs, evaluator):
    exact_fields(outputs, {*ENCODING, "eval_behavior"}, "native_outputs")
    n_trials, n_units = len(session["test"]["trial_ids"]), len(session["unit_ids"])
    predictions = {}
    for source_name, target_name in ENCODING.items():
        value = outputs[source_name]
        exact_fields(value, {"expected_counts_per_bin"}, source_name)
        rates = value["expected_counts_per_bin"]
        numeric_tree(rates, source_name)
        a = evaluator.array(rates, source_name, 3)
        require(a.shape == (n_trials, 100, n_units), source_name + ": complete trial/time/unit shape required")
        require(bool((a >= 0).all()), source_name + ": nonnegative expected counts required")
        predictions[target_name] = {"spike": json_copy(rates)}
    behavior = outputs["eval_behavior"]
    exact_fields(behavior, {"choice_class_index", "block_class_index", "wheel", "whisker"}, "eval_behavior")
    decoded = {field: decode_classes(behavior[field + "_class_index"], field, n_trials)
               for field in CLASS_VALUES}
    for field in ("wheel", "whisker"):
        numeric_tree(behavior[field], field)
        a = evaluator.array(behavior[field], field, 2)
        require(a.shape == (n_trials, 100), field + ": complete trial/time shape required")
        decoded[field] = json_copy(behavior[field])
    predictions["decode_all"] = decoded
    return predictions


def assemble(bundle, export, expected_methods, *, evaluator_directory=None):
    """Return all 168 paired receipts; validate the full 74+10 source membership.

    The operator supplies expected_methods independently. Export declarations and
    hashes bind content but cannot authenticate their scientific origin.
    """
    require(type(expected_methods) in (tuple, list) and len(expected_methods) == 2 and
            all(type(m) is str and m for m in expected_methods) and
            len(set(expected_methods)) == 2, "operator must name two distinct methods")
    exact_fields(export, {"schema", "source_commit", "evidence_kind", "methods", "records"}, "export")
    require(export["schema"] == "neds-native-prediction-export/v1" and export["source_commit"] == COMMIT,
            "export schema/source mismatch")
    require(export["methods"] == list(expected_methods), "export method order differs from operator selection")
    evaluator = load_evaluator(evaluator_directory)
    sessions = evaluator.validate_bundle(bundle, engineering_subset=False)
    require(export["evidence_kind"] == bundle["evidence_kind"], "export/bundle evidence-kind mismatch")
    require(type(export["records"]) is list, "records must be list")
    roster = evaluator.load_roster()
    ordered_eids = roster["training_eids"] + roster["heldout_eids"]
    expected = {(eid, method) for eid in ordered_eids for method in expected_methods}
    require(len(export["records"]) == len(expected), "complete paired 84-session record count required")
    receipts, budgets, exposures = {}, {}, {}
    for row in export["records"]:
        exact_fields(row, RECEIPT_METADATA | {"native_outputs"}, "record")
        require(type(row["eid"]) is str and type(row["method"]) is str, "string session/method required")
        key = (row["eid"], row["method"])
        require(key in expected and key not in receipts, "unknown or duplicate session/method")
        session = sessions[row["eid"]]
        receipt = {name: json_copy(row[name]) for name in RECEIPT_METADATA}
        receipt["predictions"] = convert_outputs(session, row["native_outputs"], evaluator)
        evaluator._validate_receipt(session, receipt, expected_methods, set(roster["training_eids"]))
        require(budgets.setdefault(row["eid"], row["budget_contract"]) == row["budget_contract"],
                "paired budget declarations differ")
        exposure = sorted(row["pretrained_eids"])
        require(exposures.setdefault(row["eid"], exposure) == exposure, "paired pretraining declarations differ")
        receipts[key] = receipt
    require(set(receipts) == expected, "incomplete paired source support")
    records = [receipts[(eid, method)] for eid in ordered_eids for method in expected_methods]
    return {
        "schema": "neds-native-output-bridge-result/v1", "task_id": TASK_ID,
        "source_commit": COMMIT, "evidence_kind": bundle["evidence_kind"],
        "bundle_sha256": evaluator.digest(bundle), "export_sha256": evaluator.digest(export),
        "receipts_sha256": evaluator.digest(records), "methods": list(expected_methods),
        "coverage": {"training_sessions": 74, "heldout_sessions": 10, "paired_records": 168,
                     "masks_per_record": 6, "endpoint_count_per_record": 9},
        "receipts": records, "scientific_qualification": "unknown", "readiness_promoted": False,
        "limitations": ["declared_output_and_identity_binding_not_native_capture_attestation",
                        "no_probability_reconstruction_from_source_hard_class_predictions",
                        "expected_count_input_not_log_rate_or_hertz_conversion",
                        "full_trial_component_not_final_batch_execution_parity",
                        "no_protected_execution_source_reference_or_joint_superiority_qualification"],
    }


def evaluate_export(bundle, export, expected_methods, *, evaluator_directory=None, draws=1000, seed=0):
    """Operator-only bridge followed by the unchanged existing scorer, with no fit."""
    assembled = assemble(bundle, export, expected_methods, evaluator_directory=evaluator_directory)
    evaluator = load_evaluator(evaluator_directory)
    score = evaluator.evaluate(bundle, assembled["receipts"], tuple(expected_methods),
                               engineering_subset=False, draws=draws, seed=seed)
    return {"bridge": {k: v for k, v in assembled.items() if k != "receipts"}, "evaluation": score}


def read_json(path):
    def unique(pairs):
        d = {}
        for key, value in pairs:
            require(key not in d, "duplicate JSON object key: " + key)
            d[key] = value
        return d
    return json.loads(Path(path).read_text(), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(BridgeError("nonfinite JSON")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("export", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--methods", nargs=2, required=True)
    parser.add_argument("--evaluator-directory", type=Path)
    parser.add_argument("--score", action="store_true")
    args = parser.parse_args()
    function = evaluate_export if args.score else assemble
    result = function(read_json(args.bundle), read_json(args.export), args.methods,
                      evaluator_directory=args.evaluator_directory)
    # Never replace a prior conversion/scoring artifact.
    with args.output.open("x") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
