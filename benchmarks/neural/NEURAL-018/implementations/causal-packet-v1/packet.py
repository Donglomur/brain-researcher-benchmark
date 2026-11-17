"""Operator-only projection of complete, organizer-binned NEURAL-018 counts.

This module does no NWB loading, smoothing, fitting, candidate execution or scoring.
Its input is an upstream-authenticated complete count tensor. See README for the
unresolved upstream preparation boundary. Production dimensions are never relaxed.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np

TRAIN = 1721
QUERY = 574
HELDIN = 137
HELDOUT = 45
PAST = 140
FUTURE = 40
SOURCE_FIELDS = frozenset({
    "counts", "trial_ids", "split", "unit_ids", "unit_is_heldout",
    "bin_left_edges_ms", "trial_type", "trial_version",
})
PUBLIC_FIELDS = frozenset({
    "train_spikes_heldin", "train_spikes_heldout", "train_future_counts",
    "eval_spikes_heldin", "train_trial_ids", "eval_trial_ids",
    "heldin_unit_ids", "heldout_unit_ids", "forecast_unit_ids",
    "train_trial_type", "train_trial_version", "eval_trial_type",
    "eval_trial_version", "past_bin_left_edges_ms", "bin_left_edges_ms",
    "observation_units", "prediction_units", "panel_fingerprint",
})
TARGET_FIELDS = frozenset({
    "target_counts", "trial_ids", "unit_ids", "bin_left_edges_ms",
    "valid_mask", "panel_fingerprint",
})


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _identities(value, length, name):
    a = np.asarray(value)
    _require(a.shape == (length,) and a.dtype.kind == "U"
             and 0 < a.dtype.itemsize <= 256, name + ": bounded Unicode IDs required")
    ids = a.tolist()
    _require(all(ids) and len(set(ids)) == length, name + ": empty or repeated ID")
    return a


def _validate_source(source):
    _require(set(source) == SOURCE_FIELDS, "Exact operator source inventory required")
    count = np.asarray(source["counts"])
    _require(count.shape == (TRAIN + QUERY, PAST + FUTURE, HELDIN + HELDOUT),
             "Complete 2295 x 180 x 182 source panel required")
    _require(count.dtype.kind in "fiu" and count.dtype.itemsize <= 8,
             "Counts must be real numeric, not bool/object/complex")
    # Bound intermediate memory while checking every cell, including private ones.
    for row in count:
        _require(np.isfinite(row).all() and (row >= 0).all()
                 and (row <= 2**53).all() and (row == np.floor(row)).all(),
                 "Source must contain finite nonnegative integer counts without missing cells")
    trials = _identities(source["trial_ids"], TRAIN + QUERY, "trial_ids")
    units = _identities(source["unit_ids"], HELDIN + HELDOUT, "unit_ids")
    split = np.asarray(source["split"])
    _require(split.shape == (TRAIN + QUERY,) and split.dtype.kind == "U"
             and np.count_nonzero(split == "train") == TRAIN
             and np.count_nonzero(split == "val") == QUERY,
             "Exact 1721 train / 574 val split required; no exclusions or test relabeling")
    heldout = np.asarray(source["unit_is_heldout"])
    _require(heldout.shape == (HELDIN + HELDOUT,) and heldout.dtype == np.bool_
             and np.count_nonzero(heldout) == HELDOUT, "Exactly 137 held-in / 45 held-out units required")
    clock = np.asarray(source["bin_left_edges_ms"])
    _require(clock.dtype.kind in "fiu" and clock.dtype.itemsize <= 8
             and np.array_equal(clock, np.arange(-250, 650, 5)),
             "Exact organizer-relative 5-ms grid [-250,650) required")
    conditions = {}
    for name in ("trial_type", "trial_version"):
        values = np.asarray(source[name])
        _require(values.shape == (TRAIN + QUERY,) and values.dtype.kind in "iu"
                 and values.dtype.itemsize <= 8, name + ": one source integer condition per trial required")
        conditions[name] = values
    return count, trials, units, split, heldout, conditions


def _fingerprint(public):
    """Bind exactly the permitted observations, clocks, conditions and identities.

    Query targets and held-out query past have no influence on this digest.
    Dtypes and shapes are part of the versioned wire representation.
    """
    digest = hashlib.sha256(b"neural-018-causal-packet/v1\n")
    for name in sorted(set(public) - {"panel_fingerprint"}):
        original = np.asarray(public[name])
        value = np.ascontiguousarray(original)
        header = json.dumps([name, original.dtype.str, list(original.shape)],
                            ensure_ascii=True, separators=(",", ":")).encode("ascii")
        digest.update(len(header).to_bytes(8, "big"))
        digest.update(header)
        digest.update(memoryview(value).cast("B"))
    return digest.hexdigest()


def project(source):
    """Return independent public and operator dictionaries with exact inventories.

    Input axes may be reordered with their IDs and split/unit flags. Preserve
    source row order within each split and source unit order within each group.
    No returned ndarray aliases source storage or the other packet.
    """
    count, trials, units, split, heldout, conditions = _validate_source(source)
    training = np.flatnonzero(split == "train")
    queries = np.flatnonzero(split == "val")
    observed_units = np.flatnonzero(~heldout)
    hidden_units = np.flatnonzero(heldout)
    forecast_units = np.concatenate((observed_units, hidden_units))
    past_bins = np.arange(PAST)
    future_bins = np.arange(PAST, PAST + FUTURE)
    # Every tensor is projected by role before any public serialization. Never
    # write a full panel and then attempt to delete forbidden fields or rows.
    public = {
        "train_spikes_heldin": count[np.ix_(training, past_bins, observed_units)],
        "train_spikes_heldout": count[np.ix_(training, past_bins, hidden_units)],
        "train_future_counts": count[np.ix_(training, future_bins, forecast_units)],
        "eval_spikes_heldin": count[np.ix_(queries, past_bins, observed_units)],
        "train_trial_ids": trials[training].copy(),
        "eval_trial_ids": trials[queries].copy(),
        "heldin_unit_ids": units[observed_units].copy(),
        "heldout_unit_ids": units[hidden_units].copy(),
        "forecast_unit_ids": units[forecast_units].copy(),
        "past_bin_left_edges_ms": np.arange(-250, 450, 5, dtype=np.int64),
        "bin_left_edges_ms": np.arange(450, 650, 5, dtype=np.int64),
        "observation_units": np.asarray("spike_counts_per_5ms_bin"),
        "prediction_units": np.asarray("expected_spikes_per_bin"),
    }
    for name, values in conditions.items():
        public["train_" + name] = values[training].copy()
        public["eval_" + name] = values[queries].copy()
    public["panel_fingerprint"] = np.asarray(_fingerprint(public))
    targets = {
        "target_counts": count[np.ix_(queries, future_bins, forecast_units)],
        "trial_ids": trials[queries].copy(),
        "unit_ids": units[forecast_units].copy(),
        "bin_left_edges_ms": public["bin_left_edges_ms"].copy(),
        "valid_mask": np.ones((QUERY, FUTURE, HELDIN + HELDOUT), dtype=bool),
        "panel_fingerprint": public["panel_fingerprint"].copy(),
    }
    _require(set(public) == PUBLIC_FIELDS and set(targets) == TARGET_FIELDS,
             "Internal projection inventory error")
    return public, targets


def scorer_public(public):
    """Make the exact public-only identity dictionary consumed by scoring-v2."""
    _require(set(public) == PUBLIC_FIELDS, "Exact public packet inventory required")
    _require(str(public["panel_fingerprint"]) == _fingerprint(public),
             "Public packet contents differ from their fingerprint")
    return {
        "trial_ids": public["eval_trial_ids"].copy(),
        "forecast_unit_ids": public["forecast_unit_ids"].copy(),
        "bin_left_edges_ms": public["bin_left_edges_ms"].copy(),
        "prediction_units": public["prediction_units"].copy(),
        "panel_fingerprint": public["panel_fingerprint"].copy(),
    }


def _write_archive(path, bundle):
    # Exclusive creation: a failed or previous preparation is never overwritten.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        np.savez(stream, **bundle)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def write_packets(source, public_dir, operator_dir):
    """Write a new allowlisted public NPZ and a separately rooted operator NPZ.

    Caller must create and isolate the two existing directories. This function
    is an operator utility, not an adversarial filesystem sandbox. The returned
    receipt is operator-only: it includes a private-target archive commitment.
    """
    public_root, private_root = Path(public_dir).resolve(strict=True), Path(operator_dir).resolve(strict=True)
    _require(public_root.is_dir() and private_root.is_dir(), "Existing packet directories required")
    _require(public_root != private_root and public_root not in private_root.parents
             and private_root not in public_root.parents, "Public and operator directories must be disjoint")
    _require(not any(public_root.iterdir()) and not any(private_root.iterdir()),
             "Packet directories must be empty; do not mix participant and operator assets")
    public_path, private_path = public_root / "public_input.npz", private_root / "operator_future_targets.npz"
    _require(not public_path.exists() and not public_path.is_symlink()
             and not private_path.exists() and not private_path.is_symlink(), "Packet destinations must be new")
    public, targets = project(source)
    # Targets are written only under the private root. Never put the operator
    # receipt or private content digest into the participant directory.
    private_pin = _write_archive(private_path, targets)
    public_pin = _write_archive(public_path, public)
    return {
        "schema_version": "neural-018-causal-packet-receipt/v1",
        "panel_fingerprint": str(public["panel_fingerprint"]),
        "public_input": public_pin,
        "operator_targets": private_pin,
        "train_trials": TRAIN,
        "query_trials": QUERY,
        "query_observation_shape": [QUERY, PAST, HELDIN],
        "forecast_shape": [QUERY, FUTURE, HELDIN + HELDOUT],
        "upstream_preprocessing_authenticated_by_this_utility": False,
    }
