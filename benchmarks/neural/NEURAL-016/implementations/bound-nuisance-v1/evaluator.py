"""NEURAL-016 scoring with a separately pinned operator nuisance comparator.

Candidate packets contain full-model predictions only. The operator supplies the
expected nuisance-file digest independently of every candidate-controlled input.
This binds bytes, not proof of actual train-only fitting or source authenticity.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any

PREDECESSOR = Path(__file__).resolve().parents[1] / "initial-evaluator-v1" / "evaluator.py"
_spec = importlib.util.spec_from_file_location("neural016_initial_evaluator", PREDECESSOR)
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
ContractError = base.ContractError
require = base.require


def exact_fields(value: Any, required: set[str], optional: set[str], name: str) -> None:
    require(isinstance(value, dict), f"{name} must be an object")
    require(required <= set(value) <= required | optional, f"incorrect fields in {name}")


def sha256(value: Any, name: str) -> str:
    require(isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value), f"invalid {name} SHA256")
    return value


def strict_json(raw: bytes) -> Any:
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value):
        raise ContractError(f"nonfinite JSON constant: {value}")

    return json.loads(raw, object_pairs_hook=object_pairs, parse_constant=reject_constant)


def bound_nuisance(raw: bytes, expected_sha256: str) -> dict:
    """Verify an independently supplied byte digest before decoding the comparator."""
    sha256(expected_sha256, "operator nuisance")
    require(isinstance(raw, bytes), "operator nuisance must be exact file bytes")
    require(hashlib.sha256(raw).hexdigest() == expected_sha256,
            "operator nuisance file hash mismatch")
    packet = strict_json(raw)
    exact_fields(packet, {"schema_version", "task_id", "protocol_sha256", "predictions",
                          "fit_provenance"}, set(), "operator nuisance")
    require(type(packet["schema_version"]) is int and packet["schema_version"] == 1
            and packet["task_id"] == "NEURAL-016", "unsupported nuisance schema or task")
    return packet


def prediction_map(values: Any, expected: set[str], arm: str) -> dict:
    result = base.keyed(values, "row_id", arm + " predictions")
    require(set(result) == expected, f"{arm} prediction IDs must exactly match evaluation rows")
    for row in result.values():
        exact_fields(row, {"row_id", arm}, set(), arm + " prediction")
        base.number(row[arm], arm + " prediction")
    return result


def fit_map(values: Any, context: dict, arm: str) -> dict:
    result = base.keyed(values, "fold_id", arm + " fit provenance")
    require(set(result) == set(context["folds"]), f"{arm} fit provenance must cover every fold")
    for fold_id, item in result.items():
        exact_fields(item, {"fold_id", "fit_row_ids", "recipe_sha256", arm + "_artifact_sha256"},
                     set(), arm + " fit provenance")
        require(set(base.unique(item["fit_row_ids"], "fit rows"))
                == set(context["folds"][fold_id]["fit_row_ids"]), "declared fit rows differ from frozen fold")
        require(item["recipe_sha256"] == base.canonical_hash(context["recipe"]), "fit recipe hash mismatch")
        sha256(item[arm + "_artifact_sha256"], arm + " artifact")
    return result


def absolute_summary(blocks: list[dict]) -> dict:
    """Use the same equal block/electrode/person weights for absolute metrics."""
    metrics = ("nuisance_r2", "full_r2", "nuisance_explained_variance", "full_explained_variance")

    def average(group):
        output = {}
        for metric in metrics:
            try:
                value = math.fsum(row[metric] / len(group) for row in group)
            except OverflowError as error:
                raise ContractError("nonfinite absolute aggregate") from error
            require(math.isfinite(value), "nonfinite absolute aggregate")
            output[metric] = value
        return output

    groups = defaultdict(list)
    for block in blocks:
        groups[(block["participant_id"], block["electrode_id"])].append(block)
    electrodes = [dict(participant_id=p, electrode_id=e, n_blocks=len(group), **average(group))
                  for (p, e), group in sorted(groups.items())]
    participants = []
    for person in sorted({row["participant_id"] for row in electrodes}):
        group = [row for row in electrodes if row["participant_id"] == person]
        participants.append(dict(participant_id=person, n_electrodes=len(group), **average(group)))
    require(bool(participants), "no absolute participant summaries")
    return {"electrodes": electrodes, "participants": participants, "estimate": average(participants)}


def evaluate(protocol: dict, private_targets: dict, candidate: dict, *,
             nuisance_bytes: bytes, expected_nuisance_sha256: str) -> dict:
    """Recompute full-minus-fixed-nuisance R²; candidate cannot replace nuisance.

    expected_nuisance_sha256 must come from operator-owned configuration frozen
    before candidate outcomes, never from a submitted file or candidate option.
    """
    nuisance = bound_nuisance(nuisance_bytes, expected_nuisance_sha256)
    context = base.validate_protocol(protocol)
    require(context["recipe"]["primary_metric"] == "delta_r2", "current NEURAL-016 primary must be delta_r2")
    digest = base.canonical_hash(protocol)
    exact_fields(candidate, {"schema_version", "task_id", "protocol_sha256", "predictions", "fit_provenance",
                             "claimed_delta_r2"}, {"null_predictions"}, "candidate")
    require(type(candidate["schema_version"]) is int and candidate["schema_version"] == 1
            and candidate["task_id"] == "NEURAL-016", "unsupported candidate schema or task")
    require(candidate["protocol_sha256"] == nuisance["protocol_sha256"] == digest,
            "candidate or nuisance protocol hash mismatch")
    claim = base.number(candidate["claimed_delta_r2"], "claimed delta R2")
    expected = context["evaluation_ids"]
    nuisance_predictions = prediction_map(nuisance["predictions"], expected, "nuisance")
    nuisance_fits = fit_map(nuisance["fit_provenance"], context, "nuisance")

    def pair(full_rows, full_provenance):
        full = prediction_map(full_rows, expected, "full")
        fits = fit_map(full_provenance, context, "full")
        rows = [{"row_id": row_id, "nuisance": nuisance_predictions[row_id]["nuisance"],
                 "full": full[row_id]["full"]} for row_id in sorted(expected)]
        provenance = [dict(fits[fold_id], nuisance_artifact_sha256=
                           nuisance_fits[fold_id]["nuisance_artifact_sha256"]) for fold_id in sorted(fits)]
        return rows, provenance

    rows, fits = pair(candidate["predictions"], candidate["fit_provenance"])
    paired = {"protocol_sha256": digest, "predictions": rows, "fit_provenance": fits}
    nulls = candidate.get("null_predictions", [])
    require(isinstance(nulls, list), "null predictions must be a list")
    paired["null_predictions"] = []
    for null in nulls:
        exact_fields(null, {"permutation_id", "control", "refitted_recipe_sha256", "shift_manifest_sha256",
                            "predictions", "fit_provenance"}, set(), "candidate null")
        null_rows, null_fits = pair(null["predictions"], null["fit_provenance"])
        paired["null_predictions"].append(dict(null, predictions=null_rows, fit_provenance=null_fits))

    result = base.evaluate(protocol, private_targets, paired)
    absolute = absolute_summary(result["blocks"])
    error = abs(claim - result["primary_estimate"])
    require(math.isfinite(error), "nonfinite claim error")
    result.update(implementation="bound-nuisance-v1", submission_sha256=base.canonical_hash(candidate),
                  operator_nuisance_file_sha256=expected_nuisance_sha256,
                  absolute_summary=absolute,
                  claim_score={"claimed_delta_r2": claim, "computed_delta_r2": result["primary_estimate"],
                               "absolute_error": error, "direction": "lower_is_better"},
                  full_prediction_statistic={"name": "full_r2", "value": absolute["estimate"]["full_r2"],
                                             "direction": "higher_is_better",
                                             "scope": "descriptive; native reference qualification absent"})
    result["additional_holds"].extend([
        "Operator must freeze the expected nuisance digest independently before candidate outcomes; a self-supplied digest is not a trust anchor.",
        "Byte binding prevents candidate nuisance substitution but does not verify authentic signals, competent nuisance fitting, or execution timing.",
        "Claim error evaluates agreement with this computed contrast; it does not establish direct or viewer interpretation.",
    ])
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("protocol", "private-targets", "candidate", "operator-nuisance", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-nuisance-sha256", required=True)
    args = parser.parse_args()
    temporary = None
    try:
        paths = {name: getattr(args, name) for name in ("protocol", "private_targets", "candidate", "operator_nuisance")}
        require(args.output.resolve() not in {path.resolve() for path in paths.values()}, "output must not overwrite an input")
        # Reject a substituted comparator before reading private targets.
        raw = {"operator_nuisance": args.operator_nuisance.read_bytes()}
        bound_nuisance(raw["operator_nuisance"], args.expected_nuisance_sha256)
        for name in ("protocol", "candidate", "private_targets"):
            raw[name] = paths[name].read_bytes()
        result = evaluate(strict_json(raw["protocol"]), strict_json(raw["private_targets"]), strict_json(raw["candidate"]),
                          nuisance_bytes=raw["operator_nuisance"], expected_nuisance_sha256=args.expected_nuisance_sha256)
        result["input_file_sha256"] = {name: hashlib.sha256(content).hexdigest() for name, content in raw.items()}
        serialized = json.dumps(result, indent=2, allow_nan=False) + "\n"
        with tempfile.NamedTemporaryFile(mode="w", dir=args.output.parent, prefix=".neural016-score-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(serialized)
        os.replace(temporary, args.output)
        temporary = None
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(2, f"invalid NEURAL-016 bound input: {error}\n")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
