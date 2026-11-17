"""Authored evaluator for prospective donor-held FL/PL morphology prediction.

This is not a replica of the paper's neuron-stratified cross-validation.
The production CLI requires a reconciled full 2,363-human/16,011-mouse census.
It consumes protected metadata, never executes a participant program, and does
not itself provide container isolation or authenticate a biological group map.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

SOURCE_COUNTS = {"human": 2363, "mouse": 16011}
SPECIES = ("human", "mouse")
LOBES = ("FL", "PL")
EXCLUSIONS = {"outside_FL_PL", "not_pyramidal", "outside_declared_layer", "missing_required_feature"}
MAX_BYTES = 16 * 1024 * 1024


class Invalid(ValueError):
    """An incomplete or contradictory protected task/submission."""


def _require(test, message):
    if not test:
        raise Invalid(message)


def _keys(obj, keys):
    _require(type(obj) is dict and set(obj) == set(keys), "unexpected object fields")


def _text(value):
    _require(type(value) is str and 0 < len(value) <= 256 and value.strip() == value,
             "invalid identifier")
    return value


def fold_id(species, group):
    """Stable opaque identity, not a source for inferring donor identity."""
    return hashlib.sha256(json.dumps([species, group], separators=(",", ":")).encode()).hexdigest()


def _validate_manifest(manifest, source_counts):
    _keys(manifest, {"schema", "source_revision", "group_map_sha256", "census"})
    _require(manifest["schema"] == "dendrite-lobe-protected-v1", "wrong protected schema")
    _require(manifest["source_revision"] == "a0cc151a00384543a21c95c61479e65112ba6b5d",
             "wrong source revision")
    digest = manifest["group_map_sha256"]
    _require(type(digest) is str and len(digest) == 64 and all(x in "0123456789abcdef" for x in digest),
             "group map digest required")
    rows = manifest["census"]
    _require(type(rows) is list and len(rows) == sum(source_counts.values()), "incomplete source census")
    included, seen, counts = {}, set(), Counter()
    groups = defaultdict(lambda: defaultdict(set))
    for row in rows:
        _require(type(row) is dict and type(row.get("included")) is bool, "inclusion must be Boolean")
        common = {"neuron_id", "species", "included"}
        _keys(row, common | ({"group_id", "lobe"} if row["included"] else {"exclusion"}))
        identity = _text(row["neuron_id"])
        species = row["species"]
        _require(species in SPECIES, "unknown species")
        _require(identity not in seen, "duplicate neuron identity")
        seen.add(identity)
        counts[species] += 1
        if not row["included"]:
            _require(row["exclusion"] in EXCLUSIONS, "unsupported exclusion")
            continue
        group = _text(row["group_id"])
        _require(row["lobe"] in LOBES, "wrong lobe endpoint")
        included[identity] = row
        groups[species][group].add(row["lobe"])
    _require(dict(counts) == source_counts, "species census mismatch")
    for species in SPECIES:
        _require(len(groups[species]) >= 3, "nested validation needs at least three biological groups per species")
        for group in groups[species]:
            # Each held-group prediction must be learnable from both classes
            # in the remaining groups. No silent dropping of difficult folds.
            training_lobes = set().union(*(v for g, v in groups[species].items() if g != group))
            _require(training_lobes == set(LOBES), "a held-group fold lacks a training class")
            for inner_group in groups[species]:
                if inner_group == group:
                    continue
                inner_training = set().union(*(v for g, v in groups[species].items()
                                                if g not in (group, inner_group)))
                _require(inner_training == set(LOBES), "an inner training fold lacks a class")
        _require(set().union(*groups[species].values()) == set(LOBES), "missing evaluation lobe")
    return included, groups, counts


def _evaluate(included, submission):
    _keys(submission, {"schema", "predictions"})
    _require(submission["schema"] == "dendrite-lobe-predictions-v1", "wrong prediction schema")
    predictions = submission["predictions"]
    _require(type(predictions) is list and len(predictions) == len(included), "incomplete predictions")
    seen, cells, errors, log_losses = set(), defaultdict(list), defaultdict(list), defaultdict(list)
    for pred in predictions:
        _keys(pred, {"neuron_id", "fold_id", "p_PL"})
        identity = _text(pred["neuron_id"])
        _require(identity in included and identity not in seen, "unknown or duplicate prediction")
        seen.add(identity)
        row = included[identity]
        _require(pred["fold_id"] == fold_id(row["species"], row["group_id"]), "wrong held-group fold")
        p = pred["p_PL"]
        _require(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1, "invalid probability")
        y = int(row["lobe"] == "PL")
        # An exact 0.5 tie selects FL, fixed before seeing any predictions.
        guess = int(p > 0.5)
        key = (row["species"], row["lobe"], row["group_id"])
        cells[key].append(int(guess == y))
        errors[key].append((p-y)**2)
        q = p if y else 1-p
        log_losses[key].append(-math.log(max(q, 1e-15)))
    _require(seen == set(included), "prediction identity mismatch")
    # Average cells within each biological group, then groups within each
    # species/lobe, then the two lobes and two species. Cell count is not n.
    by_species = {}
    for species in SPECIES:
        class_scores, class_brier, class_log = {}, {}, {}
        for lobe in LOBES:
            keys = [k for k in cells if k[:2] == (species, lobe)]
            _require(bool(keys), "missing evaluation class")
            avg = lambda values: math.fsum(math.fsum(values[k])/len(values[k]) for k in keys)/len(keys)
            class_scores[lobe] = avg(cells)
            class_brier[lobe] = avg(errors)
            class_log[lobe] = avg(log_losses)
        by_species[species] = {
            "group_macro_balanced_accuracy": math.fsum(class_scores.values())/2,
            "group_class_recall": class_scores,
            "group_class_brier": math.fsum(class_brier.values())/2,
            "group_class_log_loss": math.fsum(class_log.values())/2,
        }
    return {
        "primary": math.fsum(x["group_macro_balanced_accuracy"] for x in by_species.values())/2,
        "by_species": by_species,
        "included_neurons": len(included),
        "distinct_biological_groups": len({(r["species"], r["group_id"]) for r in included.values()}),
    }


def score(manifest, submission, baseline=None):
    included, _, _ = _validate_manifest(manifest, SOURCE_COUNTS)
    result = _evaluate(included, submission)
    result["status"] = "DESCRIPTIVE_PROTECTED_MANIFEST_SCORE"
    result["scientific_qualification"] = False
    if baseline is not None:
        reference = _evaluate(included, baseline)
        result["frozen_reference_primary"] = reference["primary"]
        result["paired_primary_delta"] = result["primary"] - reference["primary"]
    return result


def _unique_pairs(pairs):
    obj = {}
    for key, value in pairs:
        _require(key not in obj, "duplicate JSON key")
        obj[key] = value
    return obj


def load_json(path):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    _require(len(data) <= MAX_BYTES, "JSON input exceeds 16 MiB")
    return json.loads(data, object_pairs_hook=_unique_pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(Invalid("non-finite JSON constant")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("protected_manifest")
    parser.add_argument("submission")
    parser.add_argument("--frozen-reference")
    args = parser.parse_args()
    result = score(load_json(args.protected_manifest), load_json(args.submission),
                   load_json(args.frozen_reference) if args.frozen_reference else None)
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
