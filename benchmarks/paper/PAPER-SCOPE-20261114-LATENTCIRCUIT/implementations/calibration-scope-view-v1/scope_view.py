"""Read the exact historical PFC metadata with its mandatory scope correction.

No array, model, or target path is followed. This view is not data admission,
protected execution, a paper reproduction, or permission to fit a model.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path


TASK_ID = "PAPER-SCOPE-20261114-LATENTCIRCUIT"
INDEX_BYTES = 135382
INDEX_SHA256 = "9f3ca6d958b673671143371ded10f617e768dd384b9788f22fef5249e723f891"
CORRECTION_BYTES = 3115
CORRECTION_SHA256 = "96ed0f533e651d3ccf4cef77e9ef7fee1cf80dc19432232a37f7f391db693588"
ANIMALS = ("ar", "fe")
PROFILE = "R_splitlocal_reconstruction"
EFFECTIVE_SCOPE = "validation_fitted_reconstruction_only"


class ScopeRefusal(ValueError):
    """The exact admitted metadata view cannot be constructed."""


def require(condition, message):
    if not condition:
        raise ScopeRefusal(message)


def _pinned(raw, size, digest, name):
    require(type(raw) is bytes, name + ": bytes required")
    require(len(raw) == size, name + ": unexpected byte extent")
    require(hashlib.sha256(raw).hexdigest() == digest, name + ": byte identity mismatch")


def _json(raw):
    def pairs(rows):
        out = {}
        for key, value in rows:
            require(key not in out, "duplicate JSON key")
            out[key] = value
        return out

    def nonfinite(_):
        raise ScopeRefusal("nonfinite JSON constant")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, ScopeRefusal):
            raise
        raise ScopeRefusal("invalid metadata JSON") from exc


def effective_index(index_bytes, correction_bytes):
    """Return an independent corrected index, changing exactly two scope strings.

    Both exact historical records are authenticated before either is decoded.
    Paths inside them are inert metadata. The original bytes/objects are never
    modified, and a different source version needs a separately reviewed view.
    """
    _pinned(index_bytes, INDEX_BYTES, INDEX_SHA256, "population index")
    _pinned(correction_bytes, CORRECTION_BYTES, CORRECTION_SHA256, "scope correction")
    original = _json(index_bytes)
    correction = _json(correction_bytes)
    try:
        require(type(original) is dict and set(original) == set(ANIMALS),
                "both original animal metadata records required")
        require(correction["schema"] == "latent_response_additive_effective_calibration_scope/v1",
                "unexpected correction schema")
        binding = correction["applies_to_exact_population_index"]
        require(binding["bytes"] == INDEX_BYTES and binding["sha256"] == INDEX_SHA256,
                "correction is bound to another index")
        rows = correction["corrections"]
        require(type(rows) is list and len(rows) == 2, "exactly two scope corrections required")
        expected = {
            f"{animal}.{PROFILE}.validation_calibration.fit_scope" for animal in ANIMALS
        }
        require({row["field_path"] for row in rows} == expected,
                "scope correction paths must cover exactly both original animals")
        for row in rows:
            require(row["original_value"] == "training_only"
                    and row["effective_value"] == EFFECTIVE_SCOPE
                    and row["original_value_is_correct"] is False
                    and row["protected_prediction_eligible"] is False,
                    "scope correction semantics differ")
        for animal in ANIMALS:
            entry = original[animal]
            require(entry[PROFILE]["validation_calibration"]["fit_scope"] == "training_only",
                    "historical field no longer has the documented defect")
            require(entry[PROFILE]["valid_for_protected_prediction"] is False,
                    "R reconstruction cannot be treated as protected prediction")
            require(entry["common"]["training_calibration"]["fit_scope"] == "training_only"
                    and entry["common"]["training_pca_parameters"]["fit_scope"] == "training_only",
                    "unchanged training calibration or PCA scope differs")
            held = entry["I_locked_traincal_two_way"]
            require(held["all_calibration_from_development"] is True
                    and held["outer_used_for_selection"] is False,
                    "unchanged I-profile declarations differ")
    except (KeyError, TypeError) as exc:
        raise ScopeRefusal("required calibration metadata is absent or malformed") from exc
    result = copy.deepcopy(original)
    for animal in ANIMALS:
        result[animal][PROFILE]["validation_calibration"]["fit_scope"] = EFFECTIVE_SCOPE
    return result


def summary(index_bytes, correction_bytes):
    """Return an operator summary without exposing metadata paths or array pins."""
    effective_index(index_bytes, correction_bytes)
    return {
        "schema": "latentcircuit.effective-calibration-scope-summary/v1",
        "task_id": TASK_ID,
        "population_index_sha256": INDEX_SHA256,
        "scope_correction_sha256": CORRECTION_SHA256,
        "corrected_fields": [
            f"{animal}.{PROFILE}.validation_calibration.fit_scope" for animal in ANIMALS
        ],
        "original_scope": "training_only",
        "effective_scope": EFFECTIVE_SCOPE,
        "R_protected_prediction_eligible": False,
        "I_profile_and_common_training_metadata": "unchanged",
        "array_payloads_read": 0,
        "original_metadata_modified": False,
        "scientific_qualification": "unresolved",
        "protected_execution_qualification": "not_established",
        "readiness_promoted": False,
    }


def _bounded_read(path, size):
    # Read only one named metadata file; never traverse any referenced path.
    with Path(path).open("rb") as handle:
        raw = handle.read(size + 1)
    require(len(raw) == size, "metadata file byte extent differs")
    return raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--population-index", required=True)
    parser.add_argument("--scope-correction", required=True)
    args = parser.parse_args(argv)
    try:
        result = summary(_bounded_read(args.population_index, INDEX_BYTES),
                         _bounded_read(args.scope_correction, CORRECTION_BYTES))
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    except (OSError, ScopeRefusal) as exc:
        parser.exit(2, "scope refusal: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
