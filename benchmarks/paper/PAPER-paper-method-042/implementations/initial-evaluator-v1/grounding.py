#!/usr/bin/env python3
"""BrainHub REC scoring with identity joins and paired stimulus controls.

This evaluates existing operator-supplied outputs. It never runs a model or
fetches annotations. See the accompanying scope note before native use.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
from typing import Any

TASK = "PAPER-paper-method-042"
BRAINHUB_REVISION = "4838666f1a04d0521c2184fa50b5b77e7e7ac5ee"
IMAGE_TENSOR_SHA256 = "1a313a2d4796f14aa4a930afb0ce94a1080ae9ea0482862f597a1b0afd539078"
SUBJECTS = ("S1", "S2", "S5", "S7")
ROLES = ("candidate", "official_baseline", "neural_free", "shuffled_neural")
THRESHOLDS = (0.3, 0.5, 0.7)
# Class names and group membership are facts from the pinned BrainHub category map.
CREATURES = "person|bird|cat|dog|horse|sheep|cow|elephant|bear|zebra|giraffe".split("|")
OBJECTS = "bicycle|car|motorcycle|airplane|bus|train|truck|boat|bench|chair|couch|bed|dining table|toilet|sink|refrigerator|clock".split("|")
INCONSPICUOUS = "traffic light|fire hydrant|stop sign|parking meter|backpack|umbrella|handbag|tie|suitcase|frisbee|skis|snowboard|sports ball|kite|baseball bat|baseball glove|skateboard|surfboard|tennis racket|bottle|wine glass|cup|fork|knife|spoon|bowl|banana|apple|sandwich|orange|broccoli|carrot|hot dog|pizza|donut|cake|potted plant|tv|laptop|mouse|remote|keyboard|cell phone|microwave|oven|toaster|book|vase|scissors|teddy bear|hair drier|toothbrush".split("|")
GROUPS = {"All": frozenset(CREATURES + OBJECTS + INCONSPICUOUS),
          "Salient": frozenset(CREATURES + OBJECTS),
          "Salient Creatures": frozenset(CREATURES),
          "Salient Objects": frozenset(OBJECTS),
          "Inconspicuous": frozenset(INCONSPICUOUS)}
HOLDS = [
    "No authentic NSD/model/reference execution or scientific qualification is established.",
    "Operator-provided image order and native annotation bytes require independent source qualification.",
    "Declared exposure matching does not prove actual model, image, language-prior or training exposure.",
    "Control checkpoint pairing and neural interventions are declarations; execution fidelity remains unverified.",
    "NSD/stimulus, annotation and pretrained-model rights remain separately gated.",
    "Captioning, retrieval, adaptation and whole-paper reproduction remain outside this component.",
    "Protected candidate isolation, baseline competence and reference numerical agreement remain unverified.",
]


class ContractError(ValueError):
    """A reference, population or comparison contract is inconsistent."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj = {}
    for key, value in pairs:
        _require(key not in obj, f"duplicate JSON key: {key}")
        obj[key] = value
    return obj


def _parse_json(payload: bytes) -> Any:
    def invalid(value: str) -> None:
        raise ContractError(f"non-finite JSON number: {value}")
    return json.loads(payload.decode("utf-8"), object_pairs_hook=_pairs,
                      parse_constant=invalid)


def read_json(path: Path) -> Any:
    return _parse_json(path.read_bytes())


def read_json_snapshot(path: Path) -> tuple[Any, dict[str, Any]]:
    """Parse and identify the same bytes, even if the input is later replaced."""
    payload = path.read_bytes()
    return _parse_json(payload), {"sha256": hashlib.sha256(payload).hexdigest(),
                                 "bytes": len(payload)}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest(value: Any, name: str) -> str:
    _require(isinstance(value, str) and len(value) == 64 and
             all(c in "0123456789abcdef" for c in value), f"{name}: SHA256 required")
    return value


