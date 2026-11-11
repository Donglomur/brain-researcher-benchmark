"""Prospective NEURAL092 pairing, state effects, and metadata-only sensitivity.

No recording I/O, state estimation, baseline fitting, model, or genetic-class
inference. Caller binds the complete frozen session/mouse/unit roster and state
thresholds. All means use exact rational representations of admitted float64
rates, preserving signed differences and avoiding rounded intermediate scores.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import math
from types import MappingProxyType
from typing import Mapping

import numpy as np

AREAS = ("VISp", "VISl", "VISal", "VISrl", "VISam", "VISpm")
RUN_BINS = ("REST", "RUN", "TRANSITION", "MISSING")
PUPIL_BINS = ("LOW", "MID", "HIGH", "MISSING")
MATCH_BINS = {"FITbaseline": (1., 2., 4., 8., 16., 32., 64.),
              "presence_ratio": (.97, .99), "isi_violations": (.1, .3),
              "amplitude_cutoff": (.05,)}


class StateInputError(ValueError):
    pass


def _real(value, name):
    try:
        a = np.asarray(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise StateInputError(f"{name}: real numeric input required") from exc
    if a.dtype.kind not in "fiu":
        raise StateInputError(f"{name}: real numeric input required")
    with np.errstate(over="ignore", invalid="ignore"):
        a = a.astype(np.float64, copy=False)
    if not np.isfinite(a).all():
        raise StateInputError(f"{name}: finite float64 required")
    return a


def _number(value, name):
    a = _real(value, name)
    if a.ndim:
        raise StateInputError(f"{name}: scalar required")
    return float(a)


def _ids(values, name):
    if isinstance(values, (str, bytes)):
        raise StateInputError(f"{name}: ID sequence required")
    values = tuple(values)
    if not values or any(not isinstance(v, str) or not v for v in values) or len(set(values)) != len(values):
        raise StateInputError(f"{name}: nonempty unique string IDs required")
    return values


def _scalar(value, reason="undefined_no_pairs"):
    if value is None:
        return {"status": reason, "value": None, "decimal": None, "float64_status": "not_applicable"}
    with localcontext() as ctx:
        ctx.prec = 100
        decimal = Decimal(value.numerator) / Decimal(value.denominator)
    try:
        represented = float(value)
    except OverflowError:
        represented = math.inf if value > 0 else -math.inf
    if not math.isfinite(represented):
        represented, disposition = None, "overflow"
    elif represented == 0 and value != 0:
        represented, disposition = None, "underflow"
    else:
        disposition = "representable"
    return {"status": "finite", "value": represented, "decimal": str(decimal),
            "float64_status": disposition}


@dataclass(frozen=True)
class PairingResult:
    mode: str
    row_count: int
    low_indices: tuple[int, ...]
    high_indices: tuple[int, ...]
    pairs: tuple[dict, ...]
    unused: tuple[dict, ...]

    def report(self):
        return {"mode": self.mode, "rows": self.row_count, "pair_count": len(self.low_indices),
                "pairs": list(self.pairs), "unused": list(self.unused),
                "policy": "within exact stimulus/block/other-state stratum; chronological zip; no reuse",
                "missing_pupil_pairs": sum(p["other_state_bin"] == "MISSING" for p in self.pairs)}


def deterministic_pairs(rows, mode="running"):
    """Match from metadata only; every unused trial has an explicit reason.

    IDs are unique strings, onset finite/nonnegative, block integer, and the
    condition_key is a tuple of canonical strings/finite floats. Running uses
    REST->RUN, matched also on pupil bin (MISSING is an explicit allowed bin).
    Pupil uses LOW->HIGH, matched also on REST/RUN. TRANSITION/MISSING running
    states are excluded in both modes; MID/MISSING pupils excluded only in pupil.
    """
    if mode not in ("running", "pupil"):
        raise StateInputError("mode must be running or pupil")
    if not isinstance(rows, (list, tuple)):
        raise StateInputError("rows must be a concrete sequence")
    groups, unused, seen, admitted = defaultdict(lambda: ([], [])), [], set(), []
    required = {"id", "onset", "condition_key", "block", "run_bin", "pupil_bin"}
    # Validate the complete metadata panel before constructing any matches.
    for i, row in enumerate(rows):
        if not isinstance(row, Mapping) or set(row) != required:
            raise StateInputError("exact trial metadata fields required")
        uid = row["id"]
        if not isinstance(uid, str) or not uid or uid in seen:
            raise StateInputError("unique nonempty trial IDs required")
        seen.add(uid)
        onset = _number(row["onset"], "onset")
        if onset < 0 or type(row["block"]) is not int:
            raise StateInputError("nonnegative onset/integer block required")
        condition = row["condition_key"]
        if not isinstance(condition, tuple) or not condition:
            raise StateInputError("nonempty canonical tuple condition required")
        if any(not (isinstance(x, str) or (type(x) is float and math.isfinite(x))) for x in condition):
            raise StateInputError("condition fields must be canonical strings/finite floats")
        if row["run_bin"] not in RUN_BINS or row["pupil_bin"] not in PUPIL_BINS:
            raise StateInputError("unknown state bin")
        admitted.append((i, uid, onset, condition, row["block"], row["run_bin"], row["pupil_bin"]))
    for i, uid, onset, condition, block, run, pupil in admitted:
        if run in ("TRANSITION", "MISSING"):
            unused.append({"index": i, "id": uid, "reason": "excluded_running_" + run.lower()})
            continue
        if mode == "pupil" and pupil in ("MID", "MISSING"):
            unused.append({"index": i, "id": uid, "reason": "excluded_pupil_" + pupil.lower()})
            continue
        other, state = (pupil, run) if mode == "running" else (run, pupil)
        side = 0 if state in ("REST", "LOW") else 1
        groups[(condition, block, other)][side].append((onset, uid, i))
    pairs = []
    for (condition, block, other), (low, high) in groups.items():
        low.sort()
        high.sort()
        size = min(len(low), len(high))
        for a, b in zip(low[:size], high[:size]):
            pairs.append({"low_index": a[2], "high_index": b[2], "low_id": a[1], "high_id": b[1],
                          "condition_key": condition, "block": block, "other_state_bin": other,
                          "low_onset": a[0], "high_onset": b[0]})
        for label, remainder in (("low", low[size:]), ("high", high[size:])):
            unused.extend({"index": x[2], "id": x[1], "reason": "unmatched_" + label} for x in remainder)
    pairs.sort(key=lambda p: (p["low_onset"], p["high_onset"], p["low_id"], p["high_id"]))
    unused.sort(key=lambda u: u["index"])
    return PairingResult(mode, len(rows), tuple(p["low_index"] for p in pairs),
                         tuple(p["high_index"] for p in pairs), tuple(pairs), tuple(unused))


@dataclass(frozen=True)
class EffectVector:
    values: tuple[Fraction | None, ...]
    pairs: int
    trials: int

    def report(self):
        return {"pairs": self.pairs, "trials": self.trials, "units": len(self.values),
                "effects": [_scalar(v) for v in self.values],
                "estimand": "mean paired (high-rate minus low-rate) / same-unit fixed FIT baseline"}


def unit_effects(rates, pairs: PairingResult, baseline_rates):
    rates = _real(rates, "query trial rates")
    baseline = _real(baseline_rates, "FIT baseline rates")
    if rates.ndim != 2 or rates.shape[1] < 1 or np.any(rates < 0):
        raise StateInputError("nonnegative [trials,units] rates required")
    if baseline.shape != (rates.shape[1],) or np.any(baseline <= 0):
        raise StateInputError("one strictly positive FIT baseline per unit required")
    if not isinstance(pairs, PairingResult) or pairs.row_count != rates.shape[0]:
        raise StateInputError("pairing must match complete trial rows")
    indices = pairs.low_indices + pairs.high_indices
    if len(pairs.low_indices) != len(pairs.high_indices) or any(type(i) is not int or i < 0 or i >= rates.shape[0] for i in indices) or len(set(indices)) != len(indices):
        raise StateInputError("paired trial indices must be valid and unreused")
    n = len(pairs.low_indices)
    if n == 0:
        return EffectVector((None,) * rates.shape[1], 0, rates.shape[0])
    result = []
    for j in range(rates.shape[1]):
        difference = sum((Fraction.from_float(float(rates[h, j])) - Fraction.from_float(float(rates[l, j]))
                          for l, h in zip(pairs.low_indices, pairs.high_indices)), Fraction())
        result.append(difference / n / Fraction.from_float(float(baseline[j])))
    return EffectVector(tuple(result), n, rates.shape[0])


@dataclass(frozen=True)
class AreaEffects:
    values: Mapping[str, Fraction | None]
    unit_counts: Mapping[str, int]
    pairs: int

    def report(self):
        return {"areas": {a: {"units": self.unit_counts[a],
                              "effect": _scalar(v, "absent_area" if self.unit_counts[a] == 0 else "undefined_no_pairs")}
                          for a, v in self.values.items()}, "pairs": self.pairs,
                "weighting": "equal units within each fixed anatomical area; no genetic-class inference"}


def area_effects(effects: EffectVector, area_labels, required_areas=AREAS):
    roster = _ids(required_areas, "area roster")
    labels = tuple(area_labels)
    if not isinstance(effects, EffectVector) or len(labels) != len(effects.values) or any(a not in roster for a in labels):
        raise StateInputError("one admitted area label per unit required")
    values, counts = {}, {}
    for area in roster:
        selected = [v for v, a in zip(effects.values, labels) if a == area]
        counts[area] = len(selected)
        values[area] = (sum(selected, Fraction()) / len(selected)
                        if selected and all(v is not None for v in selected) else None)
    return AreaEffects(MappingProxyType(values), MappingProxyType(counts), effects.pairs)


@dataclass(frozen=True)
class SessionError:
    value: Fraction | None
    available_areas: tuple[str, ...]
    absent_or_undefined_areas: tuple[str, ...]

    def report(self):
        return {"mean_absolute_error": _scalar(self.value, "undefined_no_available_areas"),
                "available_areas": list(self.available_areas),
                "absent_or_undefined_areas": list(self.absent_or_undefined_areas),
                "weighting": "equal available fixed-area effects"}


def mean_absolute_error(candidate: Mapping[str, float | None], expected: AreaEffects):
    """Finite candidate area effects; absent/undefined target areas require null.

    Error is computed against exact effects, not their rounded reports. Large
    finite error is represented explicitly rather than clipped or made infinite.
    """
    if not isinstance(expected, AreaEffects) or not isinstance(candidate, Mapping) or set(candidate) != set(expected.values):
        raise StateInputError("exact full area-key set required")
    available, missing, errors = [], [], []
    for area, truth in expected.values.items():
        if truth is None:
            if candidate[area] is not None:
                raise StateInputError("absent/undefined area requires null")
            missing.append(area)
        else:
            value = _number(candidate[area], "candidate effect")
            errors.append(abs(Fraction.from_float(value) - truth))
            available.append(area)
    return SessionError(sum(errors, Fraction()) / len(errors) if errors else None,
                        tuple(available), tuple(missing))


def aggregate_session_errors(errors: Mapping[str, SessionError], session_to_mouse: Mapping[str, str]):
    if not isinstance(session_to_mouse, Mapping):
        raise StateInputError("frozen session-to-mouse roster required")
    roster = _ids(session_to_mouse, "session roster")
    if not isinstance(errors, Mapping) or set(errors) != set(roster) or any(not isinstance(x, SessionError) for x in errors.values()):
        raise StateInputError("complete exact session error objects required")
    if any(not isinstance(m, str) or not m for m in session_to_mouse.values()):
        raise StateInputError("nonempty mouse identity required")
    groups = defaultdict(list)
    for sid in roster:
        groups[session_to_mouse[sid]].append(sid)
    mice = {}
    for mouse, ids in sorted(groups.items()):
        vals = [errors[sid].value for sid in ids]
        mice[mouse] = sum(vals, Fraction()) / len(vals) if all(v is not None for v in vals) else None
    primary = sum(mice.values(), Fraction()) / len(mice) if all(v is not None for v in mice.values()) else None
    return {"primary_mean_absolute_error": _scalar(primary, "undefined_required_session"),
            "mice": {m: _scalar(v, "undefined_required_session") for m, v in mice.items()},
            "required_sessions": len(roster), "required_mice": len(groups),
            "undefined_session_ids": [sid for sid in roster if errors[sid].value is None],
            "weighting": "equal available areas per session; equal required sessions within mouse; equal mice"}


def matched_area_units(metadata, area_pair):
    """Deterministic sensitivity subset from FIT/QC metadata only.

    Bins use bisect_right: an exact boundary enters the next bin. Within every
    4D bin choose the smaller count from each area, ordered by SHA256(unit_id
    UTF-8), then ID. This balances coarse metadata bins, not exact physiology,
    and creates no universal cross-area cohort or cross-area unit identity.
    """
    areas = _ids(area_pair, "area pair")
    if len(areas) != 2 or any(a not in AREAS for a in areas):
        raise StateInputError("two distinct fixed anatomical areas required")
    if not isinstance(metadata, (list, tuple)):
        raise StateInputError("metadata sequence required")
    required = {"unit_id", "area", *MATCH_BINS}
    groups, seen, outside = defaultdict(lambda: {a: [] for a in areas}), set(), []
    for row in metadata:
        if not isinstance(row, Mapping) or set(row) != required:
            raise StateInputError("exact FIT/QC metadata fields only; no query measurements")
        uid = row["unit_id"]
        if not isinstance(uid, str) or not uid or uid in seen or row["area"] not in AREAS:
            raise StateInputError("unique unit IDs and fixed area labels required")
        seen.add(uid)
        values = {name: _number(row[name], name) for name in MATCH_BINS}
        if values["FITbaseline"] <= 0 or values["isi_violations"] < 0 or not 0 <= values["presence_ratio"] <= 1 or not 0 <= values["amplitude_cutoff"] <= 1:
            raise StateInputError("invalid FIT/QC range")
        if row["area"] not in areas:
            outside.append(uid)
            continue
        key = tuple(bisect_right(bounds, values[name]) for name, bounds in MATCH_BINS.items())
        groups[key][row["area"]].append(uid)
    selected = {a: [] for a in areas}
    strata, unmatched = [], []
    order = lambda uid: (hashlib.sha256(uid.encode("utf-8")).hexdigest(), uid)
    for key in sorted(groups):
        ordered = {a: sorted(groups[key][a], key=order) for a in areas}
        n = min(len(ordered[a]) for a in areas)
        for a in areas:
            selected[a].extend(ordered[a][:n])
            unmatched.extend(ordered[a][n:])
        strata.append({"bin_indices": list(key), "counts": {a: len(ordered[a]) for a in areas},
                       "selected_per_area": n})
    return {"area_pair": list(areas), "selected_unit_ids": selected, "strata": strata,
            "unmatched_unit_ids": sorted(unmatched), "outside_pair_unit_ids": sorted(outside),
            "bin_fields": list(MATCH_BINS), "bin_edges": {k: list(v) for k, v in MATCH_BINS.items()},
            "boundary_policy": "bisect_right; exact boundary in next bin",
            "selection_source": "FIT baseline and QC metadata only; no query rates",
            "scope": "coarse pairwise bin balance, not exact matching or a universal cross-area cohort"}
