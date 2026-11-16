"""Prospective continuous-widefield owner preparation; no model or SVD fitting.

Only serialized records cross the participant boundary. Trusted Python loaders,
sinks and returned owner state are not an adversarial execution boundary.
"""
from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction
import hashlib
import json
import math

import trial_preparation as trials

POLICY = "sbind-train-only-continuous-normalization-v1"
PIXELS = 128 * 128
ROLES = ("train", "validation", "test")


def _require(ok, message):
    trials._require(ok, message)


def _number(value):
    _require(type(value) in (int, float), "finite binary64 numeric value required")
    try:
        result = float(value)
    except OverflowError as exc:
        raise trials.AdmissionError("value outside binary64") from exc
    _require(math.isfinite(result), "nonfinite numeric value")
    return result


def _sequence(value, length):
    _require(isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
             and len(value) == length, "complete numeric dimension required")
    return value


def _neural(value):
    plane = _sequence(value, 1)[0]
    _sequence(plane, 128)
    return tuple(_number(x) for row in plane for x in _sequence(row, 128))


def _behavior(value, channels):
    return tuple(_number(x) for x in _sequence(value, channels))


def _sqrt_ratio(value):
    """Square root of an exact nonnegative variance without squaring float limits."""
    _require(value >= 0, "negative population variance")
    if not value:
        return 1.0
    exponent = (value.numerator.bit_length() - value.denominator.bit_length()) // 2
    scale = Fraction(2) ** (2 * exponent)
    try:
        result = math.ldexp(math.sqrt(float(value / scale)), exponent)
    except OverflowError as exc:
        raise trials.AdmissionError("unrepresentable population SD") from exc
    _require(math.isfinite(result) and result > 0, "unrepresentable nonzero population SD")
    return result


def _standardize(value, mean, scale):
    result = (value - mean) / scale
    if not math.isfinite(result):
        try:
            result = float((Fraction(value) - Fraction(mean)) / Fraction(scale))
        except OverflowError as exc:
            raise trials.AdmissionError("unrepresentable normalized value") from exc
    _require(math.isfinite(result), "unrepresentable normalized value")
    return result


def admit_representations(raw, expected, protocol):
    """Check all ten owner declarations before any source values are requested.

    Hashes authenticate declaration bytes, not the truth of their fit provenance.
    The owner must separately authenticate original values and both fitted SVDs.
    """
    value = trials._load(raw, expected)
    trials._keys(value, ("schema", "task_id", "census_sha256", "split_sha256", "folds"))
    _require(value["schema"] == "sbind-owner-fold-representations-v1" and
             value["task_id"] == trials.TASK and value["census_sha256"] == protocol.census_sha256
             and value["split_sha256"] == protocol.split_sha256, "wrong representation grid")
    rows = value["folds"]
    _require(type(rows) is list and len(rows) == 10, "both assays and all five representation folds required")
    for row, (assay, fold) in zip(rows, ((a, f) for a in protocol.assays for f in a.folds)):
        trials._keys(row, ("assay_id", "fold", "source_sha256", "representation_sha256",
                          "fit_trial_ids", "fitted_artifact_sha256", "method_source_sha256"))
        _require(row["assay_id"] == assay.assay_id and type(row["fold"]) is int and
                 row["fold"] == fold.number and row["source_sha256"] == assay.source_sha256
                 and row["representation_sha256"] == assay.representation_sha256,
                 "representation does not match selected full source/fold")
        _require(row["fit_trial_ids"] == [s.trial_id for s in fold.train],
                 "representation fitting must declare exactly the training trials in source order")
        trials._hash(row["fitted_artifact_sha256"]); trials._hash(row["method_source_sha256"])
    return tuple(rows)


def fit_training(view, channels):
    """Owner-only fit: per-pixel means, one raw-image SD, per-channel behavior stats.

    Exact rational accumulation follows binary64 conversion. Rounding therefore
    need not match NumPy 1.24.1. This implements the source's mathematical formula,
    not a historical numerical reproduction or the missing SVD computation.
    """
    _require(len(view) > 0 and type(channels) is int and 0 < channels <= 4096,
             "nonempty training view and declared channels required")
    pixel_sum = [Fraction(0) for _ in range(PIXELS)]
    raw_sum = Fraction(0); raw_square = Fraction(0)
    z_sum = [Fraction(0) for _ in range(channels)]
    z_square = [Fraction(0) for _ in range(channels)]
    count = 0
    for frame in view:
        y = _neural(frame.neural); z = _behavior(frame.behavior, channels)
        for i, value in enumerate(y):
            exact = Fraction(value)
            pixel_sum[i] += exact
            raw_sum += exact; raw_square += exact * exact
        for i, value in enumerate(z):
            exact = Fraction(value); z_sum[i] += exact; z_square[i] += exact * exact
        count += 1
    raw_count = count * PIXELS
    raw_mean = raw_sum / raw_count
    return {"policy": POLICY, "training_frames": count,
            "neural_mean": tuple(float(x / count) for x in pixel_sum),
            "neural_sd": _sqrt_ratio(raw_square / raw_count - raw_mean * raw_mean),
            "behavior_mean": tuple(float(x / count) for x in z_sum),
            "behavior_sd": tuple(_sqrt_ratio(z_square[i] / count - (z_sum[i] / count) ** 2)
                                 for i in range(channels))}


