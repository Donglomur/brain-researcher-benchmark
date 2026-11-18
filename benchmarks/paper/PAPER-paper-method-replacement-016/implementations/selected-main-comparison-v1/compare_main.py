"""Descriptive full 99-model main-panel comparisons, without a scientific pass.

The source-selected endpoint is distinct from the predecessor's 335-condition
broader-paper comparison. No training/control observations are fabricated here.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
from types import ModuleType

TASK = "PAPER-paper-method-replacement-016"
LEGACY_SHA256 = "587669014bf424ce8b528747c682c73eef373438b9c9e3a4f3e8796a9cb0add6"
LEGACY_BYTES = 12907
REFERENCE_SCHEMA = "hundred_models_selected_main_reference_v1"
REPRODUCTION_SCHEMA = "hundred_models_selected_main_reproduction_v1"
CANDIDATE_SCHEMA = "hundred_models_original_candidate_v1"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_legacy(path=None):
    """Reuse only byte-authenticated, already reviewed source helper code."""
    path = Path(path) if path is not None else (
        Path(__file__).resolve().parent.parent / "original-panel-comparison-v1" / "compare.py")
    with path.open("rb") as handle:
        raw = handle.read(LEGACY_BYTES + 1)
    require(len(raw) == LEGACY_BYTES and hashlib.sha256(raw).hexdigest() == LEGACY_SHA256,
            "original comparator source identity mismatch")
    module = ModuleType("hundred_models_pinned_original_compare")
    module.__file__ = str(path)
    # Execute the verified bytes, rather than rereading a path after hashing.
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def _fields(value, names, label):
    require(type(value) is dict and set(value) == set(names), label + " exact fields")


def _axes(protocol_path, source):
    axes = source.source_axes(protocol_path)
    conditions = [condition for condition, role in axes["conditions"] if role == "main"]
    require(conditions == ["test:pca:" + name for name in axes["models"]]
            and len(conditions) == 99, "complete original main PCA model order")
    return axes, conditions


def _support(document, axes, source):
    support = document["test_support"]
    _fields(support, ("subjects", "stimuli", "repetitions", "brain_rdms_sha256",
                      "video_inputs_sha256"), "original test support")
    require(all(support[key] == axes[key] for key in ("subjects", "stimuli", "repetitions"))
            and type(support["repetitions"]) is int,
            "original ten people / 102 ordered test videos / ten repetitions")
    require(source._sha(support["brain_rdms_sha256"])
            and source._sha(support["video_inputs_sha256"]),
            "declared brain/video observation digests")
    require(source._sha(document["run_sha256"]), "declared full run-record digest")


def _ceilings(rows, axes):
    require(type(rows) is list and len(rows) == 17, "all 17 test noise-ceiling rows")
    for row, roi in zip(rows, axes["rois"]):
        _fields(row, ("roi", "lower", "upper"), "noise ceiling")
        require(row["roi"] == roi, "original noise-ceiling ROI order")
        require(all(value is None or (type(value) in (int, float)
                    and math.isfinite(value) and -1 <= value <= 1)
                    for value in (row["lower"], row["upper"])),
                "signed finite noise ceilings or explicit null")


def _full_main(document, schema, axes, conditions, source):
    names = {"schema", "test_support", "run_sha256", "noise_ceilings", "layer_catalog", "rsa"}
    if schema == REFERENCE_SCHEMA:
        names.add("origin")
    _fields(document, names, "selected-main document")
    require(document["schema"] == schema, "selected-main document schema")
    if schema == REFERENCE_SCHEMA:
        require(document["origin"] in ("published_author_outputs", "reproduced_author_outputs"),
                "published and reproduced author origins remain distinct")
    _support(document, axes, source)
    _ceilings(document["noise_ceilings"], axes)
    catalog = document["layer_catalog"]
    require(type(catalog) is dict and set(catalog) == set(conditions),
            "exact 99 main condition layer catalogs; no fabricated companions")
    for layers in catalog.values():
        source._layers(layers)
    rows = document["rsa"]
    require(type(rows) is list and len(rows) == 99 * 17, "complete 99 by 17 RSA rows")
    selected = {}
    summaries = []
    for row, (condition, roi) in zip(rows, ((c, r) for c in conditions for r in axes["rois"])):
        _fields(row, ("condition", "roi", "layers", "values"), "main RSA row")
        require((row["condition"], row["roi"]) == (condition, roi),
                "complete original main condition/ROI order")
        require(row["layers"] == catalog[condition], "complete declared reference layers")
        summary = source.select(row["layers"], row["values"])
        selected[(condition, roi)] = summary
        summaries.append({"condition": condition, "roi": roi, **summary})
    return selected, summaries


def _candidate(document, axes, source):
    _fields(document, ("schema", "test_support", "run_sha256", "freeze_sha256",
                       "layers", "rsa"), "candidate")
    require(document["schema"] == CANDIDATE_SCHEMA, "candidate schema")
    _support(document, axes, source)
    require(source._sha(document["freeze_sha256"]), "declared candidate freeze-record digest")
    source._layers(document["layers"])
    require(type(document["rsa"]) is list and len(document["rsa"]) == 17,
            "all 17 candidate ROIs")
    result = {}
    for row, roi in zip(document["rsa"], axes["rois"]):
        _fields(row, ("roi", "layers", "values"), "candidate RSA row")
        require(row["roi"] == roi, "original candidate ROI order")
        require(row["layers"] == document["layers"], "one complete candidate layer catalog across ROIs")
        result[roi] = source.select(row["layers"], row["values"])
    return result


def _difference(observed, reference):
    return None if observed is None or reference is None else observed - reference


def _base(reference, observed, axes, source, mode):
    require(reference["test_support"] == observed["test_support"],
            "both sides must use the identical declared original observations")
    return {"schema": "hundred_models_selected_main_comparison_v1", "task_id": TASK,
            "mode": mode, "status": "descriptive_comparison_only",
            "protocol_sha256": source.PROTOCOL_SHA256, "source_component_sha256": LEGACY_SHA256,
            "reference_sha256": source.digest(reference), "observed_sha256": source.digest(observed),
            "reference_origin": reference["origin"], "test_support": reference["test_support"],
            "counts": {"main_models": 99, "rois": 17, "participants": 10,
                       "stimuli": 102, "test_repetitions": 10, "reference_rows": 1683},
            "source_scope": {"endpoint": "selected_original_main_pca",
                             "separate_scopes_not_required_or_fabricated": ["figure16_srp_unreduced",
                                 "figure17_training_videos", "figure18_auxiliary_videomae"],
                             "public_panel_exposure": "original public panel; not an unseen test"},
            "inference": {"independent_units": "participants with shared stimuli and correlated ROIs/layers",
                          "selection": "whole-cohort signed layer-mean maximum; selection-aware inference unresolved",
                          "interval": None, "equivalence_tolerance": None,
                          "reproduction_pass": None, "across_roi_decision": None, "paper_win": None},
            "qualification": {"input_authenticity": False, "historical_parity": False,
                              "candidate_freeze_verified": False, "scientific_reproduction": False,
                              "scientific_improvement": False, "current_sota": "not_assessed"}}


def compare_candidate(protocol_path, reference, candidate, *, legacy_path=None):
    """Retain the full main panel and all test companions, with no scalar win."""
    source = load_legacy(legacy_path)
    axes, conditions = _axes(protocol_path, source)
    original, summaries = _full_main(reference, REFERENCE_SCHEMA, axes, conditions, source)
    proposed = _candidate(candidate, axes, source)
    result = _base(reference, candidate, axes, source, "candidate_against_original_main")
    comparisons, profiles = [], []
    for roi in axes["rois"]:
        new = proposed[roi]
        old_rows = [original[(condition, roi)] for condition in conditions]
        index = (max(range(99), key=lambda i: old_rows[i]["score"])
                 if all(row["score"] is not None for row in old_rows) else None)
        for model, old in zip(axes["models"], old_rows):
            defined = old["score"] is not None and new["score"] is not None
            comparisons.append({"roi": roi, "reference_model": model,
                                "delta": _difference(new["score"], old["score"]),
                                "selected_participant_deltas":
                                [a - b for a, b in zip(new["selected_subject_values"],
                                                      old["selected_subject_values"])] if defined else None})
        best = None if index is None else old_rows[index]["score"]
        profiles.append({"roi": roi, "candidate": new,
                         "strongest_reference_model": None if index is None else axes["models"][index],
                         "strongest_reference_score": best,
                         "delta_to_strongest": _difference(new["score"], best)})
    result.update(reference_conditions=summaries, noise_ceilings=reference["noise_ceilings"],
                  per_reference_comparisons=comparisons, roi_profile=profiles)
    result["counts"]["candidate_reference_deltas"] = len(comparisons)
    return result


def compare_reproduction(protocol_path, reference, reproduction, *, legacy_path=None):
    """Return every paired source-row difference; no tolerance or pass invented."""
    source = load_legacy(legacy_path)
    axes, conditions = _axes(protocol_path, source)
    original, summaries = _full_main(reference, REFERENCE_SCHEMA, axes, conditions, source)
    rerun, rerun_summaries = _full_main(reproduction, REPRODUCTION_SCHEMA, axes, conditions, source)
    require(reference["layer_catalog"] == reproduction["layer_catalog"],
            "reproduction must retain every original source layer identity/order")
    result = _base(reference, reproduction, axes, source, "reproduction_against_original_main")
    rows = []
    for condition in conditions:
        for roi in axes["rois"]:
            old, new = original[(condition, roi)], rerun[(condition, roi)]
            rows.append({"condition": condition, "roi": roi, "layers": old["layers"],
                         "participant_deltas": [[_difference(a, b) for a, b in zip(new_row, old_row)]
                                                for new_row, old_row in zip(new["subject_values"], old["subject_values"])],
                         "profile_delta": _difference(new["score"], old["score"]),
                         "reference_selected_layer": old["selected_layer"],
                         "reproduction_selected_layer": new["selected_layer"]})
    ceiling_deltas = [{"roi": old["roi"], "lower": _difference(new["lower"], old["lower"]),
                       "upper": _difference(new["upper"], old["upper"])}
                      for old, new in zip(reference["noise_ceilings"], reproduction["noise_ceilings"])]
    result.update(reference_conditions=summaries, reproduction_conditions=rerun_summaries,
                  per_source_row_comparisons=rows,
                  noise_ceilings={"reference": reference["noise_ceilings"],
                                  "reproduction": reproduction["noise_ceilings"], "deltas": ceiling_deltas})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("candidate", "reproduction"))
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--observed", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--legacy-component")
    args = parser.parse_args()
    source = load_legacy(args.legacy_component)
    function = compare_candidate if args.mode == "candidate" else compare_reproduction
    result = function(args.protocol, source.read_json(args.reference), source.read_json(args.observed),
                      legacy_path=args.legacy_component)
    with Path(args.output).open("x", encoding="utf-8") as handle:
        json.dump(result, handle, allow_nan=False, separators=(",", ":"))
        handle.write("\n")


if __name__ == "__main__":
    main()
