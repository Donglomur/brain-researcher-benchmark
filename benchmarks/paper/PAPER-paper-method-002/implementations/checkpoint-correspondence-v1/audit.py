"""Audit recorded Jaxley retinal validation/checkpoint correspondence.

This is an operator metadata check, not a scientific admission or model runner.
The supplied scores, digests, schedule and input identity require independent
provenance. No target arrays, parameter objects or pickle files are opened.
"""
from __future__ import annotations

import hashlib
import json
import math
import re


SCHEMA = "jaxley-retinal-checkpoint-correspondence-input/v1"
MAX_EVENTS = 100_000
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class CorrespondenceError(ValueError):
    """The supplied metadata does not satisfy the declared source schedule."""


def _require(condition, message):
    if not condition:
        raise CorrespondenceError(message)


def _keys(value, expected, name):
    _require(type(value) is dict and set(value) == set(expected),
             f"{name}: exact keys required")


def _integer(value, minimum, maximum, name):
    _require(type(value) is int and minimum <= value <= maximum,
             f"{name}: bounded integer required")


def _digest(value, name, *, optional=False):
    if optional and value is None:
        return
    _require(type(value) is str and _SHA.fullmatch(value) is not None,
             f"{name}: lowercase SHA-256 required")


def _score(value):
    # Undefined source means may be represented as null, never as invented zero.
    if value is None:
        return None
    _require(type(value) in (int, float) and -1 <= value <= 1
             and math.isfinite(value), "validation mean: finite Pearson value or null")
    return value


def audit(document):
    """Check one complete *declared* run's recorded validation selection.

    An event's after_batch is a zero-based batch index, or 'epoch_end'. A
    checkpoint boundary n refers to params_n at optimizer step n*batches.
    Parameter digests must use one externally fixed byte serialization. A digest
    is optional on an evaluation because historical scalar logs need not bind
    parameter state. Missing digests preserve an unresolved result.

    The function neither reconstructs unavailable history nor supplies historical
    authenticity. Test scores are deliberately absent from the closed schema.
    """
    _keys(document, ("schema", "source_commit", "observation_manifest_sha256",
                     "epochs", "batches_per_epoch", "evaluate_every_nth_batch",
                     "events", "checkpoints"), "input")
    _require(document["schema"] == SCHEMA, "unsupported schema")
    _require(document["source_commit"] == "5e7a86282adb9d4603b5546ac5d8dad59aec7cc0",
             "source revision differs")
    _digest(document["observation_manifest_sha256"], "observation manifest")
    epochs = document["epochs"]
    batches = document["batches_per_epoch"]
    every = document["evaluate_every_nth_batch"]
    for value, name in ((epochs, "epochs"), (batches, "batches_per_epoch"),
                        (every, "evaluate_every_nth_batch")):
        _integer(value, 1, MAX_EVENTS, name)
    event_count = epochs * (batches // every + 1)
    _require(event_count <= MAX_EVENTS, "complete event roster exceeds metadata limit")
    events = document["events"]
    _require(type(events) is list and len(events) == event_count,
             "complete declared evaluation history required")
    expected = []
    for epoch in range(epochs):
        expected.extend((epoch, batch, epoch * batches + batch + 1)
                        for batch in range(every - 1, batches, every))
        # The source evaluates again at epoch-end even if its final batch also
        # triggered evaluation. Equal optimizer step does not erase this event.
        expected.append((epoch, "epoch_end", (epoch + 1) * batches))

    selected = None
    best = -1.0
    undefined = 0
    digests_at_step = {}
    for ordinal, (event, coordinate) in enumerate(zip(events, expected)):
        _keys(event, ("epoch", "after_batch", "validation_mean_pearson",
                      "parameter_state_sha256"), f"event {ordinal}")
        epoch, batch, step = coordinate
        _require(type(event["epoch"]) is int and event["epoch"] == epoch,
                 f"event {ordinal}: epoch or order differs")
        _require(type(event["after_batch"]) is type(batch)
                 and event["after_batch"] == batch,
                 f"event {ordinal}: batch coordinate or order differs")
        digest = event["parameter_state_sha256"]
        _digest(digest, f"event {ordinal} state", optional=True)
        if digest is not None:
            if step in digests_at_step:
                _require(digests_at_step[step] == digest,
                         "same optimizer step has conflicting state digests")
            digests_at_step[step] = digest
        score = _score(event["validation_mean_pearson"])
        if score is None:
            undefined += 1
        elif score > best:
            # Strict comparison preserves the first maximum and source -1
            # initialization. Undefined events never become selection winners.
            best = score
            selected = {"event_index": ordinal, "epoch": epoch,
                        "after_batch": batch, "optimizer_step": step,
                        "validation_mean_pearson": score,
                        "parameter_state_sha256": digest}

    checkpoints = document["checkpoints"]
    _require(type(checkpoints) is list and len(checkpoints) <= epochs + 1,
             "checkpoint inventory exceeds source epoch-boundary roster")
    by_boundary = {}
    for index, checkpoint in enumerate(checkpoints):
        _keys(checkpoint, ("epoch_boundary", "parameter_state_sha256"),
              f"checkpoint {index}")
        boundary = checkpoint["epoch_boundary"]
        _integer(boundary, 0, epochs, "checkpoint boundary")
        _require(boundary not in by_boundary, "duplicate checkpoint boundary")
        _digest(checkpoint["parameter_state_sha256"], "checkpoint state")
        by_boundary[boundary] = checkpoint["parameter_state_sha256"]

    same_step, other_steps = [], []
    if selected is None:
        status = "no_validation_winner_above_source_initial_minus_one"
    elif selected["parameter_state_sha256"] is None:
        status = "winner_parameter_identity_unrecorded"
    else:
        digest = selected["parameter_state_sha256"]
        step = selected["optimizer_step"]
        for boundary, checkpoint_digest in by_boundary.items():
            if checkpoint_digest == digest:
                (same_step if boundary * batches == step else other_steps).append(boundary)
        if same_step:
            status = "declared_winner_matches_checkpoint_at_same_step"
        elif step % batches:
            status = "winner_is_between_source_checkpoint_boundaries"
        elif step // batches not in by_boundary:
            status = "winner_boundary_checkpoint_not_in_inventory"
        else:
            status = "winner_and_boundary_checkpoint_digests_differ"

    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
    return {
        "schema": "jaxley-retinal-checkpoint-correspondence-report/v1",
        "input_sha256": hashlib.sha256(encoded).hexdigest(),
        "source_commit": document["source_commit"],
        "observation_manifest_sha256": document["observation_manifest_sha256"],
        "scope": "supplied_operator_metadata_only",
        "complete_declared_event_count": event_count,
        "undefined_validation_event_count": undefined,
        "selected_event": selected,
        "checkpoint_correspondence": status,
        "matching_same_step_boundaries": sorted(same_step),
        "identical_digest_at_other_boundaries": sorted(other_steps),
        "missing_checkpoint_boundaries": [n for n in range(epochs + 1)
                                          if n not in by_boundary],
        "historical_authenticity": "not_established",
        "observation_identity_authenticity": "not_established",
        "checkpoint_bytes_verified": False,
        "scientific_readiness": "not_established",
        "paper_win": None,
    }
