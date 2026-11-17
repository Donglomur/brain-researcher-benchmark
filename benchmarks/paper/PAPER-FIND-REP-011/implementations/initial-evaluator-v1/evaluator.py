"""Source-grounded spine activity and prospective next-visit risk evaluation.

This is not the author's MATLAB analysis or a qualified whole-paper reproduction.
Only existing NumPy is needed. See the task-level documentation for frozen policy.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

SCHEMA = "rep011-processed-v1"
MODELS = {"intercept": (), "activity": ("events_per_min",),
          "activity_local": ("events_per_min", "local_coactivity")}
HOLDS = [
    "Native MATLAB/processed-array mapping and complete authentic cohort not validated.",
    "Optical registration, activity detection and independent fate assessment not validated.",
    "Author mixed-effects significance, spatial shuffles and postsynaptic timing not reproduced.",
    "Protected reference, equal-access replay, rights and baseline competence remain unqualified.",
    "Prospective complete-case next-visit risk is not a time-to-event survival estimate or causal result.",
]


class ContractError(ValueError):
    pass


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ContractError(message)


def finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def nonempty(x: Any) -> bool:
    return isinstance(x, str) and bool(x.strip())


def mean(values):
    v = [float(x) for x in values if x is not None]
    return sum(v) / len(v) if v else None


def events(trace):
    """Count continuous active runs; a run at frame zero counts once (v1 policy)."""
    return sum(bool(x) and (i == 0 or not trace[i - 1]) for i, x in enumerate(trace))


def coactivity(a, b):
    """Dimensionless run-overlap rate / geometric mean individual rates."""
    require(len(a) == len(b) and len(a) > 0, "pair traces must have equal nonzero length")
    na, nb = events(a), events(b)
    if not na or not nb:
        return None
    return events([x and y for x, y in zip(a, b)]) / math.sqrt(na * nb)


def validate(data):
    require(isinstance(data, dict) and data.get("schema_version") == SCHEMA, "unsupported schema")
    require(data.get("cohort") in {"iglusnfr2", "iglusnfr3_rcamp2"}, "one declared sensor cohort required")
    provenance = data.get("provenance", {})
    require(isinstance(provenance, dict), "provenance must be an object")
    for key in ("input_scope", "alignment_policy_id", "activity_detection_policy_id", "fate_assessment_id"):
        require(nonempty(provenance.get(key)), f"provenance.{key} required")
    require(provenance.get("kind") in {"generated_engineering_control", "empirical"}, "declare input kind")
    require(provenance.get("source_record") == "zenodo.10108836", "source identity must remain zenodo.10108836")
    sessions = data.get("sessions")
    require(isinstance(sessions, list) and len(sessions) >= 2, "at least two scheduled sessions required")
    ids, days = [], []
    for s in sessions:
        require(isinstance(s, dict) and nonempty(s.get("session_id")) and finite(s.get("day")), "invalid session")
        ids.append(s["session_id"]); days.append(s["day"])
    require(len(ids) == len(set(ids)) and all(a < b for a, b in zip(days, days[1:])), "sessions must be unique and ordered in days")
    dendrites = data.get("dendrites")
    require(isinstance(dendrites, list) and bool(dendrites), "nonempty complete supplied dendrite roster required")
    seen = set()
    for d in dendrites:
        require(isinstance(d, dict), "dendrite must be an object")
        for key in ("mouse_id", "dendrite_id"):
            require(nonempty(d.get(key)), f"{key} required")
        dk = (d["mouse_id"], d["dendrite_id"])
        require(dk not in seen, "duplicate mouse/dendrite identity"); seen.add(dk)
        require(d.get("health_status") in {"eligible", "excluded", "unresolved"}, "explicit health_status required")
        require(nonempty(d.get("health_assessment_id")), "health_assessment_id required")
        lo, hi = d.get("arc_start_um"), d.get("arc_end_um")
        require(finite(lo) and finite(hi) and lo < hi, "valid dendritic arc limits required")
        spines = d.get("spines")
        require(isinstance(spines, list) and bool(spines), "complete supplied spine roster required")
        seen_spines = set(); grids = {}
        for spine in spines:
            require(isinstance(spine, dict) and nonempty(spine.get("spine_id")), "spine_id required")
            require(spine["spine_id"] not in seen_spines, "duplicate spine identity"); seen_spines.add(spine["spine_id"])
            obs = spine.get("observations")
            require(isinstance(obs, list) and len(obs) == len(ids), "every scheduled visit needs explicit observation, including unknown")
            require(all(isinstance(o, dict) for o in obs), "observations must be objects")
            require([o.get("session_id") for o in obs] == ids, "observation schedule must exactly match sessions")
            for o in obs:
                state = o.get("state")
                require(state in {"present", "absent", "unknown"}, "invalid fate state")
                if state != "present":
                    require(all(k not in o for k in ("activity", "sample_hz", "position_um")), "non-present observation cannot supply activity/position")
                    continue
                require(finite(o.get("position_um")) and lo <= o["position_um"] <= hi, "position must be dendritic arc coordinate inside imaged limits")
                require(finite(o.get("sample_hz")) and o["sample_hz"] > 0, "positive sample rate required")
                require(o.get("continuous_complete_session") is True, "trace must explicitly represent one complete continuous session, never concatenated blocks")
                a = o.get("activity")
                require(isinstance(a, list) and len(a) >= 2 and all(type(x) in (int, bool) and x in (0, 1) for x in a), "complete binary activity trace required")
                grid = (len(a), o["sample_hz"])
                require(o["session_id"] not in grids or grids[o["session_id"]] == grid, "simultaneous dendritic traces require identical length/rate")
                grids[o["session_id"]] = grid
    return data


def row_key(row):
    return tuple(row[k] for k in ("mouse_id", "dendrite_id", "spine_id", "session_id"))


def derive(data):
    """Create interval rows without converting unknown fate to retention."""
    validate(data)
    sessions = data["sessions"]
    rows, exclusions = [], []
    for d in data["dendrites"]:
        identity = {k: d[k] for k in ("mouse_id", "dendrite_id")}
        if d["health_status"] != "eligible":
            exclusions.append({**identity, "reason": "dendrite_health_" + d["health_status"], "spines": len(d["spines"])})
            continue
        eligible = []
        baseline_spines = [s for s in d["spines"] if s["observations"][0]["state"] == "present"]
        for spine in d["spines"]:
            states = [o["state"] for o in spine["observations"]]
            reason = None
            if states[0] != "present":
                reason = "not_confirmed_baseline_present"
            elif any(states[i] == "absent" and "present" in states[i + 1:] for i in range(len(states))):
                reason = "reappearance_requires_identity_review"
            if reason:
                exclusions.append({**identity, "spine_id": spine["spine_id"], "reason": reason})
            else:
                eligible.append(spine)
        for i, session in enumerate(sessions):
            present = [(s, s["observations"][i]) for s in baseline_spines if s["observations"][i]["state"] == "present"]
            for spine, obs in present:
                if not any(spine is s for s in eligible):
                    continue
                neighbors = [(s, o) for s, o in present if s is not spine and abs(o["position_um"] - obs["position_um"]) <= 10]
                pairs = [coactivity(obs["activity"], o["activity"]) for _, o in neighbors]
                label = None
                if i + 1 == len(sessions):
                    status, end_day, end_session = "no_next_scheduled_visit", None, None
                else:
                    next_state = spine["observations"][i + 1]["state"]
                    end_day, end_session = sessions[i + 1]["day"], sessions[i + 1]["session_id"]
                    if next_state == "unknown":
                        status = "next_visit_unknown"
                    else:
                        label = int(next_state == "absent"); status = "eliminated_interval" if label else "retained_interval"
                row = {**identity, "spine_id": spine["spine_id"], "session_id": session["session_id"],
                       "start_day": session["day"], "next_session_id": end_session, "end_day": end_day,
                       "label": label, "outcome_status": status, "events_per_min": events(obs["activity"]) * 60 * obs["sample_hz"] / len(obs["activity"]),
                       "local_coactivity": mean(pairs), "neighbor_count": len(neighbors),
                       "eligible_pair_count": sum(p is not None for p in pairs),
                       "zero_activity_pair_count": sum(p is None for p in pairs)}
                rows.append(row)
    # The historical comparison selection uses outcome information, so it is
    # diagnostic only and never removes rows from prospective fitting/scoring.
    event_blocks = {(r["mouse_id"], r["dendrite_id"], r["session_id"]) for r in rows if r["label"] == 1}
    for row in rows:
        row["historical_elimination_block"] = (row["mouse_id"], row["dendrite_id"], row["session_id"]) in event_blocks
    return rows, exclusions


def _weights(rows):
    counts = Counter(r["mouse_id"] for r in rows)
    return np.array([1 / (len(counts) * counts[r["mouse_id"]]) for r in rows], dtype=float)


def _design(train, test, names):
    """Weighted train-only mean/scale; missing values get train mean + indicator."""
    weights = _weights(train)
    means, scales = [], []
    for name in names:
        observed = np.array([r[name] is not None for r in train])
        values = np.array([r[name] if r[name] is not None else 0 for r in train], dtype=float)
        mass = float(weights[observed].sum())
        mu = float(np.dot(weights[observed], values[observed]) / mass) if mass else 0.0
        sd = math.sqrt(float(np.dot(weights[observed], (values[observed] - mu) ** 2) / mass)) if mass else 1.0
        means.append(mu); scales.append(sd if sd > 1e-12 else 1.0)
    def transform(rows):
        matrix = [[1.0] for _ in rows]
        for j, name in enumerate(names):
            for values, row in zip(matrix, rows):
                missing = row[name] is None
                values.extend([0.0 if missing else (row[name] - means[j]) / scales[j], float(missing)])
        return np.array(matrix, dtype=float)
    return transform(train), transform(test), {"features": list(names), "means": means, "scales": scales}


def _sigmoid(x):
    return np.exp(-np.logaddexp(0, -x))


def _fit(x, y, w):
    # Frozen v1 ridge 1 on standardized features/missing indicators; weak
    # intercept regularization ensures a finite solution on one-class folds.
    penalty = np.ones(x.shape[1]); penalty[0] = 1e-6
    beta = np.zeros(x.shape[1])
    def objective(b):
        z = x @ b
        return float(np.dot(w, np.logaddexp(0, z) - y * z) + .5 * np.dot(penalty * b, b))
    for iteration in range(100):
        p = _sigmoid(x @ beta)
        grad = x.T @ (w * (p - y)) + penalty * beta
        if np.max(np.abs(grad)) < 1e-10:
            return beta, iteration
        hessian = x.T @ ((w * p * (1 - p))[:, None] * x) + np.diag(penalty)
        step = np.linalg.solve(hessian, grad)
        old, rate = objective(beta), 1.0
        while rate > 2 ** -30:
            candidate = beta - rate * step
            if objective(candidate) <= old - 1e-4 * rate * float(grad @ step):
                beta = candidate; break
            rate *= .5
        else:
            raise ContractError("logistic fit did not find a descending step")
    raise ContractError("logistic fit failed to converge within 100 iterations")


def fit_predict(rows):
    labeled = [r for r in rows if r["label"] is not None]
    mice = sorted(set(r["mouse_id"] for r in labeled))
    require(len(mice) >= 3, "at least three mice with known next-visit outcomes required for leave-mouse-out evaluation")
    predictions = {name: [] for name in MODELS}; folds = []
    for mouse in mice:
        train = [r for r in labeled if r["mouse_id"] != mouse]
        test = [r for r in rows if r["mouse_id"] == mouse and r["next_session_id"] is not None]
        fold = {"test_mouse": mouse, "train_mice": sorted(set(r["mouse_id"] for r in train)), "models": {}}
        for model, names in MODELS.items():
            x, xt, transform = _design(train, test, names)
            beta, iterations = _fit(x, np.array([r["label"] for r in train]), _weights(train))
            for row, p in zip(test, _sigmoid(xt @ beta)):
                predictions[model].append({"key": list(row_key(row)), "probability": float(p)})
            fold["models"][model] = {**transform, "coefficients": beta.tolist(), "iterations": iterations,
                                       "training_rows": len(train)}
        folds.append(fold)
    # Entirely censored mice cannot be evaluated and are explicit, not silently scored.
    unscorable = sorted(set(r["mouse_id"] for r in rows) - set(mice))
    return predictions, folds, unscorable


def _auc(labels, scores):
    positive = [s for y, s in zip(labels, scores) if y == 1]
    negative = [s for y, s in zip(labels, scores) if y == 0]
    if not positive or not negative:
        return None
    return sum((a > b) + .5 * (a == b) for a in positive for b in negative) / (len(positive) * len(negative))


def score(rows, predictions):
    """Strict complete coverage of the declared evaluation mice, with no joins by position."""
    mice = {r["mouse_id"] for r in rows if r["label"] is not None}
    expected = {row_key(r): r for r in rows if r["mouse_id"] in mice and r["next_session_id"] is not None}
    require(len(expected) == sum(r["mouse_id"] in mice and r["next_session_id"] is not None for r in rows), "duplicate interval rows")
    found = {}
    for p in predictions:
        require(isinstance(p, dict) and isinstance(p.get("key"), list) and len(p["key"]) == 4 and all(nonempty(x) for x in p["key"]), "invalid prediction identity")
        key = tuple(p["key"])
        require(key in expected and key not in found, "extra or duplicate prediction")
        require(finite(p.get("probability")) and 0 <= p["probability"] <= 1, "probability must be finite in [0,1]")
        found[key] = p["probability"]
    require(set(found) == set(expected), "predictions must cover every scheduled interval, including censored rows")
    by_mouse = defaultdict(list)
    for key, row in expected.items():
        if row["label"] is not None:
            by_mouse[row["mouse_id"]].append((row["label"], found[key]))
    per_mouse = []
    for mouse, pairs in sorted(by_mouse.items()):
        ys, ps = zip(*pairs)
        losses = [-y * math.log(max(p, 1e-15)) - (1-y) * math.log(max(1-p, 1e-15)) for y, p in pairs]
        per_mouse.append({"mouse_id": mouse, "rows": len(pairs), "events": sum(ys),
                          "brier": mean((p-y)**2 for y,p in pairs), "log_loss": mean(losses),
                          "calibration_bias": mean(p-y for y,p in pairs), "auc": _auc(ys, ps)})
    macro = {name: mean(r[name] for r in per_mouse) for name in ("brier", "log_loss", "calibration_bias", "auc")}
    # Equal-mouse weighted fixed-decile reliability table, no test-set bin selection.
    bins = []
    for b in range(10):
        entries = [(y, p, 1/(len(by_mouse)*len(pairs))) for pairs in by_mouse.values() for y,p in pairs if min(int(p*10),9) == b]
        mass = sum(w for _,_,w in entries)
        bins.append({"lower": b/10, "upper": (b+1)/10, "right_closed": b == 9, "rows": len(entries),
                     "weight": mass, "mean_probability": sum(p*w for _,p,w in entries)/mass if mass else None,
                     "event_fraction": sum(y*w for y,_,w in entries)/mass if mass else None})
    return {"primary": "equal_mouse_mean_brier", "equal_mouse": macro, "per_mouse": per_mouse,
            "auc_defined_mice": sum(r["auc"] is not None for r in per_mouse), "reliability_deciles": bins,
            "known_rows": sum(len(v) for v in by_mouse.values()), "censored_rows": sum(r["label"] is None for r in expected.values()),
            "probability_clip_for_log_loss": 1e-15}


def contrasts(rows):
    result = {}
    for feature in ("events_per_min", "local_coactivity"):
        mice = []
        for mouse in sorted(set(r["mouse_id"] for r in rows)):
            selected = [r for r in rows if r["mouse_id"] == mouse and r["historical_elimination_block"] and r["label"] is not None]
            retained = [r[feature] for r in selected if r["label"] == 0 and r[feature] is not None]
            eliminated = [r[feature] for r in selected if r["label"] == 1 and r[feature] is not None]
            a, b = mean(retained), mean(eliminated)
            mice.append({"mouse_id": mouse, "retained_rows": len(retained), "eliminated_rows": len(eliminated),
                         "retained_mean": a, "eliminated_mean": b, "difference_eliminated_minus_retained": b-a if a is not None and b is not None else None})
        result[feature] = {"per_mouse": mice, "equal_mouse_mean_difference": mean(r["difference_eliminated_minus_retained"] for r in mice),
                           "inferential_status": "descriptive_prospective_aggregation_not_author_fitlme"}
    return result


def evaluate(data):
    rows, exclusions = derive(data)
    predictions, folds, unscorable = fit_predict(rows)
    scores = {name: score(rows, p) for name, p in predictions.items()}
    paired = []
    left = {r["mouse_id"]: r for r in scores["activity"]["per_mouse"]}
    for r in scores["activity_local"]["per_mouse"]:
        paired.append({"mouse_id": r["mouse_id"], "brier_local_minus_activity": r["brier"]-left[r["mouse_id"]]["brier"]})
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return {"schema_version": "rep011-result-v1", "task_id": "PAPER-FIND-REP-011", "cohort": data["cohort"],
            "input_kind": data["provenance"]["kind"], "input_canonical_sha256": hashlib.sha256(encoded).hexdigest(),
            "policy": "prospective_next_scheduled_visit_v1", "scientific_qualification": "unknown", "holds": HOLDS,
            "rows": rows, "exclusions": exclusions, "unscorable_mice_all_intervals_censored": unscorable,
            "population": {"supplied_mice": len(set(d["mouse_id"] for d in data["dendrites"])),
                           "supplied_dendrites": len(data["dendrites"]), "supplied_spines": sum(len(d["spines"]) for d in data["dendrites"]),
                           "interval_rows": sum(r["next_session_id"] is not None for r in rows),
                           "terminal_rows": sum(r["next_session_id"] is None for r in rows),
                           "known_rows": sum(r["label"] is not None for r in rows),
                           "censored_scheduled_rows": sum(r["label"] is None and r["next_session_id"] is not None for r in rows)},
            "folds": folds, "predictions": predictions, "scores": scores, "descriptive_contrasts": contrasts(rows),
            "paired_model_comparison": {"per_mouse": paired, "mean_brier_local_minus_activity": mean(r["brier_local_minus_activity"] for r in paired),
                                        "direction": "negative favors activity_local; no significance or causal claim"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path); parser.add_argument("output", type=Path)
    args = parser.parse_args()
    require(args.input.resolve() != args.output.resolve(), "output must not overwrite input")
    data = json.loads(args.input.read_text())
    result = evaluate(data)
    # Refuse accidental replacement of an existing result.
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False); stream.write("\n")


if __name__ == "__main__":
    main()
