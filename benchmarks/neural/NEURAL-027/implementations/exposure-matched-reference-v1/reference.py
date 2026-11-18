"""Frozen NEURAL-027 Gaussian comparator with exactly the direct prompt exposure.

Consumes public direct packets only. No source arrays, private targets, participant
execution, network access, or scientific admission are supplied by this module.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import math
from pathlib import Path


DELIVERY_SHA256 = "2861dde9010d2d47f8870b0748f912a163f267b278f18872dfb09bcbfdb346f8"
DELIVERY_PATH = Path(__file__).resolve().parents[1] / "direct-packets-v1" / "delivery.py"
if hashlib.sha256(DELIVERY_PATH.read_bytes()).hexdigest() != DELIVERY_SHA256:
    raise RuntimeError("reviewed direct-packet implementation changed")
_spec = importlib.util.spec_from_file_location("neural027_matched_delivery", DELIVERY_PATH)
delivery = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(delivery)
base = delivery.base
SCHEMA = "neural027-exposure-matched-reference/v1"


def predict(packet):
    """Return complete responses using only the displayed examples and features.

    Original direct-packet construction requires equal counts in every selected
    training-mouse/class cell. Consequently every displayed example has the same
    weight in the existing Reference recipe. An internal pool ID below is only a
    fitting-API adapter; it is never an animal identity or a scoring unit.
    """
    delivery.validate_packet(packet)
    classes = packet["classes_in_probability_order"]
    examples = packet["demonstrations"]
    items = packet["items"]
    if not examples:
        return [{"item_id": row["item_id"], "probabilities": [1 / len(classes)] * len(classes)}
                for row in items]
    counts = Counter(row["label"] for row in examples)
    delivery.require(set(counts) == set(classes) and len(set(counts.values())) == 1,
                     "displayed demonstrations must cover all classes equally")
    modality = "neural" if packet["observation_condition"] == "neural" else "context"
    train = [{"item_id": f"displayed-example-{i}", "mname": "equal_weight_fitting_pool",
              "phase": "displayed_training", "label": row["label"], modality: list(row["values"])}
             for i, row in enumerate(examples)]
    # Reference.predict accepts an allowlisted two-field interface. The unused
    # modality is empty, so no observation from the other arm is introduced.
    queries = [{"item_id": row["item_id"], "neural": [], "context": [],
                modality: list(row["values"])} for row in items]
    model = base.Reference(classes, modality).fit(train)
    for name in ("mean", "scale", "centroids", "variance"):
        base.finite(getattr(model, name), "fitted reference " + name)
    responses = model.predict(queries)
    delivery.require(all(len(row["probabilities"]) == len(classes) and
                         all(math.isfinite(p) and 0 <= p <= 1 for p in row["probabilities"]) and
                         abs(sum(row["probabilities"]) - 1) <= 1e-8 for row in responses),
                     "reference produced invalid probabilities")
    return responses


def predict_pair(public):
    """Bind both public conditions before producing any output; no gold is read."""
    delivery.require(isinstance(public, dict) and set(public) == set(delivery.FEATURES),
                     "both public observation conditions required")
    for arm, packet in public.items():
        delivery.validate_packet(packet)
        delivery.require(packet["observation_condition"] == arm, "observation condition mismatch")
    neural, control = public["neural"], public["movement_position"]
    for key in ("classes_in_probability_order", "demonstration_condition"):
        delivery.require(neural[key] == control[key], "paired class/exposure condition mismatch")
    delivery.require([r["item_id"] for r in neural["items"]] ==
                     [r["item_id"] for r in control["items"]], "paired query identities mismatch")
    delivery.require([r["label"] for r in neural["demonstrations"]] ==
                     [r["label"] for r in control["demonstrations"]],
                     "paired displayed demonstration targets mismatch")
    responses = {arm: predict(public[arm]) for arm in delivery.FEATURES}
    report = {
        "schema": SCHEMA, "task_id": "NEURAL-027",
        "role": "public_demonstration_matched_numerical_reference",
        "recipe": "uniform_probabilities" if not neural["demonstrations"] else
                  "existing_diagonal_gaussian_on_displayed_examples_only",
        "demonstrations_per_condition": len(neural["demonstrations"]),
        "queries_per_condition": len(neural["items"]),
        "public_sha256": {arm: delivery.digest(public[arm]) for arm in delivery.FEATURES},
        "response_sha256": {arm: delivery.digest(responses[arm]) for arm in delivery.FEATURES},
        "delivery_sha256": DELIVERY_SHA256, "evaluator_sha256": delivery.BASE_SHA256,
        "scientific_qualification": "not_established", "participant_execution": False,
        "limits": [
            "This is a fitted numerical reference, not native/direct interpretation or a participant runner.",
            "Only displayed examples are fitted; the previous full-training reference is a different exposure condition.",
            "Public class balance does not authenticate original mouse balance or source provenance; retain the operator-private frozen binding.",
            "Grade with the unchanged direct collector, which checks its frozen public hashes and original biological groups.",
            "No authentic input, complete cohort, source-export equality, protected isolation or reference competence is established."
        ],
    }
    return responses, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    public_dir, output_dir = args.public_dir.resolve(), args.output_dir.resolve()
    delivery.require(public_dir != output_dir and public_dir not in output_dir.parents and
                     output_dir not in public_dir.parents, "input and output directories must be disjoint")
    delivery.require(not output_dir.exists(), "output directory must be new")
    packets = {arm: delivery.read_json(public_dir / (arm + ".json")) for arm in delivery.FEATURES}
    responses, report = predict_pair(packets)
    output_dir.mkdir(parents=True, mode=0o700)
    for arm, values in responses.items():
        delivery.write_new(output_dir / (arm + "-responses.json"), values)
    delivery.write_new(output_dir / "reference.json", report)


if __name__ == "__main__":
    main()
