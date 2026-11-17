"""Local sorted-spike evaluator for the IBL brain-wide-map single-cell endpoint.

The conditional statistic reconstructs the algorithm of the pinned IBL source.
No network, native loader, historical target, or qualification claim is included.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import binom, chi2, mannwhitneyu, rankdata

SOURCE_REVISION = "118fc36cb3602934466ad2c6087c2b3b441f9f1f"
FREEZE = "2023_12_bwm_release"
PROFILES = ("pinned-examples", "paper-choice-window-proposal")
ENDPOINTS = ("stimulus", "choice", "feedback")
GATES = [
    "Exact paper-versus-pinned-source choice alignment requires owner adjudication.",
    "Pinned conditional test uses independent directional shuffles and average-rank lower tail; paper prose conflicts.",
    "The supplied roster, source masks, unit identities, anatomical assignments and export provenance require authentic audit.",
    "bwm_units RT defaults and unit-count documentation conflict with example-loader/paper settings; no silent reconciliation.",
    "Paper simple-MW implementation, complete cohort/region family and figure targets require authentic reference comparison.",
    "Mouse-level summaries are prospective; source session Fisher inference is not independent mouse inference.",
    "Data/component rights, source exposure and protected assessment policy remain unresolved.",
    "Native reference execution, resource scaling, meaningful difficulty and scientific qualification remain unestablished.",
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and np.isfinite(value)


def nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def seeded(seed, *parts):
    raw = json.dumps([int(seed), *parts], separators=(",", ":")).encode()
    return np.random.RandomState(int.from_bytes(hashlib.sha256(raw).digest()[:4], "big"))


def trial_mask(trials):
    """Apply example-loader finite/event/RT filters AND an exported source mask.

    The caller must supply the actual source mask (including engagement truncation
    and any saturated-interval exclusions), not a claim that our RT rule replaces it.
    """
    required = ("choice", "probabilityLeft", "feedbackType", "feedback_times",
                "stimOn_times", "firstMovement_times")
    out = []
    for trial in trials:
        require(type(trial.get("source_mask")) is bool, "each trial needs a boolean source_mask")
        valid = all(number(trial.get(key)) for key in required)
        if valid:
            rt = trial["firstMovement_times"] - trial["stimOn_times"]
            valid = 0.08 <= rt <= 2.0
        out.append(bool(trial["source_mask"] and valid))
    return np.asarray(out, dtype=bool)


def window_counts(spike_times, anchors, start, stop):
    """Counts in [anchor+start, anchor+stop); one sorted spike vector per unit."""
    times = np.asarray(spike_times, dtype=float)
    anchors = np.asarray(anchors, dtype=float)
    require(times.ndim == anchors.ndim == 1, "spikes and anchors must be vectors")
    require(np.isfinite(times).all() and np.isfinite(anchors).all(), "nonfinite times")
    require(np.all(np.diff(times) >= 0), "spike_times must be sorted")
    require(number(start) and number(stop) and start < stop, "invalid counting window")
    return np.searchsorted(times, anchors + stop, side="left") - np.searchsorted(times, anchors + start, side="left")


def directional_u(values_a, values_b, blocks_a, blocks_b, n_shuffles, rng):
    """IBL directional rank-sum draws, permuting only shared contiguous blocks."""
    na, nb = len(values_a), len(values_b)
    ranks = rankdata(np.concatenate([values_a, values_b]))
    block_pairs = []
    for block in np.intersect1d(blocks_a, blocks_b):
        ids = np.concatenate([np.flatnonzero(blocks_a == block),
                              np.flatnonzero(blocks_b == block) + na])
        block_pairs.append(ids)
    values = np.empty(n_shuffles + 1)
    values[0] = ranks[:na].sum() - na * (na + 1) / 2
    for draw in range(n_shuffles):
        indices = np.arange(na + nb)
        for ids in block_pairs:
            indices[ids] = ids[rng.choice(len(ids), size=len(ids), replace=False)]
        values[draw + 1] = ranks[indices[:na]].sum() - na * (na + 1) / 2
    return values


def conditional_test(counts, labels, strata, blocks, n_shuffles, rng):
    """Reconstruct pinned Time_TwoNmannWhitneyUshuf and combined rank p.

    Source computes forward/reverse draws independently then takes their minimum.
    This intentionally preserves that nonstandard null construction, including the
    average-rank tie rule. It is NOT a conventional two-sided permutation p-value.
    """
    counts = np.asarray(counts, dtype=float)
    labels, strata, blocks = map(np.asarray, (labels, strata, blocks))
    require(all(x.shape == counts.shape for x in (labels, strata, blocks)), "test arrays differ")
    require(counts.ndim == 1 and np.isfinite(counts).all(), "invalid counts")
    require(type(n_shuffles) is int and n_shuffles >= 1, "positive shuffle count required")
    total = np.zeros(n_shuffles + 1)
    pairs = 0
    exchangeable_blocks = 0
    for stratum in (0, 1, 2, 3):
        a = (strata == stratum) & (labels == 1)
        b = (strata == stratum) & (labels == -1)
        na, nb = int(a.sum()), int(b.sum())
        if not na or not nb:
            continue
        forward = directional_u(counts[a], counts[b], blocks[a], blocks[b], n_shuffles, rng)
        reverse = directional_u(counts[b], counts[a], blocks[b], blocks[a], n_shuffles, rng)
        total += np.minimum(forward, reverse)
        pairs += na * nb
        exchangeable_blocks += len(np.intersect1d(blocks[a], blocks[b]))
    if pairs == 0:
        return {"status": "not_estimable", "reason": "no within-condition opposing-label pairs", "p": None,
                "statistic": None, "pairs": 0, "exchangeable_blocks": 0}
    statistic = total / pairs
    return {"status": "computed", "p": float(rankdata(statistic)[0] / len(statistic)),
            "statistic": float(statistic[0]), "pairs": pairs,
            "exchangeable_blocks": int(exchangeable_blocks)}


def endpoint_design(trials, endpoint, profile):
    """Four source strata; block identities are derived AFTER the common mask."""
    require(profile in PROFILES and endpoint in ENDPOINTS, "unknown fixed endpoint/profile")
    n = len(trials)
    block_probability = np.array([t["probabilityLeft"] for t in trials])
    blocks = np.r_[0, np.cumsum(np.diff(block_probability) != 0)] if n else np.array([], dtype=int)
    side = np.zeros(n, dtype=int)
    for i, trial in enumerate(trials):
        left, right = trial.get("contrastLeft"), trial.get("contrastRight")
        if number(left) and left > 0:
            side[i] = 1
        if number(right) and right > 0:
            require(side[i] == 0, "both sides have positive contrast")
            side[i] = -1
    choice = np.array([t["choice"] for t in trials])
    if endpoint == "stimulus":
        labels, condition = side, choice
        anchors = np.array([t["stimOn_times"] for t in trials])
        window = (0.0, 0.1)
    elif endpoint == "choice":
        labels, condition = choice, side
        key = "stimOn_times" if profile == "pinned-examples" else "firstMovement_times"
        anchors = np.array([t[key] for t in trials])
        window = (-0.1, 0.0)
    else:
        require(all(number(t.get("rewardVolume")) for t in trials), "feedback requires finite rewardVolume")
        labels = np.array([1 if t["rewardVolume"] > 0 else -1 for t in trials])
        condition = side
        anchors = np.array([t["feedback_times"] for t in trials])
        window = (0.0, 0.2)
    strata = np.full(n, -1, dtype=int)
    for index, (prob, cond) in enumerate(((0.8, 1), (0.8, -1), (0.2, 1), (0.2, -1))):
        strata[(block_probability == prob) & (condition == cond)] = index
    return anchors, window, labels, strata, blocks


def simple_test(counts, labels):
    a, b = np.asarray(counts)[labels == 1], np.asarray(counts)[labels == -1]
    if not len(a) or not len(b):
        return None
    # Prospective explicit resolution: asymptotic, tie-corrected two-sided MW
    # with continuity correction. Paper specifies MW, but not these software options.
    return float(mannwhitneyu(a, b, alternative="two-sided", method="asymptotic", use_continuity=True).pvalue)


def bh_adjust(pvalues):
    values = np.asarray(pvalues, dtype=float)
    require(values.ndim == 1 and np.isfinite(values).all() and np.all((values >= 0) & (values <= 1)), "invalid p-values")
    if not len(values):
        return []
    order = np.argsort(values, kind="stable")
    q = np.minimum.accumulate((values[order] * len(values) / np.arange(1, len(values) + 1))[::-1])[::-1]
    restored = np.empty(len(values))
    restored[order] = np.minimum(q, 1)
    return restored.tolist()


def validate_packet(packet):
    require(packet.get("schema_version") == 1, "schema_version must be 1")
    require(packet.get("freeze") == FREEZE and packet.get("source_revision") == SOURCE_REVISION, "incorrect source pin")
    require(packet.get("evidence_kind") in ("generated_engineering", "unverified_local_export"), "invalid evidence kind")
    require(packet.get("spike_sorting_revision") == "2024-05-06", "incorrect spike sorting revision")
    require(packet.get("trials_modified_before") == "2024-07-10", "incorrect trial revision bound")
    require(nonempty_string(packet.get("unit_version_evidence")), "unit version evidence required")
    require(nonempty_string(packet.get("mask_provenance")), "source mask provenance required")
    regions = packet.get("regions")
    require(isinstance(regions, list) and regions and all(nonempty_string(x) for x in regions), "explicit region family required")
    require(len(set(regions)) == len(regions) and not {"root", "void"}.intersection(regions), "invalid region family")
    roster = packet.get("roster")
    sessions = packet.get("sessions")
    require(isinstance(roster, list) and roster and isinstance(sessions, list), "roster and sessions required")
    expected = {}
    all_pids = set()
    for row in roster:
        require(all(nonempty_string(row.get(k)) for k in ("eid", "mouse_id")), "roster identities required")
        pids = row.get("pids")
        require(isinstance(pids, list) and pids and all(nonempty_string(p) for p in pids), "probe roster required")
        require(len(set(pids)) == len(pids) and not all_pids.intersection(pids), "duplicate probe identity")
        all_pids.update(pids)
        require(row["eid"] not in expected, "duplicate roster session")
        expected[row["eid"]] = (row["mouse_id"], set(pids))
    require(len(sessions) == len(expected), "incomplete session population")
    seen_eids, seen_units = set(), set()
    for session in sessions:
        eid = session.get("eid")
        require(eid in expected and eid not in seen_eids, "extra or duplicate session")
        seen_eids.add(eid)
        require((session.get("mouse_id"), set(session.get("pids", []))) == expected[eid], "session roster mismatch")
        require(len(session["pids"]) == len(set(session["pids"])), "duplicate session probe")
        trials = session.get("trials")
        require(isinstance(trials, list) and trials, "empty trials")
        ids = [t.get("trial_id") for t in trials]
        require(type(session.get("expected_trial_count")) is int and session["expected_trial_count"] > 0, "full trial count required")
        require(all(type(i) is int for i in ids) and ids == list(range(session["expected_trial_count"])), "complete ordered original trial population required")
        require(all(all(k in trial for k in ("contrastLeft", "contrastRight", "rewardVolume")) for trial in trials), "contrast/reward columns must be present; use explicit null when unavailable")
        trial_mask(trials)
        units = session.get("units")
        require(isinstance(units, list), "units required")
        inventory = session.get("expected_unit_uuids")
        require(isinstance(inventory, list) and len(inventory) == len(set(inventory)), "unit inventory required")
        require({u.get("uuid") for u in units} == set(inventory) and len(units) == len(inventory), "unit inventory mismatch")
        for unit in units:
            require(nonempty_string(unit.get("uuid")) and unit["uuid"] not in seen_units, "missing/duplicate global unit UUID")
            seen_units.add(unit["uuid"])
            require(unit.get("pid") in expected[eid][1], "unit probe is outside roster")
            require(nonempty_string(unit.get("region")) and number(unit.get("quality_label")), "unit metadata required")
            require(type(unit.get("gray_matter")) is bool, "source anatomical mask required")
            window_counts(unit.get("spike_times"), [], 0, 1)
    return regions


def summarize(rows, regions, n_bootstrap, seed):
    output = []
    for endpoint in ENDPOINTS:
        family = []
        for region in regions:
            candidates = [r for r in rows if r["region"] == region and r["endpoint"] == endpoint]
            by_session = defaultdict(list)
            for row in candidates:
                by_session[(row["eid"], row["mouse_id"])].append(row)
            eligible = [(key, vals) for key, vals in by_session.items() if len(vals) >= 5]
            record = {"region": region, "endpoint": endpoint, "eligible_sessions": len(eligible),
                      "excluded_small_sessions": sorted(k[0] for k, v in by_session.items() if len(v) < 5),
                      "source_session_fisher_p": None, "source_family_bh_q": None, "source_family_significant_001": None,
                      "status": "insufficient_sessions", "sessions": [], "prospective_mouse_summary": None}
            if len(eligible) < 2:
                output.append(record)
                continue
            if any(row["sensitive"] is None for _, vals in eligible for row in vals):
                record["status"] = "not_estimable_units"
                output.append(record)
                continue
            logps, fractions, mice = [], [], defaultdict(list)
            for (eid, mouse), vals in sorted(eligible):
                n, k = len(vals), sum(row["sensitive"] for row in vals)
                logp = float(binom.logsf(k - 1, n, 0.001 * 0.05))
                logps.append(logp)
                fraction = k / n
                fractions.append(fraction)
                mice[mouse].append(fraction)
                record["sessions"].append({"eid": eid, "mouse_id": mouse, "units": n, "sensitive": k,
                                            "fraction": fraction, "binomial_p": float(np.exp(logp))})
            record["status"] = "computed_with_preserved_gates"
            record["mean_session_fraction"] = float(np.mean(fractions))
            record["source_session_fisher_p"] = float(chi2.sf(-2 * np.sum(logps), 2 * len(logps)))
            mouse_values = np.array([np.mean(mice[m]) for m in sorted(mice)])
            summary = {"estimand": "equal mice; mean of eligible session fractions within mouse", "n_mice": len(mice),
                       "mean": float(np.mean(mouse_values)), "bootstrap_percentile_95": None,
                       "mouse_values": {m: float(np.mean(mice[m])) for m in sorted(mice)}}
            if len(mouse_values) >= 2:
                rng = seeded(seed, "mouse-bootstrap", endpoint, region)
                boot = np.mean(rng.choice(mouse_values, size=(n_bootstrap, len(mouse_values)), replace=True), axis=1)
                summary["bootstrap_percentile_95"] = np.quantile(boot, [0.025, 0.975]).tolist()
            record["prospective_mouse_summary"] = summary
            family.append(record)
            output.append(record)
        # Missing/nonestimable members must not silently reduce the BH family.
        full_family = [row for row in output if row["endpoint"] == endpoint]
        if len(family) == len(full_family):
            for row, q in zip(family, bh_adjust([r["source_session_fisher_p"] for r in family])):
                row["source_family_bh_q"] = q
                row["source_family_significant_001"] = q < 0.01
        else:
            for row in full_family:
                row["family_gate"] = "incomplete declared region family; BH withheld"
    return output


def evaluate(packet, *, profile, seed=0, n_shuffles=3000, n_bootstrap=2000):
    require(profile in PROFILES, "an explicit fixed profile is required")
    require(type(seed) is int and seed >= 0, "nonnegative integer seed required")
    require(type(n_shuffles) is int and n_shuffles >= 1, "positive shuffle count required")
    require(type(n_bootstrap) is int and n_bootstrap >= 1, "positive bootstrap count required")
    if packet.get("evidence_kind") != "generated_engineering":
        require(n_shuffles == 3000, "source export requires 3000 shuffles")
    regions = validate_packet(packet)
    rows, coverage = [], []
    for session in sorted(packet["sessions"], key=lambda x: x["eid"]):
        mask = trial_mask(session["trials"])
        trials = [t for t, keep in zip(session["trials"], mask) if keep]
        selected = [u for u in session["units"] if u["quality_label"] >= 1 and u["gray_matter"]
                    and u["region"] in regions and u["region"] not in ("root", "void")]
        n_errors = sum(t["feedbackType"] == -1 for t in trials)
        coverage.append({"eid": session["eid"], "mouse_id": session["mouse_id"], "pids": sorted(session["pids"]),
                         "input_trials": len(mask), "retained_trials": int(mask.sum()),
                         "retained_trial_ids": [t["trial_id"] for t in trials],
                         "input_units": len(session["units"]), "retained_units": len(selected),
                         "error_trials_after_mask": n_errors, "analysis_included": n_errors >= 3,
                         "exclusion_reason": None if n_errors >= 3 else "fewer than three error trials after common mask"})
        if n_errors < 3:
            continue
        for endpoint in ENDPOINTS:
            anchors, window, labels, strata, blocks = endpoint_design(trials, endpoint, profile)
            for unit in sorted(selected, key=lambda x: x["uuid"]):
                counts = window_counts(unit["spike_times"], anchors, *window)
                result = conditional_test(counts, labels, strata, blocks, n_shuffles,
                                          seeded(seed, session["eid"], unit["uuid"], endpoint))
                p_simple = simple_test(counts, labels)
                sensitive = None if result["p"] is None or p_simple is None else bool(result["p"] < 0.05 and p_simple < 0.001)
                rows.append({"eid": session["eid"], "mouse_id": session["mouse_id"], "pid": unit["pid"],
                             "uuid": unit["uuid"], "region": unit["region"], "endpoint": endpoint,
                             "conditional": result, "simple_mw_p_prospective_options": p_simple,
                             "sensitive": sensitive, "window_seconds": list(window)})
    return {"schema_version": 1, "task_id": "PAPER-FIND-005", "profile": profile,
            "freeze": FREEZE, "source_revision": SOURCE_REVISION, "evidence_kind": packet["evidence_kind"],
            "n_shuffles": n_shuffles, "n_bootstrap": n_bootstrap, "seed": seed,
            "scientific_qualification": "unknown", "full_contract_complete": False,
            "input_sha256": hashlib.sha256(json.dumps(packet, sort_keys=True, allow_nan=False).encode()).hexdigest(),
            "coverage": coverage, "units": rows, "regions": summarize(rows, regions, n_bootstrap, seed),
            "preserved_gates": GATES}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", choices=PROFILES, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--shuffles", type=int, default=3000)
    parser.add_argument("--bootstrap", type=int, default=2000)
    args = parser.parse_args()
    packet = json.loads(args.input.read_text())
    result = evaluate(packet, profile=args.profile, seed=args.seed,
                      n_shuffles=args.shuffles, n_bootstrap=args.bootstrap)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
