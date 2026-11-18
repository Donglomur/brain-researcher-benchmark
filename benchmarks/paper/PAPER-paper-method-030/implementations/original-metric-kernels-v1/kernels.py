"""Conditional arithmetic for CellMincer Fig.3; not a complete paper scorer.

Caller-supplied clocks, threshold grids, weights and spectra are not authenticated
historical inputs. No peak detector, STFT producer, calibration or study pooling
is selected here. The original prospective evaluator remains a separate package.
"""
from __future__ import annotations

from bisect import bisect_left
from fractions import Fraction
import math
import re
from typing import Any


class InputError(ValueError):
    """Invalid explicitly supplied kernel operands."""


class UndefinedMetric(ValueError):
    """The source does not supply the missing support/arithmetic convention."""


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise InputError(message)


def _vector(x: Any, name: str, *, empty: bool = False) -> list:
    _require(isinstance(x, (list, tuple)), f"{name}: list or tuple required")
    _require(empty or bool(x), f"{name}: nonempty sequence required")
    return list(x)


def _number(x: Any, name: str) -> float:
    _require(type(x) in (int, float), f"{name}: finite real number required")
    try:
        value = float(x)
    except OverflowError as exc:
        raise InputError(f"{name}: unrepresentable number") from exc
    _require(math.isfinite(value), f"{name}: finite real number required")
    return value


def _identity(x: Any, name: str) -> str:
    _require(isinstance(x, str) and len(x) == 64 and
             all(c in "0123456789abcdef" for c in x), f"{name}: SHA256 required")
    return x


def _rational(x: Any, name: str) -> Fraction:
    # Explicit decimal/rational strings avoid an invented boundary epsilon.
    _require(isinstance(x, str) and 0 < len(x) <= 96, f"{name}: bounded rational string required")
    _require(re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]+)?|[0-9]+/[1-9][0-9]*)", x) is not None,
             f"{name}: finite decimal or integer-ratio syntax required")
    try:
        result = Fraction(x)
    except (ValueError, ZeroDivisionError) as exc:
        raise InputError(f"{name}: invalid rational") from exc
    _require(result.numerator.bit_length() <= 512 and result.denominator.bit_length() <= 512,
             f"{name}: unsupported numeric extent")
    return result


def _weighted_mean(values: list[float], weights: list[float]) -> float:
    scale = max(weights)
    normalized = [w / scale for w in weights]
    if any(w == 0 for w in normalized):
        raise UndefinedMetric("weight normalization is outside supported numeric range")
    total = math.fsum(normalized)
    try:
        result = math.fsum(v * (w / total) for v, w in zip(values, normalized))
    except (OverflowError, ValueError) as exc:
        raise UndefinedMetric("weighted arithmetic is outside supported numeric range") from exc
    if not math.isfinite(result):
        raise UndefinedMetric("nonfinite weighted arithmetic")
    return result


def fuzzy_peak_score(reference_ticks: Any, predicted_ticks: Any, *,
                     ticks_per_second: int, clock_identity: str) -> dict:
    """Eq.21/22 on an explicit exact tick clock, with strict distance <2 ms.

    No quantization or clock recovery occurs. Each peak independently needs some
    nearby counterpart; matching is not one-to-one. Missing denominators and
    zero/zero harmonic F1 refuse rather than importing a prospective zero policy.
    """
    _require(type(ticks_per_second) is int and 0 < ticks_per_second < 2**128,
             "positive bounded integer ticks_per_second required")
    _identity(clock_identity, "clock_identity")
    def ticks(x: Any, name: str) -> list[int]:
        items = _vector(x, name, empty=True)
        _require(all(type(v) is int and abs(v) < 2**128 for v in items),
                 f"{name}: bounded integer ticks required")
        _require(all(a < b for a, b in zip(items, items[1:])), f"{name}: strictly increasing ticks required")
        return items
    ref = ticks(reference_ticks, "reference")
    pred = ticks(predicted_ticks, "predicted")
    if not ref or not pred:
        raise UndefinedMetric("empty-set convention is not supplied by the original equations")
    def matched(query: list[int], other: list[int]) -> int:
        count = 0
        for tick in query:
            i = bisect_left(other, tick)
            neighbors = other[max(0, i - 1):min(len(other), i + 1)]
            count += any(abs(tick - candidate) * 500 < ticks_per_second for candidate in neighbors)
        return count
    matched_pred = matched(pred, ref)
    matched_ref = matched(ref, pred)
    precision = Fraction(matched_pred, len(pred))
    recall = Fraction(matched_ref, len(ref))
    if precision + recall == 0:
        raise UndefinedMetric("zero/zero F1 convention is not supplied by the original equations")
    return {"reference_count": len(ref), "predicted_count": len(pred),
            "matched_reference_count": matched_ref, "matched_predicted_count": matched_pred,
            "precision": float(precision), "recall": float(recall),
            "f1": float(2 * precision * recall / (precision + recall)),
            "clock_identity": clock_identity, "clock_authenticated": False}


