"""Validate the complete private training projection before any packet is read.

This is a new prospective selection interface, not a native MAT schema. The
caller must authenticate the manifest and its source/eligibility/scale receipts.
Digest syntax and consistency cannot establish their biological provenance.
The module performs no file access and accepts no loader or prediction callback.
"""

import math
import re


SCALE_RECIPE_SHA256 = "633610d7df4ffe8ff15bdf13b371db84804d197600ea2f76b05d4d8e3894308c"
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_QUERY = re.compile(r"q_[0-9a-f]{32}\Z")
_FOLD = re.compile(r"fold_[0-9a-f]{32}\Z")
_EXCLUSIONS = frozenset(("missing_target", "missing_timing", "missing_baseline",
                         "no_complete_memory_acquisition"))
_EPISODE_KEYS = frozenset(("record_id", "native_hz", "reconciliation_sha256",
                           "clock_mapping_sha256", "representation_sha256",
                           "fold_key", "scale", "trials", "packets"))


class AdmissionError(ValueError):
    """The full training denominator is inadmissible; selection must not run."""


def _require(ok, message):
    if not ok:
        raise AdmissionError(message)


def _keys(value, expected, where):
    _require(type(value) is dict and set(value) == set(expected),
             where + ": exact keys required")


def _pin(value, where):
    _require(type(value) is str and _HEX.fullmatch(value) is not None,
             where + ": lowercase SHA256 required")


def _positive_finite(value):
    try:
        return type(value) in (int, float) and value > 0 and math.isfinite(value)
    except OverflowError:
        return False


def _roster(roster):
    """Defensive support checks; exact source identity is the caller's duty."""
    _require(type(roster) in (tuple, list) and len(roster) == 49,
             "complete 49-record canonical roster required")
    metadata = []
    for row in roster:
        _require(type(row) in (tuple, list) and len(row) == 5, "roster row shape")
        rid, animal, system, count, elapsed = row
        _require(type(rid) is str and 0 < len(rid) <= 64, "roster record identifier")
        _require(animal in ("L", "P") and type(animal) is str, "roster animal")
        _require(type(system) is str and system in ("offlineVantage", "prototypeRT"),
                 "roster recording system")
        _require(type(count) is int and count >= 0 and type(elapsed) is int and elapsed >= 0,
                 "roster count and elapsed days")
        metadata.append({"record_id": rid, "animal": animal, "declared_trials": count})
    _require(len({r["record_id"] for r in metadata}) == 49, "unique canonical records")
    _require(sum(r["declared_trials"] for r in metadata) == 20622, "complete declared trial count")
    _require([r["record_id"] for r in metadata if r["declared_trials"] == 0] == ["L-S45-R1"],
             "preserve the sole declared zero record")
    _require({a: sum(r["animal"] == a for r in metadata) for a in ("L", "P")} == {"L": 27, "P": 22},
             "complete two-animal roster")
    return metadata


