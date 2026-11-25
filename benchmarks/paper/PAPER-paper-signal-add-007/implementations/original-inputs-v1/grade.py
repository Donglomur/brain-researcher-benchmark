"""Join frozen complete ICNet preparation/predictions to the unchanged scorer."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import numpy as np

from source import (ANIMALS, SOUNDS, TIME_BINS, UNITS, SOURCE_FILES, InputError, is_sha,
                    read_json_with_pin, require, sha256_file, validate_policy, write_json)
from predictions import MAX_BLOCK_BINS, inside, load_array, validate_public

SCORER_SHA256 = "c2643973762868391ea1d32b9c7ed54f546740f615db65bb2c920bc4ca9a493a"


def _canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def _cases(rows):
    require(type(rows) is list and len(rows) == 28, "complete 28-case source panel required")
    result = {}
    for row in rows:
        key = (row.get("animal"), row.get("sound"))
        require(type(key[0]) is int and key[0] in ANIMALS and key[1] in SOUNDS and key not in result,
                "duplicate or foreign panel case")
        require(type(row.get("time_bins")) is int and row["time_bins"] == TIME_BINS,
                "source temporal support changed")
        result[key] = row
    return result


def assemble(public_path, reference_path, predictions_path, workspace_root, *, variance_ddof):
    """Prepare a private scoring manifest without copying multi-GB predictions.

    The explicit operator workspace must contain all source and prediction
    arrays. It is not given to the participant and is not a sandbox.
    """
    require(type(variance_ddof) is int and variance_ddof in (0, 1), "explicit variance divisor required")
    workspace = Path(workspace_root).resolve(strict=True)
    paths = [Path(p).resolve(strict=True) for p in (public_path, reference_path, predictions_path)]
    require(all(p.is_relative_to(workspace) for p in paths), "all inputs must belong to the operator workspace")
    public_path, reference_path, predictions_path = paths
    documents = [read_json_with_pin(p) for p in paths]
    (public, public_pin), (reference, reference_pin), (prediction, prediction_pin) = documents
    validate_public(public)
    require(set(reference) == {"schema", "animals", "cases", "policy", "source_files",
                               "source_authentication", "qualification", "public_manifest_sha256"},
            "unexpected private reference fields")
    require(reference.get("schema") == "icnet-original-private-panel/v1", "unsupported private reference")
    require(reference["qualification"] == "source_preparation_not_scientific_admission", "private reference qualification changed")
    validate_policy(reference["policy"])
    require(set(prediction) == {"schema", "public_manifest_sha256", "predictor_sha256", "sampling_seed",
                                "sampling", "cases", "complete", "qualification"}, "unexpected prediction artifact fields")
    require(prediction.get("schema") == "icnet-original-predictions/v1" and prediction.get("complete") is True,
            "a complete frozen prediction artifact is required")
    require(prediction["sampling"] == "NumPy-PCG64-original-column-row-major-inverse-CDF"
            and type(prediction["sampling_seed"]) is int and 0 <= prediction["sampling_seed"] < 2**63
            and is_sha(prediction["predictor_sha256"]), "invalid predictor/sampling provenance")
    require(prediction["qualification"] == "complete_prediction_artifact_not_protected_or_scientifically_qualified",
            "prediction qualification changed")
    require(reference.get("public_manifest_sha256") == prediction.get("public_manifest_sha256") == public_pin,
            "prepared inputs and prediction artifacts refer to different public panels")
    require(reference.get("source_files") == public["source_files"], "public/private source identities disagree")
    require(reference.get("source_authentication") in ("publisher_bytes_md5", "generated_test_descriptors"),
            "missing explicit source-authentication scope")
    if reference["source_authentication"] == "publisher_bytes_md5":
        require(all(row["authenticated_md5"] == SOURCE_FILES[row["filename"]][1] for row in public["source_files"]),
                "generated source descriptors cannot be relabeled as publisher-authenticated")
    require(set(reference["animals"]) == {str(a) for a in ANIMALS}, "all source animals required")
    eligible = 0
    for animal in ANIMALS:
        ref = reference["animals"][str(animal)]
        require(set(ref) == {"unit_ids", "eligible_mask"}
                and ref["unit_ids"] == public["animals"][str(animal)]["unit_ids"], "source column identities disagree")
        mask = ref["eligible_mask"]
        require(type(mask) is list and len(mask) == UNITS and all(type(v) is bool for v in mask) and any(mask),
                "complete Boolean source mask required")
        cf = load_array(public_path.parent, public["animals"][str(animal)]["characteristic_frequencies"],
                        (UNITS,), "float64")
        require(np.all((np.isfinite(cf) & (cf > 0)) | np.isneginf(cf))
                and np.array_equal(np.asarray(mask), np.isfinite(cf)),
                "private mask does not match the authenticated public source CF columns")
        eligible += sum(mask)
    require(eligible == 3476, "original 3476-unit population is incomplete")
    public_cases, references, predictions = map(_cases, (public["cases"], reference["cases"], prediction["cases"]))
    cases = []
    for key in sorted(public_cases, key=lambda k: (SOUNDS.index(k[1]), k[0])):
        identity = public_cases[key]
        original, predicted = references[key], predictions[key]
        require(set(original) == {"animal", "sound", "time_bins", "measurement_times_seconds", "arrays"}
                and set(predicted) == {"animal", "sound", "time_bins", "measurement_times_seconds", "arrays", "trials"},
                "unexpected private or prediction case fields")
        require(type(predicted["trials"]) is list and len(predicted["trials"]) == 2,
                "two prediction trial receipts required")
        for ti, receipt in enumerate(predicted["trials"], start=1):
            require(type(receipt) is dict and set(receipt) == {"trial", "blocks", "column_indices"}
                    and type(receipt["trial"]) is int and receipt["trial"] == ti
                    and type(receipt["blocks"]) is int
                    and math.ceil(TIME_BINS / MAX_BLOCK_BINS) <= receipt["blocks"] <= TIME_BINS,
                    "invalid full-support trial receipt")
            columns = receipt["column_indices"]
            require(type(columns) is list and len(columns) == UNITS and all(type(x) is int for x in columns)
                    and set(columns) == set(range(UNITS)), "invalid prediction column permutation receipt")
        require(set(original["arrays"]) == {"recorded_trial1", "recorded_trial2"}, "both original trials required")
        require(set(predicted["arrays"]) == {"sampled_trial1", "sampled_trial2", "expected_trial1", "expected_trial2"},
                "separate sampled and expected counts for both trials required")
        for row in (original, predicted):
            require(row["measurement_times_seconds"] == identity["measurement_times_seconds"],
                    "prediction/source measurement-time alignment differs")
        arrays = {}
        for row, root in ((original, reference_path.parent), (predicted, predictions_path.parent)):
            for name, descriptor in row["arrays"].items():
                dtype = "float64" if name.startswith("expected_") else "int8"
                # Check fixed NPY headers and hashes before handing them to the
                # retained scorer, whose mathematical implementation is unchanged.
                loaded = load_array(root, descriptor, (TIME_BINS, UNITS), dtype)
                del loaded
                path = inside(root, descriptor["path"])
                require(path.is_relative_to(workspace), "scoring input escapes operator workspace")
                arrays[name] = {"path": str(path.relative_to(workspace)), "sha256": descriptor["sha256"]}
        cases.append({**identity, "arrays": arrays})
    return {"schema": "icnet-source-equations-input/v1", "variance_ddof": variance_ddof,
            "preparation": {
                "source_mask_sha256": _canonical_hash(reference["animals"]),
                "alignment_protocol_sha256": reference["policy"]["alignment_review_sha256"],
                "prediction_freeze_sha256": prediction_pin,
                "measurement_times_sha256": _canonical_hash([c["measurement_times_seconds"] for c in cases]),
                "mask_origin": "source_broadband_noise_reliability",
                "split": "original_four_sounds_held_out_from_training",
                "mask_evidence_sha256": reference["policy"]["mask_evidence_sha256"],
                "source_authentication": reference["source_authentication"],
                "public_manifest_sha256": public_pin,
                "private_reference_sha256": reference_pin,
                "scope": "operator_policy_declarations_are_not_independently_authenticated"},
            "animals": reference["animals"], "cases": cases}


def grade(manifest, workspace_root):
    path = Path(__file__).resolve().parent.parent / "source-equations-v1" / "scorer.py"
    scorer_bytes = path.read_bytes()
    require(hashlib.sha256(scorer_bytes).hexdigest() == SCORER_SHA256, "retained source-equation scorer changed")
    spec = importlib.util.spec_from_file_location("icnet_retained_source_equations", path)
    scorer = importlib.util.module_from_spec(spec)
    exec(compile(scorer_bytes, str(path), "exec"), scorer.__dict__)
    result = scorer.score_panel(manifest, workspace_root)
    result["input_adapter_schema"] = "icnet-original-inputs/v1"
    result["retained_scorer_sha256"] = SCORER_SHA256
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-manifest", type=Path, required=True)
    parser.add_argument("--private-reference", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--variance-ddof", type=int, choices=(0, 1), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = assemble(args.public_manifest, args.private_reference, args.predictions,
                        args.workspace_root, variance_ddof=args.variance_ddof)
    result = grade(manifest, args.workspace_root)
    write_json(args.output, result)


if __name__ == "__main__":
    main()
