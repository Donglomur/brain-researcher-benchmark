"""NEURAL-016 operator gate for feature support and causal availability.

A nonpositive nominal lag does not imply that an extracted feature is available
at the prediction time. This gate binds the operator's explicit support envelope
before calling the unchanged operator-bound nuisance scorer. Declarations and
byte hashes do not authenticate the feature extraction or admit a scientific run.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import tempfile

PREDECESSOR = Path(__file__).resolve().parents[1] / "bound-nuisance-v1" / "evaluator.py"
_spec = importlib.util.spec_from_file_location("neural016_bound_nuisance", PREDECESSOR)
bound = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bound)
ContractError = bound.ContractError
require = bound.require


def finite(value, name):
    require(type(value) in (int, float), f"invalid {name}")
    try:
        result = float(value)
    except (ValueError, OverflowError) as error:
        raise ContractError(f"invalid {name}") from error
    require(math.isfinite(result), f"invalid {name}")
    return result


def validate_availability(protocol, raw: bytes, expected_sha256: str):
    """Check a pinned conservative feature envelope for every declared lag.

    support_seconds and available_after_seconds are relative to the feature's
    anchor; feature_lags_seconds offsets that anchor from each protocol row time.
    Every declared row must be held out exactly once, including rows also used
    for fitting other folds. Support conservatively covers every declared row.
    Actual extractor conformance remains an independent operator obligation.
    """
    bound.sha256(expected_sha256, "operator feature manifest")
    require(isinstance(raw, bytes), "feature manifest must be exact bytes")
    require(hashlib.sha256(raw).hexdigest() == expected_sha256,
            "operator feature manifest file hash mismatch")
    manifest = bound.strict_json(raw)
    bound.exact_fields(manifest, {"schema_version", "task_id", "protocol_sha256",
                                 "policy", "coverage", "features"}, set(), "feature manifest")
    require(type(manifest["schema_version"]) is int and manifest["schema_version"] == 1
            and manifest["task_id"] == "NEURAL-016", "unsupported feature manifest")
    require(manifest["protocol_sha256"] == bound.base.canonical_hash(protocol),
            "feature manifest protocol hash mismatch")
    require(manifest["policy"] == "available_at_row_time", "unsupported feature availability policy")
    require(manifest["coverage"] == "all_declared_fit_and_evaluation_rows",
            "feature envelope must cover every declared row")
    context = bound.base.validate_protocol(protocol)
    # The canonical task scores every declared row and included recording.
    # Fit coverage alone must not hide a recording, block or electrode from scoring.
    require(context["evaluation_ids"] == set(context["rows"]),
            "every declared row must be evaluated; fit-only inclusion is forbidden")
    roles = {}
    for role, names in context["recipe"]["nuisance_features"].items():
        roles.update((name, role) for name in names)
    roles.update((name, "linguistic") for name in context["recipe"]["linguistic_features"])
    features = bound.base.keyed(manifest["features"], "name", "feature declarations")
    require(set(features) == set(roles), "feature names must exactly match the frozen recipe")
    lags = context["recipe"]["feature_lags_seconds"]
    support_min = math.inf
    support_max = -math.inf
    latest_availability = -math.inf
    for name, feature in features.items():
        bound.exact_fields(feature, {"name", "role", "support_seconds", "available_after_seconds",
                                    "definition", "extractor_sha256"}, set(), "feature declaration")
        require(feature["role"] == roles[name], "feature role differs from frozen recipe")
        bound.base.identifier(feature["definition"], "feature definition")
        bound.sha256(feature["extractor_sha256"], "feature extractor")
        support = feature["support_seconds"]
        require(isinstance(support, list) and len(support) == 2, "feature support needs two bounds")
        start, end = (finite(x, "feature support") for x in support)
        require(start <= end, "reversed feature support")
        available = finite(feature["available_after_seconds"], "feature availability")
        require(available >= end, "feature declared available before its latest input")
        for lag in lags:
            lower, upper, ready = start + lag, end + lag, available + lag
            require(all(math.isfinite(x) for x in (lower, upper, ready)),
                    "nonfinite effective feature support")
            require(ready <= 0, "feature is unavailable at the declared row time")
            support_min = min(support_min, lower)
            support_max = max(support_max, upper)
            latest_availability = max(latest_availability, ready)
    guard = context["recipe"]["guard_seconds"]
    require(guard >= max(abs(support_min), abs(support_max)),
            "declared temporal guard misses effective feature support")
    blocks = {b["block_id"]: b for b in protocol["blocks"]}
    for row in context["rows"].values():
        block = blocks[row["block_id"]]
        require(block["start_seconds"] <= row["time_seconds"] + support_min
                and row["time_seconds"] + support_max <= block["end_seconds"],
                "effective feature support leaves its continuous block")
    return {"operator_feature_manifest_file_sha256": expected_sha256,
            "feature_count": len(features), "row_count": len(context["rows"]),
            "effective_support_seconds": [support_min, support_max],
            "latest_availability_relative_to_row_seconds": latest_availability,
            "policy": manifest["policy"],
            "status": "declared_temporal_support_validated_extractor_conformance_unverified"}


def evaluate(protocol, private_targets, candidate, *, nuisance_bytes,
             expected_nuisance_sha256, feature_manifest_bytes, expected_feature_manifest_sha256):
    support = validate_availability(protocol, feature_manifest_bytes, expected_feature_manifest_sha256)
    result = bound.evaluate(protocol, private_targets, candidate, nuisance_bytes=nuisance_bytes,
                            expected_nuisance_sha256=expected_nuisance_sha256)
    result["implementation"] = "feature-availability-v1"
    result["feature_availability"] = support
    result["additional_holds"].append(
        "Operator feature envelopes and extractor hashes require independent conformance and provenance verification; declarations do not certify causal extraction.")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    names = ("protocol", "private-targets", "candidate", "operator-nuisance", "operator-feature-manifest", "output")
    for name in names:
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-nuisance-sha256", required=True)
    parser.add_argument("--expected-feature-manifest-sha256", required=True)
    args = parser.parse_args()
    temporary = None
    try:
        paths = {name.replace("-", "_"): getattr(args, name.replace("-", "_")) for name in names[:-1]}
        require(args.output.resolve() not in {p.resolve() for p in paths.values()}, "output must not overwrite an input")
        raw = {"protocol": args.protocol.read_bytes(),
               "operator_feature_manifest": args.operator_feature_manifest.read_bytes()}
        protocol = bound.strict_json(raw["protocol"])
        validate_availability(protocol, raw["operator_feature_manifest"], args.expected_feature_manifest_sha256)
        raw["operator_nuisance"] = args.operator_nuisance.read_bytes()
        bound.bound_nuisance(raw["operator_nuisance"], args.expected_nuisance_sha256)
        # Reject incomplete evaluation/feature support and comparator substitution
        # before private targets. Support validation also precedes candidate reads.
        raw["candidate"] = args.candidate.read_bytes()
        raw["private_targets"] = args.private_targets.read_bytes()
        result = evaluate(protocol, bound.strict_json(raw["private_targets"]), bound.strict_json(raw["candidate"]),
                          nuisance_bytes=raw["operator_nuisance"], expected_nuisance_sha256=args.expected_nuisance_sha256,
                          feature_manifest_bytes=raw["operator_feature_manifest"],
                          expected_feature_manifest_sha256=args.expected_feature_manifest_sha256)
        result["input_file_sha256"] = {k: hashlib.sha256(v).hexdigest() for k, v in raw.items()}
        with tempfile.NamedTemporaryFile(mode="w", dir=args.output.parent, prefix=".neural016-availability-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
        os.replace(temporary, args.output)
        temporary = None
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(2, f"invalid NEURAL-016 feature-support input: {error}\n")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