def _encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


class _Writer:
    def __init__(self, sink):
        self.sink = sink; self.sha = hashlib.sha256(); self.bytes = 0; self.records = 0

    def put(self, value):
        raw = _encode(value)
        position = 0
        while position < len(raw):
            written = self.sink.write(raw[position:])
            _require(type(written) is int and 0 < written <= len(raw) - position,
                     "sink did not complete a bounded write")
            self.sha.update(raw[position:position + written]); self.bytes += written; position += written
        self.records += 1

    def receipt(self):
        return {"bytes": self.bytes, "sha256": self.sha.hexdigest(), "records": self.records}


def _identity(frame, role):
    return {"role": role, "source_index": frame.source_index, "trial_id": frame.trial_id,
            "trial_offset": frame.trial_offset, "reset": frame.reset}


def prepare_selected_fold(census_bytes, split_bytes, representations_bytes, *,
                          census_sha256, split_sha256, representations_sha256,
                          assay_id, fold, source_loader, sinks, owner_targets_sink):
    """Write one complete assay/fold; all ten metadata folds are admitted first.

    `source_loader(assay, fold, representation_declaration)` is a trusted owner
    function returning the existing SourceRows type. Sinks must be trusted binary
    writers to externally separated destinations. Only the serialized participant
    streams may be exposed to candidate code. Neither Python nor file mounts are
    isolated here. No success receipt is returned after a partial/failed write;
    the owner must discard all partial streams and perform durable publication.
    """
    protocol = trials.compile_protocol(census_bytes, split_bytes, census_sha256=census_sha256,
                                       split_sha256=split_sha256)
    representations = admit_representations(representations_bytes, representations_sha256, protocol)
    _require(assay_id in trials.COUNTS, "unknown assay")
    trials._integer(fold, 0, 4)
    trials._keys(sinks, ROLES)
    _require(len({id(x) for x in (*sinks.values(), owner_targets_sink)}) == 4,
             "distinct participant and owner sinks required")
    assay = next(a for a in protocol.assays if a.assay_id == assay_id)
    declaration = next(x for x in representations if x["assay_id"] == assay_id and x["fold"] == fold)
    # Reuse the admitted full-source interface and complete extent checks unchanged.
    views = trials.prepare_fold(census_bytes, split_bytes, census_sha256=census_sha256,
                                split_sha256=split_sha256, assay_id=assay_id, fold=fold,
                                source_loader=lambda admitted: source_loader(admitted, fold, declaration))
    stats = fit_training(views["train"], len(assay.channels))
    stats_pin = hashlib.sha256(_encode(stats)).hexdigest()
    writers = {role: _Writer(sinks[role]) for role in ROLES}
    targets = _Writer(owner_targets_sink)
    common = {"schema": "sbind-normalized-fold-stream-v1", "task_id": trials.TASK,
              "policy": POLICY, "assay_id": assay_id, "fold": fold,
              "census_sha256": census_sha256, "split_sha256": split_sha256,
              "representations_sha256": representations_sha256, "normalization_sha256": stats_pin,
              "neural_shape": list(trials.SHAPE), "behavior_channels": list(assay.channels),
              "model_call_policy": "complete-single-trial-sequence-reset-true-at-every-trial-no-tail-drop"}
    for role in ROLES:
        writers[role].put(dict(common, role=role, record="header", includes_behavior=role == "train"))
        for frame in views[role]:
            normalized = tuple(_standardize(x, mean, stats["neural_sd"])
                               for x, mean in zip(_neural(frame.neural), stats["neural_mean"]))
            record = dict(_identity(frame, role), record="frame",
                          neural=[[list(normalized[i:i+128]) for i in range(0, PIXELS, 128)]])
            if role == "train":
                record["behavior"] = [_standardize(x, mean, sd) for x, mean, sd in
                                      zip(_behavior(frame.behavior, len(assay.channels)),
                                          stats["behavior_mean"], stats["behavior_sd"])]
            writers[role].put(record)
    # Private targets are inspected only after all participant streams complete.
    targets.put(dict(common, role="owner-held-targets", record="header", includes_behavior=True))
    for role in ("validation", "test"):
        for frame in views[role]:
            targets.put(dict(_identity(frame, role), record="target",
                             behavior=[_standardize(x, mean, sd) for x, mean, sd in
                                       zip(_behavior(frame.behavior, len(assay.channels)),
                                           stats["behavior_mean"], stats["behavior_sd"])]))
    return {"schema": "sbind-owner-normalization-result-v1", "task_id": trials.TASK,
            "assay_id": assay_id, "fold": fold, "normalization": stats,
            "normalization_sha256": stats_pin,
            "participant_streams": {role: writer.receipt() for role, writer in writers.items()},
            "owner_targets": targets.receipt(),
            "complete_selected_fold_frames": {role: len(views[role]) for role in ROLES},
            "historical_reproduction_qualified": False, "runtime_isolation_qualified": False,
            "durable_publication_qualified": False, "whole_grid_execution_qualified": False}
