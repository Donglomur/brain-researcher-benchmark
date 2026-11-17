#!/usr/bin/env python3
"""Independently recompute NEURAL-040 fixed fits before reading evaluation targets.

Operator-owned reference inputs are required. This is a software verification
component, not authentication of source data, participant isolation, or readiness.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
from pathlib import Path

import numpy as np

VERSION = "fixed-fit-evaluator-v2"
BASE_SOURCE = Path(__file__).resolve().parents[1] / "initial-evaluator-v1" / "evaluator.py"
BASE_SHA256 = "19d1f793b0c59200420dcfd0570be911202c402698f488a3b75ae5a128f6db98"
# This tolerance admits serialization/roundoff only. Scores always use the
# recomputed arrays, preventing tiny changes to near-constant predictions from
# changing Pearson r even when they pass this comparison.
PREDICTION_RTOL = 1e-10
PREDICTION_ATOL = 1e-12


def _load_base():
    source = BASE_SOURCE.read_bytes()
    if hashlib.sha256(source).hexdigest() != BASE_SHA256:
        raise RuntimeError("pinned predecessor evaluator changed")
    spec = importlib.util.spec_from_file_location("neural040_fixed_fit_base", BASE_SOURCE)
    module = importlib.util.module_from_spec(spec)
    # Execute the exact bytes checked above, avoiding a second source read.
    exec(compile(source, str(BASE_SOURCE), "exec"), module.__dict__)
    return module


base = _load_base()
ContractError = base.ContractError


def complete_claims(claims):
    """Require exactly one finite numerical claim per family, in canonical order."""
    base.require(isinstance(claims, list) and len(claims) == len(base.FAMILIES),
                 "exactly three complete modality claims are required")
    by_family = {}
    for claim in claims:
        base.require(isinstance(claim, dict) and set(claim) == {"family", "mean_delta_r"},
                     "claim requires only family and mean_delta_r")
        family, value = claim["family"], claim["mean_delta_r"]
        base.require(isinstance(family, str) and family in base.FAMILIES and family not in by_family,
                     "claim family must be known and unique")
        base.require(type(value) in (int, float) and np.isfinite(value),
                     "claim must be finite numeric")
        by_family[family] = {"family": family, "mean_delta_r": value}
    return [by_family[family] for family in base.FAMILIES]


def verify_fixed_fit(protocol, features, training_targets, training_metadata,
                     predictions, prediction_metadata):
    """Refit all four arms from trusted permitted inputs; never read held targets.

    Comparing hashes or self-reported fit metadata alone is insufficient. This
    function compares every submitted prediction to a newly computed fixed fit.
    """
    base.validate_protocol(protocol)
    base.require(isinstance(prediction_metadata, dict), "prediction metadata must be an object")
    base.require(prediction_metadata.get("protocol_sha256") == base.digest(protocol),
                 "prediction protocol mismatch")
    base.require(prediction_metadata.get("parcel_ids") == protocol["parcel_ids"],
                 "prediction parcel order mismatch")
    expected_keys = {arm + "__" + segment["id"] for arm in base.ARMS
                     for segment in base.selected_segments(protocol, split="evaluation")}
    base.require(isinstance(predictions, dict) and set(predictions) == expected_keys,
                 "missing or extra prediction arm/segment IDs")
    expected, metadata = base.encode(protocol, features, training_targets, training_metadata)
    deviations = {}
    for key, reference in expected.items():
        submitted = base.matrix(predictions[key], reference.shape[0], 1000, key)
        base.require(np.allclose(submitted, reference, rtol=PREDICTION_RTOL,
                                 atol=PREDICTION_ATOL, equal_nan=False),
                     "fixed-fit prediction mismatch: " + key)
        deviations[key] = float(np.max(np.abs(submitted - reference)))
    return expected, metadata, {
        "method": "recompute_all_four_arms_from_operator_reference_inputs",
        "encoder_sha256": BASE_SHA256,
        "prediction_rtol": PREDICTION_RTOL,
        "prediction_atol": PREDICTION_ATOL,
        "maximum_absolute_deviation_by_prediction": deviations,
        "scored_predictions": "independently_recomputed",
        "fits": metadata["fits"],
        "scope": "numerical consistency with supplied reference inputs; not source authentication",
    }


def score_fixed_fit(protocol, features, training_targets, training_metadata,
                    predictions, prediction_metadata, claims, evaluation_loader):
    """Verify the submission, then request private targets exactly once.

    evaluation_loader is an operator callback returning (targets, metadata).
    It is called only after claim and fit verification; it must not be a
    participant callback. No claims or scored effects influence the fixed fit.
    """
    claims = complete_claims(claims)
    base.require(callable(evaluation_loader), "operator evaluation loader required")
    reference, metadata, verification = verify_fixed_fit(
        protocol, features, training_targets, training_metadata, predictions, prediction_metadata)
    targets, target_metadata = evaluation_loader()
    result = base.score(protocol, reference, targets, metadata, target_metadata, claims)
    result["implementation"] = VERSION
    result["fixed_fit_verification"] = verification
    result["claims_complete"] = True
    result["all_numerical_claims_verified"] = all(c["verified"] for c in result["claims"])
    result["fitting_lineage"] = (
        "Predictions numerically checked against independently recomputed pinned encoder; "
        "source identity, upstream feature lineage and participant access remain unqualified.")
    return result


def _read_targets(path, metadata_path, hashes, prefix):
    metadata = base.load_json(metadata_path)
    actual = base.sha256(path)
    base.require(isinstance(metadata, dict) and metadata.get("npz_sha256") == actual,
                 prefix + " target hash mismatch")
    targets = base.load_npz(path)
    base.require(base.sha256(path) == actual, prefix + " targets changed during read")
    hashes[prefix + "_targets"] = actual
    hashes[prefix + "_target_metadata"] = base.sha256(metadata_path)
    return targets, metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("protocol", "features", "training-targets", "training-target-metadata",
                 "predictions", "prediction-metadata", "claims", "private-targets",
                 "private-target-metadata", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    # Claim completeness fails before any neural target file is touched.
    claims = complete_claims(base.load_json(args.claims))
    protocol = base.load_json(args.protocol)
    base.validate_protocol(protocol)
    hashes = {"protocol_file": base.sha256(args.protocol),
              "features": base.sha256(args.features),
              "predictions": base.sha256(args.predictions),
              "claims": base.sha256(args.claims)}
    features = base.load_npz(args.features)
    training, training_metadata = _read_targets(
        args.training_targets, args.training_target_metadata, hashes, "training")
    prediction_metadata = base.load_json(args.prediction_metadata)
    base.require(isinstance(prediction_metadata, dict) and
                 prediction_metadata.get("artifact_sha256", {}).get("predictions") == hashes["predictions"],
                 "prediction NPZ hash mismatch")
    predictions = base.load_npz(args.predictions)
    base.require(base.sha256(args.features) == hashes["features"] and
                 base.sha256(args.predictions) == hashes["predictions"],
                 "features or predictions changed during read")

    def evaluation_loader():
        return _read_targets(args.private_targets, args.private_target_metadata, hashes, "private")

    result = score_fixed_fit(protocol, features, training, training_metadata,
                             predictions, prediction_metadata, claims, evaluation_loader)
    result["artifact_sha256"] = hashes
    # Scores include private parcel/film effects. Keep the entire output operator-private.
    with open(args.output, "x") as stream:
        import json
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
