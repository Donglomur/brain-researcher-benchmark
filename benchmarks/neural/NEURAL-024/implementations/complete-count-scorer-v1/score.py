"""Offline mathematics for the fixed, exposed NEURAL-024 development episode.

This module does not admit transcripts or establish commit-before-reveal access.
Only operator-owned observations and pre-frozen reference means may be scored.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Iterable, Iterator

CHANNELS = 96
ROUNDS = 22100
WARMUP = 10
SCORED_ROWS = ROUNDS - WARMUP
REFERENCE_NAMES = (
    "source_rate", "calibration_rate", "self_history_frozen",
    "self_history_adapted", "self_population_history_frozen",
    "self_population_history_adapted",
)
UINT32_MAX = 2**32 - 1


class ScoreError(ValueError):
    """Incomplete support, invalid numerical values, or untrusted source bytes."""


class _Sum:
    """Neumaier sum with explicit failure, never clipping finite overflow."""

    __slots__ = ("value", "correction")

    def __init__(self) -> None:
        self.value = self.correction = 0.0

    def add(self, x: float) -> None:
        if not math.isfinite(x):
            raise ScoreError("nonfinite Poisson arithmetic")
        total = self.value + x
        if not math.isfinite(total):
            raise ScoreError("Poisson accumulation overflow")
        if abs(self.value) >= abs(x):
            self.correction += (self.value - total) + x
        else:
            self.correction += (x - total) + self.value
        self.value = total
        if not math.isfinite(self.correction):
            raise ScoreError("Poisson correction overflow")

    def finish(self) -> float:
        value = self.value + self.correction
        if not math.isfinite(value):
            raise ScoreError("Poisson total overflow")
        return value


def _vector(value: object, *, counts: bool = False) -> tuple:
    if not isinstance(value, list) or len(value) != CHANNELS:
        raise ScoreError("every row must contain all 96 channels")
    if counts:
        if any(type(x) is not int or not 0 <= x <= UINT32_MAX for x in value):
            raise ScoreError("observations must be uint32-compatible integer counts")
        return tuple(value)
    result = []
    for x in value:
        if type(x) not in (int, float):
            raise ScoreError("means must be real numbers, not booleans or strings")
        try:
            x = float(x)
        except (ValueError, OverflowError) as exc:
            raise ScoreError("mean is not float64-compatible") from exc
        if not math.isfinite(x) or x <= 0:
            raise ScoreError("means must be strictly positive and finite")
        result.append(x)
    return tuple(result)


def _record(value: object, sequence: int, keys: set[str]) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise ScoreError("record fields do not match the scoring schema")
    if type(value["sequence"]) is not int or value["sequence"] != sequence:
        raise ScoreError("missing, duplicate, or out-of-order sequence")
    return value


def _fsum(values: Iterable[float]) -> float:
    try:
        result = math.fsum(values)
    except (ValueError, OverflowError) as exc:
        raise ScoreError("Poisson reduction overflow") from exc
    if not math.isfinite(result):
        raise ScoreError("nonfinite Poisson reduction")
    return result


def _bps(gain: float, spikes: int) -> float | None:
    if spikes == 0:
        return None
    value = (gain / spikes) / math.log(2.0)
    if not math.isfinite(value):
        raise ScoreError("bits-per-spike arithmetic overflow")
    return value


def score_records(predictions: Iterable[dict], outcomes: Iterable[dict]) -> dict:
    """Score complete offline streams on the original fixed support.

    ``outcomes`` must contain operator-owned counts and all six immutable
    reference mean vectors. The caller is responsible for their provenance;
    ``score_files`` additionally requires a trusted SHA-256 supplied externally.
    No fitting, reference regeneration, target selection or scaling occurs here.
    """
    predictions, outcomes = iter(predictions), iter(outcomes)
    likelihood = [_Sum() for _ in range(CHANNELS)]
    gains = {name: [_Sum() for _ in range(CHANNELS)] for name in REFERENCE_NAMES}
    spikes = [0] * CHANNELS
    missing = object()
    for sequence in range(ROUNDS):
        prediction, outcome = next(predictions, missing), next(outcomes, missing)
        if prediction is missing or outcome is missing:
            raise ScoreError("complete 22100-round support is required; partial score forbidden")
        prediction = _record(prediction, sequence, {"sequence", "means"})
        outcome = _record(outcome, sequence, {"sequence", "counts", "reference_means"})
        means = _vector(prediction["means"])
        counts = _vector(outcome["counts"], counts=True)
        reference = outcome["reference_means"]
        if not isinstance(reference, dict) or set(reference) != set(REFERENCE_NAMES):
            raise ScoreError("exactly the six immutable references are required")
        refs = {name: _vector(reference[name]) for name in REFERENCE_NAMES}
        # Every warm-up row is required and validated, but has no metric support.
        if sequence < WARMUP:
            continue
        for channel, (count, mean) in enumerate(zip(counts, means)):
            log_mean = math.log(mean)
            likelihood[channel].add(count * log_mean - mean - math.lgamma(count + 1))
            spikes[channel] += count
            for name in REFERENCE_NAMES:
                ref = refs[name][channel]
                # Direct contrast avoids subtracting two large full likelihoods.
                # Separate logarithms avoid overflow/underflow from mean / ref.
                gains[name][channel].add(count * (log_mean - math.log(ref)) - (mean - ref))
    if next(predictions, missing) is not missing or next(outcomes, missing) is not missing:
        raise ScoreError("extra rounds are forbidden")
    per_ll = [value.finish() for value in likelihood]
    per_gain = {name: [value.finish() for value in gains[name]] for name in REFERENCE_NAMES}
    total_spikes = sum(spikes)
    total_ll = _fsum(per_ll)
    contrasts = {name: _fsum(per_gain[name]) for name in REFERENCE_NAMES}
    per_channel = [{
        "channel_index": channel,
        "observed_spikes": spikes[channel],
        "full_poisson_log_likelihood": per_ll[channel],
        "mean_nll": -per_ll[channel] / SCORED_ROWS,
        "bits_per_spike": {name: _bps(per_gain[name][channel], spikes[channel]) for name in REFERENCE_NAMES},
        "log_likelihood_gain": {name: per_gain[name][channel] for name in REFERENCE_NAMES},
        "denominator_status": "defined" if spikes[channel] else "undefined_zero_spikes",
    } for channel in range(CHANNELS)]
    return {
        "schema": "neural024-offline-poisson-score/v1",
        "task_id": "NEURAL-024",
        "scope": "exposed_one_monkey_one_day_pair_development",
        "causal_access_established": False,
        "protocol_rounds": ROUNDS,
        "warmup_rounds_excluded": WARMUP,
        "scored_rows": SCORED_ROWS,
        "scored_cells": SCORED_ROWS * CHANNELS,
        "target_bin_first": 3010,
        "target_bin_last": 25099,
        "bin_seconds": 0.02,
        "mean_unit": "count_per_bin",
        "observed_spikes": total_spikes,
        "denominator_status": "defined" if total_spikes else "undefined_zero_spikes",
        "bits_per_spike_vs_calibration_rate": _bps(contrasts["calibration_rate"], total_spikes),
        "full_poisson_log_likelihood": total_ll,
        "mean_nll": -total_ll / (SCORED_ROWS * CHANNELS),
        "signed_reference_contrasts": {name: {
            "log_likelihood_gain": contrasts[name],
            "bits_per_spike": _bps(contrasts[name], total_spikes),
        } for name in REFERENCE_NAMES},
        "per_channel": per_channel,
    }


def _object(pairs: list) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ScoreError("duplicate JSON field")
        value[key] = item
    return value


def _invalid_constant(value: str) -> None:
    raise ScoreError("nonfinite JSON constant")


def _jsonl(handle, max_bytes: int, digest=None) -> Iterator[dict]:
    while True:
        line = handle.readline(max_bytes + 1)
        if not line:
            return
        if digest is not None:
            digest.update(line)
        if len(line) > max_bytes or not line.endswith(b"\n"):
            raise ScoreError("oversized or unterminated JSONL record")
        try:
            yield json.loads(line.decode("utf-8"), object_pairs_hook=_object,
                             parse_constant=_invalid_constant)
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
            raise ScoreError("invalid JSONL record") from exc


def score_files(predictions: Path, operator_outcomes: Path, operator_sha256: str) -> dict:
    """Read once, hash the exact consumed operator stream, then release a score.

    The expected digest must be frozen by the trusted operator before candidate
    evaluation. A candidate-authored digest does not establish provenance.
    """
    if not re.fullmatch(r"[0-9a-f]{64}", operator_sha256):
        raise ScoreError("expected operator SHA-256 must be 64 lowercase hex characters")
    digest = hashlib.sha256()
    with Path(predictions).open("rb") as candidate, Path(operator_outcomes).open("rb") as truth:
        result = score_records(_jsonl(candidate, 4096), _jsonl(truth, 65536, digest))
    if digest.hexdigest() != operator_sha256:
        raise ScoreError("operator outcome/reference stream SHA-256 mismatch")
    result["operator_stream_sha256"] = operator_sha256
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--operator-outcomes", type=Path, required=True)
    parser.add_argument("--operator-sha256", required=True)
    args = parser.parse_args()
    try:
        result = score_files(args.predictions, args.operator_outcomes, args.operator_sha256)
    except (ScoreError, OSError) as exc:
        parser.exit(2, f"No score: {exc}\n")
    print(json.dumps(result, allow_nan=False, sort_keys=True))


if __name__ == "__main__":
    main()
