"""Operator-only paired direct/viewer grading using the existing worm scorer.

All public collections and session audits are admitted before private targets.
This source does not enforce participant isolation or qualify native inputs.
"""
import argparse
import copy
import importlib
import importlib.util
import math
from pathlib import Path


def _paired_differences(delivery, grades):
    """Equal-animal descriptive differences; positive BA and negative loss favor viewer."""
    direct = grades["direct_observation"]
    viewer = grades["typed_viewer"]
    delivery.io.need(direct["status"] == viewer["status"] == "scored" and
                     direct["packet_id"] == viewer["packet_id"] and
                     direct["animals"] == viewer["animals"], "Same complete scored panel")
    rows = []
    delivery.io.need(len(direct["groups"]) == len(viewer["groups"]) == direct["animals"],
                     "Complete paired animal support")
    for left, right in zip(direct["groups"], viewer["groups"]):
        delivery.io.need(all(left[key] == right[key] for key in
                             ("fold_id", "test_group", "events", "class_counts")),
                         "Exact paired animal, events and class support")
        arms = {}
        for arm in delivery.CHANNELS:
            left_ba, right_ba = (item["arms"][arm]["balanced_accuracy"] for item in (left, right))
            delivery.io.need((left_ba is None) == (right_ba is None), "Shared defined BA support")
            arms[arm] = {
                "balanced_accuracy_difference": None if left_ba is None else right_ba - left_ba,
                "log_loss_difference": right["arms"][arm]["log_loss"] - left["arms"][arm]["log_loss"],
            }
        rows.append({key: left[key] for key in ("fold_id", "test_group", "events", "class_counts")}
                    | {"arms": arms})
    macro = {}
    for arm in delivery.CHANNELS:
        values = [row["arms"][arm] for row in rows]
        ba = [row["balanced_accuracy_difference"] for row in values]
        macro[arm] = {
            "balanced_accuracy_difference": None if any(value is None for value in ba)
            else math.fsum(ba) / len(ba),
            "log_loss_difference": math.fsum(row["log_loss_difference"] for row in values) / len(values),
        }
    return {"contrast": "typed_viewer_minus_direct_observation", "aggregation_unit": "animal",
            "animals": len(rows), "groups": rows, "animal_macro": macro,
            "primary_N_balanced_accuracy_difference": macro["N"]["balanced_accuracy_difference"],
            "co_primary_N_log_loss_difference": macro["N"]["log_loss_difference"],
            "interpretation": "Positive balanced accuracy or negative log loss favors the viewer descriptively.",
            "uncertainty": None,
            "uncertainty_limit": "No new paired uncertainty estimator or superiority rule is introduced. "
            "The original per-condition intervals remain descriptive under overlapping training folds."}


def compare_paired(delivery, audit_collection, score, panel, contexts, responses, audits, load_private):
    """Grade two complete audited conditions after joint admission.

    Dependencies and load_private are trusted operator functions, never participant
    selections. The external target loader is called once only after both complete
    conditions are accepted. Each unchanged scorer then calls its cached provider.
    """
    paired = audit_collection.collect_paired_audited(delivery, panel, contexts, responses, audits)
    submissions = copy.deepcopy({mode: paired["collections"][mode]["collection"]["submission"]
                                 for mode in delivery.MODES})
    abstentions = {mode: delivery.admit(panel, submissions[mode])[1] for mode in delivery.MODES}
    common = {"schema": "neural047-paired-observation-grade-v1", "packet_id": panel["packet_id"],
              "protocol_pin": paired["protocol_pin"], "collection_pin": delivery.digest(paired),
              "modes": list(delivery.MODES), "scientific_success": None,
              "runtime_verified": False, "native_input_qualified": False,
              "condition_limit": "Direct numeric histories versus typed numerical histories with SVG; "
              "not an image-only viewer condition. Isolation, authentic inputs and model provenance are external."}
    if any(abstentions.values()):
        return {**common, "status": "abstained", "private_target_loads": 0,
                "scorer_cached_target_callbacks": 0, "grades": None, "paired_differences": None,
                "abstained_contexts": {mode: [{"fold_id": fold, "arm": arm} for fold, arm in values]
                                       for mode, values in abstentions.items()},
                "reason": "At least one required condition/fold/arm abstained; no subset or one-mode grade."}
    # A target loader cannot mutate the admitted public objects between conditions.
    frozen_panel = copy.deepcopy(panel)
    private = copy.deepcopy(load_private())
    callbacks = 0

    def cached():
        nonlocal callbacks
        callbacks += 1
        return private

    grades = {mode: score(frozen_panel, submissions[mode], cached) for mode in delivery.MODES}
    return {**common, "status": "scored", "private_target_loads": 1,
            "scorer_cached_target_callbacks": callbacks, "grades": grades,
            "paired_differences": _paired_differences(delivery, grades)}


def _load_sources():
    here = Path(__file__).resolve().parent

    def load(name, filename):
        spec = importlib.util.spec_from_file_location(name, here / filename)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    delivery = load("neural047_pair_delivery", "delivery.py")
    audit = load("neural047_pair_audits", "audit_collection.py")
    scorer = importlib.import_module(delivery.public_contract.__module__)
    return delivery, audit, scorer.score


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("panel", "contexts", "responses", "audits", "private-targets", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    delivery, audit, score = _load_sources()
    io, cap = delivery.io, delivery.CAP
    io.need(not io.regular(args.output).exists(), "Fresh private operator grade output")
    panel, contexts, responses, audits = [io.json_file(path, cap) for path in
                                        (args.panel, args.contexts, args.responses, args.audits)]
    result = compare_paired(delivery, audit, score, panel, contexts, responses, audits,
                            lambda: io.json_file(args.private_targets, cap))
    io.put(args.output, result, cap)


if __name__ == "__main__":
    main()
