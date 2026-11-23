"""Compare candidate and ICNet predictions on the matched original Fig. 4 panel.

This is a descriptive equation component. Shared hashes establish byte identity,
not authentic source data, a recovered baseline, protected exposure or a paper win.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

SCORER_SHA256 = "6059486fcf3cf1c07c53fb1c214e5f5f76ded53995757c329d6ada557b812bae"
METRICS = ("correlation_explained_percent", "variance_explained_percent")
SHARED_PREPARATION = ("source_mask_sha256", "alignment_protocol_sha256",
                      "measurement_times_sha256", "mask_origin", "split")
ROLES = ("baseline", "candidate")


def _scorer():
    path = Path(__file__).with_name("scorer.py")
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != SCORER_SHA256:
        raise ValueError("source-equation scorer pin changed")
    spec = importlib.util.spec_from_loader("icnet_candidate_equations", loader=None)
    module = importlib.util.module_from_spec(spec)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def _mapping(value, label):
    if type(value) is not dict:
        raise ValueError(label + " must be an object")
    return value


def _cases(panel, scorer):
    cases = panel.get("cases")
    expected = {(animal, sound) for animal in scorer.ANIMALS for sound in scorer.SOUNDS}
    if type(cases) is not list or len(cases) != len(expected):
        raise ValueError("each model requires all 28 original cases")
    indexed = {}
    for case in cases:
        _mapping(case, "case")
        animal, sound = case.get("animal"), case.get("sound")
        if type(animal) is not int or type(sound) is not str:
            raise ValueError("case identity must be an original animal and sound")
        key = (animal, sound)
        if key not in expected or key in indexed:
            raise ValueError("duplicate or foreign animal/sound case")
        bins, times = case.get("time_bins"), case.get("measurement_times_seconds")
        if type(bins) is not int or bins < 2:
            raise ValueError("at least two original time bins required")
        if (type(times) is not list or len(times) != 2
                or any(type(t) not in (int, float) or not math.isfinite(t) or t < 0 for t in times)):
            raise ValueError("both trial-specific measurement times required")
        arrays = _mapping(case.get("arrays"), "case arrays")
        if set(arrays) != set(scorer.ARRAY_NAMES):
            raise ValueError("both recorded, sampled and expected-count trials required")
        for descriptor in arrays.values():
            if (type(descriptor) is not dict or set(descriptor) != {"path", "sha256"}
                    or type(descriptor["path"]) is not str
                    or not scorer._sha(descriptor["sha256"])):
                raise ValueError("each array requires a path and SHA256")
        indexed[key] = case
    return indexed


def _matched_panels(manifest, scorer):
    """Reject mismatched declarations before opening or scoring any arrays."""
    if (type(manifest) is not dict
            or set(manifest) != {"schema", *ROLES}
            or manifest["schema"] != "icnet-candidate-comparison-input/v1"):
        raise ValueError("unsupported candidate comparison input")
    panels, indexed = {}, {}
    for role in ROLES:
        entry = _mapping(manifest[role], role)
        if set(entry) != {"panel", "provenance"}:
            raise ValueError("each model requires panel and provenance")
        provenance = _mapping(entry["provenance"], "model provenance")
        if (set(provenance) != {"model_sha256", "prediction_protocol_sha256", "stochastic_policy"}
                or not all(scorer._sha(provenance[key]) for key in
                           ("model_sha256", "prediction_protocol_sha256"))
                or type(provenance["stochastic_policy"]) is not str
                or not provenance["stochastic_policy"].strip()):
            raise ValueError("model/protocol pins and explicit stochastic policy required for each model")
        panel = _mapping(entry["panel"], "panel")
        if panel.get("schema") != "icnet-source-equations-input/v1":
            raise ValueError("both models require a source-equations panel")
        ddof = panel.get("variance_ddof")
        if type(ddof) is not int or ddof not in (0, 1):
            raise ValueError("an explicit variance divisor is required")
        preparation = _mapping(panel.get("preparation"), "preparation")
        for key in (*SHARED_PREPARATION[:3], "prediction_freeze_sha256"):
            if not scorer._sha(preparation.get(key)):
                raise ValueError("missing preparation pin: " + key)
        if (preparation.get("mask_origin") != "source_broadband_noise_reliability"
                or preparation.get("split") != "original_four_sounds_held_out_from_training"):
            raise ValueError("the original mask origin and split are required")
        _mapping(panel.get("animals"), "animals")
        panels[role], indexed[role] = panel, _cases(panel, scorer)
    baseline, candidate = (panels[role] for role in ROLES)
    if baseline["variance_ddof"] != candidate["variance_ddof"]:
        raise ValueError("models must use the same variance divisor")
    if baseline["animals"] != candidate["animals"]:
        raise ValueError("original ordered unit identities and source masks must match")
    if any(baseline["preparation"][key] != candidate["preparation"][key]
           for key in SHARED_PREPARATION):
        raise ValueError("source mask, alignment, measurement-time and split declarations must match")
    for key, left in indexed["baseline"].items():
        right = indexed["candidate"][key]
        if (left["time_bins"] != right["time_bins"]
                or left["measurement_times_seconds"] != right["measurement_times_seconds"]):
            raise ValueError("temporal support and trial measurement times must match")
        for role in ("recorded_trial1", "recorded_trial2"):
            if left["arrays"][role]["sha256"] != right["arrays"][role]["sha256"]:
                raise ValueError("both models must be scored against the same recorded trial bytes")
    return panels


def _difference(baseline, candidate):
    return {metric: (None if baseline[metric] is None or candidate[metric] is None
                     else candidate[metric] - baseline[metric]) for metric in METRICS}


def compare_panel(manifest, input_root):
    """Return complete paired vectors; no aggregate superiority decision."""
    scorer = _scorer()
    panels = _matched_panels(manifest, scorer)
    reports = {role: scorer.score_panel(panels[role], input_root) for role in ROLES}
    baseline_cases = {(case["animal"], case["sound"]): case
                      for case in reports["baseline"]["cases"]}
    cases = []
    for candidate in reports["candidate"]["cases"]:
        baseline = baseline_cases[(candidate["animal"], candidate["sound"])]
        if any(baseline[key] != candidate[key] for key in
               ("time_bins", "original_units", "eligible_units", "variance_ddof")):
            raise ValueError("scored support differs between models")
        if len(baseline["by_unit"]) != len(candidate["by_unit"]):
            raise ValueError("scored unit populations differ between models")
        units = []
        for left, right in zip(baseline["by_unit"], candidate["by_unit"]):
            identity = (left["unit_id"], left["column_zero_based"])
            if identity != (right["unit_id"], right["column_zero_based"]):
                raise ValueError("scored unit order differs between models")
            units.append({"unit_id": identity[0], "column_zero_based": identity[1],
                          "baseline": left, "candidate": right,
                          "candidate_minus_baseline_percentage_points": _difference(left, right)})
        cases.append({
            "animal": candidate["animal"], "sound": candidate["sound"],
            "measurement_times_seconds": candidate["measurement_times_seconds"],
            "time_bins": candidate["time_bins"], "original_units": candidate["original_units"],
            "eligible_units": candidate["eligible_units"],
            "fig4d_time_only_unit_vector": units,
            "fig4b_flattened_companion": {
                "baseline": baseline["flattened"], "candidate": candidate["flattened"],
                "candidate_minus_baseline_percentage_points":
                    _difference(baseline["flattened"], candidate["flattened"])}
        })
    return {
        "schema": "icnet-candidate-comparison-result/v1",
        "qualification": "matched_equation_component_only",
        "scorer_sha256": SCORER_SHA256,
        "metric_scope": "Fig4d time-only per-unit vectors; Fig4b flattened per-animal companions",
        "reference_role": "operator-declared source ICNet baseline; authenticity unverified",
        "source_paper_comparator_context": "The original Fig4d comparator was Poisson LNP; this component compares a candidate with ICNet.",
        "variance_ddof": panels["baseline"]["variance_ddof"],
        "shared_preparation": {key: panels["baseline"]["preparation"][key] for key in SHARED_PREPARATION},
        "models": {role: {"provenance": manifest[role]["provenance"],
                          "prediction_freeze_sha256": panels[role]["preparation"]["prediction_freeze_sha256"]}
                   for role in ROLES},
        "n_animals": 7, "n_sounds": 4, "eligible_units": 3476, "cases": cases,
        "difference_direction": "positive means the candidate exceeds the baseline for that unit/animal and metric",
        "inference": "descriptive paired differences; no animal-level uncertainty, scalar reduction or superiority decision",
        "unverified": ["authentic original observations, masks and alignment",
                       "source ICNet checkpoint and baseline numerical parity",
                       "original training access and held-out evaluation protection",
                       "historical variance and stochastic conventions",
                       "prespecified stochastic replication, uncertainty and meaningful improvement rule"],
        "model_provenance_authenticated": False,
        "native_author_baseline_reproduced": False,
        "reproduction_evaluated": False, "improvement_evaluated": False,
        "paper_win_evaluated": False,
    }


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON field: " + key)
        value[key] = item
    return value


def _nonfinite(value):
    raise ValueError("nonfinite JSON literal: " + value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    body = args.manifest.read_bytes()
    manifest = json.loads(body, object_pairs_hook=_unique_object, parse_constant=_nonfinite)
    report = compare_panel(manifest, args.input_root)
    report["input_manifest_sha256"] = hashlib.sha256(body).hexdigest()
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