def prominence_bin_profile(*, ep_thresholds_mv: Any, optical_thresholds_mv: Any,
                           f1_values: Any, bins: Any, grid_identity: str,
                           bin_rule_identity: str) -> dict:
    """Maximize over supplied q states per p, THEN form explicit weighted bins.

    This computes conditional supplied-grid maxima, not certified continuous
    Eq.23 optima. The producer must eventually establish original peak/grid/bin
    semantics; hashes supplied here are labels, not evidence of that recovery.
    Each bin supplies p indices and positive weights; no study scalar is made.
    """
    _identity(grid_identity, "grid_identity")
    _identity(bin_rule_identity, "bin_rule_identity")
    p_text = _vector(ep_thresholds_mv, "EP thresholds")
    ps = [_rational(p, "EP threshold") for p in p_text]
    _require(all(p >= 0 for p in ps) and all(a < b for a, b in zip(ps, ps[1:])),
             "EP thresholds must be nonnegative and strictly increasing")
    q_rows = _vector(optical_thresholds_mv, "optical threshold rows")
    score_rows = _vector(f1_values, "F1 rows")
    _require(len(q_rows) == len(score_rows) == len(ps), "threshold/F1 row coverage mismatch")
    maxima = []
    for p, qs_raw, scores_raw in zip(ps, q_rows, score_rows):
        qs = [_rational(q, "optical threshold") for q in _vector(qs_raw, "optical row")]
        scores = [_number(v, "F1") for v in _vector(scores_raw, "F1 row")]
        _require(len(qs) == len(scores), "optical threshold/F1 state coverage mismatch")
        _require(all(a < b for a, b in zip(qs, qs[1:])), "optical thresholds must be strictly increasing")
        _require(all(p - Fraction(1, 5) <= q <= p + Fraction(1, 5) for q in qs),
                 "optical threshold lies outside the source plus/minus0.2mV interval")
        _require(all(0 <= value <= 1 for value in scores), "F1 outside [0,1]")
        maxima.append(max(scores))
    output = []
    used = set()
    names = set()
    for item in _vector(bins, "bins"):
        _require(isinstance(item, dict) and set(item) == {"id", "p_indices", "weights"},
                 "each bin requires only id, p_indices and weights")
        name = item["id"]
        _require(isinstance(name, str) and 0 < len(name) <= 256 and name not in names, "unique bounded bin id required")
        names.add(name)
        indices = _vector(item["p_indices"], "bin p indices")
        _require(all(type(i) is int and 0 <= i < len(ps) for i in indices), "invalid bin p index")
        _require(len(set(indices)) == len(indices), "duplicate p index within bin")
        weights = [_number(w, "bin weight") for w in _vector(item["weights"], "bin weights")]
        _require(len(weights) == len(indices) and all(w > 0 for w in weights), "positive complete bin weights required")
        used.update(indices)
        output.append({"id": name, "p_indices": indices, "weights": weights,
                       "mean_supplied_grid_max_f1": _weighted_mean([maxima[i] for i in indices], weights)})
    _require(used == set(range(len(ps))), "bins must retain every supplied p threshold")
    return {"ep_thresholds_mv": p_text, "supplied_grid_max_f1": maxima, "bins": output,
            "grid_identity": grid_identity, "bin_rule_identity": bin_rule_identity,
            "continuous_optimum_established": False, "historical_recipe_authenticated": False}