def admit(manifest, roster):
    """Return fresh projections for all 47 training records in canonical order.

    The outer-held record appears only as its public roster identifier. Every
    other positive record contributes a complete source-order trial census and
    every eligible post-calibration query. Each inner episode uses one frozen
    scale whose declared fitting contributors are the remaining 46 records;
    neither the outer-held nor the current inner record may contribute.

    This function validates the entire manifest before returning. A downstream
    caller must not load packets or score anything before successful return.
    An absent input/class is an admission failure, not a smaller denominator.
    Failed predictions are handled later without removing admitted queries.
    """
    metadata = _roster(roster)
    positive = [r for r in metadata if r["declared_trials"] > 0]
    _require(len(positive) == 48, "complete 48-positive-record roster")
    _keys(manifest, ("schema", "held_record_id", "zero_record", "review_sha256", "episodes"),
          "training manifest")
    _require(manifest["schema"] == "fus_outer_training_episodes_v1", "training manifest schema")
    held = manifest["held_record_id"]
    _require(type(held) is str and held in {r["record_id"] for r in positive},
             "outer-held record must be a positive canonical record")
    _pin(manifest["review_sha256"], "independent source/intake/eligibility review")
    zero = manifest["zero_record"]
    _keys(zero, ("record_id", "reconciliation_sha256"), "zero-record reconciliation")
    _require(zero["record_id"] == "L-S45-R1", "declared zero record identity")
    _pin(zero["reconciliation_sha256"], "zero-record reconciliation")

    expected = [r for r in positive if r["record_id"] != held]
    expected_ids = [r["record_id"] for r in expected]
    episodes = manifest["episodes"]
    _require(type(episodes) is list and len(episodes) == 47,
             "all 47 outer-training episodes required")
    # Exclude an injected held record, duplicate, omission, extra field or
    # reordering before walking any episode's private labels/census.
    for episode in episodes:
        _keys(episode, _EPISODE_KEYS, "training episode")
    _require([e["record_id"] for e in episodes] == expected_ids,
             "exact canonical training roster required; outer-held episode forbidden")

    admitted, global_query_ids, fold_keys = [], set(), set()
    common_recipe = None
    for episode, meta in zip(episodes, expected):
        rid = meta["record_id"]
        _require(type(episode["native_hz"]) is int and episode["native_hz"] in (1, 2),
                 "declared native rate must be 1 or 2 Hz")
        for key in ("reconciliation_sha256", "clock_mapping_sha256", "representation_sha256"):
            _pin(episode[key], rid + ": " + key)
        fold_key = episode["fold_key"]
        _require(type(fold_key) is str and _FOLD.fullmatch(fold_key) is not None
                 and fold_key not in fold_keys, "unique opaque inner-fold identity required")
        fold_keys.add(fold_key)
        scale = episode["scale"]
        _keys(scale, ("value", "training_record_ids", "recipe_sha256", "receipt_sha256"),
              rid + ": inner scale")
        _require(_positive_finite(scale["value"]), "positive finite frozen scale required")
        scale_ids = [other for other in expected_ids if other != rid]
        _require(type(scale["training_record_ids"]) is list
                 and scale["training_record_ids"] == scale_ids and len(scale_ids) == 46,
                 "inner scale requires exact 46-record training-only contributor roster")
        _pin(scale["recipe_sha256"], "scale recipe")
        _require(scale["recipe_sha256"] == SCALE_RECIPE_SHA256,
                 "exact frozen training-only max-absolute scale policy required")
        _pin(scale["receipt_sha256"], "scale preparation receipt")
        if common_recipe is None:
            common_recipe = scale["recipe_sha256"]
        _require(scale["recipe_sha256"] == common_recipe, "identical inner scale recipe required")

        trials = episode["trials"]
        _require(type(trials) is list and len(trials) == meta["declared_trials"],
                 "complete declared source-trial census required: " + rid)
        calibration, queries = {}, []
        for ordinal, trial in enumerate(trials):
            _require(type(trial) is dict, "trial must be an explicit census row")
            if trial.get("disposition") == "adjudicated_excluded":
                _keys(trial, ("disposition", "source_order", "exclusion_reason", "adjudication_sha256"),
                      "excluded trial")
                _require(type(trial["exclusion_reason"]) is str and trial["exclusion_reason"] in _EXCLUSIONS,
                         "unrecognized source eligibility exclusion")
                _require(trial["adjudication_sha256"] == manifest["review_sha256"],
                         "excluded trial requires matching independent adjudication")
            else:
                _keys(trial, ("disposition", "source_order", "query_id", "direction"), "eligible trial")
                _require(trial["disposition"] == "eligible", "unresolved trial disposition")
                qid, direction = trial["query_id"], trial["direction"]
                _require(type(qid) is str and _QUERY.fullmatch(qid) is not None
                         and qid not in global_query_ids,
                         "globally unique opaque eligible-trial identities required")
                _require(type(direction) is int and 0 <= direction < 8, "eight-direction integer class")
                global_query_ids.add(qid)
                projected = {"query_id": qid, "direction": direction}
                if direction not in calibration:
                    calibration[direction] = projected
                else:
                    queries.append(projected)
            _require(type(trial["source_order"]) is int and trial["source_order"] == ordinal,
                     "complete source-order trial census required")
        _require(set(calibration) == set(range(8)), "all eight earliest eligible calibration classes required")
        _require({q["direction"] for q in queries} == set(range(8)),
                 "all eight post-calibration query classes required for balanced accuracy")

        packets = episode["packets"]
        _require(type(packets) is list and len(packets) == len(queries),
                 "complete post-calibration packet roster required")
        projected_packets = []
        for packet, query in zip(packets, queries):
            _keys(packet, ("query_id", "bytes", "sha256"), "packet descriptor")
            _require(packet["query_id"] == query["query_id"],
                     "packet roster must retain every query in source order")
            _require(type(packet["bytes"]) is int and packet["bytes"] > 0,
                     "positive complete packet byte extent required")
            _pin(packet["sha256"], "packet content identity")
            projected_packets.append(dict(packet))
        admitted.append({"record_id": rid, "animal": meta["animal"],
                         "native_hz": episode["native_hz"], "fold_key": fold_key,
                         "scale": scale["value"],
                         "calibration": [calibration[c] for c in range(8)],
                         "queries": queries, "packets": projected_packets})
    return admitted
