"""Independent, prospective construction components for PAPER-ROOT-ADD-007.

No native pickle reader, author code import, supplied cluster labels, or scientific
qualification. See ../../docs/initial-evaluator-v1.md for estimands and holds.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from functools import lru_cache
import hashlib
import itertools
import json
import math
from pathlib import Path
import time

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import pdist
from scipy.special import gammaln, logsumexp, xlogy
from scipy.stats import rankdata

MICE = ("478", "481", "483", "485")
PHASES = ("learning", "learned")
CONDITIONS = ("sampling_L", "sampling_R", "outward_L", "outward_R",
              "reward_L", "reward_R", "inward_L", "inward_R")
POLICY = "pfc-prospective-rank-recurrence-v1"
HOLDS = [
    "Trusted native conversion, cell registration and exact trial/session/mask alignment unverified.",
    "Native saved nrm.npy calibration and threshold domain unverified; this policy uses rank permutation p values.",
    "No authentic data execution, paper numeric reference agreement, difficulty or scientific qualification.",
    "Bayesian trajectory kernel does not reconstruct native rate maps, neighbor bins or the Figure 5H reference.",
    "Code license unresolved; no official source is redistributed or imported.",
    "Public results/exposure and access-condition packet equality remain unresolved.",
]


class ContractError(ValueError):
    pass


def _require(ok, message):
    if not ok:
        raise ContractError(message)


def _seed(seed, *labels):
    digest = hashlib.sha256(json.dumps([seed, *labels], sort_keys=True).encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _finite_matrix(value, name, nonnegative=False):
    try:
        x = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"{name}: numeric matrix required") from exc
    _require(x.ndim == 2 and min(x.shape) > 0 and np.isfinite(x).all(), f"{name}: finite nonempty matrix required")
    if nonnegative:
        _require((x >= 0).all(), f"{name}: negative values")
    return x


def rank_correlation(a, b):
    """Spearman correlation after restricting both unique orders to shared cells."""
    _require(len(a) == len(set(a)) and len(b) == len(set(b)), "duplicate cells in sequence")
    common = set(a).intersection(b)
    n = len(common)
    if n < 2:
        return None, n
    aa = [x for x in a if x in common]
    pos = {x: i for i, x in enumerate(x for x in b if x in common)}
    squared = sum((i - pos[x]) ** 2 for i, x in enumerate(aa))
    return float(1 - 6 * squared / (n * (n * n - 1))), n


@lru_cache(maxsize=256)
def _rank_null(n, seed, draws):
    _require(n >= 2, "rank null requires at least two cells")
    base = np.arange(n)
    exact = n <= 7
    perms = itertools.permutations(range(n)) if exact else (np.random.default_rng(_seed(seed, n, i)).permutation(n) for i in range(draws))
    values = np.array([1 - 6 * np.sum((base - np.asarray(p)) ** 2) / (n * (n*n - 1)) for p in perms])
    return values, exact


def rank_test(a, b, seed=0, draws=10000):
    """Positive-order test; exact for <=7 cells, plus-one Monte Carlo otherwise."""
    _require(type(draws) is int and draws >= 99, "draws must be an integer >=99")
    rho, n = rank_correlation(a, b)
    if rho is None:
        return {"rho": None, "overlap": n, "p_upper": None, "z": None}
    null, exact = _rank_null(n, int(seed), draws)
    exceed = int(np.count_nonzero(null >= rho - 1e-12))
    p = exceed / len(null) if exact else (exceed + 1) / (len(null) + 1)
    return {"rho": rho, "overlap": n, "p_upper": float(p),
            "z": float((rho-null.mean())/null.std()), "null_exact": exact}


def sequence_order(event):
    # Equal onset times lack an identifiable rank: schema rejects them.
    return sorted(event["onsets_s"], key=lambda cell: event["onsets_s"][cell])


def mean_onset_template(events):
    values = defaultdict(list)
    for event in events:
        for cell, onset in event["onsets_s"].items():
            values[cell].append(onset)
    # Prospective deterministic lexicographic tie break only for averaged templates.
    return sorted(values, key=lambda cell: (float(np.mean(values[cell])), cell))


def _quality(events, labels, seed, draws, min_ratio):
    orders = [sequence_order(e) for e in events]
    retained, rejected = [], []
    for label in sorted(set(labels)):
        idx = [i for i, x in enumerate(labels) if x == label]
        template = mean_onset_template([events[i] for i in idx])
        sig = np.array([(rank_test(template, o, seed, draws)["p_upper"] or 1.0) <= .05 for o in orders])
        inside = np.array([x == label for x in labels])
        # Self-match cannot supply recurrence evidence. Rebuild each within-template
        # without its assessed event; require two distinct trial blocks.
        loo = []
        for i in idx:
            others = [events[j] for j in idx if j != i]
            p = rank_test(mean_onset_template(others), orders[i], seed, draws)["p_upper"] if others else None
            loo.append(p is not None and p <= .05)
        within = float(np.mean(loo))
        blocks = {(events[i]["session"], events[i]["trial"]) for i in idx}
        across = float(sig[~inside].mean()) if (~inside).any() else None
        ratio = within/across if across else None
        accepted = len(blocks) >= 2 and across is not None and within > 0 and (across == 0 or ratio >= min_ratio)
        entry = {"cluster": int(label), "members": [events[i]["id"] for i in idx], "template": template,
                 "within_match_fraction": within, "within_policy": "leave_one_event_out", "distinct_trial_blocks": len(blocks), "across_match_fraction": across,
                 "ratio": ratio, "ratio_infinite": across == 0 and within > 0,
                 "accepted": accepted}
        (retained if accepted else rejected).append(entry)
    return retained, rejected


def fit_clusters(events, seed=0, draws=10000):
    """Refit Ward linkage on rank-significance profiles; never consume cluster IDs.

    Source notebook structure: fac=1, initial quality ratio=1, merge z>2.5 and
    recomputed quality ratio=.1. Significance uses a prospective corrected domain.
    """
    _require(len(events) >= 2, "clustering needs >=2 observations")
    orders = [sequence_order(e) for e in events]
    profiles = np.zeros((len(events), len(events)))
    for i in range(len(events)):
        for j in range(i):
            p = rank_test(orders[i], orders[j], seed, draws)["p_upper"]
            profiles[i, j] = profiles[j, i] = p is not None and p <= .05
    distances = pdist(profiles)
    if not distances.any():
        # No pairwise significant edge: do not merge all identical zero profiles.
        labels = np.arange(len(events))
    else:
        labels = fcluster(linkage(distances, method="ward"), float(distances.max()), criterion="distance")-1
    kept, rejected = _quality(events, labels, seed, draws, 1.0)
    merges = []
    while len(kept) > 1:
        candidates = []
        for i, a in enumerate(kept):
            for b in kept[i+1:]:
                result = rank_test(a["template"], b["template"], seed, draws)
                if result["p_upper"] is not None and result["p_upper"] <= .05 and result["z"] > 2.5:
                    candidates.append((result["z"], a["cluster"], b["cluster"]))
        if not candidates:
            break
        _, a, b = sorted(candidates, key=lambda x: (-x[0], x[1], x[2]))[0]
        labels = np.array([a if label == b else label for label in labels])
        merges.append([a, b])
        # Only previously retained members may participate after rejection.
        active_ids = set().union(*(set(k["members"]) for k in kept))
        active = [i for i, e in enumerate(events) if e["id"] in active_ids]
        kept, newly_rejected = _quality([events[i] for i in active], labels[active], seed, draws, .1)
        rejected.extend(newly_rejected)
    return {"labels": {e["id"]: int(label) for e, label in zip(events, labels)},
            "templates": kept, "rejected_templates": rejected, "merges": merges,
            "significant_edges": int(profiles.sum()/2)}


def validate_packet(packet):
    _require(isinstance(packet, dict) and set(packet) == {"schema_version", "provenance", "mice", "events"}, "packet keys must exactly match documented schema")
    _require(packet["schema_version"] == 1 and type(packet["schema_version"]) is int, "schema_version must be 1")
    _require(isinstance(packet["mice"], dict) and set(packet["mice"]) == set(MICE), "all four registered mice required")
    provenance = packet["provenance"]
    _require(isinstance(provenance, dict) and set(provenance) == {"kind", "conversion_receipt", "mask_mapping"}, "explicit provenance required")
    _require(provenance["kind"] in {"generated_control", "trusted_conversion_pending_validation"}, "invalid provenance kind")
    _require(all(isinstance(provenance[k], str) and provenance[k].strip() for k in ("conversion_receipt", "mask_mapping")), "nonempty receipt and mask mapping required")
    for mouse, cells in packet["mice"].items():
        _require(isinstance(cells, list) and len(cells) >= 2 and all(isinstance(x, str) and x for x in cells) and len(set(cells)) == len(cells), f"{mouse}: unique registered cell IDs required")
    _require(isinstance(packet["events"], list) and packet["events"], "events required")
    ids, coverage = set(), set()
    keys = {"id", "mouse", "context", "session", "trial", "phase", "condition", "correct", "speed_pass", "onsets_s"}
    for event in packet["events"]:
        _require(isinstance(event, dict) and set(event) == keys, "event fields must match exactly; supplied clusters are forbidden")
        for key in ("id", "mouse", "context", "session", "trial", "condition"):
            _require(isinstance(event[key], str) and event[key], f"invalid {key}")
        _require(event["id"] not in ids, "duplicate event ID")
        ids.add(event["id"])
        _require(event["mouse"] in MICE and event["context"] in ("Task", "Arena", "Sleep"), "unknown mouse/context")
        coverage.add((event["mouse"], event["context"]))
        _require(type(event["correct"]) is bool and type(event["speed_pass"]) is bool, "explicit boolean masks required")
        if event["context"] == "Task":
            _require(event["phase"] in PHASES and event["condition"] in CONDITIONS, "task phase/condition mapping required")
        else:
            _require(event["phase"] is None and event["condition"] == "rest", "rest phase must be null; no guessed phase labels")
        onsets = event["onsets_s"]
        _require(isinstance(onsets, dict) and len(onsets) >= 2 and set(onsets) <= set(packet["mice"][event["mouse"]]), "onsets need >=2 registered cells")
        vals = list(onsets.values())
        _require(all(type(x) in (int, float) and math.isfinite(x) and 0 <= x <= .5 for x in vals), "onsets must be finite seconds within 500 ms burst")
        _require(len(set(vals)) == len(vals), "tied onsets require explicit upstream resolution; no arbitrary neural rank")
    _require(coverage == set(itertools.product(MICE, ("Task", "Arena", "Sleep"))), "complete four-mouse Task/Arena/Sleep census required")
    # A session/trial is not allowed to straddle biological phases.
    trial_phases = defaultdict(set)
    session_phases = defaultdict(set)
    trial_correctness = defaultdict(set)
    for e in packet["events"]:
        if e["context"] == "Task":
            trial_phases[(e["mouse"], e["session"], e["trial"])].add(e["phase"])
            session_phases[(e["mouse"], e["session"])].add(e["phase"])
            trial_correctness[(e["mouse"], e["session"], e["trial"])].add(e["correct"])
    _require(all(len(p) == 1 for p in trial_phases.values()), "trial crosses learning phase")
    _require(all(len(p) == 1 for p in session_phases.values()), "learning phase crosses session")
    _require(all(len(p) == 1 for p in trial_correctness.values()), "contradictory trial correctness masks")
    return packet


def _match_phase_counts(events, seed):
    """Match outward event counts per goal arm; all selected IDs are disclosed."""
    groups = defaultdict(lambda: defaultdict(list))
    for e in events:
        groups[e["condition"]][e["phase"]].append(e)
    selected, census = [], []
    for condition in ("outward_L", "outward_R"):
        group = groups[condition]
        n = min(len(group[p]) for p in PHASES)
        _require(n >= 2, f"{condition}: >=2 eligible bursts in each phase required")
        for phase in PHASES:
            rows = sorted(group[phase], key=lambda e: e["id"])
            rng = np.random.default_rng(_seed(seed, condition, phase))
            take = sorted(rng.choice(len(rows), n, replace=False))
            selected.extend(rows[i] for i in take)
            census.append({"condition": condition, "phase": phase, "available": len(rows), "selected": n})
    return sorted(selected, key=lambda e: e["id"]), census


def _expression(events, templates, seed, draws, mapping=None):
    if not templates or not events:
        return None
    values = []
    for event in events:
        order = sequence_order(event)
        if mapping:
            order = [mapping[(event["context"], event["session"])][x] for x in order]
        values.append(any((rank_test(t["template"], order, seed, draws)["p_upper"] or 1) <= .05 for t in templates))
    return float(np.mean(values))


def _paired_summary(values):
    _require(len(values) == 4 and all(math.isfinite(x) for x in values), "four finite mouse values required")
    x = np.asarray(values)
    # Enumerating 4^4 resampled mice is exact for the empirical bootstrap distribution.
    means = np.array([x[list(draw)].mean() for draw in itertools.product(range(4), repeat=4)])
    sign_means = [float(np.mean(x*np.asarray(sign))) for sign in itertools.product((-1, 1), repeat=4)]
    return {"n_animals": 4, "mean": float(x.mean()), "sample_sd": float(x.std(ddof=1)),
            "animal_bootstrap_percentile_95": np.quantile(means, [.025, .975]).tolist(),
            "exact_signflip_two_sided_p": float(np.mean(np.abs(sign_means) >= abs(x.mean())-1e-12)),
            "uncertainty_caution": "Four mice; empirical bootstrap and symmetric sign-flip model are descriptive prospective uncertainty."}


def evaluate(packet, seed=0, draws=10000, null_draws=199):
    validate_packet(packet)
    _require(type(seed) is int and type(null_draws) is int and null_draws >= 19, "integer seed and null_draws>=19 required")
    results, contrasts = [], []
    for mouse in MICE:
        events = sorted([e for e in packet["events"] if e["mouse"] == mouse], key=lambda e: e["id"])
        task = [e for e in events if e["context"] == "Task"]
        longitudinal = fit_clusters(task, _seed(seed, mouse, "longitudinal"), draws)
        table = Counter((longitudinal["labels"][e["id"]], e["phase"], e["condition"], e["correct"], e["speed_pass"]) for e in task)
        outward = [e for e in task if e["condition"].startswith("outward_") and e["correct"] and e["speed_pass"]]
        selected, census = _match_phase_counts(outward, _seed(seed, mouse))
        phase_fits = {p: fit_clusters([e for e in selected if e["phase"] == p], _seed(seed, mouse, p), draws) for p in PHASES}
        # Both phase template banks see exactly the same complete rest events.
        rest = [e for e in events if e["context"] != "Task"]
        fractions = {p: _expression(rest, phase_fits[p]["templates"], seed, draws) for p in PHASES}
        contrast = None if None in fractions.values() else fractions["learned"]-fractions["learning"]
        if contrast is not None:
            contrasts.append(contrast)
        groups = sorted(set((e["context"], e["session"]) for e in rest))
        null = []
        if contrast is not None:
            for repeat in range(null_draws):
                maps = {}
                cells = sorted(packet["mice"][mouse])
                for group in groups:
                    rng = np.random.default_rng(_seed(seed, mouse, group, repeat))
                    maps[group] = dict(zip(cells, rng.permutation(cells)))
                null.append(_expression(rest, phase_fits["learned"]["templates"], seed, draws, maps)-_expression(rest, phase_fits["learning"]["templates"], seed, draws, maps))
        # Every task mask stratum remains visible; sampling/reward expression is not called spatial replay.
        expression = []
        for phase, condition in itertools.product(PHASES, CONDITIONS):
            rows = [e for e in task if e["phase"] == phase and e["condition"] == condition]
            expression.append({"phase": phase, "condition": condition, "n": len(rows),
                               "fraction": _expression(rows, phase_fits[phase]["templates"], seed, draws),
                               "outward_fit_overlap": condition.startswith("outward_")})
        results.append({"mouse": mouse, "n_events": len(events), "context_census": dict(Counter(e["context"] for e in events)),
                        "task_cell_participation_fraction": {c: sum(c in e["onsets_s"] for e in task)/len(task) for c in sorted(packet["mice"][mouse])},
                        "longitudinal_clusters": longitudinal, "selectivity_counts": [dict(zip(("cluster", "phase", "condition", "correct", "speed_pass", "count"), (*k, n))) for k, n in sorted(table.items())],
                        "matched_training_census": census, "selected_outward_ids": [e["id"] for e in selected], "phase_refits": phase_fits,
                        "task_template_expression": expression, "rest_template_expression": fractions, "learned_minus_learning_rest_expression": contrast,
                        "identity_alignment_null": {"grouping": "mouse/context/session; one shared cell permutation per group", "values": null,
                            "two_sided_p": None if contrast is None else (1+sum(abs(x)>=abs(contrast)-1e-12 for x in null))/(1+len(null))}})
    return {"task_id": "PAPER-ROOT-ADD-007", "policy": POLICY, "scientific_qualification": "unknown", "native_reproduction": "held", "holds": HOLDS,
            "provenance": packet["provenance"], "seed": seed, "rank_null_draws": draws, "grouped_null_draws": null_draws,
            "animals": results, "animal_summary": _paired_summary(contrasts) if len(contrasts)==4 else None,
            "estimand": "Mean across four mice of learned-minus-learning outward-template expression in the same complete declared-packet Arena/Sleep event set; prospective recurrence, not spatial replay."}


def poisson_decode(counts, rates_hz, bin_seconds):
    """Independent Poisson decoder with uniform position prior; rows=time/cells.

    Counts [time,cell], rates [cell,position]. Explicit exact-zero likelihood;
    impossible bins return null positions rather than an arbitrary first-bin argmax.
    """
    counts = _finite_matrix(counts, "counts", True)
    rates = _finite_matrix(rates_hz, "rates_hz", True)
    _require(np.equal(counts, np.floor(counts)).all(), "counts must be integers")
    _require(counts.shape[1] == rates.shape[0] and rates.shape[1] >= 2, "decoder dimensions incompatible")
    _require(type(bin_seconds) in (int, float) and math.isfinite(bin_seconds) and bin_seconds>0, "positive bin_seconds required")
    lam = rates*bin_seconds
    ll = np.sum(xlogy(counts[:, :, None], lam[None, :, :])-lam[None, :, :]-gammaln(counts[:, :, None]+1), axis=1)
    valid = np.isfinite(ll).any(axis=1)
    posterior = np.zeros_like(ll)
    posterior[valid] = np.exp(ll[valid]-logsumexp(ll[valid], axis=1)[:, None])
    positions = []
    for i, row in enumerate(ll):
        maxima = np.flatnonzero(row == np.max(row)) if valid[i] else []
        positions.append(int(maxima[0]) if len(maxima)==1 else None)
    return {"posterior": posterior.tolist(), "position_indices": positions,
            "undefined_bins": [i for i, p in enumerate(positions) if p is None], "prior": "uniform"}


def trajectory_score(position_indices):
    if any(p is None for p in position_indices) or len(position_indices)<5:
        return None
    x = np.asarray(position_indices, dtype=float)
    _require(x.ndim==1 and np.isfinite(x).all(), "finite positions required")
    ranks = rankdata(x)
    if np.std(ranks)==0:
        return None
    return float(np.corrcoef(np.arange(len(x)), ranks)[0, 1])


def trajectory_replay(counts, rates_hz, bin_seconds, seed=0, draws=499):
    """Recompute decoded trajectories under cell-index permutations.

    Component endpoint only: supplied rate maps must have been built without burst
    and neighboring samples. Within-session shared shuffles are implemented by
    trajectory_session, not by repeated independent calls to this function.
    """
    return trajectory_session([counts], rates_hz, bin_seconds, seed, draws)["events"][0]


def trajectory_session(event_counts, rates_hz, bin_seconds, seed=0, draws=499):
    """One shared rate-map cell-index shuffle for all bursts in a session/draw."""
    _require(type(draws) is int and draws>=99 and type(seed) is int, "draws>=99 and integer seed required")
    rates = _finite_matrix(rates_hz, "rates_hz", True)
    _require(isinstance(event_counts, list) and event_counts, "session event counts required")
    arrays = [_finite_matrix(c, "counts", True) for c in event_counts]
    decoded = [poisson_decode(c, rates, bin_seconds) for c in arrays]
    observed = [trajectory_score(d["position_indices"]) if np.count_nonzero(c.sum(axis=1))>=5 else None for c,d in zip(arrays,decoded)]
    nulls = [[] for _ in arrays]
    for repeat in range(draws):
        order = np.random.default_rng(_seed(seed, "trajectory", repeat)).permutation(len(rates))
        for i, c in enumerate(arrays):
            if observed[i] is not None:
                nulls[i].append(trajectory_score(poisson_decode(c, rates[order], bin_seconds)["position_indices"]))
    reports = []
    for d, obs, null in zip(decoded, observed, nulls):
        # Undefined null trajectories invalidate significance; never silently drop them.
        valid = obs is not None and all(x is not None for x in null)
        forward = (1+sum(x>=obs-1e-12 for x in null))/(draws+1) if valid else None
        backward = (1+sum(x<=obs+1e-12 for x in null))/(draws+1) if valid else None
        sd = float(np.std(null)) if valid else 0
        reports.append({"decoded": d, "rho": obs, "null_rhos": null,
                        "z": (obs-float(np.mean(null)))/sd if valid and sd>0 else None,
                        "p_forward": forward, "p_backward": backward,
                        "forward": forward<=.025 if valid else None, "backward": backward<=.025 if valid else None,
                        "status": "scored" if valid else "held_undefined_trajectory_or_null",
                        "policy": "prospective plus-one tails; source native map/preprocessing agreement held"})
    return {"events": reports, "shuffle_group": "one shared cell-index permutation across all session events", "draws": draws}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--rank-draws", type=int, default=10000)
    parser.add_argument("--null-draws", type=int, default=199)
    args = parser.parse_args()
    started = time.perf_counter()
    try:
        # JSON only: explicitly never execute pickle or object-array deserialization.
        raw = args.packet.read_bytes()
        packet = json.loads(raw, parse_constant=lambda x: (_ for _ in ()).throw(ContractError(f"invalid JSON constant {x}")))
        result = evaluate(packet, args.seed, args.rank_draws, args.null_draws)
        result["engineering_resources"] = {"elapsed_seconds": time.perf_counter()-started, "input_bytes": len(raw), "input_sha256": hashlib.sha256(raw).hexdigest(), "scientific_runs": 0}
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, f"contract error: {exc}\n")


if __name__ == "__main__":
    main()
