"""Construct all inner episodes from one outer fold's private training records.

The public wrapper authenticates these dependencies and the input projection.
This module is an internal operator interface, not a native MAT normalizer or a
participant sandbox. All staged packets remain private until successful return
and operator commit. Failure never admits a partial training population.
"""

import hashlib
import json
import math


class PreparationError(ValueError):
    """A complete nested-training preparation could not be admitted."""


def _require(ok, message):
    if not ok:
        raise PreparationError(message)


def _keys(value, expected, where):
    _require(type(value) is dict and set(value) == set(expected),
             where + ": exact keys required")


def _positive(value, where):
    _require(type(value) is int and value > 0, where + ": positive integer required")


def _wire(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _digest(body):
    return hashlib.sha256(body).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON object key")
        result[key] = value
    return result


def _constant(value):
    raise PreparationError("nonfinite JSON constant")


def _float(value):
    result = float(value)
    _require(math.isfinite(result), "nonfinite JSON numeric literal")
    return result


def _decode(body, limit, where):
    _require(type(body) is bytes and 0 < len(body) <= limit,
             where + ": immutable bytes within declared cap required")
    try:
        return json.loads(body.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant, parse_float=_float)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PreparationError(where + ": invalid JSON") from error


def _preflight(projection, deps, max_record_bytes, max_total_record_bytes):
    """Admit all metadata and trial denominators before any normalized load."""
    scorer, admission = deps["scorer"], deps["admission"]
    roster = deps["roster"].ROSTER
    metadata = admission._roster(roster)
    positive = [row for row in metadata if row["declared_trials"] > 0]
    _require(len(positive) == 48, "complete positive canonical roster required")
    _keys(projection, ("schema", "held_record_id", "zero_record", "review_sha256", "records"),
          "private training projection")
    _require(projection["schema"] == "fus_nested_training_input_v1", "private training schema")
    held = projection["held_record_id"]
    _require(type(held) is str and held in {row["record_id"] for row in positive},
             "outer-held record must be a positive canonical record")
    _require(scorer.pin(projection["review_sha256"]), "independent projection review identity required")
    zero = projection["zero_record"]
    _keys(zero, ("record_id", "reconciliation_sha256"), "zero record")
    _require(zero["record_id"] == "L-S45-R1" and scorer.pin(zero["reconciliation_sha256"]),
             "explicit declared-zero reconciliation required")
    expected = [row for row in positive if row["record_id"] != held]
    records = projection["records"]
    _require(type(records) is list and len(records) == 47, "complete 47-record training projection required")
    for entry in records:
        _keys(entry, ("fold_key", "normalized_source", "record"), "projected record entry")
        _keys(entry["record"], ("record_id", "native_hz", "reconciliation_sha256",
                               "clock_mapping_sha256", "representation_sha256", "trials"),
              "frozen training record")
    _require([entry["record"]["record_id"] for entry in records] ==
             [row["record_id"] for row in expected],
             "canonical 47-record order required; outer-held body forbidden")

    parts, source_ids, query_ids, fold_keys = [], set(), set(), set()
    total_record_bytes = 0
    for entry, meta in zip(records, expected):
        record = entry["record"]
        rid = record["record_id"]
        fold_key = entry["fold_key"]
        _require(type(fold_key) is str and deps["fullfield"].FOLD_KEY.fullmatch(fold_key)
                 and fold_key not in fold_keys, "unique opaque inner-fold identity required")
        fold_keys.add(fold_key)
        source = entry["normalized_source"]
        _keys(source, ("bytes", "sha256"), "normalized-source descriptor")
        _require(type(source["bytes"]) is int and 0 < source["bytes"] <= max_record_bytes
                 and scorer.pin(source["sha256"]), "bounded normalized-source extent and identity required")
        total_record_bytes += source["bytes"]
        _require(type(record["native_hz"]) is int and record["native_hz"] in (1, 2), "native rate")
        _require(all(scorer.pin(record[key]) for key in
                     ("reconciliation_sha256", "clock_mapping_sha256", "representation_sha256")),
                 "record reconciliation, clock and representation receipts required")
        trials = record["trials"]
        _require(type(trials) is list and len(trials) == meta["declared_trials"],
                 "complete declared source-trial census required: " + rid)
        calibration, queries, selector_trials = {}, [], []
        for ordinal, trial in enumerate(trials):
            _keys(trial, ("source_trial_id", "source_order", "disposition", "query_id",
                          "direction", "timing", "exclusion_reason", "adjudication_sha256"), "frozen trial")
            sid = trial["source_trial_id"]
            _require(type(sid) is str and 0 < len(sid) <= 200 and sid not in source_ids,
                     "globally unique source trial lineage required")
            source_ids.add(sid)
            _require(type(trial["source_order"]) is int and trial["source_order"] == ordinal,
                     "complete ordered trial census required")
            if trial["disposition"] == "adjudicated_excluded":
                _require(type(trial["exclusion_reason"]) is str and trial["exclusion_reason"] in scorer.EXCLUSIONS
                         and trial["adjudication_sha256"] == projection["review_sha256"]
                         and trial["query_id"] is None and trial["timing"] is None
                         and (trial["direction"] is None or
                              (type(trial["direction"]) is int and 0 <= trial["direction"] < 8)),
                         "unresolved or unreviewed eligibility exclusion")
                selector_trials.append({"disposition": "adjudicated_excluded", "source_order": ordinal,
                                        "exclusion_reason": trial["exclusion_reason"],
                                        "adjudication_sha256": trial["adjudication_sha256"]})
                continue
            _require(trial["disposition"] == "eligible" and trial["exclusion_reason"] is None
                     and trial["adjudication_sha256"] is None, "unresolved trial disposition")
            qid, direction = trial["query_id"], trial["direction"]
            _require(type(qid) is str and scorer.OPAQUE.fullmatch(qid) and qid not in query_ids,
                     "globally unique opaque eligible-trial identity required")
            query_ids.add(qid)
            _require(type(direction) is int and 0 <= direction < 8, "direction class")
            timing = trial["timing"]
            _keys(timing, ("cue", "memory_start", "memory_end", "go", "baseline_start", "baseline_end",
                           "acquisition_start", "acquisition_end"), "frozen timing")
            _require(all(scorer.finite(value) for value in timing.values()), "finite common-clock timing")
            _require(timing["baseline_start"] < timing["baseline_end"] < timing["cue"] <=
                     timing["memory_start"] < timing["memory_end"] <= timing["go"],
                     "baseline/cue/memory/go ordering")
            _require(timing["memory_start"] <= timing["acquisition_start"] < timing["acquisition_end"] <=
                     min(timing["memory_end"], timing["go"]), "complete memory acquisition interval")
            projected = {"query_id": qid, "direction": direction}
            if direction not in calibration:
                calibration[direction] = projected
            else:
                queries.append(projected)
            selector_trials.append({"disposition": "eligible", "source_order": ordinal,
                                    "query_id": qid, "direction": direction})
        _require(set(calibration) == set(range(8)), "all eight earliest eligible calibration classes required")
        _require({trial["direction"] for trial in queries} == set(range(8)),
                 "all post-calibration query classes required")
        parts.append({"meta": meta, "entry": entry, "record": record,
                      "calibration": [calibration[c] for c in range(8)], "queries": queries,
                      "selector_trials": selector_trials})
    _require(2 * total_record_bytes <= max_total_record_bytes,
             "two complete normalized passes exceed returned-byte budget before first load")
    return parts, total_record_bytes


def _load(part, load_record, max_record_bytes, max_map_bytes):
    rid = part["record"]["record_id"]
    descriptor = part["entry"]["normalized_source"]
    body = load_record(rid)
    _require(type(body) is bytes and len(body) == descriptor["bytes"]
             and len(body) <= max_record_bytes, "normalized returned byte extent mismatch: " + rid)
    _require(_digest(body) == descriptor["sha256"], "normalized content identity changed: " + rid)
    normalized = _decode(body, max_record_bytes, "normalized record")
    _require(type(normalized) is dict, "normalized record object required")
    shape = normalized.get("shape")
    _require(type(shape) is list and len(shape) == 2
             and all(type(value) is int and value > 0 for value in shape), "native image shape")
    _require(3 * shape[0] * shape[1] <= max_map_bytes,
             "complete native map exceeds byte budget; resizing forbidden")
    return normalized


def _image(part, trial, deltas, metadata, scale, calibration, deps, max_map_bytes):
    rgb, invalid, saturated = bytearray(), 0, 0
    for value in deltas:
        pixel, clipped = deps["fullfield"].encode(value, scale)
        rgb.extend(pixel)
        invalid += value is None
        saturated += clipped
    payload = {"schema": "fus_fullfield_map_v1", "fold_key": part["entry"]["fold_key"],
               "query_id": trial["query_id"], "role": "calibration" if calibration else "query",
               "scale": scale, **metadata, "rgb": bytes(rgb), "invalid_pixels": invalid,
               "saturated_pixels": saturated}
    if calibration:
        payload["direction"] = trial["direction"]
    return deps["delivery"]._map(payload, trial=trial, calibration=calibration,
                                 fold_key=part["entry"]["fold_key"], scale=scale,
                                 rate=part["record"]["native_hz"], max_bytes=max_map_bytes)


def prepare_training(projection_wire, load_record, stage_packet, *, expected_projection_sha256,
                     max_projection_bytes, max_record_bytes, max_total_record_bytes,
                     max_map_bytes, max_packet_bytes, max_total_packet_bytes,
                     max_manifest_bytes, max_receipt_bytes, deps):
    """Return canonical {'manifest': bytes, 'receipt': bytes} after complete staging.

    load_record(record_id) returns immutable, descriptor-pinned normalized JSON
    bytes. Each of the 47 records is loaded exactly twice. The second private
    decoded record is traversed twice, retaining only eight support images and
    one query image; early queries therefore survive without whole-map caching.
    stage_packet(record_id, query_id, bytes) must keep output private. No callback
    receives the outer-held identifier as a requested record.

    Caps bound returned/staged byte payloads, not a callback's physical I/O,
    Python allocation peak or protected process isolation. The external owner
    must impose finite time/RAM/storage limits and authenticate source custody.
    The output manifest and receipt have independent finite retained-byte caps.
    """
    limits = (max_projection_bytes, max_record_bytes, max_total_record_bytes, max_map_bytes,
              max_packet_bytes, max_total_packet_bytes, max_manifest_bytes, max_receipt_bytes)
    for value in limits:
        _positive(value, "byte budget")
    _require(callable(load_record) and callable(stage_packet), "explicit private callbacks required")
    _keys(deps, ("roster", "scorer", "fullfield", "delivery", "admission"), "authenticated dependencies")
    _require(deps["scorer"].pin(expected_projection_sha256), "expected private projection digest required")
    _require(type(projection_wire) is bytes and 0 < len(projection_wire) <= max_projection_bytes,
             "bounded immutable private projection required")
    _require(_digest(projection_wire) == expected_projection_sha256, "private projection identity mismatch")
    projection = _decode(projection_wire, max_projection_bytes, "private projection")
    parts, one_pass_bytes = _preflight(projection, deps, max_record_bytes, max_total_record_bytes)
    fullfield, delivery, admission = deps["fullfield"], deps["delivery"], deps["admission"]

    summaries = []
    for part in parts:
        normalized = _load(part, load_record, max_record_bytes, max_map_bytes)
        maximum, maps, valid, invalid = 0.0, 0, 0, 0
        for _, deltas, _ in fullfield.record_deltas(part["record"], normalized):
            maps += 1
            for value in deltas:
                if value is None:
                    invalid += 1
                else:
                    valid += 1
                    maximum = max(maximum, abs(value))
        _require(maps == 8 + len(part["queries"]), "complete eligible map count mismatch")
        summaries.append({"record_id": part["record"]["record_id"],
                          "normalized_source": dict(part["entry"]["normalized_source"]),
                          "acquisition_census_sha256": normalized["acquisition_census_sha256"],
                          "maps": maps, "valid_pixels": valid, "invalid_pixels": invalid,
                          "maximum_absolute_finite_delta": maximum})
        del normalized, deltas

    # Finish every scale before any packet is staged. A zero scale in the last
    # episode cannot leave a seemingly successful earlier subset.
    scale_receipts = []
    for part in parts:
        rid = part["record"]["record_id"]
        contributors = [summary for summary in summaries if summary["record_id"] != rid]
        _require(len(contributors) == 46, "exact 46-record inner scale support required")
        scale = max(summary["maximum_absolute_finite_delta"] for summary in contributors)
        _require(deps["scorer"].finite(scale) and scale > 0,
                 "zero/nonfinite inner scale refuses complete preparation before packet staging")
        scale_receipts.append({"schema": "fus_nested_training_scale_receipt_v1",
                               "status": "source_component_completed",
                               "input_projection_sha256": expected_projection_sha256,
                               "outer_held_record_id": projection["held_record_id"],
                               "episode_record_id": rid, "fold_key": part["entry"]["fold_key"],
                               "recipe_sha256": admission.SCALE_RECIPE_SHA256,
                               "training_records": 46, "contributors": contributors,
                               "training_maps": sum(row["maps"] for row in contributors),
                               "training_valid_pixels": sum(row["valid_pixels"] for row in contributors),
                               "training_invalid_pixels": sum(row["invalid_pixels"] for row in contributors),
                               "scale": scale})
    _require(len(_wire(scale_receipts)) <= max_receipt_bytes,
             "all scale receipts exceed receipt cap before packet staging")

    episodes, total_packet_bytes, total_packets = [], 0, 0
    for part, scale_receipt in zip(parts, scale_receipts):
        record, entry = part["record"], part["entry"]
        scale = scale_receipt["scale"]
        normalized = _load(part, load_record, max_record_bytes, max_map_bytes)
        calibration_ids = {trial["query_id"] for trial in part["calibration"]}
        support = {}
        for trial, deltas, metadata in fullfield.record_deltas(record, normalized):
            if trial["query_id"] in calibration_ids:
                support[trial["direction"]] = _image(part, trial, deltas, metadata, scale, True,
                                                    deps, max_map_bytes)
        _require(set(support) == set(range(8)), "complete eight-map support required")
        images = [support[c] for c in range(8)]
        signature = delivery._json({key: images[0][key] for key in delivery._METADATA})
        _require(all(delivery._json({key: image[key] for key in delivery._METADATA}) == signature
                     for image in images), "common native support geometry required")
        packets = []
        for trial, deltas, metadata in fullfield.record_deltas(record, normalized):
            if trial["query_id"] in calibration_ids:
                continue
            _require(len(packets) < len(part["queries"])
                     and trial["query_id"] == part["queries"][len(packets)]["query_id"],
                     "complete query source order required")
            image = _image(part, trial, deltas, metadata, scale, False, deps, max_map_bytes)
            _require(delivery._json({key: image[key] for key in delivery._METADATA}) == signature,
                     "query/support native geometry mismatch")
            wire = delivery._json({"schema": "fus_nine_map_packet_v1", "fold_key": entry["fold_key"],
                                   "query_id": trial["query_id"],
                                   "class_angles_degrees": list(range(0, 360, 45)),
                                   "context": delivery.CONTEXT, "calibration": images, "query": image})
            _require(len(wire) <= max_packet_bytes, "complete packet exceeds individual byte budget")
            _require(total_packet_bytes + len(wire) <= max_total_packet_bytes,
                     "complete packet population exceeds staged-byte budget")
            stage_packet(record["record_id"], trial["query_id"], wire)
            packets.append({"query_id": trial["query_id"], "bytes": len(wire), "sha256": _digest(wire)})
            total_packet_bytes += len(wire)
            total_packets += 1
        _require(len(packets) == len(part["queries"]), "missing post-calibration query packet")
        episodes.append({"record_id": record["record_id"], "native_hz": record["native_hz"],
                         "reconciliation_sha256": record["reconciliation_sha256"],
                         "clock_mapping_sha256": record["clock_mapping_sha256"],
                         "representation_sha256": record["representation_sha256"],
                         "fold_key": entry["fold_key"],
                         "scale": {"value": scale,
                                   "training_record_ids": [row["record_id"] for row in scale_receipt["contributors"]],
                                   "recipe_sha256": admission.SCALE_RECIPE_SHA256,
                                   "receipt_sha256": _digest(_wire(scale_receipt))},
                         "trials": part["selector_trials"], "packets": packets})
        del normalized, support, images, image, wire, deltas

    manifest = {"schema": "fus_outer_training_episodes_v1", "held_record_id": projection["held_record_id"],
                "zero_record": dict(projection["zero_record"]), "review_sha256": projection["review_sha256"],
                "episodes": episodes}
    admission.admit(manifest, deps["roster"].ROSTER)
    manifest_wire = _wire(manifest)
    _require(len(manifest_wire) <= max_manifest_bytes, "complete selector manifest exceeds byte cap")
    receipt = {"schema": "fus_nested_training_preparation_receipt_v1", "status": "source_component_completed",
               "input_projection_sha256": expected_projection_sha256,
               "outer_held_record_id": projection["held_record_id"],
               "roster_records": 49, "positive_records": 48, "training_records": 47,
               "declared_source_trials": 20622,
               "training_source_trials": sum(part["meta"]["declared_trials"] for part in parts),
               "normalized_loads": 94, "returned_normalized_bytes": 2 * one_pass_bytes,
               "training_maps": sum(row["maps"] for row in summaries),
               "query_packets": total_packets, "total_packet_bytes": total_packet_bytes,
               "manifest_bytes": len(manifest_wire), "manifest_sha256": _digest(manifest_wire),
               "scale_policy_sha256": admission.SCALE_RECIPE_SHA256,
               "source_summaries": summaries, "scale_receipts": scale_receipts,
               "native_source_authenticated": False, "full_resolution_delivery_qualified": False,
               "protected_evaluation_established": False, "scientifically_qualified": False,
               "publication_requires_success_and_operator_commit": True}
    receipt_wire = _wire(receipt)
    _require(len(receipt_wire) <= max_receipt_bytes, "complete preparation receipt exceeds byte cap")
    return {"manifest": manifest_wire, "receipt": receipt_wire}