def box(value: Any, *, reference: bool) -> tuple[float, float, float, float]:
    _require(isinstance(value, list) and len(value) == 4, "box must be xyxy length four")
    try:
        finite = all(type(x) in (int, float) and math.isfinite(x) for x in value)
    except OverflowError:
        finite = False
    _require(finite, "box coordinates must be finite representable numbers")
    x1, y1, x2, y2 = (float(x) for x in value)
    _require(all(0 <= x <= 1 for x in (x1, y1, x2, y2)), "box coordinates must be normalized to [0,1]")
    _require(x1 <= x2 and y1 <= y2, "box corners must be ordered")
    if reference:
        _require(x1 < x2 and y1 < y2 and (x2 - x1) * (y2 - y1) > 0,
                 "reference box must have representably positive area")
    return x1, y1, x2, y2


def intersection_over_union(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    intersection = max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return intersection / (area_a + area_b - intersection)


def prepare_reference(annotations: Any, image_order: Any, profile: str) -> dict[tuple[str, str], tuple[float, ...]]:
    _require(profile in ("engineering_controls", "paper_population"), "unknown population profile")
    _require(isinstance(annotations, dict) and bool(annotations), "annotations must be a nonempty image object")
    _require(isinstance(image_order, dict) and bool(image_order), "image_order must be a nonempty image-to-stimulus object")
    _require(all(isinstance(v, str) and v for v in image_order.values()), "stimulus identities must be nonempty strings")
    _require(len(set(image_order.values())) == len(image_order), "image_order stimulus identities must be unique")
    _require(set(annotations) == set(image_order), "annotation membership must equal pinned image order")
    _require(set(image_order) == {str(i) for i in range(len(image_order))}, "native image indices must be contiguous strings starting at zero")
    if profile == "paper_population":
        _require(len(image_order) == 982, "paper population must preserve all 982 shared images")
    targets = {}
    for image_id in sorted(annotations, key=int):
        categories = annotations[image_id]
        _require(isinstance(categories, dict), f"{image_id}: categories must be an object")
        for category, boxes in categories.items():
            _require(category in GROUPS["All"], f"unknown COCO category: {category}")
            _require(isinstance(boxes, list) and bool(boxes), "reference category must contain boxes")
            validated = [box(b, reference=True) for b in boxes]
            targets[(image_id, category)] = validated[0]
    _require(bool(targets), "empty query population")
    if profile == "paper_population":
        total_boxes = sum(len(boxes) for categories in annotations.values() for boxes in categories.values())
        _require(total_boxes == 5829, "paper population must preserve all 5829 annotated boxes")
    return targets


def _prediction(value: Any) -> tuple[tuple[float, ...] | None, str]:
    if value is None:
        return None, "missing"
    if value == []:
        return None, "empty_extraction"
    try:
        _require(isinstance(value, list) and len(value) > 0 and isinstance(value[0], list)
                 and len(value[0]) > 0, "expected extracted group/box nesting")
        return box(value[0][0], reference=False), "valid"
    except ContractError:
        return None, "invalid_extraction"


def score_subject(targets: dict, images: set[str], responses: Any) -> list[dict[str, Any]]:
    _require(isinstance(responses, dict), "responses must be an image object")
    _require(set(responses) <= images, "unexpected prediction image IDs")
    expected = {image: {category for i, category in targets if i == image} for image in images}
    for image, categories in responses.items():
        _require(isinstance(categories, dict), "response image must map category to extracted boxes")
        _require(set(categories) <= expected[image], "unexpected prediction category")
    rows = []
    for (image, category), target in targets.items():
        predicted, status = _prediction(responses.get(image, {}).get(category))
        iou = 0.0 if predicted is None else intersection_over_union(predicted, target)
        rows.append({"image_id": image, "category": category, "iou": iou, "prediction_status": status})
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for name, categories in GROUPS.items():
        chosen = [row for row in rows if row["category"] in categories]
        n = len(chosen)
        result[name] = {"query_count": n, "mean_iou": statistics.fmean(r["iou"] for r in chosen) if n else None,
                        "accuracy": {str(t): sum(r["iou"] > t for r in chosen) / n if n else None for t in THRESHOLDS},
                        "missing_or_invalid": sum(r["prediction_status"] != "valid" for r in chosen)}
    return result


def _percentile(values: list[float], q: float) -> float:
    values = sorted(values)
    position = (len(values) - 1) * q
    lo, hi = math.floor(position), math.ceil(position)
    return values[lo] + (values[hi] - values[lo]) * (position - lo)


def paired_image_bootstrap(candidate: dict[str, list[dict]], comparator: dict[str, list[dict]],
                           images: list[str], draws: int, seed: int) -> dict[str, Any]:
    """Resample shared target-image clusters, keeping subjects and categories together."""
    _require(type(draws) is int and 0 <= draws <= 10000, "bootstrap draws must be integer 0..10000")
    _require(type(seed) is int, "bootstrap seed must be integer")
    per_image = {image: [0, 0] for image in images}
    subjects = sorted(candidate)
    _require(subjects == sorted(comparator), "paired subject population differs")
    for subject in subjects:
        left = {(r["image_id"], r["category"]): r for r in candidate[subject]}
        right = {(r["image_id"], r["category"]): r for r in comparator[subject]}
        _require(left.keys() == right.keys(), "paired query population differs")
        for (image, category), row in left.items():
            per_image[image][0] += int(row["iou"] > .5) - int(right[(image, category)]["iou"] > .5)
            per_image[image][1] += 1
    observed = sum(v[0] for v in per_image.values()) / sum(v[1] for v in per_image.values())
    samples = []
    rng = random.Random(seed)
    for _ in range(draws):
        selected = rng.choices(images, k=len(images))
        denominator = sum(per_image[i][1] for i in selected)
        if denominator:
            samples.append(sum(per_image[i][0] for i in selected) / denominator)
    return {"delta_accuracy_at_0.5": observed,
            "image_cluster_percentile_95_interval": [_percentile(samples, .025), _percentile(samples, .975)] if samples else None,
            "requested_draws": draws, "valid_draws": len(samples), "seed": seed,
            "scope": "Paired shared-stimulus uncertainty conditional on these four subjects; no new-subject inference."}


def validate_design(contract: Any, image_order: dict[str, str]) -> None:
    _require(isinstance(contract, dict), "contract must be an object")
    _require(contract.get("task_id") == TASK, "wrong task ID")
    _require(contract.get("subject_design") == "shared_subjects_1_2_5_7", "only the shared-subject stimulus-held-out design is implemented")
    _require(contract.get("brainhub_revision") == BRAINHUB_REVISION, "BrainHub revision mismatch")
    _require(contract.get("all_images_sha256") == IMAGE_TENSOR_SHA256, "all_images.pt content identity mismatch")
    _digest(contract.get("annotations_sha256"), "annotations_sha256")
    _digest(contract.get("image_order_sha256"), "image_order_sha256")
    exposure = contract.get("exposure")
    _require(isinstance(exposure, dict), "exposure object required")
    for key in ("training_neural_sha256", "pretrained_language_sha256", "pretrained_image_sha256", "prompt_sha256"):
        _digest(exposure.get(key), key)
    _require(exposure.get("training_subjects") == list(SUBJECTS), "declare training subjects S1,S2,S5,S7; this is not a subject-held-out design")
    training = exposure.get("training_stimulus_ids")
    _require(isinstance(training, list) and all(isinstance(x, str) and x for x in training), "training stimulus IDs required")
    _require(len(set(training)) == len(training), "duplicate training stimulus IDs")
    _require(not set(training) & set(image_order.values()), "training/evaluation stimulus overlap")
    _require(type(exposure.get("training_presentations")) is int and exposure["training_presentations"] >= 0, "nonnegative training presentation count required")
    if contract.get("profile") == "paper_population":
        _require(len(training) > 0 and exposure["training_presentations"] > 0, "native comparison requires declared nonempty training exposure")
    runs = contract.get("runs")
    _require(isinstance(runs, dict) and set(runs) == set(ROLES), "candidate, official_baseline, neural_free and shuffled_neural runs required")
    expected_condition = {"candidate": "observed", "official_baseline": "observed", "neural_free": "none", "shuffled_neural": "permuted"}
    for role, run in runs.items():
        _require(isinstance(run, dict) and isinstance(run.get("model_id"), str) and run["model_id"], f"{role}: model identity required")
        _digest(run.get("checkpoint_sha256"), f"{role}: checkpoint_sha256")
        _require(run.get("exposure") == exposure, f"{role}: unmatched declared neural/data/prior exposure")
        _require(run.get("neural_condition") == expected_condition[role], f"{role}: wrong neural condition")
        _require(isinstance(run.get("responses"), dict) and set(run["responses"]) == set(SUBJECTS), f"{role}: all four subjects required")
        _require(all(isinstance(p, str) and p for p in run["responses"].values()), f"{role}: response paths required")
    for role in ("neural_free", "shuffled_neural"):
        _require(runs[role].get("control_of") == "candidate", f"{role}: control must declare candidate pairing")
        _require(runs[role]["checkpoint_sha256"] == runs["candidate"]["checkpoint_sha256"], f"{role}: control checkpoint differs from candidate")
    shuffled = runs["shuffled_neural"].get("source_image_by_target")
    _require(isinstance(shuffled, dict) and set(shuffled) == set(SUBJECTS), "shuffle mapping required for each subject")
    for subject, mapping in shuffled.items():
        _require(isinstance(mapping, dict) and set(mapping) == set(image_order), f"{subject}: incomplete shuffle targets")
        _require(all(isinstance(v, str) for v in mapping.values()) and set(mapping.values()) == set(image_order), f"{subject}: shuffle must be a within-subject bijection")
        _require(all(k != v for k, v in mapping.items()), f"{subject}: shuffled-neural control has fixed images")


def evaluate(contract_path: Path, annotations_path: Path, image_order_path: Path,
             *, bootstrap_draws: int = 1000, seed: int = 0) -> dict[str, Any]:
    contract, contract_pin = read_json_snapshot(contract_path)
    annotations, annotations_pin = read_json_snapshot(annotations_path)
    image_order, image_order_pin = read_json_snapshot(image_order_path)
    _require(isinstance(contract, dict), "contract must be an object")
    targets = prepare_reference(annotations, image_order, contract.get("profile"))
    validate_design(contract, image_order)
    _require(annotations_pin["sha256"] == contract["annotations_sha256"], "annotation bytes do not match contract pin")
    _require(image_order_pin["sha256"] == contract["image_order_sha256"], "image order bytes do not match contract pin")
    scores, rows, input_pins = {}, {}, {}
    for role in ROLES:
        rows[role], scores[role], input_pins[role] = {}, {}, {}
        for subject in SUBJECTS:
            path = contract_path.parent / contract["runs"][role]["responses"][subject]
            responses, response_pin = read_json_snapshot(path)
            rows[role][subject] = score_subject(targets, set(image_order), responses)
            scores[role][subject] = summarize(rows[role][subject])
            input_pins[role][subject] = response_pin
    comparisons = {role: paired_image_bootstrap(rows["candidate"], rows[role], sorted(image_order, key=int), bootstrap_draws, seed)
                   for role in ROLES if role != "candidate"}
    return {"task_id": TASK, "component": "brainhub_rec_grounding_v1", "profile": contract["profile"],
            "primary_endpoint": "All-category REC accuracy at strict IoU > 0.5, reported separately for S1/S2/S5/S7",
            "qualification": "unknown", "authentic_reference_run": False,
            "population": {"subjects": list(SUBJECTS), "shared_images": len(image_order), "queries_per_subject": len(targets),
                           "observed_class_count": len({category for _, category in targets}),
                           "ontology_class_count": len(GROUPS["All"]),
                           "all_annotation_boxes": sum(len(boxes) for cats in annotations.values() for boxes in cats.values())},
            "source_revision": BRAINHUB_REVISION, "input_pins": {"contract_sha256": contract_pin["sha256"],
            "annotations_sha256": annotations_pin["sha256"], "image_order_sha256": image_order_pin["sha256"], "responses": input_pins},
            "scores": scores, "paired_comparisons": comparisons, "holds": HOLDS,
            "exposure_status": "matching declarations only; no execution attestation",
            "row_scores": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--image-order", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bootstrap-draws", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    try:
        result = evaluate(args.contract, args.annotations, args.image_order, bootstrap_draws=args.bootstrap_draws, seed=args.seed)
    except (ContractError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"grounding evaluation rejected: {exc}\n")
    # Never overwrite inputs or an existing result accidentally.
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2, allow_nan=False)
        output.write("\n")


if __name__ == "__main__":
    main()
