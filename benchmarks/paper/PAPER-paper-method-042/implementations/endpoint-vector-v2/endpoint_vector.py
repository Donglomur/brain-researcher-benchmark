#!/usr/bin/env python3
"""Four-subject REC comparison with joint shared-stimulus bootstrap diagnostics.

This is trusted operator scoring. It never reads native data or runs a model by
itself, and it does not decide paper superiority. See README.md for limits.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
from typing import Any

# Preserve and authenticate the reviewed first-box scorer; do not fork its math.
CORE_PATH = Path(__file__).resolve().parents[1] / "initial-evaluator-v1" / "grounding.py"
CORE_SHA256 = "1a9ae2432fd941ef531b5f1078731f1ce3ee3dd878311aaa17e729c9573c0014"
if hashlib.sha256(CORE_PATH.read_bytes()).hexdigest() != CORE_SHA256:
    raise RuntimeError("reviewed initial grounding scorer changed; re-review the v2 dependency")
spec = importlib.util.spec_from_file_location("umbrae_reviewed_grounding_v1", CORE_PATH)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

SUBJECTS = g.SUBJECTS
COMPARATORS = ("official_baseline", "neural_free", "shuffled_neural")
PUBLISHED_PERCENT = {"S1": 18.93, "S2": 18.27, "S5": 18.19, "S7": 16.74}


def _rows_by_key(rows: Any, images: set[str], label: str) -> dict[tuple[str, str], int]:
    g._require(isinstance(rows, list) and bool(rows), f"{label}: nonempty score rows required")
    keyed = {}
    for row in rows:
        g._require(isinstance(row, dict), f"{label}: score row must be an object")
        image, category = row.get("image_id"), row.get("category")
        g._require(isinstance(image, str) and image in images, f"{label}: unknown image")
        g._require(isinstance(category, str) and category in g.GROUPS["All"], f"{label}: unknown category")
        key = (image, category)
        g._require(key not in keyed, f"{label}: duplicate query")
        iou = row.get("iou")
        try:
            valid = type(iou) in (int, float) and math.isfinite(iou) and 0 <= iou <= 1
        except OverflowError:
            valid = False
        g._require(valid, f"{label}: IoU must be finite and in [0,1]")
        keyed[key] = int(iou > 0.5)
    return keyed


def compare_vectors(rows: dict[str, dict[str, list[dict]]], images: list[str],
                    *, draws: int = 1000, seed: int = 0, confidence: float = 0.95) -> dict:
    """Query-weighted percent scores and a 12-contrast bootstrap max-deviation band.

    Every draw selects shared images ONCE and uses those multiplicities for all
    subjects, arms and queries. The family is 4 subjects x 3 candidate contrasts.
    Empty-query images remain sampling units. Undefined zero-query draws are
    counted; no interval is issued if any occur (no silent conditioning).
    """
    g._require(type(draws) is int and 0 <= draws <= 10000, "draws must be integer 0..10000")
    g._require(type(seed) is int, "seed must be integer")
    g._require(type(confidence) in (int, float) and 0 < confidence < 1,
               "confidence must lie strictly between zero and one")
    g._require(isinstance(images, list) and bool(images)
               and all(isinstance(x, str) and x for x in images), "image IDs required")
    g._require(len(set(images)) == len(images), "duplicate image IDs")
    g._require(isinstance(rows, dict) and set(rows) == set(g.ROLES), "all four arms required")
    population = None
    keyed = {}
    for role in g.ROLES:
        g._require(isinstance(rows[role], dict) and set(rows[role]) == set(SUBJECTS),
                   f"{role}: exact S1/S2/S5/S7 panel required")
        keyed[role] = {}
        for subject in SUBJECTS:
            keyed[role][subject] = _rows_by_key(rows[role][subject], set(images), f"{role}/{subject}")
            keys = set(keyed[role][subject])
            if population is None:
                population = keys
            g._require(keys == population, f"{role}/{subject}: image/category population differs")
    # Canonicalize caller order so insertion order cannot change the seeded run.
    images = sorted(images)
    counts = Counter(image for image, _ in population)
    denominator = len(population)
    per_image = {image: [0] * (len(COMPARATORS) * len(SUBJECTS)) for image in images}
    labels = [(role, subject) for role in COMPARATORS for subject in SUBJECTS]
    for index, (role, subject) in enumerate(labels):
        for key in population:
            per_image[key[0]][index] += keyed["candidate"][subject][key] - keyed[role][subject][key]
    scores = {role: {subject: 100 * sum(keyed[role][subject].values()) / denominator
                     for subject in SUBJECTS} for role in g.ROLES}
    observed = [100 * sum(per_image[image][i] for image in images) / denominator
                for i in range(len(labels))]
    rng = random.Random(seed)
    deviations = []
    undefined = 0
    for _ in range(draws):
        multiplicities = Counter(rng.choices(images, k=len(images)))
        n = sum(multiplicities[image] * counts[image] for image in multiplicities)
        if n == 0:
            undefined += 1
            continue
        sample = [100 * sum(multiplicities[image] * per_image[image][i]
                            for image in multiplicities) / n for i in range(len(labels))]
        deviations.append(max(abs(x - y) for x, y in zip(sample, observed)))
    # Nearest-rank empirical quantile, without interpolation into an unobserved
    # tail. Approximate bootstrap coverage is not a finite-sample guarantee.
    radius = sorted(deviations)[math.ceil(confidence * len(deviations)) - 1] if deviations and not undefined else None
    status = "not_requested" if draws == 0 else "undefined_zero_query_resamples" if undefined else "computed_prospective_diagnostic"
    comparisons = {role: {} for role in COMPARATORS}
    for i, (role, subject) in enumerate(labels):
        delta = observed[i]
        comparisons[role][subject] = {
            "candidate_minus_comparator_percentage_points": delta,
            "simultaneous_interval_percentage_points": [max(-100.0, delta - radius), min(100.0, delta + radius)] if radius is not None else None,
        }
    return {
        "subject_order": list(SUBJECTS),
        "primary_endpoint": "All-category REC accuracy at strict IoU > 0.5",
        "score_unit": "percent", "difference_unit": "percentage_points",
        "query_count_per_subject": denominator, "shared_image_count": len(images),
        "empty_query_image_count": len(images) - len(counts),
        "scores_percent": scores,
        "candidate_contrasts": comparisons,
        "published_umbrae_v2_percent": PUBLISHED_PERCENT.copy(),
        "baseline_minus_published_percentage_points": {
            subject: scores["official_baseline"][subject] - PUBLISHED_PERCENT[subject]
            for subject in SUBJECTS},
        "bootstrap": {
            "method": "joint_shared_image_max_absolute_centered_deviation",
            "status": status, "confidence": confidence,
            "family": [{"comparator": role, "subject": subject} for role, subject in labels],
            "family_size": len(labels), "requested_draws": draws,
            "defined_draws": len(deviations), "undefined_zero_query_draws": undefined,
            "seed": seed, "radius_percentage_points": radius,
            "scope": "Prospective approximate simultaneous diagnostic over all 12 contrasts; conditional on these four trained subjects.",
        },
        "decision": "not_admitted: no effect margin, prospective analysis acceptance, native parity or competent author execution established",
    }


def evaluate(contract_path: Path, annotations_path: Path, image_order_path: Path,
             *, draws: int = 1000, seed: int = 0, confidence: float = 0.95) -> dict:
    # Reuse original source-grounded geometry, complete arm/exposure contract,
    # and first-box/missingness rules. Never report the v1 pooled contrast.
    report = g.evaluate(contract_path, annotations_path, image_order_path, bootstrap_draws=0, seed=seed)
    report.pop("paired_comparisons")
    report["component"] = "umbrae_endpoint_vector_v2"
    report["endpoint_vector"] = compare_vectors(report["row_scores"], list(g.read_json(image_order_path)),
                                                draws=draws, seed=seed, confidence=confidence)
    report["implementation_dependency_sha256"] = CORE_SHA256
    report["holds"] = report["holds"] + [
        "The simultaneous bootstrap is a prospective diagnostic, not an accepted scientific decision rule.",
        "Published v2 values are documentary; a run named official_baseline is not execution attestation.",
    ]
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--image-order", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--draws", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--confidence", type=float, default=0.95)
    args = parser.parse_args()
    try:
        result = evaluate(args.contract, args.annotations, args.image_order, draws=args.draws,
                          seed=args.seed, confidence=args.confidence)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write("\n")
    except (g.ContractError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"endpoint vector evaluation rejected: {exc}\n")


if __name__ == "__main__":
    main()
