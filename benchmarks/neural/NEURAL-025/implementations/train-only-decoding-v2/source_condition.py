"""Source-evidenced processed-input condition, with unknown exposure retained.

This deliberately supports one reviewed evidence state per representation. New
actual model-exposure receipts require a reviewed successor, not extra fields
that silently turn unknown provenance into a qualified observation bound.
"""
from __future__ import annotations

import hashlib
import json

POLICY = "processed_inputs_separate_support_unknown_exposure_v2"
CONDITION = "radical_lift_locked_processed_input_source_condition_v2"
LOCKED_GRID = list(range(-200, 801, 10))
TARGET_GRID = list(range(-100, 401, 10))
AUTHOR_COMMIT = "815b610b3beddfed5a3abf611d3a465ab9e4ce5c"
SOURCE_PINS = {
    "preproc/loadLockSave.m": "c6a15a3ac35c377eb2c8b6799ffcfa99b88622415f880cd3a743c06f518be28f",
    "preproc/loadLock4Decode.m": "01dbb2e5421908555833163a44d10821a29935d2ffd943c6b0eed372bee2ee9f",
    "preproc/eventLockRADICaL.m": "b4b47b1a3d18512a68b63ce2782e81fee078ce4e02b434f5b18c95120d5556ed",
    "preproc/eventLockDataSmooth.m": "eeba3a06b7efd5f0e31821efc4895a65c5a05490e440502b4c10efb1774b31c0",
    "main/fig5/analysis/loadDecode.m": "981c0b4e9a32557e29592bb011aa3476d97600c31560b4c933a9c7fdf5a1b727",
}
PAPER_SHA256 = "b1af6eaac2017c1ed85c06cfa65aac6f9492a8d1b2198dbe380fb256183f6175"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def build_source_condition(variant):
    """Return the known/unknown source record, never an actual exposure receipt."""
    if variant not in ("smoothed_deconvolved_events", "radical"):
        raise ValueError("Unsupported source-condition feature variant")
    radical = variant == "radical"
    preprocessing = {
        "actual_raw_frame_dependency_interval_ms": None,
        "actual_raw_frame_dependency_status": "unverified",
        "operation": "select_supplied_radical_rates" if radical else "source_event_resampling_gaussian_smoothing_and_trim",
        "additional_gaussian_smoothing_sd_ms": None if radical else 35,
        "source_requested_resampling_grid_ms": None if radical else list(range(-270, 871, 10)),
        "requested_grid_is_full_raw_dependency_bound": False,
        "deconvolution_and_learned_preprocessing_exposure_status": "unknown",
    }
    model = {
        "status": "unverified_conflicting_source_evidence" if radical else "not_radical_condition",
        "actual_input_or_inference_interval_ms": None,
        "source_statements": {
            "caller_tPtsRADICaL_ms": list(LOCKED_GRID),
            "caller_comment": "timepoints used when fitting RADICaL models",
            "helper_nonexecuting_comment_grid_ms": list(range(-200, 791, 10)),
            "paper_model_window_ms": [-100, 800],
            "paper_padding_ms": 100,
            "possible_symmetric_padded_context_ms": [-200, 900],
            "possible_context_status": "inference_from_symmetric_padding_not_verified_actual_exposure",
        } if radical else None,
        "locked_grid_establishes_model_exposure": False,
    }
    return {
        "schema": "calcium_processed_input_source_condition_v2",
        "condition": CONDITION,
        "feature_variant": variant,
        "event_conditioning": "retrospective_public_liftTimeDLC",
        "locked_output_grid_ms": list(LOCKED_GRID),
        "decoder_output_grid_ms": list(TARGET_GRID),
        "preprocessing_support": preprocessing,
        "model_input_and_inference_context": model,
        "fitted_trial_training_exposure": {
            "status": "unknown", "fit_or_checkpoint_identity": None,
            "training_trial_ids": None, "training_recording_segments": None,
            "training_source_assets": None, "evaluation_trial_exposure": "unknown",
            "fold_safety_status": "unknown",
        },
        "qualification": {
            "bounded_raw_observation_qualified": False,
            "upstream_fold_safety_qualified": False,
            "causal_or_online_qualified": False,
            "authentic_original_model_parity_qualified": False,
            "scientific_qualification": False,
        },
        "source_evidence": {
            "author_commit": AUTHOR_COMMIT,
            "code_sha256": dict(SOURCE_PINS),
            "paper_xml_sha256": PAPER_SHA256,
            "paper_version_doi": "10.7554/eLife.106270.3",
        },
    }


def reject_legacy_support(value):
    """Reject the ambiguous predecessor key anywhere in a new document."""
    if isinstance(value, dict):
        if "upstream_temporal_support_ms" in value:
            raise ValueError("Legacy upstream_temporal_support_ms is forbidden in v2")
        for child in value.values():
            reject_legacy_support(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            reject_legacy_support(child)


def validate_source_condition(record, variant):
    """Require exact evidence and unknowns; return a digest of the real body."""
    reject_legacy_support(record)
    if canonical(record) != canonical(build_source_condition(variant)):
        raise ValueError("Source condition differs from supported known/unknown evidence; no invented exposure or qualification")
    return digest(record)


def public_summary(record, variant):
    """Whitelist public source facts only; unknown training IDs stay private."""
    validate_source_condition(record, variant)
    summary = {key: record[key] for key in (
        "schema", "condition", "feature_variant", "event_conditioning",
        "locked_output_grid_ms", "decoder_output_grid_ms", "preprocessing_support",
        "model_input_and_inference_context", "qualification")}
    training = record["fitted_trial_training_exposure"]
    summary["fitted_trial_training_exposure"] = {key: training[key] for key in (
        "status", "evaluation_trial_exposure", "fold_safety_status")}
    return summary
