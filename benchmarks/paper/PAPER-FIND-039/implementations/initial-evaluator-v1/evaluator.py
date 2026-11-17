"""PAPER-FIND-039: independently written, source-derived Figure 2 metric kernels.

No author code, empirical data, or reference scores are bundled. The command
evaluates already admitted trial/bin spike counts and frozen classification masks.
It does not assert that those inputs reproduce the author's preprocessing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter1d

TASK = "PAPER-FIND-039"
SOURCE_REVISION = "1a9dd3040c9f77662caf26a34c9452403579087a"
SEGMENTS = ("block_A", "block_B", "alternation_A", "alternation_A_gain",
            "alternation_B", "alternation_B_gain")
METRICS = ("block_stability", "alternation_stability", "block_specificity",
           "alternation_specificity", "transfer_specificity")
HOLDS = [
    "Authentic import, quality exclusions, trial corrections, and classification masks not independently replayed.",
    "Independent complete mouse/session/cell/trial roster and age-balanced protected mouse partition not established.",
    "Paper says 5 cm smoothing; pinned notebook passes sigma=5 with 2 cm bins (10 cm). Discrepancy unresolved.",
    "Published mixed-effects model, locomotion/quality adjustment, behavior association and network remapping are not implemented here.",
    "Numeric reference targets/tolerances, isolated candidate replay, rights and full scientific qualification remain open.",
]


def _array(value, ndim, name, *, nonnegative=False):
    a = np.asarray(value, dtype=float)
    if a.ndim != ndim or any(s == 0 for s in a.shape) or not np.isfinite(a).all():
        raise ValueError(f"{name} must be a nonempty finite {ndim}-dimensional array")
    if nonnegative and (a < 0).any():
        raise ValueError(f"{name} must be nonnegative")
    return a


def build_rates(spike_counts, occupancy_seconds):
    """Counts T×B×C, dwell T×B -> source smoothed/min-max rates T×B×C.

    Bin columns must be the source's globally observed 2-cm bins. Missing
    per-trial bins carry the previous rate; a missing first bin starts at zero.
    The source's sigma is 5 *bins*, wrap mode, not an inferred physical sigma.
    Constant cells are undefined after global min-max normalization, as upstream.
    """
    counts = _array(spike_counts, 3, "spike_counts", nonnegative=True)
    dwell = _array(occupancy_seconds, 2, "occupancy_seconds", nonnegative=True)
    if counts.shape[:2] != dwell.shape or dwell.shape[1] < 2:
        raise ValueError("counts/dwell dimensions differ or fewer than two position bins")
    if not np.equal(counts, np.floor(counts)).all():
        raise ValueError("spike_counts must contain integer counts")
    if (counts[dwell == 0] != 0).any():
        raise ValueError("spikes cannot occur in zero-occupancy bins")
    if (dwell.sum(axis=0) == 0).any() or (dwell.sum(axis=1) == 0).any():
        raise ValueError("source bins and trials must each have some occupancy")
    rates = np.zeros_like(counts)
    for b in range(dwell.shape[1]):
        visited = dwell[:, b] > 0
        rates[visited, b] = counts[visited, b] / dwell[visited, b, None]
        if b:
            rates[~visited, b] = rates[~visited, b - 1]
    rates = gaussian_filter1d(rates, sigma=5, axis=1, mode="wrap")
    shifted = rates - rates.min(axis=(0, 1), keepdims=True)
    scale = shifted.max(axis=(0, 1), keepdims=True)
    result = np.full_like(rates, np.nan)
    np.divide(shifted, scale, out=result, where=scale > 0)
    return result


def source_similarity(trial_maps):
    """The pinned unshifted correlation: centered-row norm has epsilon 1e-6.

    NaNs from globally constant cells propagate. This does not mutate its input.
    A finite constant row (rather than a constant globally normalized cell) has
    zero similarity, including with itself, exactly as the pinned arithmetic.
    """
    maps = np.asarray(trial_maps, dtype=float)
    if maps.ndim != 2 or maps.shape[0] == 0 or maps.shape[1] < 2 or np.isinf(maps).any():
        raise ValueError("trial_maps must be T×B with B>=2 and no infinity")
    centered = maps - maps.mean(axis=1, keepdims=True)
    unit = centered / (np.linalg.norm(centered, axis=1, keepdims=True) + 1e-6)
    return unit @ unit.T


def _mean(values):
    a = np.asarray(values, dtype=float)
    good = np.isfinite(a)
    return float(a[good].mean()) if good.any() else None


def local_stability(similarity):
    """Mean of ten ±1..5 neighbors for interior rows; no context-boundary cut.

    A row with any NaN among those ten neighbors is undefined, rather than
    averaged over fewer neighbors. <=10 trials has no interior and returns None.
    """
    sim = np.asarray(similarity, dtype=float)
    if sim.ndim != 2 or sim.shape[0] != sim.shape[1] or np.isinf(sim).any():
        raise ValueError("similarity must be square and contain no infinity")
    neighbors = []
    for t in range(5, len(sim) - 5):
        neighbors.append(sum(sim[t, t + k] for k in range(-5, 6) if k) / 10)
    return _mean(neighbors)


def context_specificity(similarity, segment_lengths):
    """Three exact pinned similarity-ratio recipes, including unit subtraction.

    Rescale the *whole* cell similarity matrix to [0,1], then use non-gain A/B
    submatrices. Source subtracts a count of diagonal entries, not their actual
    sum; retained deliberately even though epsilon can make diagonals <1.
    """
    sim = np.asarray(similarity, dtype=float)
    lengths = list(segment_lengths)
    if len(lengths) != 6 or any(type(n) is not int or n < 0 for n in lengths):
        raise ValueError("six nonnegative integer segment lengths required")
    if sim.shape != (sum(lengths), sum(lengths)):
        raise ValueError("segment lengths do not cover similarity matrix")
    if sim.size == 0 or not np.isfinite(sim).all() or np.ptp(sim) == 0:
        return dict.fromkeys(METRICS[2:])
    scaled = (sim - sim.min()) / np.ptp(sim)
    cuts = np.cumsum([0] + lengths)
    idx = [np.arange(cuts[i], cuts[i + 1]) for i in range(6)]

    def within(a, b):
        na, nb = len(a), len(b)
        denominator = na * (na - 1) + nb * (nb - 1)
        if na == 0 or nb == 0 or denominator == 0:
            return None
        matched = (scaled[np.ix_(a, a)].sum() - na +
                   scaled[np.ix_(b, b)].sum() - nb) / denominator
        mismatch = scaled[np.ix_(a, b)].mean()
        return float(matched / mismatch) if mismatch != 0 else None

    a, b, aa, _, bb, _ = idx
    transfer = None
    if all(len(x) for x in (a, b, aa, bb)):
        matched = np.concatenate([scaled[np.ix_(aa, a)].ravel(), scaled[np.ix_(bb, b)].ravel()]).mean()
        mismatch = np.concatenate([scaled[np.ix_(aa, b)].ravel(), scaled[np.ix_(bb, a)].ravel()]).mean()
        if mismatch != 0:
            transfer = float(matched / mismatch)
    return {"block_specificity": within(a, b), "alternation_specificity": within(aa, bb),
            "transfer_specificity": transfer}


def _ids(items, field):
    if not isinstance(items, list) or not items or any(not isinstance(x, str) or not x for x in items):
        raise ValueError(f"{field} must be nonempty string IDs")
    if len(items) != len(set(items)):
        raise ValueError(f"duplicate {field}")
    return items


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def aggregate_mouse_level(session_rows, expected_mice, *, seed, bootstrap_replicates):
    """Prospective: equal cells/session, equal sessions/mouse, equal mice/age.

    Completeness is strict for mouse/age estimates: a missing session endpoint
    makes that mouse endpoint undefined; a missing mouse makes age/contrast
    undefined. Session means retain the source nan-mean with explicit counts.
    """
    mice = []
    for mouse_id in sorted(expected_mice):
        rows = [r for r in session_rows if r["mouse_id"] == mouse_id]
        row = {"mouse_id": mouse_id, "age_group": expected_mice[mouse_id]["age_group"],
               "n_sessions": len(rows), "metrics": {}}
        for metric in METRICS:
            values = [r["metrics"][metric]["value"] for r in rows]
            n = sum(v is not None for v in values)
            row["metrics"][metric] = {"value": float(np.mean(values)) if n == len(values) and n else None,
                                      "n_defined_sessions": n, "n_expected_sessions": len(values)}
        mice.append(row)
    groups = {}
    rng = np.random.default_rng(seed)
    draws = {}
    for age in ("young", "middle_aged", "aged"):
        rows = [r for r in mice if r["age_group"] == age]
        groups[age] = {"n_mice": len(rows), "metrics": {}}
        for metric in METRICS:
            vals = [r["metrics"][metric]["value"] for r in rows]
            complete = len(vals) > 0 and all(v is not None for v in vals)
            result = {"value": float(np.mean(vals)) if complete else None,
                      "n_defined_mice": sum(v is not None for v in vals), "ci95": None}
            if complete and len(vals) >= 2 and bootstrap_replicates:
                samples = np.asarray(vals)[rng.integers(len(vals), size=(bootstrap_replicates, len(vals)))].mean(axis=1)
                draws[(age, metric)] = samples
                result["ci95"] = np.quantile(samples, [0.025, 0.975]).tolist()
            groups[age]["metrics"][metric] = result
    contrasts = {}
    for age in ("middle_aged", "aged"):
        contrasts[f"{age}_minus_young"] = {}
        for metric in METRICS:
            a, y = groups[age]["metrics"][metric]["value"], groups["young"]["metrics"][metric]["value"]
            ci = None
            if (age, metric) in draws and ("young", metric) in draws:
                ci = np.quantile(draws[(age, metric)] - draws[("young", metric)], [0.025, 0.975]).tolist()
            contrasts[f"{age}_minus_young"][metric] = {"value": a - y if a is not None and y is not None else None, "ci95": ci}
    return {"mice": mice, "age_groups": groups, "contrasts": contrasts}


def evaluate(payload, roster, *, seed=0, bootstrap_replicates=1000):
    """Evaluate a complete admitted packet against a separately supplied roster.

    The roster supplies trusted IDs, trial identities/segments and all declared
    classification masks. The payload cannot choose its own selected population.
    Roster authenticity and protected storage remain operator responsibilities.
    """
    if type(seed) is not int or seed < 0 or type(bootstrap_replicates) is not int or not 0 <= bootstrap_replicates <= 100000:
        raise ValueError("nonnegative integer seed and bootstrap_replicates in [0,100000] required")
    if payload.get("task_id") != TASK or roster.get("task_id") != TASK:
        raise ValueError("task identity mismatch")
    if payload.get("source_revision") != SOURCE_REVISION or roster.get("source_revision") != SOURCE_REVISION:
        raise ValueError("source revision mismatch")
    if payload.get("bin_width_cm") != 2:
        raise ValueError("pinned Figure 2 recipe requires 2 cm bins")
    mice = roster["mice"]
    if not isinstance(mice, dict) or not mice:
        raise ValueError("nonempty mouse roster required")
    expected = {}
    mask_names = _ids(roster["classification_policies"], "classification_policies")
    for mouse_id, mouse in mice.items():
        if not isinstance(mouse_id, str) or not mouse_id or mouse["age_group"] not in ("young", "middle_aged", "aged"):
            raise ValueError("invalid mouse identity/age")
        if not isinstance(mouse["sessions"], dict) or not mouse["sessions"]:
            raise ValueError("each mouse needs all expected sessions")
        for session_id, session in mouse["sessions"].items():
            _ids([session_id], "session_id")
            _ids(session["cell_ids"], "cell_ids")
            _ids(session["trial_ids"], "trial_ids")
            bins = session["position_bin_ids"]
            if not isinstance(bins, list) or len(bins) < 2 or any(type(b) is not int or b < 1 for b in bins) or bins != sorted(set(bins)):
                raise ValueError("position_bin_ids must be distinct increasing positive source bin indices")
            if len(session["segments"]) != len(session["trial_ids"]) or any(x not in SEGMENTS for x in session["segments"]):
                raise ValueError("trial segments must match expected trials")
            if set(session["masks"]) != set(mask_names):
                raise ValueError("all frozen classification policies required for every session")
            for mask in session["masks"].values():
                if len(mask) != len(session["cell_ids"]) or any(type(v) is not bool for v in mask):
                    raise ValueError("classification masks must be boolean and aligned to all cells")
            expected[(mouse_id, session_id)] = session
    submitted = {}
    for session in payload["sessions"]:
        key = (session["mouse_id"], session["session_id"])
        if key in submitted:
            raise ValueError("duplicate mouse/session")
        submitted[key] = session
    if set(submitted) != set(expected):
        raise ValueError("missing or extra mouse/session against independent roster")
    by_policy = {name: [] for name in mask_names}
    cell_rows = []
    for key in sorted(expected):
        frozen, packet = expected[key], submitted[key]
        if any(packet[field] != frozen[field] for field in ("cell_ids", "trial_ids", "position_bin_ids")):
            raise ValueError("cell/trial/position-bin IDs or order disagree with roster")
        counts = _array(packet["spike_counts"], 3, "spike_counts", nonnegative=True)
        if counts.shape != (len(frozen["trial_ids"]), len(frozen["position_bin_ids"]), len(frozen["cell_ids"])):
            raise ValueError("counts do not cover expected cells/trials/position bins")
        # Stable ordering within each source context segment preserves temporal order.
        order = [i for segment in SEGMENTS for i, s in enumerate(frozen["segments"]) if s == segment]
        lengths = [frozen["segments"].count(s) for s in SEGMENTS]
        rates = build_rates(counts, packet["occupancy_seconds"])[order]
        nblock = sum(lengths[:2])
        rows = []
        for c, cell_id in enumerate(frozen["cell_ids"]):
            sim = source_similarity(rates[:, :, c])
            metrics = {"block_stability": local_stability(sim[:nblock, :nblock]),
                       "alternation_stability": local_stability(sim[nblock:, nblock:]),
                       **context_specificity(sim, lengths)}
            row = {"mouse_id": key[0], "session_id": key[1], "cell_id": cell_id,
                   "metrics": metrics, "normalization_defined": bool(np.isfinite(rates[:, :, c]).all())}
            rows.append(row)
            cell_rows.append(row)
        for policy in mask_names:
            selected = [r for r, flag in zip(rows, frozen["masks"][policy]) if flag]
            summaries = {}
            for metric in METRICS:
                vals = [r["metrics"][metric] for r in selected]
                finite = [v for v in vals if v is not None]
                summaries[metric] = {"value": _mean(finite), "n_defined_cells": len(finite), "n_selected_cells": len(vals)}
            by_policy[policy].append({"mouse_id": key[0], "session_id": key[1],
                                      "n_roster_cells": len(rows), "metrics": summaries})
    output = {"task_id": TASK, "source_revision": SOURCE_REVISION,
              "status": "source_derived_metric_component_with_prospective_mouse_estimator",
              "scientifically_qualified": False, "full_contract_complete": False,
              "input_sha256": _digest(payload), "roster_sha256": _digest(roster),
              "seed": seed, "bootstrap_replicates": bootstrap_replicates,
              "cells": cell_rows, "classification_sensitivity": {}, "holds": HOLDS}
    for policy, rows in by_policy.items():
        output["classification_sensitivity"][policy] = {"sessions": rows,
            **aggregate_mouse_level(rows, mice, seed=seed, bootstrap_replicates=bootstrap_replicates)}
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("roster", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--bootstrap-replicates", type=int, default=1000)
    args = parser.parse_args(argv)
    if args.output.resolve() in (args.input.resolve(), args.roster.resolve()):
        parser.error("output must not overwrite either input")
    try:
        result = evaluate(json.loads(args.input.read_text()), json.loads(args.roster.read_text()),
                          seed=args.seed, bootstrap_replicates=args.bootstrap_replicates)
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    except (ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
