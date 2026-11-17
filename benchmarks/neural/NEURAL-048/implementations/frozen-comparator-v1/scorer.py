"""Score NEURAL-048 neural arms against a separately pinned operator baseline.

This is an operator scorer, not a model runner or a baseline competence test.
The original equal-worm log-loss arithmetic is reused without changing v1.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from statistics import fmean


LEGACY_SHA256 = "cd2dc29f52e4aa79a5dc5b913aad9bef57b08e9bbf74f7c7a463b923c9e03d57"
LEGACY_PATH = Path(__file__).resolve().parents[1] / "initial-evaluator-v1" / "evaluator.py"
if hashlib.sha256(LEGACY_PATH.read_bytes()).hexdigest() != LEGACY_SHA256:
    raise RuntimeError("NEURAL-048 original scorer changed; independent review required")
_spec = importlib.util.spec_from_file_location("neural048_original_scorer", LEGACY_PATH)
legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(legacy)

ContractError = legacy.ContractError
digest = legacy.digest
NEURAL_ARMS = ("neural_history", "shifted_neural_history")
COMPARATOR_SCHEMA = "neural048-frozen-behavior/v1"
CANDIDATE_SCHEMA = "neural048-neural-arms/v1"
RECEIPT_FIELDS = {"split_sha256", "behavior_history_sha256", "frozen_recipe_sha256",
                  "cpu_seconds", "peak_memory_bytes"}


def _exact(value, fields, name):
    legacy._mapping(value, name)
    legacy._require(set(value) == set(fields), f"{name}: exact fields required")


def _receipt(value, reference, name):
    _exact(value, RECEIPT_FIELDS, name)
    legacy._require(value["split_sha256"] == digest(reference["folds"]),
                    f"{name}: whole-worm split mismatch")
    legacy._require(value["behavior_history_sha256"] == reference["behavior_history_sha256"],
                    f"{name}: shared behavior history mismatch")
    legacy._sha(value["frozen_recipe_sha256"], "frozen_recipe_sha256")
    legacy._require(legacy._finite(value["cpu_seconds"], "cpu_seconds") >= 0,
                    "negative resource usage")
    legacy._require(legacy._integer(value["peak_memory_bytes"], "peak_memory_bytes") >= 0,
                    "negative memory")


def _probabilities(rows, observations, arms, name):
    legacy._require(isinstance(rows, list), f"{name}: rows required")
    mapped = {}
    for row in rows:
        _exact(row, {"id", *arms}, name)
        oid = legacy._text(row["id"], "observation id")
        legacy._require(oid in observations and oid not in mapped,
                        f"{name}: unknown or duplicate observation")
        for arm in arms:
            probability = legacy._finite(row[arm], f"{arm} probability")
            legacy._require(0 < probability < 1,
                            "probabilities must be in open interval (0,1); no silent clipping")
        mapped[oid] = row
    legacy._require(set(mapped) == set(observations),
                    f"{name}: complete matched observation set required")
    return mapped


def freeze_behavior(reference, predictions, receipt, execution_manifest_sha256):
    """Build an operator comparator artifact; retain its digest outside submissions.

    This packages already produced probabilities. It neither fits a decoder nor
    authenticates the execution-manifest hash. Operator provenance/competence
    review and freezing before candidate outcomes remain separate requirements.
    """
    observations = legacy.validate_reference(reference)
    _probabilities(predictions, observations, ("behavior",), "behavior predictions")
    _receipt(receipt, reference, "behavior receipt")
    legacy._sha(execution_manifest_sha256, "execution_manifest_sha256")
    return copy.deepcopy({
        "schema": COMPARATOR_SCHEMA, "task_id": legacy.TASK_ID,
        "reference_sha256": digest(reference), "policy_sha256": digest(legacy.POLICY),
        "execution_manifest_sha256": execution_manifest_sha256,
        "receipt": receipt, "predictions": predictions,
    })


def score(reference, comparator, candidate, *, expected_comparator_sha256):
    """Compute the original paired estimand with immutable behavior probabilities.

    expected_comparator_sha256 is an operator-selected pin, never a value taken
    from the candidate. The comparator is rejected before candidate evaluation
    if any probability, identity or provenance has changed.
    """
    observations = legacy.validate_reference(reference)
    legacy._sha(expected_comparator_sha256, "expected_comparator_sha256")
    _exact(comparator, {"schema", "task_id", "reference_sha256", "policy_sha256",
                        "execution_manifest_sha256", "receipt", "predictions"}, "comparator")
    legacy._require(digest(comparator) == expected_comparator_sha256,
                    "operator comparator pin mismatch")
    legacy._require(comparator["schema"] == COMPARATOR_SCHEMA, "wrong comparator schema")
    legacy._require(comparator["task_id"] == legacy.TASK_ID, "wrong comparator task")
    legacy._require(comparator["reference_sha256"] == digest(reference),
                    "comparator reference mismatch")
    legacy._require(comparator["policy_sha256"] == digest(legacy.POLICY),
                    "comparator policy mismatch")
    legacy._sha(comparator["execution_manifest_sha256"], "execution_manifest_sha256")
    _receipt(comparator["receipt"], reference, "behavior receipt")
    behavior = _probabilities(comparator["predictions"], observations,
                              ("behavior",), "behavior predictions")

    _exact(candidate, {"schema", "task_id", "reference_sha256", "policy_sha256",
                       "comparator_sha256", "arm_receipts", "predictions"}, "candidate")
    legacy._require(candidate["schema"] == CANDIDATE_SCHEMA, "wrong candidate schema")
    legacy._require(candidate["task_id"] == legacy.TASK_ID, "wrong candidate task")
    legacy._require(candidate["reference_sha256"] == digest(reference), "candidate reference mismatch")
    legacy._require(candidate["policy_sha256"] == digest(legacy.POLICY), "candidate policy mismatch")
    legacy._require(candidate["comparator_sha256"] == expected_comparator_sha256,
                    "candidate comparator mismatch")
    _exact(candidate["arm_receipts"], NEURAL_ARMS, "candidate arm receipts")
    for arm in NEURAL_ARMS:
        _receipt(candidate["arm_receipts"][arm], reference, arm + " receipt")
    neural = _probabilities(candidate["predictions"], observations,
                            NEURAL_ARMS, "candidate predictions")

    # Explicit field projection ensures the candidate has no path to supply,
    # replace, degrade, or drop a behavior probability used in this contrast.
    combined = {
        "task_id": legacy.TASK_ID, "reference_sha256": digest(reference),
        "policy_sha256": digest(legacy.POLICY),
        "arm_receipts": {"behavior": comparator["receipt"], **candidate["arm_receipts"]},
        "predictions": [{"id": oid, "behavior": behavior[oid]["behavior"],
                         **{arm: neural[oid][arm] for arm in NEURAL_ARMS}}
                        for oid in sorted(observations)],
    }
    report = legacy.score(reference, combined)
    report.update({
        "component": "frozen-comparator-v1",
        "submission_sha256": digest(candidate),
        "combined_predictions_sha256": digest(combined),
        "comparator_sha256": expected_comparator_sha256,
        "comparator_execution_manifest_sha256": comparator["execution_manifest_sha256"],
        "absolute_equal_worm_log_loss_nats": {
            arm: fmean(worm["log_loss_nats"][arm] for worm in report["worms"])
            for arm in legacy.ARMS},
        "comparison_scope": {
            "behavior_probabilities": "operator comparator pinned independently of candidate",
            "candidate_probabilities": list(NEURAL_ARMS),
            "interpretation": "signed descriptive conditional prediction contrast",
            "not_established": ["competence of the frozen behavior decoder",
                                "execution-manifest authenticity or prospective freeze timing",
                                "causal features or isolated whole-worm model fitting",
                                "neural mechanistic causality or direct interpretation"],
        },
    })
    report["validation_scope"]["verified"].append("operator-pinned behavior probabilities")
    return copy.deepcopy(report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", help="operator-only reference JSON")
    parser.add_argument("comparator", help="separately frozen operator comparator JSON")
    parser.add_argument("candidate", help="two neural prediction arms JSON")
    parser.add_argument("--expected-comparator-sha256", required=True,
                        help="independently retained operator digest; never read from candidate")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        report = score(legacy._load(args.reference), legacy._load(args.comparator),
                       legacy._load(args.candidate),
                       expected_comparator_sha256=args.expected_comparator_sha256)
        Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    except (ContractError, OSError, KeyError, TypeError, ValueError) as exc:
        parser.exit(2, f"NEURAL-048 frozen comparison rejected: {exc}\n")


if __name__ == "__main__":
    main()