def residual_noise_profile(*, frequency_hz: Any, window_ids: Any, ep_power: Any,
                           raw_residual_power: Any, method_residual_power: Any,
                           ep_sum_frequency_indices: Any, ep_power_threshold: Any,
                           time_weights: Any, db_power_reference: Any, power_floor: Any,
                           transform_identity: str, time_grid_identity: str,
                           mask_rule_identity: str, db_rule_identity: str) -> dict:
    """Common EP-derived support; power-to-dB THEN explicit time reduction.

    All spectra are supplied operands. This function neither produces an STFT
    nor authenticates its64/48/source normalization, alignment or time grid.
    Transform, mask, dB/floor and time-weight choices are mandatory, never defaults.
    No above100Hz or cross-recording scalar is produced.
    """
    for name, value in (("transform_identity", transform_identity), ("time_grid_identity", time_grid_identity),
                        ("mask_rule_identity", mask_rule_identity), ("db_rule_identity", db_rule_identity)):
        _identity(value, name)
    frequencies = [_number(f, "frequency") for f in _vector(frequency_hz, "frequencies")]
    _require(all(f >= 0 for f in frequencies) and all(a < b for a, b in zip(frequencies, frequencies[1:])),
             "frequencies must be nonnegative and strictly increasing")
    windows = _vector(window_ids, "window ids")
    _require(all(isinstance(w, str) and 0 < len(w) <= 256 for w in windows) and len(set(windows)) == len(windows),
             "unique bounded window ids required")
    def matrix(x: Any, name: str) -> list[list[float]]:
        rows = _vector(x, name)
        _require(len(rows) == len(frequencies), f"{name}: frequency coverage mismatch")
        out = []
        for row in rows:
            values = [_number(v, name) for v in _vector(row, name)]
            _require(len(values) == len(windows) and all(v >= 0 for v in values), f"{name}: nonnegative complete window powers required")
            out.append(values)
        return out
    ep = matrix(ep_power, "EP power")
    raw = matrix(raw_residual_power, "raw residual power")
    _require(isinstance(method_residual_power, dict) and bool(method_residual_power), "named method powers required")
    methods = {}
    for name, value in method_residual_power.items():
        _require(isinstance(name, str) and 0 < len(name) <= 256 and name != "raw", "nonreserved bounded method name required")
        methods[name] = matrix(value, f"{name} residual power")
    indices = _vector(ep_sum_frequency_indices, "EP total-power indices")
    _require(all(type(i) is int and 0 <= i < len(frequencies) for i in indices) and
             len(set(indices)) == len(indices), "unique valid EP total-power indices required")
    threshold = _number(ep_power_threshold, "EP power threshold")
    _require(threshold >= 0, "EP power threshold must be nonnegative")
    weights = [_number(w, "time weight") for w in _vector(time_weights, "time weights")]
    _require(len(weights) == len(windows) and all(w > 0 for w in weights), "positive complete time weights required")
    reference = _number(db_power_reference, "dB power reference")
    _require(reference > 0, "positive dB power reference required")
    floor = None if power_floor is None else _number(power_floor, "power floor")
    _require(floor is None or floor > 0, "power floor must be explicit None or positive")
    try:
        totals = [math.fsum(ep[i][j] for i in indices) for j in range(len(windows))]
    except OverflowError as exc:
        raise UndefinedMetric("EP total spectral power outside supported numeric range") from exc
    mask = [total <= threshold for total in totals]
    kept = [i for i, eligible in enumerate(mask) if eligible]
    if not kept:
        raise UndefinedMetric("no EP-eligible windows; no empty-support convention selected")
    selected_weights = [weights[i] for i in kept]
    def mean_db(powers: list[list[float]]) -> list[float]:
        output = []
        for row in powers:
            values = []
            for i in kept:
                power = max(row[i], floor) if floor is not None else row[i]
                if power == 0:
                    raise UndefinedMetric("zero retained power without an explicit positive floor")
                values.append(10 * (math.log10(power) - math.log10(reference)))
            output.append(_weighted_mean(values, selected_weights))
        return output
    raw_db = mean_db(raw)
    outputs = {}
    for name, powers in methods.items():
        db = mean_db(powers)
        gains = [a - b for a, b in zip(raw_db, db)]
        if not all(math.isfinite(g) for g in gains):
            raise UndefinedMetric("nonfinite noise reduction")
        outputs[name] = {"mean_residual_db": db, "noise_reduction_db": gains}
    return {"frequency_hz": frequencies, "window_ids": windows, "ep_total_power": totals,
            "ep_eligible_mask": mask, "time_weights": weights, "raw_mean_residual_db": raw_db,
            "methods": outputs, "transform_identity": transform_identity,
            "time_grid_identity": time_grid_identity, "mask_rule_identity": mask_rule_identity,
            "db_rule_identity": db_rule_identity, "historical_recipe_authenticated": False}
